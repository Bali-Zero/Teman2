"""
Unit tests for backend/services/portal/portal_service.py
Covers: VirusScanner, DocumentOCR, ExpiryDetector, PortalService
(dashboard, visa, companies, tax, documents, messages, preferences)
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Standard asyncpg pool mock."""
    pool = MagicMock()
    conn = AsyncMock()

    class _Ctx:
        async def __aenter__(self) -> AsyncMock:
            return conn

        async def __aexit__(self, *args: Any) -> None:
            pass

    pool.acquire = MagicMock(return_value=_Ctx())
    return pool, conn


# ═══════════════════════════════════════════════════════════════════════════════
# VirusScanner
# ═══════════════════════════════════════════════════════════════════════════════


class TestVirusScanner:
    def setup_method(self) -> None:
        from backend.services.portal.portal_service import VirusScanner

        self.scanner = VirusScanner

    def test_clean_pdf(self) -> None:
        result = self.scanner.scan(b"%PDF-1.4 clean content", "document.pdf")
        assert result["clean"] is True
        assert result["threats"] == []
        assert result["scanner"] == "basic_heuristic_v1"

    def test_suspicious_extension_exe(self) -> None:
        result = self.scanner.scan(b"content", "malware.exe")
        assert result["clean"] is False
        assert any("extension" in t.lower() for t in result["threats"])

    def test_suspicious_extension_bat(self) -> None:
        result = self.scanner.scan(b"content", "script.bat")
        assert result["clean"] is False

    def test_suspicious_extension_php(self) -> None:
        result = self.scanner.scan(b"content", "shell.php")
        assert result["clean"] is False

    def test_suspicious_pattern_eval(self) -> None:
        result = self.scanner.scan(b"eval(base64_decode('abc'))", "page.html")
        assert result["clean"] is False
        assert len(result["threats"]) >= 1

    def test_suspicious_pattern_php(self) -> None:
        result = self.scanner.scan(b"<?php system('cmd');", "file.txt")
        assert result["clean"] is False

    def test_suspicious_pattern_script(self) -> None:
        result = self.scanner.scan(b"<script>alert(1)</script>", "page.html")
        assert result["clean"] is False

    def test_suspicious_pattern_javascript(self) -> None:
        result = self.scanner.scan(b"javascript:void(0)", "link.html")
        assert result["clean"] is False

    def test_clean_image(self) -> None:
        result = self.scanner.scan(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "photo.png")
        assert result["clean"] is True

    def test_validate_mime_type_allowed(self) -> None:
        assert self.scanner.validate_mime_type("application/pdf") is True
        assert self.scanner.validate_mime_type("image/jpeg") is True
        assert self.scanner.validate_mime_type("image/png") is True
        assert self.scanner.validate_mime_type("text/csv") is True

    def test_validate_mime_type_disallowed(self) -> None:
        assert self.scanner.validate_mime_type("application/x-executable") is False
        assert self.scanner.validate_mime_type("application/javascript") is False

    def test_validate_mime_type_none(self) -> None:
        assert self.scanner.validate_mime_type(None) is False

    def test_validate_mime_type_case_insensitive(self) -> None:
        assert self.scanner.validate_mime_type("Application/PDF") is True


# ═══════════════════════════════════════════════════════════════════════════════
# DocumentOCR
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocumentOCR:
    def setup_method(self) -> None:
        from backend.services.portal.portal_service import DocumentOCR

        self.ocr = DocumentOCR

    @pytest.mark.asyncio
    async def test_extract_text_unsupported_mime(self) -> None:
        result = await self.ocr.extract_text(b"content", "file.xyz", "application/xyz")
        assert result["success"] is False
        assert "Unsupported" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_text_none_mime_uses_detection(self) -> None:
        # With unknown extension and no mime -> fallback detection -> unsupported
        result = await self.ocr.extract_text(b"content", "file.xyz")
        assert result["success"] is False

    def test_detect_mime_type_with_extension(self) -> None:
        # Use real PDF magic bytes so libmagic (when available) detects application/pdf
        result = self.ocr._detect_mime_type(b"%PDF-1.4", "test.pdf")
        assert result == "application/pdf"

    def test_detect_mime_type_unknown(self) -> None:
        # Empty bytes + unknown extension: libmagic returns x-empty, fallback returns octet-stream
        result = self.ocr._detect_mime_type(b"", "file.zzz")
        assert result in ("application/octet-stream", "application/x-empty", "inode/x-empty")

    @pytest.mark.asyncio
    async def test_extract_from_pdf_no_vision(self) -> None:
        with patch("backend.services.portal.document_processing.PDF_VISION_AVAILABLE", False):
            with patch("backend.services.portal.document_processing.PYMUPDF_AVAILABLE", False):
                result = await self.ocr._extract_from_pdf(b"%PDF-content")
                assert result["success"] is False
                assert "not available" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_from_image_no_vision(self) -> None:
        with patch("backend.services.portal.document_processing.PDF_VISION_AVAILABLE", False):
            result = await self.ocr._extract_from_image(b"\x89PNG")
            assert result["success"] is False
            assert "not available" in result["error"]

    def test_image_to_base64(self) -> None:
        from PIL import Image

        img = Image.new("RGB", (10, 10), "red")
        result = self.ocr._image_to_base64(img)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_extract_text_exception_handling(self) -> None:
        with patch(
            "backend.services.portal.portal_service.DocumentOCR._extract_from_pdf",
            new_callable=AsyncMock,
            side_effect=Exception("boom"),
        ):
            result = await self.ocr.extract_text(b"content", "test.pdf", "application/pdf")
            assert result["success"] is False
            assert "failed" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════════
