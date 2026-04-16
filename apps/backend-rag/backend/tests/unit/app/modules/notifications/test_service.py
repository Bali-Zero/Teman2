"""
Test NotificationService.
"""

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend.app.modules.notifications.models import (
    AlertStatus,
    AlertType,
    ClientAlert,
)
from backend.app.modules.notifications.service import (
    NotificationService,
    SendGridProvider,
    SMTPProvider,
)


class TestSendGridProvider:
    """Test SendGrid email provider."""

    @pytest.fixture
    def provider(self):
        return SendGridProvider(api_key="test_key")

    @pytest.mark.asyncio
    async def test_send_email_success(self, provider):
        """Successfully send email via SendGrid."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 202
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await provider.send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_body="<p>Test</p>",
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_send_email_no_api_key(self):
        """Fail gracefully when API key not set."""
        provider = SendGridProvider(api_key=None)

        result = await provider.send_email(
            to_email="test@example.com",
            subject="Test",
            html_body="<p>Test</p>",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_email_with_bcc(self, provider):
        """Send email with BCC recipients."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 202
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await provider.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<p>Test</p>",
                bcc=["leader@example.com"],
            )

            assert result is True
            # Verify BCC was included in payload
            call_args = mock_post.call_args
            assert "bcc" in str(call_args)


class TestSMTPProviderAttachments:
    """Regression: PDF attachments must NOT be double-base64-encoded."""

    @pytest.mark.asyncio
    async def test_attachment_payload_decoded_once(self, monkeypatch):
        """
        invoice_service sends `content` already base64-encoded. The MIME builder
        must decode it before set_payload, so encoders.encode_base64 produces
        exactly one layer. Otherwise clients see a base64 string instead of a
        PDF and report "PDF rusak / struktur tidak valid".
        """
        provider = SMTPProvider()
        provider.user = "u"
        provider.password = "p"

        captured = {}

        async def fake_send(msg, **_kwargs):
            captured["msg"] = msg

        monkeypatch.setattr(
            "backend.app.modules.notifications.service.aiosmtplib.send",
            fake_send,
        )

        raw_pdf = b"%PDF-1.4\n%fake bytes\n%%EOF"
        b64_input = base64.b64encode(raw_pdf).decode()

        ok = await provider.send_email(
            to_email="asya@balizero.com",
            subject="Test",
            html_body="<p>x</p>",
            attachments=[{"name": "Invoice.pdf", "content": b64_input}],
        )
        assert ok is True

        # Find the application/octet-stream part
        msg = captured["msg"]
        parts = [p for p in msg.walk() if p.get_content_type() == "application/octet-stream"]
        assert parts, "expected an attachment part"
        att = parts[0]

        # The MIME transfer-encoded payload, when decoded once, must equal raw bytes.
        # get_payload(decode=True) reverses the Content-Transfer-Encoding header.
        decoded = att.get_payload(decode=True)
        assert decoded == raw_pdf, (
            "Attachment was double-encoded: clients receive a base64 string "
            "instead of the PDF bytes."
        )


