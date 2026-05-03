"""Compliance Monitoring Tools - 4 tools for regulatory deadline tracking."""

from typing import Optional

from nuzantara_mcp.auth import require_role


def register(mcp, _call, _call_safe):
    @mcp.tool()
    @require_role("visa_specialist", "tax_consultant")
    async def track_compliance(
        client_id: str,
        compliance_type: str,
        title: str,
        description: str,
        deadline: str,
        estimated_cost: Optional[float] = None,
        required_documents: Optional[list[str]] = None,
    ) -> dict:
        """
        Track a compliance deadline with automatic alerts at 60/30/7 days.

        Creates a monitored compliance item that triggers notifications
        as the deadline approaches.

        Args:
            client_id: UUID of the client
            compliance_type: One of:
                - visa_expiry (KITAS, KITAP, passport)
                - tax_filing (SPT Tahunan, PPh, PPn)
                - license_renewal (IMTA, NIB, permits)
                - regulatory_change (law/regulation changes)
            title: Short title for the compliance item
            description: Detailed description
            deadline: Deadline date in YYYY-MM-DD format
            estimated_cost: Optional estimated renewal/filing cost
            required_documents: Optional list of required document names

        Returns:
            Created compliance item with alert schedule.
        """
        payload: dict = {
            "client_id": client_id,
            "compliance_type": compliance_type,
            "title": title,
            "description": description,
            "deadline": deadline,
        }
        if estimated_cost is not None:
            payload["estimated_cost"] = estimated_cost
        if required_documents:
            payload["required_documents"] = required_documents
        return await _call(
            "/api/agents/compliance/track", method="POST", json=payload
        )

    @mcp.tool()
    @require_role("visa_specialist", "tax_consultant")
    async def get_compliance_alerts(
        client_id: Optional[str] = None,
        severity: Optional[str] = None,
        auto_notify: bool = False,
    ) -> dict:
        """
        Get upcoming compliance alerts.

        Args:
            client_id: Optional filter by client UUID
            severity: Optional filter: CRITICAL, URGENT, WARNING, INFO
            auto_notify: If true, automatically send notifications for due items

        Returns:
            List of alerts with severity, days_remaining, required_action.
        """
        params: dict = {"auto_notify": str(auto_notify).lower()}
        if client_id:
            params["client_id"] = client_id
        if severity:
            params["severity"] = severity
        return await _call("/api/agents/compliance/alerts", params=params)

    @mcp.tool()
    @require_role("tax_consultant")
    async def get_client_compliance(client_id: str) -> dict:
        """
        Get all compliance items for a specific client.

        Returns every tracked deadline, renewal, and regulatory item
        for the client, ordered by urgency.

        Args:
            client_id: UUID of the client

        Returns:
            All compliance items: visa, tax, license, regulatory with status.
        """
        return await _call(f"/api/agents/compliance/client/{client_id}")

    @mcp.tool()
    @require_role("tax_consultant")
    async def get_compliance_summary() -> dict:
        """
        Get a system-wide compliance summary (critical alerts view).

        Returns CRITICAL-severity compliance alerts across all clients.
        Use get_compliance_alerts() with severity filter for other levels,
        or get_client_compliance() for per-client details.

        Returns:
            List of critical compliance alerts with severity, days_remaining, required_action.
        """
        return await _call(
            "/api/agents/compliance/alerts",
            params={"severity": "CRITICAL"},
        )
