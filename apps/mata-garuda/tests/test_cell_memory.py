"""Tests for mata_garuda.cell.memory_bridge — adapts KnowledgeBase as cell-core memory."""
import time
import pytest
from pathlib import Path

from cell_core.types import Episode, LearnedRule
from cell_core.protocols import LTMStore, EpisodicStore, STMStore


@pytest.fixture
def kb(tmp_path):
    from mata_garuda.runtime.knowledge import KnowledgeBase
    return KnowledgeBase(db_path=tmp_path / "test_kb.db")


class TestKnowledgeBridgeLTM:
    def test_implements_ltm_protocol(self, kb):
        from mata_garuda.cell.memory_bridge import KnowledgeBridgeLTM
        ltm = KnowledgeBridgeLTM(kb)
        assert isinstance(ltm, LTMStore)

    @pytest.mark.asyncio
    async def test_store_and_load_rules(self, kb):
        from mata_garuda.cell.memory_bridge import KnowledgeBridgeLTM
        ltm = KnowledgeBridgeLTM(kb)
        rule = LearnedRule(rule_text="Always check HTTP 200 before scraping", support_count=3)
        await ltm.store_rule(rule)
        rules = await ltm.load_rules(limit=10)
        assert len(rules) >= 1
        assert "HTTP 200" in rules[0].rule_text

    @pytest.mark.asyncio
    async def test_condense_extracts_patterns(self, kb):
        from mata_garuda.cell.memory_bridge import KnowledgeBridgeLTM
        ltm = KnowledgeBridgeLTM(kb)
        episodes = [
            Episode(situation={}, emotion="calm", action_taken="scrape",
                    outcome="success", lesson="curl first", timestamp=time.time())
            for _ in range(5)
        ]
        rules = await ltm.condense(episodes)
        assert len(rules) >= 1


class TestReflectionEpisodicStore:
    def test_implements_episodic_protocol(self, kb):
        from mata_garuda.cell.memory_bridge import ReflectionEpisodicStore
        ep = ReflectionEpisodicStore(kb)
        assert isinstance(ep, EpisodicStore)

    @pytest.mark.asyncio
    async def test_store_episode(self, kb):
        from mata_garuda.cell.memory_bridge import ReflectionEpisodicStore
        ep = ReflectionEpisodicStore(kb)
        episode = Episode(
            situation={"status": "red"}, emotion="stressed",
            action_taken="restart", outcome="success", lesson="restart works",
            timestamp=time.time(),
        )
        eid = await ep.store(episode)
        assert eid > 0

    @pytest.mark.asyncio
    async def test_recall_recent(self, kb):
        from mata_garuda.cell.memory_bridge import ReflectionEpisodicStore
        ep = ReflectionEpisodicStore(kb)
        for i in range(3):
            await ep.store(Episode(
                situation={"i": i}, emotion="calm", action_taken="scrape",
                outcome="success", lesson=f"lesson {i}", timestamp=time.time(),
            ))
        results = await ep.recall_recent(hours=1, limit=10)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_forget_weak(self, kb):
        from mata_garuda.cell.memory_bridge import ReflectionEpisodicStore
        ep = ReflectionEpisodicStore(kb)
        for i in range(10):
            await ep.store(Episode(
                situation={}, emotion="calm", action_taken="x",
                outcome="success", lesson=f"l{i}",
                timestamp=time.time() - (10 - i) * 3600,
            ))
        removed = await ep.forget_weak(keep=5)
        assert removed == 5


class TestBridgeSTM:
    def test_implements_stm_protocol(self, kb):
        from mata_garuda.cell.memory_bridge import BridgeSTM
        stm = BridgeSTM()
        assert isinstance(stm, STMStore)

    @pytest.mark.asyncio
    async def test_store_and_recent(self):
        from mata_garuda.cell.memory_bridge import BridgeSTM
        stm = BridgeSTM()
        await stm.store("health", {"status": "green"})
        results = await stm.recent("health", limit=5)
        assert len(results) == 1
