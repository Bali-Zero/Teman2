"""
Notification Service
====================
Service for sending email notifications.

Supports multiple email providers:
- SendGrid (default)
- AWS SES
- SMTP (fallback)

Features:
- Rate limiting
- Retry logic with exponential backoff
- BCC to team leader for critical alerts
- Email tracking
"""

import base64
import binascii
import logging
import os
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiohttp

try:
    import aiosmtplib

    _AIOSMTPLIB_AVAILABLE = True
except ImportError:
    aiosmtplib = None  # type: ignore[assignment]
    _AIOSMTPLIB_AVAILABLE = False

from backend.app.modules.notifications.models import (
    AlertStatus,
    AlertType,
    ClientAlert,
    NotificationResult,
)

logger = logging.getLogger(__name__)


class EmailProvider:
    """Base class for email providers."""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        bcc: list[str] | None = None,
        from_email: str = "notifications@balizero.com",
        from_name: str = "Bali Zero Team",
    ) -> bool:
        raise NotImplementedError


class SMTPProvider(EmailProvider):
    """SMTP email provider (Gmail, etc.)."""

    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER")
        # ZOHO_SMTP_PASSWORD is the app-specific SMTP password (preferred over SMTP_PASSWORD)
        self.password = os.getenv("ZOHO_SMTP_PASSWORD") or os.getenv("SMTP_PASSWORD")
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.from_email = os.getenv("SMTP_FROM", self.user)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        from_email: str = None,
        from_name: str = "Bali Zero Team",
        attachments: list[dict] | None = None,
    ) -> bool:
        """Send email via SMTP with optional attachments."""
        if not self.user or not self.password:
            logger.error("SMTP credentials not configured")
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{from_name} <{from_email or self.from_email}>"
            msg["To"] = to_email

            # Add CC/BCC if provided
            if cc:
                msg["Cc"] = ", ".join(cc)
            if bcc:
                msg["Bcc"] = ", ".join(bcc)

            # Attach body parts
            if text_body:
                msg.attach(MIMEText(text_body, "plain", "utf-8"))
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Handle attachments
            if attachments:
                # Create a new multipart/mixed message
                mixed_msg = MIMEMultipart("mixed")
                mixed_msg["Subject"] = msg["Subject"]
                mixed_msg["From"] = msg["From"]
                mixed_msg["To"] = msg["To"]
                if cc:
                    mixed_msg["Cc"] = msg["Cc"]
                if bcc:
                    mixed_msg["Bcc"] = msg["Bcc"]

                # Attach the body part
                mixed_msg.attach(msg)

                # Add file attachments
                for attachment in attachments:
                    # Support both "name" (new) and "filename" (legacy)
                    filename = attachment.get("name") or attachment.get("filename", "attachment")
                    content = attachment.get("content")
                    attachment.get("contentType") or attachment.get(
                        "content_type", "application/octet-stream"
                    )

                    if content:
                        # `content` is the base64-encoded payload from the API caller.
                        # Decode to raw bytes BEFORE handing to MIMEBase: encode_base64 will
                        # re-encode them. Skipping the decode produced double-encoded
                        # attachments — clients saw a base64 string instead of the file,
                        # surfacing as "PDF rusak / struktur tidak valid" on receipt.
                        if isinstance(content, str):
                            try:
                                payload_bytes = base64.b64decode(content, validate=False)
                            except (binascii.Error, ValueError):
                                logger.warning(
                                    "Attachment %s has non-base64 content; sending raw",
                                    filename,
                                )
                                payload_bytes = content.encode("utf-8")
                        else:
                            payload_bytes = content

                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(payload_bytes)
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f'attachment; filename="{filename}"',
                        )
                        mixed_msg.attach(part)

                msg = mixed_msg

            # Send email
            # For port 587: use STARTTLS (use_tls=False, start_tls=True)
            # For port 465: use TLS (use_tls=True, start_tls=False)
            use_tls = self.port == 465
            start_tls = self.port == 587

            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                use_tls=use_tls,
                start_tls=start_tls,
            )

            logger.info(
                "Email sent via SMTP",
                extra={"to": to_email, "subject": subject, "host": self.host},
            )
            return True

        except Exception as e:
            logger.error("Failed to send email via SMTP", exc_info=e)
            return False


