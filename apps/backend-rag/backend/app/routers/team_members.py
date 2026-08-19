"""Team members endpoint — returns active team members for dropdowns and assignments."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.service_accounts import NON_HUMAN_ROLES_SQL

router = APIRouter(prefix="/api/team", tags=["team"])


@router.get("/members")
async def list_team_members(
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """List active team members. Used by CRM dropdowns for assignment."""
    async with pool.acquire() as conn:
        # Service accounts are excluded alongside clients: this list populates the
        # CRM assignment dropdown, and a client must never be assignable to an
        # unattended machine.
        rows = await conn.fetch(
            f"""
            SELECT email, full_name, role, avatar_url
            FROM team_members
            WHERE active = true AND role NOT IN ({NON_HUMAN_ROLES_SQL})
            ORDER BY full_name
            """
        )
        return {
            "members": [
                {
                    "email": r["email"],
                    "full_name": r["full_name"],
                    "role": r["role"],
                    "avatar_url": r.get("avatar_url"),
                }
                for r in rows
            ]
        }
