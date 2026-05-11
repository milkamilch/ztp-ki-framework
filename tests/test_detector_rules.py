from ki.detector.anomaly_detector import AnomalyDetector
from ki.models import AnomalyType, Severity
from tests.conftest import (
    make_snapshot, make_temp_sensor, make_fan_sensor,
    make_power_sensor, make_sel_entry,
)


def _detector() -> AnomalyDetector:
    return AnomalyDetector()


def test_normal_sensors_return_ok():
    snapshot = make_snapshot(sensors=[
        make_temp_sensor("CPU 1", 45.0),
        make_fan_sensor("Fan 1", 6000.0),
        make_power_sensor("PSU", 350.0),
    ])
    result = _detector().detect(snapshot, [])
    assert result.is_anomaly is False
    assert result.severity == Severity.OK


def test_temp_above_warn_threshold_returns_medium():
    snapshot = make_snapshot(sensors=[make_temp_sensor("CPU 1", 78.0)])
    result = _detector().detect(snapshot, [])
    assert result.is_anomaly is True
    assert result.severity == Severity.MEDIUM
    assert result.anomaly_type == AnomalyType.TEMPERATURE


def test_temp_above_critical_threshold_returns_critical():
    snapshot = make_snapshot(sensors=[make_temp_sensor("CPU 1", 87.0)])
    result = _detector().detect(snapshot, [])
    assert result.is_anomaly is True
    assert result.severity == Severity.CRITICAL
    assert result.anomaly_type == AnomalyType.TEMPERATURE


def test_fan_below_min_rpm_returns_high():
    snapshot = make_snapshot(sensors=[make_fan_sensor("Fan 2A", 200.0)])
    result = _detector().detect(snapshot, [])
    assert result.is_anomaly is True
    assert result.severity == Severity.HIGH
    assert result.anomaly_type == AnomalyType.FAN


def test_power_above_max_returns_medium():
    snapshot = make_snapshot(sensors=[make_power_sensor("PSU", 1300.0)])
    result = _detector().detect(snapshot, [])
    assert result.is_anomaly is True
    assert result.severity == Severity.MEDIUM
    assert result.anomaly_type == AnomalyType.POWER


def test_fan_at_zero_rpm_not_flagged():
    """RPM == 0 bedeutet Sensor nicht vorhanden, nicht Ausfall (0 < FAN_MIN_RPM prüft > 0)."""
    snapshot = make_snapshot(sensors=[make_fan_sensor("Fan X", 0.0)])
    result = _detector().detect(snapshot, [])
    assert result.is_anomaly is False


def test_critical_rule_overrides_ml_warmup():
    """Regelbasiertes CRITICAL-Ergebnis wird zurückgegeben, auch während ML-Warmup."""
    from ki.parser.drain3_parser import DrainLogParser
    parser = DrainLogParser()
    sel = [make_sel_entry("DIMM_A1 uncorrectable ECC error detected", "Warning")]
    events = parser.parse(sel)
    snapshot = make_snapshot(
        sensors=[make_temp_sensor("CPU 1", 45.0)],
        sel_entries=sel,
    )
    result = _detector().detect(snapshot, events)
    assert result.is_anomaly is True
    assert result.severity == Severity.HIGH
    assert result.source == "rule"


def test_ml_severity_overrides_rule_when_higher():
    """Wenn ML-Severity > Regel-Severity, wird ML-Ergebnis zurückgegeben."""
    from unittest.mock import MagicMock
    import numpy as np

    detector = AnomalyDetector()
    # Inject a trained ML model that returns a strong anomaly (HIGH severity)
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([-1])
    mock_model.score_samples.return_value = np.array([-0.4])  # → HIGH
    detector._model = mock_model
    detector._trained = True

    # Rule check: normal temperature → OK
    snapshot = make_snapshot(sensors=[make_temp_sensor("CPU 1", 45.0)])
    result = detector.detect(snapshot, [])

    assert result.is_anomaly is True
    assert result.severity == Severity.HIGH
    assert result.source == "ml"
