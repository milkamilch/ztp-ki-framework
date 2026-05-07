"""
Zweistufige Anomalieerkennung:
  1. Regelbasiert  — harte Schwellenwerte (sofort, deterministisch)
  2. ML-basiert    — Isolation Forest auf Sensor-Zeitreihen
                     (Warmup-Phase: erste N Snapshots, dann Inferenz)
"""
from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from ki.models import (
    AnomalyResult, AnomalyType, CollectorSnapshot, ParsedLogEvent, Severity,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Schwellenwerte (können per config.yaml überschrieben werden)
# ──────────────────────────────────────────
TEMP_WARN_C  = 75.0
TEMP_CRIT_C  = 85.0
FAN_MIN_RPM  = 500.0
POWER_MAX_W  = 1200.0
WARMUP_SIZE  = 50      # Samples bis das ML-Modell trainiert wird


class AnomalyDetector:
    def __init__(
        self,
        model_path: Path | None = None,
        contamination: float = 0.05,
        temp_warn: float = TEMP_WARN_C,
        temp_crit: float = TEMP_CRIT_C,
    ):
        self.model_path    = model_path
        self.contamination = contamination
        self.temp_warn     = temp_warn
        self.temp_crit     = temp_crit

        self._model:          IsolationForest | None = None
        self._warmup_buffer:  list[list[float]]      = []
        self._trained = False

        if model_path and model_path.exists():
            self._model   = joblib.load(model_path)
            self._trained = True
            logger.info("Isolation Forest geladen: %s", model_path)

    # ──────────────────────────────────────────
    # Haupt-Einstiegspunkt
    # ──────────────────────────────────────────

    def detect(
        self,
        snapshot: CollectorSnapshot,
        events:   list[ParsedLogEvent],
    ) -> AnomalyResult:
        rule = self._rule_check(snapshot, events)

        # Kritische Regelanomalien haben immer Vorrang
        if rule.severity in (Severity.HIGH, Severity.CRITICAL):
            return rule

        features = self._extract_features(snapshot)
        if features:
            ml = self._ml_check(features, snapshot)
            if ml.is_anomaly and ml.severity.value > rule.severity.value:
                return ml

        return rule

    # ──────────────────────────────────────────
    # 1. Regelbasierte Prüfung
    # ──────────────────────────────────────────

    def _rule_check(
        self,
        snapshot: CollectorSnapshot,
        events:   list[ParsedLogEvent],
    ) -> AnomalyResult:

        for sensor in snapshot.sensors:
            if sensor.unit == "C":
                if sensor.value >= self.temp_crit:
                    return self._result(
                        True, AnomalyType.TEMPERATURE, Severity.CRITICAL, 1.0,
                        f"{sensor.name}: {sensor.value}°C ≥ {self.temp_crit}°C (kritisch)",
                        snapshot,
                    )
                if sensor.value >= self.temp_warn:
                    return self._result(
                        True, AnomalyType.TEMPERATURE, Severity.MEDIUM, 1.0,
                        f"{sensor.name}: {sensor.value}°C ≥ {self.temp_warn}°C (Warnung)",
                        snapshot,
                    )
            if sensor.unit == "RPM" and sensor.value < FAN_MIN_RPM and sensor.value > 0:
                return self._result(
                    True, AnomalyType.FAN, Severity.HIGH, 1.0,
                    f"{sensor.name}: {sensor.value} RPM < {FAN_MIN_RPM} RPM",
                    snapshot,
                )
            if sensor.unit == "W" and sensor.value > POWER_MAX_W:
                return self._result(
                    True, AnomalyType.POWER, Severity.MEDIUM, 1.0,
                    f"{sensor.name}: {sensor.value} W > {POWER_MAX_W} W",
                    snapshot,
                )

        for event in events:
            if event.severity == "Critical":
                anomaly_type = (
                    AnomalyType.POST_ERROR
                    if "post" in event.raw_message.lower()
                    else AnomalyType.SEL_CRITICAL
                )
                return self._result(
                    True, anomaly_type, Severity.HIGH, 1.0,
                    f"Kritischer SEL-Eintrag: {event.raw_message}",
                    snapshot,
                )

        return self._result(
            False, AnomalyType.NONE, Severity.OK, 1.0,
            "Regelprüfung: alles OK", snapshot,
        )

    # ──────────────────────────────────────────
    # 2. ML-basierte Prüfung (Isolation Forest)
    # ──────────────────────────────────────────

    def _extract_features(self, snapshot: CollectorSnapshot) -> list[float] | None:
        temps  = [s.value for s in snapshot.sensors if s.unit == "C"]
        fans   = [s.value for s in snapshot.sensors if s.unit == "RPM"]
        power  = [s.value for s in snapshot.sensors if s.unit == "W"]
        if not temps:
            return None
        return [
            float(np.mean(temps)),
            float(np.max(temps)),
            float(np.mean(fans)  if fans  else 0.0),
            float(np.min(fans)   if fans  else 0.0),
            float(np.mean(power) if power else 0.0),
            float(len([e for e in snapshot.sel_entries if e.severity == "Critical"])),
        ]

    def _ml_check(
        self, features: list[float], snapshot: CollectorSnapshot
    ) -> AnomalyResult:
        # Warmup: Modell noch nicht trainiert
        if not self._trained:
            self._warmup_buffer.append(features)
            if len(self._warmup_buffer) >= WARMUP_SIZE:
                self._train(np.array(self._warmup_buffer))
            return self._result(
                False, AnomalyType.NONE, Severity.OK, 0.0,
                f"ML-Warmup: {len(self._warmup_buffer)}/{WARMUP_SIZE} Samples",
                snapshot, source="ml",
            )

        x     = np.array([features])
        pred  = self._model.predict(x)[0]       # +1 normal, -1 Anomalie
        score = self._model.score_samples(x)[0] # negativer = anomaler

        is_anomaly = pred == -1
        confidence = float(max(0.0, min(1.0, -score)))

        return self._result(
            is_anomaly,
            AnomalyType.ML_OUTLIER if is_anomaly else AnomalyType.NONE,
            Severity.MEDIUM if is_anomaly else Severity.OK,
            confidence,
            f"Isolation Forest Score: {score:.4f}",
            snapshot, source="ml",
        )

    def _train(self, X: np.ndarray) -> None:
        logger.info("Trainiere Isolation Forest auf %d Samples ...", len(X))
        self._model = IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            random_state=42,
        )
        self._model.fit(X)
        self._trained = True
        if self.model_path:
            joblib.dump(self._model, self.model_path)
            logger.info("Modell gespeichert: %s", self.model_path)

    # ──────────────────────────────────────────
    # Helper
    # ──────────────────────────────────────────

    @staticmethod
    def _result(
        is_anomaly:   bool,
        anomaly_type: AnomalyType,
        severity:     Severity,
        confidence:   float,
        details:      str,
        snapshot:     CollectorSnapshot,
        source:       str = "rule",
    ) -> AnomalyResult:
        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_type=anomaly_type,
            severity=severity,
            confidence=confidence,
            details=details,
            source=source,
            raw_snapshot=snapshot,
        )
