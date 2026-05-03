"""
Portal Notification Service — inserts portal_messages for client-facing notifications.

Used when the team takes actions that the client should see in their portal:
- Team uploads a document → client sees "New document: passport"
- Practice status changes → client sees "Your KITAS status updated to on_process"
- Profile fields updated → client sees "Your profile has been updated"
"""

import asyncpg

from backend.app.utils.logging_utils import get_logger
from backend.services.notifications.email_audit import notify_email_failure_critical

logger = get_logger(__name__)

# Fields that warrant a client notification when updated
SIGNIFICANT_FIELDS = {
    "passport_number", "passport_expiry", "visa_type", "visa_expiry",
    "address", "city", "province", "status", "date_of_birth",
}

# Fields that are internal-only and should NOT trigger notifications
INTERNAL_FIELDS = {
    "assigned_to", "notes", "tags", "custom_fields", "lead_source",
    "last_contacted_at", "avatar_url", "service_interest",
}


class PortalNotificationService:
    """Inserts team_to_client messages into portal_messages."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def notify_document_uploaded(
        self,
        client_id: int,
        document_type: str,
        sent_by: str,
        practice_id: int | None = None,
    ) -> int | None:
        """Notify client that a new document was added by the team."""
        doc_display = document_type.replace("_", " ").title()
        return await self._insert_message(
            client_id=client_id,
            practice_id=practice_id,
            subject=f"New document: {doc_display}",
            content=f"A new {doc_display} document has been added to your profile.",
            sent_by=sent_by,
        )

    async def notify_practice_status_changed(
        self,
        client_id: int,
        practice_id: int,
        practice_type: str,
        new_status: str,
        sent_by: str,
    ) -> int | None:
        """Notify client that their practice status changed."""
        status_display = new_status.replace("_", " ").title()
        return await self._insert_message(
            client_id=client_id,
            practice_id=practice_id,
            subject=f"Status update: {practice_type}",
            content=f"Your {practice_type} status has been updated to {status_display}.",
            sent_by=sent_by,
        )

    async def notify_profile_updated(
        self,
        client_id: int,
        updated_fields: list[str],
        sent_by: str,
    ) -> int | None:
        """Notify client that their profile was updated (significant fields only)."""
        significant = [f for f in updated_fields if f in SIGNIFICANT_FIELDS]
        if not significant:
            return None

        fields_display = ", ".join(f.replace("_", " ") for f in significant)
        return await self._insert_message(
            client_id=client_id,
            practice_id=None,
            subject="Profile updated",
            content=f"Your profile has been updated: {fields_display}.",
            sent_by=sent_by,
        )

    async def _insert_message(
        self,
        client_id: int,
        practice_id: int | None,
        subject: str,
        content: str,
        sent_by: str,
    ) -> int | None:
        """Insert a portal_messages record. Returns message id or None on error."""
        try:
            async with self.pool.acquire() as conn:
                msg_id = await conn.fetchval(
                    """
                    INSERT INTO portal_messages
                        (client_id, practice_id, subject, direction, content, sent_by)
                    VALUES ($1, $2, $3, 'team_to_client', $4, $5)
                    RETURNING id
                    """,
                    client_id,
                    practice_id,
                    subject,
                    content,
                    sent_by,
                )
                logger.info(
                    f"Portal notification sent to client {client_id}: {subject}",
                )
                return msg_id
        except Exception as e:
            logger.error(
                f"Failed to insert portal notification for client {client_id}: {e}",
            )
            # Audit bug #4: previously returned None silently — client lost
            # every status-change notification when insert failed. Page the
            # owner via the email-critical channel so operations can recover
            # (the in-app notification is functionally equivalent to a
            # critical email from the client's point of view).
            notify_email_failure_critical(
                email_type="portal_notification",
                to_email=f"client#{client_id}",
                subject=subject,
                practice_id=practice_id,
                error=f"portal_messages insert failed: {e}",
            )
            return None
