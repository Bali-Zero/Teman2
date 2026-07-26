"""
Containment tests for the shared/service-identity memory bleed (P0-MEM).

Path B (WhatsApp) authenticates every sender via a SHARED internal key
(``hybrid_auth.py``), which resolves to ONE fixed pseudo-identity
(``wa-mirror-internal`` / ``wa-mirror-internal@balizero.com``) for every
client. Before this fix that shared id was used as the long-term memory
``user_id`` key on both the write side (``memory_handler.save_conversation_memory``)
and the read side (``context_manager.get_user_context``) — so facts from
ANY client were saved AND read back under one shared bucket, bleeding
across clients (UU PDP violation).

Containment: a single predicate, ``is_non_personal_memory_identity``,
applied at both chokepoints so the shared identity is treated exactly
like ``"anonymous"`` — no save, no read. In-thread ``conversation_history``
(API-supplied, not keyed on this user_id) is untouched by this fix and is
NOT covered here — see ``test_context_manager.py`` for that contract.

GUILT = the shared identity must be blocked.
INNOCENCE = real authenticated users must be unaffected (no regression).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag.agentic import context_manager as module
from backend.services.rag.agentic._memory_identity import (
    NON_PERSONAL_MEMORY_IDS,
    is_non_personal_memory_identity,
)
from backend.services.rag.agentic.context_manager import get_user_context
from backend.services.rag.agentic.memory_handler import MemoryHandler

# ============================================================
# Predicate contract — is_non_personal_memory_identity
# ============================================================

NON_PERSONAL_CASES = [
    None,
    "",
    "   ",
    "anonymous",
    "Anonymous",
    "ANONYMOUS",
    "wa-mirror-internal",
    "WA-Mirror-Internal",
    "WA-MIRROR-INTERNAL",
    "wa-mirror-internal@balizero.com",
    "WA-Mirror-Internal@BaliZero.com",
    "  wa-mirror-internal@balizero.com  ",
]

PERSONAL_CASES = [
    "real.client@example.com",
    "user@test.com",
    "marco@example.com",
    "wa-mirror-internal2",  # near-miss, must NOT match (no bare-substring trap)
    "not-wa-mirror-internal",
    "somewa-mirror-internal@balizero.com",
]


@pytest.mark.parametrize("value", NON_PERSONAL_CASES)
def test_is_non_personal_memory_identity_true_cases(value: str | None) -> None:
    assert is_non_personal_memory_identity(value) is True


@pytest.mark.parametrize("value", PERSONAL_CASES)
def test_is_non_personal_memory_identity_false_cases(value: str) -> None:
    assert is_non_personal_memory_identity(value) is False


def test_non_personal_memory_ids_contains_expected_identities() -> None:
    assert NON_PERSONAL_MEMORY_IDS == frozenset(
        {"anonymous", "wa-mirror-internal", "wa-mirror-internal@balizero.com"},
    )


# ============================================================
# WRITE chokepoint — memory_handler.save_conversation_memory
# ============================================================


@dataclass
class FakeProcessResult:
    success: bool = True
    facts_extracted: int = 1
    facts_saved: int = 1
    processing_time_ms: float = 1.0


@pytest.fixture
def handler() -> MemoryHandler:
    return MemoryHandler(db_pool=MagicMock())


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    orch = AsyncMock()
    orch.process_conversation = AsyncMock(return_value=FakeProcessResult())
    return orch


@pytest.mark.asyncio
async def test_save_guilt_shared_identity_email(
    handler: MemoryHandler,
    mock_orchestrator: AsyncMock,
) -> None:
    """GUILT: the shared wa-mirror-internal EMAIL form must never persist facts."""
    handler._memory_orchestrator = mock_orchestrator
    await handler.save_conversation_memory(
        user_id="wa-mirror-internal@balizero.com",
        query="q",
        answer="a",
    )
    mock_orchestrator.process_conversation.assert_not_called()


@pytest.mark.asyncio
async def test_save_guilt_shared_identity_bare(
    handler: MemoryHandler,
    mock_orchestrator: AsyncMock,
) -> None:
    """GUILT: the shared wa-mirror-internal BARE form must never persist facts."""
    handler._memory_orchestrator = mock_orchestrator
    await handler.save_conversation_memory(
        user_id="wa-mirror-internal",
        query="q",
        answer="a",
    )
    mock_orchestrator.process_conversation.assert_not_called()


@pytest.mark.asyncio
async def test_save_innocence_real_client(
    handler: MemoryHandler,
    mock_orchestrator: AsyncMock,
) -> None:
    """INNOCENCE: a real authenticated client must still get memory saved (no regression)."""
    handler._memory_orchestrator = mock_orchestrator
    await handler.save_conversation_memory(
        user_id="real.client@example.com",
        query="q",
        answer="a",
    )
    mock_orchestrator.process_conversation.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_regression_anonymous_still_skipped(
    handler: MemoryHandler,
    mock_orchestrator: AsyncMock,
) -> None:
    """REGRESSION: pre-existing anonymous-skip behaviour must be preserved."""
    handler._memory_orchestrator = mock_orchestrator
    await handler.save_conversation_memory(user_id="anonymous", query="q", answer="a")
    mock_orchestrator.process_conversation.assert_not_called()


@pytest.mark.asyncio
async def test_save_regression_empty_user_still_skipped(
    handler: MemoryHandler,
    mock_orchestrator: AsyncMock,
) -> None:
    """REGRESSION: pre-existing empty-user-skip behaviour must be preserved."""
    handler._memory_orchestrator = mock_orchestrator
    await handler.save_conversation_memory(user_id="", query="q", answer="a")
    mock_orchestrator.process_conversation.assert_not_called()


# ============================================================
# READ chokepoint — context_manager.get_user_context
# ============================================================

EMPTY_CONTEXT: dict[str, Any] = {
    "profile": None,
    "history": [],
    "facts": [],
    "collective_facts": [],
    "entities": {},
}


def _patch_fetchers(monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncMock, AsyncMock]:
    profile_mock = AsyncMock(return_value={"profile": {"name": "Marco"}, "history": [], "entities": {}})
    memory_mock = AsyncMock(
        return_value={
            "facts": ["some fact"],
            "collective_facts": [],
            "timeline_summary": None,
            "kg_entities": [],
            "summary": None,
            "counters": None,
            "memory_context": None,
        },
    )
    monkeypatch.setattr(module, "fetch_profile_and_history", profile_mock)
    monkeypatch.setattr(module, "fetch_memory_facts", memory_mock)
    return profile_mock, memory_mock


@pytest.mark.asyncio
async def test_get_user_context_guilt_shared_identity_bare(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GUILT: shared bare identity must get the neutral empty context, no fetch."""
    profile_mock, memory_mock = _patch_fetchers(monkeypatch)

    result = await get_user_context(MagicMock(), "wa-mirror-internal")

    assert result == EMPTY_CONTEXT
    profile_mock.assert_not_called()
    memory_mock.assert_not_called()


