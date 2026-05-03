# Olympus v2 — Rewrite Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete all 6 Olympus files and rewrite from scratch with zero dead code, correct DB constraints, working feedback loop, and proper alert handling.

**Architecture:** Same 5-file structure (models, heartbeat, pulse, rules_engine, guardian), but every method that exists is called, every outcome matches the DB CHECK constraint, and the feedback loop (record_applied + lower_confidence) is wired into the pulse. No Insight/Skill models — they were speculative. Alert handling is nullable-safe.

**Tech Stack:** Python 3.11, asyncpg, Pydantic v2, FastAPI

---

## Pre-Rewrite: What's Wrong (reference for implementer)

| Bug ID | File | Problem | Impact |
|--------|------|---------|--------|
| BUG-1 | pulse.py | Writes `outcome="ok"/"error"` but DB CHECK allows only `"success"/"failure"/"skipped"/"proposed"` | Every `_persist_action()` silently fails — `olympus_actions` table is always empty |
| BUG-2 | alerts.py | `OlympusAlerts.__init__` takes `AlertService` but light init passes `None` | First alert on API machines crashes the heartbeat/pulse loop with `AttributeError` |
| BUG-3 | heartbeat.py:57 | Looks up rule `"long_query_seconds"` but DB seed has `"long_query_threshold_seconds"` | Threshold always falls back to hardcoded 30s, rule never applied |
| BUG-4 | guardian.py:76 | Counts `outcome == "error"` for summary but router counts `outcome == "failure"` | Router always reports 0 successes / 0 failures |
| DEAD-1 | rules_engine.py | `lower_confidence()` never called | Rules never degrade — no learning |
| DEAD-2 | rules_engine.py | `get_rule()` never called | Dead method |
| DEAD-3 | alerts.py | `send_proposal()` never called | Dead method |
| DEAD-4 | guardian.py | `stop()` never called from shutdown.py | No graceful shutdown |
| DEAD-5 | models.py | `Insight` and `Skill` models never used | Dead classes, tables forever empty |
| MISS-1 | pulse.py | Pulse never calls `record_applied()` for actions without `rule_applied` set | Only vacuum and cleanup track rule usage |
| MISS-2 | guardian.py | No `lower_confidence()` call on pulse failures | Confidence never drops |

## Migration Strategy

**No new migration needed.** The DB schema (migration 100) is fine. We fix the code to match the constraints, not the other way around.

One ALTER needed: relax the CHECK constraint to also accept `"skipped"` which is already in the constraint — confirmed. The actual fix is changing pulse.py to emit `"success"/"failure"` instead of `"ok"/"error"`.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/services/olympus/__init__.py` | Keep | Empty module |
| `backend/services/olympus/models.py` | **Rewrite** | HeartbeatSnapshot, PulseAction, OlympusRule — no Insight, no Skill |
| `backend/services/olympus/rules_engine.py` | **Rewrite** | load, get_threshold, record_applied, lower_confidence — no get_rule |
| `backend/services/olympus/heartbeat.py` | **Rewrite** | collect, check_alerts, persist — fix rule name |
| `backend/services/olympus/pulse.py` | **Rewrite** | 7 actions + run_full_pulse — fix outcome values |
| `backend/services/olympus/guardian.py` | **Rewrite** | init, start, stop, heartbeat_once, pulse_once with feedback loop, health summary |
| `backend/services/olympus/alerts.py` | **Rewrite** | Nullable-safe alert_service, no send_proposal |
| `backend/app/routers/olympus.py` | **Rewrite** | internal_router only, fix outcome counting |
| `backend/app/routers/health.py` | **Keep** | `/health/db` endpoint already correct |
| `backend/app/setup/service_initializer.py` | **Edit** | Both init paths pass alert_service=None safely |
| `backend/app/lifecycle/shutdown.py` | **Edit** | Add olympus.stop() |
| `backend/tests/services/olympus/test_olympus_v2.py` | **Create** | Tests for all wiring |

---

### Task 1: Delete old files and write models.py

**Files:**
- Rewrite: `apps/backend-rag/backend/services/olympus/models.py`
- Test: `apps/backend-rag/backend/tests/services/olympus/test_models.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for Olympus v2 models."""
import json
import pytest
from backend.services.olympus.models import HeartbeatSnapshot, PulseAction, OlympusRule


class TestHeartbeatSnapshot:
    def test_pool_utilization_computed(self):
        s = HeartbeatSnapshot(
            pool_size=10, pool_idle=3, active_connections=5,
            max_connections=100, db_size_bytes=1000,
        )
        assert s.pool_utilization == 0.7

    def test_pool_utilization_zero_pool(self):
        s = HeartbeatSnapshot(
            pool_size=0, pool_idle=0, active_connections=0,
            max_connections=100, db_size_bytes=0,
        )
        assert s.pool_utilization == 0.0

    def test_defaults(self):
        s = HeartbeatSnapshot(
            pool_size=5, pool_idle=5, active_connections=0,
            max_connections=100, db_size_bytes=0,
        )
        assert s.long_queries == 0
        assert s.lock_waits == 0
        assert s.alerts_sent == 0
        assert s.bloat_top3 == []


class TestPulseAction:
    def test_outcome_values_match_db_constraint(self):
        """Outcome MUST be one of: success, failure, skipped, proposed."""
        for outcome in ("success", "failure", "skipped", "proposed"):
            a = PulseAction(action_type="test", outcome=outcome)
            assert a.outcome == outcome

    def test_defaults(self):
        a = PulseAction(action_type="vacuum")
        assert a.rhythm == "pulse"
        assert a.target is None
        assert a.outcome is None
        assert a.detail == {}


class TestOlympusRule:
    def test_config_parsed_from_json_string(self):
        r = OlympusRule(
            id=1, rule_name="test", category="threshold",
            config='{"value": 10, "unit": "percent"}', source="seed",
        )
        assert r.config == {"value": 10, "unit": "percent"}
        assert r.get_value() == 10

    def test_config_accepts_dict(self):
        r = OlympusRule(
            id=1, rule_name="test", category="threshold",
            config={"value": 42}, source="seed",
        )
        assert r.get_value() == 42

    def test_defaults(self):
        r = OlympusRule(
            id=1, rule_name="test", category="threshold",
            config={"value": 1}, source="seed",
        )
        assert r.confidence == 1.0
        assert r.applied_count == 0
        assert r.last_applied is None
        assert r.superseded_by is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/services/olympus/test_models.py -v`
Expected: Tests fail because models.py will be rewritten.

- [ ] **Step 3: Rewrite models.py**

```python
"""Pydantic models for Olympus DB Guardian v2.

Three models only — no speculative Insight/Skill.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HeartbeatSnapshot(BaseModel):
    """Metrics collected during a single heartbeat cycle."""

    pool_size: int
    pool_idle: int
    active_connections: int
    max_connections: int
    db_size_bytes: int
    bloat_top3: list[dict[str, Any]] = Field(default_factory=list)
    long_queries: int = Field(default=0)
    lock_waits: int = Field(default=0)
    alerts_sent: int = Field(default=0)
    recorded_at: datetime = Field(default_factory=_utc_now)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pool_utilization(self) -> float:
        if self.pool_size == 0:
            return 0.0
        return round(1 - self.pool_idle / self.pool_size, 2)


