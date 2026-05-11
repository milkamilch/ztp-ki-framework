# Bugfixes + Unit Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs (wrong POST-code field, hardcoded ML severity) and add a pytest unit-test suite covering the parser, detector, and decision engine.

**Architecture:** TDD throughout — write a failing test first, then fix/implement the minimum code to make it pass. Tests live in `tests/` alongside the existing mock-BMC code. A shared `conftest.py` provides dataclass fixtures so each test file stays focused.

**Tech Stack:** Python 3.12, pytest, scikit-learn (IsolationForest), drain3, existing `ki.models` dataclasses

---

## File Structure

```
tests/
├── conftest.py                  ← create: shared pytest fixtures
├── test_post_code_fix.py        ← create: TDD for POST-code bug fix
├── test_ml_severity.py          ← create: TDD for ML severity escalation
├── test_parser.py               ← create: DrainLogParser unit tests
├── test_detector_rules.py       ← create: AnomalyDetector rule-check tests
└── test_healing_engine.py       ← create: HealingEngine decision matrix tests
ki/
├── collector/redfish_collector.py   ← modify line 160: wrong field name
└── detector/anomaly_detector.py    ← modify lines 221-231: hardcoded MEDIUM
```

---

### Task 1: pytest setup + conftest fixtures

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Check pytest is available**

  ```bash
  cd /home/lars/ZTP-KI-framework/ztp-ki-framework
  python -m pytest --version
  ```

  If missing: `pip install pytest`

- [ ] **Step 2: Create conftest.py with shared fixtures**

  ```python
  # tests/conftest.py
  from datetime import datetime, timezone

  import pytest

  from ki.models import (
      CollectorSnapshot, SelEntry, SensorReading,
  )


  def _ts() -> datetime:
      return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


  def make_snapshot(
      sensors: list[SensorReading] | None = None,
      sel_entries: list[SelEntry] | None = None,
      power_state: str = "On",
      post_code: str | None = None,
      target: str = "192.168.1.1",
  ) -> CollectorSnapshot:
      return CollectorSnapshot(
          target=target,
          timestamp=_ts(),
          sensors=sensors or [],
          sel_entries=sel_entries or [],
          post_code=post_code,
          power_state=power_state,
      )


  def make_temp_sensor(name: str, value: float, status: str = "OK") -> SensorReading:
      return SensorReading(name=name, value=value, unit="C", status=status, timestamp=_ts())


  def make_fan_sensor(name: str, rpm: float, status: str = "OK") -> SensorReading:
      return SensorReading(name=name, value=rpm, unit="RPM", status=status, timestamp=_ts())


  def make_power_sensor(name: str, watts: float) -> SensorReading:
      return SensorReading(name=name, value=watts, unit="W", status="OK", timestamp=_ts())


  def make_sel_entry(message: str, severity: str = "OK") -> SelEntry:
      return SelEntry(
          entry_id="1",
          timestamp=_ts(),
          message=message,
          severity=severity,
      )
  ```

- [ ] **Step 3: Verify conftest loads without error**

  ```bash
  cd /home/lars/ZTP-KI-framework/ztp-ki-framework
  python -m pytest tests/conftest.py --collect-only
  ```

  Expected: `no tests ran` (no test functions yet, but no import errors)

- [ ] **Step 4: Commit**

  ```bash
  git add tests/conftest.py
  git commit -m "test: add pytest conftest with shared snapshot fixtures"
  ```

---

### Task 2: Fix POST-code field (TDD)

**Files:**
- Create: `tests/test_post_code_fix.py`
- Modify: `ki/collector/redfish_collector.py:152-161`

