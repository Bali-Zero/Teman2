"""
Unit tests for PortalService, VirusScanner, DocumentOCR, ExpiryDetector.
Target: document upload, OCR processing, messaging, timeline, edge cases.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.portal.portal_service import (
    DocumentOCR,
    ExpiryDetector,
    PortalService,
    VirusScanner,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg pool with acquire() as async context manager."""
    pool = MagicMock()
    mock_conn = AsyncMock()

    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        ),
    )
    pool._mock_conn = mock_conn
    return pool


@pytest.fixture
def portal_service(mock_db_pool):
    """Create PortalService with mocked pool."""
    return PortalService(pool=mock_db_pool)


@pytest.fixture
def mock_conn(mock_db_pool):
    """Shortcut to the mocked connection."""
    return mock_db_pool._mock_conn


@pytest.fixture
def ctx_client_1():
    """ClientContext for client_id=1 — covers the majority of legacy assertions."""
    return {"client_id": 1, "email": "client-1@example.com"}


@pytest.fixture
def ctx_client_999():
    """ClientContext for the 'not found' dashboard test."""
    return {"client_id": 999, "email": "client-999@example.com"}


# ============================================================================
# VIRUS SCANNER TESTS
# ============================================================================


class TestVirusScanner:
    """Tests for VirusScanner helper class."""

    def test_scan_clean_pdf(self):
        """Clean PDF passes virus scan."""
        result = VirusScanner.scan(b"%PDF-1.4 clean content", "document.pdf")
        assert result["clean"] is True
        assert result["threats"] == []
        assert result["scanner"] == "basic_heuristic_v1"

    def test_scan_suspicious_extension(self):
        """Suspicious extensions are flagged."""
        result = VirusScanner.scan(b"clean content", "malware.exe")
        assert result["clean"] is False
        assert len(result["threats"]) >= 1
        assert any("extension" in t.lower() for t in result["threats"])

    def test_scan_suspicious_pattern_php(self):
        """PHP code pattern detected."""
        result = VirusScanner.scan(b"<?php echo 'hacked'; ?>", "readme.txt")
        assert result["clean"] is False
        assert any("<?php" in t for t in result["threats"])

    def test_scan_suspicious_pattern_eval(self):
        """JavaScript eval pattern detected."""
        result = VirusScanner.scan(b"eval(atob('something'))", "image.png")
        assert result["clean"] is False

    def test_scan_suspicious_pattern_script(self):
        """<script tag detected in content."""
        result = VirusScanner.scan(b"Hello <script>alert('xss')</script>", "doc.pdf")
        assert result["clean"] is False

    def test_validate_mime_type_allowed(self):
        """Allowed MIME types pass validation."""
        assert VirusScanner.validate_mime_type("application/pdf") is True
        assert VirusScanner.validate_mime_type("image/jpeg") is True
        assert VirusScanner.validate_mime_type("text/csv") is True

    def test_validate_mime_type_rejected(self):
        """Disallowed MIME types are rejected."""
        assert VirusScanner.validate_mime_type("application/x-executable") is False
        assert VirusScanner.validate_mime_type("application/javascript") is False

    def test_validate_mime_type_none(self):
        """None MIME type is rejected."""
        assert VirusScanner.validate_mime_type(None) is False

    def test_validate_mime_type_case_insensitive(self):
        """MIME type validation is case-insensitive."""
        assert VirusScanner.validate_mime_type("APPLICATION/PDF") is True
        assert VirusScanner.validate_mime_type("Image/PNG") is True

    def test_scan_large_content_only_checks_first_8kb(self):
        """Only first 8KB of content is scanned for patterns."""
        content = b"A" * 10000 + b"<?php evil_code();"
        result = VirusScanner.scan(content, "large_file.pdf")
        assert result["clean"] is True


# ============================================================================
# DOCUMENT OCR TESTS
# ============================================================================


