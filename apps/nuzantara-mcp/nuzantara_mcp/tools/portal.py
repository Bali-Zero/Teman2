"""Portal Tools - 6 tools for client-facing portal operations."""

from typing import Optional

from nuzantara_mcp.auth import require_role


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def get_portal_dashboard(client_id: str) -> dict:
        """
        Get the client portal dashboard overview.

        Args:
            client_id: UUID of the client

        Returns:
            Dashboard: active practices, pending documents, unread messages, recent activity.
        """
        return await _call(
            "/api/portal/dashboard", params={"client_id": client_id}
        )

    @mcp.tool()
    @require_role("visa_specialist")
    async def get_portal_visa_status(client_id: str) -> dict:
        """
        Get visa status with detailed timeline for a client.

        Args:
            client_id: UUID of the client

        Returns:
            Visa details: type, status, expiry date, timeline of processing steps.
        """
        return await _call(
            "/api/portal/visa", params={"client_id": client_id}
        )

    @mcp.tool()
    async def list_portal_messages(
        client_id: str, unread_only: bool = False, limit: int = 20
    ) -> dict:
        """
        List messages in client's portal inbox.

        Args:
            client_id: UUID of the client
            unread_only: Only show unread messages
            limit: Max messages to return

        Returns:
            List of messages with sender, subject, date, read_status.
        """
        params: dict = {"client_id": client_id, "limit": limit}
        if unread_only:
            params["unread_only"] = True
        return await _call("/api/portal/messages", params=params)

    @mcp.tool()
    async def send_portal_message(
        client_id: str, subject: str, body: str
    ) -> dict:
        """
        Send a message to a client through the portal.

        Args:
            client_id: UUID of the client
            subject: Message subject line
            body: Message body (supports markdown)

        Returns:
            Sent message record with delivery status.
        """
        return await _call(
            "/api/portal/messages",
            method="POST",
            json={"client_id": client_id, "subject": subject, "body": body},
        )

    @mcp.tool()
    async def list_portal_documents(
        client_id: str, category: Optional[str] = None
    ) -> dict:
        """
        List documents available to a client in their portal.

        Args:
            client_id: UUID of the client
            category: Filter by category (passport, visa, company, tax, legal, other)

        Returns:
            List of documents with name, category, upload_date, size, download_url.
        """
        params: dict = {"client_id": client_id}
        if category:
            params["category"] = category
        return await _call("/api/portal/documents", params=params)

    @mcp.tool()
    async def get_portal_timeline(client_id: str) -> dict:
        """
        Get the practice progress timeline visible to the client.

        Args:
            client_id: UUID of the client

        Returns:
            Timeline of practice milestones: step, status, date, description.
        """
        return await _call(
            "/api/portal/timeline", params={"client_id": client_id}
        )