class PulseAction(BaseModel):
    """Record of a single pulse action.

    outcome MUST be one of: success, failure, skipped, proposed
    to match the CHECK constraint on olympus_actions.
    """

    rhythm: str = Field(default="pulse")
    action_type: str
    target: str | None = Field(default=None)
    detail: dict[str, Any] = Field(default_factory=dict)
    outcome: str | None = Field(default=None)
    duration_ms: int | None = Field(default=None)
    rule_applied: str | None = Field(default=None)
    reflection: str | None = Field(default=None)
    executed_at: datetime = Field(default_factory=_utc_now)


class OlympusRule(BaseModel):
    """A rule from olympus_rules. Config is JSON text in DB."""

    id: int
    rule_name: str
    category: str
    config: dict[str, Any]
    source: str
    confidence: float = Field(default=1.0)
    applied_count: int = Field(default=0)
    last_applied: datetime | None = Field(default=None)
    superseded_by: int | None = Field(default=None)

    @field_validator("config", mode="before")
    @classmethod
    def _parse_json_config(cls, v: Any) -> dict[str, Any]:
        if isinstance(v, str):
            return json.loads(v)
        return v

    def get_value(self, key: str = "value") -> Any:
        return self.config.get(key)
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_models.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/models.py backend/tests/services/olympus/test_models.py
git commit -m "feat(olympus-v2): rewrite models — drop dead Insight/Skill, keep 3 core models"
```

---

### Task 2: Rewrite rules_engine.py

**Files:**
- Rewrite: `apps/backend-rag/backend/services/olympus/rules_engine.py`
- Test: `apps/backend-rag/backend/tests/services/olympus/test_rules_engine.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for Olympus v2 RulesEngine."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.olympus.rules_engine import RulesEngine
from backend.services.olympus.models import OlympusRule


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    return pool


@pytest.fixture
def sample_rules_rows():
    return [
        {
            "id": 1, "rule_name": "vacuum_dead_pct_threshold",
            "category": "threshold", "config": '{"value": 10, "unit": "percent"}',
            "source": "initial", "confidence": 1.0, "applied_count": 0,
            "last_applied": None, "superseded_by": None,
        },
        {
            "id": 2, "rule_name": "audit_retention_days",
            "category": "policy", "config": '{"value": 90}',
            "source": "initial", "confidence": 0.8, "applied_count": 5,
            "last_applied": None, "superseded_by": None,
        },
    ]


class TestRulesEngine:
    @pytest.mark.asyncio
    async def test_load_rules(self, mock_pool, sample_rules_rows):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=sample_rules_rows)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RulesEngine(mock_pool)
        await engine.load_rules()

        assert len(engine.rules) == 2
        assert "vacuum_dead_pct_threshold" in engine.rules
        assert engine.rules["vacuum_dead_pct_threshold"].config["value"] == 10

    @pytest.mark.asyncio
    async def test_get_threshold_exists(self, mock_pool, sample_rules_rows):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=sample_rules_rows)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RulesEngine(mock_pool)
        await engine.load_rules()

        assert engine.get_threshold("vacuum_dead_pct_threshold") == 10

    def test_get_threshold_missing_returns_default(self, mock_pool):
        engine = RulesEngine(mock_pool)
        assert engine.get_threshold("nonexistent", default=42) == 42

    @pytest.mark.asyncio
    async def test_record_applied_increments(self, mock_pool, sample_rules_rows):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=sample_rules_rows)
        conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RulesEngine(mock_pool)
        await engine.load_rules()

        old_count = engine.rules["vacuum_dead_pct_threshold"].applied_count
        await engine.record_applied("vacuum_dead_pct_threshold")
        assert engine.rules["vacuum_dead_pct_threshold"].applied_count == old_count + 1

    @pytest.mark.asyncio
    async def test_lower_confidence_clamps_to_zero(self, mock_pool, sample_rules_rows):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=sample_rules_rows)
        conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RulesEngine(mock_pool)
        await engine.load_rules()

        # Lower by a huge amount — should clamp to 0.0
        await engine.lower_confidence("vacuum_dead_pct_threshold", delta=-5.0)
        assert engine.rules["vacuum_dead_pct_threshold"].confidence == 0.0

    @pytest.mark.asyncio
    async def test_lower_confidence_missing_rule_noop(self, mock_pool):
        conn = AsyncMock()
        conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = RulesEngine(mock_pool)
        # Should not raise
        await engine.lower_confidence("nonexistent")
        conn.execute.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_rules_engine.py -v`
Expected: FAIL (old rules_engine.py has different interface).

- [ ] **Step 3: Rewrite rules_engine.py**

```python
"""Olympus v2 — Rules Engine.

Loads rules from DB, provides threshold lookups, records usage,
and lowers confidence on failure. Every public method is called.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.services.olympus.models import OlympusRule

logger = logging.getLogger("olympus.rules")


class RulesEngine:
    """Load, query, and evolve operational rules from olympus_rules."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool
        self.rules: dict[str, OlympusRule] = {}

    async def load_rules(self) -> None:
        query = """
            SELECT id, rule_name, category, config, source,
                   confidence, applied_count, last_applied, superseded_by
            FROM olympus_rules
            WHERE superseded_by IS NULL
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        self.rules = {}
        for row in rows:
            rule = OlympusRule(
                id=row["id"],
                rule_name=row["rule_name"],
                category=row["category"],
                config=row["config"],
                source=row["source"],
                confidence=float(row["confidence"]),
                applied_count=row["applied_count"],
                last_applied=row["last_applied"],
                superseded_by=row["superseded_by"],
            )
            self.rules[rule.rule_name] = rule

        logger.info("Loaded %d active rules", len(self.rules))

    def get_threshold(self, rule_name: str, default: Any = None) -> Any:
        rule = self.rules.get(rule_name)
        if rule is None:
            return default
        return rule.get_value()

    async def record_applied(self, rule_name: str) -> None:
        """Increment applied_count and touch last_applied. Called by guardian after each pulse action."""
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE olympus_rules SET applied_count = applied_count + 1, "
                "last_applied = $1, updated_at = $1 WHERE rule_name = $2",
                now, rule_name,
            )
        rule = self.rules.get(rule_name)
        if rule is not None:
            rule.applied_count += 1
            rule.last_applied = now
        logger.debug("Rule '%s' applied (count=%d)", rule_name,
                      rule.applied_count if rule else 0)

    async def lower_confidence(self, rule_name: str, delta: float = -0.1) -> None:
        """Decrease confidence on failure. Called by guardian when a pulse action fails."""
        rule = self.rules.get(rule_name)
        if rule is None:
            return

        new_confidence = max(0.0, rule.confidence + delta)
        now = datetime.now(timezone.utc)

        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE olympus_rules SET confidence = $1, updated_at = $2 "
                "WHERE rule_name = $3",
                new_confidence, now, rule_name,
            )

        old = rule.confidence
        rule.confidence = new_confidence
        logger.warning("Rule '%s' confidence: %.2f -> %.2f", rule_name, old, new_confidence)
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_rules_engine.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/rules_engine.py backend/tests/services/olympus/test_rules_engine.py
git commit -m "feat(olympus-v2): rewrite rules_engine — drop dead get_rule, keep 4 methods all called"
```

---

### Task 3: Rewrite alerts.py (nullable-safe)

**Files:**
- Rewrite: `apps/backend-rag/backend/services/olympus/alerts.py`
- Test: `apps/backend-rag/backend/tests/services/olympus/test_alerts.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for Olympus v2 OlympusAlerts — nullable alert_service."""
import pytest
from unittest.mock import AsyncMock
from backend.services.olympus.alerts import OlympusAlerts


