"""Tests for mata_garuda.cell.actor — MetaChain wrapped as cell-core Actor."""
import pytest
from unittest.mock import patch, MagicMock

from cell_core.types import Proposal
from cell_core.protocols import Actor


class TestMetaChainActor:
    def test_implements_actor_protocol(self):
        from mata_garuda.cell.actor import MetaChainActor
        actor = MetaChainActor()
        assert isinstance(actor, Actor)

    def test_can_execute_known_actions(self):
        from mata_garuda.cell.actor import MetaChainActor
        actor = MetaChainActor()
        assert actor.can_execute("run_regulation_watcher") is True
        assert actor.can_execute("run_meta_agent") is True
        assert actor.can_execute("unknown_action") is False

    @pytest.mark.asyncio
    async def test_act_runs_agent(self):
        from mata_garuda.cell.actor import MetaChainActor
        from mata_garuda.types import Response

        mock_response = Response(
            messages=[{"role": "assistant", "content": "Case resolved. The result is: done"}],
        )

        with patch("mata_garuda.cell.actor.get_agent", return_value=MagicMock(name="Regulation Watcher")), \
             patch("mata_garuda.cell.actor.run_with_lamarckian_feedback", return_value=mock_response):
            actor = MetaChainActor()
            proposal = Proposal(
                action="run_regulation_watcher",
                reason="daily harvest",
                confidence=0.9,
                tier_used=0,
            )
            result = await actor.act(proposal)

        assert "resolved" in result.lower() or "done" in result.lower()

    @pytest.mark.asyncio
    async def test_act_returns_failure_on_error(self):
        from mata_garuda.cell.actor import MetaChainActor

        with patch("mata_garuda.cell.actor.get_agent", return_value=MagicMock(name="Regulation Watcher")), \
             patch("mata_garuda.cell.actor.run_with_lamarckian_feedback", side_effect=Exception("boom")):
            actor = MetaChainActor()
            proposal = Proposal(action="run_regulation_watcher", reason="test", confidence=0.9, tier_used=0)
            result = await actor.act(proposal)

        assert "error" in result.lower()

    def test_executed_actions_tracked(self):
        from mata_garuda.cell.actor import MetaChainActor
        actor = MetaChainActor()
        assert actor.last_run_success is None  # no runs yet
