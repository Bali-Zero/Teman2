"""
Unit tests for Zoho Email Router
Comprehensive test coverage for email sending functionality
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(backend_path))


@pytest.fixture
def mock_zoho_email_service():
    """Mock ZohoEmailService"""
    service = MagicMock()
    service.send_email = AsyncMock()
    service.send_template_email = AsyncMock()
    service.send_bulk_email = AsyncMock()
    service.get_email_status = AsyncMock()
    service.get_sent_emails = AsyncMock()
    service.validate_email = AsyncMock()
    return service


@pytest.fixture
def mock_request():
    """Mock FastAPI Request"""
    request = MagicMock()
    return request


@pytest.mark.unit
class TestZohoEmailRouter:
    """Test Zoho Email Router endpoints"""

    @pytest.mark.asyncio
    async def test_send_email_success(self, mock_zoho_email_service, mock_request):
        """Test successful email send"""
        from app.routers.zoho_email import SendEmailRequest, send_email

        mock_zoho_email_service.send_email = AsyncMock(
            return_value={
                "success": True,
                "message_id": "msg_123",
                "status": "sent",
            }
        )

        request_data = SendEmailRequest(
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        response = await send_email(request_data, mock_request, mock_zoho_email_service)

        assert response["success"] is True
        assert response["message_id"] == "msg_123"
        mock_zoho_email_service.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_error(self, mock_zoho_email_service, mock_request):
        """Test email send error handling"""
        from app.routers.zoho_email import SendEmailRequest, send_email
        from fastapi import HTTPException

        mock_zoho_email_service.send_email = AsyncMock(side_effect=Exception("Email service error"))

        request_data = SendEmailRequest(
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        with pytest.raises(HTTPException) as exc:
            await send_email(request_data, mock_request, mock_zoho_email_service)
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_send_email_with_cc_bcc(self, mock_zoho_email_service, mock_request):
        """Test email send with CC and BCC"""
        from app.routers.zoho_email import SendEmailRequest, send_email

        mock_zoho_email_service.send_email = AsyncMock(
            return_value={
                "success": True,
                "message_id": "msg_123",
            }
        )

        request_data = SendEmailRequest(
            to="test@example.com",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            subject="Test Subject",
            body="Test Body",
        )

        response = await send_email(request_data, mock_request, mock_zoho_email_service)

        assert response["success"] is True
        mock_zoho_email_service.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_template_email_success(self, mock_zoho_email_service, mock_request):
        """Test successful template email send"""
        from app.routers.zoho_email import SendTemplateEmailRequest, send_template_email

        mock_zoho_email_service.send_template_email = AsyncMock(
            return_value={
                "success": True,
                "message_id": "msg_123",
            }
        )

        request_data = SendTemplateEmailRequest(
            to="test@example.com",
            template_id="template_123",
            template_data={"name": "Test User"},
        )

        response = await send_template_email(request_data, mock_request, mock_zoho_email_service)

        assert response["success"] is True
        mock_zoho_email_service.send_template_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_template_email_error(self, mock_zoho_email_service, mock_request):
        """Test template email send error handling"""
        from app.routers.zoho_email import SendTemplateEmailRequest, send_template_email
        from fastapi import HTTPException

        mock_zoho_email_service.send_template_email = AsyncMock(side_effect=Exception("Template error"))

        request_data = SendTemplateEmailRequest(
            to="test@example.com",
            template_id="template_123",
            template_data={"name": "Test User"},
        )

        with pytest.raises(HTTPException) as exc:
            await send_template_email(request_data, mock_request, mock_zoho_email_service)
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_send_bulk_email_success(self, mock_zoho_email_service, mock_request):
        """Test successful bulk email send"""
        from app.routers.zoho_email import SendBulkEmailRequest, send_bulk_email

        mock_zoho_email_service.send_bulk_email = AsyncMock(
            return_value={
                "success": True,
                "sent_count": 2,
                "failed_count": 0,
            }
        )

        request_data = SendBulkEmailRequest(
            recipients=["test1@example.com", "test2@example.com"],
            subject="Bulk Test",
            body="Bulk Body",
        )

        response = await send_bulk_email(request_data, mock_request, mock_zoho_email_service)

        assert response["success"] is True
        assert response["sent_count"] == 2
        mock_zoho_email_service.send_bulk_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_bulk_email_partial_failure(self, mock_zoho_email_service, mock_request):
        """Test bulk email with partial failures"""
        from app.routers.zoho_email import SendBulkEmailRequest, send_bulk_email

        mock_zoho_email_service.send_bulk_email = AsyncMock(
            return_value={
                "success": True,
                "sent_count": 1,
                "failed_count": 1,
                "errors": [{"email": "fail@example.com", "error": "Invalid email"}],
            }
        )

        request_data = SendBulkEmailRequest(
            recipients=["test@example.com", "fail@example.com"],
            subject="Bulk Test",
            body="Bulk Body",
        )

        response = await send_bulk_email(request_data, mock_request, mock_zoho_email_service)

        assert response["success"] is True
        assert response["sent_count"] == 1
        assert response["failed_count"] == 1

    @pytest.mark.asyncio
    async def test_get_email_status_success(self, mock_zoho_email_service, mock_request):
        """Test get email status"""
        from app.routers.zoho_email import get_email_status

        mock_zoho_email_service.get_email_status = AsyncMock(
            return_value={
                "success": True,
                "status": "delivered",
                "delivered_at": "2024-01-01T00:00:00",
            }
        )

        response = await get_email_status("msg_123", mock_request, mock_zoho_email_service)

        assert response["success"] is True
        assert response["status"] == "delivered"
        mock_zoho_email_service.get_email_status.assert_called_once_with("msg_123")

    @pytest.mark.asyncio
    async def test_get_email_status_not_found(self, mock_zoho_email_service, mock_request):
        """Test get email status - not found"""
        from app.routers.zoho_email import get_email_status
        from fastapi import HTTPException

        mock_zoho_email_service.get_email_status = AsyncMock(
            return_value={
                "success": False,
                "error": "Message not found",
            }
        )

        with pytest.raises(HTTPException) as exc:
            await get_email_status("invalid_msg", mock_request, mock_zoho_email_service)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_sent_emails_success(self, mock_zoho_email_service, mock_request):
        """Test get sent emails list"""
        from app.routers.zoho_email import get_sent_emails

        mock_zoho_email_service.get_sent_emails = AsyncMock(
            return_value={
                "success": True,
                "emails": [
                    {"message_id": "msg_1", "to": "test1@example.com", "subject": "Test 1"},
                    {"message_id": "msg_2", "to": "test2@example.com", "subject": "Test 2"},
                ],
                "total": 2,
            }
        )

        response = await get_sent_emails(mock_request, mock_zoho_email_service, limit=10, offset=0)

        assert response["success"] is True
        assert len(response["emails"]) == 2
        mock_zoho_email_service.get_sent_emails.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_email_success(self, mock_zoho_email_service, mock_request):
        """Test email validation"""
        from app.routers.zoho_email import ValidateEmailRequest, validate_email

        mock_zoho_email_service.validate_email = AsyncMock(
            return_value={
                "success": True,
                "valid": True,
                "email": "test@example.com",
            }
        )

        request_data = ValidateEmailRequest(email="test@example.com")

        response = await validate_email(request_data, mock_request, mock_zoho_email_service)

        assert response["success"] is True
        assert response["valid"] is True
        mock_zoho_email_service.validate_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_email_invalid(self, mock_zoho_email_service, mock_request):
        """Test email validation - invalid email"""
        from app.routers.zoho_email import ValidateEmailRequest, validate_email

        mock_zoho_email_service.validate_email = AsyncMock(
            return_value={
                "success": True,
                "valid": False,
                "email": "invalid-email",
                "error": "Invalid email format",
            }
        )

        request_data = ValidateEmailRequest(email="invalid-email")

        response = await validate_email(request_data, mock_request, mock_zoho_email_service)

        assert response["success"] is True
        assert response["valid"] is False

    @pytest.mark.asyncio
    async def test_pydantic_models_validation(self):
        """Test Pydantic model validations"""
        from app.routers.zoho_email import (
            SendEmailRequest,
            SendTemplateEmailRequest,
            SendBulkEmailRequest,
            ValidateEmailRequest,
        )

        # Test SendEmailRequest
        email_request = SendEmailRequest(
            to="test@example.com",
            subject="Test",
            body="Test body",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )
        assert email_request.to == "test@example.com"
        assert email_request.cc == ["cc@example.com"]

        # Test SendTemplateEmailRequest
        template_request = SendTemplateEmailRequest(
            to="test@example.com",
            template_id="template_123",
            template_data={"key": "value"},
        )
        assert template_request.template_id == "template_123"

        # Test SendBulkEmailRequest
        bulk_request = SendBulkEmailRequest(
            recipients=["test1@example.com", "test2@example.com"],
            subject="Bulk",
            body="Bulk body",
        )
        assert len(bulk_request.recipients) == 2

        # Test ValidateEmailRequest
        validate_request = ValidateEmailRequest(email="test@example.com")
        assert validate_request.email == "test@example.com"

