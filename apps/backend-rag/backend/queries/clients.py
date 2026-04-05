"""
Client query helpers — eliminates 6x duplicated SELECT patterns.

Each function takes an asyncpg connection and returns typed results.
Prefer these over inline SQL in routers.
"""

from __future__ import annotations

from typing import Any

import asyncpg


async def get_client_by_id(
    conn: asyncpg.Connection, client_id: int
) -> dict[str, Any] | None:
    """Fetch a single client by ID (soft-delete aware)."""
    row = await conn.fetchrow(
        "SELECT * FROM clients WHERE id = $1 AND deleted_at IS NULL",
        client_id,
    )
    return dict(row) if row else None


async def get_client_assigned_to(
    conn: asyncpg.Connection, client_id: int
) -> str | None:
    """Get the assigned_to email for a client. Used 6x across CRM routers."""
    return await conn.fetchval(
        "SELECT assigned_to FROM clients WHERE id = $1 AND deleted_at IS NULL",
        client_id,
    )


async def get_client_email(
    conn: asyncpg.Connection, client_id: int
) -> str | None:
    """Get client email. Used 6x across notification/portal services."""
    return await conn.fetchval(
        "SELECT email FROM clients WHERE id = $1 AND deleted_at IS NULL",
        client_id,
    )


async def verify_client_access(
    conn: asyncpg.Connection,
    client_id: int,
    user_email: str,
    is_admin: bool = False,
) -> bool:
    """
    Verify user has access to a client record.

    Admin users always have access. Non-admin users must be assigned_to.
    Returns True if access granted, False otherwise.
    """
    if is_admin:
        return True
    assigned = await get_client_assigned_to(conn, client_id)
    return assigned == user_email if assigned else False


async def get_client_drive_folder(
    conn: asyncpg.Connection, client_id: int
) -> str | None:
    """Get Google Drive folder_id for a client."""
    return await conn.fetchval(
        "SELECT drive_folder_id FROM clients WHERE id = $1 AND deleted_at IS NULL",
        client_id,
    )
