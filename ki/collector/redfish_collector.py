"""
Sammelt Sensor-Daten und SEL-Logs von einem BMC via Redfish REST-API.
Fällt auf ipmitool zurück, wenn Redfish nicht erreichbar ist.
"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from typing import Any

import requests
import urllib3

from ki.models import CollectorSnapshot, SelEntry, SensorReading

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


class RedfishCollector:
    def __init__(self, username: str, password: str, timeout: int = 10):
        self.username = username
        self.password = password
        self.timeout  = timeout
        self._sessions: dict[str, requests.Session] = {}

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def collect(self, target: str) -> CollectorSnapshot:
        sensors    = self._collect_sensors(target)
        sel        = self._collect_sel(target)
        state, pco = self._collect_system_state(target)
        return CollectorSnapshot(
            target=target,
            timestamp=datetime.now(timezone.utc),
            sensors=sensors,
            sel_entries=sel,
            post_code=pco,
            power_state=state,
        )

    # ──────────────────────────────────────────
    # Sensor-Daten (Thermal + Power)
    # ──────────────────────────────────────────

    def _collect_sensors(self, host: str) -> list[SensorReading]:
        readings: list[SensorReading] = []

        thermal = self._get(host, "/redfish/v1/Chassis/1/Thermal")
        for temp in thermal.get("Temperatures", []):
            val = temp.get("ReadingCelsius")
            if val is not None:
                readings.append(SensorReading(
                    name=temp.get("Name", "Temp"),
                    value=float(val),
                    unit="C",
                    status=temp.get("Status", {}).get("Health", "Unknown"),
                ))
        for fan in thermal.get("Fans", []):
            val = fan.get("Reading") or fan.get("ReadingRPM")
            if val is not None:
                readings.append(SensorReading(
                    name=fan.get("Name", "Fan"),
                    value=float(val),
                    unit=fan.get("ReadingUnits", "RPM"),
                    status=fan.get("Status", {}).get("Health", "Unknown"),
                ))

        power = self._get(host, "/redfish/v1/Chassis/1/Power")
        for ctrl in power.get("PowerControl", []):
            val = ctrl.get("PowerConsumedWatts")
            if val is not None:
                readings.append(SensorReading(
                    name=ctrl.get("Name", "Power"),
                    value=float(val),
                    unit="W",
                    status="OK",
                ))

        if not readings:
            logger.warning("[%s] Redfish lieferte keine Sensordaten — versuche ipmitool", host)
            readings = self._ipmitool_sensors(host)

        return readings

    # ──────────────────────────────────────────
    # System Event Log
    # ──────────────────────────────────────────

    def _collect_sel(self, host: str) -> list[SelEntry]:
        data    = self._get(host, "/redfish/v1/Systems/1/LogServices/Sel/Entries")
        entries = []
        for m in data.get("Members", [])[:50]:
            try:
                ts = datetime.fromisoformat(m.get("Created", "").rstrip("Z"))
            except ValueError:
                ts = datetime.now(timezone.utc)
            entries.append(SelEntry(
                entry_id=str(m.get("Id", "")),
                timestamp=ts,
                message=m.get("Message", ""),
                severity=m.get("Severity", "OK"),
                sensor_type=m.get("SensorType", ""),
            ))
        return entries

    # ──────────────────────────────────────────
    # System-Status + POST-Code
    # ──────────────────────────────────────────

    def _collect_system_state(self, host: str) -> tuple[str, str | None]:
        data        = self._get(host, "/redfish/v1/Systems/1")
        power_state = data.get("PowerState", "Unknown")
        post_code   = data.get("Boot", {}).get("BootSourceOverrideEnabled")
        return power_state, post_code

    # ──────────────────────────────────────────
    # IPMI-Fallback via ipmitool
    # ──────────────────────────────────────────

    def _ipmitool_sensors(self, host: str) -> list[SensorReading]:
        try:
            out = subprocess.check_output(
                ["ipmitool", "-I", "lanplus", "-H", host,
                 "-U", self.username, "-P", self.password, "sensor"],
                timeout=self.timeout, stderr=subprocess.DEVNULL, text=True,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            return []

        readings = []
        for line in out.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                continue
            name, raw_val, unit = parts[0], parts[1], parts[2]
            try:
                readings.append(SensorReading(
                    name=name, value=float(raw_val), unit=unit, status="OK"
                ))
            except ValueError:
                pass
        return readings

    # ──────────────────────────────────────────
    # HTTP-Helper
    # ──────────────────────────────────────────

    def _get(self, host: str, path: str) -> dict[str, Any]:
        if host not in self._sessions:
            s = requests.Session()
            s.auth    = (self.username, self.password)
            s.verify  = False
            s.headers.update({"Accept": "application/json"})
            self._sessions[host] = s
        try:
            resp = self._sessions[host].get(
                f"https://{host}{path}", timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.debug("[%s] Redfish GET %s: %s", host, path, exc)
            return {}