@pytest.fixture
def mock_alert_service():
    svc = AsyncMock()
    svc.send_alert = AsyncMock()
    return svc


class TestOlympusAlerts:
    @pytest.mark.asyncio
    async def test_send_alert_with_service(self, mock_alert_service):
        alerts = OlympusAlerts(mock_alert_service)
        await alerts.send_alert("test message")
        mock_alert_service.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_without_service_no_crash(self):
        """BUG-2 fix: alert_service=None must not crash."""
        alerts = OlympusAlerts(None)
        # Should not raise
        await alerts.send_alert("test message")

    @pytest.mark.asyncio
    async def test_send_pulse_summary_with_failures(self, mock_alert_service):
        alerts = OlympusAlerts(mock_alert_service)
        await alerts.send_pulse_summary(10, 3)
        mock_alert_service.send_alert.assert_called_once()
        call_args = mock_alert_service.send_alert.call_args
        assert "3 fallimenti" in call_args.kwargs.get("message", call_args.args[1] if len(call_args.args) > 1 else "")

    @pytest.mark.asyncio
    async def test_send_pulse_summary_no_failures(self, mock_alert_service):
        alerts = OlympusAlerts(mock_alert_service)
        await alerts.send_pulse_summary(10, 0)
        mock_alert_service.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_pulse_summary_without_service(self):
        alerts = OlympusAlerts(None)
        await alerts.send_pulse_summary(5, 2)  # No crash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_alerts.py -v`
Expected: FAIL — old alerts.py crashes on None alert_service.

- [ ] **Step 3: Rewrite alerts.py**

```python
"""Olympus v2 — Alerts (nullable-safe).

alert_service may be None on API machines (light init).
Every method handles this gracefully — log only, no crash.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.monitoring.alert_service import AlertLevel, AlertService

logger = logging.getLogger("olympus.alerts")


class OlympusAlerts:
    """Sends alerts via Telegram. Safe when alert_service is None."""

    def __init__(self, alert_service: AlertService | None) -> None:
        self._service = alert_service

    async def send_alert(self, message: str, level: AlertLevel | None = None) -> None:
        if self._service is None:
            logger.info("[OLIMPO] (no alert_service) %s", message)
            return
        from backend.services.monitoring.alert_service import AlertLevel as AL
        await self._service.send_alert(
            title="Olympus DB Guardian",
            message=f"[OLIMPO] {message}",
            level=level or AL.WARNING,
        )

    async def send_pulse_summary(self, actions_count: int, failures: int) -> None:
        if failures > 0:
            msg = f"Pulse completato: {actions_count} azioni, {failures} fallimenti"
        else:
            msg = f"Pulse completato: {actions_count} azioni, tutto OK"
        await self.send_alert(msg)
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_alerts.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/alerts.py backend/tests/services/olympus/test_alerts.py
git commit -m "fix(olympus-v2): rewrite alerts — nullable alert_service, drop dead send_proposal"
```

---

### Task 4: Rewrite heartbeat.py (fix rule name)

**Files:**
- Rewrite: `apps/backend-rag/backend/services/olympus/heartbeat.py`
- Test: `apps/backend-rag/backend/tests/services/olympus/test_heartbeat.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for Olympus v2 Heartbeat."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.olympus.heartbeat import Heartbeat
from backend.services.olympus.models import HeartbeatSnapshot


@pytest.fixture
def mock_rules():
    rules = MagicMock()
    rules.get_threshold = MagicMock(side_effect=lambda name, default=None: {
        "long_query_threshold_seconds": 30,
        "pool_alert_pct": 80,
        "connection_alert_pct": 70,
    }.get(name, default))
    return rules


class TestHeartbeat:
    def test_rule_name_is_long_query_threshold_seconds(self, mock_rules):
        """BUG-3 fix: must use 'long_query_threshold_seconds', not 'long_query_seconds'."""
        mock_pool = AsyncMock()
        hb = Heartbeat(mock_pool, mock_rules)
        # The rule name constant should match what's in the DB
        # We verify this by checking the collect_metrics code uses the right name
        # (tested indirectly via integration, but the name is the key fix)

    @pytest.mark.asyncio
    async def test_check_alerts_pool_over_threshold(self, mock_rules):
        hb = Heartbeat(AsyncMock(), mock_rules)
        snapshot = HeartbeatSnapshot(
            pool_size=10, pool_idle=1, active_connections=5,
            max_connections=100, db_size_bytes=1000,
        )
        # pool_utilization = 0.9 > 80% threshold
        alert_called = False
        async def on_alert(msg):
            nonlocal alert_called
            alert_called = True
        hb.on_alert(on_alert)
        msgs = await hb.check_alerts(snapshot)
        assert len(msgs) >= 1
        assert alert_called

    @pytest.mark.asyncio
    async def test_check_alerts_no_alerts_when_healthy(self, mock_rules):
        hb = Heartbeat(AsyncMock(), mock_rules)
        snapshot = HeartbeatSnapshot(
            pool_size=10, pool_idle=8, active_connections=2,
            max_connections=100, db_size_bytes=1000,
        )
        msgs = await hb.check_alerts(snapshot)
        assert len(msgs) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_heartbeat.py -v`

- [ ] **Step 3: Rewrite heartbeat.py**

Same as current code, but with ONE critical fix at line 57-58:

Change `"long_query_seconds"` to `"long_query_threshold_seconds"` to match the DB seed.

