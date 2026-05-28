from ki.decision.healing_engine import DECISION_MATRIX, HealingAction
from ki.detector.anomaly_detector import AnomalyDetector
from ki.models import AnomalyType, Severity
from ki.parser.drain3_parser import DrainLogParser
from tests.conftest import make_sel_entry, make_snapshot


def _detector() -> AnomalyDetector:
    d = AnomalyDetector()
    d._trained = True
    return d


def _detect(message: str):
    snap = make_snapshot(sel_entries=[make_sel_entry(message, severity="Critical")])
    events = DrainLogParser().parse(snap.sel_entries)
    return _detector().detect(snap, events)


def test_boot_timeout_on_watchdog_sel():
    result = _detect("BMC watchdog timeout during POST")
    assert result.anomaly_type == AnomalyType.BOOT_TIMEOUT
    assert result.severity == Severity.HIGH


def test_boot_timeout_on_boot_failure_sel():
    result = _detect("System boot failure detected")
    assert result.anomaly_type == AnomalyType.BOOT_TIMEOUT


def test_boot_timeout_on_timeout_keyword():
    result = _detect("PXE boot timeout after 300 seconds")
    assert result.anomaly_type == AnomalyType.BOOT_TIMEOUT


def test_no_boot_timeout_for_ecc_error():
    result = _detect("DIMM_A1 uncorrectable ECC error")
    assert result.anomaly_type == AnomalyType.SEL_CRITICAL


def test_no_boot_timeout_for_post_error():
    result = _detect("POST error: memory initialization failed")
    assert result.anomaly_type == AnomalyType.POST_ERROR


def test_boot_timeout_in_decision_matrix():
    assert (AnomalyType.BOOT_TIMEOUT, Severity.HIGH) in DECISION_MATRIX
    assert (AnomalyType.BOOT_TIMEOUT, Severity.CRITICAL) in DECISION_MATRIX
    assert DECISION_MATRIX[(AnomalyType.BOOT_TIMEOUT, Severity.HIGH)] == HealingAction.RETRY
    assert DECISION_MATRIX[(AnomalyType.BOOT_TIMEOUT, Severity.CRITICAL)] == HealingAction.ROLLBACK
