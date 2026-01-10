"""
Team Management Router
Handles team member listing with visibility rules
"""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool

router = APIRouter(prefix="/api/team", tags=["team"])


class TeamMember(BaseModel):
    """Team member model"""

    email: str
    name: str
    full_name: str | None = None
    role: str | None = None
    department: str | None = None
    active: bool = True
    avatar: str | None = None


@router.get("/members", response_model=list[TeamMember])
async def get_team_members(
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get list of team members visible to the current user.

    Visibility rules:
    1. User-specific visibility rules (team_member_visibility_rules table)
    2. Department-based visibility (all users in same department)
    3. Board/Founders see everyone
    """
    user_email = current_user.get("email")

    if not user_email:
        raise HTTPException(status_code=401, detail="User email not found")

    async with pool.acquire() as conn:
        # Get current user's department
        user_dept = await conn.fetchval(
            "SELECT department FROM team_members WHERE email = $1", user_email
        )

        # Check if user has specific visibility rules
        visibility_rules = await conn.fetch(
            """SELECT visible_member_email
               FROM team_member_visibility_rules
               WHERE viewer_email = $1 AND active = TRUE""",
            user_email,
        )

        if visibility_rules:
            # User has specific visibility rules - use them
            visible_emails = [rule["visible_member_email"] for rule in visibility_rules]

            members = await conn.fetch(
                """SELECT email, name, full_name, role, department, active, avatar
                   FROM team_members
                   WHERE email = ANY($1::text[]) AND active = TRUE
                   ORDER BY name""",
                visible_emails,
            )
        elif user_dept in ["board", "founders"]:
            # Board and founders see everyone
            members = await conn.fetch(
                """SELECT email, name, full_name, role, department, active, avatar
                   FROM team_members
                   WHERE active = TRUE
                   ORDER BY name"""
            )
        else:
            # Default: see only members of same department
            members = await conn.fetch(
                """SELECT email, name, full_name, role, department, active, avatar
                   FROM team_members
                   WHERE department = $1 AND active = TRUE
                   ORDER BY name""",
                user_dept,
            )

        return [
            TeamMember(
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
