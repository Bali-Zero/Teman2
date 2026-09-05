"""
Team Management Router
Handles team member listing with visibility rules
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.dependencies import get_database_pool, require_team_member
from backend.app.utils.service_accounts import non_human_roles_sql_array

router = APIRouter(prefix="/api/team", tags=["team"])


class TeamMember(BaseModel):
    """Team member model"""

    id: str | None = None
    email: str
    name: str
    full_name: str | None = None
    role: str | None = None
    department: str | None = None
    active: bool = True
    avatar: str | None = None


@router.get("/members", response_model=list[TeamMember])
async def get_team_members(
    current_user: dict = Depends(require_team_member),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> list[Any]:
    """
    Get list of team members visible to the current user.

    Access: team members only (``require_team_member``). Clients, service
    accounts and external partners get 403 — no partner-portal page consumes
    this roster (it is the staff workspace's people list), so a partner JWT
    previously received 200 with an empty or department-scoped list, which
    answered "what does the team look like" to a caller who is not on it.

    Visibility rules:
    1. User-specific visibility rules (team_member_visibility_rules table)
    2. Department-based visibility (all users in same department)
    3. Board/Founders see everyone
    """
    user_email = current_user.get("email")

    if not user_email:
        raise HTTPException(status_code=401, detail="User email not found")

    async with pool.acquire() as conn:
        # Get current user's department and role
        user_row = await conn.fetchrow(
            "SELECT department, role FROM team_members WHERE email = $1",
            user_email,
        )
        user_dept = user_row["department"] if user_row else None
        user_role = (user_row["role"] or "").lower() if user_row else ""

        # Check if user has specific visibility rules
        visibility_rules = await conn.fetch(
            """SELECT visible_member_email
               FROM team_member_visibility_rules
               WHERE viewer_email = $1 AND active = TRUE""",
            user_email,
        )

        # Service accounts (e.g. the login-healthcheck probe, role "monitoring")
        # are excluded alongside clients on every branch below: this is the
        # human-facing team roster, not an access gate — see service_accounts.py.
        if visibility_rules:
            # User has specific visibility rules - use them
            visible_emails = [rule["visible_member_email"] for rule in visibility_rules]

            members = await conn.fetch(
                """SELECT id, email, name, full_name, role, department, active, avatar
                   FROM team_members
                   WHERE email = ANY($1::text[]) AND active = TRUE
                     AND role <> ALL($2::text[])
                   ORDER BY name""",
                visible_emails,
                non_human_roles_sql_array(),
            )
        elif user_dept in ["board", "founders", "management"] or user_role in (
            "founder",
            "ceo",
            "board member",
            "admin",
        ):
            # Board, founders, management, and leadership roles see everyone
            members = await conn.fetch(
                """SELECT id, email, name, full_name, role, department, active, avatar
                   FROM team_members
                   WHERE active = TRUE
                     AND role <> ALL($1::text[])
                   ORDER BY name""",
                non_human_roles_sql_array(),
            )
        else:
            # Default: see only members of same department
            members = await conn.fetch(
                """SELECT id, email, name, full_name, role, department, active, avatar
                   FROM team_members
                   WHERE department = $1 AND active = TRUE
                     AND role <> ALL($2::text[])
                   ORDER BY name""",
                user_dept,
                non_human_roles_sql_array(),
            )

        return [
            TeamMember(
                id=m["id"],
                email=m["email"],
                name=m["name"],
                full_name=m["full_name"],
                role=m["role"],
                department=m["department"],
                active=m["active"],
                avatar=m["avatar"],
            )
            for m in members
        ]
