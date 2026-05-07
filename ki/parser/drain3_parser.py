"""
Strukturiert rohe SEL-Log-Nachrichten mit dem Drain3-Algorithmus.
Drain3 clustert wiederkehrende Log-Muster zu Templates und extrahiert
variable Teile (Parameter) — wichtige Vorarbeit für den Anomalie-Detektor.
"""
from __future__ import annotations

import logging
from datetime import datetime

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from ki.models import ParsedLogEvent, SelEntry

logger = logging.getLogger(__name__)

# Muster, die unabhängig vom ML-Modell sofort als kritisch gelten
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
    def __init__(self):
        cfg = TemplateMinerConfig()
        cfg.drain_sim_th               = 0.4
        cfg.drain_depth                = 4
        cfg.drain_max_clusters         = 1000
        cfg.parametrize_numeric_tokens = True
        self._miner = TemplateMiner(config=cfg)
        logging.getLogger("drain3").setLevel(logging.WARNING)

    def parse(self, entries: list[SelEntry]) -> list[ParsedLogEvent]:
        events = []
        for entry in entries:
            result  = self._miner.add_log_message(entry.message)
            cluster = result["cluster"]

            severity = self._escalate_severity(entry.message, entry.severity)
            params   = self._miner.get_parameter_list(
                cluster.get_template(), entry.message
            )

            events.append(ParsedLogEvent(
                template_id=cluster.cluster_id,
                template=cluster.get_template(),
                params=[str(p) for p in (params or [])],
                raw_message=entry.message,
                severity=severity,
                timestamp=entry.timestamp,
            ))
        return events

    @staticmethod
    def _escalate_severity(message: str, original: str) -> str:
        lower = message.lower()
        if any(kw in lower for kw in CRITICAL_KEYWORDS):
            return "Critical"
        return original
