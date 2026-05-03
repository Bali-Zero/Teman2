"""
Portal messaging + preferences mixin.

Grouped together because both read/write tiny client-scoped tables
(portal_messages, client_preferences) and neither has cross-dependency
on other mixins.
"""

from typing import Any

import asyncpg

from backend.services.common.cache import cache_invalidating
from backend.services.portal._rbac import ClientContext, require_client_access


class PortalMessagingMixin:
    """Messaging (portal_messages) and client preferences (client_preferences)."""

    pool: asyncpg.Pool

    # ================================================
    # MESSAGES
    # ================================================

    @require_client_access
    async def get_messages(
        self,
        client_id: int,
        limit: int = 50,
        offset: int = 0,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """Get message threads for client."""
        async with self.pool.acquire() as conn:
            messages = await conn.fetch(
                """
                SELECT m.id, m.subject, m.content, m.direction, m.sent_by,
                       m.read_at, m.created_at, m.practice_id,
                       p.id as practice_id, pt.name as practice_name
                FROM portal_messages m
                LEFT JOIN practices p ON p.id = m.practice_id
                LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE m.client_id = $1
                ORDER BY m.created_at DESC
                LIMIT $2 OFFSET $3
                """,
                client_id,
                limit,
                offset,
            )

            total = await conn.fetchval(
                "SELECT COUNT(*) FROM portal_messages WHERE client_id = $1",
                client_id,
            )

            unread = await conn.fetchval(
                """
                SELECT COUNT(*) FROM portal_messages
                WHERE client_id = $1
                AND direction = 'team_to_client'
                AND read_at IS NULL
                """,
                client_id,
            )

            return {
                "messages": [
                    {
                        "id": m["id"],
                        "subject": m["subject"],
                        "content": m["content"],
                        "from_team": m["direction"] == "team_to_client",
                        "sent_by": m["sent_by"],
                        "is_read": m["read_at"] is not None,
                        "practice_id": m["practice_id"],
                        "practice_name": m["practice_name"],
                        "created_at": m["created_at"].isoformat(),
                    }
                    for m in messages
                ],
                "total": total,
                "unread_count": unread,
            }

    @cache_invalidating([
        lambda self, client_id, *a, **k: f"zantara:portal_messages:{client_id}:*",
        "zantara:portal_messages:*",
    ])
    @require_client_access
    async def send_message(
        self,
        client_id: int,
        content: str,
        subject: str | None = None,
        practice_id: int | None = None,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """Send a message from client to team."""
        async with self.pool.acquire() as conn:
            # Get client email for sent_by
            client = await conn.fetchrow(
                "SELECT email FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )

            message = await conn.fetchrow(
                """
                INSERT INTO portal_messages (
                    client_id, practice_id, subject, direction, content, sent_by
                )
                VALUES ($1, $2, $3, 'client_to_team', $4, $5)
                RETURNING id, created_at
                """,
                client_id,
                practice_id,
                subject,
                content,
                client["email"],
            )

            return {
                "id": message["id"],
                "created_at": message["created_at"].isoformat(),
            }

    @cache_invalidating([
        lambda self, client_id, *a, **k: f"zantara:portal_messages:{client_id}:*",
    ])
    @require_client_access
    async def mark_message_read(
        self,
        client_id: int,
        message_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """Mark a message as read."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE portal_messages
                SET read_at = NOW()
                WHERE id = $1 AND client_id = $2 AND read_at IS NULL
                """,
                message_id,
                client_id,
            )

            return {"success": result != "UPDATE 0"}

    # ================================================
    # PREFERENCES
    # ================================================

    @require_client_access
    async def get_preferences(
        self,
        client_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """Get client preferences."""
        async with self.pool.acquire() as conn:
            prefs = await conn.fetchrow(
                """
                SELECT email_notifications, whatsapp_notifications,
                       language, timezone
                FROM client_preferences
                WHERE client_id = $1
                """,
                client_id,
            )

            if not prefs:
                # Return defaults
                return {
                    "email_notifications": True,
                    "whatsapp_notifications": True,
                    "language": "en",
                    "timezone": "Asia/Jakarta",
                }

            return {
                "email_notifications": prefs["email_notifications"],
                "whatsapp_notifications": prefs["whatsapp_notifications"],
                "language": prefs["language"],
                "timezone": prefs["timezone"],
            }

    @cache_invalidating([
        lambda self, client_id, *a, **k: f"zantara:portal_preferences:{client_id}:*",
    ])
    @require_client_access
    async def update_preferences(
        self,
        client_id: int,
        preferences: dict[str, Any],
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """Update client preferences."""
        async with self.pool.acquire() as conn:
            # Build dynamic update
            updates = []
            params = [client_id]
            param_idx = 2

            allowed_fields = {
                "email_notifications": bool,
                "whatsapp_notifications": bool,
                "language": str,
                "timezone": str,
            }

            for field, _field_type in allowed_fields.items():
                if field in preferences:
                    updates.append(f"{field} = ${param_idx}")
                    params.append(preferences[field])
                    param_idx += 1

            if not updates:
                return await self.get_preferences(
                    client_id,
                    current_user=current_user,
                )

            # Upsert preferences
            await conn.execute(
                f"""
                INSERT INTO client_preferences (client_id, {", ".join(allowed_fields.keys())})
                VALUES ($1, true, true, 'en', 'Asia/Jakarta')
                ON CONFLICT (client_id) DO UPDATE
                SET {", ".join(updates)}
                """,
                *params,
            )

            return await self.get_preferences(
                client_id,
                current_user=current_user,
            )


__all__ = ["PortalMessagingMixin"]