class SendGridProvider(EmailProvider):
    """SendGrid email provider."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("SENDGRID_API_KEY")
        self.base_url = "https://api.sendgrid.com/v3"

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        bcc: list[str] | None = None,
        from_email: str = "notifications@balizero.com",
        from_name: str = "Bali Zero Team",
    ) -> bool:
        if not self.api_key:
            logger.error("SendGrid API key not configured")
            return False

        payload = {
            "personalizations": [
                {
                    "to": [{"email": to_email}],
                    "subject": subject,
                },
            ],
            "from": {"email": from_email, "name": from_name},
            "content": [
                {"type": "text/html", "value": html_body},
            ],
        }

        if text_body:
            payload["content"].insert(0, {"type": "text/plain", "value": text_body})

        if bcc:
            payload["personalizations"][0]["bcc"] = [{"email": e} for e in bcc]

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self.base_url}/mail/send",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response,
            ):
                if response.status == 202:
                    logger.info(
                        "Email sent via SendGrid",
                        extra={"to": to_email, "subject": subject},
                    )
                    return True
                error_text = await response.text()
                logger.error(
                    "SendGrid API error",
                    extra={
                        "status": response.status,
                        "error": error_text,
                        "to": to_email,
                    },
                )
                return False
        except Exception as e:
            logger.error("Failed to send email via SendGrid", exc_info=e)
            return False


class NotificationService:
    """Main service for handling notifications."""

    def __init__(self, db_pool, email_provider: EmailProvider | None = None) -> None:
        self.db_pool = db_pool
        self.email_provider = email_provider or self._create_provider()

    def _create_provider(self) -> EmailProvider:
        """Create email provider based on configuration."""
        provider_type = os.getenv("EMAIL_PROVIDER", "sendgrid").lower()

        if provider_type == "smtp":
            return SMTPProvider()
        if provider_type == "sendgrid":
            return SendGridProvider()
        # Auto-detect: use SMTP if SMTP_USER is set, otherwise SendGrid
        if os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"):
            return SMTPProvider()
        return SendGridProvider()

    async def process_alert(self, alert: ClientAlert, client_email: str) -> NotificationResult:
        """
        Process a single alert: send email and update status.

        Args:
            alert: The alert to process
            client_email: Client's email address

        Returns:
            NotificationResult with success status
        """
        try:
            # Determine if team leader should be BCC'd
            bcc = []
            if alert.alert_type in [
                AlertType.PASSPORT_CRITICAL,
                AlertType.PASSPORT_EXPIRED,
                AlertType.VISA_EMERGENCY,
                AlertType.VISA_CRITICAL,
                AlertType.VISA_EXPIRED,
            ]:
                # Get team leader email from database. This address is a BCC:
                # it is a courtesy copy, never the reason a client goes unwarned.
                # Until 2026-08-29 this ran unguarded, so a database error here
                # aborted the whole send and the alert never left the building.
                try:
                    team_leader = await self._get_team_leader_email(alert.client_id)
                except Exception as bcc_error:  # best effort by design: a BCC never blocks the alert
                    logger.warning(
                        "Team leader lookup failed; sending alert without BCC",
                        extra={"client_id": alert.client_id, "error": str(bcc_error)},
                    )
                else:
                    if team_leader:
                        bcc.append(team_leader)

            # Send email
            success = await self.email_provider.send_email(
                to_email=client_email,
                subject=alert.email_subject,
                html_body=alert.email_body,
                bcc=bcc if bcc else None,
            )

            if success:
                await self._update_alert_status(alert, AlertStatus.SENT)
                return NotificationResult(success=True, alert_id=alert.id)
            await self._update_alert_status(alert, AlertStatus.FAILED, "Email provider failed")
            return NotificationResult(
                success=False,
                alert_id=alert.id,
                error_message="Failed to send email",
            )

        except Exception as e:
            logger.error(f"Failed to process alert {alert.id}", exc_info=e)
            # Recording the failure must never mask the failure itself: until
            # 2026-08-29 a broken UPDATE here replaced the real cause in Sentry
            # and left the row 'pending' forever, so it was re-selected as the
            # head of the queue on every subsequent run.
            try:
                await self._update_alert_status(alert, AlertStatus.FAILED, str(e))
            except Exception as status_error:
                logger.error(
                    "Could not record alert failure; the row stays pending",
                    extra={"alert_id": alert.id, "error": str(status_error)},
                )
            return NotificationResult(
                success=False,
                alert_id=alert.id,
                error_message=str(e),
            )

    async def _process_one(
        self,
        alert: ClientAlert,
        get_client_email_func,
    ) -> NotificationResult:
        """Resolve the recipient and process a single alert."""
        client_email = await get_client_email_func(alert.client_id)
        if not client_email:
            logger.warning(f"No email found for client {alert.client_id}")
            await self._update_alert_status(
                alert,
                AlertStatus.SUPPRESSED,
                "No email address found",
            )
            return NotificationResult(
                success=False,
                alert_id=alert.id,
                error_message="No email address found",
            )

        return await self.process_alert(alert, client_email)

    async def process_alerts_batch(
        self,
        alerts: list[ClientAlert],
        get_client_email_func,
    ) -> list[NotificationResult]:
        """
        Process multiple alerts in batch.

        Args:
            alerts: List of alerts to process
            get_client_email_func: Async function to get client email by ID

        Returns:
            List of NotificationResult
        """
        results = []

        for alert in alerts:
            # One alert's failure must never end the run. The queue is ordered
            # oldest-first with no LIMIT, so before 2026-08-29 an exception on
            # the first alert meant every alert behind it was never attempted
            # at all -- silent non-delivery, with no Sentry event to show for it.
            try:
                results.append(await self._process_one(alert, get_client_email_func))
            except Exception as e:
                logger.error(
                    "Alert processing raised; continuing with the rest of the batch",
                    exc_info=e,
                    extra={"alert_id": alert.id},
                )
                results.append(
                    NotificationResult(
                        success=False,
                        alert_id=alert.id,
                        error_message=str(e),
                    ),
                )

        logger.info(
            "Batch processing completed",
            extra={
                "total": len(alerts),
                "successful": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
            },
        )

        return results

    async def _get_team_leader_email(self, client_id: int) -> str | None:
        """Get team leader email for a client."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT tm.email
                FROM team_members tm
                JOIN clients c ON lower(c.assigned_to) = lower(tm.email)
                WHERE c.id = $1
                  AND tm.active IS NOT FALSE
                """,
                client_id,
            )
            return row["email"] if row else None

    async def _update_alert_status(
        self,
        alert: ClientAlert,
        status: AlertStatus,
        error_message: str | None = None,
    ):
        """Update alert status in database."""
        async with self.db_pool.acquire() as conn:
            if alert.id:
                # `$1` WITHOUT A CAST, and `$4` rather than a second `$1`.
                #
                # This statement used to read `status = $1` alongside
                # `CASE WHEN $1::text = 'sent'`. Postgres deduces a parameter's
                # type from ALL of its uses and refuses the statement when they
                # disagree: the assignment target `status` is
                # `character varying`, the cast says `text`, and PREPARE dies
                # with `AmbiguousParameterError: inconsistent types deduced for
                # parameter $1 -- text versus character varying`. It never
                # executed once.
                #
                # The blast radius was not "some status updates are lost". This
                # is the ONLY path that moves a row off `pending`, so every
                # alert that reached it stayed pending and was re-selected on
                # the next run, forever. Measured on production 2026-09-01:
                # 3120 pending rows across 139 clients -- 22.4 duplicates each,
                # accumulating daily since 2026-08-09 -- against 290 `sent`.
                # The 290 are not a contradiction: they took the INSERT branch
                # below, which never had the defect, so alerts sent on first
                # sight succeeded while anything needing an UPDATE could not
                # leave the queue.
                #
                # Separate parameters, so no future edit can re-couple the two
                # uses and re-break PREPARE the same way.
                await conn.execute(
                    """
                    UPDATE notification_alerts
                    SET status = $1,
                        sent_at = CASE WHEN $4 = 'sent' THEN NOW() ELSE sent_at END,
                        error_message = $2
                    WHERE id = $3
                    """,
                    status.value,
                    error_message,
                    alert.id,
                    status.value,
                )
            else:
                # Insert new alert record
                row = await conn.fetchrow(
                    """
                    INSERT INTO notification_alerts
                    (client_id, alert_type, status, message, email_subject, email_body, created_at, sent_at, error_message)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING id
                    """,
                    alert.client_id,
                    alert.alert_type.value,
                    status.value,
                    alert.message,
                    alert.email_subject,
                    alert.email_body,
                    alert.created_at,
                    datetime.now(tz=timezone.utc).replace(tzinfo=None)
                    if status == AlertStatus.SENT
                    else None,
                    error_message,
                )
                alert.id = row["id"]

    async def supersede_duplicate_pending_alerts(self) -> int:
        """Collapse a client's repeated pending alerts of one type down to the
        newest, and return how many were superseded.

        THIS SHIPS WITH THE `_update_alert_status` FIX AND MUST NOT BE SPLIT
        FROM IT. While that UPDATE could not execute, no row ever left
        `pending`, so the daily sentinel re-created the same warning for the
        same client every day and nothing consumed the pile: 3120 rows for 139
        clients on 2026-09-01, of which 923 sat inside the 7-day selection
        window below against only 147 distinct (client, alert_type) pairs.
        Repairing the UPDATE alone would make all 923 deliverable and mail 129
        real clients an average of seven copies each of the same expiry
        warning. Curing the write path is what CREATES that outcome, so the
        cure carries it.

        `suppressed` is the existing status for "rate limited or opted out"
        (`models.py:32`) and is the honest label here — the alert was real, it
        is simply not the one worth sending. No migration, no new state.

        Idempotent, and safe to run on every poll: it keeps exactly one row per
        (client_id, alert_type) because the tuple comparison is a strict total
        order, so a tie on `created_at` still leaves precisely one survivor
        rather than suppressing both or neither.
        """
        async with self.db_pool.acquire() as conn:
            superseded = await conn.fetch(
                """
                UPDATE notification_alerts AS a
                   SET status = 'suppressed',
                       error_message = 'superseded by a newer pending alert of the same type'
                 WHERE a.status = 'pending'
                   AND EXISTS (
                       SELECT 1
                         FROM notification_alerts AS b
                        WHERE b.client_id = a.client_id
                          AND b.alert_type = a.alert_type
                          AND b.status = 'pending'
                          AND (b.created_at, b.id) > (a.created_at, a.id)
                   )
                RETURNING a.id
                """,
            )
        if superseded:
            logger.info(
                "Superseded duplicate pending alerts",
                extra={"count": len(superseded)},
            )
        return len(superseded)

    async def get_pending_alerts(self) -> list[ClientAlert]:
        """Get all pending alerts from database, one per client and type.

        The de-duplication runs HERE rather than in the caller so that every
        consumer of the queue inherits it — a second caller that forgot the
        step would resurrect the duplicate-mail storm this method exists to
        prevent.
        """
        await self.supersede_duplicate_pending_alerts()
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM notification_alerts
                WHERE status = 'pending'
                AND created_at > NOW() - INTERVAL '7 days'
                ORDER BY created_at ASC
                """,
            )
            return [ClientAlert(**dict(row)) for row in rows]