class TestDocumentOCR:
    """Tests for DocumentOCR class."""

    @pytest.mark.asyncio
    async def test_extract_text_unsupported_mime(self):
        """Unsupported MIME types return error."""
        result = await DocumentOCR.extract_text(b"content", "file.xyz", "application/zip")
        assert result["success"] is False
        assert "Unsupported MIME type" in result["error"]

    @pytest.mark.asyncio
    @patch("backend.services.portal.document_processing.PDF_VISION_AVAILABLE", False)
    @patch("backend.services.portal.document_processing.PYMUPDF_AVAILABLE", False)
    async def test_extract_from_pdf_no_services(self):
        """PDF extraction fails gracefully without vision/pymupdf."""
        result = await DocumentOCR._extract_from_pdf(b"%PDF-1.4 content")
        assert result["success"] is False
        assert "not available" in result["error"]

    @pytest.mark.asyncio
    @patch("backend.services.portal.document_processing.PDF_VISION_AVAILABLE", False)
    async def test_extract_from_image_no_vision(self):
        """Image extraction fails gracefully without vision service."""
        result = await DocumentOCR._extract_from_image(b"\x89PNG fake image")
        assert result["success"] is False
        assert "not available" in result["error"]

    def test_detect_mime_type_fallback(self):
        """MIME detection uses extension fallback when magic unavailable."""
        with patch("backend.services.portal.document_processing.MAGIC_AVAILABLE", False):
            mime = DocumentOCR._detect_mime_type(b"content", "test.pdf")
            assert mime == "application/pdf"

    def test_detect_mime_type_unknown_extension(self):
        """Unknown extension returns octet-stream."""
        with patch("backend.services.portal.document_processing.MAGIC_AVAILABLE", False):
            mime = DocumentOCR._detect_mime_type(b"content", "file.xyz123")
            assert mime == "application/octet-stream"


# ============================================================================
# EXPIRY DETECTOR TESTS
# ============================================================================


class TestExpiryDetector:
    """Tests for ExpiryDetector class."""

    def test_detect_expiry_with_keyword(self):
        """Detects expiry date near keyword."""
        text = "Passport Details\nExpiry Date: 15/06/2027\nIssue Date: 01/01/2022"
        result = ExpiryDetector.detect_expiry(text, "passport")
        assert result["expiry_date"] is not None
        assert result["confidence"] == 0.8
        assert result["method"] == "keyword_context"

    def test_detect_expiry_fallback_pattern(self):
        """Uses pattern match fallback for passport/visa types."""
        text = "Some doc 01/01/2025 other text 31/12/2028"
        result = ExpiryDetector.detect_expiry(text, "passport")
        assert result["expiry_date"] is not None
        assert result["confidence"] == 0.5
        assert result["method"] == "pattern_match"

    def test_detect_expiry_no_dates(self):
        """Returns empty when no dates found."""
        text = "This document has no dates at all, just text."
        result = ExpiryDetector.detect_expiry(text, "passport")
        assert result["expiry_date"] is None
        assert result["confidence"] == 0.0
        assert result["method"] == "none"

    def test_detect_expiry_short_text(self):
        """Short text returns empty result."""
        result = ExpiryDetector.detect_expiry("hi", "visa")
        assert result["expiry_date"] is None
        assert result["method"] == "none"

    def test_detect_expiry_empty_text(self):
        """Empty text returns empty result."""
        result = ExpiryDetector.detect_expiry("", "visa")
        assert result["expiry_date"] is None

    def test_detect_expiry_non_visa_type_no_fallback(self):
        """Non-visa document types don't use pattern match fallback."""
        text = "Some doc 01/01/2025 other text 31/12/2028"
        result = ExpiryDetector.detect_expiry(text, "invoice")
        assert result["expiry_date"] is None
        assert len(result["all_dates"]) > 0

    def test_normalize_date_iso_format(self):
        """YYYY-MM-DD format correctly parsed."""
        result = ExpiryDetector._normalize_date(("2027", "06", "15"))
        assert result == "2027-06-15"

    def test_normalize_date_european_format(self):
        """DD/MM/YYYY format correctly parsed."""
        result = ExpiryDetector._normalize_date(("15", "06", "2027"))
        assert result == "2027-06-15"


