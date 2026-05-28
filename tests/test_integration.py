"""
End-to-End-Integrationstest der kompletten KI-Pipeline.

Startet den Mock-BMC-Server und spielt alle 6 Szenarien durch.
Prüft: Collector → Parser → Detector → DECISION_MATRIX liefert
die erwarteten AnomalyType und HealingAction je Szenario.

ML-Warmup: Detector läuft im Default-Modus (kein _trained-Override).
Bei HIGH/CRITICAL-Schweregrad kehrt detect() vor dem ML-Check zurück.
Bei MEDIUM/OK läuft der ML-Warmup-Pfad (sammelt Samples, keine Vorhersage).
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
import requests
import uvicorn

from ki.collector.redfish_collector import RedfishCollector
from ki.decision.healing_engine import DECISION_MATRIX, HealingAction
from ki.detector.anomaly_detector import AnomalyDetector
from ki.models import AnomalyType
from ki.parser.drain3_parser import DrainLogParser

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 8765


@pytest.fixture(scope="module")
def mock_bmc_target():
    """Startet Mock-BMC-Server einmal für alle Tests im Modul."""
    config = uvicorn.Config(
        "tests.mock_bmc.server:app",
        host=MOCK_HOST,
        port=MOCK_PORT,
        log_level="error",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(40):
        try:
            requests.get(f"http://{MOCK_HOST}:{MOCK_PORT}/control/active", timeout=1)
            break
        except requests.ConnectionError:
            time.sleep(0.2)
    else:
        pytest.fail("Mock-BMC-Server nicht erreichbar nach dem Start")

    return f"{MOCK_HOST}:{MOCK_PORT}"


@pytest.fixture(scope="module")
def pipeline():
    collector = RedfishCollector(username="admin", password="test",
                                 timeout=5, scheme="http")
    parser    = DrainLogParser()
    detector  = AnomalyDetector()  # Warmup-Modus — kein trainiertes Modell nötig
    return collector, parser, detector


def _set_scenario(name: str) -> None:
    requests.post(f"http://{MOCK_HOST}:{MOCK_PORT}/control/scenario/{name}", timeout=5)


def _run(mock_bmc_target, pipeline):
    collector, parser, detector = pipeline
    snapshot = collector.collect(mock_bmc_target)
    events   = parser.parse(snapshot.sel_entries)
    result   = detector.detect(snapshot, events)
    action   = DECISION_MATRIX.get((result.anomaly_type, result.severity), HealingAction.NONE)
    return result, action


@pytest.mark.parametrize("scenario,expected_type,expected_action", [
    ("normal",        AnomalyType.NONE,         HealingAction.NONE),
    ("temp_warning",  AnomalyType.TEMPERATURE,  HealingAction.ALERT),
    ("temp_critical", AnomalyType.TEMPERATURE,  HealingAction.POWER_CYCLE),
    ("fan_failure",   AnomalyType.FAN,          HealingAction.REBOOT),
    ("sel_critical",  AnomalyType.SEL_CRITICAL, HealingAction.REBOOT),
    ("post_error",    AnomalyType.POST_ERROR,   HealingAction.RETRY),
])
def test_scenario(mock_bmc_target, pipeline, scenario, expected_type, expected_action):
    _set_scenario(scenario)
    time.sleep(0.05)

    result, action = _run(mock_bmc_target, pipeline)

    assert result.anomaly_type == expected_type, (
        f"Szenario '{scenario}': Typ erwartet={expected_type.value}, "
        f"bekommen={result.anomaly_type.value} — {result.details}"
    )
    if expected_type == AnomalyType.NONE:
        assert result.is_anomaly is False
    else:
        assert result.is_anomaly is True
        assert action == expected_action, (
            f"Szenario '{scenario}': Aktion erwartet={expected_action.value}, bekommen={action.value}"
        )
