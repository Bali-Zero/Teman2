"""
Test — Council Orchestrator.

Tests the full deliberation flow: dispatch, consensus, groupthink, escalation.
All LLM calls are mocked (no real subprocess).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mata_garuda.council.models import (
    AgentVote,
    ConsensusResult,
    CouncilDecision,
    Topic,
)
from mata_garuda.council.orchestrator import CouncilOrchestrator


def _make_topic(**kwargs) -> Topic:
    return Topic(
        id="test-topic-1",
        title=kwargs.get("title", "Test topic"),
        description=kwargs.get("description", "Should we do X?"),
        category=kwargs.get("category", "operational"),
        source="cli",
        created_at="2026-04-16T00:00:00Z",
    )


def _make_agent(name: str, position: str, elapsed: float = 30.0, success: bool = True) -> MagicMock:
    """Create a mock CouncilAgent."""
    agent = MagicMock()
    agent.name = name
    agent.runtime = "test"

    async def _deliberate(topic):
        return AgentVote(
            agent_name=name, runtime="test",
            position=position, confidence=0.7,
            key_arguments=["arg1"], risks_identified=["risk1"],
            elapsed_seconds=elapsed, success=success,
        )

    agent.deliberate = _deliberate
    return agent


def _make_failing_agent(name: str) -> MagicMock:
    """Create a mock agent that raises an exception."""
    agent = MagicMock()
    agent.name = name
    agent.runtime = "test"

    async def _deliberate(topic):
        raise TimeoutError(f"{name} timed out")

    agent.deliberate = _deliberate
    return agent


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.save_decision = MagicMock()
    return store


@pytest.fixture
def mock_moderator():
    mod = MagicMock()

    async def _synthesize(**kwargs):
        return {
            "synthesis": "Test synthesis",
            "action_items": ["item1"],
            "confidence": 7,
            "requires_zero_approval": False,
            "escalation_reason": "",
        }

    mod.synthesize = _synthesize
    return mod


class TestOrchestratorMinimumAgents:
    """Test minimum agent enforcement."""

    def test_insufficient_agents_abstain(self, mock_store, mock_moderator):
        """Fewer than min_agents → ABSTAIN."""
        orch = CouncilOrchestrator(
            agents=[_make_agent("claude", "pos")],
            moderator=mock_moderator,
            store=mock_store,
            min_agents=2,
        )
        topic = _make_topic()
        decision = asyncio.run(orch.deliberate(topic))

        assert decision.status == "abstain"
        assert "insufficient" in decision.synthesis.lower() or "insufficient" in decision.escalation_reason.lower()

    def test_sufficient_agents_proceed(self, mock_store, mock_moderator):
        """With enough agents, council proceeds."""
        orch = CouncilOrchestrator(
            agents=[
                _make_agent("claude", "position A"),
                _make_agent("gemini", "position B"),
            ],
            moderator=mock_moderator,
            store=mock_store,
            min_agents=2,
        )
        topic = _make_topic()
        with patch("mata_garuda.council.orchestrator.score_consensus") as mock_score:
            mock_score.return_value = ConsensusResult(score=0.70, method="jaccard")
            decision = asyncio.run(orch.deliberate(topic))

        assert decision.status != "abstain"
        assert len([v for v in decision.votes if v.success]) >= 2


class TestOrchestratorGracefulDegradation:
    """Test resilience when agents fail."""

    def test_one_agent_fails_others_continue(self, mock_store, mock_moderator):
        """1/3 agents fail → council proceeds with 2."""
        orch = CouncilOrchestrator(
            agents=[
                _make_agent("claude", "position A"),
                _make_failing_agent("gemini"),
                _make_agent("deepseek", "position C"),
            ],
            moderator=mock_moderator,
            store=mock_store,
            min_agents=2,
        )
        topic = _make_topic()
        with patch("mata_garuda.council.orchestrator.score_consensus") as mock_score:
            mock_score.return_value = ConsensusResult(score=0.65, method="jaccard")
            decision = asyncio.run(orch.deliberate(topic))

        assert decision.status != "abstain"
        successful = [v for v in decision.votes if v.success]
        assert len(successful) == 2

    def test_two_agents_fail_abstain(self, mock_store, mock_moderator):
        """2/3 agents fail → ABSTAIN (below min_agents=2)."""
        orch = CouncilOrchestrator(
            agents=[
                _make_agent("claude", "position A"),
                _make_failing_agent("gemini"),
                _make_failing_agent("deepseek"),
            ],
            moderator=mock_moderator,
            store=mock_store,
            min_agents=2,
        )
        topic = _make_topic()
        decision = asyncio.run(orch.deliberate(topic))

        assert decision.status == "abstain"


class TestOrchestratorEscalation:
    """Test escalation decision logic."""

    def test_low_consensus_escalates(self, mock_store):
        """Consensus < 0.50 → requires_zero_approval."""
        mod = MagicMock()

        async def _synth(**kwargs):
            return {
                "synthesis": "Deep disagreement",
                "action_items": [],
                "confidence": 4,
                "requires_zero_approval": False,
                "escalation_reason": "",
            }

        mod.synthesize = _synth

        orch = CouncilOrchestrator(
            agents=[
                _make_agent("claude", "A"),
                _make_agent("gemini", "B"),
            ],
            moderator=mod,
            store=mock_store,
        )
        topic = _make_topic()
        with patch("mata_garuda.council.orchestrator.score_consensus") as mock_score:
            mock_score.return_value = ConsensusResult(score=0.35, method="jaccard")
            decision = asyncio.run(orch.deliberate(topic))

        assert decision.requires_zero_approval is True
        assert "consensus" in decision.escalation_reason

    def test_architecture_topic_escalates(self, mock_store, mock_moderator):
        """Architecture topics always escalate."""
        orch = CouncilOrchestrator(
            agents=[
                _make_agent("claude", "A"),
                _make_agent("gemini", "B"),
            ],
            moderator=mock_moderator,
            store=mock_store,
        )
        topic = _make_topic(category="architecture")
        with patch("mata_garuda.council.orchestrator.score_consensus") as mock_score:
            mock_score.return_value = ConsensusResult(score=0.90, method="jaccard")
            decision = asyncio.run(orch.deliberate(topic))

        assert decision.requires_zero_approval is True
        assert "architecture" in decision.escalation_reason

    def test_high_consensus_operational_auto_approved(self, mock_store, mock_moderator):
        """High consensus + operational → auto_approved."""
        orch = CouncilOrchestrator(
            agents=[
                _make_agent("claude", "same"),
                _make_agent("gemini", "same"),
            ],
            moderator=mock_moderator,
            store=mock_store,
        )
        topic = _make_topic(category="operational")
        with patch("mata_garuda.council.orchestrator.score_consensus") as mock_score:
            mock_score.return_value = ConsensusResult(score=0.80, method="jaccard")
            decision = asyncio.run(orch.deliberate(topic))

        assert decision.status == "auto_approved"
        assert decision.requires_zero_approval is False


class TestOrchestratorDecisionPersistence:
    """Test that decisions are stored."""

    def test_decision_persisted_to_store(self, mock_store, mock_moderator):
        """Decision is saved to store after deliberation."""
        orch = CouncilOrchestrator(
            agents=[
                _make_agent("claude", "A"),
                _make_agent("gemini", "B"),
            ],
            moderator=mock_moderator,
            store=mock_store,
        )
        topic = _make_topic()
        with patch("mata_garuda.council.orchestrator.score_consensus") as mock_score:
            mock_score.return_value = ConsensusResult(score=0.70, method="jaccard")
            asyncio.run(orch.deliberate(topic))

        mock_store.save_decision.assert_called_once()
        saved = mock_store.save_decision.call_args[0][0]
        assert isinstance(saved, CouncilDecision)
