"""Tests for Vertical Feedback (child→parent improvement proposals)."""
import pytest
import time

from cell_core.hgt.feedback import VerticalFeedback, STREAM_FEEDBACK


@pytest.mark.asyncio
async def test_propose_improvement_published(fake_redis, genome):
    """Child with improved inherited skill publishes proposal."""
    # Parent records original skill
    genome.record_skill(
        cell="parent", skill_id="chunk_v1",
        procedure="Split at 5000 chars", confidence=0.6,
        scope="Project", domain="rag",
    )
    # Child inherits and improves
    genome.record_skill(
        cell="child", skill_id="hgt_chunk_v1",
        procedure="Split at 10000 chars with overlap",
        confidence=0.85, scope="Project",
        inherited_from="chunk_v1", domain="rag",
    )
    # Simulate usage
    for _ in range(5):
        genome.use_skill("hgt_chunk_v1")

    child_skill = genome.get_active(cell="child")[0]

    feedback = VerticalFeedback(fake_redis, genome, cell_name="child")
    result = await feedback.propose_improvement(child_skill)
    assert result is True

    stream = fake_redis.get_stream(STREAM_FEEDBACK)
    assert len(stream) == 1
    _, data = stream[0]
    assert data["from_cell"] == "child"
    assert data["to_cell"] == "parent"
    assert data["original_inherited_from"] == "chunk_v1"


@pytest.mark.asyncio
async def test_propose_rejected_low_improvement(fake_redis, genome):
    """Proposal rejected if improvement < threshold."""
    genome.record_skill(
        cell="parent", skill_id="s1", procedure="p1",
        confidence=0.8, scope="Project",
    )
    genome.record_skill(
        cell="child", skill_id="hgt_s1", procedure="p2",
        confidence=0.85, scope="Project",  # only +0.05, below 0.15 threshold
        inherited_from="s1",
    )
    for _ in range(5):
        genome.use_skill("hgt_s1")

    child_skill = genome.get_active(cell="child")[0]
    feedback = VerticalFeedback(fake_redis, genome, cell_name="child")
    result = await feedback.propose_improvement(child_skill)
    assert result is False


@pytest.mark.asyncio
async def test_propose_rejected_low_uses(fake_redis, genome):
    """Proposal rejected if uses < MIN_USES."""
    genome.record_skill(
        cell="parent", skill_id="s1", procedure="p1",
        confidence=0.5, scope="Project",
    )
    genome.record_skill(
        cell="child", skill_id="hgt_s1", procedure="p2",
        confidence=0.9, scope="Project",
        inherited_from="s1",
    )
    # Only 1 use, below MIN_USES=3
    genome.use_skill("hgt_s1")

    child_skill = genome.get_active(cell="child")[0]
    feedback = VerticalFeedback(fake_redis, genome, cell_name="child")
    result = await feedback.propose_improvement(child_skill)
    assert result is False


@pytest.mark.asyncio
async def test_propose_rejected_not_inherited(fake_redis, genome):
    """Proposal rejected if skill is not inherited."""
    genome.record_skill(
        cell="child", skill_id="original",
        procedure="my own skill", confidence=0.9,
    )
    for _ in range(5):
        genome.use_skill("original")

    child_skill = genome.get_active(cell="child")[0]
    feedback = VerticalFeedback(fake_redis, genome, cell_name="child")
    result = await feedback.propose_improvement(child_skill)
    assert result is False


@pytest.mark.asyncio
async def test_propose_graceful_degradation(broken_redis, genome):
    """Redis down doesn't crash proposal."""
    genome.record_skill(
        cell="parent", skill_id="s1", procedure="p1",
        confidence=0.5, scope="Project",
    )
    genome.record_skill(
        cell="child", skill_id="hgt_s1", procedure="p2",
        confidence=0.9, scope="Project", inherited_from="s1",
    )
    for _ in range(5):
        genome.use_skill("hgt_s1")

    child_skill = genome.get_active(cell="child")[0]
    feedback = VerticalFeedback(broken_redis, genome, cell_name="child")
    result = await feedback.propose_improvement(child_skill)
    assert result is False  # no crash


@pytest.mark.asyncio
async def test_process_proposals_merge(fake_redis, genome):
    """Parent accepts and merges valid improvement."""
    # Parent skill
    genome.record_skill(
        cell="parent", skill_id="s1",
        procedure="old technique", confidence=0.6,
        scope="Project", domain="legal",
    )

    # Simulate child proposal via direct xadd
    await fake_redis.xadd(STREAM_FEEDBACK, {
        "skill_id": "hgt_s1",
        "from_cell": "child",
        "to_cell": "parent",
        "original_inherited_from": "s1",
        "new_confidence": "0.9",
        "procedure_updated": "improved technique with overlap",
        "uses": "5",
    })

    feedback = VerticalFeedback(fake_redis, genome, cell_name="parent")
    await feedback.ensure_group()
    result = await feedback.process_proposals()
    assert result["accepted"] == 1
    assert result["rejected"] == 0

    # Verify parent skill was updated
    active = genome.get_active(cell="parent")
    s1 = [s for s in active if s["id"] == "s1"][0]
    assert "improved technique" in s1["procedure"]
    # Merged confidence: 0.9 * 0.9 decay = 0.81
    assert abs(s1["confidence"] - 0.81) < 0.01


@pytest.mark.asyncio
async def test_process_proposals_reject_insufficient_improvement(fake_redis, genome):
    """Parent rejects proposal that doesn't meet threshold."""
    genome.record_skill(
        cell="parent", skill_id="s1",
        procedure="current technique", confidence=0.8,
    )

    await fake_redis.xadd(STREAM_FEEDBACK, {
        "skill_id": "hgt_s1",
        "from_cell": "child",
        "to_cell": "parent",
        "original_inherited_from": "s1",
        "new_confidence": "0.85",  # only +0.05, below threshold
        "procedure_updated": "slightly better",
        "uses": "10",
    })

    feedback = VerticalFeedback(fake_redis, genome, cell_name="parent")
    await feedback.ensure_group()
    result = await feedback.process_proposals()
    assert result["rejected"] == 1
    assert result["accepted"] == 0

    # Original unchanged
    active = genome.get_active(cell="parent")
    s1 = [s for s in active if s["id"] == "s1"][0]
    assert s1["procedure"] == "current technique"
    assert s1["confidence"] == 0.8


@pytest.mark.asyncio
async def test_cooldown_prevents_rapid_reproposal(fake_redis, genome):
    """After rejection, same skill from same cell is blocked for COOLDOWN_DAYS."""
    genome.record_skill(
        cell="parent", skill_id="s1", procedure="p1", confidence=0.8,
    )

    # First proposal — rejected (insufficient improvement)
    await fake_redis.xadd(STREAM_FEEDBACK, {
        "skill_id": "hgt_s1",
        "from_cell": "child",
        "to_cell": "parent",
        "original_inherited_from": "s1",
        "new_confidence": "0.85",
        "procedure_updated": "slightly better",
        "uses": "5",
    })

    feedback = VerticalFeedback(fake_redis, genome, cell_name="parent")
    await feedback.ensure_group()
    result1 = await feedback.process_proposals()
    assert result1["rejected"] == 1

    # Cooldown should be set
    assert ("child", "hgt_s1") in feedback._cooldown
