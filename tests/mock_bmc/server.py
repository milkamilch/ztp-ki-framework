"""
Mock-BMC-Server — simuliert eine Redfish REST-API für Tests ohne echte Hardware.

Implementiert die vier Endpoints, die der RedfishCollector abfragt:
    GET /redfish/v1/Chassis/1/Thermal         → Temperaturen + Lüfter
    GET /redfish/v1/Chassis/1/Power           → Stromverbrauch
    GET /redfish/v1/Systems/1/LogServices/Sel/Entries → SEL-Logs
    GET /redfish/v1/Systems/1                 → System-Status

Das aktive Szenario kann jederzeit per API umgeschaltet werden:
    POST /control/scenario/{name}
    GET  /control/scenarios

Starten:
    uvicorn tests.mock_bmc.server:app --host 127.0.0.1 --port 8888 --reload
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from tests.mock_bmc.scenarios import SCENARIOS, Scenario

app = FastAPI(title="Mock BMC — Redfish API", version="1.0")

# Aktives Szenario — kann zur Laufzeit gewechselt werden
_state: dict[str, str] = {"scenario": "normal"}


def _current() -> Scenario:
    """Gibt das aktuell aktive Szenario zurück."""
    return SCENARIOS[_state["scenario"]]


# ──────────────────────────────────────────
# Redfish-Endpoints (werden vom RedfishCollector abgefragt)
# ──────────────────────────────────────────

@app.get("/redfish/v1/Chassis/1/Thermal")
def thermal():
    """Liefert Temperatur- und Lüfter-Daten im Redfish-Format."""
    s = _current()
    return {
        "Temperatures": [
            {
                "Name": name,
                "ReadingCelsius": value,
                "Status": {"Health": health},
            }
            for name, value, health in s.temps_c
        ],
        "Fans": [
            {
                "Name": name,
                "ReadingRPM": value,
                "ReadingUnits": "RPM",
                "Status": {"Health": health},
            }
            for name, value, health in s.fans_rpm
        ],
    }


@app.get("/redfish/v1/Chassis/1/Power")
def power():
    """Liefert Stromverbrauchs-Daten im Redfish-Format."""
    s = _current()
    return {
        "PowerControl": [
            {
                "Name": "System Power Control",
                "PowerConsumedWatts": s.power_w,
            }
        ]
    }


@app.get("/redfish/v1/Systems/1/LogServices/Sel/Entries")
def sel_entries():
    """Liefert SEL-Einträge des aktuellen Szenarios."""
    s = _current()
    now = datetime.now(timezone.utc).isoformat()
    return {
        "Members": [
            {
                "Id": str(i + 1),
                "Created": now,
                "Message": message,
                "Severity": severity,
                "SensorType": "Unknown",
            }
            for i, (message, severity) in enumerate(s.sel_entries)
        ],
        "Members@odata.count": len(s.sel_entries),
    }


@app.get("/redfish/v1/Systems/1")
def system():
    """Liefert den System-Gesamtstatus (Power-State, Boot-Info)."""
    s = _current()
    return {
        "PowerState": s.power_state,
        "Boot": {"BootSourceOverrideEnabled": "None", "PostCode": "0xA0"},
        "Status": {"Health": "OK", "State": "Enabled"},
    }


# ──────────────────────────────────────────
# Steuerungs-Endpoints (nur für Tests)
# ──────────────────────────────────────────

@app.get("/control/scenarios")
def list_scenarios():
    """Gibt alle verfügbaren Szenario-Namen und ihre Beschreibungen zurück."""
    return {
        name: scenario.description
        for name, scenario in SCENARIOS.items()
    }


@app.get("/control/active")
def active_scenario():
    """Gibt das aktuell aktive Szenario zurück."""
    s = _current()
    return {"name": s.name, "description": s.description}


@app.post("/control/scenario/{name}")
def set_scenario(name: str):
    """Wechselt das aktive Szenario zur Laufzeit.

    Args:
        name: Name eines Szenarios aus SCENARIOS (z. B. "temp_critical").

    Raises:
        HTTPException 404: Wenn das Szenario nicht existiert.
    """
    if name not in SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Unbekanntes Szenario '{name}'. Verfügbar: {list(SCENARIOS.keys())}",
        )
    _state["scenario"] = name
    return {"active": name, "description": SCENARIOS[name].description}
