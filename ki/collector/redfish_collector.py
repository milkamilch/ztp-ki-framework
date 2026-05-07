"""
Sammelt Sensor-Daten und SEL-Logs von einem BMC via Redfish REST-API.
Fällt automatisch auf ipmitool zurück, wenn Redfish keine Sensordaten liefert.
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
    """Liest Telemetriedaten von einem BMC (Baseboard Management Controller).

    Nutzt die Redfish REST-API (HTTPS/JSON) als primäre Quelle.
    Falls Redfish keine Sensordaten zurückliefert (ältere Hardware oder
    inkompatible Firmware), wird automatisch auf ``ipmitool`` umgeschaltet.
    BMC-TLS-Zertifikate werden bewusst nicht verifiziert (self-signed üblich).
    """

    def __init__(self, username: str, password: str, timeout: int = 10):
        """Initialisiert den Collector mit BMC-Zugangsdaten.

        Args:
            username: BMC-Benutzername (z. B. "admin").
            password: BMC-Passwort.
            timeout:  HTTP-Timeout in Sekunden pro Anfrage.
        """
        self.username = username
        self.password = password
        self.timeout  = timeout
        self._sessions: dict[str, requests.Session] = {}

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def collect(self, target: str) -> CollectorSnapshot:
        """Führt eine vollständige Datenabfrage für einen BMC-Host durch.

        Kombiniert Sensor-Readings, SEL-Einträge und System-Status zu einem
        CollectorSnapshot, der durch die weitere KI-Pipeline verarbeitet wird.

        Args:
            target: IP-Adresse des BMC (z. B. "192.168.100.201").

        Returns:
            CollectorSnapshot mit allen verfügbaren Daten zum aktuellen Zeitpunkt.
        """
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
        """Liest Temperatur-, Lüfter- und Leistungsdaten via Redfish.

        Fragt /Thermal (Temperaturen, Lüfter) und /Power (Stromverbrauch) ab.
        Gibt bei leerem Ergebnis an ipmitool weiter.
        """
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
        """Liest die letzten 50 Einträge aus dem System Event Log (SEL).

        Der SEL enthält Hardware-Ereignisse wie ECC-Fehler, Temperaturschwellen
        oder POST-Fehler und ist die wichtigste Quelle für den Log-Parser.
        """
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
        """Liest den aktuellen Power-State und Boot-Override-Status des Systems.

        Returns:
            Tuple (power_state, post_code), z. B. ("On", None).
        """
        data        = self._get(host, "/redfish/v1/Systems/1")
        power_state = data.get("PowerState", "Unknown")
        post_code   = data.get("Boot", {}).get("BootSourceOverrideEnabled")
        return power_state, post_code

    # ──────────────────────────────────────────
    # IPMI-Fallback via ipmitool
    # ──────────────────────────────────────────

    def _ipmitool_sensors(self, host: str) -> list[SensorReading]:
        """Liest Sensor-Daten über das ipmitool-Kommandozeilenwerkzeug.

        Wird nur aufgerufen, wenn die Redfish-Abfrage keine Daten liefert.
        Parst die tabellarische Ausgabe von ``ipmitool sensor``.
        """
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
        """Führt einen authentifizierten GET-Request gegen die Redfish-API aus.

        Baut pro Host eine wiederverwendbare Session auf.
        Gibt bei Fehlern ein leeres Dict zurück, statt eine Exception zu werfen,
        damit der Collector weiterläuft auch wenn ein Host kurz nicht erreichbar ist.
        """
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
