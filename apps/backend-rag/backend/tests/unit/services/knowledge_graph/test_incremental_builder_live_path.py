"""
Live-path starter tests for the KG incremental builder (§10f).

Necropsy follow-up 2026-07-14: the builder was doubly unarmed — registered on
the dead AutonomousScheduler AND gated by an ENABLE_KG_INCREMENTAL env never
set on Fly. The live path is the loop; these tests pin its contract the same
way TestLiveLoopStarter does for the WhatsApp guardian (§10d).

SCAR 2026-07-19: the original loop acquired the Redis dedup lock with
TTL = interval_seconds (24h) BEFORE running, and that same TTL doubled as the
cadence signal. A run that crashed mid-flight left the 24h lock held with no
verdict persisted, so every subsequent boot's acquire returned False and the
run stayed poisoned for a full day. The fix decouples cadence (DB timestamp
read via `_get_last_kg_run_ts`) from dedup (short-TTL Redis lock, released in
a `finally` via `_release_task_lock`). These tests were rewritten to pin the
NEW contract: `_kg_incremental_tick` for the single-cycle logic and
`_kg_incremental_loop` for the check-interval polling shell around it.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.knowledge_graph.incremental_builder import (
    _get_last_kg_run_ts,
    _kg_incremental_loop,
    _kg_incremental_tick,
    _persist_kg_verdict,
    start_kg_incremental_task,
)


class TestStartKgIncrementalTask:
    @pytest.mark.asyncio
    async def test_starts_named_task(self):
        task = start_kg_incremental_task(MagicMock())
        assert task is not None
        assert task.get_name() == "kg_incremental_builder"
        task.cancel()

    @pytest.mark.asyncio
    async def test_default_is_armed(self, monkeypatch):
        """W81 guilt: an unset env must NOT mean off — that was the theater."""
        monkeypatch.delenv("ENABLE_KG_INCREMENTAL", raising=False)
        task = start_kg_incremental_task(MagicMock())
        assert task is not None
        task.cancel()

    @pytest.mark.asyncio
    async def test_kill_switch_returns_none(self, monkeypatch):
        monkeypatch.setenv("ENABLE_KG_INCREMENTAL", "false")
        assert start_kg_incremental_task(MagicMock()) is None

    @pytest.mark.asyncio
    async def test_no_db_pool_returns_none(self):
        assert start_kg_incremental_task(None) is None


class TestGetLastKgRunTs:
    @pytest.mark.asyncio
    async def test_returns_timestamp_when_verdict_exists(self):
        ts = datetime(2026, 7, 15, 3, 0, tzinfo=timezone.utc)
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"updated_at": ts})

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _get_last_kg_run_ts(pool)

        assert result == ts
        sql = conn.fetchrow.await_args.args[0]
        assert "kg_incremental_last" in sql
        assert "system_settings" in sql

    @pytest.mark.asyncio
    async def test_returns_none_when_never_ran(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        assert await _get_last_kg_run_ts(pool) is None

    @pytest.mark.asyncio
    async def test_fails_open_to_none_on_db_error(self):
        pool = MagicMock()
        pool.acquire.side_effect = RuntimeError("db unavailable")

        # Fail-open: a broken DB read must not crash the loop — treated as
        # "never ran" by the caller, same philosophy as _acquire_task_lock
        # falling open on Redis errors.
        assert await _get_last_kg_run_ts(pool) is None


class TestKgIncrementalTick:
    @pytest.mark.asyncio
    async def test_runs_when_never_ran_and_lock_available(self):
        runs: list[dict] = []
        verdicts: list[dict] = []

        async def fake_build(db_pool):
            stats = {"status": "ok", "total_chunks": 7}
            runs.append(stats)
            return stats

        async def fake_persist(db_pool, stats):
            verdicts.append(stats)

        with (
            patch(
                "backend.services.knowledge_graph.incremental_builder._get_last_kg_run_ts",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler._acquire_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_acquire,
            patch(
                "backend.services.misc.autonomous_scheduler._release_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_release,
            patch(
                "backend.services.knowledge_graph.incremental_builder."
                "run_knowledge_graph_incremental_build",
                side_effect=fake_build,
            ),
            patch(
                "backend.services.knowledge_graph.incremental_builder._persist_kg_verdict",
                side_effect=fake_persist,
            ),
        ):
            await _kg_incremental_tick(MagicMock(), 86400, 14400)

        assert len(runs) == 1
        assert verdicts == runs
        mock_acquire.assert_awaited_once_with("kg_incremental_builder", 14400)
        mock_release.assert_awaited_once_with("kg_incremental_builder")

    @pytest.mark.asyncio
    async def test_skips_when_not_due(self):
        """Cadence honors the DB timestamp: <24h since last success -> skip."""
        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        build = AsyncMock()

        with (
            patch(
                "backend.services.knowledge_graph.incremental_builder._get_last_kg_run_ts",
                new_callable=AsyncMock,
                return_value=recent,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler._acquire_task_lock",
                new_callable=AsyncMock,
            ) as mock_acquire,
            patch(
                "backend.services.knowledge_graph.incremental_builder."
                "run_knowledge_graph_incremental_build",
                build,
            ),
        ):
            await _kg_incremental_tick(MagicMock(), 86400, 14400)

        build.assert_not_awaited()
        mock_acquire.assert_not_awaited()  # not-due short-circuits before the lock

    @pytest.mark.asyncio
    async def test_runs_when_due_after_full_cadence(self):
        """>=24h since last success -> due, run proceeds."""
        stale = datetime.now(timezone.utc) - timedelta(hours=25)
        build = AsyncMock(return_value={"status": "ok"})

        with (
            patch(
                "backend.services.knowledge_graph.incremental_builder._get_last_kg_run_ts",
                new_callable=AsyncMock,
                return_value=stale,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler._acquire_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler._release_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.knowledge_graph.incremental_builder."
                "run_knowledge_graph_incremental_build",
                build,
            ),
            patch(
                "backend.services.knowledge_graph.incremental_builder._persist_kg_verdict",
                new_callable=AsyncMock,
            ),
        ):
            await _kg_incremental_tick(MagicMock(), 86400, 14400)

        build.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_run_when_lock_not_held(self):
        build = AsyncMock()

        with (
            patch(
                "backend.services.knowledge_graph.incremental_builder._get_last_kg_run_ts",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler._acquire_task_lock",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler._release_task_lock",
                new_callable=AsyncMock,
            ) as mock_release,
            patch(
                "backend.services.knowledge_graph.incremental_builder."
                "run_knowledge_graph_incremental_build",
                build,
            ),
        ):
            await _kg_incremental_tick(MagicMock(), 86400, 14400)

        build.assert_not_awaited()
        mock_release.assert_not_awaited()  # never acquired -> nothing to release

    @pytest.mark.asyncio
    async def test_lock_released_even_when_run_raises(self):
        """A crashed run must not poison the lock for its full TTL (SCAR 2026-07-19)."""
        build = AsyncMock(side_effect=RuntimeError("boom"))

        with (
            patch(
                "backend.services.knowledge_graph.incremental_builder._get_last_kg_run_ts",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler._acquire_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler._release_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_release,
            patch(
                "backend.services.knowledge_graph.incremental_builder."
                "run_knowledge_graph_incremental_build",
                build,
            ),
            pytest.raises(RuntimeError, match="boom"),
        ):
            await _kg_incremental_tick(MagicMock(), 86400, 14400)

        mock_release.assert_awaited_once_with("kg_incremental_builder")

    @pytest.mark.asyncio
    async def test_lock_released_even_when_persist_raises(self):
        """Verdict-persist failure (already caught internally) must still release."""
        build = AsyncMock(return_value={"status": "ok"})
        persist = AsyncMock(side_effect=RuntimeError("db write failed"))

        with (
            patch(
                "backend.services.knowledge_graph.incremental_builder._get_last_kg_run_ts",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler._acquire_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler._release_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_release,
            patch(
                "backend.services.knowledge_graph.incremental_builder."
                "run_knowledge_graph_incremental_build",
                build,
            ),
            patch(
                "backend.services.knowledge_graph.incremental_builder._persist_kg_verdict",
                persist,
            ),
        ):
            await _kg_incremental_tick(MagicMock(), 86400, 14400)

        mock_release.assert_awaited_once_with("kg_incremental_builder")


class TestKgIncrementalLoop:
    @pytest.mark.asyncio
    async def test_loop_boots_then_ticks_on_check_interval(self, monkeypatch):
        monkeypatch.setenv("KG_CHECK_INTERVAL", "3600")
        monkeypatch.setenv("KG_LOCK_TTL", "14400")

        ticks: list[tuple] = []
        sleeps: list[float] = []

        async def fake_tick(db_pool, interval_seconds, lock_ttl_seconds):
            ticks.append((interval_seconds, lock_ttl_seconds))

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) >= 3:  # boot sleep + 2 tick-interval sleeps
                raise StopAsyncIteration

        with (
            patch(
                "backend.services.knowledge_graph.incremental_builder._kg_incremental_tick",
                side_effect=fake_tick,
            ),
            patch("asyncio.sleep", side_effect=fake_sleep),
            pytest.raises(StopAsyncIteration),
        ):
            await _kg_incremental_loop(MagicMock(), 86400)

        assert sleeps[0] == 120  # boot delay preserved
        assert sleeps[1:] == [3600, 3600]  # KG_CHECK_INTERVAL, not the 24h cadence
        assert len(ticks) == 2
        assert all(t == (86400, 14400) for t in ticks)

    @pytest.mark.asyncio
    async def test_loop_survives_tick_exception(self):
        """The loop must never die — a per-tick exception is caught and logged."""
        sleeps: list[float] = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) >= 2:
                raise StopAsyncIteration

        with (
            patch(
                "backend.services.knowledge_graph.incremental_builder._kg_incremental_tick",
                new_callable=AsyncMock,
                side_effect=RuntimeError("tick blew up"),
            ),
            patch("asyncio.sleep", side_effect=fake_sleep),
            pytest.raises(StopAsyncIteration),
        ):
            await _kg_incremental_loop(MagicMock(), 86400, check_interval_seconds=60)

        # Loop kept going past the exception (reached the second sleep).
        assert len(sleeps) == 2

    @pytest.mark.asyncio
    async def test_loop_propagates_cancellation(self):
        async def fake_sleep(seconds):
            return None

        with (
            patch(
                "backend.services.knowledge_graph.incremental_builder._kg_incremental_tick",
                new_callable=AsyncMock,
                side_effect=asyncio.CancelledError(),
            ),
            patch("asyncio.sleep", side_effect=fake_sleep),
            pytest.raises(asyncio.CancelledError),
        ):
            await _kg_incremental_loop(MagicMock(), 86400, check_interval_seconds=60)


class TestPersistKgVerdict:
    @pytest.mark.asyncio
    async def test_upserts_system_settings_row(self):
        pool = MagicMock()
        pool.execute = AsyncMock()

        await _persist_kg_verdict(pool, {"status": "ok", "total_chunks": 3, "errors": []})

        sql = pool.execute.await_args.args[0]
        assert "kg_incremental_last" in sql
        assert "ON CONFLICT (key) DO UPDATE" in sql
