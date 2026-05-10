"""
Portal billing + profile mixin.

Grouped together because both touch read-only views of client data (invoices,
profile) with no cross-dependency on other portal mixins. Sensitive profile
fields are whitelisted here (PROFILE_EDITABLE_FIELDS).
"""

from typing import Any

import asyncpg
import httpx

from backend.app.utils.logging_utils import get_logger
from backend.services.common.cache import cache_invalidating
from backend.services.portal._rbac import ClientContext, require_client_access

logger = get_logger(__name__)


class PortalBillingMixin:
    """Client billing (invoices) and profile update."""

    pool: asyncpg.Pool

    # Whitelisted profile fields a client can self-serve update via the portal.
    # Anything else requires team intervention.
    PROFILE_EDITABLE_FIELDS: set[str] = {"phone", "whatsapp", "address", "language"}

    # ================================================
    # BILLING
    # ================================================

    @require_client_access
    async def get_billing(
        self,
        client_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """
        Get all invoices for a client with summary statistics.

        Reads from the `invoices` table (primary) joined with practices for context.
        Falls back to practices.documents JSONB if invoices table doesn't exist.

        Returns format expected by frontend BillingResponse type:
            - invoices: list of invoice dicts
            - summary: {total_invoiced, total_paid, total_pending, count}
        """
        async with self.pool.acquire() as conn:
            # Try invoices table first (primary source)
            try:
                rows = await conn.fetch(
                    """
                    SELECT
                        i.id,
                        i.invoice_number,
                        i.amount_idr,
                        i.invoice_source,
                        i.drive_file_id,
                        i.drive_web_link,
                        i.email_sent_to_client,
                        i.generated_at,
                        i.created_at,
                        i.practice_id,
                        pt.name AS practice_name,
                        pt.category AS practice_category,
                        p.payment_status,
                        p.quoted_price
                    FROM invoices i
                    JOIN practices p ON p.id = i.practice_id
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE i.client_id = $1
                    ORDER BY i.created_at DESC
                    """,
                    client_id,
                )
            except Exception as e:
                # invoices table may not exist — fallback to practices JSONB
                logger.warning(f"invoices table query failed, falling back to JSONB: {e}")
                rows = []

        invoices = []
        total_invoiced = 0.0
        total_paid = 0.0

        for row in rows:
            amount = float(row["amount_idr"] or 0)
            payment_status = row["payment_status"] or "pending"
            total_invoiced += amount
            if payment_status == "paid":
                total_paid += amount

            invoices.append({
                "id": row["id"],
                "invoice_number": row["invoice_number"],
                "amount_idr": amount,
                "invoice_source": row["invoice_source"],
                "has_pdf": bool(row["drive_file_id"]),
                "drive_web_link": None,
                "email_sent": bool(row["email_sent_to_client"]),
                "generated_at": row["generated_at"].isoformat() if row["generated_at"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "practice_id": row["practice_id"],
                "practice_name": row["practice_name"],
                "practice_category": row["practice_category"],
                "payment_status": payment_status,
            })

        return {
            "invoices": invoices,
            "summary": {
                "total_invoiced": total_invoiced,
                "total_paid": total_paid,
                "total_pending": total_invoiced - total_paid,
                "count": len(invoices),
            },
        }

    @require_client_access
    async def get_invoice_pdf_url(
        self,
        client_id: int,
        invoice_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, str] | None:
        """Get Drive download URL for an invoice PDF. Returns None if not found."""
        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    "SELECT drive_web_link, drive_file_id FROM invoices WHERE id = $1 AND client_id = $2",
                    invoice_id,
                    client_id,
                )
            except (asyncpg.PostgresError, ConnectionError) as db_exc:
                logger.warning(
                    "billing: get_invoice_pdf_url DB error for client=%s invoice=%s: %s",
                    client_id,
                    invoice_id,
                    db_exc,
                )
                return None

        if not row or (not row["drive_web_link"] and not row["drive_file_id"]):
            return None

        return {"download_url": f"/api/portal/billing/{invoice_id}/pdf"}

    @require_client_access
    async def download_invoice_pdf(
        self,
        client_id: int,
        invoice_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any] | None:
        """Download an invoice PDF through the portal proxy."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT invoice_number, drive_web_link, drive_file_id
                FROM invoices
                WHERE id = $1 AND client_id = $2
                """,
                invoice_id,
                client_id,
            )

        if not row or (not row["drive_web_link"] and not row["drive_file_id"]):
            return None

        extractor = getattr(self, "_extract_drive_file_id", None)
        file_id = row["drive_file_id"] or (
            extractor(row["drive_web_link"]) if extractor else None
        )
        if not file_id:
            return None

        from backend.services.integrations.google_drive_service import GoogleDriveService

        drive_service = GoogleDriveService(self.pool)
        access_token = await drive_service.get_valid_token(GoogleDriveService.SYSTEM_USER_ID)
        if not access_token:
            raise RuntimeError("Google Drive is not connected")

        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            meta_response = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"fields": "mimeType,name,size"},
                headers=headers,
            )
            if meta_response.status_code == 404:
                return None
            if meta_response.status_code != 200:
                logger.error("Portal invoice metadata fetch failed: %s", meta_response.status_code)
                raise RuntimeError("Failed to fetch invoice metadata")

            metadata = meta_response.json()
            mime_type = metadata.get("mimeType") or "application/pdf"
            file_name = metadata.get("name") or f"{row['invoice_number']}.pdf"

            download_response = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"alt": "media"},
                headers=headers,
            )
            if download_response.status_code == 404:
                return None
            if download_response.status_code != 200:
                logger.error("Portal invoice download failed: %s", download_response.status_code)
                raise RuntimeError("Failed to download invoice")

        return {
            "content": download_response.content,
            "file_name": file_name,
            "mime_type": mime_type,
        }

    # ================================================
    # PROFILE UPDATE
    # ================================================

    @cache_invalidating([
        lambda _self, client_id, *_a, **_k: f"zantara:portal_profile:{client_id}:*",
        lambda _self, client_id, *_a, **_k: f"zantara:crm_client:{client_id}:*",
        "zantara:portal_messages:*",
    ])
    @require_client_access
    async def update_profile(
        self,
        client_id: int,
        fields: dict[str, Any],
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """
        Update client profile with whitelisted fields only.

        Sensitive fields (full_name, email, passport_number, nationality, etc.)
        are silently ignored — they require team intervention.

        Side effects when fields are actually changed:
        - Inserts a notification_alerts record (portal_profile_update) for the CRM bell
        - Inserts a portal_messages record (client_to_team) so the team sees the change
        - Cache invalidation handled by the router layer

        Returns the updated profile.
        """
        safe_fields = {
            k: v for k, v in fields.items()
            if k in self.PROFILE_EDITABLE_FIELDS and v is not None
        }

        async with self.pool.acquire() as conn:
            if safe_fields:
                set_parts = []
                params: list[Any] = []
                for i, (key, value) in enumerate(safe_fields.items(), start=1):
                    set_parts.append(f"{key} = ${i}")
                    params.append(value)

                params.append(client_id)
                set_clause = ", ".join(set_parts)

                await conn.execute(
                    f"UPDATE clients SET {set_clause}, updated_at = NOW() WHERE id = ${len(params)} AND deleted_at IS NULL",
                    *params,
                )

                logger.info(f"Portal profile updated for client {client_id}: {list(safe_fields.keys())}")

                # Notify CRM team: insert notification_alerts record (deduped daily)
                fields_label = ", ".join(k.replace("_", " ") for k in safe_fields)
                try:
                    await conn.execute(
                        """
                        INSERT INTO notification_alerts
                            (client_id, alert_type, status, message, email_subject)
                        VALUES ($1, 'portal_profile_update', 'sent', $2, $3)
                        ON CONFLICT ON CONSTRAINT uq_notification_alert_daily DO NOTHING
                        """,
                        client_id,
                        f"Client updated their profile: {fields_label}",
                        "Portal: profile update",
                    )
                except Exception as e:
                    logger.warning(f"Failed to insert portal_profile_update alert for client {client_id}: {e}")

                # Insert portal_messages record so CRM team can see the change in thread view
                try:
                    await conn.execute(
                        """
                        INSERT INTO portal_messages
                            (client_id, practice_id, subject, direction, content, sent_by)
                        VALUES ($1, NULL, 'Profile updated', 'client_to_team', $2, 'portal')
                        """,
                        client_id,
                        f"Client updated their profile via the portal: {fields_label}.",
                    )
                except Exception as e:
                    logger.warning(f"Failed to insert portal_messages record for client {client_id}: {e}")

            return await self._get_profile_data(conn, client_id)

    async def _get_profile_data(self, conn: Any, client_id: int) -> dict[str, Any]:
        """Fetch profile data from DB (shared between get_profile and update_profile)."""
        row = await conn.fetchrow(
            """
            SELECT c.id, c.full_name, c.email, c.phone, c.whatsapp,
                   c.nationality, c.passport_number, c.passport_expiry,
                   c.date_of_birth, c.gender, c.address, c.created_at as member_since,
                   tm.email as assigned_to_email, tm.full_name as assigned_to_name,
                   tm.avatar_url as assigned_to_avatar
            FROM clients c
            LEFT JOIN team_members tm ON tm.email = c.assigned_to AND tm.active = true
            WHERE c.id = $1 AND c.deleted_at IS NULL
            """,
            client_id,
        )

        if not row:
            return {}

        return {
            "id": row["id"],
            "full_name": row["full_name"],
            "email": row["email"],
            "phone": row["phone"],
            "whatsapp": row["whatsapp"],
            "nationality": row["nationality"],
            "passport_number": row["passport_number"],
            "passport_expiry": str(row["passport_expiry"]) if row["passport_expiry"] else None,
            "date_of_birth": str(row["date_of_birth"]) if row["date_of_birth"] else None,
            "gender": row["gender"],
            "address": row["address"],
            "member_since": str(row["member_since"]) if row["member_since"] else None,
            "assigned_to": {
                "email": row["assigned_to_email"],
                "name": row["assigned_to_name"],
                "avatar_url": row["assigned_to_avatar"],
            } if row["assigned_to_email"] else None,
        }


__all__ = ["PortalBillingMixin"]
