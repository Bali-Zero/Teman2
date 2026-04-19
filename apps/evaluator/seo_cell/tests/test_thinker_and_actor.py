"""Thinker returns no-op in pre_natal; actor refuses non-whitelist actions."""
import pytest

from cell_core.types import HomeostaticState, Proposal, SensorReading
from apps.evaluator.seo_cell.actor import SEOActor
from apps.evaluator.seo_cell.phase import SEOPhase
from cell_core.types import Phase
from apps.evaluator.seo_cell.thinker import SEOThinker


@pytest.mark.asyncio
async def test_thinker_returns_none_in_pre_natal():
    """With stub GSC (query_count=0) the cell is always pre_natal →
    proposal.action must be 'none'."""
    thinker = SEOThinker()
    readings = [
        SensorReading(sensor_name="gsc", status="yellow", value={"query_count": 0}),
    ]
    proposal = await thinker.think(readings, HomeostaticState(), {})
    assert proposal.action == "none"
    assert thinker._last_phase is not None
    assert thinker._last_phase.pre_natal is True


@pytest.mark.asyncio
async def test_actor_refuses_non_none_action_when_pre_natal():
    actor = SEOActor()
    actor.set_phase(SEOPhase(native=Phase.EMBRIONE, pre_natal=True))
    outcome = await actor.act(
        Proposal(
            action="publish_schema",
            reason="test",
            confidence=0.9,
            tier_used=1,
        )
    )
    assert outcome == "refused_pre_natal"
    assert len(actor._refused_intents) == 1
    assert actor._refused_intents[0]["action"] == "publish_schema"


@pytest.mark.asyncio
async def test_actor_refuses_unknown_action_even_if_graduated():
    actor = SEOActor()
    actor.set_phase(SEOPhase(native=Phase.GIOVANE, pre_natal=False))
    outcome = await actor.act(
        Proposal(
            action="publish_schema",  # not in sprint1 whitelist
            reason="test",
            confidence=0.9,
            tier_used=1,
        )
    )
    assert outcome == "refused_not_implemented"


@pytest.mark.asyncio
async def test_actor_accepts_noop_always():
    actor = SEOActor()
    # No phase set — no-op is still safe
    outcome = await actor.act(
        Proposal(action="none", reason="stable", confidence=1.0, tier_used=0)
    )
    assert outcome == "no_action"


def test_actor_whitelist_is_only_noop_in_sprint1():
    actor = SEOActor()
    assert actor.can_execute("none") is True
    assert actor.can_execute("publish_schema") is False
    assert actor.can_execute("queue_article_draft") is False
