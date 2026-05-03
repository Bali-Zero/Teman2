"""Tests for cell_core.reasoner — tier escalation framework."""
import asyncio
import json

import pytest

from cell_core.types import Proposal


class TestTierConfig:
    def test_creation(self):
        from cell_core.reasoner import TierConfig
        t = TierConfig(tier=0, name="fast", command=["echo", "test"], max_cost_usd=0.0, timeout_seconds=5.0)
        assert t.tier == 0
        assert t.name == "fast"


class TestReasonerFramework:
    def _make(self, tiers=None, allowlist=None):
        from cell_core.reasoner import ReasonerFramework, TierConfig
        if tiers is None:
            tiers = [
                TierConfig(
                    tier=0, name="echo_reasoner",
                    command=["echo", json.dumps({"action": "none", "reason": "stable", "confidence": 1.0})],
                    max_cost_usd=0.0, timeout_seconds=5.0,
                ),
            ]
        if allowlist is None:
            allowlist = ["restart_service", "alert_human", "none"]
        return ReasonerFramework(tiers=tiers, allowlist=allowlist)

    @pytest.mark.asyncio
    async def test_reason_returns_proposal(self):
        rf = self._make()
        proposal = await rf.reason("system is healthy", {})
        assert isinstance(proposal, Proposal)
        assert proposal.action == "none"

    @pytest.mark.asyncio
    async def test_tiers_sorted_by_cost(self):
        from cell_core.reasoner import TierConfig
        expensive = TierConfig(
            tier=1, name="expensive",
            command=["echo", json.dumps({"action": "none", "reason": "ok", "confidence": 1.0})],
            max_cost_usd=1.0, timeout_seconds=5.0,
        )
        cheap = TierConfig(
            tier=0, name="cheap",
            command=["echo", json.dumps({"action": "none", "reason": "ok", "confidence": 1.0})],
            max_cost_usd=0.0, timeout_seconds=5.0,
        )
        rf = self._make(tiers=[expensive, cheap])
        assert rf._tiers[0].name == "cheap"

    @pytest.mark.asyncio
    async def test_timeout_escalates(self):
        from cell_core.reasoner import TierConfig
        slow = TierConfig(
            tier=0, name="slow",
            command=["sleep", "10"],
            max_cost_usd=0.0, timeout_seconds=0.1,
        )
        fast = TierConfig(
            tier=1, name="fast",
            command=["echo", json.dumps({"action": "none", "reason": "fallback", "confidence": 0.5})],
            max_cost_usd=0.1, timeout_seconds=5.0,
        )
        rf = self._make(tiers=[slow, fast])
        proposal = await rf.reason("test", {})
        assert proposal.tier_used == 1  # escalated to fast

    @pytest.mark.asyncio
    async def test_invalid_json_escalates(self):
        from cell_core.reasoner import TierConfig
        bad = TierConfig(
            tier=0, name="bad",
            command=["echo", "not json"],
            max_cost_usd=0.0, timeout_seconds=5.0,
        )
        good = TierConfig(
            tier=1, name="good",
            command=["echo", json.dumps({"action": "none", "reason": "ok", "confidence": 0.8})],
            max_cost_usd=0.1, timeout_seconds=5.0,
        )
        rf = self._make(tiers=[bad, good])
        proposal = await rf.reason("test", {})
        assert proposal.tier_used == 1

    @pytest.mark.asyncio
    async def test_all_tiers_fail_returns_none_proposal(self):
        from cell_core.reasoner import TierConfig
        bad = TierConfig(
            tier=0, name="bad",
            command=["false"],  # exits with code 1
            max_cost_usd=0.0, timeout_seconds=2.0,
        )
        rf = self._make(tiers=[bad])
        proposal = await rf.reason("test", {})
        assert proposal.action == "none"
        assert proposal.tier_used == -1