# ExpiryDetector
# ═══════════════════════════════════════════════════════════════════════════════


class TestExpiryDetector:
    def setup_method(self) -> None:
        from backend.services.portal.portal_service import ExpiryDetector

        self.detector = ExpiryDetector

    def test_empty_text(self) -> None:
        result = self.detector.detect_expiry("", "passport")
        assert result["expiry_date"] is None
        assert result["method"] == "none"

    def test_short_text(self) -> None:
        result = self.detector.detect_expiry("short", "passport")
        assert result["expiry_date"] is None

    def test_keyword_context_detection(self) -> None:
        text = "Passport Number: A1234567\nExpiry Date: 15/06/2028\nIssue Date: 15/06/2018"
        result = self.detector.detect_expiry(text, "passport")
        assert result["expiry_date"] is not None
        assert result["method"] == "keyword_context"
        assert result["confidence"] == 0.8

    def test_pattern_match_fallback(self) -> None:
        text = "Document details\nDate: 01/01/2030\nAnother date: 15/06/2025"
        result = self.detector.detect_expiry(text, "passport")
        # For passport type, should find dates via pattern_match
        assert result["method"] in ("keyword_context", "pattern_match")

    def test_visa_document_type(self) -> None:
        text = "KITAS card\nDate issued 01/01/2025\nValid 01/01/2027"
        result = self.detector.detect_expiry(text, "kitas")
        assert result["expiry_date"] is not None

    def test_non_expiry_document_no_keywords(self) -> None:
        text = "Receipt #1234\nDate: 15/06/2025\nAmount: Rp 1,000,000"
        result = self.detector.detect_expiry(text, "receipt")
        # No keyword match, doc type not in expiry types
        assert result["method"] in ("none", "pattern_match")

    def test_all_dates_populated(self) -> None:
        text = "Date1: 01/01/2025\nDate2: 15/06/2028\nDate3: 2024-12-31"
        result = self.detector.detect_expiry(text, "other")
        assert len(result["all_dates"]) >= 2

    def test_normalize_date_yyyy_mm_dd(self) -> None:
        result = self.detector._normalize_date(("2025", "6", "15"))
        assert result == "2025-06-15"

    def test_normalize_date_dd_mm_yyyy(self) -> None:
        result = self.detector._normalize_date(("15", "6", "2025"))
        assert result is not None
        assert "2025" in result

    def test_normalize_date_invalid(self) -> None:
        result = self.detector._normalize_date(("x", "y", "z"))
        assert result is None

    def test_normalize_date_two_digit_year(self) -> None:
        result = self.detector._normalize_date(("15", "6", "28"))
        assert result is not None
        assert "2028" in result

    def test_berlaku_keyword(self) -> None:
        text = "Berlaku sampai 15/06/2028\nNomor: 12345"
        result = self.detector.detect_expiry(text, "visa")
        assert result["expiry_date"] is not None


