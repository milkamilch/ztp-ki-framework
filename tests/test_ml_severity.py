"""
Der Isolation Forest soll je nach Score die Severity eskalieren:
  score >= -0.1  → LOW   (marginaler Ausreißer)
  score  < -0.1  → MEDIUM
  score  < -0.3  → HIGH
"""
from unittest.mock import MagicMock, patch
import numpy as np

from ki.detector.anomaly_detector import AnomalyDetector
from ki.models import Severity

from tests.conftest import make_snapshot, make_temp_sensor


def _trained_detector() -> AnomalyDetector:
    """Gibt einen Detector zurück der bereits trainiert ist (kein Warmup)."""
    detector = AnomalyDetector()
    mock_model = MagicMock()
    detector._model = mock_model
    detector._trained = True
    return detector


def test_ml_low_severity_for_marginal_outlier():
    detector = _trained_detector()
    # predict=-1 (Anomalie), score=-0.05 (marginal)
    detector._model.predict.return_value = np.array([-1])
    detector._model.score_samples.return_value = np.array([-0.05])

    snapshot = make_snapshot(sensors=[make_temp_sensor("CPU", 50.0)])
    result = detector._ml_check([50.0, 50.0, 6000.0, 6000.0, 350.0, 0.0], snapshot)

    assert result.is_anomaly is True
    assert result.severity == Severity.LOW


def test_ml_medium_severity_for_moderate_outlier():
    detector = _trained_detector()
    detector._model.predict.return_value = np.array([-1])
    detector._model.score_samples.return_value = np.array([-0.2])

    snapshot = make_snapshot(sensors=[make_temp_sensor("CPU", 50.0)])
    result = detector._ml_check([50.0, 50.0, 6000.0, 6000.0, 350.0, 0.0], snapshot)

    assert result.is_anomaly is True
    assert result.severity == Severity.MEDIUM


def test_ml_high_severity_for_strong_outlier():
    detector = _trained_detector()
    detector._model.predict.return_value = np.array([-1])
    detector._model.score_samples.return_value = np.array([-0.4])

    snapshot = make_snapshot(sensors=[make_temp_sensor("CPU", 50.0)])
    result = detector._ml_check([50.0, 50.0, 6000.0, 6000.0, 350.0, 0.0], snapshot)

    assert result.is_anomaly is True
    assert result.severity == Severity.HIGH


def test_ml_ok_when_not_anomaly():
    detector = _trained_detector()
    detector._model.predict.return_value = np.array([1])
    detector._model.score_samples.return_value = np.array([0.1])

    snapshot = make_snapshot(sensors=[make_temp_sensor("CPU", 50.0)])
    result = detector._ml_check([50.0, 50.0, 6000.0, 6000.0, 350.0, 0.0], snapshot)

    assert result.is_anomaly is False
    assert result.severity == Severity.OK


def test_ml_boundary_at_minus_0_1_is_low():
    """score == -0.1 maps to LOW (exclusive boundary: < -0.1 is MEDIUM)."""
    detector = _trained_detector()
    detector._model.predict.return_value = np.array([-1])
    detector._model.score_samples.return_value = np.array([-0.1])

    snapshot = make_snapshot(sensors=[make_temp_sensor("CPU", 50.0)])
    result = detector._ml_check([50.0, 50.0, 6000.0, 6000.0, 350.0, 0.0], snapshot)

    assert result.is_anomaly is True
    assert result.severity == Severity.LOW


def test_ml_boundary_at_minus_0_3_is_medium():
    """score == -0.3 maps to MEDIUM (exclusive boundary: < -0.3 is HIGH)."""
    detector = _trained_detector()
    detector._model.predict.return_value = np.array([-1])
    detector._model.score_samples.return_value = np.array([-0.3])

    snapshot = make_snapshot(sensors=[make_temp_sensor("CPU", 50.0)])
    result = detector._ml_check([50.0, 50.0, 6000.0, 6000.0, 350.0, 0.0], snapshot)

    assert result.is_anomaly is True
    assert result.severity == Severity.MEDIUM
