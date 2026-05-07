"""
ZTP-Monitor — Hauptschleife des KI-Self-Healing-Layers.
Startet mit: python -m ki.main [config.yaml]
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

import yaml

from ki.collector.redfish_collector import RedfishCollector
from ki.decision.healing_engine import HealingEngine
from ki.detector.anomaly_detector import AnomalyDetector
from ki.parser.drain3_parser import DrainLogParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("ztp.monitor")


class ZTPMonitor:
    def __init__(self, config_path: Path):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        self.targets       = cfg["targets"]
        self.poll_interval = cfg.get("poll_interval_seconds", 30)
        self._running      = True

        bmc = cfg["bmc"]
        self.collector = RedfishCollector(
            username=bmc["username"],
            password=bmc["password"],
            timeout=bmc.get("timeout", 10),
        )
        self.parser   = DrainLogParser()
        self.detector = AnomalyDetector(
            model_path=Path(cfg.get("model_path", "ki/model.joblib")),
            contamination=cfg.get("contamination", 0.05),
        )
        self.engine = HealingEngine(
            ansible_inventory=cfg["ansible"]["inventory"],
            redfish_user=bmc["username"],
            redfish_password=bmc["password"],
        )

    async def run(self) -> None:
        logger.info(
            "ZTP-Monitor gestartet | %d Target(s) | Intervall: %ds",
            len(self.targets), self.poll_interval,
        )
        while self._running:
            for target in self.targets:
                await self._process(target)
            await asyncio.sleep(self.poll_interval)
        logger.info("ZTP-Monitor gestoppt.")

    async def _process(self, target: str) -> None:
        try:
            snapshot = self.collector.collect(target)
            events   = self.parser.parse(snapshot.sel_entries)
            anomaly  = self.detector.detect(snapshot, events)

            if anomaly.is_anomaly:
                self.engine.handle(anomaly, target)
            else:
                logger.debug("[%s] OK — %s", target, anomaly.details)
        except Exception:
            logger.exception("[%s] Unbehandelter Fehler", target)

    def stop(self) -> None:
        self._running = False


def main() -> None:
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ki/config.yaml")
    if not config_path.exists():
        logger.error("Config nicht gefunden: %s", config_path)
        sys.exit(1)

    monitor = ZTPMonitor(config_path)
    loop    = asyncio.new_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, monitor.stop)

    loop.run_until_complete(monitor.run())
    loop.close()


if __name__ == "__main__":
    main()
