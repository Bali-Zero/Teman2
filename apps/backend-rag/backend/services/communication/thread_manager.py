"""Thread Manager — cross-channel conversation grouping and lifecycle.

Groups messages into threads by client identity, manages thread status
(open → assigned → waiting → resolved → closed), and provides the data
layer for the unified inbox API.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from backend.services.communication.models import (
    Priority,
    ThreadFilter,
    ThreadMessage,
    ThreadStatus,
)

logger = logging.getLogger(__name__)


class ThreadManager:
    """Manages conversation threads across all channels."""

    def __init__(self, db_pool: Any) -> None:
        self._db = db_pool

    async def get_or_create_thread(
        self,
        client_id: int | None,
        channel: str,
        *,
        sender_id: str | None = None,
        subject: str | None = None,
    ) -> UUID:
        """Find open thread for client or create new one.

        Args:
            client_id: CRM client ID (None for unidentified senders).
            channel: Channel name (whatsapp, telegram, etc.).
            sender_id: Raw sender ID for unidentified users.
            subject: Optional subject for new threads.

        Returns:
            Thread UUID.
        """
        # Use INSERT ... ON CONFLICT pattern to avoid race conditions
        # when two messages from the same client arrive simultaneously.
        if client_id:
            # Try to find or atomically create thread for this client
            thread_id = await self._db.fetchval(
                """
                SELECT id FROM conversation_threads
                WHERE client_id = $1 AND status IN ('open', 'assigned', 'waiting')
                ORDER BY last_activity_at DESC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """,
                client_id,
            )
            if thread_id:
                # Update channels array if new channel
                await self._db.execute(
                    """
                    UPDATE conversation_threads
                    SET channels = CASE WHEN $2 = ANY(channels) THEN channels
                                        ELSE array_append(channels, $2) END,
                        last_activity_at = NOW()
                    WHERE id = $1
                    """,
                    thread_id,
                    channel,
                )
                return thread_id

        # Try by sender_id for unidentified users
        if not client_id and sender_id:
            thread_id = await self._db.fetchval(
                """
                SELECT id FROM conversation_threads
                WHERE metadata->>'sender_id' = $1
                  AND status IN ('open', 'assigned', 'waiting')
                ORDER BY last_activity_at DESC
                LIMIT 1
                """,
                sender_id,
            )
            if thread_id:
                return thread_id

        # Create new thread
        metadata: dict[str, Any] = {}
        if sender_id and not client_id:
            metadata["sender_id"] = sender_id

        thread_id = await self._db.fetchval(
            """
            INSERT INTO conversation_threads
                (client_id, channels, subject, metadata)
            VALUES ($1, $2, $3, $4::jsonb)
            RETURNING id
            """,
            client_id,
            [channel],
            subject,
            json.dumps(metadata),
        )
        logger.info(f"Created thread {thread_id} for client_id={client_id} channel={channel}")
        return thread_id

    async def add_message_to_thread(
        self,
        thread_id: UUID,
        message_id: int,
        channel: str,
        *,
        preview: str | None = None,
        direction: str = "inbound",
    ) -> None:
        """Link message to thread and update thread metadata.

        Args:
            thread_id: Thread UUID.
            message_id: conversation_messages.id.
            channel: Channel name.
            preview: Message preview text.
            direction: 'inbound' or 'outbound'.
        """
        # Update message's thread_id
        await self._db.execute(
            "UPDATE conversation_messages SET thread_id = $1 WHERE id = $2",
            thread_id, message_id,
        )

        # Update thread metadata
        update_parts = [
            "last_activity_at = NOW()",
            "channels = CASE WHEN $2 = ANY(channels) THEN channels ELSE array_append(channels, $2) END",
        ]
        params: list[Any] = [thread_id, channel]

        if preview:
            update_parts.append(f"last_message_preview = ${len(params) + 1}")
            params.append(preview[:200])

        if direction == "inbound":
            update_parts.append("unread_count = unread_count + 1")

        await self._db.execute(
            f"UPDATE conversation_threads SET {', '.join(update_parts)} WHERE id = $1",
            *params,
        )

    async def assign_thread(self, thread_id: UUID, email: str) -> None:
        """Assign thread to a team member."""
        await self._db.execute(
            """
            UPDATE conversation_threads
            SET assigned_to = $2, status = 'assigned', last_activity_at = NOW()
            WHERE id = $1
            """,
            thread_id, email,
        )
        logger.info(f"Thread {thread_id} assigned to {email}")

    async def resolve_thread(self, thread_id: UUID) -> None:
        """Mark thread as resolved."""
        await self._db.execute(
            """
            UPDATE conversation_threads
            SET status = 'resolved', resolved_at = NOW(), last_activity_at = NOW()
            WHERE id = $1
            """,
            thread_id,
        )
        logger.info(f"Thread {thread_id} resolved")

    async def update_thread(
        self,
        thread_id: UUID,
        *,
        status: ThreadStatus | None = None,
        priority: Priority | None = None,
        assigned_to: str | None = None,
    ) -> bool:
        """Update thread fields. Returns True if thread exists."""
        updates: list[str] = []
        params: list[Any] = [thread_id]

        if status is not None:
            params.append(status.value)
            updates.append(f"status = ${len(params)}")
            if status == ThreadStatus.RESOLVED:
                updates.append("resolved_at = NOW()")
        if priority is not None:
            params.append(priority.value)
            updates.append(f"priority = ${len(params)}")
        if assigned_to is not None:
            params.append(assigned_to)
            updates.append(f"assigned_to = ${len(params)}")

        if not updates:
            return True

        updates.append("last_activity_at = NOW()")
        result = await self._db.execute(
            f"UPDATE conversation_threads SET {', '.join(updates)} WHERE id = $1",
            *params,
        )
        return "UPDATE 1" in (result or "")

    async def mark_read(self, thread_id: UUID) -> None:
        """Reset unread count for a thread."""
        await self._db.execute(
            "UPDATE conversation_threads SET unread_count = 0 WHERE id = $1",
            thread_id,
        )

    async def get_thread_messages(
        self, thread_id: UUID, *, limit: int = 50, offset: int = 0,
    ) -> list[ThreadMessage]:
        """Get messages for a thread, ordered chronologically."""
        rows = await self._db.fetch(
            """
            SELECT id, channel, direction, sender_id, content, metadata, created_at
            FROM conversation_messages
            WHERE thread_id = $1
            ORDER BY created_at ASC
            LIMIT $2 OFFSET $3
            """,
            thread_id, limit, offset,
        )

        messages = []
        for row in rows:
            meta = row["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
            messages.append(ThreadMessage(
                id=row["id"],
                channel=row["channel"],
                direction=row["direction"],
                sender_id=row["sender_id"],
                content=row["content"],
                metadata=meta or {},
                created_at=row["created_at"].isoformat() if row["created_at"] else "",
            ))
        return messages

    async def get_threads(self, filters: ThreadFilter, *, user_email: str | None = None, is_admin: bool = False) -> tuple[list[dict[str, Any]], int]:
        """List threads with filters. Returns (threads, total_count).

        Args:
            filters: Filter parameters.
            user_email: Current user email (for RBAC).
            is_admin: Whether user is admin (sees all threads).
        """
        conditions: list[str] = []
        params: list[Any] = []

        if filters.status:
            params.append(filters.status.value)
            conditions.append(f"t.status = ${len(params)}")
        if filters.assigned_to:
            params.append(filters.assigned_to)
            conditions.append(f"t.assigned_to = ${len(params)}")
        if filters.priority:
            params.append(filters.priority.value)
            conditions.append(f"t.priority = ${len(params)}")
        if filters.channel:
            params.append(filters.channel)
            conditions.append(f"${len(params)} = ANY(t.channels)")
        if filters.client_id:
            params.append(filters.client_id)
            conditions.append(f"t.client_id = ${len(params)}")
        if filters.search:
            params.append(f"%{filters.search}%")
            conditions.append(f"(t.subject ILIKE ${len(params)} OR t.last_message_preview ILIKE ${len(params)})")

        # RBAC: non-admin sees only assigned threads
        if not is_admin and user_email:
            params.append(user_email)
            conditions.append(f"(t.assigned_to = ${len(params)} OR t.assigned_to IS NULL)")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Total count
        total = await self._db.fetchval(
            f"SELECT COUNT(*) FROM conversation_threads t {where}", *params,
        )

        # Fetch threads with client name join
        params.extend([filters.limit, filters.offset])
        rows = await self._db.fetch(
            f"""
            SELECT t.id, t.client_id, t.status, t.priority, t.assigned_to,
                   t.subject, t.channels, t.intent, t.unread_count,
                   t.last_message_preview, t.last_activity_at, t.created_at,
                   t.metadata,
                   c.full_name as client_name, c.email as client_email
            FROM conversation_threads t
            LEFT JOIN clients c ON c.id = t.client_id
            {where}
            ORDER BY
                CASE t.priority
                    WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
                    WHEN 'normal' THEN 2 ELSE 3
                END,
                t.last_activity_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """,
            *params,
        )

        threads = []
        for row in rows:
            meta = row["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
            threads.append({
                "id": str(row["id"]),
                "client_id": row["client_id"],
                "client_name": row["client_name"],
                "client_email": row["client_email"],
                "status": row["status"],
                "priority": row["priority"],
                "assigned_to": row["assigned_to"],
                "subject": row["subject"],
                "channels": row["channels"] or [],
                "intent": row["intent"],
                "unread_count": row["unread_count"],
                "last_message_preview": row["last_message_preview"],
                "last_activity_at": row["last_activity_at"].isoformat() if row["last_activity_at"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "metadata": meta or {},
            })

        return threads, total or 0

    async def get_thread_summary(self, thread_id: UUID, *, max_messages: int = 5) -> str:
        """Generate a compact summary of recent thread messages for context injection."""
        messages = await self.get_thread_messages(thread_id, limit=max_messages)
        if not messages:
            return ""

        lines = []
        for msg in messages:
            direction_icon = "→" if msg.direction == "outbound" else "←"
            sender = msg.metadata.get("sender_name") or msg.metadata.get("first_name") or msg.sender_id
            channel_tag = msg.channel.upper()[:2]
            content_preview = msg.content[:150].replace("\n", " ")
            lines.append(f"[{channel_tag}] {direction_icon} {sender}: {content_preview}")

        return "\n".join(lines)