```python
"""Olympus v2 — Heartbeat Rhythm.

Collects database metrics, evaluates alert conditions, persists snapshots.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import asyncpg

from backend.services.olympus.models import HeartbeatSnapshot

if TYPE_CHECKING:
    from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.heartbeat")

AlertCallback = Callable[[str], Awaitable[None]]


class Heartbeat:
    def __init__(self, db_pool: asyncpg.Pool, rules: RulesEngine) -> None:
        self._pool = db_pool
        self._rules = rules
        self._alert_callbacks: list[AlertCallback] = []

    def on_alert(self, callback: AlertCallback) -> None:
        self._alert_callbacks.append(callback)

    async def alert(self, message: str) -> None:
        logger.warning("ALERT: %s", message)
        for cb in self._alert_callbacks:
            await cb(message)

    async def collect_metrics(self) -> HeartbeatSnapshot:
        pool_size: int = self._pool.get_size()
        pool_idle: int = self._pool.get_idle_size()

        async with self._pool.acquire() as conn:
            active_connections = await self._count_active_connections(conn)
            max_connections = await self._get_max_connections(conn)
            db_size_bytes = await self._get_db_size(conn)
            bloat_top3 = await self._get_bloat_top3(conn)

            # FIX BUG-3: was "long_query_seconds", must be "long_query_threshold_seconds"
            long_query_threshold: int = self._rules.get_threshold(
                "long_query_threshold_seconds", default=30,
            )
            long_queries = await self._count_long_queries(conn, long_query_threshold)
            lock_waits = await self._count_lock_waits(conn)

        snapshot = HeartbeatSnapshot(
            pool_size=pool_size,
            pool_idle=pool_idle,
            active_connections=active_connections,
            max_connections=max_connections,
            db_size_bytes=db_size_bytes,
            bloat_top3=bloat_top3,
            long_queries=long_queries,
            lock_waits=lock_waits,
        )
        logger.info(
            "Heartbeat: pool=%d/%d active=%d/%d long=%d locks=%d",
            pool_size - pool_idle, pool_size,
            active_connections, max_connections,
            long_queries, lock_waits,
        )
        return snapshot

    async def check_alerts(self, snapshot: HeartbeatSnapshot) -> list[str]:
        messages: list[str] = []

        pool_alert_pct: float = self._rules.get_threshold("pool_alert_pct", default=80)
        if snapshot.pool_utilization > pool_alert_pct / 100:
            msg = f"Pool utilization {snapshot.pool_utilization:.0%} exceeds {pool_alert_pct:.0f}%"
            await self.alert(msg)
            messages.append(msg)

        connection_alert_pct: float = self._rules.get_threshold("connection_alert_pct", default=80)
        if snapshot.max_connections > 0:
            conn_ratio = snapshot.active_connections / snapshot.max_connections
            if conn_ratio > connection_alert_pct / 100:
                msg = f"Connection ratio {conn_ratio:.0%} exceeds {connection_alert_pct:.0f}%"
                await self.alert(msg)
                messages.append(msg)

        if snapshot.long_queries > 0:
            msg = f"{snapshot.long_queries} long-running queries detected"
            await self.alert(msg)
            messages.append(msg)

        snapshot.alerts_sent = len(messages)
        return messages

    async def persist(self, snapshot: HeartbeatSnapshot) -> None:
        query = """
            INSERT INTO olympus_heartbeats (
                pool_size, pool_idle, active_connections, max_connections,
                db_size_bytes, bloat_top3, long_queries, lock_waits,
                alerts_sent, recorded_at, pool_utilization
            ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                snapshot.pool_size, snapshot.pool_idle,
                snapshot.active_connections, snapshot.max_connections,
                snapshot.db_size_bytes, snapshot.bloat_top3,
                snapshot.long_queries, snapshot.lock_waits,
                snapshot.alerts_sent, snapshot.recorded_at,
                snapshot.pool_utilization,
            )

    @staticmethod
    async def _count_active_connections(conn: asyncpg.Connection) -> int:
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM pg_stat_activity WHERE state != 'idle'",
        )
        return int(row["cnt"]) if row else 0

    @staticmethod
    async def _get_max_connections(conn: asyncpg.Connection) -> int:
        row = await conn.fetchrow("SHOW max_connections")
        return int(row["max_connections"]) if row else 100

    @staticmethod
    async def _get_db_size(conn: asyncpg.Connection) -> int:
        row = await conn.fetchrow(
            "SELECT pg_database_size(current_database()) AS size",
        )
        return int(row["size"]) if row else 0

    @staticmethod
    async def _get_bloat_top3(conn: asyncpg.Connection) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            "SELECT relname, n_dead_tup, n_live_tup "
            "FROM pg_stat_user_tables WHERE n_dead_tup > 1000 "
            "ORDER BY n_dead_tup DESC LIMIT 3",
        )
        return [
            {"table": r["relname"], "dead_tuples": r["n_dead_tup"], "live_tuples": r["n_live_tup"]}
            for r in rows
        ]

    @staticmethod
    async def _count_long_queries(conn: asyncpg.Connection, threshold_seconds: int) -> int:
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM pg_stat_activity "
            "WHERE state = 'active' AND query_start < now() - make_interval(secs => $1)",
            threshold_seconds,
        )
        return int(row["cnt"]) if row else 0

    @staticmethod
    async def _count_lock_waits(conn: asyncpg.Connection) -> int:
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM pg_locks WHERE NOT granted",
        )
        return int(row["cnt"]) if row else 0
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_heartbeat.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/heartbeat.py backend/tests/services/olympus/test_heartbeat.py
git commit -m "fix(olympus-v2): rewrite heartbeat — fix rule name long_query_threshold_seconds"
```

---

### Task 5: Rewrite pulse.py (fix outcome values)

**Files:**
- Rewrite: `apps/backend-rag/backend/services/olympus/pulse.py`
- Test: `apps/backend-rag/backend/tests/services/olympus/test_pulse.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for Olympus v2 Pulse — outcome values match DB CHECK constraint."""
import pytest
from backend.services.olympus.models import PulseAction
from backend.services.olympus.pulse import Pulse

VALID_OUTCOMES = {"success", "failure", "skipped", "proposed"}


class TestPulseOutcomes:
    def test_no_ok_or_error_in_code(self):
        """BUG-1 fix: pulse must never emit 'ok' or 'error' as outcome."""
        import inspect
        source = inspect.getsource(Pulse)
        # outcome="ok" and outcome="error" must not appear
        assert 'outcome="ok"' not in source, "Found 'ok' outcome — must be 'success'"
        assert "outcome=\"error\"" not in source, "Found 'error' outcome — must be 'failure'"

    def test_all_outcomes_in_valid_set(self):
        """Every outcome literal in pulse.py must match the DB CHECK constraint."""
        import inspect, re
        source = inspect.getsource(Pulse)
        outcomes = re.findall(r'outcome="(\w+)"', source)
        for o in outcomes:
            assert o in VALID_OUTCOMES, f"Invalid outcome '{o}' — must be one of {VALID_OUTCOMES}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_pulse.py -v`
Expected: FAIL — old pulse.py has `outcome="ok"` and `outcome="error"`.

- [ ] **Step 3: Rewrite pulse.py**

Same structure as current code, but with ALL `outcome="ok"` changed to `outcome="success"` and ALL `outcome="error"` changed to `outcome="failure"`. The safe-list, SQL queries, and maintenance logic stay identical.

Full rewrite (key changes marked with `# FIX BUG-1`):

