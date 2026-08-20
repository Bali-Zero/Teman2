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

from backend.channels.base import ChannelMessage
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
