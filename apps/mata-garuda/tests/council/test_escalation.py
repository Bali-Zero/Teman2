"""
Test — Escalation Decision Logic.

Tests when decisions require Zero's approval.
"""
from __future__ import annotations

import pytest

from mata_garuda.council.models import ConsensusResult, Topic
from mata_garuda.council.orchestrator import CouncilOrchestrator


def _topic(category: str = "operational") -> Topic:
    return Topic(
        id="t1", title="Test", description="desc", category=category,
    )


class TestEscalationLogic:
    """Test _check_escalation method."""

    def setup_method(self):
        self.orch = CouncilOrchestrator.__new__(CouncilOrchestrator)

    def test_low_consensus_escalates(self):
        requires, reason = self.orch._check_escalation(
            topic=_topic(),
            consensus=ConsensusResult(score=0.35, method="jaccard"),
            mod_confidence=7,
            mod_result={"requires_zero_approval": False, "escalation_reason": ""},
        )
        assert requires is True
        assert "consensus" in reason

    def test_low_moderator_confidence_escalates(self):
        requires, reason = self.orch._check_escalation(
            topic=_topic(),
            consensus=ConsensusResult(score=0.70, method="jaccard"),
            mod_confidence=3,
            mod_result={"requires_zero_approval": False, "escalation_reason": ""},
        )
        assert requires is True
        assert "confidence" in reason

    def test_architecture_category_escalates(self):
        requires, reason = self.orch._check_escalation(
            topic=_topic(category="architecture"),
            consensus=ConsensusResult(score=0.90, method="jaccard"),
            mod_confidence=9,
            mod_result={"requires_zero_approval": False, "escalation_reason": ""},
        )
        assert requires is True
        assert "architecture" in reason

    def test_escalation_category_escalates(self):
        requires, reason = self.orch._check_escalation(
            topic=_topic(category="escalation"),
            consensus=ConsensusResult(score=0.90, method="jaccard"),
            mod_confidence=9,
            mod_result={"requires_zero_approval": False, "escalation_reason": ""},
        )
        assert requires is True

    def test_groupthink_escalates(self):
        requires, reason = self.orch._check_escalation(
            topic=_topic(),
            consensus=ConsensusResult(score=0.90, method="jaccard", groupthink_detected=True),
            mod_confidence=7,
            mod_result={"requires_zero_approval": False, "escalation_reason": ""},
        )
        assert requires is True
        assert "groupthink" in reason

    def test_moderator_requests_escalation(self):
        requires, reason = self.orch._check_escalation(
            topic=_topic(),
            consensus=ConsensusResult(score=0.70, method="jaccard"),
            mod_confidence=7,
            mod_result={"requires_zero_approval": True, "escalation_reason": "complex decision"},
        )
        assert requires is True
        assert "complex decision" in reason

    def test_no_escalation_normal_case(self):
        requires, reason = self.orch._check_escalation(
            topic=_topic(category="operational"),
            consensus=ConsensusResult(score=0.75, method="jaccard"),
            mod_confidence=8,
            mod_result={"requires_zero_approval": False, "escalation_reason": ""},
        )
        assert requires is False
        assert reason == ""

    def test_multiple_reasons_combined(self):
        requires, reason = self.orch._check_escalation(
            topic=_topic(category="architecture"),
            consensus=ConsensusResult(score=0.35, method="jaccard", groupthink_detected=True),
            mod_confidence=3,
            mod_result={"requires_zero_approval": True, "escalation_reason": "unclear"},
        )
        assert requires is True
        # Multiple reasons joined by semicolons
        assert ";" in reason
