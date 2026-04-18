"""
AlertDispatcher tests.

Covers:
- team channel severity gating
- client channel filtering via notification_prefs
- notification_log dedup (ref-based)
- per-channel failure isolation
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock

import asyncpg
import pytest

from backend.services.compliance.alert_dispatcher import AlertDispatcher
from backend.services.compliance.alert_repository import AlertRow


pytestmark = pytest.mark.integration


def _alert(**overrides) -> AlertRow:
    base = dict(
        alert_id=f"alert_test_{uuid.uuid4().hex[:6]}",
        client_id=1,
        category="visa_expiry",
        severity="urgent",
        status="pending",
        deadline=date.today() + timedelta(days=7),
        days_until=7,
        compliance_item_ref="doc_1",
        dedup_key="visa:1:doc_1",
        message_it="messaggio IT",
        message_en="message EN",
        message_id="pesan ID",
        suggested_action="renew",
        estimated_cost_idr=None,
        evidence_refs=[],
        nb2_ref=None,
    )
    base.update(overrides)
    return AlertRow(**base)


@pytest.fixture
def mock_email() -> AsyncMock:
    m = AsyncMock()
    m.send = AsyncMock(return_value={"ok": True})
    return m


@pytest.fixture
def mock_telegram() -> AsyncMock:
    m = AsyncMock()
    m.send_message = AsyncMock(return_value={"ok": True})
    return m


@pytest.fixture
def mock_inapp() -> AsyncMock:
    m = AsyncMock()
    m.emit = AsyncMock(return_value=None)
    return m


@pytest.fixture
def mock_wa() -> AsyncMock:
    m = AsyncMock()
    m.send = AsyncMock(return_value={"ok": True})
    return m


@pytest.mark.asyncio
async def test_critical_alert_hits_telegram_owner(
    db_tx: asyncpg.Connection,
    sample_client,
    mock_email,
    mock_telegram,
    mock_inapp,
    mock_wa,
) -> None:
    dispatcher = AlertDispatcher.with_connection(
        db_tx,
        email_service=mock_email,
        telegram_service=mock_telegram,
        inapp_service=mock_inapp,
        wa_service=mock_wa,
    )
    alert = _alert(client_id=sample_client["id"], severity="critical")
    await dispatcher.dispatch(alert)
    # critical → exactly 1 telegram_owner call; verify the chat kwarg
    assert mock_telegram.send_message.await_count == 1
    assert mock_telegram.send_message.call_args.kwargs.get("chat") == "owner"


@pytest.mark.asyncio
async def test_warning_alert_skips_telegram_team(
    db_tx: asyncpg.Connection,
    sample_client,
    mock_email,
    mock_telegram,
    mock_inapp,
    mock_wa,
) -> None:
    dispatcher = AlertDispatcher.with_connection(
        db_tx,
        email_service=mock_email,
        telegram_service=mock_telegram,
        inapp_service=mock_inapp,
        wa_service=mock_wa,
    )
    alert = _alert(client_id=sample_client["id"], severity="warning")
    await dispatcher.dispatch(alert)
    # warning → team: only in-app; no Telegram team ping
    mock_telegram.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_info_alert_inapp_only(
    db_tx: asyncpg.Connection,
    sample_client,
    mock_email,
    mock_telegram,
    mock_inapp,
    mock_wa,
) -> None:
    dispatcher = AlertDispatcher.with_connection(
        db_tx,
        email_service=mock_email,
        telegram_service=mock_telegram,
        inapp_service=mock_inapp,
        wa_service=mock_wa,
    )
    alert = _alert(client_id=sample_client["id"], severity="info")
    await dispatcher.dispatch(alert)
    mock_inapp.emit.assert_awaited()
    mock_telegram.send_message.assert_not_awaited()
    mock_email.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_client_email_sent_when_prefs_enable(
    db_tx: asyncpg.Connection,
    sample_client,
    mock_email,
    mock_telegram,
    mock_inapp,
    mock_wa,
) -> None:
    # Insert notification_prefs for the portal user of sample_client.
    # If clients table has no portal_user_id, dispatcher logs info and skips.
    portal_user_id = "00000000-0000-0000-0000-000000000001"
    await db_tx.execute(
        "INSERT INTO notification_prefs (user_id, email_enabled, wa_enabled) "
        "VALUES ($1::uuid, TRUE, FALSE) ON CONFLICT (user_id) DO UPDATE "
        "SET email_enabled=EXCLUDED.email_enabled, wa_enabled=EXCLUDED.wa_enabled",
        portal_user_id,
    )
    # Patch client row to carry the portal_user_id (column may be absent on some schemas)
    # Dispatcher is expected to fallback gracefully if column missing.

    dispatcher = AlertDispatcher.with_connection(
        db_tx,
        email_service=mock_email,
        telegram_service=mock_telegram,
        inapp_service=mock_inapp,
        wa_service=mock_wa,
        _resolve_portal_user_id=lambda client_id: portal_user_id,
    )
    alert = _alert(client_id=sample_client["id"], severity="urgent")
    await dispatcher.dispatch(alert)
    mock_email.send.assert_awaited()


@pytest.mark.asyncio
async def test_wa_suppressed_when_prefs_disable(
    db_tx: asyncpg.Connection,
    sample_client,
    mock_email,
    mock_telegram,
    mock_inapp,
    mock_wa,
) -> None:
    portal_user_id = "00000000-0000-0000-0000-000000000002"
    await db_tx.execute(
        "INSERT INTO notification_prefs (user_id, email_enabled, wa_enabled) "
        "VALUES ($1::uuid, TRUE, FALSE) ON CONFLICT (user_id) DO UPDATE "
        "SET email_enabled=EXCLUDED.email_enabled, wa_enabled=EXCLUDED.wa_enabled",
        portal_user_id,
    )
    dispatcher = AlertDispatcher.with_connection(
        db_tx,
        email_service=mock_email,
        telegram_service=mock_telegram,
        inapp_service=mock_inapp,
        wa_service=mock_wa,
        _resolve_portal_user_id=lambda client_id: portal_user_id,
    )
    alert = _alert(client_id=sample_client["id"], severity="urgent")
    await dispatcher.dispatch(alert)
    mock_wa.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_dedup_blocks_second_dispatch_same_channel_24h(
    db_tx: asyncpg.Connection,
    sample_client,
    mock_email,
    mock_telegram,
    mock_inapp,
    mock_wa,
) -> None:
    # Pre-insert a notification_log row with the exact ref → dispatcher must skip.
    portal_user_id = "00000000-0000-0000-0000-000000000003"
    alert = _alert(client_id=sample_client["id"], severity="urgent")
    await db_tx.execute(
        "INSERT INTO notification_log (user_id, channel, ref) VALUES ($1::uuid, $2, $3)",
        portal_user_id,
        "email_client",
        f"compliance_alert:{alert.alert_id}:email_client",
    )
    dispatcher = AlertDispatcher.with_connection(
        db_tx,
        email_service=mock_email,
        telegram_service=mock_telegram,
        inapp_service=mock_inapp,
        wa_service=mock_wa,
        _resolve_portal_user_id=lambda client_id: portal_user_id,
    )
    await db_tx.execute(
        "INSERT INTO notification_prefs (user_id, email_enabled, wa_enabled) "
        "VALUES ($1::uuid, TRUE, FALSE) ON CONFLICT (user_id) DO UPDATE "
        "SET email_enabled=TRUE",
        portal_user_id,
    )
    await dispatcher.dispatch(alert)
    mock_email.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_channel_failure_does_not_abort_other_channels(
    db_tx: asyncpg.Connection,
    sample_client,
    mock_email,
    mock_telegram,
    mock_inapp,
    mock_wa,
) -> None:
    mock_telegram.send_message = AsyncMock(side_effect=RuntimeError("telegram 500"))
    dispatcher = AlertDispatcher.with_connection(
        db_tx,
        email_service=mock_email,
        telegram_service=mock_telegram,
        inapp_service=mock_inapp,
        wa_service=mock_wa,
    )
    alert = _alert(client_id=sample_client["id"], severity="critical")
    await dispatcher.dispatch(alert)
    # inapp should still have fired even though telegram blew up
    mock_inapp.emit.assert_awaited()


@pytest.mark.asyncio
async def test_dedup_expired_25h_ago_does_not_block_resend(
    db_tx: asyncpg.Connection,
    sample_client,
    mock_email,
    mock_telegram,
    mock_inapp,
    mock_wa,
) -> None:
    # Pre-insert a notification_log row with sent_at 25h ago (outside window)
    portal_user_id = "00000000-0000-0000-0000-000000000099"
    alert = _alert(client_id=sample_client["id"], severity="urgent")
    await db_tx.execute(
        "INSERT INTO notification_log (user_id, channel, ref, sent_at) "
        "VALUES ($1::uuid, $2, $3, NOW() - INTERVAL '25 hours')",
        portal_user_id, "email_client",
        f"compliance_alert:{alert.alert_id}:email_client",
    )
    await db_tx.execute(
        "INSERT INTO notification_prefs (user_id, email_enabled, wa_enabled) "
        "VALUES ($1::uuid, TRUE, FALSE) ON CONFLICT (user_id) DO UPDATE "
        "SET email_enabled=TRUE",
        portal_user_id,
    )
    dispatcher = AlertDispatcher.with_connection(
        db_tx,
        email_service=mock_email,
        telegram_service=mock_telegram,
        inapp_service=mock_inapp,
        wa_service=mock_wa,
        _resolve_portal_user_id=lambda client_id: portal_user_id,
    )
    await dispatcher.dispatch(alert)
    # Entry is OUTSIDE the 24h window → email should fire
    mock_email.send.assert_awaited()
