"""
Portal Family Router.

Returns the authenticated client's family members from
`client_family_members`, split into adults/minors by date_of_birth.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/family", tags=["portal-family"])


def _is_adult(dob: date | None) -> bool:
    if not dob:
        return True  # default to adult when unknown; safer re: editability
    today = date.today()
    age = (
        today.year
        - dob.year
        - ((today.month, today.day) < (dob.month, dob.day))
    )
    return age >= 18


def _shape_member(row: asyncpg.Record) -> dict[str, Any]:
    dob = row["date_of_birth"]
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "relationship": row["relationship"],
        "date_of_birth": dob.isoformat() if dob else None,
        "is_adult": _is_adult(dob),
        "nationality": row["nationality"],
        "passport_number": row["passport_number"],
        "passport_expiry": row["passport_expiry"].isoformat()
        if row["passport_expiry"]
        else None,
        "visa_type": row["current_visa_type"],
        "visa_expiry": row["visa_expiry"].isoformat() if row["visa_expiry"] else None,
        "email": row["email"],
        "phone": row["phone"],
    }


@router.get("")
async def list_family(
    client: dict = Depends(get_current_client),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    client_id = client["client_id"]
    members: list[dict[str, Any]] = []
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                """
                SELECT id, full_name, relationship, date_of_birth,
                       nationality, passport_number, passport_expiry,
                       current_visa_type, visa_expiry, email, phone
                FROM client_family_members
                WHERE client_id = $1
                ORDER BY
                    CASE relationship
                        WHEN 'spouse' THEN 1
                        WHEN 'child'  THEN 2
                        ELSE 3
                    END,
                    full_name
                """,
                client_id,
            )
            members = [_shape_member(r) for r in rows]
        except Exception as e:
            logger.warning(f"family list fetch failed: {e}")
            members = []

    adults = [m for m in members if m["is_adult"]]
    minors = [m for m in members if not m["is_adult"]]
    return {"adults": adults, "minors": minors}
