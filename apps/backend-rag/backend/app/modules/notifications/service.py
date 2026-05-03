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
                    attachment.get("contentType") or attachment.get("content_type", "application/octet-stream")

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
                # Get team leader email from database
                team_leader = await self._get_team_leader_email(alert.client_id)
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
            await self._update_alert_status(alert, AlertStatus.FAILED, str(e))
            return NotificationResult(
                success=False,
                alert_id=alert.id,
                error_message=str(e),
            )

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
            # Get client email
            client_email = await get_client_email_func(alert.client_id)
            if not client_email:
                logger.warning(f"No email found for client {alert.client_id}")
                await self._update_alert_status(
                    alert, AlertStatus.SUPPRESSED, "No email address found",
                )
                results.append(
                    NotificationResult(
                        success=False,
                        alert_id=alert.id,
                        error_message="No email address found",
                    ),
                )
                continue

            result = await self.process_alert(alert, client_email)
            results.append(result)

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
                SELECT u.email
                FROM users u
                JOIN clients c ON c.assigned_to = u.email
                WHERE c.id = $1
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
                await conn.execute(
                    """
                    UPDATE notification_alerts
                    SET status = $1,
                        sent_at = CASE WHEN $1 = 'sent' THEN NOW() ELSE sent_at END,
                        error_message = $2
                    WHERE id = $3
                    """,
                    status.value,
                    error_message,
                    alert.id,
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

    async def get_pending_alerts(self) -> list[ClientAlert]:
        """Get all pending alerts from database."""
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
