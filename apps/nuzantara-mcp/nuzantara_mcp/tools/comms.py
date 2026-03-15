"""Communication Tools - 6 tools for email, WhatsApp, and Telegram."""

from typing import Optional


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def send_email(
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
    ) -> dict:
        """
        Send an email via Zoho Mail integration.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (supports HTML)
            cc: CC recipients (comma-separated)

        Returns:
            Send status with message ID.
        """
        payload: dict = {"to": to, "subject": subject, "body": body}
        if cc:
            payload["cc"] = cc
        return await _call("/api/zoho/emails", method="POST", json=payload)

    @mcp.tool()
    async def list_emails(
        folder: str = "inbox",
        limit: int = 20,
        unread_only: bool = False,
    ) -> dict:
        """
        List emails from Zoho Mail.

        Args:
            folder: Mail folder (inbox, sent, drafts, trash)
            limit: Max emails to return
            unread_only: Only return unread emails

        Returns:
            List of emails with from, subject, date, snippet, read_status.
        """
        params: dict = {"folder": folder, "limit": limit}
        if unread_only:
            params["unread_only"] = True
        return await _call("/api/zoho/emails", params=params)

    @mcp.tool()
    async def search_emails(query: str, limit: int = 10) -> dict:
        """
        Search emails by keyword.

        Args:
            query: Search query (searches subject, body, sender)
            limit: Max results

        Returns:
            Matching emails ranked by relevance.
        """
        return await _call(
            "/api/zoho/emails/search", params={"query": query, "limit": limit}
        )

    @mcp.tool()
    async def send_whatsapp(phone: str, message: str) -> dict:
        """
        Send a WhatsApp message via Meta WhatsApp Cloud API.

        Args:
            phone: Recipient phone number with country code (e.g. "+62812345678")
            message: Message text (max 4096 chars)

        Returns:
            Delivery status from Meta API.

        Note:
            Requires auth. Rate limited to 20 msgs/phone/hour.
            Recipient must exist in CRM clients table.
        """
        return await _call(
            "/api/whatsapp/send",
            method="POST",
            json={"phone": phone, "message": message},
        )

    @mcp.tool()
    async def list_whatsapp_conversations(limit: int = 20) -> dict:
        """
        List recent WhatsApp conversations.

        Args:
            limit: Max conversations to return

        Returns:
            List of conversations with contact, last_message, timestamp, unread_count.
        """
        return await _call(
            "/api/whatsapp/conversations", params={"limit": limit}
        )

    @mcp.tool()
    async def list_telegram_conversations(limit: int = 20) -> dict:
        """
        List recent Telegram conversations.

        Args:
            limit: Max conversations to return

        Returns:
            List of conversations with contact, last_message, timestamp.
        """
        return await _call(
            "/api/telegram/conversations", params={"limit": limit}
        )