- [ ] **Step 1: Write the failing test**

  ```python
  # tests/test_post_code_fix.py
  from unittest.mock import MagicMock, patch

  from ki.collector.redfish_collector import RedfishCollector


  def _make_collector() -> RedfishCollector:
      return RedfishCollector(username="admin", password="test", scheme="http")


  def test_post_code_read_from_boot_post_code():
      """_collect_system_state liest PostCode aus Boot.PostCode, nicht BootSourceOverrideEnabled."""
      collector = _make_collector()
      fake_response = {
          "PowerState": "On",
          "Boot": {
              "PostCode": "0xA0",
              "BootSourceOverrideEnabled": "Once",
          },
      }
      with patch.object(collector, "_get", return_value=fake_response):
          state, post_code = collector._collect_system_state("192.168.1.1")

      assert post_code == "0xA0"
      assert state == "On"


  def test_post_code_none_when_not_present():
      """Gibt None zurück wenn kein PostCode im Redfish-Response vorhanden."""
      collector = _make_collector()
      fake_response = {
          "PowerState": "Off",
          "Boot": {"BootSourceOverrideEnabled": "Disabled"},
      }
      with patch.object(collector, "_get", return_value=fake_response):
          state, post_code = collector._collect_system_state("192.168.1.1")

      assert post_code is None
      assert state == "Off"
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  cd /home/lars/ZTP-KI-framework/ztp-ki-framework
  python -m pytest tests/test_post_code_fix.py -v
  ```

  Expected: `FAILED` — `test_post_code_read_from_boot_post_code` liefert `"Once"` statt `"0xA0"`

- [ ] **Step 3: Fix `_collect_system_state` in `ki/collector/redfish_collector.py`**

  Replace line 160 (the `post_code` assignment):

  **Before:**
  ```python
  post_code   = data.get("Boot", {}).get("BootSourceOverrideEnabled")
  ```

  **After:**
  ```python
  post_code   = data.get("Boot", {}).get("PostCode")
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  cd /home/lars/ZTP-KI-framework/ztp-ki-framework
  python -m pytest tests/test_post_code_fix.py -v
  ```

  Expected: `2 passed`

- [ ] **Step 5: Commit**

  ```bash
  git add ki/collector/redfish_collector.py tests/test_post_code_fix.py
  git commit -m "fix: read Boot.PostCode instead of BootSourceOverrideEnabled"
  ```

---

### Task 3: Fix ML severity escalation (TDD)

**Files:**
- Create: `tests/test_ml_severity.py`
- Modify: `ki/detector/anomaly_detector.py:196-231`

- [ ] **Step 1: Write the failing tests**

  ```python
  # tests/test_ml_severity.py
  """
  Der Isolation Forest soll je nach Score die Severity eskalieren:
    score >= -0.1  → LOW   (marginaler Ausreißer)
    score  < -0.1  → MEDIUM
    score  < -0.3  → HIGH
  """
  from unittest.mock import MagicMock, patch
  import numpy as np

  from ki.detector.anomaly_detector import AnomalyDetector
  from ki.models import Severity

  from tests.conftest import make_snapshot, make_temp_sensor


  def _trained_detector() -> AnomalyDetector:
      """Gibt einen Detector zurück der bereits trainiert ist (kein Warmup)."""
      detector = AnomalyDetector()
      mock_model = MagicMock()
      detector._model = mock_model
      detector._trained = True
      return detector


  def test_ml_low_severity_for_marginal_outlier():
      detector = _trained_detector()
      # predict=-1 (Anomalie), score=-0.05 (marginal)
      detector._model.predict.return_value = np.array([-1])
      detector._model.score_samples.return_value = np.array([-0.05])

      snapshot = make_snapshot(sensors=[make_temp_sensor("CPU", 50.0)])
      result = detector._ml_check([50.0, 50.0, 6000.0, 6000.0, 350.0, 0.0], snapshot)

      assert result.is_anomaly is True
      assert result.severity == Severity.LOW


  def test_ml_medium_severity_for_moderate_outlier():
      detector = _trained_detector()
      detector._model.predict.return_value = np.array([-1])
      detector._model.score_samples.return_value = np.array([-0.2])

      snapshot = make_snapshot(sensors=[make_temp_sensor("CPU", 50.0)])
      result = detector._ml_check([50.0, 50.0, 6000.0, 6000.0, 350.0, 0.0], snapshot)

      assert result.is_anomaly is True
      assert result.severity == Severity.MEDIUM


  def test_ml_high_severity_for_strong_outlier():
      detector = _trained_detector()
      detector._model.predict.return_value = np.array([-1])
      detector._model.score_samples.return_value = np.array([-0.4])

      snapshot = make_snapshot(sensors=[make_temp_sensor("CPU", 50.0)])
      result = detector._ml_check([50.0, 50.0, 6000.0, 6000.0, 350.0, 0.0], snapshot)

      assert result.is_anomaly is True
      assert result.severity == Severity.HIGH


  def test_ml_ok_when_not_anomaly():
      detector = _trained_detector()
      detector._model.predict.return_value = np.array([1])
      detector._model.score_samples.return_value = np.array([0.1])

      snapshot = make_snapshot(sensors=[make_temp_sensor("CPU", 50.0)])
      result = detector._ml_check([50.0, 50.0, 6000.0, 6000.0, 350.0, 0.0], snapshot)

      assert result.is_anomaly is False
      assert result.severity == Severity.OK
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  cd /home/lars/ZTP-KI-framework/ztp-ki-framework
  python -m pytest tests/test_ml_severity.py -v
  ```

  Expected: `test_ml_low_severity_for_marginal_outlier` FAILED (returns MEDIUM, not LOW),
  `test_ml_high_severity_for_strong_outlier` FAILED (returns MEDIUM, not HIGH)

