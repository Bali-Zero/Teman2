"""Reply obligations are independent of message read receipts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg

_PENDING_QUERY = """
    SELECT c.id AS client_id, c.full_name AS client_name,
           COUNT(pm.id) AS pending_count, COUNT(*) OVER () AS total_pending
    FROM clients c
    JOIN portal_messages pm ON pm.client_id = c.id
    WHERE c.deleted_at IS NULL AND pm.direction = 'client_to_team'
      AND pm.is_system_generated = FALSE
      -- The historical profile-update writer used this non-email sentinel.
      AND COALESCE(pm.sent_by, '') <> 'portal'
      {assignment}
      AND NOT EXISTS (
          SELECT 1 FROM portal_messages reply
          WHERE reply.client_id = pm.client_id
            AND reply.direction = 'team_to_client'
            AND reply.is_system_generated = FALSE
            AND (reply.created_at, reply.id) > (pm.created_at, pm.id)
      )
    GROUP BY c.id, c.full_name
    ORDER BY MIN(pm.created_at), c.id
    LIMIT 10
"""


def pending_reply_query(assigned_filter: str | None) -> tuple[str, tuple[str, ...]]:
    """Keep the total and visible rows under the same assignment restriction."""
    assignment = "AND LOWER(c.assigned_to) = $1" if assigned_filter is not None else ""
    return _PENDING_QUERY.format(assignment=assignment), (
        () if assigned_filter is None else (assigned_filter,)
    )


async def get_pending_replies(
    conn: asyncpg.Connection, assigned_filter: str | None
) -> dict[str, Any]:
    query, params = pending_reply_query(assigned_filter)
    rows = await conn.fetch(query, *params)
    return {
        "total_pending": int(rows[0]["total_pending"]) if rows else 0,
        "pending_by_client": [
            {
                "client_id": row["client_id"],
                "client_name": row["client_name"],
                "pending_count": row["pending_count"],
            }
            for row in rows
        ],
    }
