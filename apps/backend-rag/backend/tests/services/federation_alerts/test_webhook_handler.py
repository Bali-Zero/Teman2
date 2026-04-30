"""Unit tests for FAD webhook callback handler."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from backend.services.federation_alerts.approval import (
    callback_token_prefix,
    generate_approval_token,
)
from backend.services.federation_alerts.approval_models import encode_callback
from backend.services.federation_alerts.webhook import handle_fad_callback


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _proposal_dict(
    *,
    proposal_id: str = "550e8400-e29b-41d4-a716-446655440000",
    status: str = "awaiting_approval",
    approval_token: str | None = None,
    requires_approval: bool = True,
) -> dict:
    return {
        "id": 1,
        "proposal_id": proposal_id,
        "run_id": f"rid-{proposal_id}",
        "idempotency_key": f"iden-{proposal_id}",
        "source_outbox_id": None,
        "source_channel": "federation_alert",
        "source_ref": None,
        "mode": "production",
        "status": status,
        "alert_type": "cron_failure",
        "severity": "medium",
        "risk_level": "L2",
        "requested_action": "cleanup_log",
        "target_file": None,
        "action_payload": "{}",
        "compact_payload": '{"v":1}',
        "full_payload": "{}",
        "dispatch_plan": "{}",
        "deliberation_result": "{}",
        "votes": "{}",
        "gate_6_passes": None,
        "requires_approval": requires_approval,
        "approval_token": approval_token,
        "telegram_chat_id": "111",
        "telegram_message_id": 999,
        "approved_by": None,
        "approved_at": None,
        "rejected_by": None,
        "rejected_at": None,
        "action_idempotency_key": None,
        "quarantine_token": None,
        "quarantine_reason": None,
        "quarantined_at": None,
        "lease_owner": None,
        "lease_expires_at": None,
        "attempt_count": 0,
        "max_attempts": 3,
        "next_attempt_at": _now(),
        "last_error": None,
        "last_error_at": None,
        "artifact_uri": None,
        "created_at": _now(),
        "updated_at": _now(),
        "completed_at": None,
    }


def _callback_query(
    *,
    data: str,
    chat_id: int = 111,
    callback_id: str = "cb-1",
    username: str = "tester",
) -> dict:
    return {
        "id": callback_id,
        "data": data,
        "from": {"id": 42, "username": username},
        "message": {
            "chat": {"id": chat_id},
            "message_id": 999,
        },
    }


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("FEDERATION_ALERT_ADMIN_CHAT_IDS", "111")


@pytest.fixture(autouse=True)
def silence_telegram(monkeypatch):
    """Stub the urllib.urlopen calls so tests never hit the network."""
    import urllib.request as urlreq

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"ok":true,"result":{"message_id":1}}'

    monkeypatch.setattr(
        urlreq, "urlopen", lambda *a, **kw: _Resp()
    )


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_false_for_non_fad_callback(mock_db_pool, admin_env) -> None:
    pool, _ = mock_db_pool
    cq = _callback_query(data="intel:approve:news:abc")
    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is False


@pytest.mark.asyncio
async def test_malformed_callback_handled_silently(
    mock_db_pool, admin_env
) -> None:
    pool, _ = mock_db_pool
    cq = _callback_query(data="fad:malformed")
    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True


@pytest.mark.asyncio
async def test_non_admin_chat_id_rejected(mock_db_pool, admin_env) -> None:
    pool, conn = mock_db_pool
    pid = "550e8400-e29b-41d4-a716-446655440000"
    cb = encode_callback("approve", pid, "deadbeef")
    cq = _callback_query(data=cb, chat_id=999)  # NOT in admin allow-list
    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True
    # Repo must NOT have been called
    conn.fetchrow.assert_not_called()


# ---------------------------------------------------------------------------
# Approval flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_happy_path(mock_db_pool, admin_env) -> None:
    pool, conn = mock_db_pool
    token = generate_approval_token()
    pid = "550e8400-e29b-41d4-a716-446655440000"
    prefix = callback_token_prefix(token, pid)

    # First call: get_by_proposal_id returns the row.
    # Second call: record_approval UPDATE returns the row.
    conn.fetchrow = AsyncMock(
        side_effect=[
            _proposal_dict(proposal_id=pid, approval_token=token),
            _proposal_dict(
                proposal_id=pid,
                approval_token=token,
                status="executing",
            ),
        ]
    )

    cb = encode_callback("approve", pid, prefix)
    cq = _callback_query(data=cb, chat_id=111)

    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True
    # Two SQL calls: get_by_proposal_id + record_approval
    assert conn.fetchrow.await_count == 2


@pytest.mark.asyncio
async def test_proposal_not_found(mock_db_pool, admin_env) -> None:
    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(return_value=None)
    pid = "550e8400-e29b-41d4-a716-446655440000"
    cb = encode_callback("approve", pid, "deadbeef")
    cq = _callback_query(data=cb)

    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True
    # Only the lookup happened
    assert conn.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_token_mismatch_rejected(mock_db_pool, admin_env) -> None:
    pool, conn = mock_db_pool
    pid = "550e8400-e29b-41d4-a716-446655440000"
    real_token = generate_approval_token()
    conn.fetchrow = AsyncMock(
        return_value=_proposal_dict(
            proposal_id=pid, approval_token=real_token
        )
    )
    # Use a fake prefix, NOT derived from real_token
    cb = encode_callback("approve", pid, "00000000")
    cq = _callback_query(data=cb)

    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True
    # Lookup happened, but record_approval should NOT have run
    assert conn.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_callback_on_terminal_proposal_idempotent(
    mock_db_pool, admin_env
) -> None:
    """Late callback on already-completed proposal must not double-execute."""
    pool, conn = mock_db_pool
    pid = "550e8400-e29b-41d4-a716-446655440000"
    token = generate_approval_token()
    prefix = callback_token_prefix(token, pid)

    conn.fetchrow = AsyncMock(
        return_value=_proposal_dict(
            proposal_id=pid,
            approval_token=token,
            status="completed",
        )
    )

    cb = encode_callback("approve", pid, prefix)
    cq = _callback_query(data=cb)

    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True
    # Only the lookup; no UPDATE
    assert conn.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_reject_happy_path(mock_db_pool, admin_env) -> None:
    pool, conn = mock_db_pool
    pid = "550e8400-e29b-41d4-a716-446655440000"
    token = generate_approval_token()
    prefix = callback_token_prefix(token, pid)

    conn.fetchrow = AsyncMock(
        side_effect=[
            _proposal_dict(proposal_id=pid, approval_token=token),
            _proposal_dict(
                proposal_id=pid,
                approval_token=token,
                status="quarantined",
            ),
        ]
    )

    cb = encode_callback("reject", pid, prefix)
    cq = _callback_query(data=cb)

    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True
    assert conn.fetchrow.await_count == 2


@pytest.mark.asyncio
async def test_defer_no_db_write(mock_db_pool, admin_env) -> None:
    pool, conn = mock_db_pool
    pid = "550e8400-e29b-41d4-a716-446655440000"
    token = generate_approval_token()
    prefix = callback_token_prefix(token, pid)

    conn.fetchrow = AsyncMock(
        return_value=_proposal_dict(
            proposal_id=pid, approval_token=token
        )
    )

    cb = encode_callback("defer", pid, prefix)
    cq = _callback_query(data=cb)

    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True
    # Only the lookup; defer is a no-op DB-side
    assert conn.fetchrow.await_count == 1


# ---------------------------------------------------------------------------
# Mode change flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mode_change_rejected_when_no_secret(
    mock_db_pool, admin_env, monkeypatch
) -> None:
    """Without FEDERATION_ALERT_MODE_TOKEN env, mode changes refuse."""
    monkeypatch.delenv("FEDERATION_ALERT_MODE_TOKEN", raising=False)
    pool, conn = mock_db_pool
    cb = encode_callback("mode", "dry_action", "deadbeef")
    cq = _callback_query(data=cb)

    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_mode_change_token_mismatch_rejected(
    mock_db_pool, admin_env, monkeypatch
) -> None:
    monkeypatch.setenv("FEDERATION_ALERT_MODE_TOKEN", "secret-mode")
    pool, conn = mock_db_pool
    cb = encode_callback("mode", "dry_action", "00000000")  # wrong prefix
    cq = _callback_query(data=cb)

    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_mode_change_happy_path(
    mock_db_pool, admin_env, monkeypatch
) -> None:
    import hashlib
    import hmac

    monkeypatch.setenv("FEDERATION_ALERT_MODE_TOKEN", "secret-mode")
    target = "dry_action"
    expected_prefix = hmac.new(
        b"secret-mode",
        f"mode:{target}".encode(),
        hashlib.sha256,
    ).hexdigest()[:8]

    pool, conn = mock_db_pool
    conn.execute = AsyncMock(return_value="UPDATE 1")
    cb = encode_callback("mode", target, expected_prefix)
    cq = _callback_query(data=cb)

    handled = await handle_fad_callback(cq, pool=pool, bot_token="t")
    assert handled is True
    conn.execute.assert_awaited_once()
