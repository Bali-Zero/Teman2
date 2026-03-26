"""CRM Tools - 12 tools for client and practice management."""

from typing import Any, Optional


def register(mcp: Any, _call: Any, _call_safe: Any) -> None:
    @mcp.tool()
    async def list_clients(
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        List all CRM clients with optional filters.

        Args:
            status: Filter by status (active, inactive, prospect, archived)
            search: Search by name, email, or phone
            limit: Max results (default 50, max 200)
            offset: Pagination offset

        Returns:
            List of clients with id, name, email, phone, status, nationality, created_at.
        """
        params = {"limit": min(limit, 200), "offset": offset}
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        result = await _call("/api/crm/clients/", params=params)
        if isinstance(result, list):
            return {"clients": result, "count": len(result)}
        return result

    @mcp.tool()
    async def get_client(client_id: str) -> dict:
        """
        Get full details for a specific client.

        Args:
            client_id: UUID of the client

        Returns:
            Complete client record: personal info, practices, documents, interactions.
        """
        return await _call(f"/api/crm/clients/{client_id}")

    @mcp.tool()
    async def create_client(
        name: str,
        email: str,
        nationality: str,
        phone: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Create a new client in the CRM.

        Args:
            name: Full legal name
            email: Email address
            nationality: Country of citizenship (e.g. "Italian", "Australian")
            phone: Phone number with country code (e.g. "+62812345678")
            notes: Internal notes about the client

        Returns:
            Created client record with assigned UUID.
        """
        payload: dict = {"name": name, "email": email, "nationality": nationality}
        if phone:
            payload["phone"] = phone
        if notes:
            payload["notes"] = notes
        return await _call("/api/crm/clients/", method="POST", json=payload)

    @mcp.tool()
    async def update_client(client_id: str, updates: dict) -> dict:
        """
        Update a client's information.

        Args:
            client_id: UUID of the client
            updates: Dict of fields to update (name, email, phone, status, notes, nationality)

        Returns:
            Updated client record.
        """
        return await _call(f"/api/crm/clients/{client_id}", method="PUT", json=updates)

    @mcp.tool()
    async def get_client_stats() -> dict:
        """
        Get global CRM statistics.

        Returns:
            Total clients, active/inactive/prospect counts, nationality distribution,
            practices per status, revenue metrics.
        """
        return await _call("/api/crm/clients/stats/overview")

    @mcp.tool()
    async def list_practices(
        client_id: Optional[str] = None,
        status: Optional[str] = None,
        practice_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        List practices (visas, company setups, renewals, etc.).

        Args:
            client_id: Filter by client UUID
            status: Filter by status (active, pending, completed, renewal_needed, stalled)
            practice_type: Filter by type (kitas, kitap, pt_pma, pt_perorangan, npwp, etc.)
            limit: Max results (default 50)
            offset: Pagination offset

        Returns:
            List of practices with id, client, type, status, dates, documents.
        """
        params: dict = {"limit": min(limit, 200), "offset": offset}
        if client_id:
            params["client_id"] = client_id
        if status:
            params["status"] = status
        if practice_type:
            params["type"] = practice_type
        result = await _call("/api/crm/practices/", params=params)
        if isinstance(result, list):
            return {"practices": result, "count": len(result)}
        return result

    @mcp.tool()
    async def get_practice(practice_id: str) -> dict:
        """
        Get full details for a specific practice.

        Args:
            practice_id: UUID of the practice

        Returns:
            Practice record: type, status, client info, documents, timeline, costs.
        """
        return await _call(f"/api/crm/practices/{practice_id}")

    @mcp.tool()
    async def create_practice(
        client_id: str,
        practice_type: str,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Create a new practice for a client.

        Args:
            client_id: UUID of the client
            practice_type: Type of practice (kitas, kitap, pt_pma, pt_perorangan, npwp, imta, rptka)
            notes: Internal notes

        Returns:
            Created practice record with assigned UUID.
        """
        payload: dict = {"client_id": client_id, "type": practice_type}
        if notes:
            payload["notes"] = notes
        return await _call("/api/crm/practices/", method="POST", json=payload)

    @mcp.tool()
    async def update_practice_status(
        practice_id: str,
        status: str,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Update the status of a practice.

        Args:
            practice_id: UUID of the practice
            status: New status (active, pending, submitted, waiting_documents, completed, renewal_needed, stalled, archived)
            notes: Optional note explaining the status change

        Returns:
            Updated practice record.
        """
        payload: dict = {"status": status}
        if notes:
            payload["notes"] = notes
        return await _call(
            f"/api/crm/practices/{practice_id}", method="PATCH", json=payload
        )

    @mcp.tool()
    async def get_expiry_alerts(days_ahead: int = 90) -> dict:
        """
        Get document/visa/practice expiry alerts.

        Checks all active practices and documents for upcoming expirations.

        Args:
            days_ahead: How many days ahead to check (default 90)

        Returns:
            List of alerts: client, practice, document, expiry_date, days_remaining, severity.
        """
        result = await _call(
            "/api/crm/expiry-alerts",
            params={"days_ahead": days_ahead},
        )
        # Backend returns list directly — wrap for MCP compatibility
        if isinstance(result, list):
            return {"alerts": result, "count": len(result)}
        return result

    @mcp.tool()
    async def get_client_timeline(client_id: str, limit: int = 50) -> dict:
        """
        Get the full interaction timeline for a client.

        Shows all touchpoints: emails, calls, WhatsApp, meetings, document submissions.

        Args:
            client_id: Numeric ID of the client
            limit: Max interactions to return

        Returns:
            Chronological list of interactions with type, date, summary, sentiment.
        """
        return await _call(
            f"/api/crm/interactions/client/{client_id}/timeline",
            params={"limit": limit},
        )

    @mcp.tool()
    async def log_interaction(
        client_id: str,
        interaction_type: str,
        summary: str,
        channel: str = "internal",
    ) -> dict:
        """
        Log a new interaction with a client.

        Args:
            client_id: UUID of the client
            interaction_type: Type (call, email, whatsapp, meeting, note, document, system)
            summary: Brief description of the interaction
            channel: Communication channel used

        Returns:
            Created interaction record.
        """
        return await _call(
            "/api/crm/interactions",
            method="POST",
            json={
                "client_id": client_id,
                "type": interaction_type,
                "summary": summary,
                "channel": channel,
            },
        )
