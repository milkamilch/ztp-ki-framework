from unittest.mock import patch

from ki.decision.healing_engine import HealingEngine
from ki.models import AnomalyResult, AnomalyType, HealingAction, Severity
from tests.conftest import make_snapshot


def _engine() -> HealingEngine:
    return HealingEngine(
        ansible_inventory="inventory/hosts.ini",
        redfish_user="admin",
        redfish_password="test",
    )


def _anomaly(anomaly_type: AnomalyType, severity: Severity) -> AnomalyResult:
    return AnomalyResult(
        is_anomaly=True,
        anomaly_type=anomaly_type,
        severity=severity,
        confidence=1.0,
        details="test",
        source="rule",
        raw_snapshot=make_snapshot(),
    )


def test_temp_critical_triggers_power_cycle():
    engine = _engine()
    anomaly = _anomaly(AnomalyType.TEMPERATURE, Severity.CRITICAL)
    with patch.object(engine, "_power_cycle", return_value=(True, "ok")) as mock:
        engine.handle(anomaly, "192.168.1.1")
        mock.assert_called_once()


def test_temp_medium_triggers_alert():
    engine = _engine()
    anomaly = _anomaly(AnomalyType.TEMPERATURE, Severity.MEDIUM)
    with patch.object(engine, "_alert", return_value=(True, "ok")) as mock:
        engine.handle(anomaly, "192.168.1.1")
        mock.assert_called_once()


def test_post_error_high_triggers_retry():
    engine = _engine()
    anomaly = _anomaly(AnomalyType.POST_ERROR, Severity.HIGH)
    with patch.object(engine, "_retry", return_value=(True, "ok")) as mock:
        engine.handle(anomaly, "192.168.1.1")
        mock.assert_called_once()


def test_sel_critical_critical_triggers_rollback():
    engine = _engine()
    anomaly = _anomaly(AnomalyType.SEL_CRITICAL, Severity.CRITICAL)
    with patch.object(engine, "_rollback", return_value=(True, "ok")) as mock:
        engine.handle(anomaly, "192.168.1.1")
        mock.assert_called_once()


def test_unknown_combination_defaults_to_alert():
    engine = _engine()
    # LOW severity ist nicht in der Matrix → ALERT
    anomaly = _anomaly(AnomalyType.TEMPERATURE, Severity.LOW)
    with patch.object(engine, "_alert", return_value=(True, "ok")) as mock:
        engine.handle(anomaly, "192.168.1.1")
        mock.assert_called_once()


def test_handle_records_to_history():
    engine = _engine()
    anomaly = _anomaly(AnomalyType.TEMPERATURE, Severity.MEDIUM)
    with patch.object(engine, "_alert", return_value=(True, "alerted")):
        record = engine.handle(anomaly, "192.168.1.1")
    assert len(engine.history) == 1
    assert engine.history[0] is record
    assert record.action == HealingAction.ALERT
    assert record.success is True


def test_ml_outlier_low_defaults_to_alert():
    """ML_OUTLIER + LOW is not in the decision matrix → defaults to ALERT."""
    engine = _engine()
    anomaly = _anomaly(AnomalyType.ML_OUTLIER, Severity.LOW)
    with patch.object(engine, "_alert", return_value=(True, "ok")) as mock:
        engine.handle(anomaly, "192.168.1.1")
        mock.assert_called_once()
