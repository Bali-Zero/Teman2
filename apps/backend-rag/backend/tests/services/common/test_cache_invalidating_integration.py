"""Integration tests for @cache_invalidating applied to real service methods.

These exercise the full decorator wiring on three representative production
methods:

- EnhancedCRMService.create_client        — CRM mutation, multi-namespace fanout
- EnhancedCRMService.update_practice_status — entity-scoped + namespace wildcard
- PortalMessagingMixin.mark_message_read  — tiny portal mutation, single pattern

Each test uses an in-memory CacheService instance (Redis absent → LRU fallback)
and seeds some cache keys that should be wiped after the mutation succeeds.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.cache import CacheService


@pytest.fixture
def in_memory_cache() -> CacheService:
    """Fresh CacheService backed by the in-memory LRU (no Redis)."""
    svc = CacheService()
    # Force Redis-unavailable path — rely on LRU.
    svc._redis_checked = True
    svc.redis_available = False
    svc.redis_client = None
    return svc


async def _seed(cache: CacheService, *keys: str) -> None:
    for k in keys:
        await cache.set(k, {"seeded": True}, ttl=60)
    for k in keys:
        assert await cache.get(k) is not None, f"seed failed for {k}"


async def _assert_cleared(cache: CacheService, *keys: str) -> None:
    for k in keys:
        assert await cache.get(k) is None, f"{k} should have been invalidated"


# ── 1. create_client fans out to both stats + list namespaces ──────────────

@pytest.mark.asyncio
async def test_create_client_invalidates_crm_namespaces(in_memory_cache: CacheService) -> None:
    from backend.services.crm import client_core as cc_mod

    await _seed(
        in_memory_cache,
        "zantara:crm_clients_stats:all",
        "zantara:crm_clients:list:page1",
    )

    # Build a minimal EnhancedCRMService without touching real asyncpg.
    svc = cc_mod.EnhancedCRMService.__new__(cc_mod.EnhancedCRMService)
    svc.db_pool = MagicMock()
    svc._find_duplicate_client = AsyncMock(return_value=None)
    svc.auditor = MagicMock()
    svc.auditor.log_client_created = AsyncMock()

    # Fake asyncpg connection: fetchrow returns a dict-like row.
    fake_row = {"id": 1337, "full_name": "Zero Test", "email": "zero@balizero.com"}
    fake_conn = MagicMock()
    fake_conn.fetchrow = AsyncMock(return_value=fake_row)

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=fake_conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    svc.db_pool.acquire = MagicMock(return_value=acquire_ctx)

    with patch(
        "backend.services.common.cache._invalidate_cache",
        side_effect=in_memory_cache.clear_pattern,
    ):
        result = await svc.create_client(
            {"full_name": "Zero Test", "email": "zero@balizero.com"},
            user_id="zero@balizero.com",
        )

    assert result["id"] == 1337
    await _assert_cleared(
        in_memory_cache,
        "zantara:crm_clients_stats:all",
        "zantara:crm_clients:list:page1",
    )


# ── 2. update_practice_status targets per-practice + namespace ─────────────

@pytest.mark.asyncio
async def test_update_practice_status_invalidates_per_practice(
    in_memory_cache: CacheService,
) -> None:
    from backend.services.crm import client_core as cc_mod

    await _seed(
        in_memory_cache,
        "zantara:crm_practice:99:detail",
        "zantara:crm_practices:list",
        # unrelated key must survive
        "zantara:unrelated:x",
    )

    svc = cc_mod.EnhancedCRMService.__new__(cc_mod.EnhancedCRMService)
    svc.db_pool = MagicMock()
    svc.auditor = MagicMock()
    svc.auditor.log_practice_status_change = AsyncMock()
    svc._create_hr_bonus_entry = AsyncMock()

    fake_conn = MagicMock()
    fake_conn.fetchrow = AsyncMock(
        side_effect=[
            {"status": "open", "client_id": 1},  # old
            {"id": 99, "status": "in_progress", "client_id": 1},  # updated
        ],
    )

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=fake_conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    svc.db_pool.acquire = MagicMock(return_value=acquire_ctx)

    with patch(
        "backend.services.common.cache._invalidate_cache",
        side_effect=in_memory_cache.clear_pattern,
    ):
        result = await svc.update_practice_status(99, "in_progress", user_id="asya@balizero.com")

    assert result["id"] == 99
    await _assert_cleared(
        in_memory_cache,
        "zantara:crm_practice:99:detail",
        "zantara:crm_practices:list",
    )
    # The unrelated key must still be present.
    assert await in_memory_cache.get("zantara:unrelated:x") == {"seeded": True}


# ── 3. mark_message_read clears only the portal_messages namespace ─────────

@pytest.mark.asyncio
async def test_mark_message_read_invalidates_portal_messages(
    in_memory_cache: CacheService,
) -> None:
    from backend.services.portal._mixins.messaging import PortalMessagingMixin

    await _seed(
        in_memory_cache,
        "zantara:portal_messages:42:inbox",
        "zantara:portal_messages:42:unread_count",
    )

    class _Mixin(PortalMessagingMixin):
        pass

    svc = _Mixin()
    fake_conn = MagicMock()
    fake_conn.execute = AsyncMock(return_value="UPDATE 1")
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=fake_conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    svc.pool = MagicMock()
    svc.pool.acquire = MagicMock(return_value=acquire_ctx)

    with patch(
        "backend.services.common.cache._invalidate_cache",
        side_effect=in_memory_cache.clear_pattern,
    ):
        result = await svc.mark_message_read(
            client_id=42, message_id=777,
            current_user={"client_id": 42, "email": "test@example.com"},
        )

    assert result == {"success": True}
    await _assert_cleared(
        in_memory_cache,
        "zantara:portal_messages:42:inbox",
        "zantara:portal_messages:42:unread_count",
    )
