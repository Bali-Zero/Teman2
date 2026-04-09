"""Tests for cell_core.memory_sqlite — SQLite-backed memory stores."""
import asyncio
import time

import pytest

from cell_core.types import Episode, LearnedRule


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_cell.db")


class TestSqliteSTM:
    @pytest.mark.asyncio
    async def test_store_and_recent(self, db_path):
        from cell_core.memory_sqlite import SqliteSTM
        stm = SqliteSTM(db_path, ttl_seconds=3600)
        await stm.store("health", {"status": "green", "rt": 100})
        await stm.store("health", {"status": "yellow", "rt": 200})
        results = await stm.recent("health", limit=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_recent_respects_limit(self, db_path):
        from cell_core.memory_sqlite import SqliteSTM
        stm = SqliteSTM(db_path)
        for i in range(10):
            await stm.store("sensor", {"i": i})
        results = await stm.recent("sensor", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_recent_filters_by_event_type(self, db_path):
        from cell_core.memory_sqlite import SqliteSTM
        stm = SqliteSTM(db_path)
        await stm.store("health", {"v": 1})
        await stm.store("db", {"v": 2})
        results = await stm.recent("health", limit=10)
        assert len(results) == 1
        assert results[0]["v"] == 1

    @pytest.mark.asyncio
    async def test_recent_empty_type_returns_all(self, db_path):
        from cell_core.memory_sqlite import SqliteSTM
        stm = SqliteSTM(db_path)
        await stm.store("a", {"v": 1})
        await stm.store("b", {"v": 2})
        results = await stm.recent("", limit=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_ttl_cleanup(self, db_path):
        from cell_core.memory_sqlite import SqliteSTM
        stm = SqliteSTM(db_path, ttl_seconds=1)
        await stm.store("x", {"v": 1})
        await asyncio.sleep(1.1)
        await stm.store("x", {"v": 2})  # triggers cleanup
        results = await stm.recent("x", limit=10)
        assert len(results) == 1
        assert results[0]["v"] == 2


class TestSqliteEpisodic:
    @pytest.mark.asyncio
    async def test_store_and_recall(self, db_path):
        from cell_core.memory_sqlite import SqliteEpisodic
        ep = SqliteEpisodic(db_path)
        episode = Episode(
            situation={"status": "red"}, emotion="stressed",
            action_taken="restart", outcome="success", lesson="restart works",
            timestamp=time.time(),
        )
        eid = await ep.store(episode)
        assert eid > 0
        results = await ep.recall_recent(hours=1, limit=10)
        assert len(results) == 1
        assert results[0].action_taken == "restart"

    @pytest.mark.asyncio
    async def test_recall_orders_by_activation(self, db_path):
        from cell_core.memory_sqlite import SqliteEpisodic
        ep = SqliteEpisodic(db_path)
        # Old episode
        old = Episode(
            situation={}, emotion="calm", action_taken="none",
            outcome="success", lesson="ok",
            timestamp=time.time() - 86400 * 5,
        )
        # Recent episode
        recent = Episode(
            situation={}, emotion="alert", action_taken="scale",
            outcome="success", lesson="scale helps",
            timestamp=time.time(),
        )
        await ep.store(old)
        await ep.store(recent)
        results = await ep.recall({}, limit=2)
        assert results[0].action_taken == "scale"  # more recent = higher activation

    @pytest.mark.asyncio
    async def test_forget_weak(self, db_path):
        from cell_core.memory_sqlite import SqliteEpisodic
        ep = SqliteEpisodic(db_path)
        for i in range(10):
            e = Episode(
                situation={"i": i}, emotion="calm", action_taken="none",
                outcome="success", lesson=f"lesson {i}",
                timestamp=time.time() - (10 - i) * 3600,
            )
            await ep.store(e)
        removed = await ep.forget_weak(keep=5)
        assert removed == 5
        remaining = await ep.recall_recent(hours=24, limit=100)
        assert len(remaining) == 5

    @pytest.mark.asyncio
    async def test_recall_increments_recall_count(self, db_path):
        from cell_core.memory_sqlite import SqliteEpisodic
        ep = SqliteEpisodic(db_path)
        episode = Episode(
            situation={}, emotion="calm", action_taken="none",
            outcome="success", lesson="ok", timestamp=time.time(),
        )
        eid = await ep.store(episode)
        await ep.recall({}, limit=1)
        await ep.recall({}, limit=1)
        results = await ep.recall_recent(hours=1, limit=1)
        assert results[0].recall_count == 2


class TestSqliteLTM:
    @pytest.mark.asyncio
    async def test_store_and_load(self, db_path):
        from cell_core.memory_sqlite import SqliteLTM
        ltm = SqliteLTM(db_path)
        rule = LearnedRule(rule_text="When latency > 500ms, restart", support_count=3)
        await ltm.store_rule(rule)
        rules = await ltm.load_rules(limit=10)
        assert len(rules) == 1
        assert rules[0].rule_text == "When latency > 500ms, restart"

    @pytest.mark.asyncio
    async def test_load_respects_limit(self, db_path):
        from cell_core.memory_sqlite import SqliteLTM
        ltm = SqliteLTM(db_path)
        for i in range(10):
            await ltm.store_rule(LearnedRule(rule_text=f"Rule {i}", support_count=1))
        rules = await ltm.load_rules(limit=3)
        assert len(rules) == 3

    @pytest.mark.asyncio
    async def test_condense_extracts_patterns(self, db_path):
        from cell_core.memory_sqlite import SqliteLTM
        ltm = SqliteLTM(db_path)
        episodes = [
            Episode(
                situation={"status": "red"}, emotion="stressed",
                action_taken="restart", outcome="success", lesson="restart works",
                timestamp=time.time(),
            )
            for _ in range(5)
        ]
        rules = await ltm.condense(episodes)
        assert len(rules) >= 1
        assert any("restart" in r.rule_text.lower() for r in rules)


class TestSqliteMemoryStack:
    @pytest.mark.asyncio
    async def test_creates_all_three_stores(self, db_path):
        from cell_core.memory_sqlite import SqliteMemoryStack
        from cell_core.protocols import STMStore, LTMStore, EpisodicStore
        stack = SqliteMemoryStack(db_path)
        assert isinstance(stack.stm, STMStore)
        assert isinstance(stack.ltm, LTMStore)
        assert isinstance(stack.episodic, EpisodicStore)

    @pytest.mark.asyncio
    async def test_shared_db_file(self, db_path):
        from cell_core.memory_sqlite import SqliteMemoryStack
        stack = SqliteMemoryStack(db_path)
        await stack.stm.store("test", {"v": 1})
        episode = Episode(
            situation={}, emotion="calm", action_taken="none",
            outcome="success", lesson="ok", timestamp=time.time(),
        )
        await stack.episodic.store(episode)
        await stack.ltm.store_rule(LearnedRule(rule_text="rule", support_count=1))
        # All use same DB file — just verify no errors
