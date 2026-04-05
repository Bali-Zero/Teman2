"""
Practice query helpers — eliminates duplicated JOIN patterns.

The `practices JOIN clients` pattern appears 18+ times in the codebase.
"""

from __future__ import annotations

from typing import Any

import asyncpg


async def get_practice_by_id(
    conn: asyncpg.Connection, practice_id: int
) -> dict[str, Any] | None:
    """Fetch a single practice with basic client info."""
    row = await conn.fetchrow(
        """
        SELECT p.*, c.full_name as client_name, c.email as client_email,
               c.assigned_to, c.phone
        FROM practices p
        JOIN clients c ON c.id = p.client_id
        WHERE p.id = $1 AND c.deleted_at IS NULL
        """,
        practice_id,
    )
    return dict(row) if row else None


async def get_practices_by_client(
    conn: asyncpg.Connection,
    client_id: int,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch practices for a client, optionally filtered by status."""
    if status:
        rows = await conn.fetch(
            """
            SELECT p.*, c.full_name as client_name
            FROM practices p
            JOIN clients c ON c.id = p.client_id
            WHERE p.client_id = $1 AND p.status = $2
            AND c.deleted_at IS NULL
            ORDER BY p.updated_at DESC
            LIMIT $3
            """,
            client_id,
            status,
            limit,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT p.*, c.full_name as client_name
            FROM practices p
            JOIN clients c ON c.id = p.client_id
            WHERE p.client_id = $1 AND c.deleted_at IS NULL
            ORDER BY p.updated_at DESC
            LIMIT $2
            """,
            client_id,
            limit,
        )
    return [dict(r) for r in rows]


async def get_practices_with_client(
    conn: asyncpg.Connection,
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Fetch practices with client info — the most common JOIN pattern (18x)."""
    base = """
        SELECT p.id, p.practice_type, p.status, p.expiry_date,
               p.created_at, p.updated_at,
               c.id as client_id, c.full_name as client_name,
               c.email as client_email, c.assigned_to
        FROM practices p
        JOIN clients c ON c.id = p.client_id
        WHERE c.deleted_at IS NULL
    """
    params: list[Any] = []
    idx = 1
    if status:
        base += f" AND p.status = ${idx}"
        params.append(status)
        idx += 1
    base += f" ORDER BY p.updated_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
    params.extend([limit, offset])
    rows = await conn.fetch(base, *params)
    return [dict(r) for r in rows]
