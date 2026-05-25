"""CRM Guardian Drive intelligence tools.

These tools expose read-only CRM Guardian evidence state through the backend.
They do not call Google Drive directly and do not mutate Drive or CRM rows.
"""

from typing import Any, Optional


def register(mcp: Any, _call: Any, _call_safe: Any) -> None:
    @mcp.tool()
    async def crm_guardian_drive_validation_summary() -> dict:
        """
        Summarize CRM Guardian Drive metadata validation.

        Returns:
            Counts by validation status, owner domain, and MIME type.
        """
        return await _call("/api/crm-guardian/drive/validation-summary")

    @mcp.tool()
    async def crm_guardian_find_external_owner_risks(limit: int = 50) -> dict:
        """
        List valid Drive anchors that need external-owner migration review.

        Args:
            limit: Max rows to return, capped by backend at 500.

        Returns:
            Open external-owner backlog rows.
        """
        rows = await _call(
            "/api/crm-guardian/drive/external-owner-risks",
            params={"limit": limit},
        )
        return {"items": rows, "count": len(rows) if isinstance(rows, list) else None}

    @mcp.tool()
    async def crm_guardian_find_stale_drive_links(limit: int = 50) -> dict:
        """
        List DB-linked Drive IDs that failed direct metadata validation.

        Args:
            limit: Max rows to return, capped by backend at 500.

        Returns:
            Stale/inaccessible candidate rows. These are review candidates,
            not automatic delete instructions.
        """
        rows = await _call(
            "/api/crm-guardian/drive/stale-link-candidates",
            params={"limit": limit},
        )
        return {"items": rows, "count": len(rows) if isinstance(rows, list) else None}

    @mcp.tool()
    async def crm_guardian_find_unlinked_drive_items(limit: int = 50) -> dict:
        """
        List visible CRM-relevant Drive items not yet matched to CRM entities.

        Args:
            limit: Max rows to return, capped by backend at 500.

        Returns:
            Unlinked Drive item backlog rows.
        """
        rows = await _call(
            "/api/crm-guardian/drive/unlinked-items",
            params={"limit": limit},
        )
        return {"items": rows, "count": len(rows) if isinstance(rows, list) else None}

    @mcp.tool()
    async def crm_guardian_shortcut_resolution_status(
        status: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """
        List shortcut target edges for Canonical migration planning.

        Args:
            status: Optional resolution_status filter.
            limit: Max rows to return, capped by backend at 500.

        Returns:
            Shortcut edge rows with source and target IDs.
        """
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        rows = await _call("/api/crm-guardian/drive/shortcut-edges", params=params)
        return {"items": rows, "count": len(rows) if isinstance(rows, list) else None}