# ═══════════════════════════════════════════════════════════════════════════════
# PortalService — static helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestPortalServiceHelpers:
    def setup_method(self) -> None:
        from backend.services.portal.portal_service import PortalService

        self.cls = PortalService

    def test_sanitize_filename_basic(self) -> None:
        assert self.cls._sanitize_filename("test.pdf") == "test.pdf"

    def test_sanitize_filename_path_traversal(self) -> None:
        result = self.cls._sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_sanitize_filename_backslash(self) -> None:
        result = self.cls._sanitize_filename("C:\\Users\\file.txt")
        assert "\\" not in result
        assert result == "file.txt"

    def test_sanitize_filename_long(self) -> None:
        long_name = "a" * 300 + ".pdf"
        result = self.cls._sanitize_filename(long_name)
        assert len(result) <= 200

    def test_sanitize_filename_unsafe_chars(self) -> None:
        result = self.cls._sanitize_filename("file name (1).pdf")
        assert "(" not in result  # parentheses replaced by _

    def test_is_undefined_column_error(self) -> None:
        exc = MagicMock()
        exc.sqlstate = "42703"
        assert self.cls._is_undefined_column_error(exc) is True

    def test_is_undefined_column_error_false(self) -> None:
        exc = MagicMock()
        exc.sqlstate = "12345"
        assert self.cls._is_undefined_column_error(exc) is False

    def test_is_undefined_table_error(self) -> None:
        exc = MagicMock()
        exc.sqlstate = "42P01"
        assert self.cls._is_undefined_table_error(exc) is True

    def test_classify_document_immigration(self) -> None:
        assert self.cls._classify_document_category("kitas", "kitas_card.pdf") == "immigration"

    def test_classify_document_personal(self) -> None:
        assert self.cls._classify_document_category("passport", "passport.jpg") == "personal"

    def test_classify_document_pma(self) -> None:
        assert self.cls._classify_document_category("akta_pendirian", "akta.pdf") == "pma"

    def test_classify_document_tax(self) -> None:
        assert self.cls._classify_document_category("tax_return", "spt_2025.pdf") == "tax"

    def test_classify_document_family(self) -> None:
        assert self.cls._classify_document_category("birth certificate", "birth.pdf") == "family"

    def test_classify_document_other(self) -> None:
        assert self.cls._classify_document_category("unknown", "random.pdf") == "other"

    def test_get_drive_folder_immigration(self) -> None:
        assert self.cls._get_drive_folder_for_category("immigration") == "01_Immigration"

    def test_get_drive_folder_personal(self) -> None:
        assert self.cls._get_drive_folder_for_category("personal") == "00_Profile"

    def test_get_drive_folder_pma(self) -> None:
        assert self.cls._get_drive_folder_for_category("pma") == "02_Company"

    def test_get_drive_folder_unknown(self) -> None:
        assert self.cls._get_drive_folder_for_category("unknown") == "99_Misc"


# ═══════════════════════════════════════════════════════════════════════════════
# PortalService — dashboard building helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestPortalServiceDashboardHelpers:
    def setup_method(self) -> None:
        from backend.services.portal.portal_service import PortalService

        pool = MagicMock()
        self.service = PortalService(pool)

    def test_build_visa_dashboard_no_practice(self) -> None:
        result = self.service._build_visa_dashboard_data(None)
        assert result["status"] == "none"
        assert result["type"] is None

    def test_build_visa_dashboard_active(self) -> None:
        future = datetime.now(tz=timezone.utc) + timedelta(days=200)
        visa = {
            "status": "completed",
            "expiry_date": future,
            "code": "C316",
            "name": "KITAS",
        }
        result = self.service._build_visa_dashboard_data(visa)
        assert result["status"] == "active"
        assert result["daysRemaining"] > 90

    def test_build_visa_dashboard_warning(self) -> None:
        future = datetime.now(tz=timezone.utc) + timedelta(days=30)
        visa = {
            "status": "completed",
            "expiry_date": future,
            "code": "C316",
            "name": "KITAS",
        }
        result = self.service._build_visa_dashboard_data(visa)
        assert result["status"] == "warning"

    def test_build_visa_dashboard_expired(self) -> None:
        past = datetime.now(tz=timezone.utc) - timedelta(days=10)
        visa = {
            "status": "completed",
            "expiry_date": past,
            "code": None,
            "name": "KITAS",
        }
        result = self.service._build_visa_dashboard_data(visa)
        assert result["status"] == "expired"

    def test_build_visa_dashboard_pending(self) -> None:
        visa = {
            "status": "in_progress",
            "expiry_date": None,
            "code": "C316",
            "name": "KITAS",
        }
        result = self.service._build_visa_dashboard_data(visa)
        assert result["status"] == "pending"

    def test_get_tax_status_compliant(self) -> None:
        assert self.service._get_tax_status(None) == "compliant"

    def test_get_tax_status_attention(self) -> None:
        deadline = {"days_until": 10}
        assert self.service._get_tax_status(deadline) == "attention"

    def test_get_tax_status_overdue(self) -> None:
        deadline = {"days_until": -5}
        assert self.service._get_tax_status(deadline) == "overdue"

    def test_get_tax_status_compliant_far(self) -> None:
        deadline = {"days_until": 30}
        assert self.service._get_tax_status(deadline) == "compliant"

    def test_build_action_items_empty(self) -> None:
        visa_data = {"status": "active", "daysRemaining": 200}
        result = self.service._build_action_items([], visa_data)
        assert result == []

    def test_build_action_items_visa_warning(self) -> None:
        visa_data = {"status": "warning", "daysRemaining": 25}
        result = self.service._build_action_items([], visa_data)
        assert len(result) == 1
        assert result[0]["type"] == "visa_renewal"
        assert result[0]["priority"] == "high"

    def test_build_action_items_visa_warning_medium(self) -> None:
        visa_data = {"status": "warning", "daysRemaining": 60}
        result = self.service._build_action_items([], visa_data)
        assert result[0]["priority"] == "medium"

    def test_build_action_items_missing_docs(self) -> None:
        visa_data = {"status": "active", "daysRemaining": 200}
        items = [
            {
                "id": 1,
                "practice_name": "KITAS Application",
                "missing_documents": ["passport", "photo"],
                "status": "waiting_documents",
            },
        ]
        result = self.service._build_action_items(items, visa_data)
        assert len(result) == 1
        assert result[0]["type"] == "missing_documents"
        assert result[0]["priority"] == "high"

    def test_build_action_items_max_5(self) -> None:
        visa_data = {"status": "warning", "daysRemaining": 25}
        items = [
            {"id": i, "practice_name": f"P{i}", "missing_documents": ["doc"], "status": "in_progress"}
            for i in range(10)
        ]
        result = self.service._build_action_items(items, visa_data)
        assert len(result) <= 5


