"""
Simulations-Script für den KI-Self-Healing-Layer.

Startet den Mock-BMC-Server im Hintergrund und spielt automatisch alle
Szenarien durch. Für jedes Szenario wird die komplette Pipeline ausgeführt
(Collector → Parser → Detector) und das Ergebnis mit der zugehörigen
Healing-Aktion ausgegeben — ohne echte Ansible- oder Redfish-Befehle
auszuführen (Dry-Run-Modus).

Verwendung:
    cd ztp-ki-framework
    python -m tests.simulate

Voraussetzung:
    pip install -r tests/requirements.txt
"""
from __future__ import annotations

import sys
import time
import threading
from pathlib import Path

import requests
import uvicorn

# Projektpfad für Imports setzen
sys.path.insert(0, str(Path(__file__).parent.parent))

from ki.collector.redfish_collector import RedfishCollector
from ki.decision.healing_engine import DECISION_MATRIX, HealingAction
from ki.detector.anomaly_detector import AnomalyDetector
from ki.models import AnomalyType, Severity
from ki.parser.drain3_parser import DrainLogParser
from tests.mock_bmc.scenarios import SCENARIOS

# ──────────────────────────────────────────
# Konfiguration
# ──────────────────────────────────────────
MOCK_HOST = "127.0.0.1"
MOCK_PORT = 8888
MOCK_BASE = f"http://{MOCK_HOST}:{MOCK_PORT}"

SCENARIO_PAUSE = 3   # Sekunden zwischen den Szenarien

# Reihenfolge der Demo-Szenarien
DEMO_ORDER = [
    "normal",
    "temp_warning",
    "temp_critical",
    "fan_failure",
    "sel_critical",
    "post_error",
]

# ANSI-Farben für die Ausgabe
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

SEVERITY_COLOR = {
    Severity.OK:       GREEN,
    Severity.LOW:      GREEN,
    Severity.MEDIUM:   YELLOW,
    Severity.HIGH:     RED,
    Severity.CRITICAL: RED + BOLD,
}

ACTION_COLOR = {
    HealingAction.NONE:        GREEN,
    HealingAction.ALERT:       YELLOW,
    HealingAction.RETRY:       YELLOW,
    HealingAction.REBOOT:      RED,
    HealingAction.POWER_CYCLE: RED + BOLD,
    HealingAction.ROLLBACK:    RED + BOLD,
}


# ──────────────────────────────────────────
# Mock-Server starten
# ──────────────────────────────────────────