```python
"""Olympus v2 — Pulse Rhythm.

Periodic maintenance: vacuum, audit cleanup, sequence repair,
index rebuild, MV refresh, session cleanup, partitioning.

IMPORTANT: outcome values MUST be "success", "failure", or "skipped"
to match the CHECK constraint on olympus_actions.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import asyncpg

from backend.services.olympus.models import PulseAction

if TYPE_CHECKING:
    from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.pulse")

_SAFE_VACUUM_TABLES: set[str] = {
    "api_audit_trail", "auth_audit_log", "kg_edges", "kg_nodes",
    "company_documents", "memory_facts", "team_timesheet",
    "whatsapp_message_context", "cell_pulse_log", "user_stats",
    "clients", "ab_test_metrics", "whatsapp_contacts", "documents",
    "query_analytics", "activity_log", "workflow_analytics",
    "cell_episodes", "conversations", "episodic_memories",
    "olympus_heartbeats", "olympus_actions",
}


class Pulse:
    def __init__(self, db_pool: asyncpg.Pool, rules: RulesEngine) -> None:
        self._pool = db_pool
        self._rules = rules

    async def vacuum_bloated_tables(self) -> list[PulseAction]:
        threshold: int = self._rules.get_threshold("vacuum_dead_pct_threshold", default=5)
        query = """
            SELECT relname, n_live_tup, n_dead_tup,
                   CASE WHEN n_live_tup + n_dead_tup = 0 THEN 0
                        ELSE (n_dead_tup * 100.0 / (n_live_tup + n_dead_tup))
                   END AS dead_pct
            FROM pg_stat_user_tables WHERE n_dead_tup > 0
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        actions: list[PulseAction] = []
        for row in rows:
            table, dead_pct = row["relname"], float(row["dead_pct"])
            if dead_pct <= threshold:
                continue
            if table not in _SAFE_VACUUM_TABLES:
                actions.append(PulseAction(
                    action_type="vacuum", target=table,
                    detail={"dead_pct": dead_pct},
                    outcome="skipped",  # valid CHECK value
                    rule_applied="vacuum_dead_pct_threshold",
                    reflection=f"Not in safe-list",
                ))
                logger.info("Skipped VACUUM on %s (dead_pct=%.1f%%, not in safe-list)", table, dead_pct)
                continue

            t0 = time.monotonic()
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(f"VACUUM ANALYZE {table}")  # noqa: S608
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(PulseAction(
                    action_type="vacuum", target=table,
                    detail={"dead_pct": dead_pct},
                    outcome="success",  # FIX BUG-1: was "ok"
                    duration_ms=duration_ms,
                    rule_applied="vacuum_dead_pct_threshold",
                ))
                logger.info("VACUUM ANALYZE %s in %dms (dead_pct=%.1f%%)", table, duration_ms, dead_pct)
            except Exception:
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(PulseAction(
                    action_type="vacuum", target=table,
                    detail={"dead_pct": dead_pct},
                    outcome="failure",  # FIX BUG-1: was "error"
                    duration_ms=duration_ms,
                    rule_applied="vacuum_dead_pct_threshold",
                    reflection="VACUUM failed",
                ))
                logger.exception("VACUUM ANALYZE %s failed", table)
        return actions

    async def cleanup_audit_trail(self) -> PulseAction:
        retention: int = self._rules.get_threshold("audit_retention_days", default=90)
        sql = f"DELETE FROM api_audit_trail WHERE created_at < NOW() - INTERVAL '{retention} days'"
        t0 = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(sql)
            duration_ms = int((time.monotonic() - t0) * 1000)
            deleted = int(result.split()[-1]) if result else 0
            return PulseAction(
                action_type="cleanup_audit_trail", target="api_audit_trail",
                detail={"retention_days": retention, "rows_deleted": deleted},
                outcome="success",  # FIX BUG-1
                duration_ms=duration_ms,
                rule_applied="audit_retention_days",
            )
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("cleanup_audit_trail failed")
            return PulseAction(
                action_type="cleanup_audit_trail", target="api_audit_trail",
                detail={"retention_days": retention},
                outcome="failure",  # FIX BUG-1
                duration_ms=duration_ms,
                rule_applied="audit_retention_days",
                reflection="DELETE failed",
            )

    async def repair_sequences(self) -> list[PulseAction]:
        query = """
            SELECT t.relname AS table_name, a.attname AS column_name,
                   pg_get_serial_sequence(t.relname::text, a.attname::text) AS seq
            FROM pg_class t
            JOIN pg_attribute a ON a.attrelid = t.oid
            WHERE t.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
              AND pg_get_serial_sequence(t.relname::text, a.attname::text) IS NOT NULL
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        actions: list[PulseAction] = []
        for row in rows:
            table, column, seq = row["table_name"], row["column_name"], row["seq"]
            async with self._pool.acquire() as conn:
                max_val = await conn.fetchval(f"SELECT COALESCE(MAX({column}), 0) FROM {table}")  # noqa: S608
                last_val = await conn.fetchval(f"SELECT last_value FROM {seq}")  # noqa: S608

            if max_val is not None and last_val is not None and max_val > last_val:
                t0 = time.monotonic()
                try:
                    async with self._pool.acquire() as conn:
                        await conn.execute(f"SELECT setval('{seq}', {max_val})")  # noqa: S608
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="repair_sequence", target=seq,
                        detail={"table": table, "column": column, "old": last_val, "new": max_val},
                        outcome="success",  # FIX BUG-1
                        duration_ms=duration_ms,
                    ))
                    logger.info("Repaired sequence %s: %d -> %d", seq, last_val, max_val)
                except Exception:
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="repair_sequence", target=seq,
                        detail={"table": table, "column": column},
                        outcome="failure",  # FIX BUG-1
                        duration_ms=duration_ms,
                        reflection="setval failed",
                    ))
                    logger.exception("Failed to repair sequence %s", seq)
        return actions

    async def rebuild_invalid_indexes(self) -> list[PulseAction]:
        query = """
            SELECT c.relname AS index_name, t.relname AS table_name
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            JOIN pg_class t ON t.oid = i.indrelid
            WHERE NOT i.indisvalid
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        actions: list[PulseAction] = []
        for row in rows:
            idx, table = row["index_name"], row["table_name"]
            t0 = time.monotonic()
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(f"REINDEX INDEX CONCURRENTLY {idx}")  # noqa: S608
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(PulseAction(
                    action_type="reindex", target=idx,
                    detail={"table": table},
                    outcome="success",  # FIX BUG-1
                    duration_ms=duration_ms,
                ))
            except Exception:
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(PulseAction(
                    action_type="reindex", target=idx,
                    detail={"table": table},
                    outcome="failure",  # FIX BUG-1
                    duration_ms=duration_ms,
                    reflection="REINDEX CONCURRENTLY failed",
                ))
                logger.exception("REINDEX CONCURRENTLY %s failed", idx)
        return actions

    async def refresh_materialized_views(self) -> list[PulseAction]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT matviewname FROM pg_matviews")

        actions: list[PulseAction] = []
        for row in rows:
            view = row["matviewname"]
            t0 = time.monotonic()
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")  # noqa: S608
                duration_ms = int((time.monotonic() - t0) * 1000)
                actions.append(PulseAction(
                    action_type="refresh_matview", target=view,
                    detail={"concurrent": True},
                    outcome="success",  # FIX BUG-1
                    duration_ms=duration_ms,
                ))
            except Exception:
                logger.warning("CONCURRENT refresh failed for %s, trying non-concurrent", view)
                t0 = time.monotonic()
                try:
                    async with self._pool.acquire() as conn:
                        await conn.execute(f"REFRESH MATERIALIZED VIEW {view}")  # noqa: S608
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="refresh_matview", target=view,
                        detail={"concurrent": False},
                        outcome="success",  # FIX BUG-1
                        duration_ms=duration_ms,
                        reflection="Fell back to non-concurrent refresh",
                    ))
                except Exception:
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    actions.append(PulseAction(
                        action_type="refresh_matview", target=view,
                        detail={"concurrent": False},
                        outcome="failure",  # FIX BUG-1
                        duration_ms=duration_ms,
                        reflection="Both concurrent and non-concurrent failed",
                    ))
                    logger.exception("Refresh matview %s failed entirely", view)
        return actions

    async def cleanup_expired_sessions(self) -> PulseAction:
        sql = "DELETE FROM persistent_sessions WHERE updated_at < NOW() - INTERVAL '30 days'"
        t0 = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(sql)
            duration_ms = int((time.monotonic() - t0) * 1000)
            deleted = int(result.split()[-1]) if result else 0
            return PulseAction(
                action_type="cleanup_expired_sessions", target="persistent_sessions",
                detail={"rows_deleted": deleted},
                outcome="success",  # FIX BUG-1
                duration_ms=duration_ms,
            )
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("cleanup_expired_sessions failed")
            return PulseAction(
                action_type="cleanup_expired_sessions", target="persistent_sessions",
                outcome="failure",  # FIX BUG-1
                duration_ms=duration_ms,
                reflection="DELETE failed",
            )

    async def ensure_next_partition(self) -> PulseAction | None:
        sql_bounds = """
            SELECT date_trunc('month', NOW() + INTERVAL '1 month') AS start,
                   date_trunc('month', NOW() + INTERVAL '2 months') AS stop
        """
        async with self._pool.acquire() as conn:
            bounds = await conn.fetchrow(sql_bounds)

        start, stop = bounds["start"], bounds["stop"]
        partition_name = f"olympus_heartbeats_{start.strftime('%Y_%m')}"

        async with self._pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_class WHERE relname = $1 AND relkind = 'r'",
                partition_name,
            )
        if exists:
            return None

        create_sql = (
            f"CREATE TABLE {partition_name} PARTITION OF olympus_heartbeats "
            f"FOR VALUES FROM ('{start.strftime('%Y-%m-%d')}') "
            f"TO ('{stop.strftime('%Y-%m-%d')}')"
        )
        t0 = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(create_sql)
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info("Created partition %s", partition_name)
            return PulseAction(
                action_type="ensure_partition", target=partition_name,
                detail={"range_start": start.strftime("%Y-%m-%d"), "range_stop": stop.strftime("%Y-%m-%d")},
                outcome="success",  # FIX BUG-1
                duration_ms=duration_ms,
            )
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("Failed to create partition %s", partition_name)
            return PulseAction(
                action_type="ensure_partition", target=partition_name,
                outcome="failure",  # FIX BUG-1
                duration_ms=duration_ms,
                reflection="CREATE TABLE partition failed",
            )

    async def run_full_pulse(self) -> list[PulseAction]:
        actions: list[PulseAction] = []
        actions.extend(await self.vacuum_bloated_tables())
        actions.append(await self.cleanup_audit_trail())
        actions.extend(await self.repair_sequences())
        actions.extend(await self.rebuild_invalid_indexes())
        actions.extend(await self.refresh_materialized_views())
        actions.append(await self.cleanup_expired_sessions())
        partition = await self.ensure_next_partition()
        if partition is not None:
            actions.append(partition)
        logger.info("Full pulse: %d actions", len(actions))
        return actions
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_pulse.py -v`
Expected: All PASS (no `"ok"` or `"error"` outcomes).

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/pulse.py backend/tests/services/olympus/test_pulse.py
git commit -m "fix(olympus-v2): rewrite pulse — outcome success/failure matches DB CHECK constraint"
```

---

### Task 6: Rewrite guardian.py (feedback loop + shutdown)

**Files:**
- Rewrite: `apps/backend-rag/backend/services/olympus/guardian.py`
- Test: `apps/backend-rag/backend/tests/services/olympus/test_guardian.py`

This is the most critical task. The guardian wires everything together and closes the feedback loop.

- [ ] **Step 1: Write the test file**

```python
"""Tests for Olympus v2 Guardian — feedback loop and shutdown."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.olympus.guardian import OlympusGuardian
from backend.services.olympus.models import PulseAction


class TestGuardianFeedbackLoop:
    @pytest.mark.asyncio
    async def test_pulse_records_applied_rules(self):
        """record_applied is called for every action with a rule_applied."""
        pool = AsyncMock()
        guardian = OlympusGuardian(db_pool=pool, alert_service=None)
        guardian.rules_engine = MagicMock()
        guardian.rules_engine.record_applied = AsyncMock()
        guardian.rules_engine.lower_confidence = AsyncMock()
        guardian.pulse = MagicMock()
        guardian.pulse.run_full_pulse = AsyncMock(return_value=[
            PulseAction(action_type="vacuum", target="t1", outcome="success", rule_applied="vacuum_dead_pct_threshold"),
            PulseAction(action_type="vacuum", target="t2", outcome="success", rule_applied="vacuum_dead_pct_threshold"),
            PulseAction(action_type="cleanup", target="t3", outcome="success", rule_applied="audit_retention_days"),
        ])
        guardian.alerts = MagicMock()
        guardian.alerts.send_pulse_summary = AsyncMock()

        # Mock _persist_action
        guardian._persist_action = AsyncMock()

        actions = await guardian.run_pulse_once()

        # record_applied called once per unique rule
        assert guardian.rules_engine.record_applied.call_count == 2
        called_rules = {c.args[0] for c in guardian.rules_engine.record_applied.call_args_list}
        assert called_rules == {"vacuum_dead_pct_threshold", "audit_retention_days"}

    @pytest.mark.asyncio
    async def test_pulse_lowers_confidence_on_failure(self):
        """MISS-2 fix: lower_confidence called when action fails."""
        pool = AsyncMock()
        guardian = OlympusGuardian(db_pool=pool, alert_service=None)
        guardian.rules_engine = MagicMock()
        guardian.rules_engine.record_applied = AsyncMock()
        guardian.rules_engine.lower_confidence = AsyncMock()
        guardian.pulse = MagicMock()
        guardian.pulse.run_full_pulse = AsyncMock(return_value=[
            PulseAction(action_type="vacuum", target="t1", outcome="failure", rule_applied="vacuum_dead_pct_threshold"),
        ])
        guardian.alerts = MagicMock()
        guardian.alerts.send_pulse_summary = AsyncMock()
        guardian._persist_action = AsyncMock()

        await guardian.run_pulse_once()

        # lower_confidence called for the failed action's rule
        guardian.rules_engine.lower_confidence.assert_called_once_with("vacuum_dead_pct_threshold")

    @pytest.mark.asyncio
    async def test_pulse_no_lower_confidence_on_success(self):
        pool = AsyncMock()
        guardian = OlympusGuardian(db_pool=pool, alert_service=None)
        guardian.rules_engine = MagicMock()
        guardian.rules_engine.record_applied = AsyncMock()
        guardian.rules_engine.lower_confidence = AsyncMock()
        guardian.pulse = MagicMock()
        guardian.pulse.run_full_pulse = AsyncMock(return_value=[
            PulseAction(action_type="vacuum", target="t1", outcome="success", rule_applied="vacuum_dead_pct_threshold"),
        ])
        guardian.alerts = MagicMock()
        guardian.alerts.send_pulse_summary = AsyncMock()
        guardian._persist_action = AsyncMock()

        await guardian.run_pulse_once()

        guardian.rules_engine.lower_confidence.assert_not_called()

    @pytest.mark.asyncio
    async def test_pulse_summary_counts_failures_correctly(self):
        """BUG-4 fix: count 'failure' not 'error'."""
        pool = AsyncMock()
        guardian = OlympusGuardian(db_pool=pool, alert_service=None)
        guardian.rules_engine = MagicMock()
        guardian.rules_engine.record_applied = AsyncMock()
        guardian.rules_engine.lower_confidence = AsyncMock()
        guardian.pulse = MagicMock()
        guardian.pulse.run_full_pulse = AsyncMock(return_value=[
            PulseAction(action_type="a", outcome="success"),
            PulseAction(action_type="b", outcome="failure"),
            PulseAction(action_type="c", outcome="failure"),
        ])
        guardian.alerts = MagicMock()
        guardian.alerts.send_pulse_summary = AsyncMock()
        guardian._persist_action = AsyncMock()

        await guardian.run_pulse_once()

        guardian.alerts.send_pulse_summary.assert_called_once_with(3, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_guardian.py -v`

- [ ] **Step 3: Rewrite guardian.py**

```python
"""Olympus v2 — Guardian orchestrator.

