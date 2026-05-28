"""Unit-Tests für den RedfishCollector."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from ki.collector.redfish_collector import RedfishCollector
from ki.models import CollectorSnapshot


def _collector() -> RedfishCollector:
    return RedfishCollector(username="admin", password="test", scheme="http")


def _stub_get(responses: dict):
    """Gibt eine _get-Ersetzung zurück, die Path-basiert auf responses matched."""
    def _get(host: str, path: str) -> dict:
        for key, data in responses.items():
            if key in path:
                return data
        return {}
    return _get


def test_collect_returns_snapshot_with_sensors():
    responses = {
        "/Thermal": {
            "Temperatures": [{"Name": "CPU 1", "ReadingCelsius": 45.0, "Status": {"Health": "OK"}}],
            "Fans": [{"Name": "Fan 1", "ReadingRPM": 6000.0, "ReadingUnits": "RPM", "Status": {"Health": "OK"}}],
        },
        "/Power": {
            "PowerControl": [{"Name": "System Power", "PowerConsumedWatts": 350.0}]
        },
        "Sel/Entries": {"Members": []},
        "/Systems/1": {"PowerState": "On", "Boot": {}},
    }
    c = _collector()
    with patch.object(c, "_get", side_effect=_stub_get(responses)):
        snap = c.collect("192.168.1.1")

    assert isinstance(snap, CollectorSnapshot)
    assert snap.target == "192.168.1.1"
    assert snap.power_state == "On"
    temps = [s for s in snap.sensors if s.unit == "C"]
    fans  = [s for s in snap.sensors if s.unit == "RPM"]
    power = [s for s in snap.sensors if s.unit == "W"]
    assert len(temps) == 1 and temps[0].value == 45.0
    assert len(fans) == 1 and fans[0].value == 6000.0
    assert len(power) == 1 and power[0].value == 350.0


def test_collect_parses_sel_entries():
    responses = {
        "/Thermal": {"Temperatures": [], "Fans": []},
        "/Power": {"PowerControl": []},
        "Sel/Entries": {
            "Members": [
                {
                    "Id": "1",
                    "Created": "2026-05-01T12:00:00Z",
                    "Message": "CPU 1 over temperature",
                    "Severity": "Critical",
                    "SensorType": "Temperature",
                }
            ]
        },
        "/Systems/1": {"PowerState": "On", "Boot": {}},
    }
    c = _collector()
    with patch.object(c, "_get", side_effect=_stub_get(responses)):
        snap = c.collect("192.168.1.1")

    assert len(snap.sel_entries) == 1
    assert snap.sel_entries[0].message == "CPU 1 over temperature"
    assert snap.sel_entries[0].severity == "Critical"


def test_collect_reads_post_code():
    responses = {
        "/Thermal": {"Temperatures": [], "Fans": []},
        "/Power": {"PowerControl": []},
        "Sel/Entries": {"Members": []},
        "/Systems/1": {"PowerState": "PoweringOn", "Boot": {"PostCode": "0xA0"}},
    }
    c = _collector()
    with patch.object(c, "_get", side_effect=_stub_get(responses)):
        snap = c.collect("192.168.1.1")

    assert snap.power_state == "PoweringOn"
    assert snap.post_code == "0xA0"


def test_collect_returns_empty_on_connection_error():
    c = _collector()
    with patch.object(c, "_get", return_value={}):
        snap = c.collect("192.168.1.99")

    assert isinstance(snap, CollectorSnapshot)
    assert snap.sensors == []
    assert snap.sel_entries == []


def test_sel_limited_to_50_entries():
    members = [
        {"Id": str(i), "Created": "2026-05-01T12:00:00Z",
         "Message": f"Event {i}", "Severity": "OK", "SensorType": ""}
        for i in range(60)
    ]
    responses = {
        "/Thermal": {"Temperatures": [], "Fans": []},
        "/Power": {"PowerControl": []},
        "Sel/Entries": {"Members": members},
        "/Systems/1": {"PowerState": "On", "Boot": {}},
    }
    c = _collector()
    with patch.object(c, "_get", side_effect=_stub_get(responses)):
        snap = c.collect("192.168.1.1")

    assert len(snap.sel_entries) == 50