def start_mock_server() -> None:
    """Startet den Mock-BMC-Server in einem Daemon-Thread."""
    config = uvicorn.Config(
        "tests.mock_bmc.server:app",
        host=MOCK_HOST,
        port=MOCK_PORT,
        log_level="error",   # Uvicorn-Logs unterdrücken während der Demo
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()


def wait_for_server(retries: int = 20) -> None:
    """Wartet, bis der Mock-Server HTTP-Anfragen beantwortet."""
    for _ in range(retries):
        try:
            requests.get(f"{MOCK_BASE}/control/active", timeout=1)
            return
        except requests.ConnectionError:
            time.sleep(0.3)
    raise RuntimeError("Mock-BMC-Server nicht erreichbar nach dem Start.")


def set_scenario(name: str) -> None:
    """Wechselt das aktive Szenario auf dem Mock-Server."""
    requests.post(f"{MOCK_BASE}/control/scenario/{name}", timeout=5)


# ──────────────────────────────────────────
# Pipeline ausführen (Dry-Run)
# ──────────────────────────────────────────

def run_pipeline(
    collector: RedfishCollector,
    parser:    DrainLogParser,
    detector:  AnomalyDetector,
    target:    str,
) -> None:
    """Führt einen einzelnen Pipeline-Zyklus aus und gibt das Ergebnis aus.

    Dry-Run: Die HealingEngine wird nicht aufgerufen. Stattdessen wird
    die zugehörige Aktion aus der Entscheidungsmatrix nachgeschlagen und
    angezeigt, ohne sie wirklich auszuführen.
    """
    snapshot = collector.collect(target)
    events   = parser.parse(snapshot.sel_entries)
    result   = detector.detect(snapshot, events)

    action = DECISION_MATRIX.get(
        (result.anomaly_type, result.severity),
        HealingAction.NONE,
    ) if result.is_anomaly else HealingAction.NONE

    sev_col    = SEVERITY_COLOR.get(result.severity, RESET)
    action_col = ACTION_COLOR.get(action, RESET)

    status = f"{RED}ANOMALIE{RESET}" if result.is_anomaly else f"{GREEN}OK{RESET}"

    print(f"  Status:    {status}")
    print(f"  Typ:       {result.anomaly_type.value}")
    print(f"  Schwere:   {sev_col}{result.severity.value}{RESET}")
    print(f"  Quelle:    {result.source}")
    print(f"  Details:   {result.details}")
    if result.is_anomaly:
        print(f"  → Aktion:  {action_col}{BOLD}{action.value.upper()}{RESET}")


# ──────────────────────────────────────────
# Demo-Ablauf
# ──────────────────────────────────────────

def print_sensors(target: str) -> None:
    """Zeigt eine kompakte Sensor-Übersicht für den aktuellen Snapshot."""
    try:
        thermal = requests.get(f"{MOCK_BASE}/redfish/v1/Chassis/1/Thermal", timeout=3).json()
        power   = requests.get(f"{MOCK_BASE}/redfish/v1/Chassis/1/Power",   timeout=3).json()
        sel     = requests.get(
            f"{MOCK_BASE}/redfish/v1/Systems/1/LogServices/Sel/Entries", timeout=3
        ).json()

        temps = [(t["Name"], t["ReadingCelsius"]) for t in thermal.get("Temperatures", [])]
        fans  = [(f["Name"], f["ReadingRPM"])     for f in thermal.get("Fans", [])]
        pw    = power.get("PowerControl", [{}])[0].get("PowerConsumedWatts", "–")
        sel_c = len(sel.get("Members", []))

        print(f"  Temperaturen: " + "  ".join(f"{n}: {v}°C" for n, v in temps))
        print(f"  Lüfter:       " + "  ".join(f"{n}: {v} RPM" for n, v in fans))
        print(f"  Leistung:     {pw} W   SEL-Einträge: {sel_c}")
    except Exception:
        print("  (Sensordaten nicht abrufbar)")


def run_demo() -> None:
    """Startet die vollständige Simulation aller Szenarien."""
    print(f"\n{BOLD}{BLUE}{'═' * 60}{RESET}")
    print(f"{BOLD}{BLUE}  ZTP-KI-Framework — Simulations-Demo{RESET}")
    print(f"{BOLD}{BLUE}{'═' * 60}{RESET}\n")

    print("Starte Mock-BMC-Server ...")
    start_mock_server()
    wait_for_server()
    print(f"Mock-BMC läuft auf {MOCK_BASE}\n")

    target    = f"{MOCK_HOST}:{MOCK_PORT}"
    collector = RedfishCollector(username="admin", password="test",
                                 timeout=5, scheme="http")
    parser    = DrainLogParser()
    detector  = AnomalyDetector(model_path=Path("tests/model_test.joblib"))

    for scenario_name in DEMO_ORDER:
        scenario = SCENARIOS[scenario_name]
        set_scenario(scenario_name)

        print(f"{BOLD}{'─' * 60}{RESET}")
        print(f"{BOLD}Szenario: {scenario_name}{RESET}  —  {scenario.description}")
        print_sensors(target)
        print()
        run_pipeline(collector, parser, detector, target)
        print()

        if scenario_name != DEMO_ORDER[-1]:
            time.sleep(SCENARIO_PAUSE)

    print(f"{BOLD}{BLUE}{'═' * 60}{RESET}")
    print(f"{BOLD}{GREEN}Demo abgeschlossen.{RESET}")
    print()
    print("Hinweis ML-Warmup: Der Isolation Forest braucht 50 Samples")
    print("zum Trainieren. In der Demo ist er noch im Warmup-Modus —")
    print("die Erkennung basiert ausschließlich auf Regeln.")
    print("Für ML-Tests: Script mehrfach laufen lassen oder")
    print(f"`tests/model_test.joblib` löschen und 50+ Zyklen sammeln.\n")


if __name__ == "__main__":
    run_demo()
