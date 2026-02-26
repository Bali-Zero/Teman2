"""
Notification Queries
====================
Database queries extracted from router to break circular imports.
The scheduler and router both need these — keeping them here avoids
scheduler -> router -> admin_router import chains.
"""

import logging
from datetime import datetime
from typing import Any

from .models import ClientInfo

logger = logging.getLogger(__name__)

# SQL shared between router and scheduler
_CLIENT_SELECT = """
    SELECT
        c.id,
        c.email,
        c.full_name,
        COALESCE(c.preferred_language, 'en') as preferred_language,
        c.assigned_to as team_leader_email,
        c.date_of_birth,
        c.passport_expiry,
        c.passport_number,
        v.expiry_date as visa_expiry,
        v.visa_type
    FROM clients c
    LEFT JOIN (
        SELECT DISTINCT ON (client_id)
            client_id, expiry_date, document_type as visa_type
        FROM client_documents
        WHERE document_category = 'immigration'
        AND expiry_date IS NOT NULL
        ORDER BY client_id, expiry_date DESC
    ) v ON v.client_id = c.id
"""


async def get_clients_from_db(
    pool: Any, client_id: int | None = None
) -> list[ClientInfo]:
    """Fetch active clients from database with passport/visa data."""
    async with pool.acquire() as conn:
        if client_id:
            rows = await conn.fetch(
                f"{_CLIENT_SELECT} WHERE c.id = $1 AND c.is_active = true",
                client_id,
            )
        else:
            rows = await conn.fetch(
                f"{_CLIENT_SELECT} WHERE c.is_active = true"
            )

    clients: list[ClientInfo] = []
    for row in rows:
        client_data = dict(row)
        for field in ("date_of_birth", "passport_expiry", "visa_expiry"):
            val = client_data.get(field)
            if val and isinstance(val, str):
                client_data[field] = datetime.fromisoformat(val)
        clients.append(ClientInfo(**client_data))

    return clients


async def get_client_email(pool: Any, client_id: int) -> str | None:
    """Get a single client's email by ID."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT email FROM clients WHERE id = $1",
            client_id,
        )
