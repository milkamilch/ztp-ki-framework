from unittest.mock import MagicMock, patch

from ki.collector.redfish_collector import RedfishCollector


def _make_collector() -> RedfishCollector:
    return RedfishCollector(username="admin", password="test", scheme="http")


def test_post_code_read_from_boot_post_code():
    """_collect_system_state liest PostCode aus Boot.PostCode, nicht BootSourceOverrideEnabled."""
    collector = _make_collector()
    fake_response = {
        "PowerState": "On",
        "Boot": {
            "PostCode": "0xA0",
            "BootSourceOverrideEnabled": "Once",
        },
    }
    with patch.object(collector, "_get", return_value=fake_response):
        state, post_code = collector._collect_system_state("192.168.1.1")

    assert post_code == "0xA0"
    assert state == "On"


def test_post_code_none_when_not_present():
    """Gibt None zurück wenn kein PostCode im Redfish-Response vorhanden."""
    collector = _make_collector()
    fake_response = {
        "PowerState": "Off",
        "Boot": {"BootSourceOverrideEnabled": "Disabled"},
    }
    with patch.object(collector, "_get", return_value=fake_response):
        state, post_code = collector._collect_system_state("192.168.1.1")

    assert post_code is None
    assert state == "Off"
