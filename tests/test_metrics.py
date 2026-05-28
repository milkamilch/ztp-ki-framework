"""Tests für das Prometheus-Metriken-Modul."""


def _sample_value(metric_name: str, labels: dict) -> float:
    """Liest den aktuellen Wert einer Prometheus-Metrik aus der Registry.

    Prometheus-Client 0.20+ hängt bei Countern ein _total-Suffix an den
    Sample-Namen — wir suchen deshalb nach sample.name, nicht mf.name.
    """
    from prometheus_client import REGISTRY
    for mf in REGISTRY.collect():
        for sample in mf.samples:
            if sample.name == metric_name and all(sample.labels.get(k) == v for k, v in labels.items()):
                return sample.value
    return 0.0


def test_anomaly_counter_increments():
    from ki.metrics import record_anomaly
    before = _sample_value("ztp_anomaly_total", {"target": "1.1.1.1", "anomaly_type": "temperature", "severity": "high"})
    record_anomaly(target="1.1.1.1", anomaly_type="temperature", severity="high")
    after = _sample_value("ztp_anomaly_total", {"target": "1.1.1.1", "anomaly_type": "temperature", "severity": "high"})
    assert after == before + 1.0


def test_healing_counter_increments():
    from ki.metrics import record_healing
    before = _sample_value("ztp_healing_action_total", {"target": "1.1.1.2", "action": "reboot", "success": "true"})
    record_healing(target="1.1.1.2", action="reboot", success=True)
    after = _sample_value("ztp_healing_action_total", {"target": "1.1.1.2", "action": "reboot", "success": "true"})
    assert after == before + 1.0


def test_poll_error_counter_increments():
    from ki.metrics import record_poll_error
    before = _sample_value("ztp_poll_errors_total", {"target": "1.1.1.99"})
    record_poll_error(target="1.1.1.99")
    after = _sample_value("ztp_poll_errors_total", {"target": "1.1.1.99"})
    assert after == before + 1.0


def test_poll_duration_context_manager_records():
    from ki.metrics import poll_timer
    before = _sample_value("ztp_poll_duration_seconds_count", {"target": "1.1.1.1"})
    with poll_timer("1.1.1.1"):
        pass
    after = _sample_value("ztp_poll_duration_seconds_count", {"target": "1.1.1.1"})
    assert after == before + 1.0
