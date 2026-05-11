"""
Zweistufige Anomalie-Erkennung auf Sensor-Zeitreihen und Log-Ereignissen.

Stufe 1 — Regelbasiert:
    Harte Schwellenwerte für Temperatur, Lüfter und SEL-Einträge.
    Liefert sofort ein deterministisches Ergebnis ohne Trainingsphase.

Stufe 2 — ML-basiert (Isolation Forest):
    Erkennt statistische Ausreißer in einem 6-dimensionalen Feature-Vektor
    aus Sensor-Aggregaten. Benötigt eine Warmup-Phase von WARMUP_SIZE Samples,
    bevor das Modell trainiert und aktiv wird.

Stufe 1 hat immer Vorrang bei hohem/kritischem Schweregrad.
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

TEMP_WARN_C  = 75.0
TEMP_CRIT_C  = 85.0
FAN_MIN_RPM  = 500.0
POWER_MAX_W  = 1200.0
WARMUP_SIZE  = 50


class AnomalyDetector:
    """Erkennt Anomalien in Sensor-Daten und Log-Ereignissen.

    Kombiniert Regelprüfung (schnell, deterministisch) mit einem
    Isolation-Forest-Modell (lernt normale Sensor-Profile).
    Das trainierte Modell wird als .joblib-Datei persistiert und
    beim nächsten Start automatisch geladen.
    """

    def __init__(
        self,
        model_path:   Path | None = None,
        contamination: float = 0.05,
        temp_warn:     float = TEMP_WARN_C,
        temp_crit:     float = TEMP_CRIT_C,
    ):
        """Initialisiert den Detektor.

        Args:
            model_path:    Pfad zum gespeicherten Isolation-Forest-Modell (.joblib).
                           Wenn die Datei existiert, wird sie geladen und die
                           Warmup-Phase übersprungen.
            contamination: Erwarteter Anteil anomaler Samples im Trainings-Set
                           (0.05 = 5 %). Steuert die Empfindlichkeit des Modells.
            temp_warn:     Temperatur-Schwelle in °C für Severity.MEDIUM.
            temp_crit:     Temperatur-Schwelle in °C für Severity.CRITICAL.
        """
        self.model_path    = model_path
        self.contamination = contamination
        self.temp_warn     = temp_warn
        self.temp_crit     = temp_crit

        self._model:         IsolationForest | None = None
        self._warmup_buffer: list[list[float]]      = []
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
        """Führt die zweistufige Anomalie-Erkennung für einen Snapshot durch.

        Stufe 1 (Regelcheck) hat Vorrang: Bei HIGH oder CRITICAL wird das
        Ergebnis sofort zurückgegeben. Nur bei OK/LOW/MEDIUM wird zusätzlich
        der ML-Check ausgeführt und das schlimmere der beiden Ergebnisse gewählt.

        Args:
            snapshot: Sensor-Daten und SEL-Einträge des aktuellen Abfrage-Zyklus.
            events:   Geparste Log-Ereignisse vom DrainLogParser.

        Returns:
            AnomalyResult mit Urteil, Typ, Schweregrad und Begründung.
        """
        rule = self._rule_check(snapshot, events)

        if rule.severity in (Severity.HIGH, Severity.CRITICAL):
            return rule

        features = self._extract_features(snapshot)
        if features:
            ml = self._ml_check(features, snapshot)
            if ml.is_anomaly and ml.severity.value > rule.severity.value:
                return ml

        return rule

    # ──────────────────────────────────────────
    # Stufe 1: Regelbasierte Prüfung
    # ──────────────────────────────────────────

    def _rule_check(
        self,
        snapshot: CollectorSnapshot,
        events:   list[ParsedLogEvent],
    ) -> AnomalyResult:
        """Prüft alle Sensoren und Log-Ereignisse gegen harte Schwellenwerte.

        Gibt beim ersten Treffer sofort das Ergebnis zurück (fail-fast).
        Reihenfolge: Temperatur → Lüfter → Leistung → SEL-Einträge.
        """
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
            if sensor.unit == "RPM" and 0 < sensor.value < FAN_MIN_RPM:
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
    # Stufe 2: ML-basierte Prüfung (Isolation Forest)
    # ──────────────────────────────────────────

    def _extract_features(self, snapshot: CollectorSnapshot) -> list[float] | None:
        """Berechnet einen 6-dimensionalen Feature-Vektor aus einem Snapshot.

        Features: [mean_temp, max_temp, mean_fan, min_fan, mean_power, critical_sel_count]
        Gibt None zurück, wenn keine Temperaturdaten vorliegen (Modell kann nicht arbeiten).
        """
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
        """Führt die Isolation-Forest-Inferenz für einen Feature-Vektor durch.

        Während der Warmup-Phase (< WARMUP_SIZE Samples) werden Daten gesammelt
        und das Modell trainiert. Danach wechselt der Detector in den Inferenz-Modus.

        Der Isolation-Forest-Score ist negativ: je negativer, desto anomaler.
        ``predict()`` gibt -1 (Anomalie) oder +1 (normal) zurück.
        """
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
        pred  = self._model.predict(x)[0]
        score = self._model.score_samples(x)[0]

        is_anomaly = bool(pred == -1)
        confidence = float(max(0.0, min(1.0, -score)))

        if is_anomaly:
            if score < -0.3:
                severity = Severity.HIGH
            elif score < -0.1:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW
        else:
            severity = Severity.OK

        return self._result(
            is_anomaly,
            AnomalyType.ML_OUTLIER if is_anomaly else AnomalyType.NONE,
            severity,
            confidence,
            f"Isolation Forest Score: {score:.4f}",
            snapshot, source="ml",
        )

    def _train(self, X: np.ndarray) -> None:
        """Trainiert den Isolation Forest auf dem gesammelten Warmup-Datensatz.

        Wird einmalig aufgerufen, sobald WARMUP_SIZE Samples vorliegen.
        Das trainierte Modell wird anschließend auf model_path gespeichert,
        damit ein Neustart die Warmup-Phase überspringt.
        """
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
        """Hilfsfunktion: erstellt ein AnomalyResult mit einheitlicher Signatur."""
        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_type=anomaly_type,
            severity=severity,
            confidence=confidence,
            details=details,
            source=source,
            raw_snapshot=snapshot,
        )