# ═══════════════════════════════════════════════════════════════════════════════
# PortalService — async methods (get_dashboard, get_visa_status, etc.)
# ═══════════════════════════════════════════════════════════════════════════════


def _ctx(cid: int) -> dict:
    """Build a minimal ClientContext for a client viewing its own data."""
    return {"client_id": cid, "email": f"client-{cid}@example.com"}


class TestPortalServiceDashboard:
    @pytest.mark.asyncio
    async def test_get_dashboard_client_not_found(self, mock_pool: tuple) -> None:
        from backend.services.portal.portal_service import PortalService

        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value=None)

        service = PortalService(pool)
        with pytest.raises(ValueError, match="not found"):
            await service.get_dashboard(999, current_user=_ctx(999))

    @pytest.mark.asyncio
    async def test_get_dashboard_success(self, mock_pool: tuple) -> None:
        from backend.services.portal.portal_service import PortalService

        pool, conn = mock_pool

        # Client
        client_row = {"id": 1, "full_name": "John Doe", "email": "john@example.com"}
        # Visa
        visa_row = None
        # Companies
        companies = []
        # Action items
        action_items = []
        # Unread
        unread = 3
        # Doc counts
        doc_counts = {"total": 5, "pending": 1}

        # fetchrow returns: client, visa, doc_counts
        conn.fetchrow = AsyncMock(side_effect=[client_row, visa_row, doc_counts])
        # fetch returns: companies, action_items
        conn.fetch = AsyncMock(side_effect=[companies, action_items])
        # fetchval returns: unread
        conn.fetchval = AsyncMock(return_value=unread)

        service = PortalService(pool)
        result = await service.get_dashboard(1, current_user=_ctx(1))

        assert result["visa"]["status"] == "none"
        assert result["company"]["totalCompanies"] == 0
        assert result["messages"]["unread"] == 3
        assert result["documents"]["total"] == 5


class TestPortalServiceVisaStatus:
    @pytest.mark.asyncio
    async def test_get_visa_status_client_not_found(self, mock_pool: tuple) -> None:
        from backend.services.portal.portal_service import PortalService

        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value=None)

        service = PortalService(pool)
        with pytest.raises(ValueError, match="not found"):
            await service.get_visa_status(999, current_user=_ctx(999))


class TestPortalServiceCompanies:
    @pytest.mark.asyncio
    async def test_get_companies(self, mock_pool: tuple) -> None:
        from backend.services.portal.portal_service import PortalService

        pool, conn = mock_pool
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "company_id": 10,
                    "company_name": "PT Test",
                    "company_type": "PMA",
                    "role": "director",
                    "is_primary": True,
                    "ownership_percentage": 75.0,
                    "nib": "1234567890123",
                    "npwp_company": "01.234.567.8-901.000",
                    "kbli_code": "62010",
                    "company_status": "active",
                    "link_status": "active",
                },
            ],
        )

        service = PortalService(pool)
        result = await service.get_companies(1, current_user=_ctx(1))
        assert len(result) == 1
        assert result[0]["name"] == "PT Test"
        assert result[0]["isPrimary"] is True
        assert result[0]["ownership_pct"] == 75.0

    @pytest.mark.asyncio
    async def test_get_company_detail_not_found(self, mock_pool: tuple) -> None:
        from backend.services.portal.portal_service import PortalService

        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value=None)

        service = PortalService(pool)
        with pytest.raises(ValueError, match="not found"):
            await service.get_company_detail(1, 999, current_user=_ctx(1))
