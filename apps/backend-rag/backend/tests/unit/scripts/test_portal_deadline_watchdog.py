"""Tests for the portal_deadline_watchdog cron script."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from scripts.portal_deadline_watchdog import _format_message, _iter_due, _log_sent, run


def test_format_message_mentions_label_and_date() -> None:
    due = date(2026, 6, 15)
    msg = _format_message("Visa expiry", due)
    assert "Visa expiry" in msg
    assert "2026-06-15" in msg


@pytest.mark.asyncio
async def test_iter_due_returns_empty_when_query_fails() -> None:
    conn = AsyncMock()
    conn.fetch.side_effect = Exception("relation 'notification_prefs' does not exist")
    assert await _iter_due(conn) == []


@pytest.mark.asyncio
async def test_log_sent_tolerates_insert_failure() -> None:
    conn = AsyncMock()
    conn.execute.side_effect = Exception("notification_log missing")
    # should not raise
    await _log_sent(conn, "uuid", "practice:1")


@pytest.mark.asyncio
async def test_run_dry_run_does_not_send(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://dummy")

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "user_id": "uuid-a",
            "wa_phone": "628123456789",
            "ref": "practice:1",
            "label": "KITAS renewal",
            "due_date": datetime.now(timezone.utc) + timedelta(days=5),
        },
    ]
    with patch("scripts.portal_deadline_watchdog.asyncpg.connect", new=AsyncMock(return_value=mock_conn)):
        code = await run(dry_run=True)
    assert code == 0
    # No send path should have been taken in dry-run, so execute is only for log?
    # Actually in dry-run we don't log either — the logger.info suffices.
    mock_conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_run_sends_and_logs(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://dummy")

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "user_id": "uuid-a",
            "wa_phone": "628123456789",
            "ref": "practice:1",
            "label": "KITAS renewal",
            "due_date": datetime.now(timezone.utc) + timedelta(days=5),
        },
        {
            "user_id": "uuid-b",
            "wa_phone": "628987654321",
            "ref": "client-visa:10",
            "label": "Visa expiry",
            "due_date": datetime.now(timezone.utc) + timedelta(days=2),
        },
    ]
    fake_wa = AsyncMock()
    fake_wa.send_message = AsyncMock(return_value={"id": "sent"})

    import scripts.portal_deadline_watchdog as mod
    import sys, types

    fake_module = types.ModuleType("backend.services.integrations.whatsapp_service")
    fake_module.whatsapp_service = fake_wa  # type: ignore[attr-defined]

    # Preload the import so `from backend.services.integrations.whatsapp_service import whatsapp_service`
    # inside run() picks our stub.
    sys.modules["backend.services.integrations.whatsapp_service"] = fake_module

    with patch.object(mod.asyncpg, "connect", new=AsyncMock(return_value=mock_conn)):
        code = await run(dry_run=False)
    assert code == 0
    assert fake_wa.send_message.await_count == 2
    # Two notification_log INSERTs expected
    assert mock_conn.execute.await_count == 2
