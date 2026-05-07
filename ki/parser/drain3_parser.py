"""
Strukturiert rohe SEL-Log-Nachrichten mit dem Drain3-Algorithmus.

Drain3 clustert wiederkehrende Log-Muster zu Templates und extrahiert
variable Teile (Parameter). Das Ergebnis macht Logs vergleichbar und
ist Voraussetzung für eine sinnvolle Anomalie-Erkennung.
"""
from __future__ import annotations

import logging
from datetime import datetime

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from ki.models import ParsedLogEvent, SelEntry

logger = logging.getLogger(__name__)

# Schlüsselwörter, die unabhängig vom ML-Modell sofort auf "Critical" eskalieren.
# Bewusst lowercase — Vergleich erfolgt case-insensitive.
CRITICAL_KEYWORDS = [
    "uncorrectable ecc",
    "machine check",
    "post error",
    "fan failure",
    "fan not detected",
    "over temperature",
    "thermal trip",
    "power supply failure",
    "psu failure",
    "hard drive failure",
    "nvme failure",
]


class DrainLogParser:
    """Wrapper um den Drain3-Template-Miner für SEL-Log-Einträge.

    Drain3 lernt während des Betriebs kontinuierlich neue Log-Templates.
    Ein Template fasst strukturell ähnliche Nachrichten zusammen, z. B.:
      "DIMM_A1 correctable ECC error"
      "DIMM_B2 correctable ECC error"
    → Template: "DIMM_* correctable ECC error", Parameter: ["A1"] / ["B2"]
    """

    def __init__(self):
        """Initialisiert den Drain3 TemplateMiner mit konservativen Einstellungen.

        sim_th=0.4 erlaubt großzügiges Clustering, damit ähnliche
        Hardware-Nachrichten verschiedener Hersteller zusammengefasst werden.
        """
        cfg = TemplateMinerConfig()
        cfg.drain_sim_th               = 0.4
        cfg.drain_depth                = 4
        cfg.drain_max_clusters         = 1000
        cfg.parametrize_numeric_tokens = True
        self._miner = TemplateMiner(config=cfg)
        logging.getLogger("drain3").setLevel(logging.WARNING)

    def parse(self, entries: list[SelEntry]) -> list[ParsedLogEvent]:
        """Verarbeitet eine Liste von SEL-Einträgen zu strukturierten Log-Ereignissen.

        Args:
            entries: Rohe SEL-Einträge aus dem CollectorSnapshot.

        Returns:
            Liste von ParsedLogEvent — ein Eintrag pro SEL-Zeile, angereichert
            um Template-ID, extrahierte Parameter und ggf. eskalierte Severity.
        """
        events = []
        for entry in entries:
            # drain3 0.9.x gibt kein "cluster"-Objekt zurück, sondern ein
            # flaches Dict mit cluster_id und template_mined als Strings.
            result      = self._miner.add_log_message(entry.message)
            template    = result["template_mined"]
            cluster_id  = result["cluster_id"]

            severity = self._escalate_severity(entry.message, entry.severity)
            params   = self._miner.get_parameter_list(template, entry.message)

            events.append(ParsedLogEvent(
                template_id=cluster_id,
                template=template,
                params=[str(p) for p in (params or [])],
                raw_message=entry.message,
                severity=severity,
                timestamp=entry.timestamp,
            ))
        return events

    @staticmethod
    def _escalate_severity(message: str, original: str) -> str:
        """Stuft die Severity auf 'Critical' hoch, wenn ein bekanntes kritisches Schlüsselwort enthalten ist.

        Ergänzt die BMC-eigene Severity, die bei manchen Herstellern unvollständig
        oder zu konservativ gesetzt ist.
        """
        lower = message.lower()
        if any(kw in lower for kw in CRITICAL_KEYWORDS):
            return "Critical"
        return original