- [ ] **Step 3: Fix `_ml_check` in `ki/detector/anomaly_detector.py`**

  Replace lines 217–231 (the `is_anomaly`/`return` block at the end of `_ml_check`):

  **Before:**
  ```python
  x     = np.array([features])
  pred  = self._model.predict(x)[0]
  score = self._model.score_samples(x)[0]

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
  ```

  **After:**
  ```python
  x     = np.array([features])
  pred  = self._model.predict(x)[0]
  score = self._model.score_samples(x)[0]

  is_anomaly = pred == -1
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
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  cd /home/lars/ZTP-KI-framework/ztp-ki-framework
  python -m pytest tests/test_ml_severity.py -v
  ```

  Expected: `4 passed`

- [ ] **Step 5: Commit**

  ```bash
  git add ki/detector/anomaly_detector.py tests/test_ml_severity.py
  git commit -m "fix: escalate ML anomaly severity based on Isolation Forest score"
  ```

---

### Task 4: Unit tests for DrainLogParser

**Files:**
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write tests**

  ```python
  # tests/test_parser.py
  from ki.parser.drain3_parser import DrainLogParser
  from tests.conftest import make_sel_entry


  def test_parse_returns_one_event_per_entry():
      parser = DrainLogParser()
      entries = [
          make_sel_entry("CPU 1 temperature above warning threshold", "Warning"),
          make_sel_entry("Fan 1A speed normal", "OK"),
      ]
      events = parser.parse(entries)
      assert len(events) == 2


  def test_parse_preserves_raw_message():
      parser = DrainLogParser()
      msg = "DIMM_A1 correctable ECC error detected"
      events = parser.parse([make_sel_entry(msg, "Warning")])
      assert events[0].raw_message == msg


  def test_escalate_severity_on_uncorrectable_ecc():
      parser = DrainLogParser()
      entries = [make_sel_entry("DIMM_A1 uncorrectable ECC error detected", "Warning")]
      events = parser.parse(entries)
      assert events[0].severity == "Critical"


  def test_escalate_severity_on_fan_failure():
      parser = DrainLogParser()
      entries = [make_sel_entry("Fan 2A fan failure detected", "Warning")]
      events = parser.parse(entries)
      assert events[0].severity == "Critical"


  def test_no_escalation_on_normal_message():
      parser = DrainLogParser()
      entries = [make_sel_entry("System boot completed successfully", "OK")]
      events = parser.parse(entries)
      assert events[0].severity == "OK"


  def test_drain_clusters_similar_messages():
      """Gleiche Log-Struktur mit unterschiedlichen DIMM-Bezeichnern → selbes Template."""
      parser = DrainLogParser()
      entries = [
          make_sel_entry("DIMM_A1 correctable ECC error", "Warning"),
          make_sel_entry("DIMM_B2 correctable ECC error", "Warning"),
          make_sel_entry("DIMM_C3 correctable ECC error", "Warning"),
      ]
      events = parser.parse(entries)
      template_ids = {e.template_id for e in events}
      assert len(template_ids) == 1, "Alle drei Einträge sollten dasselbe Template erhalten"
  ```