class TestNotificationService:
    """Test NotificationService."""

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool with async context manager."""
        pool = Mock()
        conn = AsyncMock()
        ctx_manager = AsyncMock()
        ctx_manager.__aenter__.return_value = conn
        ctx_manager.__aexit__.return_value = False
        pool.acquire.return_value = ctx_manager
        return pool

    @pytest.fixture
    def service(self, mock_db_pool):
        mock_provider = Mock()
        mock_provider.send_email = AsyncMock(return_value=True)
        return NotificationService(mock_db_pool, mock_provider)

    @pytest.mark.asyncio
    async def test_process_alert_success(self, service, mock_db_pool):
        """Successfully process and send alert."""
        alert = ClientAlert(
            id=1,
            client_id=123,
            alert_type=AlertType.PASSPORT_WARNING,
            status=AlertStatus.PENDING,
            message="Test alert",
            email_subject="Test Subject",
            email_body="<p>Test</p>",
            created_at=datetime.now(tz=timezone.utc),
        )

        result = await service.process_alert(alert, "test@example.com")

        assert result.success is True
        assert result.alert_id == 1

    @pytest.mark.asyncio
    async def test_process_alert_critical_includes_team_leader(self, service, mock_db_pool):
        """Critical alerts should BCC team leader."""
        # Mock team leader lookup
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow.return_value = {"email": "leader@example.com"}

        alert = ClientAlert(
            id=1,
            client_id=123,
            alert_type=AlertType.PASSPORT_CRITICAL,
            status=AlertStatus.PENDING,
            message="Critical alert",
            email_subject="URGENT",
            email_body="<p>Test</p>",
            created_at=datetime.now(tz=timezone.utc),
        )

        await service.process_alert(alert, "test@example.com")

        # Verify email was sent with BCC
        service.email_provider.send_email.assert_called_once()
        call_kwargs = service.email_provider.send_email.call_args.kwargs
        assert call_kwargs["bcc"] is not None
        assert "leader@example.com" in call_kwargs["bcc"]

    @pytest.mark.asyncio
    async def test_process_alert_birthday_no_team_leader(self, service, mock_db_pool):
        """Birthday alerts should not BCC team leader."""
        alert = ClientAlert(
            id=1,
            client_id=123,
            alert_type=AlertType.BIRTHDAY,
            status=AlertStatus.PENDING,
            message="Happy birthday",
            email_subject="Happy Birthday",
            email_body="<p>Test</p>",
            created_at=datetime.now(tz=timezone.utc),
        )

        await service.process_alert(alert, "test@example.com")

        # Verify email was sent without BCC
        call_kwargs = service.email_provider.send_email.call_args.kwargs
        assert call_kwargs.get("bcc") is None

    @pytest.mark.asyncio
    async def test_process_alert_failure(self, service, mock_db_pool):
        """Handle email send failure."""
        service.email_provider.send_email = AsyncMock(return_value=False)

        alert = ClientAlert(
            id=1,
            client_id=123,
            alert_type=AlertType.PASSPORT_WARNING,
            status=AlertStatus.PENDING,
            message="Test alert",
            email_subject="Test",
            email_body="<p>Test</p>",
            created_at=datetime.now(tz=timezone.utc),
        )

        result = await service.process_alert(alert, "test@example.com")

        assert result.success is False
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_process_alerts_batch(self, service, mock_db_pool):
        """Process multiple alerts in batch."""
        alerts = [
            ClientAlert(
                id=1,
                client_id=123,
                alert_type=AlertType.PASSPORT_WARNING,
                status=AlertStatus.PENDING,
                message="Alert 1",
                email_subject="Subject 1",
                email_body="<p>Test</p>",
                created_at=datetime.now(tz=timezone.utc),
            ),
            ClientAlert(
                id=2,
                client_id=456,
                alert_type=AlertType.VISA_CRITICAL,
                status=AlertStatus.PENDING,
                message="Alert 2",
                email_subject="Subject 2",
                email_body="<p>Test</p>",
                created_at=datetime.now(tz=timezone.utc),
            ),
        ]

        async def get_email(client_id):
            return f"client{client_id}@example.com"

        results = await service.process_alerts_batch(alerts, get_email)

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_get_pending_alerts(self, service, mock_db_pool):
        """Retrieve pending alerts from database."""
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch.return_value = [
            {
                "id": 1,
                "client_id": 123,
                "alert_type": "passport_warning",
                "status": "pending",
                "message": "Test",
                "email_subject": "Subject",
                "email_body": "<p>Test</p>",
                "created_at": datetime.now(tz=timezone.utc),
                "sent_at": None,
                "error_message": None,
            },
        ]

        alerts = await service.get_pending_alerts()

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.PASSPORT_WARNING