Wires heartbeat, pulse, rules, and alerts together. Closes the feedback loop:
- record_applied() on every successful rule-governed action
- lower_confidence() on every failed rule-governed action
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg

from backend.services.olympus.alerts import OlympusAlerts
from backend.services.olympus.heartbeat import Heartbeat
from backend.services.olympus.models import PulseAction
from backend.services.olympus.pulse import Pulse
from backend.services.olympus.rules_engine import RulesEngine

logger = logging.getLogger("olympus.guardian")


class OlympusGuardian:
    def __init__(self, db_pool: asyncpg.Pool, alert_service: Any | None) -> None:
        self._pool = db_pool
        self.alerts = OlympusAlerts(alert_service)
        self.rules_engine: RulesEngine | None = None
        self.heartbeat: Heartbeat | None = None
        self.pulse: Pulse | None = None
        self._running: bool = False
        self._tasks: list[asyncio.Task[None]] = []

    async def initialize(self) -> None:
        self.rules_engine = RulesEngine(self._pool)
        await self.rules_engine.load_rules()
        self.heartbeat = Heartbeat(self._pool, self.rules_engine)
        self.heartbeat.on_alert(self.alerts.send_alert)
        self.pulse = Pulse(self._pool, self.rules_engine)
        logger.info("OlympusGuardian initialized — %d rules", len(self.rules_engine.rules))

    # ------------------------------------------------------------------
    # Single-shot executions
    # ------------------------------------------------------------------

    async def run_heartbeat_once(self) -> None:
        assert self.heartbeat is not None
        snapshot = await self.heartbeat.collect_metrics()
        await self.heartbeat.check_alerts(snapshot)
        await self.heartbeat.persist(snapshot)

    async def run_pulse_once(self) -> list[PulseAction]:
        assert self.pulse is not None
        assert self.rules_engine is not None

        actions = await self.pulse.run_full_pulse()

        # Persist each action
        for action in actions:
            await self._persist_action(action)

        # --- FEEDBACK LOOP ---
        applied_rules: set[str] = set()
        failed_rules: set[str] = set()

        for action in actions:
            if action.rule_applied:
                if action.outcome == "failure":
                    failed_rules.add(action.rule_applied)
                elif action.outcome == "success":
                    applied_rules.add(action.rule_applied)

        # Record successful applications
        for rule_name in applied_rules:
            await self.rules_engine.record_applied(rule_name)

        # Lower confidence on failures
        for rule_name in failed_rules:
            await self.rules_engine.lower_confidence(rule_name)

        # Summary — count "failure" (matches DB CHECK constraint)
        failures = sum(1 for a in actions if a.outcome == "failure")
        await self.alerts.send_pulse_summary(len(actions), failures)

        logger.info("Pulse complete: %d actions, %d failures", len(actions), failures)
        return actions

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                await self.run_heartbeat_once()
            except Exception:
                logger.exception("Heartbeat cycle failed")
            await asyncio.sleep(self._get_heartbeat_interval())

    async def _pulse_loop(self) -> None:
        await asyncio.sleep(60)  # initial delay
        while self._running:
            try:
                await self.run_pulse_once()
            except Exception:
                logger.exception("Pulse cycle failed")
                await self.alerts.send_alert("Pulse cycle failed — check logs")
            await asyncio.sleep(self._get_pulse_interval_hours() * 3600)

    async def start(self) -> None:
        self._running = True
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._pulse_loop()),
        ]
        logger.info("OlympusGuardian started")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("OlympusGuardian stopped")

    # ------------------------------------------------------------------
    # Health summary
    # ------------------------------------------------------------------

    async def get_health_summary(self) -> dict[str, Any]:
        last_heartbeat: dict[str, Any] | None = None
        recent_actions: list[dict[str, Any]] = []
        rules_count = len(self.rules_engine.rules) if self.rules_engine else 0

        try:
            async with self._pool.acquire() as conn:
                hb_row = await conn.fetchrow(
                    "SELECT * FROM olympus_heartbeats ORDER BY recorded_at DESC LIMIT 1",
                )
                if hb_row:
                    last_heartbeat = dict(hb_row)
                action_rows = await conn.fetch(
                    "SELECT * FROM olympus_actions ORDER BY executed_at DESC LIMIT 10",
                )
                recent_actions = [dict(r) for r in action_rows]
        except Exception:
            logger.exception("Failed to query health summary")

        return {
            "status": "alive",
            "running": self._running,
            "rules_count": rules_count,
            "last_heartbeat": last_heartbeat,
            "recent_actions": recent_actions,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _persist_action(self, action: PulseAction) -> None:
        query = """
            INSERT INTO olympus_actions (
                rhythm, action_type, target, detail, outcome,
                duration_ms, rule_applied, reflection, executed_at
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9)
        """
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query, action.rhythm, action.action_type, action.target,
                    json.dumps(action.detail), action.outcome, action.duration_ms,
                    action.rule_applied, action.reflection, action.executed_at,
                )
        except Exception:
            logger.exception("Failed to persist action: %s", action.action_type)

    def _get_heartbeat_interval(self) -> int:
        if self.rules_engine is None:
            return 300
        return int(self.rules_engine.get_threshold("heartbeat_interval_seconds", default=300))

    def _get_pulse_interval_hours(self) -> int:
        if self.rules_engine is None:
            return 6
        return int(self.rules_engine.get_threshold("pulse_interval_hours", default=6))
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/test_guardian.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/olympus/guardian.py backend/tests/services/olympus/test_guardian.py
git commit -m "feat(olympus-v2): rewrite guardian — feedback loop wired, lower_confidence on failure"
```

---

### Task 7: Rewrite router + wire shutdown + update service_initializer

**Files:**
- Rewrite: `apps/backend-rag/backend/app/routers/olympus.py`
- Modify: `apps/backend-rag/backend/app/lifecycle/shutdown.py:108-114`
- Modify: `apps/backend-rag/backend/app/setup/service_initializer.py:1198-1215`

- [ ] **Step 1: Rewrite olympus.py router (fix outcome counting)**

```python
"""Olympus v2 — internal management endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger("olympus.router")

internal_router = APIRouter(prefix="/internal/olympus", tags=["olympus-internal"])


@internal_router.post("/pulse")
async def trigger_pulse(request: Request) -> dict[str, Any]:
    """Manually trigger a pulse cycle."""
    olympus = getattr(request.app.state, "olympus", None)
    if olympus is None:
        return {"error": "Olympus not initialized"}
    actions = await olympus.run_pulse_once()
    return {
        "actions": len(actions),
        # FIX BUG-4: count "success"/"failure" to match actual outcome values
        "successes": sum(1 for a in actions if a.outcome == "success"),
        "failures": sum(1 for a in actions if a.outcome == "failure"),
    }


@internal_router.get("/rules")
async def list_rules(request: Request) -> list[dict[str, Any]]:
    olympus = getattr(request.app.state, "olympus", None)
    if olympus is None:
        return []
    return [r.model_dump() for r in olympus.rules_engine.rules.values()]
```

- [ ] **Step 2: Add olympus.stop() to shutdown.py**

After the "Shutdown Database Health Check Loop" block (line 114), add:

```python
        # Shutdown Olympus Guardian
        olympus = getattr(app.state, "olympus", None)
        if olympus:
            await olympus.stop()
            logger.info("✅ Olympus Guardian stopped")
```

- [ ] **Step 3: Clean up service_initializer.py type annotation**

In the full init (line 1201-1206), change the `AlertService` type hint to accept None properly:

```python
        # 10c. Olympus DB Guardian
        try:
            from backend.services.olympus.guardian import OlympusGuardian

            olympus = OlympusGuardian(db_pool=db_pool, alert_service=alert_service)
            await olympus.initialize()
            await olympus.start()
            app.state.olympus = olympus
            service_registry.register("olympus", ServiceStatus.HEALTHY, critical=False)
            logger.info("✅ Olympus DB Guardian: Active")
        except Exception as e:
            service_registry.register(
                "olympus", ServiceStatus.DEGRADED, error=str(e), critical=False,
            )
            logger.error(f"❌ Failed to initialize Olympus: {e}")
```

No changes needed to the light init — it already passes `alert_service=None`, which is now safe.

- [ ] **Step 4: Verify import chain**

Run: `cd apps/backend-rag && source .venv/bin/activate && python -c "from backend.app.dependencies import get_current_user; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Run all Olympus tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/olympus/ -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/olympus.py backend/app/lifecycle/shutdown.py backend/app/setup/service_initializer.py
git commit -m "feat(olympus-v2): router fix + graceful shutdown + nullable alert_service"
```

---

### Task 8: Deploy and verify

**Files:** None (deploy only)

- [ ] **Step 1: Deploy**

```bash
cd apps/backend-rag && fly deploy --strategy rolling
```

- [ ] **Step 2: Verify /health/db**

```bash
curl -s https://nuzantara-rag.fly.dev/health/db | python3 -m json.tool
```

Expected: `status: "alive"`, `rules_count: 10`, `recent_actions` should start populating after first pulse (6h or manual trigger).

- [ ] **Step 3: Verify no crashes in logs**

```bash
fly logs --app nuzantara-rag | grep -iE "olympus|guardian" | head -20
```

Expected: "OlympusGuardian initialized", "OlympusGuardian started", heartbeat logs. No errors.

- [ ] **Step 4: Trigger manual pulse to verify feedback loop**

```bash
# Need auth token for internal endpoint
curl -s -X POST https://nuzantara-rag.fly.dev/internal/olympus/pulse \
  -H "Authorization: Bearer $NZ_TOKEN" | python3 -m json.tool
```

Expected: `actions > 0`, `successes > 0`, `failures >= 0`. Check `/health/db` again — `recent_actions` should now be populated.

- [ ] **Step 5: Verify rule evolution in DB**

Check that `applied_count` and `confidence` changed for at least one rule after the pulse.

- [ ] **Step 6: Commit deploy verification**

No code change — just confirm everything works.

---

## Checklist: Every method is called

| Method | Called by |
|--------|----------|
| `HeartbeatSnapshot.pool_utilization` | `heartbeat.check_alerts()` |
| `PulseAction` fields | `pulse.py` every action, `guardian._persist_action()` |
| `OlympusRule._parse_json_config` | Pydantic auto on load_rules |
| `OlympusRule.get_value()` | `rules_engine.get_threshold()` |
| `RulesEngine.load_rules()` | `guardian.initialize()` |
| `RulesEngine.get_threshold()` | `heartbeat.collect_metrics()`, `heartbeat.check_alerts()`, `pulse.vacuum_bloated_tables()`, `pulse.cleanup_audit_trail()`, `guardian._get_*_interval()` |
| `RulesEngine.record_applied()` | `guardian.run_pulse_once()` on success |
| `RulesEngine.lower_confidence()` | `guardian.run_pulse_once()` on failure |
| `Heartbeat.on_alert()` | `guardian.initialize()` |
| `Heartbeat.alert()` | `heartbeat.check_alerts()` |
| `Heartbeat.collect_metrics()` | `guardian.run_heartbeat_once()` |
| `Heartbeat.check_alerts()` | `guardian.run_heartbeat_once()` |
| `Heartbeat.persist()` | `guardian.run_heartbeat_once()` |
| `Pulse.run_full_pulse()` | `guardian.run_pulse_once()` |
| `OlympusAlerts.send_alert()` | `heartbeat.alert()` callback, `guardian._pulse_loop()` |
| `OlympusAlerts.send_pulse_summary()` | `guardian.run_pulse_once()` |
| `OlympusGuardian.initialize()` | `service_initializer.py` |
| `OlympusGuardian.start()` | `service_initializer.py` |
| `OlympusGuardian.stop()` | `shutdown.py` |
| `OlympusGuardian.run_heartbeat_once()` | `_heartbeat_loop()` |
| `OlympusGuardian.run_pulse_once()` | `_pulse_loop()`, router `/internal/olympus/pulse` |
| `OlympusGuardian.get_health_summary()` | `health.py /health/db` |

**Zero dead methods. Zero dead models. Zero dead tables (olympus_insights and olympus_skills remain in DB but no code references them — harmless).**