- [ ] **Step 2: Run tests**

  ```bash
  cd /home/lars/ZTP-KI-framework/ztp-ki-framework
  python -m pytest tests/test_parser.py -v
  ```

  Expected: `6 passed`

- [ ] **Step 3: Commit**

  ```bash
  git add tests/test_parser.py
  git commit -m "test: add DrainLogParser unit tests"
  ```

---

### Task 5: Unit tests for AnomalyDetector rule-check

**Files:**
- Create: `tests/test_detector_rules.py`

- [ ] **Step 1: Write tests**

  ```python
  # tests/test_detector_rules.py
  from ki.detector.anomaly_detector import AnomalyDetector
  from ki.models import AnomalyType, Severity
  from tests.conftest import (
      make_snapshot, make_temp_sensor, make_fan_sensor,
      make_power_sensor, make_sel_entry,
  )


  def _detector() -> AnomalyDetector:
      return AnomalyDetector()


  def test_normal_sensors_return_ok():
      snapshot = make_snapshot(sensors=[
          make_temp_sensor("CPU 1", 45.0),
          make_fan_sensor("Fan 1", 6000.0),
          make_power_sensor("PSU", 350.0),
      ])
      result = _detector().detect(snapshot, [])
      assert result.is_anomaly is False
      assert result.severity == Severity.OK


  def test_temp_above_warn_threshold_returns_medium():
      snapshot = make_snapshot(sensors=[make_temp_sensor("CPU 1", 78.0)])
      result = _detector().detect(snapshot, [])
      assert result.is_anomaly is True
      assert result.severity == Severity.MEDIUM
      assert result.anomaly_type == AnomalyType.TEMPERATURE


  def test_temp_above_critical_threshold_returns_critical():
      snapshot = make_snapshot(sensors=[make_temp_sensor("CPU 1", 87.0)])
      result = _detector().detect(snapshot, [])
      assert result.is_anomaly is True
      assert result.severity == Severity.CRITICAL
      assert result.anomaly_type == AnomalyType.TEMPERATURE


  def test_fan_below_min_rpm_returns_high():
      snapshot = make_snapshot(sensors=[make_fan_sensor("Fan 2A", 200.0)])
      result = _detector().detect(snapshot, [])
      assert result.is_anomaly is True
      assert result.severity == Severity.HIGH
      assert result.anomaly_type == AnomalyType.FAN


  def test_power_above_max_returns_medium():
      snapshot = make_snapshot(sensors=[make_power_sensor("PSU", 1300.0)])
      result = _detector().detect(snapshot, [])
      assert result.is_anomaly is True
      assert result.severity == Severity.MEDIUM
      assert result.anomaly_type == AnomalyType.POWER


  def test_fan_at_zero_rpm_not_flagged():
      """RPM == 0 bedeutet Sensor nicht vorhanden, nicht Ausfall (0 < FAN_MIN_RPM prüft > 0)."""
      snapshot = make_snapshot(sensors=[make_fan_sensor("Fan X", 0.0)])
      result = _detector().detect(snapshot, [])
      assert result.is_anomaly is False


  def test_critical_rule_overrides_ml_warmup():
      """Regelbasiertes CRITICAL-Ergebnis wird zurückgegeben, auch während ML-Warmup."""
      from ki.parser.drain3_parser import DrainLogParser
      parser = DrainLogParser()
      sel = [make_sel_entry("DIMM_A1 uncorrectable ECC error detected", "Warning")]
      events = parser.parse(sel)
      snapshot = make_snapshot(
          sensors=[make_temp_sensor("CPU 1", 45.0)],
          sel_entries=sel,
      )
      result = _detector().detect(snapshot, events)
      assert result.is_anomaly is True
      assert result.severity == Severity.HIGH
      assert result.source == "rule"
  ```

- [ ] **Step 2: Run tests**

  ```bash
  cd /home/lars/ZTP-KI-framework/ztp-ki-framework
  python -m pytest tests/test_detector_rules.py -v
  ```

  Expected: `7 passed`

