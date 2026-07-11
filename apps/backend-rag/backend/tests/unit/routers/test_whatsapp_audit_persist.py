"""WhatsApp unified audit-trail tests (COS-LAW-013, Case OS P0-0).

WhatsApp bypasses ChannelRouter; its `conversations` JSONB is a truncated
history buffer, not an audit record. `_persist_audit_messages` mirrors both
directions of every exchange into conversation_messages.
"""

from unittest.mock import AsyncMock

import pytest

from backend.app.routers.whatsapp_chat import _persist_audit_messages


@pytest.mark.asyncio
async def test_persists_both_directions():
    pool = AsyncMock()

    await _persist_audit_messages(
        db_pool=pool,
        phone="+62000000000",
        session_id="wa_s1",
        message_text="Berapa harga KITAS?",
        response_text="Il team ti risponde subito con la cifra ufficiale.",
    )

    assert pool.execute.await_count == 2
    first, second = pool.execute.await_args_list
    # args: (sql, direction, sender_id, content, metadata_json)
    assert first.args[1] == "inbound"
    assert first.args[2] == "+62000000000"
    assert first.args[3] == "Berapa harga KITAS?"
    assert second.args[1] == "outbound"
    assert second.args[2] == "zantara"
    assert "cifra ufficiale" in second.args[3]


@pytest.mark.asyncio
async def test_empty_response_persists_inbound_only():
    pool = AsyncMock()

    await _persist_audit_messages(
        db_pool=pool,
        phone="+62000000000",
        session_id="wa_s1",
        message_text="hello",
        response_text="",
    )

    assert pool.execute.await_count == 1
    assert pool.execute.await_args_list[0].args[1] == "inbound"


@pytest.mark.asyncio
async def test_db_failure_never_breaks_reply_flow():
    pool = AsyncMock()
    pool.execute.side_effect = RuntimeError("db down")

    # Must not raise — audit persistence is non-blocking by design.
    await _persist_audit_messages(
        db_pool=pool,
        phone="+62000000000",
        session_id="wa_s1",
        message_text="hi",
        response_text="hello",
    )

    assert pool.execute.await_count == 2  # tried both, swallowed both


@pytest.mark.asyncio
async def test_no_pool_is_a_noop():
    await _persist_audit_messages(
        db_pool=None,
        phone="+62000000000",
        session_id="wa_s1",
        message_text="hi",
        response_text="hello",
    )
