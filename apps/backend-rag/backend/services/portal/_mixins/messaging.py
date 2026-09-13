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
        """Get message threads for client.

        `send_message` has always refused a soft-deleted client; READING the
        thread did not, so a deleted client's session could still pull their
        entire message history (portal audit bridge F4). The router's
        `ValueError` catch was written for exactly this and documented as
        unreachable — it is now reachable, and answers 404 like
        `get_dashboard` does.
        """
        async with self.pool.acquire() as conn:
            client = await conn.fetchrow(
                "SELECT id FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )
            if not client:
                raise ValueError(f"Client {client_id} not found")

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

    @cache_invalidating(
        [
            lambda self, client_id, *a, **k: f"zantara:portal_messages:{client_id}:*",
            "zantara:portal_messages:*",
        ]
    )
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
            if not client:
                raise ValueError(f"Client {client_id} not found")

            message = await conn.fetchrow(
                """
                INSERT INTO portal_messages (
                    client_id, practice_id, subject, direction, content, sent_by
                )
                VALUES ($1, $2, $3, 'client_to_team', $4, $5)
                RETURNING id, subject, content, direction, sent_by, read_at, created_at, practice_id
                """,
                client_id,
                practice_id,
                subject,
                content,
                client["email"],
            )

            return {
                "id": message["id"],
                "subject": message["subject"],
                "content": message["content"],
                "from_team": message["direction"] == "team_to_client",
                "sent_by": message["sent_by"],
                "is_read": message["read_at"] is not None,
                "practice_id": message["practice_id"],
                "practice_name": None,
                "created_at": message["created_at"].isoformat(),
            }

    @cache_invalidating(
        [
            lambda self, client_id, *a, **k: f"zantara:portal_messages:{client_id}:*",
        ]
    )
    @require_client_access
    async def mark_message_read(
        self,
        client_id: int,
        message_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """Mark a message as read.

        Only `team_to_client` messages can be marked read by the client —
        mirrors the operator-side guard in `crm_portal_integration.py`
        (`mark_client_message_read`, which restricts to `client_to_team`).
        Without this, a client could mark one of their OWN outbound
        messages read and forge a "the team has read this" signal.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE portal_messages
                SET read_at = NOW()
                WHERE id = $1 AND client_id = $2
                AND direction = 'team_to_client' AND read_at IS NULL
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
        """Get client locale preferences.

        NOTIFICATION CONSENT IS NOT HERE. `notification_prefs` (keyed by the
        portal `user_id`, served by `portal_notification_prefs.py`) is the
        single source of truth, because it is the only one anything reads:
        `services/compliance/alert_dispatcher.py` consults it to decide
        whether a client gets a compliance email or WhatsApp message. The
        `client_preferences.email_notifications` /
        `whatsapp_notifications` columns had NO reader anywhere — not a cron,
        not a dispatcher, not a CRM surface — yet this endpoint kept
        reporting them, defaulting to true/true.

        Measured live 2026-09-11 on the same account at the same moment
        (portal audit F-04 + bridge F3):
            GET /api/portal/notifications/prefs -> {"wa_enabled": false, ...}
            GET /api/portal/settings            -> {"whatsapp_notifications": true, ...}
        Two answers to one question, and the one a client could reach through
        the UI was the one nobody enforces. Under UU PDP that is a consent
        mismatch, not a display bug — so the field is gone from this
        endpoint rather than left as the obvious place for the next
        developer to wire a new UI or cron.

        The columns themselves are left in place: dropping them is a
        migration and a data decision, not a bug fix.
        """
        async with self.pool.acquire() as conn:
            prefs = await conn.fetchrow(
                """
                SELECT language, timezone
                FROM client_preferences
                WHERE client_id = $1
                """,
                client_id,
            )

            if not prefs:
                # Return defaults
                return {
                    "language": "en",
                    "timezone": "Asia/Jakarta",
                }

            return {
                "language": prefs["language"],
                "timezone": prefs["timezone"],
            }

    @cache_invalidating(
        [
            lambda self, client_id, *a, **k: f"zantara:portal_preferences:{client_id}:*",
        ]
    )
    @require_client_access
    async def update_preferences(
        self,
        client_id: int,
        preferences: dict[str, Any],
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """Update client locale preferences.

        `email_notifications` / `whatsapp_notifications` are deliberately NOT
        accepted here — see `get_preferences` for why. A payload carrying
        them is ignored rather than rejected, so an older client build cannot
        start failing; what it can no longer do is write a consent value that
        nothing enforces.
        """
        async with self.pool.acquire() as conn:
            # Build dynamic update
            updates = []
            params = [client_id]
            param_idx = 2

            allowed_fields = {
                "language": str,
                "timezone": str,
            }

            for field in allowed_fields.keys():
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
            # The INSERT arm seeds the row's defaults; the DO UPDATE arm
            # applies the caller's values. The seed list is written out, not
            # derived from `allowed_fields`, because the two used to be
            # coupled by position — a field added to or removed from that
            # dict silently shifted the VALUES tuple.
            await conn.execute(
                f"""
                INSERT INTO client_preferences (client_id, language, timezone)
                VALUES ($1, 'en', 'Asia/Jakarta')
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
