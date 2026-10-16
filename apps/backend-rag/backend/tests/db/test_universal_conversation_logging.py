"""Fault injection for all remaining repository error-reporting boundaries."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.retention_policy import ALLOW_CLOCK_DELETE_ENV
from backend.db.repositories.conversation_repository import ConversationRepository
from backend.services.common import cache


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,args,expected",
    [
        ("get_messages", ("synthetic-session",), []),
        ("cleanup_old_conversations", (), 0),
        ("anonymize_user_data", (), 0),
    ],
)
async def test_repository_failure_never_logs_exception_text(
    method, args, expected, monkeypatch, caplog
):
    marker = "SYNTHETIC_SENSITIVE_SENTINEL"
    pool = MagicMock()
    pool.acquire.side_effect = RuntimeError(marker + "\nDETAIL: " + marker)
    monkeypatch.setenv(ALLOW_CLOCK_DELETE_ENV, "1")
    monkeypatch.setattr(cache, "_invalidate_cache", AsyncMock(return_value=0))
    assert await getattr(ConversationRepository(pool), method)(*args) == expected
    assert "RuntimeError" in caplog.text
    assert marker not in caplog.text
