"""Tests for SQLite knowledge base — unified store for facts, insights, skills."""
import pytest


@pytest.fixture
def kb(tmp_path):
    from mata_garuda.runtime.knowledge import KnowledgeBase
    return KnowledgeBase(db_path=tmp_path / "test_kb.db")


class TestKnowledgeBase:
    def test_init_creates_tables(self, kb):
        assert kb.db_path.exists()
        rows = kb.search("nonexistent")
        assert rows == []

    def test_store_and_retrieve(self, kb):
        kb.store(
            agent="Regulation Watcher",
            entry_type="fact",
            content="Perpres 31/2025 changes investment rules for PMA",
            source="peraturan.go.id",
            confidence=0.9,
        )
        results = kb.search("investment PMA")
        assert len(results) == 1
        assert "Perpres 31/2025" in results[0]["content"]
        assert results[0]["agent"] == "Regulation Watcher"

    def test_store_multiple_and_fts(self, kb):
        kb.store("agent1", "fact", "Tax regulation PMK 25/2025", "source1", 0.8)
        kb.store("agent1", "fact", "Immigration visa B211 abolished", "source2", 0.9)
        kb.store("agent1", "fact", "Tax PMK 30/2025 new brackets", "source1", 0.7)

        results = kb.search("tax PMK")
        assert len(results) == 2

    def test_store_increments_accessed_count(self, kb):
        kb.store("agent1", "fact", "Test content", "source", 0.5)
        results = kb.search("Test content")
        assert results[0]["accessed_count"] == 0

        kb.touch(results[0]["id"])
        results2 = kb.search("Test content")
        assert results2[0]["accessed_count"] == 1

    def test_decay_removes_stale(self, kb):
        kb.store("agent1", "fact", "Old unused fact", "source", 0.3)
        kb._execute(
            "UPDATE knowledge SET created_at = datetime('now', '-60 days') WHERE id = 1"
        )
        removed = kb.decay(max_age_days=30, min_access=1)
        assert removed == 1
        assert kb.search("Old unused fact") == []

    def test_stats(self, kb):
        kb.store("a", "fact", "f1", "s", 0.5)
        kb.store("a", "skill", "s1", "s", 0.8)
        kb.store("a", "fact", "f2", "s", 0.6)
        stats = kb.stats()
        assert stats["fact"] == 2
        assert stats["skill"] == 1
        assert stats["total"] == 3

    def test_skill_stored_and_retrieved_as_type(self, kb):
        kb.store("Regulation Watcher", "skill",
                 "Always check HTTP status before scraping: curl -sI $URL, verify 200",
                 "reflection_20260409", 0.9)
        skills = kb.get_by_type("skill")
        assert len(skills) == 1
        assert "check HTTP status" in skills[0]["content"]

    def test_decrement_confidence(self, kb):
        kb.store("agent1", "insight", "Source X is always down", "reflection", 0.8)
        results = kb.search("Source X")
        kb.decrement_confidence(results[0]["id"], amount=0.2)
        results2 = kb.search("Source X")
        assert results2[0]["confidence"] == pytest.approx(0.6, rel=0.01)

    def test_decrement_confidence_floors_at_zero(self, kb):
        kb.store("agent1", "fact", "Test floor", "src", 0.1)
        results = kb.search("Test floor")
        kb.decrement_confidence(results[0]["id"], amount=0.5)
        results2 = kb.search("Test floor")
        assert results2[0]["confidence"] >= 0.0

    def test_get_by_agent(self, kb):
        kb.store("agent_a", "fact", "Fact from A", "src", 0.5)
        kb.store("agent_b", "fact", "Fact from B", "src", 0.5)
        kb.store("agent_a", "insight", "Insight from A", "src", 0.7)
        results = kb.get_by_agent("agent_a")
        assert len(results) == 2
        assert all(r["agent"] == "agent_a" for r in results)
