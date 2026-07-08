from types import SimpleNamespace

import pytest

from backend.data.team_members import TEAM_MEMBERS
from backend.services.oracle import oracle_database as database_module
from backend.services.oracle.oracle_database import DatabaseManager, db_manager, get_db_manager


class FakeManager:
    async def get_user_profile(self, user_email: str) -> dict:
        return {"email": user_email}

    async def store_feedback(self, feedback_data: dict) -> None:
        self.feedback_data = feedback_data

    async def store_query_analytics(self, analytics_data: dict) -> None:
        self.analytics_data = analytics_data


def test_database_manager_skips_engine_for_placeholder_url() -> None:
    manager = DatabaseManager("postgresql://user:pass@localhost/db")

    assert manager._engine is None


def test_get_db_manager_uses_lazy_singleton_with_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(database_module, "_db_manager_instance", None)
    monkeypatch.setattr(
        database_module,
        "oracle_config",
        SimpleNamespace(database_url="postgresql://user:pass@localhost/db"),
    )

    first = get_db_manager()
    second = get_db_manager()

    assert first is second
    assert isinstance(first, DatabaseManager)
    assert first._engine is None


@pytest.mark.asyncio
async def test_get_user_profile_prefers_static_team_members() -> None:
    member = TEAM_MEMBERS[0]
    manager = DatabaseManager("postgresql://user:pass@localhost/db")

    profile = await manager.get_user_profile(member["email"])

    assert profile is not None
    assert profile["email"] == member["email"]
    assert profile["name"] == member.get("name", "Team Member")
    assert profile["language_preference"] == member.get("preferred_language", "en")


@pytest.mark.asyncio
async def test_get_user_profile_returns_none_without_static_or_db_match() -> None:
    manager = DatabaseManager("postgresql://user:pass@localhost/db")

    assert await manager.get_user_profile("missing-user@example.invalid") is None


@pytest.mark.asyncio
async def test_store_methods_degrade_when_engine_is_missing() -> None:
    manager = DatabaseManager("postgresql://user:pass@localhost/db")

    assert await manager.store_query_analytics({"query_text": "q"}) is None
    assert await manager.store_feedback({"query_text": "q"}) is None


@pytest.mark.asyncio
async def test_db_manager_proxy_forwards_to_lazy_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeManager()
    monkeypatch.setattr(database_module, "_db_manager_instance", fake)

    assert await db_manager.get_user_profile("user@example.com") == {
        "email": "user@example.com",
    }
    await db_manager.store_feedback({"rating": 5})
    await db_manager.store_query_analytics({"query": "visa"})

    assert fake.feedback_data == {"rating": 5}
    assert fake.analytics_data == {"query": "visa"}