- [ ] **Step 3: Commit**

  ```bash
  git add tests/test_detector_rules.py
  git commit -m "test: add AnomalyDetector rule-check unit tests"
  ```

---

### Task 6: Unit tests for HealingEngine decision matrix

**Files:**
- Create: `tests/test_healing_engine.py`

- [ ] **Step 1: Write tests**

  ```python
  # tests/test_healing_engine.py
  from unittest.mock import patch

  from ki.decision.healing_engine import HealingEngine
  from ki.models import AnomalyResult, AnomalyType, HealingAction, Severity
  from tests.conftest import make_snapshot


  def _engine() -> HealingEngine:
      return HealingEngine(
          ansible_inventory="inventory/hosts.ini",
          redfish_user="admin",
          redfish_password="test",
      )


  def _anomaly(anomaly_type: AnomalyType, severity: Severity) -> AnomalyResult:
      return AnomalyResult(
          is_anomaly=True,
          anomaly_type=anomaly_type,
          severity=severity,
          confidence=1.0,
          details="test",
          source="rule",
          raw_snapshot=make_snapshot(),
      )


  def test_temp_critical_triggers_power_cycle():
      engine = _engine()
      anomaly = _anomaly(AnomalyType.TEMPERATURE, Severity.CRITICAL)
      with patch.object(engine, "_power_cycle", return_value=(True, "ok")) as mock:
          engine.handle(anomaly, "192.168.1.1")
          mock.assert_called_once()


  def test_temp_medium_triggers_alert():
      engine = _engine()
      anomaly = _anomaly(AnomalyType.TEMPERATURE, Severity.MEDIUM)
      with patch.object(engine, "_alert", return_value=(True, "ok")) as mock:
          engine.handle(anomaly, "192.168.1.1")
          mock.assert_called_once()


  def test_post_error_high_triggers_retry():
      engine = _engine()
      anomaly = _anomaly(AnomalyType.POST_ERROR, Severity.HIGH)
      with patch.object(engine, "_retry", return_value=(True, "ok")) as mock:
          engine.handle(anomaly, "192.168.1.1")
          mock.assert_called_once()


  def test_sel_critical_critical_triggers_rollback():
      engine = _engine()
      anomaly = _anomaly(AnomalyType.SEL_CRITICAL, Severity.CRITICAL)
      with patch.object(engine, "_rollback", return_value=(True, "ok")) as mock:
          engine.handle(anomaly, "192.168.1.1")
          mock.assert_called_once()


  def test_unknown_combination_defaults_to_alert():
      engine = _engine()
      # LOW severity ist nicht in der Matrix → ALERT
      anomaly = _anomaly(AnomalyType.TEMPERATURE, Severity.LOW)
      with patch.object(engine, "_alert", return_value=(True, "ok")) as mock:
          engine.handle(anomaly, "192.168.1.1")
          mock.assert_called_once()


  def test_handle_records_to_history():
      engine = _engine()
      anomaly = _anomaly(AnomalyType.TEMPERATURE, Severity.MEDIUM)
      with patch.object(engine, "_alert", return_value=(True, "alerted")):
          record = engine.handle(anomaly, "192.168.1.1")
      assert len(engine.history) == 1
      assert engine.history[0] is record
      assert record.action == HealingAction.ALERT
      assert record.success is True
  ```

- [ ] **Step 2: Run tests**

  ```bash
  cd /home/lars/ZTP-KI-framework/ztp-ki-framework
  python -m pytest tests/test_healing_engine.py -v
  ```

  Expected: `6 passed`

- [ ] **Step 3: Run complete test suite**

  ```bash
  cd /home/lars/ZTP-KI-framework/ztp-ki-framework
  python -m pytest tests/test_post_code_fix.py tests/test_ml_severity.py tests/test_parser.py tests/test_detector_rules.py tests/test_healing_engine.py -v
  ```

  Expected: `25 passed`

- [ ] **Step 4: Commit**

  ```bash
  git add tests/test_healing_engine.py
  git commit -m "test: add HealingEngine decision matrix unit tests"
  ```
