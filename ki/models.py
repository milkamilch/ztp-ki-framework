from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Severity(Enum):
    OK       = "ok"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class AnomalyType(Enum):
    NONE         = "none"
    TEMPERATURE  = "temperature"
    FAN          = "fan"
    POWER        = "power"
    SEL_CRITICAL = "sel_critical"
    POST_ERROR   = "post_error"
    ML_OUTLIER   = "ml_outlier"
    BOOT_TIMEOUT = "boot_timeout"


class HealingAction(Enum):
    NONE        = "none"
    RETRY       = "retry"
    REBOOT      = "reboot"
    POWER_CYCLE = "power_cycle"
    ROLLBACK    = "rollback"
    ALERT       = "alert"


@dataclass
class SensorReading:
    name:      str
    value:     float
    unit:      str   # "C", "RPM", "W"
    status:    str   # "OK", "Warning", "Critical"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SelEntry:
    entry_id:    str
    timestamp:   datetime
    message:     str
    severity:    str  # "OK", "Warning", "Critical"
    sensor_type: str = ""


@dataclass
class CollectorSnapshot:
    target:      str
    timestamp:   datetime
    sensors:     list[SensorReading]
    sel_entries: list[SelEntry]
    post_code:   str | None
    power_state: str  # "On", "Off", "PoweringOn", "PoweringOff"


@dataclass
class ParsedLogEvent:
    template_id: int
    template:    str
    params:      list[str]
    raw_message: str
    severity:    str
    timestamp:   datetime


@dataclass
class AnomalyResult:
    is_anomaly:   bool
    anomaly_type: AnomalyType
    severity:     Severity
    confidence:   float  # 0.0 – 1.0
    details:      str
    source:       str    # "rule" | "ml"
    raw_snapshot: CollectorSnapshot | None = None


@dataclass
class HealingRecord:
    timestamp: datetime
    target:    str
    anomaly:   AnomalyResult
    action:    HealingAction
    success:   bool
    message:   str
