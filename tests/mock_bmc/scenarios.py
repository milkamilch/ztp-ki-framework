"""
Vordefinierte Sensor-Szenarien für den Mock-BMC-Server.

Jedes Szenario beschreibt einen realistischen Zustand einer physischen
Serverkomponente. Die Szenarien decken alle Anomalie-Typen ab, die der
KI-Layer erkennen soll.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Scenario:
    """Vollständiger Zustandssatz eines simulierten Servers."""
    name:        str
    description: str
    temps_c:     list[tuple[str, float, str]]  # (name, value, health)
    fans_rpm:    list[tuple[str, float, str]]  # (name, value, health)
    power_w:     float
    sel_entries: list[tuple[str, str]]         # (message, severity)
    power_state: str = "On"


SCENARIOS: dict[str, Scenario] = {

    "normal": Scenario(
        name="normal",
        description="Normalbetrieb — alle Sensoren im grünen Bereich",
        temps_c=[
            ("CPU 1 Temp",  45.0, "OK"),
            ("CPU 2 Temp",  43.0, "OK"),
            ("Inlet Temp",  22.0, "OK"),
            ("Exhaust Temp",31.0, "OK"),
        ],
        fans_rpm=[
            ("Fan 1A", 6000.0, "OK"),
            ("Fan 1B", 5900.0, "OK"),
            ("Fan 2A", 6100.0, "OK"),
            ("Fan 2B", 5950.0, "OK"),
        ],
        power_w=350.0,
        sel_entries=[],
    ),

    "temp_warning": Scenario(
        name="temp_warning",
        description="CPU 1 nähert sich dem Warn-Schwellenwert (78°C)",
        temps_c=[
            ("CPU 1 Temp",  78.0, "Warning"),
            ("CPU 2 Temp",  44.0, "OK"),
            ("Inlet Temp",  26.0, "OK"),
            ("Exhaust Temp",52.0, "Warning"),
        ],
        fans_rpm=[
            ("Fan 1A", 8500.0, "OK"),
            ("Fan 1B", 8400.0, "OK"),
            ("Fan 2A", 8600.0, "OK"),
            ("Fan 2B", 8450.0, "OK"),
        ],
        power_w=520.0,
        sel_entries=[
            ("CPU 1 temperature above warning threshold", "Warning"),
        ],
    ),

    "temp_critical": Scenario(
        name="temp_critical",
        description="CPU 1 überschreitet den kritischen Schwellenwert (87°C) — Reboot nötig",
        temps_c=[
            ("CPU 1 Temp",  87.0, "Critical"),
            ("CPU 2 Temp",  46.0, "OK"),
            ("Inlet Temp",  28.0, "OK"),
            ("Exhaust Temp",68.0, "Critical"),
        ],
        fans_rpm=[
            ("Fan 1A", 9500.0, "OK"),
            ("Fan 1B", 9400.0, "OK"),
            ("Fan 2A", 9600.0, "OK"),
            ("Fan 2B", 9450.0, "OK"),
        ],
        power_w=610.0,
        sel_entries=[
            ("CPU 1 over temperature — thermal trip imminent", "Critical"),
        ],
    ),

    "fan_failure": Scenario(
        name="fan_failure",
        description="Fan 2A ausgefallen (200 RPM) — Kühlungsausfall droht",
        temps_c=[
            ("CPU 1 Temp",  52.0, "OK"),
            ("CPU 2 Temp",  58.0, "Warning"),
            ("Inlet Temp",  24.0, "OK"),
            ("Exhaust Temp",45.0, "Warning"),
        ],
        fans_rpm=[
            ("Fan 1A", 6200.0, "OK"),
            ("Fan 1B", 6100.0, "OK"),
            ("Fan 2A",  200.0, "Critical"),  # Ausfall
            ("Fan 2B", 6000.0, "OK"),
        ],
        power_w=380.0,
        sel_entries=[
            ("Fan 2A fan failure detected", "Critical"),
        ],
    ),

    "sel_critical": Scenario(
        name="sel_critical",
        description="Unkorrektierbare ECC-Fehler im Arbeitsspeicher — DIMM defekt",
        temps_c=[
            ("CPU 1 Temp",  46.0, "OK"),
            ("CPU 2 Temp",  44.0, "OK"),
            ("Inlet Temp",  22.0, "OK"),
            ("Exhaust Temp",32.0, "OK"),
        ],
        fans_rpm=[
            ("Fan 1A", 6000.0, "OK"),
            ("Fan 1B", 5900.0, "OK"),
            ("Fan 2A", 6100.0, "OK"),
            ("Fan 2B", 5950.0, "OK"),
        ],
        power_w=355.0,
        sel_entries=[
            ("DIMM_A1 uncorrectable ECC error detected", "Critical"),
            ("Memory subsystem failure — DIMM_A1", "Critical"),
        ],
    ),

    "post_error": Scenario(
        name="post_error",
        description="POST-Fehler beim Bootvorgang — Provisionierung fehlgeschlagen",
        temps_c=[
            ("CPU 1 Temp",  38.0, "OK"),
            ("CPU 2 Temp",  37.0, "OK"),
            ("Inlet Temp",  21.0, "OK"),
            ("Exhaust Temp",28.0, "OK"),
        ],
        fans_rpm=[
            ("Fan 1A", 3000.0, "OK"),
            ("Fan 1B", 2900.0, "OK"),
            ("Fan 2A", 3100.0, "OK"),
            ("Fan 2B", 2950.0, "OK"),
        ],
        power_w=180.0,
        sel_entries=[
            ("POST error: Memory initialization failed", "Critical"),
            ("BIOS POST error code 0x0220 — memory not detected", "Critical"),
        ],
        power_state="PoweringOn",
    ),

    "boot_timeout": Scenario(
        name="boot_timeout",
        description="Boot-Watchdog abgelaufen — Server hat nicht innerhalb des Zeitfensters gebootet",
        temps_c=[
            ("CPU 1 Temp",  40.0, "OK"),
            ("CPU 2 Temp",  39.0, "OK"),
            ("Inlet Temp",  22.0, "OK"),
            ("Exhaust Temp",30.0, "OK"),
        ],
        fans_rpm=[
            ("Fan 1A", 2800.0, "OK"),
            ("Fan 1B", 2750.0, "OK"),
            ("Fan 2A", 2900.0, "OK"),
            ("Fan 2B", 2780.0, "OK"),
        ],
        power_w=160.0,
        sel_entries=[
            ("Boot watchdog timeout — system did not boot within expected time", "Critical"),
            ("OS watchdog timer expired during provisioning", "Critical"),
        ],
        power_state="PoweringOn",
    ),
}