@pytest.mark.asyncio
async def test_get_user_context_guilt_shared_identity_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GUILT: shared email-form identity must get the neutral empty context, no fetch."""
    profile_mock, memory_mock = _patch_fetchers(monkeypatch)

    result = await get_user_context(MagicMock(), "wa-mirror-internal@balizero.com")

    assert result == EMPTY_CONTEXT
    profile_mock.assert_not_called()
    memory_mock.assert_not_called()


@pytest.mark.asyncio
async def test_get_user_context_innocence_real_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INNOCENCE: a real authenticated client must still get profile+facts fetched."""
    profile_mock, memory_mock = _patch_fetchers(monkeypatch)

    result = await get_user_context(MagicMock(), "real.client@example.com")

    profile_mock.assert_awaited_once()
    memory_mock.assert_awaited_once()
    assert result["facts"] == ["some fact"]
    assert result["profile"] == {"name": "Marco"}


@pytest.mark.asyncio
async def test_get_user_context_regression_anonymous_still_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REGRESSION: pre-existing anonymous-skip behaviour must be preserved,
    even when a real (non-None) db_pool is supplied."""
    profile_mock, memory_mock = _patch_fetchers(monkeypatch)

    result = await get_user_context(MagicMock(), "anonymous")

    assert result == EMPTY_CONTEXT
    profile_mock.assert_not_called()
    memory_mock.assert_not_called()


@pytest.mark.asyncio
async def test_get_user_context_regression_no_db_pool_still_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REGRESSION: pre-existing no-db_pool-skip behaviour must be preserved."""
    profile_mock, memory_mock = _patch_fetchers(monkeypatch)

    result = await get_user_context(None, "real.client@example.com")

    assert result == EMPTY_CONTEXT
    profile_mock.assert_not_called()
    memory_mock.assert_not_called()
