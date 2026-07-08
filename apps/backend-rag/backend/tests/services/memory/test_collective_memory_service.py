from datetime import datetime, timezone

import pytest

from backend.services.memory.collective_memory_service import (
    CollectiveMemory,
    CollectiveMemoryService,
)


def test_collective_memory_to_dict_serializes_public_fields() -> None:
    learned_at = datetime(2026, 7, 1, 9, 30, tzinfo=timezone.utc)
    confirmed_at = datetime(2026, 7, 2, 10, 45, tzinfo=timezone.utc)
    memory = CollectiveMemory(
        id=42,
        content="KITAS renewals need a current sponsor letter",
        category="process",
        confidence=0.82,
        source_count=4,
        is_promoted=True,
        first_learned_at=learned_at,
        last_confirmed_at=confirmed_at,
        metadata={"internal": "not exported"},
    )

    result = memory.to_dict()

    assert result == {
        "id": 42,
        "content": "KITAS renewals need a current sponsor letter",
        "category": "process",
        "confidence": 0.82,
        "source_count": 4,
        "is_promoted": True,
        "first_learned_at": learned_at.isoformat(),
        "last_confirmed_at": confirmed_at.isoformat(),
    }


@pytest.mark.asyncio
async def test_set_pool_replaces_lazy_pool() -> None:
    service = CollectiveMemoryService()
    pool = object()

    await service.set_pool(pool)  # type: ignore[arg-type]

    assert service.pool is pool


def test_hash_content_normalizes_case_and_edges() -> None:
    assert CollectiveMemoryService._hash_content("  Same Fact  ") == (
        CollectiveMemoryService._hash_content("same fact")
    )


@pytest.mark.asyncio
async def test_write_paths_skip_without_database_pool() -> None:
    service = CollectiveMemoryService()

    contribution = await service.add_contribution(
        user_id="user@example.com",
        content="A sponsor letter is required",
        category="process",
    )
    refutation = await service.refute_fact(
        user_id="user@example.com",
        memory_id=123,
        reason="outdated",
    )

    assert contribution == {"status": "skipped", "reason": "no_database"}
    assert refutation == {"status": "skipped", "reason": "no_database"}


@pytest.mark.asyncio
async def test_read_paths_return_empty_values_without_database_pool() -> None:
    service = CollectiveMemoryService()

    context = await service.get_collective_context(category="process")
    memories = await service.get_all_memories(include_unpromoted=True)
    sources = await service.get_memory_sources(memory_id=123)
    similar = await service.search_similar("sponsor")
    stats = await service.get_stats()

    assert context == []
    assert memories == []
    assert sources == []
    assert similar == []
    assert stats == {"status": "no_database"}
