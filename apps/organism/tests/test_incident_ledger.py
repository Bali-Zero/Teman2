"""Tests for W37 incident_ledger module + dispatch/actuator integration.

The asyncpg pool is mocked with a FakePool that captures all execute()
calls; tests assert on the captured argv. Real Postgres is never touched.
The autouse `_forbid_real_subprocess` from conftest covers the actuator
subprocess axis; here we focus on the SQL trail.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from organism.supervisor import incident_ledger


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakePool:
    """Captures execute() calls and (optionally) raises on demand."""

    def __init__(self, raise_on_execute: bool = False):
        self.calls: list[tuple[str, tuple]] = []
        self.raise_on_execute = raise_on_execute
        self._closed = False

    async def execute(self, sql: str, *args):
        if self.raise_on_execute:
            raise RuntimeError("simulated pg outage")
        self.calls.append((sql, args))
        return "INSERT 0 1"

    def close(self):  # sync close — matches asyncpg.Pool.close behavior
        self._closed = True


@pytest.fixture(autouse=True)
async def _reset_ledger():
    """Ensure each test starts with a clean ledger module state."""
    await incident_ledger.reset_for_tests()
    yield
    await incident_ledger.reset_for_tests()


# ---------------------------------------------------------------------------
# 1. Migration applies clean (and the rollback DDL is well-formed)
# ---------------------------------------------------------------------------

def test_migration_file_exists_and_well_formed():
    """The migration file lives at the right path and contains the table.

    The migration runner globs migrations_v2/*.sql; this asserts the
    minimum contract — file present, CREATE TABLE, expected indexes,
    rollback note. Real apply/rollback runs in CI on a fresh PG via the
    backend test suite (out of scope for the organism test runner).
    """
    # parents: [0]=tests, [1]=apps/organism, [2]=apps, [3]=repo root.
    apps_dir = Path(__file__).resolve().parents[2]
    mig = apps_dir / "backend-rag" / "backend" / "db" / "migrations_v2" / "195_organism_incident_ledger.sql"
    assert mig.exists(), f"missing migration at {mig}"
    sql = mig.read_text(encoding="utf-8")
    # Schema additions
    assert "CREATE TABLE IF NOT EXISTS incident_ledger" in sql
    assert "incident_id     UUID NOT NULL DEFAULT gen_random_uuid()" in sql
    assert "correlation_id  TEXT NOT NULL" in sql
    assert "cell_id         TEXT NOT NULL" in sql
    assert "machine_id      TEXT," in sql  # nullable
    assert "completed_at    TIMESTAMPTZ," in sql  # nullable
    # Required indexes
    assert "idx_incident_ledger_app_started" in sql
    assert "idx_incident_ledger_correlation" in sql
    # Outcome check constraint enforces enum
    assert "incident_ledger_outcome_chk" in sql
    for v in ("dispatched", "deferred_cb", "done", "failed"):
        assert f"'{v}'" in sql, f"outcome enum missing {v}"
    # Rollback documented (in companion docs per W37 spec)
    assert "Rollback procedure documented" in sql


# ---------------------------------------------------------------------------
# 2. record_dispatch INSERTs a row with correct columns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_dispatch_inserts_row_for_fly_actuator():
    pool = FakePool()
    incident_ledger.set_pool_for_tests(pool)
    await incident_ledger.record_dispatch(
        correlation_id="corr-abc",
        actuator="fly_machines_restart",
        outcome="dispatched",
        params={
            "app": "nuzantara-rag",
            "machine": "7847d95ce257d8",
            "cell_id": "cell-pro",
            "consecutive_red": 5,
        },
    )
    assert len(pool.calls) == 1
    sql, args = pool.calls[0]
    assert "INSERT INTO incident_ledger" in sql
    assert "correlation_id, cell_id, app, machine_id" in sql
    # args order: correlation_id, cell_id, app, machine_id, actuator,
    #             outcome, consecutive_red
    assert args == (
        "corr-abc",
        "cell-pro",
        "nuzantara-rag",
        "7847d95ce257d8",
        "fly_machines_restart",
        "dispatched",
        5,
    )


@pytest.mark.asyncio
async def test_record_dispatch_defaults_when_params_missing():
    """Non-fly actuator with empty params still records a row."""
    pool = FakePool()
    incident_ledger.set_pool_for_tests(pool)
    await incident_ledger.record_dispatch(
        correlation_id="corr-xyz",
        actuator="restart_agent",
        outcome="dispatched",
        params={},
    )
    assert len(pool.calls) == 1
    _, args = pool.calls[0]
    # cell_id default = "unknown", app default = "organism",
    # machine_id None, consecutive_red None
    assert args == (
        "corr-xyz",
        "unknown",
        "organism",
        None,
        "restart_agent",
        "dispatched",
        None,
    )


@pytest.mark.asyncio
async def test_record_dispatch_swallows_pool_errors():
    """A simulated PG outage MUST NOT propagate to the supervisor."""
    pool = FakePool(raise_on_execute=True)
    incident_ledger.set_pool_for_tests(pool)
    # Must not raise.
    await incident_ledger.record_dispatch(
        correlation_id="corr-err",
        actuator="fly_machines_restart",
        outcome="dispatched",
        params={"app": "nuzantara-rag"},
    )


@pytest.mark.asyncio
async def test_record_dispatch_noop_when_no_pool():
    """Disabled ledger (no DSN, no pool) is a silent no-op."""
    incident_ledger.set_pool_for_tests(None)
    # No exception, no side-effect. Just returns.
    await incident_ledger.record_dispatch(
        correlation_id="corr-disabled",
        actuator="fly_machines_restart",
        outcome="dispatched",
        params={"app": "nuzantara-rag"},
    )


# ---------------------------------------------------------------------------
# 3. record_outcome UPDATEs the matching row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_outcome_done_updates_row():
    pool = FakePool()
    incident_ledger.set_pool_for_tests(pool)
    await incident_ledger.record_outcome(
        correlation_id="corr-done",
        actuator="fly_machines_restart",
        outcome="done",
    )
    assert len(pool.calls) == 1
    sql, args = pool.calls[0]
    assert "UPDATE incident_ledger" in sql
    assert "completed_at = now()" in sql
    # args = (outcome, error, correlation_id, actuator)
    assert args == ("done", None, "corr-done", "fly_machines_restart")


@pytest.mark.asyncio
async def test_record_outcome_failed_with_error():
    pool = FakePool()
    incident_ledger.set_pool_for_tests(pool)
    await incident_ledger.record_outcome(
        correlation_id="corr-fail",
        actuator="fly_machines_restart",
        outcome="failed",
        error="fly CLI returned exit=42",
    )
    assert len(pool.calls) == 1
    _, args = pool.calls[0]
    assert args == (
        "failed", "fly CLI returned exit=42",
        "corr-fail", "fly_machines_restart",
    )


@pytest.mark.asyncio
async def test_record_outcome_unexpected_value_coerced_to_failed():
    pool = FakePool()
    incident_ledger.set_pool_for_tests(pool)
    await incident_ledger.record_outcome(
        correlation_id="corr-bad",
        actuator="restart_agent",
        outcome="weird-state-name",
    )
    assert len(pool.calls) == 1
    _, args = pool.calls[0]
    assert args[0] == "failed"


# ---------------------------------------------------------------------------
# 4. Dispatcher integration — DISPATCHED triggers record_dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatcher_records_ledger_on_dispatched(fake_redis, tmp_path):
    """Dispatcher in active mode calls incident_ledger.record_dispatch."""
    from organism.blackout import BlackoutManager
    from organism.schemas import ActionDecision
    from organism.supervisor.circuit_breaker import CircuitBreaker
    from organism.supervisor.dispatch import Dispatcher, DispatchOutcome
    from organism.supervisor.mutex import Mutex

    class _StubActuator:
        name = "fly_machines_restart"

        async def run(self, *, params, correlation_id, dry_run=False):
            return {"success": True}

    pool = FakePool()
    incident_ledger.set_pool_for_tests(pool)

    dispatcher = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=False,
        actuator_registry={"fly_machines_restart": _StubActuator()},
    )
    decision = ActionDecision(
        actuator="fly_machines_restart",
        params={"app": "nuzantara-rag", "machine": "7847d95ce257d8"},
        confidence=0.95,
        tier="L0_yaml",
    )
    outcome = await dispatcher.dispatch(
        decision=decision,
        target="nuzantara-rag",
        correlation_id="corr-integ",
    )
    assert outcome == DispatchOutcome.DISPATCHED
    # Ledger INSERT was triggered.
    assert len(pool.calls) == 1
    sql, args = pool.calls[0]
    assert "INSERT INTO incident_ledger" in sql
    assert args[0] == "corr-integ"
    assert args[2] == "nuzantara-rag"
    assert args[3] == "7847d95ce257d8"
    assert args[4] == "fly_machines_restart"
    assert args[5] == "dispatched"
