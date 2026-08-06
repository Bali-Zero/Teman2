"""
Focused contract tests for the current PortalService public surface.

These tests fail on contract drift; they must never hide failures with dynamic skips.
"""

from collections.abc import Coroutine
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def client_context(client_id: int = 1) -> dict[str, object]:
    """Return a synthetic authenticated portal identity for RBAC checks."""
    return {
        "client_id": client_id,
        "email": "synthetic-client@example.test",
        "impersonating": False,
    }


def close_spawned_coroutine(
    coroutine: Coroutine[Any, Any, Any],
    **_kwargs: object,
) -> None:
    """Consume a background coroutine without starting a real side effect."""
    coroutine.close()


@pytest.mark.unit
class TestPortalServiceSimple:
    """Simplified unit tests for Portal Service"""

    def test_portal_service_import(self):
        """Test that PortalService can be imported"""
        from backend.services.portal.portal_service import PortalService

        assert PortalService is not None

    def test_portal_service_init(self):
        """Test PortalService initialization"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        service = PortalService(pool=mock_pool)

        assert service.pool == mock_pool

    def test_build_visa_dashboard_data(self):
        """Test _build_visa_dashboard_data method"""
        from backend.services.portal.portal_service import PortalService

        service = PortalService(pool=MagicMock())

        # Test with no visa practice
        result = service._build_visa_dashboard_data(None)
        expected = {
            "status": "none",
            "type": None,
            "expiryDate": None,
            "daysRemaining": None,
        }
        assert result == expected

        # Test with completed visa
        future_date = datetime.now(timezone.utc) + timedelta(days=100)
        visa_practice = {
            "status": "completed",
            "expiry_date": future_date,
            "code": "KITAS",
            "name": "Limited Stay Permit",
        }

        result = service._build_visa_dashboard_data(visa_practice)
        assert result["status"] == "active"
        assert result["type"] == "KITAS - Limited Stay Permit"
        assert result["expiryDate"] is not None
        assert result["daysRemaining"] == 100

        # Test with expired visa
        past_date = datetime.now(timezone.utc) - timedelta(days=10)
        visa_practice["expiry_date"] = past_date

        result = service._build_visa_dashboard_data(visa_practice)
        assert result["status"] == "expired"
        assert result["daysRemaining"] == -10

        # Test with expiring soon visa
        expiring_date = datetime.now(timezone.utc) + timedelta(days=30)
        visa_practice["expiry_date"] = expiring_date

        result = service._build_visa_dashboard_data(visa_practice)
        assert result["status"] == "warning"
        assert result["daysRemaining"] == 30

    def test_get_tax_status(self):
        """Test _get_tax_status method"""
        from backend.services.portal.portal_service import PortalService

        service = PortalService(pool=MagicMock())

        # Test with no deadline
        result = service._get_tax_status(None)
        assert result == "compliant"

        # Test with overdue deadline
        deadline = {"days_until": -5}
        result = service._get_tax_status(deadline)
        assert result == "overdue"

        # Test with attention needed
        deadline = {"days_until": 10}
        result = service._get_tax_status(deadline)
        assert result == "attention"

        # Test with compliant
        deadline = {"days_until": 30}
        result = service._get_tax_status(deadline)
        assert result == "compliant"

    def test_build_action_items(self):
        """Test _build_action_items method"""
        from backend.services.portal.portal_service import PortalService

        service = PortalService(pool=MagicMock())

        # Test with no visa warning and no action items
        visa_data = {"status": "active", "daysRemaining": 100}
        action_items = []

        result = service._build_action_items(action_items, visa_data)
        assert result == []

        # Test with visa warning
        visa_data = {"status": "warning", "daysRemaining": 30}
        action_items = []

        result = service._build_action_items(action_items, visa_data)
        assert len(result) == 1
        assert result[0]["title"] == "Visa Expiring Soon"
        assert result[0]["priority"] == "high"
        assert result[0]["type"] == "visa_renewal"

        # Test with high priority visa warning
        visa_data = {"status": "warning", "daysRemaining": 15}

        result = service._build_action_items(action_items, visa_data)
        assert result[0]["priority"] == "high"

        # Test with missing documents
        visa_data = {"status": "active"}
        action_item = MagicMock()
        action_item.__getitem__ = lambda self, key: {
            "id": 1,
            "practice_name": "Test Practice",
            "missing_documents": ["passport", "photo"],
            "status": "waiting_documents",
        }.get(key)

        result = service._build_action_items([action_item], visa_data)
        assert len(result) == 1
        assert "Documents Required" in result[0]["title"]
        assert result[0]["priority"] == "high"

    def test_get_standard_tax_deadlines(self):
        """Test _get_standard_tax_deadlines method"""
        from backend.services.portal.portal_service import PortalService

        service = PortalService(pool=MagicMock())

        # Test with current date
        today = datetime.now(timezone.utc)
        deadlines = service._get_standard_tax_deadlines(today)

        assert len(deadlines) == 3
        assert all("type" in d for d in deadlines)
        assert all("period" in d for d in deadlines)
        assert all("due_date" in d for d in deadlines)
        assert all("days_until" in d for d in deadlines)
        assert all("urgency" in d for d in deadlines)

        # Check deadline types
        types = [d["type"] for d in deadlines]
        assert "PPh 21/23/4(2)" in types
        assert "PPN (VAT)" in types
        assert "Annual SPT" in types

        # Check sorting (should be sorted by days_until)
        days_until_list = [d["days_until"] for d in deadlines]
        assert days_until_list == sorted(days_until_list)

    @pytest.mark.asyncio
    async def test_get_dashboard_with_mock(self):
        """Test get_dashboard method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        # Mock database
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock client data
        mock_client = MagicMock()
        mock_client.__getitem__ = lambda self, key: {
            "id": 1,
            "full_name": "Test Client",
            "email": "test@example.com",
        }.get(key)

        # Mock responses
        mock_conn.fetchrow.side_effect = [
            mock_client,  # Client lookup
            None,  # Visa practice
            {"total": 0, "pending": 0},  # Document counts
        ]
        mock_conn.fetch.side_effect = [
            [],  # Companies
            [],  # Action items
        ]
        mock_conn.fetchval.return_value = 0  # Unread count

        service = PortalService(pool=mock_pool)
        result = await service.get_dashboard(1, current_user=client_context())

        assert isinstance(result, dict)
        assert "visa" in result
        assert "company" in result
        assert "taxes" in result
        assert "documents" in result
        assert "messages" in result
        assert "actions" in result

        assert result["visa"]["status"] == "none"
        assert result["company"]["status"] == "none"
        assert result["documents"]["total"] == 0
        assert result["messages"]["unread"] == 0

    @pytest.mark.asyncio
    async def test_get_dashboard_client_not_found(self):
        """Test get_dashboard with non-existent client"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock client not found
        mock_conn.fetchrow.return_value = None

        service = PortalService(pool=mock_pool)

        with pytest.raises(ValueError, match="Client 999 not found"):
            await service.get_dashboard(999, current_user=client_context(999))

    @pytest.mark.asyncio
    async def test_get_visa_status_with_mock(self):
        """Test get_visa_status method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock client exists
        mock_client = MagicMock()
        mock_client.__getitem__ = lambda self, key: {"id": 1}.get(key)

        # Mock responses
        mock_conn.fetchrow.side_effect = [
            mock_client,  # Client lookup
            None,  # Current visa
        ]
        mock_conn.fetch.return_value = []  # Visa history and documents

        service = PortalService(pool=mock_pool)
        result = await service.get_visa_status(1, current_user=client_context())

        assert isinstance(result, dict)
        assert "current" in result
        assert "history" in result
        assert "documents" in result
        assert result["current"] is None
        assert result["history"] == []
        assert result["documents"] == []

    @pytest.mark.asyncio
    async def test_get_companies_with_mock(self):
        """Test get_companies method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock company data
        mock_company = MagicMock()
        mock_company.__getitem__ = lambda self, key: {
            "id": 1,
            "company_id": 1,
            "company_name": "Test Company",
            "company_type": "PT",
            "industry": "Technology",
            "role": "owner",
            "is_primary": True,
            "created_at": datetime.now(timezone.utc),
        }.get(key)

        mock_conn.fetch.return_value = [mock_company]

        service = PortalService(pool=mock_pool)
        result = await service.get_companies(1, current_user=client_context())

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "Test Company"
        assert result[0]["type"] == "PT"
        assert result[0]["isPrimary"] is True

    @pytest.mark.asyncio
    async def test_get_company_detail_with_mock(self):
        """Test get_company_detail method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock ownership and company data
        mock_ownership = MagicMock()
        mock_ownership.__getitem__ = lambda self, key: {
            "role": "owner",
            "is_primary": True,
        }.get(key)

        mock_company = MagicMock()
        mock_company.__getitem__ = lambda self, key: {
            "id": 1,
            "company_name": "Test Company",
            "company_type": "PT",
            "industry": "Technology",
        }.get(key)

        mock_conn.fetchrow.side_effect = [mock_ownership, mock_company]
        mock_conn.fetch.return_value = []  # Practices and documents

        service = PortalService(pool=mock_pool)
        result = await service.get_company_detail(1, 1, current_user=client_context())

        assert isinstance(result, dict)
        assert result["name"] == "Test Company"
        assert result["type"] == "PT"
        assert result["ownership"]["role"] == "owner"
        assert result["licenses"] == []
        assert result["documents"] == []

    @pytest.mark.asyncio
    async def test_get_company_detail_not_accessible(self):
        """Test get_company_detail with inaccessible company"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock no ownership
        mock_conn.fetchrow.return_value = None

        service = PortalService(pool=mock_pool)

        with pytest.raises(ValueError, match="Company not found or not accessible"):
            await service.get_company_detail(1, 999, current_user=client_context())

    @pytest.mark.asyncio
    async def test_set_primary_company_with_mock(self):
        """Test set_primary_company method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock successful update
        mock_conn.execute.side_effect = [
            None,  # Clear previous primary
            "UPDATE 1",  # Set new primary
        ]
        transaction = MagicMock()
        transaction.__aenter__ = AsyncMock(return_value=None)
        transaction.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=transaction)

        service = PortalService(pool=mock_pool)
        result = await service.set_primary_company(1, 1, current_user=client_context())

        assert result["success"] is True
        assert result["primary_company_id"] == 1

    @pytest.mark.asyncio
    async def test_set_primary_company_not_found(self):
        """Test set_primary_company with non-existent company"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock failed update
        mock_conn.execute.side_effect = [
            None,  # Clear previous primary
            "UPDATE 0",  # Set new primary failed
        ]
        transaction = MagicMock()
        transaction.__aenter__ = AsyncMock(return_value=None)
        transaction.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=transaction)

        service = PortalService(pool=mock_pool)

        with pytest.raises(ValueError, match="Company not found or not accessible"):
            await service.set_primary_company(1, 999, current_user=client_context())

    @pytest.mark.asyncio
    async def test_get_tax_overview_with_mock(self):
        """Test get_tax_overview method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock responses
        mock_conn.fetch.side_effect = [
            [],  # Companies
            [],  # Tax practices
        ]

        service = PortalService(pool=mock_pool)
        result = await service.get_tax_overview(1, current_user=client_context())

        assert isinstance(result, dict)
        assert set(result) == {"summary", "obligations", "history"}
        assert result["summary"]["totalDue"] == 0
        assert result["history"] == []
        assert len(result["obligations"]) == 3  # Standard deadlines

    @pytest.mark.asyncio
    async def test_get_documents_with_mock(self):
        """Test get_documents method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock document data
        mock_doc = MagicMock()
        mock_doc.__getitem__ = lambda self, key: {
            "id": 1,
            "document_type": "passport",
            "file_name": "passport.pdf",
            "status": "verified",
            "expiry_date": None,
            "file_url": "https://example.com/file.pdf",
            "file_size_kb": 100,
            "practice_id": None,
            "practice_name": None,
            "created_at": datetime.now(timezone.utc),
        }.get(key)

        mock_conn.fetch.return_value = [mock_doc]

        service = PortalService(pool=mock_pool)
        result = await service.get_documents(1, current_user=client_context())

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "passport"
        assert result[0]["name"] == "passport.pdf"
        assert result[0]["status"] == "verified"
        assert result[0]["downloadable"] is True

    @pytest.mark.asyncio
    async def test_get_documents_with_filter(self):
        """Test get_documents with document type filter"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        mock_conn.fetch.return_value = []

        service = PortalService(pool=mock_pool)
        result = await service.get_documents(
            1,
            document_type="passport",
            current_user=client_context(),
        )

        assert isinstance(result, list)
        assert result == []

        # Verify the query was called with filter
        mock_conn.fetch.assert_called_once()
        call_args = mock_conn.fetch.call_args
        assert "document_type = $2" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_upload_document_with_mock(self):
        """Test upload_document method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock responses
        mock_client = MagicMock()
        mock_client.__getitem__ = lambda self, key: {"email": "test@example.com"}.get(key)

        mock_doc = MagicMock()
        mock_doc.__getitem__ = lambda self, key: {
            "id": 1,
            "document_type": "passport",
            "file_name": "passport.pdf",
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
        }.get(key)

        mock_conn.fetchrow.side_effect = [None, mock_client, mock_doc]
        transaction = MagicMock()
        transaction.__aenter__ = AsyncMock(return_value=None)
        transaction.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=transaction)

        service = PortalService(pool=mock_pool)
        with (
            patch(
                "backend.services.portal._mixins.documents.VirusScanner.scan",
                return_value={"clean": True, "threats": []},
            ),
            patch.object(
                service,
                "_upload_to_drive",
                new=AsyncMock(return_value={"success": True}),
            ),
            patch(
                "backend.services.portal._mixins.documents.DocumentOCR.extract_text",
                new=AsyncMock(return_value={"success": True, "text": "", "pages": 1}),
            ),
            patch(
                "backend.services.portal._mixins.documents.ExpiryDetector.detect_expiry",
                return_value={"expiry_date": None, "confidence": 0},
            ),
            patch(
                "backend.services.portal._mixins.documents.spawn",
                side_effect=close_spawned_coroutine,
            ),
        ):
            result = await service.upload_document(
                client_id=1,
                file_content=b"test content",
                file_name="passport.pdf",
                document_type="passport",
                current_user=client_context(),
            )

        assert isinstance(result, dict)
        assert result["id"] == 1
        assert result["type"] == "passport"
        assert result["name"] == "passport.pdf"
        assert result["status"] == "pending"
        assert result["size_kb"] == 0  # len(b"test content") // 1024 = 0

    @pytest.mark.asyncio
    async def test_upload_document_with_practice(self):
        """Test upload_document with practice_id validation"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock practice exists
        mock_practice = MagicMock()
        mock_practice.__getitem__ = lambda self, key: {"id": 1}.get(key)

        mock_client = MagicMock()
        mock_client.__getitem__ = lambda self, key: {"email": "test@example.com"}.get(key)

        mock_doc = MagicMock()
        mock_doc.__getitem__ = lambda self, key: {
            "id": 1,
            "document_type": "passport",
            "file_name": "passport.pdf",
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
        }.get(key)

        mock_conn.fetchrow.side_effect = [None, mock_practice, mock_client, mock_doc]
        transaction = MagicMock()
        transaction.__aenter__ = AsyncMock(return_value=None)
        transaction.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=transaction)

        service = PortalService(pool=mock_pool)
        with (
            patch(
                "backend.services.portal._mixins.documents.VirusScanner.scan",
                return_value={"clean": True, "threats": []},
            ),
            patch.object(
                service,
                "_upload_to_drive",
                new=AsyncMock(return_value={"success": True}),
            ),
            patch(
                "backend.services.portal._mixins.documents.DocumentOCR.extract_text",
                new=AsyncMock(return_value={"success": True, "text": "", "pages": 1}),
            ),
            patch(
                "backend.services.portal._mixins.documents.ExpiryDetector.detect_expiry",
                return_value={"expiry_date": None, "confidence": 0},
            ),
            patch(
                "backend.services.portal._mixins.documents.spawn",
                side_effect=close_spawned_coroutine,
            ),
        ):
            result = await service.upload_document(
                client_id=1,
                file_content=b"test content",
                file_name="passport.pdf",
                document_type="passport",
                practice_id=1,
                current_user=client_context(),
            )

        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_upload_document_invalid_practice(self):
        """Test upload_document with invalid practice_id"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock practice not found
        mock_conn.fetchrow.return_value = None

        service = PortalService(pool=mock_pool)

        with pytest.raises(ValueError, match="Practice not found or not accessible"):
            await service.upload_document(
                client_id=1,
                file_content=b"test content",
                file_name="passport.pdf",
                document_type="passport",
                practice_id=999,
                current_user=client_context(),
            )

    @pytest.mark.asyncio
    async def test_get_messages_with_mock(self):
        """Test get_messages method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock message data
        mock_message = MagicMock()
        mock_message.__getitem__ = lambda self, key: {
            "id": 1,
            "subject": "Test Message",
            "content": "Test content",
            "direction": "team_to_client",
            "sent_by": "team@example.com",
            "read_at": None,
            "practice_id": None,
            "practice_name": None,
            "created_at": datetime.now(timezone.utc),
        }.get(key)

        mock_conn.fetch.return_value = [mock_message]
        mock_conn.fetchval.side_effect = [1, 0]  # total, unread

        service = PortalService(pool=mock_pool)
        result = await service.get_messages(1, current_user=client_context())

        assert isinstance(result, dict)
        assert "messages" in result
        assert "total" in result
        assert "unread_count" in result
        assert len(result["messages"]) == 1
        assert result["total"] == 1
        assert result["unread_count"] == 0
        assert result["messages"][0]["from_team"] is True
        assert result["messages"][0]["is_read"] is False

    @pytest.mark.asyncio
    async def test_send_message_with_mock(self):
        """Test send_message method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock responses
        mock_client = MagicMock()
        mock_client.__getitem__ = lambda self, key: {"email": "client@example.com"}.get(key)

        mock_message = MagicMock()
        mock_message.__getitem__ = lambda self, key: {
            "id": 1,
            "created_at": datetime.now(timezone.utc),
        }.get(key)

        mock_conn.fetchrow.side_effect = [mock_client, mock_message]

        service = PortalService(pool=mock_pool)
        result = await service.send_message(
            client_id=1,
            content="Test message",
            subject="Test Subject",
            current_user=client_context(),
        )

        assert isinstance(result, dict)
        assert result["id"] == 1
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_mark_message_read_with_mock(self):
        """Test mark_message_read method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock successful update
        mock_conn.execute.return_value = "UPDATE 1"

        service = PortalService(pool=mock_pool)
        result = await service.mark_message_read(1, 1, current_user=client_context())

        assert isinstance(result, dict)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_mark_message_read_not_found(self):
        """Test mark_message_read with non-existent message"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock no update
        mock_conn.execute.return_value = "UPDATE 0"

        service = PortalService(pool=mock_pool)
        result = await service.mark_message_read(1, 999, current_user=client_context())

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_preferences_with_mock(self):
        """Test get_preferences method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock existing preferences
        mock_prefs = MagicMock()
        mock_prefs.__getitem__ = lambda self, key: {
            "email_notifications": True,
            "whatsapp_notifications": False,
            "language": "en",
            "timezone": "Asia/Jakarta",
        }.get(key)

        mock_conn.fetchrow.return_value = mock_prefs

        service = PortalService(pool=mock_pool)
        result = await service.get_preferences(1, current_user=client_context())

        assert isinstance(result, dict)
        assert result["email_notifications"] is True
        assert result["whatsapp_notifications"] is False
        assert result["language"] == "en"
        assert result["timezone"] == "Asia/Jakarta"

    @pytest.mark.asyncio
    async def test_get_preferences_default(self):
        """Test get_preferences with no existing preferences"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock no preferences
        mock_conn.fetchrow.return_value = None

        service = PortalService(pool=mock_pool)
        result = await service.get_preferences(1, current_user=client_context())

        assert isinstance(result, dict)
        assert result["email_notifications"] is True  # Default
        assert result["whatsapp_notifications"] is True  # Default
        assert result["language"] == "en"  # Default
        assert result["timezone"] == "Asia/Jakarta"  # Default

    @pytest.mark.asyncio
    async def test_update_preferences_with_mock(self):
        """Test update_preferences method with mocked database"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock existing preferences for get_preferences call
        mock_prefs = MagicMock()
        mock_prefs.__getitem__ = lambda self, key: {
            "email_notifications": True,
            "whatsapp_notifications": True,
            "language": "en",
            "timezone": "Asia/Jakarta",
        }.get(key)

        mock_conn.fetchrow.return_value = mock_prefs

        service = PortalService(pool=mock_pool)
        result = await service.update_preferences(
            1,
            {"email_notifications": False, "language": "id"},
            current_user=client_context(),
        )

        assert isinstance(result, dict)
        assert "email_notifications" in result
        assert "language" in result

    @pytest.mark.asyncio
    async def test_update_preferences_no_changes(self):
        """Test update_preferences with no valid fields"""
        from backend.services.portal.portal_service import PortalService

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock existing preferences
        mock_prefs = MagicMock()
        mock_prefs.__getitem__ = lambda self, key: {
            "email_notifications": True,
            "whatsapp_notifications": True,
            "language": "en",
            "timezone": "Asia/Jakarta",
        }.get(key)

        mock_conn.fetchrow.return_value = mock_prefs

        service = PortalService(pool=mock_pool)
        result = await service.update_preferences(
            1,
            {"invalid_field": "value"},
            current_user=client_context(),
        )

        # Should return existing preferences
        assert result["email_notifications"] is True
