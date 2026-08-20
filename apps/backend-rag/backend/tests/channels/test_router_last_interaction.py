"""last_interaction_date freshness — ChannelRouter (ops/interaction-truth, 2026-08-21).

Before this: `clients.last_interaction_date` was written ONLY when a team
member manually logged an interaction or created a practice — an inbound
WhatsApp/Telegram/web message from a client already in the CRM never touched
it. Every dashboard metric, campaign segment, and sort/filter reading that
column was therefore measuring interface adoption, not the relationship.

These tests cover the two things that matter:
1. `_touch_client_interaction` itself — the UPDATE + cache-invalidate
   mechanism, and that a DB failure never propagates (non-blocking).
2. The wiring in `_enrich_with_routing` — it fires exactly when an inbound
   message resolves to a known CRM client, and never otherwise (unknown
   sender, DB unavailable).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.channels.base import ChannelMessage, ChannelResponse
from backend.channels.router import ChannelRouter

# ---------------------------------------------------------------------------
# _touch_client_interaction — direct unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_touch_client_interaction_updates_and_invalidates_cache():
    """Guilt: a resolved client_id writes NOW() and busts the stats cache."""
    router = ChannelRouter(MagicMock())
    db_pool = AsyncMock()

    with patch("backend.channels.router.invalidate_cache", AsyncMock()) as mock_invalidate:
        await router._touch_client_interaction(42, db_pool)

    assert db_pool.execute.await_count == 1
    sql, client_id = db_pool.execute.await_args.args
    assert "UPDATE clients" in sql
    assert "last_interaction_date = NOW()" in sql
    assert client_id == 42
    mock_invalidate.assert_awaited_once_with("zantara:crm_clients_stats:*")


@pytest.mark.asyncio
async def test_touch_client_interaction_db_failure_is_non_blocking():
    """A broken pool must never raise out of this helper — routing continues."""
    router = ChannelRouter(MagicMock())
    db_pool = AsyncMock()
    db_pool.execute.side_effect = RuntimeError("pool exhausted")

    try:
        await router._touch_client_interaction(42, db_pool)
    except RuntimeError:
        pytest.fail("_touch_client_interaction must swallow DB errors, not propagate them")


# ---------------------------------------------------------------------------
# _enrich_with_routing — wiring tests (only fires on resolved inbound client)
# ---------------------------------------------------------------------------


def _make_message(text: str = "Ciao, quanto costa il KITAS?") -> ChannelMessage:
    return ChannelMessage(
        user_id="whatsapp_628123456789",
        session_id="wa_session_628123456789",
        text=text,
        channel="whatsapp",
        metadata={"phone": "628123456789"},
    )


def _patch_enrichment_internals():
    """Patch the two heavyweight collaborators _enrich_with_routing calls,
    so tests exercise only the client-touch wiring this PR adds."""
    from backend.services.communication.models import MessageIntent, Priority

    decision = MagicMock()
    decision.intent = MessageIntent.UNKNOWN
    decision.priority = Priority.NORMAL
    decision.is_vip = False

    route_message = AsyncMock(return_value=decision)
    thread_manager_cls = MagicMock()
    thread_manager = AsyncMock()
    thread_manager.get_or_create_thread = AsyncMock(return_value="thread-1")
    thread_manager.update_thread = AsyncMock()
    thread_manager_cls.return_value = thread_manager

    return (
        patch("backend.services.communication.routing_engine.route_message", route_message),
        patch(
            "backend.services.communication.thread_manager.ThreadManager",
            thread_manager_cls,
        ),
    )


@pytest.mark.asyncio
async def test_enrich_touches_interaction_when_client_resolves():
    """A known client messaging in bumps last_interaction_date exactly once."""
    router = ChannelRouter(MagicMock())
    router._db_pool = AsyncMock()
    router._resolve_client_id = AsyncMock(return_value=101)
    router._touch_client_interaction = AsyncMock()

    patch_route, patch_thread = _patch_enrichment_internals()
    with patch_route, patch_thread:
        await router._enrich_with_routing(_make_message(), "whatsapp")

    router._touch_client_interaction.assert_awaited_once_with(101, router._db_pool)


@pytest.mark.asyncio
async def test_enrich_skips_touch_when_client_unresolved():
    """Innocence: an unknown sender (prospect, wrong number, ...) never writes."""
    router = ChannelRouter(MagicMock())
    router._db_pool = AsyncMock()
    router._resolve_client_id = AsyncMock(return_value=None)
    router._touch_client_interaction = AsyncMock()

    patch_route, patch_thread = _patch_enrichment_internals()
    with patch_route, patch_thread:
        await router._enrich_with_routing(_make_message(), "whatsapp")

    router._touch_client_interaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_enrich_skips_touch_when_db_pool_unavailable():
    """No db_pool → the whole enrichment step (including the touch) no-ops."""
    router = ChannelRouter(MagicMock())
    router._db_pool = None
    router._touch_client_interaction = AsyncMock()

    await router._enrich_with_routing(_make_message(), "whatsapp")

    router._touch_client_interaction.assert_not_awaited()


# ---------------------------------------------------------------------------
# End-to-end failure isolation — the exact scenario a reviewer must be able
# to see proven: Postgres refuses the last_interaction_date UPDATE while the
# rest of the pipeline is healthy. A tracking write must never gate a reply.
# ---------------------------------------------------------------------------


def _make_delivery_tracking_adapter() -> tuple[AsyncMock, dict]:
    """Adapter whose stream_response records completion — the observable
    proxy for "the client received their reply"."""
    delivered = {"count": 0}
    adapter = AsyncMock()
    adapter.channel_name = "whatsapp"
    adapter.timeout = 30
    adapter.update_interval = 1
    adapter.supports_markdown = True
    adapter.supports_media = False
    adapter.max_message_length = 4096
    adapter.receive_message = AsyncMock(return_value=_make_message())

    async def _consume(channel_id, stream):
        async for _ in stream:
            pass
        delivered["count"] += 1

    adapter.stream_response = AsyncMock(side_effect=_consume)
    return adapter, delivered


def _make_answering_engine(text: str = "Il KITAS costa X — chiedi al team.") -> MagicMock:
    async def _stream(message, channel_config):
        yield ChannelResponse(text=text, metadata={"event_type": "answer"})

    engine = MagicMock()
    engine.process_message = _stream
    return engine


@pytest.mark.asyncio
async def test_message_still_delivered_when_last_interaction_write_fails():
    """Postgres is down FOR THE UPDATE ONLY (everything else on the pool
    still works, as a real outage rarely takes down every query uniformly).
    route_message must not raise, and the client must still get their reply.
    """
    adapter, delivered = _make_delivery_tracking_adapter()
    router = ChannelRouter(_make_answering_engine())
    router.register_adapter("whatsapp", adapter)

    async def _execute_side_effect(sql, *args, **kwargs):
        if "UPDATE clients" in sql and "last_interaction_date" in sql:
            raise RuntimeError("connection refused")
        return None

    db_pool = AsyncMock()
    db_pool.execute = AsyncMock(side_effect=_execute_side_effect)
    router._db_pool = db_pool
    router._resolve_client_id = AsyncMock(return_value=101)

    patch_route, patch_thread = _patch_enrichment_internals()
    with patch_route, patch_thread:
        # Must not raise — a raised exception here is exactly the "silenced
        # WhatsApp" failure mode the reviewer flagged.
        await router.route_message("whatsapp", {"some": "payload"})

    assert delivered["count"] == 1, "reply must stream even though the touch failed"
