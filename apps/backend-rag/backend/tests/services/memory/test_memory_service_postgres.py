from datetime import datetime, timezone

import pytest

from backend.services.memory.memory_service_postgres import (
    MemoryServicePostgres,
    UserMemory,
)


class FakePool:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _memory_service() -> MemoryServicePostgres:
    service = MemoryServicePostgres(database_url="postgresql://unused")
    service.use_postgres = False
    service.pool = None
    service.memory_cache = {}
    return service


def test_user_memory_to_dict_serializes_datetime() -> None:
    updated_at = datetime(2026, 7, 5, 12, 30, tzinfo=timezone.utc)
    memory = UserMemory(
        user_id="user@example.com",
        profile_facts=["prefers concise updates"],
        summary="Active PT PMA case",
        counters={"conversations": 2},
        updated_at=updated_at,
    )

    assert memory.to_dict() == {
        "user_id": "user@example.com",
        "profile_facts": ["prefers concise updates"],
        "summary": "Active PT PMA case",
        "counters": {"conversations": 2},
        "updated_at": updated_at.isoformat(),
    }


@pytest.mark.asyncio
async def test_connect_without_database_url_uses_memory_only() -> None:
    service = _memory_service()

    await service.connect()

    assert service.pool is None
    assert service.use_postgres is False


@pytest.mark.asyncio
async def test_close_closes_existing_pool() -> None:
    service = _memory_service()
    pool = FakePool()
    service.pool = pool  # type: ignore[assignment]

    await service.close()

    assert pool.closed is True


@pytest.mark.asyncio
async def test_get_and_save_memory_use_cache_without_postgres() -> None:
    service = _memory_service()

    memory = await service.get_memory("user@example.com")
    memory.summary = "Case summary"
    saved = await service.save_memory(memory)
    cached = await service.get_memory("user@example.com")

    assert saved is True
    assert cached is memory
    assert cached.summary == "Case summary"


@pytest.mark.asyncio
async def test_add_fact_deduplicates_and_trims_cache() -> None:
    service = _memory_service()

    assert await service.add_fact("user@example.com", "  Has KITAS  ") is True
    assert await service.add_fact("user@example.com", "has kitas") is False

    for index in range(service.MAX_FACTS + 2):
        assert await service.add_fact("user@example.com", f"fact-{index}") is True

    memory = await service.get_memory("user@example.com")
    assert len(memory.profile_facts) == service.MAX_FACTS
    assert memory.profile_facts[0] == "fact-2"
    assert memory.profile_facts[-1] == f"fact-{service.MAX_FACTS + 1}"


@pytest.mark.asyncio
async def test_update_summary_truncates_to_configured_length() -> None:
    service = _memory_service()

    success = await service.update_summary("user@example.com", "x" * (service.MAX_SUMMARY_LENGTH + 20))

    memory = await service.get_memory("user@example.com")
    assert success is True
    assert len(memory.summary) == service.MAX_SUMMARY_LENGTH
    assert memory.summary.endswith("...")


@pytest.mark.asyncio
async def test_increment_counter_creates_unknown_counter() -> None:
    service = _memory_service()

    assert await service.increment_counter("user@example.com", "tasks") is True
    assert await service.increment_counter("user@example.com", "custom") is True

    memory = await service.get_memory("user@example.com")
    assert memory.counters["tasks"] == 1
    assert memory.counters["custom"] == 1


@pytest.mark.asyncio
async def test_save_fact_aliases_add_fact() -> None:
    service = _memory_service()

    assert await service.save_fact("user@example.com", "Uses WhatsApp", fact_type="preference") is True

    memory = await service.get_memory("user@example.com")
    assert memory.profile_facts == ["Uses WhatsApp"]


@pytest.mark.asyncio
async def test_search_uses_in_memory_cache_and_limit() -> None:
    service = _memory_service()
    await service.add_fact("alice@example.com", "Prefers Bali updates")
    await service.add_fact("bob@example.com", "Bali company setup")
    await service.update_summary("carol@example.com", "Asked about Bali visas")

    results = await service.search("bali", limit=2)

    assert len(results) == 2
    assert {result["user_id"] for result in results} == {
        "alice@example.com",
        "bob@example.com",
    }
    assert all(result["confidence"] == 1.0 for result in results)


@pytest.mark.asyncio
async def test_relevant_facts_recent_history_and_stats_without_postgres() -> None:
    service = _memory_service()
    await service.add_fact("user@example.com", "Needs investor KITAS")

    assert await service.get_relevant_facts("user@example.com", "kitas") == [
        "Needs investor KITAS",
    ]
    assert await service.get_recent_history("user@example.com") == []

    stats = await service.get_stats()
    assert stats["cached_users"] == 1
    assert stats["postgres_enabled"] is False
    assert stats["max_facts"] == service.MAX_FACTS
