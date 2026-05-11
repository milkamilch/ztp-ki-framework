from ki.parser.drain3_parser import DrainLogParser
from tests.conftest import make_sel_entry


def test_parse_returns_one_event_per_entry():
    parser = DrainLogParser()
    entries = [
        make_sel_entry("CPU 1 temperature above warning threshold", "Warning"),
        make_sel_entry("Fan 1A speed normal", "OK"),
    ]
    events = parser.parse(entries)
    assert len(events) == 2


def test_parse_preserves_raw_message():
    parser = DrainLogParser()
    msg = "DIMM_A1 correctable ECC error detected"
    events = parser.parse([make_sel_entry(msg, "Warning")])
    assert events[0].raw_message == msg


def test_escalate_severity_on_uncorrectable_ecc():
    parser = DrainLogParser()
    entries = [make_sel_entry("DIMM_A1 uncorrectable ECC error detected", "Warning")]
    events = parser.parse(entries)
    assert events[0].severity == "Critical"


def test_escalate_severity_on_fan_failure():
    parser = DrainLogParser()
    entries = [make_sel_entry("Fan 2A fan failure detected", "Warning")]
    events = parser.parse(entries)
    assert events[0].severity == "Critical"


def test_no_escalation_on_normal_message():
    parser = DrainLogParser()
    entries = [make_sel_entry("System boot completed successfully", "OK")]
    events = parser.parse(entries)
    assert events[0].severity == "OK"


def test_drain_clusters_similar_messages():
    """Gleiche Log-Struktur mit unterschiedlichen DIMM-Bezeichnern → selbes Template."""
    parser = DrainLogParser()
    entries = [
        make_sel_entry("DIMM_A1 correctable ECC error", "Warning"),
        make_sel_entry("DIMM_B2 correctable ECC error", "Warning"),
        make_sel_entry("DIMM_C3 correctable ECC error", "Warning"),
    ]
    events = parser.parse(entries)
    template_ids = {e.template_id for e in events}
    assert len(template_ids) == 1, "Alle drei Einträge sollten dasselbe Template erhalten"
