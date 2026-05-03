"""
Test — Council Store (SQLite).

Tests persistence, retrieval, status updates, and stats.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mata_garuda.council.models import (
    AgentVote,
    ConsensusResult,
    CouncilDecision,
    Dissent,
    Topic,
)
from mata_garuda.council.store import CouncilStore


@pytest.fixture
def store():
    """Create a temporary store for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_council.db"
        s = CouncilStore(db_path=db_path)
        yield s
        s.close()


def _make_decision(
    decision_id: str = "test-001",
    topic_title: str = "Test topic",
    consensus_score: float = 0.70,
    status: str = "pending",
    groupthink: bool = False,
) -> CouncilDecision:
    return CouncilDecision(
        id=decision_id,
        topic=Topic(
            id="t-001",
            title=topic_title,
            description="Test description",
            category="operational",
        ),
        votes=[
            AgentVote(agent_name="claude", position="A", success=True, elapsed_seconds=30),
            AgentVote(agent_name="gemini", position="B", success=True, elapsed_seconds=25),
        ],
        consensus=ConsensusResult(
            score=consensus_score,
            method="jaccard",
            groupthink_detected=groupthink,
        ),
        dissents=[],
        synthesis="Test synthesis",
        action_items=["item1"],
        requires_zero_approval=False,
        status=status,
        decided_at="2026-04-16T10:00:00Z",
    )


class TestStoreBasics:
    """Test basic CRUD operations."""

    def test_save_and_retrieve(self, store):
        decision = _make_decision()
        store.save_decision(decision)

        retrieved = store.get_decision("test-001")
        assert retrieved is not None
        assert retrieved.id == "test-001"
        assert retrieved.topic.title == "Test topic"
        assert retrieved.synthesis == "Test synthesis"

    def test_get_nonexistent(self, store):
        assert store.get_decision("nonexistent") is None

    def test_list_decisions(self, store):
        store.save_decision(_make_decision("d1", "Topic 1"))
        store.save_decision(_make_decision("d2", "Topic 2"))

        results = store.list_decisions()
        assert len(results) == 2

    def test_list_filtered_by_status(self, store):
        store.save_decision(_make_decision("d1", status="pending"))
        store.save_decision(_make_decision("d2", status="auto_approved"))

        pending = store.list_decisions(status="pending")
        assert len(pending) == 1
        assert pending[0]["id"] == "d1"

    def test_list_groupthink_only(self, store):
        store.save_decision(_make_decision("d1", groupthink=False))
        store.save_decision(_make_decision("d2", groupthink=True))

        gt = store.list_decisions(groupthink_only=True)
        assert len(gt) == 1
        assert gt[0]["id"] == "d2"


class TestStoreStatusUpdate:
    """Test approval/rejection workflow."""

    def test_approve_decision(self, store):
        store.save_decision(_make_decision("d1", status="pending"))

        ok = store.update_status("d1", "approved", approved_by="zero")
        assert ok is True

        retrieved = store.get_decision("d1")
        assert retrieved.status == "approved"
        assert retrieved.approved_at != ""

    def test_reject_decision(self, store):
        store.save_decision(_make_decision("d1"))

        ok = store.update_status("d1", "rejected", approved_by="zero: reason")
        assert ok is True

    def test_update_nonexistent(self, store):
        ok = store.update_status("nope", "approved")
        assert ok is False


class TestStoreStats:
    """Test aggregate statistics."""

    def test_empty_stats(self, store):
        stats = store.stats()
        assert stats["total"] == 0

    def test_computed_stats(self, store):
        store.save_decision(_make_decision("d1", consensus_score=0.80, status="pending"))
        store.save_decision(_make_decision("d2", consensus_score=0.60, status="pending", groupthink=True))
        store.update_status("d1", "approved")

        stats = store.stats()
        assert stats["total"] == 2
        assert stats["approved"] == 1
        assert stats["pending"] == 1
        assert stats["groupthink_rate"] == 0.5
        assert 0.69 < stats["avg_consensus"] < 0.71


class TestStoreDecisionFields:
    """Test that all fields survive round-trip."""

    def test_dissents_preserved(self, store):
        decision = _make_decision()
        decision.dissents = [
            Dissent(agent_name="deepseek", position="I disagree", divergence_score=0.65),
        ]
        store.save_decision(decision)

        retrieved = store.get_decision(decision.id)
        assert len(retrieved.dissents) == 1
        assert retrieved.dissents[0].agent_name == "deepseek"
        assert retrieved.dissents[0].position == "I disagree"

    def test_action_items_preserved(self, store):
        decision = _make_decision()
        decision.action_items = ["do A", "do B", "do C"]
        store.save_decision(decision)

        retrieved = store.get_decision(decision.id)
        assert retrieved.action_items == ["do A", "do B", "do C"]
