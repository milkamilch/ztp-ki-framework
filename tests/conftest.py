from datetime import datetime, timezone

import pytest

from ki.models import (
    CollectorSnapshot, SelEntry, SensorReading,
)


def _ts() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_snapshot(
    sensors: list[SensorReading] | None = None,
    sel_entries: list[SelEntry] | None = None,
    power_state: str = "On",
    post_code: str | None = None,
    target: str = "192.168.1.1",
) -> CollectorSnapshot:
    return CollectorSnapshot(
        target=target,
        timestamp=_ts(),
        sensors=sensors or [],
        sel_entries=sel_entries or [],
        post_code=post_code,
        power_state=power_state,
    )


def make_temp_sensor(name: str, value: float, status: str = "OK") -> SensorReading:
    return SensorReading(name=name, value=value, unit="C", status=status, timestamp=_ts())


def make_fan_sensor(name: str, rpm: float, status: str = "OK") -> SensorReading:
    return SensorReading(name=name, value=rpm, unit="RPM", status=status, timestamp=_ts())


def make_power_sensor(name: str, watts: float) -> SensorReading:
    return SensorReading(name=name, value=watts, unit="W", status="OK", timestamp=_ts())


def make_sel_entry(message: str, severity: str = "OK") -> SelEntry:
    return SelEntry(
        entry_id="1",
        timestamp=_ts(),
        message=message,
        severity=severity,
    )
