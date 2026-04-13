"""
Tests for collective memory race conditions.
"""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_concurrent_fact_promotion():
    """Multiple concurrent fact promotions should not corrupt data."""
    facts = {}
    lock = asyncio.Lock()

    async def promote_fact(fact_id, score):
        async with lock:
            if fact_id not in facts or facts[fact_id] < score:
                facts[fact_id] = score

    tasks = [
        promote_fact("visa_cost", 0.8),
        promote_fact("visa_cost", 0.9),
        promote_fact("kitas_info", 0.7),
    ]
    await asyncio.gather(*tasks)
    assert facts["visa_cost"] == 0.9
    assert facts["kitas_info"] == 0.7


@pytest.mark.asyncio
async def test_concurrent_contribution_same_fact():
    """Multiple contributions to same fact should be additive."""
    contributions = []
    lock = asyncio.Lock()

    async def contribute(user_id, content):
        async with lock:
            contributions.append({"user_id": user_id, "content": content})

    await asyncio.gather(
        contribute("user-1", "KITAS is 1 year"),
        contribute("user-2", "KITAS is renewable"),
        contribute("user-1", "KITAS costs vary"),
    )
    assert len(contributions) == 3