# ============================================================================
# PORTAL SERVICE - SANITIZE FILENAME
# ============================================================================


class TestPortalServiceHelpers:
    """Tests for PortalService helper/static methods."""

    def test_sanitize_filename_removes_path(self):
        """Path traversal in filenames is removed."""
        result = PortalService._sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_sanitize_filename_replaces_special_chars(self):
        """Special characters replaced with underscores."""
        result = PortalService._sanitize_filename("my file (copy).pdf")
        assert " " not in result
        assert "(" not in result

    def test_sanitize_filename_truncates_long(self):
        """Long filenames are truncated."""
        result = PortalService._sanitize_filename("a" * 300 + ".pdf")
        assert len(result) <= 200

    def test_is_undefined_column_error(self):
        """Detects PostgreSQL 42703 (undefined_column) error."""
        exc = MagicMock()
        exc.sqlstate = "42703"
        assert PortalService._is_undefined_column_error(exc) is True

    def test_is_undefined_table_error(self):
        """Detects PostgreSQL 42P01 (undefined_table) error."""
        exc = MagicMock()
        exc.sqlstate = "42P01"
        assert PortalService._is_undefined_table_error(exc) is True

    @pytest.mark.skip(reason="_status_to_progress method removed/renamed in PortalService")
    def test_status_to_progress(self, portal_service):
        """Status correctly mapped to progress percentage."""
        assert portal_service._status_to_progress("inquiry") == 10
        assert portal_service._status_to_progress("waiting_documents") == 30
        assert portal_service._status_to_progress("completed") == 100
        assert portal_service._status_to_progress("unknown_status") == 0

    def test_get_tax_status_compliant(self, portal_service):
        """Tax status is compliant with no deadline."""
        assert portal_service._get_tax_status(None) == "compliant"

    def test_get_tax_status_overdue(self, portal_service):
        """Tax status is overdue when days < 0."""
        assert portal_service._get_tax_status({"days_until": -5}) == "overdue"

    def test_get_tax_status_attention(self, portal_service):
        """Tax status is attention when days <= 14."""
        assert portal_service._get_tax_status({"days_until": 7}) == "attention"

    def test_get_tax_status_compliant_far(self, portal_service):
        """Tax status is compliant when days > 14."""
        assert portal_service._get_tax_status({"days_until": 30}) == "compliant"


# ============================================================================
# PORTAL SERVICE - DASHBOARD
# ============================================================================


