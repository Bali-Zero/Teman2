from types import SimpleNamespace

import pytest

from backend.services.oracle import user_context as user_context_module
from backend.services.oracle.user_context import UserContextService


class FakeDatabaseManager:
    def __init__(self, profile: dict | None = None, error: Exception | None = None) -> None:
        self.profile = profile
        self.error = error

    async def get_user_profile(self, user_email: str) -> dict | None:
        if self.error:
            raise self.error
        return self.profile


class FakePersonalityService:
    def __init__(self, response: dict | None = None, error: Exception | None = None) -> None:
        self.response = response or {"personality_type": "direct"}
        self.error = error

    def get_user_personality(self, user_email: str) -> dict:
        if self.error:
            raise self.error
        return self.response


class FakeMemoryService:
    def __init__(self, facts: list[str]) -> None:
        self.pool = object()
        self.facts = facts
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def get_memory(self, user_email: str) -> SimpleNamespace:
        return SimpleNamespace(profile_facts=self.facts)


@pytest.mark.asyncio
async def test_get_user_profile_returns_database_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = {"name": "Ari", "role_level": "admin"}
    monkeypatch.setattr(user_context_module, "db_manager", FakeDatabaseManager(profile))

    result = await UserContextService().get_user_profile("ari@example.com")

    assert result == profile


@pytest.mark.asyncio
async def test_get_user_profile_returns_none_on_database_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        user_context_module,
        "db_manager",
        FakeDatabaseManager(error=RuntimeError("db down")),
    )

    result = await UserContextService().get_user_profile("ari@example.com")

    assert result is None


@pytest.mark.asyncio
async def test_get_user_personality_defaults_without_service() -> None:
    assert await UserContextService().get_user_personality("ari@example.com") == {
        "personality_type": "professional",
    }


@pytest.mark.asyncio
async def test_get_user_personality_uses_service_and_handles_errors() -> None:
    assert await UserContextService(
        personality_service=FakePersonalityService({"personality_type": "warm"}),
    ).get_user_personality("ari@example.com") == {"personality_type": "warm"}

    assert await UserContextService(
        personality_service=FakePersonalityService(error=RuntimeError("broken")),
    ).get_user_personality("ari@example.com") == {"personality_type": "professional"}


@pytest.mark.asyncio
async def test_get_user_memory_facts_returns_memory_profile_facts() -> None:
    memory = FakeMemoryService(["likes short updates"])

    result = await UserContextService(memory_service=memory).get_user_memory_facts(
        "ari@example.com",
    )

    assert result == ["likes short updates"]
    assert memory.connected is False


@pytest.mark.asyncio
async def test_get_user_memory_facts_connects_when_pool_missing() -> None:
    memory = FakeMemoryService(["needs KITAS"])
    memory.pool = None

    result = await UserContextService(memory_service=memory).get_user_memory_facts(
        "ari@example.com",
    )

    assert result == ["needs KITAS"]
    assert memory.connected is True


@pytest.mark.asyncio
async def test_get_full_user_context_uses_defaults_without_email() -> None:
    result = await UserContextService().get_full_user_context(None)

    assert result == {
        "profile": None,
        "personality": {"personality_type": "professional"},
        "memory_facts": [],
        "user_name": "User",
        "user_role": "member",
    }


@pytest.mark.asyncio
async def test_get_full_user_context_combines_profile_personality_and_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        user_context_module,
        "db_manager",
        FakeDatabaseManager({"name": "Ari", "role_level": "admin"}),
    )

    result = await UserContextService(
        personality_service=FakePersonalityService({"personality_type": "direct"}),
        memory_service=FakeMemoryService(["prefers WhatsApp"]),
    ).get_full_user_context("ari@example.com")

    assert result["user_name"] == "Ari"
    assert result["user_role"] == "admin"
    assert result["personality"] == {"personality_type": "direct"}
    assert result["memory_facts"] == ["prefers WhatsApp"]
