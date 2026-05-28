"""
Prometheus-Metriken für den KI-Self-Healing-Layer.

Exportiert vier Metriken:
  ztp_anomaly_total          — Anzahl erkannter Anomalien (Counter)
  ztp_healing_action_total   — Anzahl ausgeführter Heilungsaktionen (Counter)
  ztp_poll_errors_total      — Anzahl fehlgeschlagener Poll-Zyklen (Counter)
  ztp_poll_duration_seconds  — Dauer eines Poll-Zyklus (Histogram)

Verwendung:
  from ki.metrics import record_anomaly, record_healing, record_poll_error, poll_timer
  record_anomaly("192.168.1.1", "temperature", "high")
  with poll_timer("192.168.1.1"):
      ...
"""
from __future__ import annotations

from contextlib import contextmanager

from prometheus_client import Counter, Histogram

_ANOMALY_COUNTER = Counter(
    "ztp_anomaly_total",
    "Anzahl erkannter Anomalien",
    ["target", "anomaly_type", "severity"],
)

_HEALING_COUNTER = Counter(
    "ztp_healing_action_total",
    "Anzahl ausgeführter Healing-Aktionen",
    ["target", "action", "success"],
)

_POLL_ERRORS = Counter(
    "ztp_poll_errors_total",
    "Anzahl fehlgeschlagener Poll-Zyklen",
    ["target"],
)

_POLL_DURATION = Histogram(
    "ztp_poll_duration_seconds",
    "Dauer eines Poll-Zyklus in Sekunden",
    ["target"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)


def record_anomaly(target: str, anomaly_type: str, severity: str) -> None:
    """Zählt eine erkannte Anomalie in der Prometheus-Metrik."""
    _ANOMALY_COUNTER.labels(
        target=target, anomaly_type=anomaly_type, severity=severity
    ).inc()


def record_healing(target: str, action: str, success: bool) -> None:
    """Zählt eine ausgeführte Healing-Aktion in der Prometheus-Metrik."""
    _HEALING_COUNTER.labels(
        target=target, action=action, success=str(success).lower()
    ).inc()


def record_poll_error(target: str) -> None:
    """Zählt einen fehlgeschlagenen Poll-Zyklus."""
    _POLL_ERRORS.labels(target=target).inc()


@contextmanager
def poll_timer(target: str):
    """Context-Manager: misst die Dauer eines Poll-Zyklus."""
    with _POLL_DURATION.labels(target=target).time():
        yield
