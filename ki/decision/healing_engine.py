"""
Entscheidungslogik: Anomalie-Typ + Schwere → Heilungsaktion.
Führt Aktionen aus (Ansible-Playbook, Redfish-Reset) und protokolliert alles.
"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from typing import Callable

import requests
import urllib3

from ki.models import (
    AnomalyResult, AnomalyType, HealingAction, HealingRecord, Severity,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Entscheidungsmatrix: (AnomalyType, Severity) → HealingAction
# ──────────────────────────────────────────
DECISION_MATRIX: dict[tuple[AnomalyType, Severity], HealingAction] = {
    (AnomalyType.TEMPERATURE, Severity.MEDIUM):   HealingAction.ALERT,
    (AnomalyType.TEMPERATURE, Severity.HIGH):     HealingAction.REBOOT,
    (AnomalyType.TEMPERATURE, Severity.CRITICAL): HealingAction.POWER_CYCLE,

    (AnomalyType.FAN,         Severity.MEDIUM):   HealingAction.ALERT,
    (AnomalyType.FAN,         Severity.HIGH):     HealingAction.REBOOT,
    (AnomalyType.FAN,         Severity.CRITICAL): HealingAction.POWER_CYCLE,

    (AnomalyType.POWER,       Severity.MEDIUM):   HealingAction.ALERT,
    (AnomalyType.POWER,       Severity.HIGH):     HealingAction.ALERT,

    (AnomalyType.SEL_CRITICAL, Severity.MEDIUM):  HealingAction.ALERT,
    (AnomalyType.SEL_CRITICAL, Severity.HIGH):    HealingAction.REBOOT,
    (AnomalyType.SEL_CRITICAL, Severity.CRITICAL):HealingAction.ROLLBACK,

    (AnomalyType.POST_ERROR,  Severity.MEDIUM):   HealingAction.RETRY,
    (AnomalyType.POST_ERROR,  Severity.HIGH):     HealingAction.RETRY,
    (AnomalyType.POST_ERROR,  Severity.CRITICAL): HealingAction.ROLLBACK,

    (AnomalyType.ML_OUTLIER,  Severity.MEDIUM):   HealingAction.ALERT,
    (AnomalyType.ML_OUTLIER,  Severity.HIGH):     HealingAction.RETRY,

    (AnomalyType.BOOT_TIMEOUT,Severity.HIGH):     HealingAction.RETRY,
    (AnomalyType.BOOT_TIMEOUT,Severity.CRITICAL): HealingAction.ROLLBACK,
}

ANSIBLE_PLAYBOOKS = {
    HealingAction.RETRY:    "ansible/playbooks/ztp-retry.yml",
    HealingAction.ROLLBACK: "ansible/playbooks/ztp-rollback.yml",
}


class HealingEngine:
    def __init__(
        self,
        ansible_inventory: str,
        redfish_user:      str,
        redfish_password:  str,
    ):
        self.ansible_inventory = ansible_inventory
        self.redfish_user      = redfish_user
        self.redfish_password  = redfish_password
        self.history:           list[HealingRecord] = []

    def handle(self, anomaly: AnomalyResult, target: str) -> HealingRecord:
        action = DECISION_MATRIX.get(
            (anomaly.anomaly_type, anomaly.severity),
            HealingAction.ALERT,
        )

        logger.warning(
            "[%s] %s | Schwere: %s | → %s | %s",
            target, anomaly.anomaly_type.value,
            anomaly.severity.value, action.value, anomaly.details,
        )

        executor = self._executors()[action]
        success, message = executor(target, anomaly)

        record = HealingRecord(
            timestamp=datetime.now(timezone.utc),
            target=target,
            anomaly=anomaly,
            action=action,
            success=success,
            message=message,
        )
        self.history.append(record)

        status = "OK" if success else "FEHLER"
        logger.info("[%s] Aktion %s: %s — %s", target, action.value, status, message)
        return record

    # ──────────────────────────────────────────
    # Aktions-Implementierungen
    # ──────────────────────────────────────────

    def _executors(self) -> dict[HealingAction, Callable]:
        return {
            HealingAction.NONE:        self._noop,
            HealingAction.ALERT:       self._alert,
            HealingAction.RETRY:       self._retry,
            HealingAction.REBOOT:      self._reboot,
            HealingAction.POWER_CYCLE: self._power_cycle,
            HealingAction.ROLLBACK:    self._rollback,
        }

    def _noop(self, target: str, _: AnomalyResult) -> tuple[bool, str]:
        return True, "keine Aktion"

    def _alert(self, target: str, anomaly: AnomalyResult) -> tuple[bool, str]:
        msg = f"ALERT [{target}] {anomaly.anomaly_type.value}: {anomaly.details}"
        logger.error(msg)
        # Erweiterungspunkt: Slack / PagerDuty / E-Mail hier einbinden
        return True, msg

    def _reboot(self, target: str, _: AnomalyResult) -> tuple[bool, str]:
        return self._redfish_reset(target, "GracefulRestart")

    def _power_cycle(self, target: str, _: AnomalyResult) -> tuple[bool, str]:
        return self._redfish_reset(target, "ForceRestart")

    def _retry(self, target: str, _: AnomalyResult) -> tuple[bool, str]:
        return self._run_playbook(ANSIBLE_PLAYBOOKS[HealingAction.RETRY], target)

    def _rollback(self, target: str, _: AnomalyResult) -> tuple[bool, str]:
        return self._run_playbook(ANSIBLE_PLAYBOOKS[HealingAction.ROLLBACK], target)

    # ──────────────────────────────────────────
    # Redfish-Reset
    # ──────────────────────────────────────────

    def _redfish_reset(self, target: str, reset_type: str) -> tuple[bool, str]:
        url = f"https://{target}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset"
        try:
            resp = requests.post(
                url,
                json={"ResetType": reset_type},
                auth=(self.redfish_user, self.redfish_password),
                verify=False,
                timeout=10,
            )
            resp.raise_for_status()
            return True, f"Redfish {reset_type} an {target} gesendet"
        except requests.RequestException as exc:
            return False, f"Redfish Reset fehlgeschlagen: {exc}"

    # ──────────────────────────────────────────
    # Ansible-Playbook
    # ──────────────────────────────────────────

    def _run_playbook(self, playbook: str, target: str) -> tuple[bool, str]:
        cmd = [
            "ansible-playbook",
            "-i", self.ansible_inventory,
            playbook,
            "--limit", target,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return True, f"Playbook '{playbook}' erfolgreich"
            return False, result.stderr[:500]
        except Exception as exc:
            return False, str(exc)
