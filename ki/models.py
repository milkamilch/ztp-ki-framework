"""
Gemeinsame Datenmodelle für den KI-Self-Healing-Layer.

Alle Module importieren ihre Typen von hier — kein zirkulärer Import möglich.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Severity(Enum):
    """Schweregrad einer erkannten Anomalie, aufsteigend sortiert."""
    OK       = "ok"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class AnomalyType(Enum):
    """Klassifikation der Anomalie-Ursache für die Entscheidungsmatrix."""
    NONE         = "none"
    TEMPERATURE  = "temperature"
    FAN          = "fan"
    POWER        = "power"
    SEL_CRITICAL = "sel_critical"
    POST_ERROR   = "post_error"
    ML_OUTLIER   = "ml_outlier"
    BOOT_TIMEOUT = "boot_timeout"


class HealingAction(Enum):
    """Mögliche Heilungsaktionen, die der HealingEngine ausführen kann."""
    NONE        = "none"
    RETRY       = "retry"        # Provisionierungsschritt wiederholen
    REBOOT      = "reboot"       # Graceful Restart via Redfish
    POWER_CYCLE = "power_cycle"  # Forced Restart via Redfish
    ROLLBACK    = "rollback"     # Vollständige Neu-Provisionierung per PXE
    ALERT       = "alert"        # Nur Benachrichtigung, kein Eingriff


@dataclass
class SensorReading:
    """Ein einzelner Sensor-Messwert aus der Redfish- oder IPMI-Abfrage."""
    name:      str
    value:     float
    unit:      str   # "C" für Temperatur, "RPM" für Lüfter, "W" für Leistung
    status:    str   # "OK", "Warning" oder "Critical" laut BMC
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SelEntry:
    """Ein Eintrag aus dem System Event Log (SEL) des BMC."""
    entry_id:    str
    timestamp:   datetime
    message:     str
    severity:    str  # "OK", "Warning", "Critical"
    sensor_type: str = ""


@dataclass
class CollectorSnapshot:
    """Vollständiger Datenpunkt eines Servers zu einem Zeitpunkt.

    Wird vom RedfishCollector erzeugt und durch die gesamte Pipeline weitergereicht.
    """
    target:      str              # IP-Adresse des BMC
    timestamp:   datetime
    sensors:     list[SensorReading]
    sel_entries: list[SelEntry]
    post_code:   str | None       # Aktueller POST-Code (None wenn nicht verfügbar)
    power_state: str              # "On", "Off", "PoweringOn", "PoweringOff"


@dataclass
class ParsedLogEvent:
    """Ein strukturiertes Log-Ereignis nach Verarbeitung durch den Drain3-Parser."""
    template_id: int        # Eindeutige ID des erkannten Log-Templates
    template:    str        # Template-Text, z. B. "DIMM * correctable ECC error"
    params:      list[str]  # Extrahierte variable Teile aus dem Template
    raw_message: str
    severity:    str        # Kann durch CRITICAL_KEYWORDS auf "Critical" eskaliert werden
    timestamp:   datetime


@dataclass
class AnomalyResult:
    """Ergebnis der Anomalie-Erkennung für einen Snapshot.

    Enthält sowohl das Urteil (is_anomaly) als auch alle Infos für die
    Entscheidungsmatrix (anomaly_type + severity) und das Audit-Log (details, source).
    """
    is_anomaly:   bool
    anomaly_type: AnomalyType
    severity:     Severity
    confidence:   float           # 0.0 = keine Aussage, 1.0 = sicher
    details:      str             # Menschenlesbare Erklärung für das Log
    source:       str             # "rule" oder "ml"
    raw_snapshot: CollectorSnapshot | None = None


@dataclass
class HealingRecord:
    """Protokoll-Eintrag einer ausgeführten Heilungsaktion.

    Wird in HealingEngine.history gespeichert und kann für Audits
    oder Grafana-Dashboards exportiert werden.
    """
    timestamp: datetime
    target:    str
    anomaly:   AnomalyResult
    action:    HealingAction
    success:   bool
    message:   str