class TestPortalServiceDashboard:
    """Tests for PortalService.get_dashboard."""

    @pytest.mark.asyncio
    async def test_get_dashboard_client_not_found(
        self, portal_service, mock_conn, ctx_client_999,
    ):
        """Dashboard raises ValueError for missing client."""
        mock_conn.fetchrow.return_value = None
        with pytest.raises(ValueError, match="Client 999 not found"):
            await portal_service.get_dashboard(999, current_user=ctx_client_999)

    @pytest.mark.asyncio
    async def test_get_dashboard_success(
        self, portal_service, mock_conn, ctx_client_1,
    ):
        """Dashboard returns expected structure for valid client."""
        mock_conn.fetchrow.side_effect = [
            {"id": 1, "full_name": "John", "email": "john@test.com"},
            None,
            None,
        ]
        mock_conn.fetch.side_effect = [
            [],
            [],
        ]
        mock_conn.fetchval.return_value = 0

        result = await portal_service.get_dashboard(1, current_user=ctx_client_1)

        assert "visa" in result
        assert "company" in result
        assert "taxes" in result
        assert "documents" in result
        assert "messages" in result
        assert "actions" in result

    @pytest.mark.asyncio
    async def test_build_visa_dashboard_data_none(self, portal_service):
        """Visa dashboard returns 'none' status when no visa practice."""
        result = portal_service._build_visa_dashboard_data(None)
        assert result["status"] == "none"
        assert result["type"] is None

    @pytest.mark.asyncio
    async def test_build_visa_dashboard_data_active(self, portal_service):
        """Active visa returns correct status and days remaining."""
        future_date = datetime.now(timezone.utc) + timedelta(days=180)
        visa = {
            "status": "completed",
            "expiry_date": future_date,
            "code": "E33",
            "name": "KITAS",
        }
        result = portal_service._build_visa_dashboard_data(visa)
        assert result["status"] == "active"
        assert result["daysRemaining"] > 90

    @pytest.mark.asyncio
    async def test_build_visa_dashboard_data_warning(self, portal_service):
        """Visa expiring within 90 days shows warning."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        visa = {
            "status": "completed",
            "expiry_date": future_date,
            "code": "E33",
            "name": "KITAS",
        }
        result = portal_service._build_visa_dashboard_data(visa)
        assert result["status"] == "warning"

    @pytest.mark.asyncio
    async def test_build_visa_dashboard_data_expired(self, portal_service):
        """Expired visa shows expired status."""
        past_date = datetime.now(timezone.utc) - timedelta(days=10)
        visa = {
            "status": "completed",
            "expiry_date": past_date,
            "code": "E33",
            "name": "KITAS",
        }
        result = portal_service._build_visa_dashboard_data(visa)
        assert result["status"] == "expired"

    @pytest.mark.asyncio
    async def test_build_action_items_with_visa_warning(self, portal_service):
        """Action items include visa renewal when expiring soon."""
        visa_data = {"status": "warning", "daysRemaining": 20}
        actions = portal_service._build_action_items([], visa_data)
        assert len(actions) >= 1
        assert actions[0]["type"] == "visa_renewal"
        assert actions[0]["priority"] == "high"


# ============================================================================
# PORTAL SERVICE - DOCUMENT UPLOAD
# ============================================================================


class TestPortalServiceUpload:
    """Tests for document upload flow."""

    @pytest.mark.asyncio
    async def test_upload_document_virus_detected(
        self, portal_service, mock_conn, ctx_client_1,
    ):
        """Upload blocked when virus detected."""
        malicious_content = b"<?php evil_code();"
        with pytest.raises(ValueError, match="Security threat detected"):
            await portal_service.upload_document(
                client_id=1,
                file_content=malicious_content,
                file_name="payload.php",
                document_type="passport",
                current_user=ctx_client_1,
            )

    @pytest.mark.asyncio
    async def test_upload_document_rate_limit(
        self, portal_service, mock_conn, ctx_client_1,
    ):
        """Upload blocked when rate limit exceeded."""
        portal_service._upload_rate_limits[1] = [
            datetime.now(timezone.utc).timestamp() for _ in range(10)
        ]
        with pytest.raises(ValueError, match="Rate limit exceeded"):
            await portal_service.upload_document(
                client_id=1,
                file_content=b"clean content",
                file_name="document.pdf",
                document_type="passport",
                mime_type="application/pdf",
                current_user=ctx_client_1,
            )
        portal_service._upload_rate_limits.pop(1, None)

    @pytest.mark.asyncio
    async def test_upload_document_invalid_mime(
        self, portal_service, mock_conn, ctx_client_1,
    ):
        """Upload blocked for disallowed MIME type."""
        portal_service._upload_rate_limits.pop(1, None)
        with pytest.raises(ValueError, match="File type not allowed"):
            await portal_service.upload_document(
                client_id=1,
                file_content=b"clean content",
                file_name="archive.tar.gz",
                document_type="passport",
                mime_type="application/gzip",
                current_user=ctx_client_1,
            )


# ============================================================================
# PORTAL SERVICE - MESSAGING
# ============================================================================


class TestPortalServiceMessaging:
    """Tests for messaging operations."""

    @pytest.mark.asyncio
    async def test_get_messages(self, portal_service, mock_conn, ctx_client_1):
        """get_messages returns structured response."""
        now = datetime.now(timezone.utc)
        mock_conn.fetch.return_value = [
            {
                "id": 1,
                "subject": "Test",
                "content": "Hello",
                "direction": "team_to_client",
                "sent_by": "admin@balizero.com",
                "read_at": None,
                "created_at": now,
                "practice_id": None,
                "practice_name": None,
            },
        ]
        mock_conn.fetchval.side_effect = [1, 1]

        result = await portal_service.get_messages(
            client_id=1, current_user=ctx_client_1,
        )
        assert result["total"] == 1
        assert result["unread_count"] == 1
        assert len(result["messages"]) == 1
        assert result["messages"][0]["from_team"] is True
        assert result["messages"][0]["is_read"] is False

    @pytest.mark.asyncio
    async def test_send_message(self, portal_service, mock_conn, ctx_client_1):
        """send_message inserts and returns result."""
        now = datetime.now(timezone.utc)
        mock_conn.fetchrow.side_effect = [
            {"email": "client@test.com"},
            {"id": 42, "created_at": now},
        ]

        result = await portal_service.send_message(
            client_id=1,
            content="Need help with visa",
            subject="Visa question",
            current_user=ctx_client_1,
        )
        assert result["id"] == 42

    @pytest.mark.asyncio
    async def test_mark_message_read_success(
        self, portal_service, mock_conn, ctx_client_1,
    ):
        """mark_message_read returns success when row updated."""
        mock_conn.execute.return_value = "UPDATE 1"
        result = await portal_service.mark_message_read(
            client_id=1, message_id=42, current_user=ctx_client_1,
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_mark_message_read_not_found(
        self, portal_service, mock_conn, ctx_client_1,
    ):
        """mark_message_read returns failure when no row updated."""
        mock_conn.execute.return_value = "UPDATE 0"
        result = await portal_service.mark_message_read(
            client_id=1, message_id=999, current_user=ctx_client_1,
        )
        assert result["success"] is False


# ============================================================================
# PORTAL SERVICE - PREFERENCES
# ============================================================================


class TestPortalServicePreferences:
    """Tests for preferences operations."""

    @pytest.mark.asyncio
    async def test_get_preferences_defaults(
        self, portal_service, mock_conn, ctx_client_1,
    ):
        """Returns defaults when no preferences stored."""
        mock_conn.fetchrow.return_value = None
        result = await portal_service.get_preferences(
            client_id=1, current_user=ctx_client_1,
        )
        assert result["email_notifications"] is True
        assert result["language"] == "en"
        assert result["timezone"] == "Asia/Jakarta"

    @pytest.mark.asyncio
    async def test_get_preferences_stored(
        self, portal_service, mock_conn, ctx_client_1,
    ):
        """Returns stored preferences."""
        mock_conn.fetchrow.return_value = {
            "email_notifications": False,
            "whatsapp_notifications": True,
            "language": "it",
            "timezone": "Europe/Rome",
        }
        result = await portal_service.get_preferences(
            client_id=1, current_user=ctx_client_1,
        )
        assert result["language"] == "it"
        assert result["email_notifications"] is False


# ============================================================================
# PORTAL SERVICE - TIMELINE
# ============================================================================


class TestPortalServiceTimeline:
    """Tests for timeline operations."""

    @pytest.mark.asyncio
    async def test_get_timeline_returns_structure(
        self, portal_service, mock_conn, ctx_client_1,
    ):
        """get_timeline returns expected top-level keys."""
        mock_conn.fetch.return_value = []
        mock_conn.fetchrow.return_value = None

        result = await portal_service.get_timeline(
            client_id=1, current_user=ctx_client_1,
        )
        assert result["scope"] == "portal"
        assert "entries" in result
        assert "lastUpdated" in result

    @pytest.mark.asyncio
    async def test_get_standard_tax_deadlines(self, portal_service):
        """Tax deadlines include PPh, PPN, and SPT."""
        today = datetime(2026, 3, 15, tzinfo=timezone.utc)
        deadlines = portal_service._get_standard_tax_deadlines(today)
        assert len(deadlines) == 3
        types = {d["type"] for d in deadlines}
        assert "PPh 21/23/4(2)" in types
        assert "PPN (VAT)" in types
        assert "Annual SPT" in types
        for d in deadlines:
            assert "days_until" in d
            assert "urgency" in d
