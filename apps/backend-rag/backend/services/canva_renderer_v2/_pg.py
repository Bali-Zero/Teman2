"""PostgreSQL layer for canva_renderer_v2.

Functions:
- is_kill_switch_enabled(conn) — reads system_settings.wr2_canva_renderer_enabled
- fetch_pending_draft_ids(conn, limit) — pre-scan IDs to attempt lease
- acquire_lease_and_fetch(conn, draft_id, lease_owner) — CAS, returns row or None
- inject_hero_paths(conn, draft_id, slides_json) — write hero_image_path into slides_json before cron
- persist_canva_result(conn, ...) — UPDATE status='rendered' + canva_* + clear lease
- release_lease_transient(conn, ...) — revert status='drafts_imaged_checked'
- release_lease_permanent(conn, ..., status=...) — set terminal status
- reset_stale_leases(conn, stale_after_minutes) — watchdog recovery
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


async def is_kill_switch_enabled(conn: asyncpg.Connection) -> bool:
    value = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'wr2_canva_renderer_enabled'"
    )
    return value == "true"


async def fetch_pending_draft_ids(
    conn: asyncpg.Connection, limit: int = 3
) -> list[UUID]:
    rows = await conn.fetch(
        """
        SELECT id FROM war_room_drafts
         WHERE status = 'drafts_imaged_checked'
           AND canva_edit_url IS NULL
           AND lease_owner IS NULL
         ORDER BY created_at ASC
         LIMIT $1
        """,
        limit,
    )
    return [r["id"] for r in rows]


async def acquire_lease_and_fetch(
    conn: asyncpg.Connection, *, draft_id: UUID | str, lease_owner: str,
) -> dict[str, Any] | None:
    """CAS lease + return row payload, or None if another process won."""
    row = await conn.fetchrow(
        """
        UPDATE war_room_drafts
           SET status = 'rendering',
               lease_owner = $1,
               lease_acquired_at = NOW(),
               updated_at = NOW()
         WHERE id = $2
           AND status = 'drafts_imaged_checked'
           AND canva_edit_url IS NULL
           AND lease_owner IS NULL
        RETURNING id, topic, register AS tone, slides_json
        """,
        lease_owner, draft_id,
    )
    if row is None:
        logger.info("Draft %s lease lost to another process", draft_id)
    return dict(row) if row else None


async def inject_hero_paths(
    conn: asyncpg.Connection, *,
    draft_id: UUID | str,
    slides_json: dict[str, Any],
) -> None:
    """Write slides_json (with hero_image_path on each is_hero_image slide) to PG.

    Called by wr2-design-architect after Codex imagegen completes for ALL hero
    slides, BEFORE setting status='drafts_imaged_checked'. The orchestrator cron
    reads slides_json at render time — hero_image_path must be present then.

    Idempotent: safe to call multiple times (last write wins).
    """
    import json as _json
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET slides_json = $2::jsonb,
               updated_at = NOW()
         WHERE id = $1
           AND status NOT IN ('rendering', 'rendered')
        """,
        draft_id, _json.dumps(slides_json),
    )
    logger.info("Draft %s slides_json updated with hero_image_path fields", draft_id)


async def persist_canva_result(
    conn: asyncpg.Connection, *,
    draft_id: UUID | str,
    canva_design_id: str,
    canva_edit_url: str,
    canva_view_url: str | None,
) -> None:
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET canva_design_id = $2,
               canva_edit_url = $3,
               canva_view_url = $4,
               canva_applied_at = NOW(),
               status = 'rendered',
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE id = $1
        """,
        draft_id, canva_design_id, canva_edit_url, canva_view_url,
    )


async def release_lease_transient(
    conn: asyncpg.Connection, *, draft_id: UUID | str, reason: str,
) -> None:
    """Revert to drafts_imaged_checked for natural retry on next tick."""
    logger.info("Draft %s released as transient: %s", draft_id, reason)
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET status = 'drafts_imaged_checked',
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE id = $1
        """,
        draft_id,
    )


async def release_lease_permanent(
    conn: asyncpg.Connection, *, draft_id: UUID | str, status: str, reason: str,
) -> None:
    """Mark terminal failure status. Not picked up by next tick."""
    logger.warning("Draft %s permanent failure (%s): %s", draft_id, status, reason)
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET status = $2,
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE id = $1
        """,
        draft_id, status,
    )


async def reset_stale_leases(
    conn: asyncpg.Connection, *, stale_after_minutes: int = 15,
) -> list[UUID]:
    """Watchdog: revert status='rendering' rows with old lease_acquired_at."""
    rows = await conn.fetch(
        """
        UPDATE war_room_drafts
           SET status = 'drafts_imaged_checked',
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE status = 'rendering'
           AND lease_acquired_at < NOW() - ($1 || ' minutes')::interval
        RETURNING id
        """,
        str(stale_after_minutes),
    )
    return [r["id"] for r in rows]
