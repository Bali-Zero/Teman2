"""
Live-path starter tests for the KG incremental builder (§10f).

Necropsy follow-up 2026-07-14: the builder was doubly unarmed — registered on
the dead AutonomousScheduler AND gated by an ENABLE_KG_INCREMENTAL env never
set on Fly. The live path is the loop; these tests pin its contract the same
way TestLiveLoopStarter does for the WhatsApp guardian (§10d).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.knowledge_graph.incremental_builder import (
    _kg_incremental_loop,
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


class TestKgIncrementalLoop:
    @pytest.mark.asyncio
    async def test_runs_build_and_persists_verdict_when_lock_held(self):
        runs: list[dict] = []
        verdicts: list[dict] = []

        async def fake_build(db_pool):
            stats = {"status": "ok", "total_chunks": 7}
            runs.append(stats)
            return stats

        async def fake_persist(db_pool, stats):
            verdicts.append(stats)

        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) >= 2:  # boot sleep + first interval sleep
                raise StopAsyncIteration

        with (
            patch(
                "backend.services.misc.autonomous_scheduler._acquire_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.knowledge_graph.incremental_builder."
                "run_knowledge_graph_incremental_build",
                side_effect=fake_build,
            ),
            patch(
                "backend.services.knowledge_graph.incremental_builder._persist_kg_verdict",
                side_effect=fake_persist,
            ),
            patch("asyncio.sleep", side_effect=fake_sleep),
            pytest.raises(StopAsyncIteration),
        ):
            await _kg_incremental_loop(MagicMock(), 86400)

        assert len(runs) == 1
        assert verdicts == runs

    @pytest.mark.asyncio
    async def test_skips_run_when_lock_not_held(self):
        build = AsyncMock()
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) >= 2:
                raise StopAsyncIteration

        with (
            patch(
                "backend.services.misc.autonomous_scheduler._acquire_task_lock",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "backend.services.knowledge_graph.incremental_builder."
                "run_knowledge_graph_incremental_build",
                build,
            ),
            patch("asyncio.sleep", side_effect=fake_sleep),
            pytest.raises(StopAsyncIteration),
        ):
            await _kg_incremental_loop(MagicMock(), 86400)

        build.assert_not_awaited()


class TestPersistKgVerdict:
    @pytest.mark.asyncio
    async def test_upserts_system_settings_row(self):
        pool = MagicMock()
        pool.execute = AsyncMock()

        await _persist_kg_verdict(pool, {"status": "ok", "total_chunks": 3, "errors": []})

        sql = pool.execute.await_args.args[0]
        assert "kg_incremental_last" in sql
        assert "ON CONFLICT (key) DO UPDATE" in sql
