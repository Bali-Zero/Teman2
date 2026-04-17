"""
Portal Dashboard Summary Router.

V2 matter-first dashboard: 3 hero sections returned in a single call.
- `open_actions`: practices that need client input (missing docs or waiting status)
- `upcoming_deadlines`: visa/kitas expiries and practice expiry_date within 30 days
- `unread_messages`: count from portal_messages (team_to_client, read_at IS NULL)

Each data source is wrapped in try/except so a single missing table or column
degrades to an empty list / zero instead of 500-ing the whole dashboard.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/dashboard", tags=["portal-dashboard"])


async def _fetch_open_actions(conn: asyncpg.Connection, client_id: int) -> list[dict[str, Any]]:
    try:
        rows = await conn.fetch(
            """
            SELECT p.id, pt.name AS title, pt.code AS type,
                   p.missing_documents AS pending_from_client,
                   p.status, p.updated_at
            FROM practices p
            JOIN practice_types pt ON pt.id = p.practice_type_id
            WHERE p.client_id = $1
              AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
              AND p.status IN ('inquiry', 'in_progress', 'waiting_documents')
              AND (p.missing_documents IS NOT NULL
                   OR p.status = 'waiting_documents')
            ORDER BY p.updated_at DESC NULLS LAST
            LIMIT 10
            """,
            client_id,
        )
    except Exception as e:
        logger.warning(f"open_actions fetch failed: {e}")
        return []
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "type": r["type"],
            "pending_from_client": r["pending_from_client"],
            "status": r["status"],
        }
        for r in rows
    ]


async def _fetch_deadlines(conn: asyncpg.Connection, client_id: int) -> list[dict[str, Any]]:
    """Union visa expiry (from clients.visa_expiry) + practice expiry_date within 30 days."""
    deadlines: list[dict[str, Any]] = []

    # Client-level visa expiry
    try:
        row = await conn.fetchrow(
            """
            SELECT id, visa_expiry, passport_expiry
            FROM clients WHERE id = $1
            """,
            client_id,
        )
        if row:
            if row["visa_expiry"]:
                deadlines.append(
                    {
                        "id": f"visa-{row['id']}",
                        "label": "Visa expiry",
                        "due_date": row["visa_expiry"].isoformat(),
                        "kind": "visa",
                    }
                )
            if row["passport_expiry"]:
                deadlines.append(
                    {
                        "id": f"passport-{row['id']}",
                        "label": "Passport expiry",
                        "due_date": row["passport_expiry"].isoformat(),
                        "kind": "passport",
                    }
                )
    except Exception as e:
        logger.warning(f"client expiry fetch failed: {e}")

    # Practice-level expiry (next 30 days)
    try:
        rows = await conn.fetch(
            """
            SELECT p.id, pt.name AS label, p.expiry_date, pt.category AS kind
            FROM practices p
            JOIN practice_types pt ON pt.id = p.practice_type_id
            WHERE p.client_id = $1
              AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
              AND p.expiry_date IS NOT NULL
              AND p.expiry_date > NOW()
              AND p.expiry_date < NOW() + INTERVAL '30 days'
            ORDER BY p.expiry_date ASC
            LIMIT 10
            """,
            client_id,
        )
        for r in rows:
            deadlines.append(
                {
                    "id": f"practice-{r['id']}",
                    "label": r["label"],
                    "due_date": r["expiry_date"].isoformat() if r["expiry_date"] else None,
                    "kind": r["kind"],
                }
            )
    except Exception as e:
        logger.warning(f"practice expiry fetch failed: {e}")

    deadlines.sort(key=lambda d: d["due_date"] or "9999")
    return deadlines[:10]


async def _fetch_unread_count(conn: asyncpg.Connection, client_id: int) -> int:
    try:
        n = await conn.fetchval(
            """
            SELECT COUNT(*) FROM portal_messages
            WHERE client_id = $1
              AND direction = 'team_to_client'
              AND read_at IS NULL
            """,
            client_id,
        )
        return int(n or 0)
    except Exception as e:
        logger.warning(f"unread count fetch failed: {e}")
        return 0


@router.get("/summary")
async def summary(
    client: dict = Depends(get_current_client),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Return 3-hero-card data in a single round-trip."""
    client_id = client["client_id"]
    async with pool.acquire() as conn:
        open_actions = await _fetch_open_actions(conn, client_id)
        deadlines = await _fetch_deadlines(conn, client_id)
        unread = await _fetch_unread_count(conn, client_id)

    return {
        "open_actions": open_actions,
        "upcoming_deadlines": deadlines,
        "unread_messages": unread,
    }
