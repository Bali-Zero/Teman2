"""Federation Tools - Inter-node message bus for Super OpenClaw Federation."""

from typing import Literal, Optional


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def federation_send(
        to_node: str,
        body: str,
        subject: Optional[str] = None,
        message_type: Literal["message", "task", "escalation", "ack"] = "message",
        priority: Literal["low", "normal", "high", "urgent"] = "normal",
    ) -> dict:
        """
        Send a message to another federation node (or broadcast to all nodes).

        Available nodes: pro, air, krisna, damar, all

        Args:
            to_node: Target node ID ('pro', 'air', 'krisna', 'damar', 'all')
            body: Message content
            subject: Optional subject line
            message_type: 'message' (chat), 'task' (work item), 'escalation' (urgent), 'ack' (confirm)
            priority: Message priority level

        Returns:
            Sent message record with ID and timestamp.
        """
        return await _call(
            "/api/federation/send",
            method="POST",
            json={
                "to_node": to_node,
                "body": body,
                "subject": subject,
                "message_type": message_type,
                "priority": priority,
            },
        )

    @mcp.tool()
    async def federation_inbox(
        unread_only: bool = True,
        limit: int = 20,
    ) -> dict:
        """
        Get messages in this node's inbox (including broadcasts).

        Args:
            unread_only: If True, only show unread messages (default: True)
            limit: Max messages to return (max 100)

        Returns:
            List of federation messages with sender, subject, body, and timestamp.
        """
        return await _call_safe(
            f"/api/federation/inbox?unread_only={str(unread_only).lower()}&limit={limit}"
        )

    @mcp.tool()
    async def federation_mark_read(
        message_id: str,
    ) -> dict:
        """
        Mark a federation message as read.

        Args:
            message_id: UUID of the message to mark as read

        Returns:
            Confirmation of read status update.
        """
        return await _call(
            f"/api/federation/inbox/read/{message_id}",
            method="POST",
        )

    @mcp.tool()
    async def federation_status() -> dict:
        """
        Get federation overview — unread message counts per node.

        Returns:
            Dict with unread counts per node and broadcast unread count.
        """
        return await _call_safe("/api/federation/status")
