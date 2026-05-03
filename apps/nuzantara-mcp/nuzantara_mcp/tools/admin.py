"""Admin Tools - 4 tools for team management and operations."""

from typing import Optional

from nuzantara_mcp.auth import require_role


def register(mcp, _call, _call_safe):
    @mcp.tool()
    @require_role("admin", "visa_specialist", "tax_consultant", "company_setup")
    async def clock_in(member_id: Optional[str] = None) -> dict:
        """
        Clock in a team member (start of work).

        Args:
            member_id: Team member UUID (current user if not specified)

        Returns:
            Clock-in record with timestamp, member info.
        """
        payload: dict = {}
        if member_id:
            payload["member_id"] = member_id
        return await _call(
            "/api/team-activity/clock-in", method="POST", json=payload
        )

    @mcp.tool()
    @require_role("admin", "visa_specialist", "tax_consultant", "company_setup")
    async def clock_out(member_id: Optional[str] = None) -> dict:
        """
        Clock out a team member (end of work).

        Args:
            member_id: Team member UUID (current user if not specified)

        Returns:
            Clock-out record with timestamp, hours worked today.
        """
        payload: dict = {}
        if member_id:
            payload["member_id"] = member_id
        return await _call(
            "/api/team-activity/clock-out", method="POST", json=payload
        )

    @mcp.tool()
    @require_role("admin")
    async def get_team_hours(period: str = "weekly") -> dict:
        """
        Get team working hours summary.

        Args:
            period: Period to summarize (daily, weekly, monthly)

        Returns:
            Per-member hours: total, average, overtime, attendance rate.
        """
        return await _call(
            f"/api/team-activity/hours/{period}"
        )

    @mcp.tool()
    @require_role("admin")
    async def get_admin_logs(limit: int = 50) -> dict:
        """
        Get admin activity audit logs.

        Args:
            limit: Max log entries to return

        Returns:
            Audit trail: who did what, when, on which entity, change details.
        """
        return await _call("/api/admin/logs", params={"limit": limit})
