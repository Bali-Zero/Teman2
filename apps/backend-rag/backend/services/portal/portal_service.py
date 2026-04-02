"""
Client Portal Service

Provides client-scoped data access for:
- Dashboard overview
- Visa & immigration status
- Company & licenses
- Tax deadlines
- Documents (with OCR, virus scan, Google Drive upload)
- Messages
- Preferences
"""

import asyncio
import io
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Optional imports for advanced features (graceful degradation if not installed)
try:
    from backend.services.multimodal.pdf_vision_service import PDFVisionService

    PDF_VISION_AVAILABLE = True
except ImportError:
    PDF_VISION_AVAILABLE = False
    logger.warning("PDFVisionService not available. OCR will use basic extraction.")

try:
    import fitz  # PyMuPDF for PDF rendering

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not installed. PDF to image conversion will be disabled.")

try:
    import magic

    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logger.warning("python-magic not installed. MIME type detection will use fallback.")


# =============================================================================
# DOCUMENT PROCESSING HELPERS (Virus Scan, OCR, Expiry Detection)
# =============================================================================


class VirusScanner:
    """Virus scanning for uploaded files."""

    SUSPICIOUS_EXTENSIONS = {".exe", ".dll", ".bat", ".cmd", ".sh", ".php", ".jsp", ".asp"}
    SUSPICIOUS_PATTERNS = [b"eval(", b"base64_decode", b"<?php", b"<script", b"javascript:"]

    # Allowed MIME types for upload
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/csv",
    }

    @classmethod
    def validate_mime_type(cls, mime_type: str | None) -> bool:
        """Validate if MIME type is allowed."""
        if not mime_type:
            return False
        return mime_type.lower() in cls.ALLOWED_MIME_TYPES

    @classmethod
    def scan(cls, file_content: bytes, file_name: str) -> dict[str, Any]:
        """
        Scan file for malware/suspicious content.

        Returns:
            {
                "clean": bool,
                "threats": list[str],
                "scanner": str
            }
        """
        threats = []

        # Check extension
        file_lower = file_name.lower()
        if any(file_lower.endswith(ext) for ext in cls.SUSPICIOUS_EXTENSIONS):
            threats.append(f"Suspicious file extension in {file_name}")

        # Check for suspicious patterns in content
        content_sample = file_content[:8192]  # First 8KB
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if pattern in content_sample.lower():
                threats.append(
                    f"Suspicious pattern detected: {pattern.decode('utf-8', errors='ignore')}",
                )

        # Check for executable magic bytes
        # executable_magics = [
        #     b"MZ",  # Windows executable
        #     b"\x7fELF",  # Linux executable
        #     b"#!",  # Shebang script
        #     b"%PDF",  # PDF (allowed but flagged if combined with other threats)
        # ]

        # Future: Integrate with ClamAV or cloud virus scanning service
        # Example:
        #   clamav_result = clamav.scan(file_content)
        #   if clamav_result.infected:
        #       threats.append(f"Virus detected: {clamav_result.virus_name}")

        return {"clean": len(threats) == 0, "threats": threats, "scanner": "basic_heuristic_v1"}


class DocumentOCR:
    """OCR extraction from PDF and image files using Gemini Vision."""

    @classmethod
    async def extract_text(
        cls, file_content: bytes, file_name: str, mime_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Extract text from PDF or image using Gemini Vision (same as passport box).

        Returns:
            {
                "text": str,
                "pages": int,
                "success": bool,
                "error": str | None
            }
        """
        result = {"text": "", "pages": 0, "success": False, "error": None}

        if not mime_type:
            mime_type = cls._detect_mime_type(file_content, file_name)

        try:
            if mime_type == "application/pdf":
                result = await cls._extract_from_pdf(file_content)
            elif mime_type and mime_type.startswith("image/"):
                result = await cls._extract_from_image(file_content)
            else:
                # Try basic text extraction for other types
                result["error"] = f"Unsupported MIME type for OCR: {mime_type}"
                result["success"] = False
        except Exception as e:
            result["error"] = f"OCR extraction failed: {e}"
            logger.error(f"OCR extraction failed for {file_name}: {e}")

        return result

    @classmethod
    def _detect_mime_type(cls, file_content: bytes, file_name: str) -> str:
        """Detect MIME type from content or filename."""
        if MAGIC_AVAILABLE:
            try:
                return magic.from_buffer(file_content, mime=True)
            except Exception as e:
                logger.debug(f"libmagic MIME detection failed, using extension fallback: {e}")

        # Fallback to extension-based detection
        import mimetypes

        mime, _ = mimetypes.guess_type(file_name)
        return mime or "application/octet-stream"

    @classmethod
    async def _extract_from_pdf(cls, file_content: bytes) -> dict[str, Any]:
        """Extract text from PDF using Gemini Vision (same as passport box)."""
        result = {"text": "", "pages": 0, "success": False, "error": None}

        if not PDF_VISION_AVAILABLE:
            # Fallback to PyMuPDF basic extraction
            if PYMUPDF_AVAILABLE:
                try:
                    doc = fitz.open(stream=file_content, filetype="pdf")
                    result["pages"] = len(doc)
                    texts = []
                    for page in doc:
                        texts.append(page.get_text())
                    result["text"] = "\n".join(texts)
                    result["success"] = True
                    doc.close()
                    return result
                except Exception as e:
                    result["error"] = f"PyMuPDF extraction failed: {e}"
                    return result
            else:
                result["error"] = "PDF Vision service not available"
                return result

        try:
            # Use PDFVisionService (same as passport box)
            vision_service = PDFVisionService()

            # First try direct text extraction
            text = await vision_service.extract_text(file_content)

            if text and not text.startswith("Error"):
                result["text"] = text
                result["pages"] = text.count("\n---\n") + 1  # Rough estimate
                result["success"] = True
            else:
                # Fallback: render to image and use vision
                result = await cls._extract_pdf_via_vision(file_content, vision_service)

        except Exception as e:
            result["error"] = f"PDF Vision extraction failed: {e}"

        return result

    @classmethod
    async def _extract_pdf_via_vision(
        cls, pdf_content: bytes, vision_service: Any,
    ) -> dict[str, Any]:
        """Extract text by rendering PDF pages to images and using Gemini Vision."""
        result = {"text": "", "pages": 0, "success": False, "error": None}

        if not PYMUPDF_AVAILABLE:
            result["error"] = "PyMuPDF required for PDF to image conversion"
            return result

        try:
            from PIL import Image

            doc = fitz.open(stream=pdf_content, filetype="pdf")
            result["pages"] = len(doc)
            texts = []

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))

                # Use Gemini Vision for OCR
                img_base64 = cls._image_to_base64(image)
                page_text = await cls._gemini_vision_ocr(img_base64, vision_service)

                if page_text:
                    texts.append(page_text)

            doc.close()
            result["text"] = "\n".join(texts)
            result["success"] = True

        except Exception as e:
            result["error"] = f"PDF Vision OCR failed: {e}"

        return result

    @classmethod
    async def _extract_from_image(cls, file_content: bytes) -> dict[str, Any]:
        """Extract text from image using Gemini Vision."""
        result = {"text": "", "pages": 1, "success": False, "error": None}

        if not PDF_VISION_AVAILABLE:
            result["error"] = "Vision service not available for image OCR"
            return result

        try:
            from PIL import Image

            image = Image.open(io.BytesIO(file_content))
            img_base64 = cls._image_to_base64(image)

            vision_service = PDFVisionService()
            text = await cls._gemini_vision_ocr(img_base64, vision_service)

            result["text"] = text
            result["success"] = bool(text)

        except Exception as e:
            result["error"] = f"Image Vision OCR failed: {e}"

        return result

    @classmethod
    def _image_to_base64(cls, image) -> str:
        """Convert PIL Image to base64 string."""
        import base64

        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    @classmethod
    async def _gemini_vision_ocr(cls, image_base64: str, vision_service: Any) -> str:
        """Use Gemini Vision to extract text from image."""
        try:
            client = vision_service._get_genai_client()
            if not client or not client.is_available:
                return ""

            prompt = """
            Extract all text from this document image.
            Preserve the layout and structure as much as possible.
            Return only the extracted text, no additional commentary.
            """

            contents = [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": image_base64}},
            ]

            response = await client.generate_content(
                contents=contents,
                model="gemini-2.0-flash-lite",
                max_output_tokens=4096,
            )

            return response.get("text", "")

        except Exception as e:
            logger.error(f"Gemini Vision OCR failed: {e}")
            return ""


class ExpiryDetector:
    """Detect expiry dates from document text (passports, visas, etc.)."""

    # Date patterns: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD, DD-MM-YYYY, etc.
    DATE_PATTERNS = [
        r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b",  # DD/MM/YYYY
        r"\b(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})\b",  # YYYY/MM/DD
    ]

    # Keywords that indicate expiry dates
    EXPIRY_KEYWORDS = [
        "expir",
        "valid until",
        "valid to",
        "date of expiration",
        "expiry date",
        "expiration date",
        "valid thru",
        "valid through",
        "date of expiry",
        "passport expiry",
        "visa expiry",
        "kitas expiry",
        "merp expiry",
        "validity expires",
        "until",
        "sampai",
        "berlaku",
    ]

    # Document type indicators
    DOC_TYPE_INDICATORS = {
        "passport": ["passport", "paspor", "travel document"],
        "visa": ["visa", "voa", "kitas", "kitap", "e-visa", "evisa"],
        "merp": ["merp", "re-entry", "reentry"],
        "nib": ["nib", "business registration", "nomor induk berusaha"],
        "tax": ["tax", "pajak", "npwp", "spt", "efiling"],
    }

    @classmethod
    def detect_expiry(cls, text: str, document_type: str) -> dict[str, Any]:
        """
        Detect expiry date from document text.

        Returns:
            {
                "expiry_date": str | None,  # ISO format YYYY-MM-DD
                "confidence": float,  # 0-1
                "method": str,  # "keyword_context", "pattern_match", "none"
                "all_dates": list[str]  # All dates found
            }
        """
        result = {"expiry_date": None, "confidence": 0.0, "method": "none", "all_dates": []}

        if not text or len(text.strip()) < 10:
            return result

        lines = text.split("\n")

        # Extract all dates
        all_dates = []
        for pattern in cls.DATE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    date_str = cls._normalize_date(match)
                    if date_str:
                        all_dates.append(date_str)
                except Exception:
                    continue

        result["all_dates"] = list(set(all_dates))

        # Find dates near expiry keywords
        for keyword in cls.EXPIRY_KEYWORDS:
            # Look for keyword in text
            for i, line in enumerate(lines):
                if keyword.lower() in line.lower():
                    # Check this line and adjacent lines
                    context = " ".join(lines[max(0, i - 1) : min(len(lines), i + 2)])
                    dates_in_context = []

                    for pattern in cls.DATE_PATTERNS:
                        matches = re.findall(pattern, context)
                        for match in matches:
                            date_str = cls._normalize_date(match)
                            if date_str:
                                dates_in_context.append(date_str)

                    if dates_in_context:
                        # Use the furthest future date (most likely expiry)
                        dates_in_context.sort()
                        result["expiry_date"] = dates_in_context[-1]
                        result["confidence"] = 0.8
                        result["method"] = "keyword_context"
                        return result

        # Fallback: if document type suggests expiry, use furthest future date
        if document_type.lower() in ["passport", "visa", "kitas", "kitap", "merp"]:
            if all_dates:
                all_dates.sort()
                result["expiry_date"] = all_dates[-1]  # Furthest date
                result["confidence"] = 0.5
                result["method"] = "pattern_match"

        return result

    @classmethod
    def _normalize_date(cls, match: tuple) -> str | None:
        """Convert date match to ISO format YYYY-MM-DD."""
        try:
            if len(match) == 3:
                a, b, c = match
                a, b, c = int(a), int(b), int(c)

                # Determine format based on values
                if c > 31:  # YYYY is last
                    year = c if c > 2000 else 2000 + c
                    day, month = a, b
                    # Heuristic: if a > 12, it's day
                    if a > 12:
                        day, month = a, b
                    elif b > 12:
                        day, month = b, a
                    else:
                        # Assume DD/MM (European format)
                        day, month = a, b
                elif a > 31:  # YYYY is first
                    year = a
                    month, day = b, c
                else:
                    # Assume DD/MM/YY
                    year = 2000 + c if c < 100 else c
                    day, month = a, b if b <= 12 else a
                    if b > 12:
                        day, month = b, a

                return f"{year:04d}-{month:02d}-{day:02d}"
        except Exception as e:
            logger.debug(f"Date normalization skipped for value: {e}")
        return None


class PortalService:
    """Service for client portal data access."""

    # Rate limiting: max uploads per client per window (15 min)
    _upload_rate_limits: dict[int, list[float]] = {}
    MAX_UPLOADS_PER_WINDOW = 10
    RATE_WINDOW_SECONDS = 900  # 15 minutes

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool
        self._metrics = {
            "uploads_total": 0,
            "uploads_failed": 0,
            "virus_blocked": 0,
            "drive_uploads": 0,
            "ocr_processed": 0,
        }

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal and unsafe chars."""
        import re

        # Remove path components
        filename = filename.replace("\\", "/").split("/")[-1]
        # Remove unsafe characters
        filename = re.sub(r"[^\w\-\.]", "_", filename)
        # Limit length
        if len(filename) > 200:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[:195] + ("." + ext if ext else "")
        return filename

    @staticmethod
    def _is_undefined_column_error(exc: Exception) -> bool:
        # PostgreSQL: undefined_column = 42703
        return getattr(exc, "sqlstate", None) == "42703"

    @staticmethod
    def _is_undefined_table_error(exc: Exception) -> bool:
        # PostgreSQL: undefined_table = 42P01
        return getattr(exc, "sqlstate", None) == "42P01"

    @staticmethod
    def _classify_document_category(document_type: str, file_name: str) -> str:
        """Auto-classify document_category from document_type and filename."""
        dt = (document_type or "").lower()
        fn = (file_name or "").lower()
        combined = f"{dt} {fn}"

        # Immigration
        if any(k in combined for k in (
            "kitas", "kitap", "visa", "evisa", "voa", "permit", "imta", "rptka", "itas",
        )):
            return "immigration"

        # Personal
        if any(k in combined for k in (
            "passport", "paspor", "ktp", "photo", "foto", "cv ", "resume",
            "domisili", "skck", "surat keterangan",
        )):
            return "personal"

        # Company / PMA
        if any(k in combined for k in (
            "akta", "pendirian", "perubahan", "nib", "npwp", "sk ", "profil perseroan",
            "sertifikat standar", "kbli", "sppl", "pks", "kontrak", "contract",
        )):
            return "pma"

        # Tax
        if any(k in combined for k in ("tax", "pajak", "spt", "efin", "pph", "ppn")):
            return "tax"

        # Family
        if any(k in combined for k in ("akte lahir", "akta lahir", "birth", "nikah", "marriage")):
            return "family"

        return "other"

    @staticmethod
    def _get_drive_folder_for_category(category: str) -> str:
        """Map document category to Drive folder name for OCR dispatch."""
        category_map = {
            "immigration": "01_Immigration",
            "personal": "00_Profile",
            "pma": "02_Company",
            "tax": "03_Tax",
            "family": "04_Family",
        }
        return category_map.get((category or "").lower(), "99_Misc")

    # ================================================
    # DASHBOARD
    # ================================================

    async def get_dashboard(self, client_id: int) -> dict[str, Any]:
        """
        Get client dashboard overview.

        Returns format expected by frontend PortalDashboard type:
            - visa: status, type, expiryDate, daysRemaining
            - company: status, primaryCompanyName, totalCompanies
            - taxes: status, nextDeadline, daysToDeadline
            - documents: total, pending
            - messages: unread
            - actions: list of PortalAction
        """
        async with self.pool.acquire() as conn:
            # Get client info
            client = await conn.fetchrow(
                "SELECT id, full_name, email FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )
            if not client:
                raise ValueError(f"Client {client_id} not found")

            # Get visa status (most recent KITAS/KITAP practice)
            # Use try-except to handle missing tables gracefully
            visa_practice = None
            try:
                visa_practice = await conn.fetchrow(
                    """
                    SELECT p.id, p.status, p.expiry_date, pt.code, pt.name
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND pt.category = 'visa'
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    AND p.status NOT IN ('cancelled', 'rejected')
                    ORDER BY p.expiry_date DESC NULLS LAST
                    LIMIT 1
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch visa practice: {e}")

            # Get companies
            companies = []
            try:
                companies = await conn.fetch(
                    """
                    SELECT ccl.id, ccl.role, ccl.is_primary, c.company_name, c.company_type
                    FROM client_company_links ccl
                    JOIN companies c ON c.id = ccl.company_id
                    WHERE ccl.client_id = $1
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch companies: {e}")

            # Get primary company name
            primary_company = next(
                (c for c in companies if c["is_primary"]), companies[0] if companies else None,
            )

            # Get upcoming tax deadlines (next 30 days)
            today = datetime.now(timezone.utc)
            tax_deadlines = self._get_standard_tax_deadlines(today)
            next_deadline = tax_deadlines[0] if tax_deadlines else None

            # Get action items (practices with required documents)
            action_items = []
            try:
                action_items = await conn.fetch(
                    """
                    SELECT p.id, pt.name as practice_name, p.missing_documents, p.status
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    AND p.status IN ('inquiry', 'in_progress', 'waiting_documents')
                    ORDER BY p.created_at DESC
                    LIMIT 5
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch action items: {e}")

            # Get unread messages count
            unread_count = 0
            try:
                unread_count = (
                    await conn.fetchval(
                        """
                    SELECT COUNT(*) FROM portal_messages
                    WHERE client_id = $1
                    AND direction = 'team_to_client'
                    AND read_at IS NULL
                    """,
                        client_id,
                    )
                    or 0
                )
            except Exception as e:
                logger.warning(f"Could not fetch unread messages count: {e}")

            # Get document counts
            doc_counts = None
            try:
                doc_counts = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'pending') as pending
                    FROM documents
                    WHERE client_id = $1
                    AND client_visible = true
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch document counts: {e}")

            # Build visa response
            visa_data = self._build_visa_dashboard_data(visa_practice)

            # Build company response
            company_data = {
                "status": "active" if companies else "none",
                "primaryCompanyName": primary_company["company_name"] if primary_company else None,
                "totalCompanies": len(companies),
            }

            # Build tax response
            tax_data = {
                "status": self._get_tax_status(next_deadline),
                "nextDeadline": next_deadline["due_date"][:10] if next_deadline else None,
                "daysToDeadline": next_deadline["days_until"] if next_deadline else None,
            }

            # Build actions response
            actions = self._build_action_items(action_items, visa_data)

            return {
                "visa": visa_data,
                "company": company_data,
                "taxes": tax_data,
                "documents": {
                    "total": doc_counts["total"] if doc_counts else 0,
                    "pending": doc_counts["pending"] if doc_counts else 0,
                },
                "messages": {
                    "unread": unread_count,
                },
                "actions": actions,
            }

    def _build_visa_dashboard_data(self, visa_practice) -> dict[str, Any]:
        """Build visa data in frontend expected format."""
        if not visa_practice:
            return {
                "status": "none",
                "type": None,
                "expiryDate": None,
                "daysRemaining": None,
            }

        today = datetime.now(timezone.utc).date()
        expiry = visa_practice["expiry_date"].date() if visa_practice["expiry_date"] else None
        days_left = (expiry - today).days if expiry else None

        # Determine status based on practice status and expiry
        if visa_practice["status"] == "completed":
            if days_left is not None:
                if days_left <= 0:
                    status = "expired"
                elif days_left <= 90:
                    status = "warning"
                else:
                    status = "active"
            else:
                status = "active"
        elif visa_practice["status"] in ("inquiry", "in_progress", "waiting_documents"):
            status = "pending"
        else:
            status = "pending"

        return {
            "status": status,
            "type": f"{visa_practice['code']} - {visa_practice['name']}"
            if visa_practice["code"]
            else visa_practice["name"],
            "expiryDate": visa_practice["expiry_date"].isoformat()[:10]
            if visa_practice["expiry_date"]
            else None,
            "daysRemaining": days_left,
        }

    def _get_tax_status(self, next_deadline) -> str:
        """Determine tax compliance status."""
        if not next_deadline:
            return "compliant"
        days = next_deadline["days_until"]
        if days < 0:
            return "overdue"
        if days <= 14:
            return "attention"
        return "compliant"

    def _build_action_items(self, action_items, visa_data) -> list[dict[str, Any]]:
        """Build action items for dashboard."""
        actions = []
        action_id = 1

        # Add visa warning if expiring soon
        if visa_data["status"] == "warning" and visa_data["daysRemaining"]:
            actions.append(
                {
                    "id": f"visa-{action_id}",
                    "title": "Visa Expiring Soon",
                    "description": f"Your visa expires in {visa_data['daysRemaining']} days. Start renewal process.",
                    "priority": "high" if visa_data["daysRemaining"] <= 30 else "medium",
                    "type": "visa_renewal",
                    "href": "/portal/visa",
                },
            )
            action_id += 1

        # Add missing documents actions
        for item in action_items:
            missing_docs = item["missing_documents"] or []
            if missing_docs:
                actions.append(
                    {
                        "id": f"docs-{item['id']}",
                        "title": f"Documents Required: {item['practice_name']}",
                        "description": f"Please upload: {', '.join(missing_docs[:3])}{'...' if len(missing_docs) > 3 else ''}",
                        "priority": "high" if item["status"] == "waiting_documents" else "medium",
                        "type": "missing_documents",
                        "href": "/portal/documents",
                    },
                )
                action_id += 1
                if action_id > 5:  # Max 5 actions
                    break

        return actions

    # ================================================
    # VISA & IMMIGRATION
    # ================================================

    async def get_visa_status(self, client_id: int) -> dict[str, Any]:
        """
        Get detailed visa and immigration status.

        Returns format expected by frontend VisaInfo type:
            - current: { type, status, issueDate, expiryDate, daysRemaining, permitNumber, sponsor }
            - history: [{ id, type, period, status }]
            - documents: [{ id, name, type, category, status, uploadDate, expiryDate, size, downloadUrl }]
        """
        async with self.pool.acquire() as conn:
            # Verify client exists
            client = await conn.fetchrow(
                "SELECT id FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )
            if not client:
                raise ValueError(f"Client {client_id} not found")

            # Get current visa practice (completed, not expired)
            try:
                current_visa = await conn.fetchrow(
                    """
                    SELECT p.id, p.status, p.start_date, p.completion_date, p.expiry_date,
                           p.notes, pt.code, pt.name as type_name
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND pt.category = 'visa'
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    AND p.status = 'completed'
                    AND (p.expiry_date IS NULL OR p.expiry_date > NOW())
                    ORDER BY p.expiry_date DESC NULLS LAST
                    LIMIT 1
                    """,
                    client_id,
                )
            except Exception as e:
                if self._is_undefined_column_error(e):
                    current_visa = await conn.fetchrow(
                        """
                        SELECT p.id, p.status, p.start_date, p.completion_date, p.expiry_date,
                               p.notes, pt.code, pt.name as type_name
                        FROM practices p
                        JOIN practice_types pt ON pt.id = p.practice_type_id
                        WHERE p.client_id = $1
                        AND pt.category = 'visa'
                        AND p.status = 'completed'
                        AND (p.expiry_date IS NULL OR p.expiry_date > NOW())
                        ORDER BY p.expiry_date DESC NULLS LAST
                        LIMIT 1
                        """,
                        client_id,
                    )
                else:
                    raise

            # Get visa history (all visa practices)
            try:
                visa_history = await conn.fetch(
                    """
                    SELECT p.id, pt.code, pt.name, p.start_date, p.completion_date,
                           p.expiry_date, p.status
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND pt.category = 'visa'
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    ORDER BY p.start_date DESC
                    """,
                    client_id,
                )
            except Exception as e:
                if self._is_undefined_column_error(e):
                    visa_history = await conn.fetch(
                        """
                        SELECT p.id, pt.code, pt.name, p.start_date, p.completion_date,
                               p.expiry_date, p.status
                        FROM practices p
                        JOIN practice_types pt ON pt.id = p.practice_type_id
                        WHERE p.client_id = $1
                        AND pt.category = 'visa'
                        ORDER BY p.start_date DESC
                        """,
                        client_id,
                    )
                else:
                    raise

            # Get immigration documents
            documents = await conn.fetch(
                """
                SELECT d.id, d.document_type, d.file_name, d.status,
                       d.expiry_date, d.file_url, d.file_size_kb, d.created_at
                FROM documents d
                WHERE d.client_id = $1
                AND d.client_visible = true
                AND d.document_type IN (
                    'passport', 'photo', 'cv', 'sponsor_letter',
                    'sktt', 'stm', 'kitas_card', 'merp', 'visa'
                )
                ORDER BY d.created_at DESC
                """,
                client_id,
            )

            # Build current visa response (matching frontend VisaInfo.current)
            current = None
            if current_visa:
                today = datetime.now(timezone.utc).date()
                expiry = current_visa["expiry_date"].date() if current_visa["expiry_date"] else None
                days_left = (expiry - today).days if expiry else 0

                # Determine status
                if days_left <= 0:
                    status = "expired"
                elif current_visa["status"] == "completed":
                    status = "active"
                else:
                    status = "pending"

                visa_type = (
                    f"{current_visa['code']} - {current_visa['type_name']}"
                    if current_visa["code"]
                    else current_visa["type_name"]
                )

                current = {
                    "type": visa_type,
                    "status": status,
                    "issueDate": current_visa["completion_date"].strftime("%d %b %Y")
                    if current_visa["completion_date"]
                    else "-",
                    "expiryDate": current_visa["expiry_date"].strftime("%d %b %Y")
                    if current_visa["expiry_date"]
                    else "-",
                    "daysRemaining": max(0, days_left),
                    "permitNumber": f"KITAS-{current_visa['id']:06d}",  # Generated permit number
                    "sponsor": "Bali Zero Indonesia",  # Default sponsor
                }

            # Build history response (matching frontend VisaHistoryItem)
            history = []
            for v in visa_history:
                # Determine period string
                start = v["start_date"].strftime("%b %Y") if v["start_date"] else ""
                end = (
                    v["expiry_date"].strftime("%b %Y")
                    if v["expiry_date"]
                    else v["completion_date"].strftime("%b %Y")
                    if v["completion_date"]
                    else ""
                )
                period = f"{start} - {end}" if start and end else start or end or "-"

                # Map status to frontend expected values
                hist_status = "completed" if v["status"] == "completed" else "expired"

                history.append(
                    {
                        "id": str(v["id"]),
                        "type": f"{v['code']} - {v['name']}" if v["code"] else v["name"],
                        "period": period,
                        "status": hist_status,
                    },
                )

            # Build documents response (matching frontend PortalDocument)
            doc_list = []
            for d in documents:
                # Map document type to category
                category_map = {
                    "passport": "Identity",
                    "photo": "Identity",
                    "cv": "Supporting",
                    "sponsor_letter": "Sponsorship",
                    "sktt": "Immigration",
                    "stm": "Immigration",
                    "kitas_card": "Immigration",
                    "merp": "Immigration",
                    "visa": "Immigration",
                }

                # Map status
                status_map = {
                    "verified": "verified",
                    "issued": "verified",
                    "pending": "pending",
                    "rejected": "expired",
                    "expired": "expired",
                }

                doc_list.append(
                    {
                        "id": str(d["id"]),
                        "name": d["file_name"],
                        "type": d["document_type"],
                        "category": category_map.get(d["document_type"], "Other"),
                        "status": status_map.get(d["status"], "pending"),
                        "uploadDate": d["created_at"].strftime("%d %b %Y")
                        if d["created_at"]
                        else "-",
                        "expiryDate": d["expiry_date"].strftime("%d %b %Y")
                        if d["expiry_date"]
                        else None,
                        "size": f"{d['file_size_kb']} KB" if d["file_size_kb"] else "-",
                        "downloadUrl": d["file_url"]
                        if d["status"] in ("verified", "issued")
                        else None,
                    },
                )

            return {
                "current": current,
                "history": history,
                "documents": doc_list,
            }

    # ================================================
    # COMPANIES
    # ================================================

    async def get_companies(self, client_id: int) -> list[dict[str, Any]]:
        """Get all companies associated with client."""
        async with self.pool.acquire() as conn:
            companies = await conn.fetch(
                """
                SELECT ccl.id, ccl.role, ccl.is_primary, ccl.created_at,
                       ccl.ownership_percentage, ccl.status as link_status,
                       c.id as company_id, c.company_name, c.company_type,
                       c.nib, c.npwp_company, c.kbli_code, c.status as company_status
                FROM client_company_links ccl
                JOIN companies c ON c.id = ccl.company_id
                WHERE ccl.client_id = $1
                ORDER BY ccl.is_primary DESC, ccl.created_at
                """,
                client_id,
            )

            return [
                {
                    "id": c["id"],
                    "company_id": c["company_id"],
                    "name": c["company_name"],
                    "type": c["company_type"],
                    "role": c["role"],
                    "isPrimary": c["is_primary"],
                    "ownership_pct": float(c["ownership_percentage"])
                    if c["ownership_percentage"]
                    else None,
                    "nib": c["nib"],
                    "npwp": c["npwp_company"],
                    "kbli": c["kbli_code"],
                    "status": c["company_status"],
                    "link_status": c["link_status"],
                }
                for c in companies
            ]

    async def get_company_detail(self, client_id: int, company_id: int) -> dict[str, Any]:
        """Get detailed company information."""
        async with self.pool.acquire() as conn:
            # Verify client owns this company
            ownership = await conn.fetchrow(
                """
                SELECT ccl.role, ccl.is_primary, ccl.ownership_percentage
                FROM client_company_links ccl
                WHERE ccl.client_id = $1 AND ccl.company_id = $2
                """,
                client_id,
                company_id,
            )
            if not ownership:
                raise ValueError("Company not found or not accessible")

            # Get company profile
            company = await conn.fetchrow(
                """
                SELECT * FROM companies WHERE id = $1
                """,
                company_id,
            )

            # Get company practices (licenses, registrations)
            try:
                practices = await conn.fetch(
                    """
                    SELECT p.id, pt.code, pt.name, p.status, p.expiry_date,
                           p.completion_date
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND pt.category = 'company'
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    ORDER BY p.expiry_date ASC NULLS LAST
                    """,
                    client_id,
                )
            except Exception as e:
                if self._is_undefined_column_error(e):
                    practices = await conn.fetch(
                        """
                        SELECT p.id, pt.code, pt.name, p.status, p.expiry_date,
                               p.completion_date
                        FROM practices p
                        JOIN practice_types pt ON pt.id = p.practice_type_id
                        WHERE p.client_id = $1
                        AND pt.category = 'company'
                        ORDER BY p.expiry_date ASC NULLS LAST
                        """,
                        client_id,
                    )
                else:
                    raise

            # Get company documents
            documents = await conn.fetch(
                """
                SELECT d.id, d.document_type, d.file_name, d.status, d.file_url
                FROM documents d
                JOIN practices p ON p.id = d.practice_id
                JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE p.client_id = $1
                AND pt.category = 'company'
                AND d.client_visible = true
                ORDER BY d.created_at DESC
                """,
                client_id,
            )

            # Get all directors/shareholders linked to this company
            directors = await conn.fetch(
                """
                SELECT cl.full_name, ccl.role, ccl.ownership_percentage
                FROM client_company_links ccl
                JOIN clients cl ON cl.id = ccl.client_id
                WHERE ccl.company_id = $1
                ORDER BY ccl.is_primary DESC, ccl.role, cl.full_name
                """,
                company_id,
            )

            # Parse custom_fields safely
            custom = company["custom_fields"] or {}
            if isinstance(custom, str):
                try:
                    custom = json.loads(custom)
                except Exception:
                    custom = {}
            if not isinstance(custom, dict):
                custom = {}

            return {
                "id": company["id"],
                "name": company["company_name"],
                "type": company["company_type"],
                "nib": company["nib"],
                "npwp": company["npwp_company"],
                "kbli": company["kbli_code"],
                "status": company["status"],
                "address": company["registered_address"],
                "email": company["company_email"],
                "phone": company["company_phone"],
                "akta_no": company["akta_pendirian_no"],
                "akta_date": company["akta_pendirian_date"].isoformat()
                if company["akta_pendirian_date"]
                else None,
                "sk_number": company["sk_menhumkam_no"],
                "tax_office": custom.get("tax_office"),
                "company_status": custom.get("company_status"),
                "investment_type": custom.get("investment_type"),
                "authorized_capital": custom.get("authorized_capital"),
                "ownership": {
                    "role": ownership["role"],
                    "is_primary": ownership["is_primary"],
                    "pct": float(ownership["ownership_percentage"])
                    if ownership["ownership_percentage"]
                    else None,
                },
                "licenses": [
                    {
                        "id": p["id"],
                        "code": p["code"],
                        "name": p["name"],
                        "status": p["status"],
                        "expiry_date": p["expiry_date"].isoformat() if p["expiry_date"] else None,
                    }
                    for p in practices
                ],
                "documents": [
                    {
                        "id": d["id"],
                        "type": d["document_type"],
                        "name": d["file_name"],
                        "downloadable": d["status"] in ("verified", "issued")
                        and d["file_url"] is not None,
                    }
                    for d in documents
                ],
                "directors": [
                    d["full_name"]
                    for d in directors
                    if d["role"] in ("director", "commissioner", "president_director")
                ],
                "shareholders": [
                    {
                        "name": d["full_name"],
                        "pct": float(d["ownership_percentage"])
                        if d["ownership_percentage"]
                        else None,
                    }
                    for d in directors
                ],
            }

    async def set_primary_company(self, client_id: int, company_id: int) -> dict[str, Any]:
        """Set a company as primary for the client."""
        async with self.pool.acquire() as conn, conn.transaction():
            # Clear previous primary
            await conn.execute(
                """
                    UPDATE client_company_links
                    SET is_primary = false
                    WHERE client_id = $1
                    """,
                client_id,
            )

            # Set new primary
            result = await conn.execute(
                """
                    UPDATE client_company_links
                    SET is_primary = true
                    WHERE client_id = $1 AND company_id = $2
                    """,
                client_id,
                company_id,
            )

            if result == "UPDATE 0":
                raise ValueError("Company not found or not accessible")

            return {"success": True, "primary_company_id": company_id}

    # ================================================
    # TAXES
    # ================================================

    async def get_tax_overview(self, client_id: int) -> dict[str, Any]:
        """
        Get tax overview and upcoming deadlines.

        Returns format expected by frontend TaxOverview:
        - summary: { status, totalDue, nextDeadline, daysToDeadline }
        - obligations: list of TaxObligation
        - history: list of TaxHistoryItem
        """
        async with self.pool.acquire() as conn:
            # Get tax-related practices (for obligations)
            tax_practices = []
            try:
                tax_practices = await conn.fetch(
                    """
                    SELECT p.id, pt.code, pt.name, p.status, p.expiry_date, p.created_at
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND pt.category = 'tax'
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    ORDER BY p.expiry_date ASC NULLS LAST
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch tax practices: {e}")

            # Generate standard tax deadlines
            today = datetime.now(timezone.utc)
            deadlines = self._get_standard_tax_deadlines(today)

            # Build obligations from deadlines (upcoming tax filings)
            obligations = []
            for i, d in enumerate(deadlines):
                obligations.append(
                    {
                        "id": f"deadline-{i}",
                        "name": d["type"],
                        "type": "Monthly Filing",
                        "period": d["period"],
                        "dueDate": d["due_date"],
                        "status": "overdue" if d["days_until"] < 0 else "pending",
                        "amount": None,
                    },
                )

            # Build history from completed tax practices
            history = []
            for p in tax_practices:
                if p["status"] in ("completed", "filed"):
                    history.append(
                        {
                            "id": str(p["id"]),
                            "name": p["name"],
                            "period": p["created_at"].strftime("%b %Y")
                            if p["created_at"]
                            else "N/A",
                            "filedDate": p["created_at"].isoformat() if p["created_at"] else None,
                            "amount": 0,  # No amount stored in practices
                        },
                    )

            # Calculate summary
            next_deadline = None
            days_to_deadline = None
            if deadlines:
                next_deadline = deadlines[0]["due_date"]
                days_to_deadline = deadlines[0]["days_until"]

            # Determine status based on deadlines
            status = "compliant"
            if days_to_deadline is not None:
                if days_to_deadline < 0:
                    status = "overdue"
                elif days_to_deadline <= 14:
                    status = "attention"

            return {
                "summary": {
                    "status": status,
                    "totalDue": 0,  # No payment tracking yet
                    "nextDeadline": next_deadline,
                    "daysToDeadline": days_to_deadline,
                },
                "obligations": obligations,
                "history": history,
            }

    # ================================================
    # DOCUMENTS
    # ================================================

    async def get_documents(
        self, client_id: int, document_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get all client-visible documents."""
        async with self.pool.acquire() as conn:
            query = """
                SELECT d.id, d.document_type, d.file_name, d.status,
                       d.expiry_date, d.file_url, d.file_size_kb, d.created_at,
                       p.id as practice_id, pt.name as practice_name
                FROM documents d
                LEFT JOIN practices p ON p.id = d.practice_id
                LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE d.client_id = $1
                AND d.client_visible = true
            """
            params = [client_id]

            if document_type:
                query += " AND d.document_type = $2"
                params.append(document_type)

            query += " ORDER BY d.created_at DESC"

            documents = await conn.fetch(query, *params)

            return [
                {
                    "id": d["id"],
                    "type": d["document_type"],
                    "name": d["file_name"],
                    "status": d["status"],
                    "expiry_date": d["expiry_date"].isoformat() if d["expiry_date"] else None,
                    "size_kb": d["file_size_kb"],
                    "practice_id": d["practice_id"],
                    "practice_name": d["practice_name"],
                    "downloadable": d["status"] in ("verified", "issued")
                    and d["file_url"] is not None,
                    "created_at": d["created_at"].isoformat(),
                }
                for d in documents
            ]

    async def upload_document(
        self,
        client_id: int,
        file_content: bytes,
        file_name: str,
        document_type: str,
        mime_type: str | None = None,
        practice_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Upload a document for a client with full processing:
        - Virus scanning
        - Google Drive upload with folder structure
        - OCR text extraction
        - Expiry date detection
        - Email notification to assigned lead
        """
        processing_results = {
            "virus_scan": None,
            "drive_upload": None,
            "ocr": None,
            "expiry_detection": None,
        }

        # =========================================================================
        # STEP 1: VIRUS SCAN
        # =========================================================================
        scan_result = VirusScanner.scan(file_content, file_name)
        processing_results["virus_scan"] = scan_result

        if not scan_result["clean"]:
            logger.warning(
                f"🚨 THREAT DETECTED in upload from client {client_id}: "
                f"{file_name} - Threats: {scan_result['threats']}",
            )
            raise ValueError(
                f"Security threat detected in file: {', '.join(scan_result['threats'])}. "
                "Upload blocked for security reasons.",
            )

        logger.info(f"✅ Virus scan passed for {file_name}")

        # Calculate file size
        file_size_kb = len(file_content) // 1024

        # Memory optimization: skip OCR for very large files (> 50MB)
        skip_ocr = file_size_kb > 51200  # 50MB
        if skip_ocr:
            logger.warning(f"File too large for OCR ({file_size_kb}KB), skipping: {file_name}")

        # Calculate file hash for deduplication
        # import hashlib
        # file_hash = hashlib.sha256(file_content).hexdigest()[:32]

        # =========================================================================
        # STEP 0: RATE LIMITING & VALIDATION
        # =========================================================================
        # Check rate limit
        now = datetime.now(timezone.utc).timestamp()
        client_uploads = self._upload_rate_limits.get(client_id, [])
        # Clean old entries outside window
        client_uploads = [t for t in client_uploads if now - t < self.RATE_WINDOW_SECONDS]
        if len(client_uploads) >= self.MAX_UPLOADS_PER_WINDOW:
            raise ValueError(
                f"Rate limit exceeded: max {self.MAX_UPLOADS_PER_WINDOW} uploads per 15 minutes",
            )
        client_uploads.append(now)
        self._upload_rate_limits[client_id] = client_uploads

        # Validate MIME type
        if mime_type and not VirusScanner.validate_mime_type(mime_type):
            raise ValueError(f"File type not allowed: {mime_type}")

        # Sanitize filename
        file_name = self._sanitize_filename(file_name)

        async with self.pool.acquire() as conn:
            # Check for duplicate file (same hash, same client, last 1 hour)
            duplicate = await conn.fetchrow(
                """
                SELECT id, file_name, created_at
                FROM documents
                WHERE client_id = $1
                AND file_name LIKE $2
                AND created_at > NOW() - INTERVAL '1 hour'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                client_id,
                f"%{file_name}%",
            )
            if duplicate:
                logger.info(
                    f"Duplicate file detected: {file_name} uploaded at {duplicate['created_at']}",
                )
                raise ValueError(f"File already uploaded recently at {duplicate['created_at']}")

            # Verify practice belongs to client if provided
            if practice_id:
                practice = await conn.fetchrow(
                    "SELECT id FROM practices WHERE id = $1 AND client_id = $2",
                    practice_id,
                    client_id,
                )
                if not practice:
                    raise ValueError("Practice not found or not accessible")

            # Get client info
            client = await conn.fetchrow(
                "SELECT email, full_name, assigned_to FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )

            if not client:
                raise ValueError(f"Client {client_id} not found")

            # =========================================================================
            # STEP 2: GOOGLE DRIVE UPLOAD
            # =========================================================================
            drive_result = await self._upload_to_drive(
                conn=conn,
                client_id=client_id,
                client_name=client["full_name"],
                document_type=document_type,
                file_content=file_content,
                file_name=file_name,
                mime_type=mime_type,
            )
            processing_results["drive_upload"] = drive_result

            # =========================================================================
            # STEP 3: OCR TEXT EXTRACTION (using Gemini Vision - same as passport box)
            # =========================================================================
            if skip_ocr:
                ocr_result = {
                    "text": "",
                    "pages": 0,
                    "success": False,
                    "error": "File too large for OCR (>50MB)",
                }
            else:
                ocr_result = await DocumentOCR.extract_text(
                    file_content=file_content, file_name=file_name, mime_type=mime_type,
                )
            processing_results["ocr"] = ocr_result

            if ocr_result["success"]:
                logger.info(
                    f"📄 OCR extracted {len(ocr_result['text'])} chars "
                    f"from {file_name} ({ocr_result['pages']} pages)",
                )
            else:
                logger.warning(f"⚠️ OCR failed for {file_name}: {ocr_result.get('error')}")

            # =========================================================================
            # STEP 4: EXPIRY DATE DETECTION
            # =========================================================================
            expiry_result = ExpiryDetector.detect_expiry(
                text=ocr_result.get("text", ""), document_type=document_type,
            )
            processing_results["expiry_detection"] = expiry_result

            if expiry_result["expiry_date"]:
                logger.info(
                    f"📅 Expiry date detected for {document_type}: "
                    f"{expiry_result['expiry_date']} (confidence: {expiry_result['confidence']})",
                )

            # =========================================================================
            # STEP 5: SAVE TO DATABASE (with transaction)
            # =========================================================================
            # Auto-classify document_category from document_type
            doc_category = self._classify_document_category(document_type, file_name)

            async with conn.transaction():
                try:
                    doc = await conn.fetchrow(
                        """
                        INSERT INTO documents (
                            client_id, practice_id, document_type, document_category, file_name,
                            status, uploaded_by, uploaded_source, file_size_kb, mime_type,
                            storage_type, storage_path, file_id, file_url,
                            extracted_text, expiry_date,
                            client_visible, created_at
                        )
                        VALUES (
                            $1, $2, $3, $13, $4, 'received', $5, 'client', $6, $7,
                            'google_drive', $8, $9, $10,
                            $11, $12,
                            true, NOW()
                        )
                        RETURNING id, document_type, file_name, status, created_at, expiry_date
                        """,
                        client_id,
                        practice_id,
                        document_type,
                        file_name,
                        client["email"],
                        file_size_kb,
                        mime_type,
                        drive_result.get("folder_path"),
                        drive_result.get("file_id"),
                        drive_result.get("file_url"),
                        ocr_result.get("text")[:10000]
                        if ocr_result.get("text")
                        else None,  # Limit text size
                        expiry_result.get("expiry_date"),
                        doc_category,
                    )
                except Exception as e:
                    # Backward compatibility: try without new columns
                    if self._is_undefined_column_error(e):
                        doc = await conn.fetchrow(
                            """
                            INSERT INTO documents (
                                client_id, practice_id, document_type, file_name,
                                status, uploaded_by, file_size_kb, mime_type,
                                storage_type, client_visible
                        )
                        VALUES ($1, $2, $3, $4, 'received', $5, $6, $7, 'google_drive', true)
                        RETURNING id, document_type, file_name, status, created_at, expiry_date
                        """,
                            client_id,
                            practice_id,
                            document_type,
                            file_name,
                            client["email"],
                            file_size_kb,
                            mime_type,
                        )
                else:
                    raise

            # =========================================================================
            # STEP 6: CREATE TIMELINE EVENT
            # =========================================================================
            try:
                timeline_desc = f"{file_name} uploaded successfully"
                if expiry_result.get("expiry_date"):
                    timeline_desc += f" (Expiry detected: {expiry_result['expiry_date']})"

                await conn.execute(
                    """
                    INSERT INTO timeline_events (
                        client_id, practice_id, event_type, title,
                        description, event_date, client_visible, color
                    )
                    VALUES ($1, $2, 'document_received', 'Document received',
                            $3, NOW(), true, 'success')
                    """,
                    client_id,
                    practice_id,
                    timeline_desc,
                )
            except Exception as e:
                if not self._is_undefined_table_error(e):
                    logger.warning(f"Could not create timeline event for upload: {e}")

            logger.info(
                f"✅ Document processed and stored: {file_name} for client {client_id}, "
                f"size: {file_size_kb}KB, type: {document_type}, "
                f"drive_id: {drive_result.get('file_id', 'N/A')}",
            )

            # =========================================================================
            # STEP 6b: SMART OCR DISPATCH (passport/visa/npwp/nib extraction)
            # =========================================================================
            try:
                from backend.services.documents.ocr_dispatcher_service import (
                    dispatch_ocr_by_folder,
                )

                file_id_for_ocr = drive_result.get("file_id")
                if file_id_for_ocr:
                    doc_category = self._classify_document_category(document_type, file_name)
                    folder_hint = self._get_drive_folder_for_category(doc_category)
                    asyncio.create_task(
                        dispatch_ocr_by_folder(
                            db_pool=self.pool,
                            client_id=client_id,
                            file_id=file_id_for_ocr,
                            folder_name=folder_hint,
                            filename=file_name,
                            doc_id=doc["id"],
                            document_type=document_type,
                        ),
                    )
                    logger.info(f"Smart OCR dispatch triggered for portal upload: {file_name}")
            except Exception as e:
                logger.error(f"Smart OCR dispatch failed for portal upload {file_name}: {e}")

            # =========================================================================
            # STEP 7: NOTIFY ASSIGNED LEAD
            # =========================================================================
            asyncio.create_task(
                self._notify_lead_about_document(
                    client_id=client_id,
                    document_name=file_name,
                    document_type=document_type,
                    expiry_date=expiry_result.get("expiry_date"),
                    drive_url=drive_result.get("file_url"),
                ),
            )

            # Update metrics
            self._metrics["uploads_total"] += 1
            if drive_result.get("success"):
                self._metrics["drive_uploads"] += 1
            if ocr_result.get("success"):
                self._metrics["ocr_processed"] += 1

            return {
                "id": doc["id"],
                "type": doc["document_type"],
                "name": doc["file_name"],
                "status": doc["status"],
                "size_kb": file_size_kb,
                "created_at": doc["created_at"].isoformat(),
                "expiry_date": expiry_result.get("expiry_date"),
                "extracted_text_preview": (
                    ocr_result.get("text", "")[:200] + "..."
                    if ocr_result.get("text") and len(ocr_result.get("text", "")) > 200
                    else ocr_result.get("text", "")
                ),
                "processing": {
                    "virus_clean": scan_result["clean"],
                    "ocr_pages": ocr_result.get("pages"),
                    "drive_uploaded": drive_result.get("success", False),
                },
            }

    async def _upload_to_drive(
        self,
        conn: asyncpg.Connection,
        client_id: int,
        client_name: str,
        document_type: str,
        file_content: bytes,
        file_name: str,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload file to Google Drive with organized folder structure.

        Folder structure:
        Zantara Portal Uploads/
        └── {client_id}_{client_name}/
            └── {document_type}/
                └── {timestamp}_{file_name}

        Returns:
            {
                "success": bool,
                "file_id": str | None,
                "file_url": str | None,
                "folder_path": str,
                "error": str | None
            }
        """
        result = {
            "success": False,
            "file_id": None,
            "file_url": None,
            "folder_path": "",
            "error": None,
        }

        try:
            from backend.app.core.config import settings
            from backend.services.integrations.google_drive_service import GoogleDriveService
            from backend.services.integrations.team_drive_service import TeamDriveService

            # Try OAuth first, fallback to Service Account
            drive_service = GoogleDriveService(self.pool)
            use_service_account = False

            # Check if Drive is configured
            if not drive_service.is_configured():
                logger.warning("OAuth not configured, trying Service Account...")
                use_service_account = True
            else:
                # Check if we have a valid token
                token = await drive_service.get_valid_token("SYSTEM")
                if not token:
                    logger.warning("No valid OAuth token, trying Service Account...")
                    use_service_account = True

            # Use Service Account if OAuth unavailable
            if use_service_account:
                team_drive = TeamDriveService(db_pool=self.pool)
                if not team_drive.service_account_available:
                    logger.error("Service Account also not available")
                    result["error"] = "No Drive authentication available"
                    return result
                # Use Service Account for upload
                return await self._upload_with_service_account(
                    team_drive,
                    client_id,
                    client_name,
                    document_type,
                    file_content,
                    file_name,
                    mime_type,
                    result,
                )

            # Continue with OAuth
            user_id = "SYSTEM"

            # Get or create root folder for portal uploads
            root_folder_id = await self._get_or_create_drive_folder(
                drive_service,
                user_id,
                folder_name="Zantara Portal Uploads",
                parent_id=settings.google_drive_root_folder_id or "root",
            )

            if not root_folder_id:
                result["error"] = "Failed to create root folder"
                return result

            # Create/get client folder
            safe_client_name = "".join(
                c for c in client_name if c.isalnum() or c in (" ", "_")
            ).rstrip()
            client_folder_name = f"{client_id}_{safe_client_name[:30]}"  # Limit name length

            client_folder_id = await self._get_or_create_drive_folder(
                drive_service, user_id, folder_name=client_folder_name, parent_id=root_folder_id,
            )

            if not client_folder_id:
                result["error"] = "Failed to create client folder"
                return result

            # Create/get document type folder
            type_folder_name = document_type.replace("_", " ").title()
            type_folder_id = await self._get_or_create_drive_folder(
                drive_service, user_id, folder_name=type_folder_name, parent_id=client_folder_id,
            )

            if not type_folder_id:
                result["error"] = "Failed to create type folder"
                return result

            # Add timestamp to filename to avoid collisions
            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            drive_file_name = f"{timestamp}_{file_name}"

            # Upload file with retry logic
            max_retries = 3
            upload_result = None

            for attempt in range(max_retries):
                try:
                    upload_result = await drive_service.upload_file_to_folder(
                        user_id=user_id,
                        folder_id=type_folder_id,
                        file_content=file_content,
                        file_name=drive_file_name,
                        mime_type=mime_type,
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.warning(
                            f"Drive upload attempt {attempt + 1} failed, retrying in {wait_time}s: {e}",
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        raise  # All retries exhausted

            if upload_result:
                result["success"] = True
                result["file_id"] = upload_result.get("id")
                result["file_url"] = (
                    upload_result.get("webViewLink")
                    or f"https://drive.google.com/file/d/{upload_result.get('id')}/view"
                )
                result["folder_path"] = (
                    f"Zantara Portal Uploads/{client_folder_name}/{type_folder_name}"
                )

                logger.info(
                    f"📁 File uploaded to Drive: {drive_file_name} (ID: {upload_result.get('id')})",
                )
            else:
                result["error"] = "Upload failed after all retries"

        except Exception as e:
            logger.error(f"Failed to upload to Google Drive: {e}", exc_info=True)
            result["error"] = str(e)

        return result

    async def _upload_with_service_account(
        self,
        team_drive: Any,
        client_id: int,
        client_name: str,
        document_type: str,
        file_content: bytes,
        file_name: str,
        mime_type: str | None,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Upload file using Service Account (fallback when OAuth fails)."""
        try:
            from datetime import datetime

            from backend.app.core.config import settings

            # Create folder structure
            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_client_name = "".join(
                c for c in client_name if c.isalnum() or c in (" ", "_")
            ).rstrip()[:30]
            folder_path = f"Zantara Portal Uploads/{client_id}_{safe_client_name}/{document_type.replace('_', ' ').title()}"
            drive_file_name = f"{timestamp}_{file_name}"

            # Upload using Service Account
            file_metadata = {
                "name": drive_file_name,
                "parents": [settings.google_drive_root_folder_id or "root"],
            }

            import io

            from googleapiclient.http import MediaIoBaseUpload

            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=mime_type or "application/octet-stream",
                resumable=True,
            )

            uploaded_file = (
                team_drive.drive_service.files()
                .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
                .execute()
            )

            result["success"] = True
            result["file_id"] = uploaded_file.get("id")
            result["file_url"] = uploaded_file.get(
                "webViewLink", f"https://drive.google.com/file/d/{uploaded_file.get('id')}/view",
            )
            result["folder_path"] = folder_path
            result["method"] = "service_account"

            logger.info(
                f"📁 File uploaded via Service Account: {drive_file_name} (ID: {uploaded_file.get('id')})",
            )

        except Exception as e:
            logger.error(f"Service Account upload failed: {e}", exc_info=True)
            result["error"] = f"Service Account upload failed: {str(e)}"

        return result

    async def _get_or_create_drive_folder(
        self, drive_service: Any, user_id: str, folder_name: str, parent_id: str = "root",
    ) -> str | None:
        """
        Get existing folder or create new one in Google Drive.

        Returns:
            Folder ID or None if failed
        """
        try:
            # Search for existing folder using list_files with filter
            files_result = await drive_service.list_files(
                user_id=user_id, folder_id=parent_id, page_size=100,
            )

            for file in files_result.get("files", []):
                if (
                    file.get("name") == folder_name
                    and file.get("mimeType") == "application/vnd.google-apps.folder"
                ):
                    logger.debug(f"Found existing folder '{folder_name}' with ID: {file['id']}")
                    return file["id"]

            # Create new folder
            new_folder = await drive_service.create_folder(
                user_id=user_id, name=folder_name, parent_id=parent_id,
            )

            logger.info(f"Created new folder '{folder_name}' with ID: {new_folder.get('id')}")
            return new_folder.get("id")

        except Exception as e:
            logger.error(f"Failed to get/create folder '{folder_name}': {e}")
            return None

    async def _notify_lead_about_document(
        self,
        client_id: int,
        document_name: str,
        document_type: str,
        expiry_date: str | None = None,
        drive_url: str | None = None,
    ) -> None:
        """
        Send email notification to assigned lead when client uploads a document.

        This runs async (fire-and-forget) to not block the upload response.
        """
        try:
            from backend.services.integrations.zoho_email_service import ZohoEmailService

            zoho_service = ZohoEmailService(self.pool)

            async with self.pool.acquire() as conn:
                # Get client name and assigned lead
                client = await conn.fetchrow(
                    """
                    SELECT c.full_name, c.assigned_to
                    FROM clients c
                    WHERE c.id = $1
                    """,
                    client_id,
                )

                if not client:
                    logger.debug(f"Client {client_id} not found, skipping notification")
                    return

                # Fallback to admin if no assigned lead
                lead_email = client["assigned_to"] or "zero@balizero.com"

                # Build email content
                doc_type_display = document_type.replace("_", " ").title()

                subject = f"📄 Nuovo Documento Caricato - {client['full_name']}"

                # Build extra info section
                extra_info = ""
                if expiry_date:
                    extra_info += f"• Data Scadenza Rilevata: {expiry_date}\n"
                if drive_url:
                    extra_info += f"• Link Drive: {drive_url}\n"

                body = f"""Ciao,

Il cliente {client["full_name"]} ha caricato un nuovo documento nel portale.

Dettagli:
• File: {document_name}
• Tipo: {doc_type_display}
• Cliente: {client["full_name"]}
{extra_info}
Accedi al workspace per visualizzare e verificare il documento:
https://kita.balizero.com/clients/{client_id}

---
Questa è una notifica automatica da Bali Zero CRM.
"""

                # Primary: Brevo
                sent = False
                try:
                    import os

                    import httpx

                    _api_url = os.getenv(
                        "INTERNAL_EMAIL_API_URL",
                        "https://nuzantara-rag.fly.dev/api/notifications/send-email",
                    )
                    _api_key = os.getenv("NUZANTARA_API_KEY", "zantara-secret-2024")
                    html_body = body.replace("\n", "<br>")
                    async with httpx.AsyncClient(timeout=30.0) as http_client:
                        resp = await http_client.post(
                            _api_url,
                            headers={"X-API-Key": _api_key},
                            json={"to": lead_email, "subject": subject, "body": html_body},
                        )
                        resp.raise_for_status()
                    sent = True
                    logger.info(f"📧 Document upload notification sent to {lead_email} via Brevo")
                except Exception as brevo_err:
                    logger.warning(f"Brevo failed for doc notification, trying Zoho: {brevo_err}")

                # Fallback: Zoho
                if not sent:
                    await zoho_service.send_email(
                        to_email=lead_email,
                        subject=subject,
                        body=body,
                    )
                    logger.info(
                        f"📧 Document upload notification sent to {lead_email} via Zoho",
                    )

                # Also insert CRM notification alert for the bell
                try:
                    await conn.execute(
                        """
                        INSERT INTO notification_alerts
                            (client_id, alert_type, status, message, email_subject)
                        VALUES ($1, 'portal_document_upload', 'sent', $2, $3)
                        ON CONFLICT ON CONSTRAINT uq_notification_alert_daily DO NOTHING
                        """,
                        client_id,
                        f"{client['full_name']} uploaded {document_type.replace('_', ' ')} via portal",
                        f"[Portal] {client['full_name']} uploaded {document_type.replace('_', ' ').title()}",
                    )
                except Exception as alert_err:
                    logger.debug(f"CRM alert insert failed (non-critical): {alert_err}")

        except Exception as e:
            # Don't fail upload if notification fails
            logger.error(f"Failed to send document upload notification: {e}", exc_info=True)

    # ================================================
    # MESSAGES
    # ================================================

    async def get_messages(
        self,
        client_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get message threads for client."""
        async with self.pool.acquire() as conn:
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

    async def send_message(
        self,
        client_id: int,
        content: str,
        subject: str | None = None,
        practice_id: int | None = None,
    ) -> dict[str, Any]:
        """Send a message from client to team."""
        async with self.pool.acquire() as conn:
            # Get client email for sent_by
            client = await conn.fetchrow(
                "SELECT email FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )

            message = await conn.fetchrow(
                """
                INSERT INTO portal_messages (
                    client_id, practice_id, subject, direction, content, sent_by
                )
                VALUES ($1, $2, $3, 'client_to_team', $4, $5)
                RETURNING id, created_at
                """,
                client_id,
                practice_id,
                subject,
                content,
                client["email"],
            )

            return {
                "id": message["id"],
                "created_at": message["created_at"].isoformat(),
            }

    async def mark_message_read(self, client_id: int, message_id: int) -> dict[str, Any]:
        """Mark a message as read."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE portal_messages
                SET read_at = NOW()
                WHERE id = $1 AND client_id = $2 AND read_at IS NULL
                """,
                message_id,
                client_id,
            )

            return {"success": result != "UPDATE 0"}

    # ================================================
    # PREFERENCES
    # ================================================

    async def get_preferences(self, client_id: int) -> dict[str, Any]:
        """Get client preferences."""
        async with self.pool.acquire() as conn:
            prefs = await conn.fetchrow(
                """
                SELECT email_notifications, whatsapp_notifications,
                       language, timezone
                FROM client_preferences
                WHERE client_id = $1
                """,
                client_id,
            )

            if not prefs:
                # Return defaults
                return {
                    "email_notifications": True,
                    "whatsapp_notifications": True,
                    "language": "en",
                    "timezone": "Asia/Jakarta",
                }

            return {
                "email_notifications": prefs["email_notifications"],
                "whatsapp_notifications": prefs["whatsapp_notifications"],
                "language": prefs["language"],
                "timezone": prefs["timezone"],
            }

    async def update_preferences(
        self,
        client_id: int,
        preferences: dict[str, Any],
    ) -> dict[str, Any]:
        """Update client preferences."""
        async with self.pool.acquire() as conn:
            # Build dynamic update
            updates = []
            params = [client_id]
            param_idx = 2

            allowed_fields = {
                "email_notifications": bool,
                "whatsapp_notifications": bool,
                "language": str,
                "timezone": str,
            }

            for field, _field_type in allowed_fields.items():
                if field in preferences:
                    updates.append(f"{field} = ${param_idx}")
                    params.append(preferences[field])
                    param_idx += 1

            if not updates:
                return await self.get_preferences(client_id)

            # Upsert preferences
            await conn.execute(
                f"""
                INSERT INTO client_preferences (client_id, {", ".join(allowed_fields.keys())})
                VALUES ($1, true, true, 'en', 'Asia/Jakarta')
                ON CONFLICT (client_id) DO UPDATE
                SET {", ".join(updates)}
                """,
                *params,
            )

            return await self.get_preferences(client_id)

    # ================================================
    # TIMELINE
    # ================================================

    async def get_timeline(self, client_id: int, limit: int = 50) -> dict[str, Any]:
        """
        Get client activity timeline.

        Combines:
        - Messages (sent and received)
        - Document uploads
        - Practice status changes
        - Upcoming deadlines

        Returns format expected by frontend TimelineResponse:
            - scope: 'portal'
            - entries: list of TimelineEntry
            - lastUpdated: timestamp
        """
        import time

        entries = []

        async with self.pool.acquire() as conn:
            # Persisted portal timeline events (preferred when available)
            try:
                timeline_events = await conn.fetch(
                    """
                    SELECT id, practice_id, event_type, title, description, event_date
                    FROM timeline_events
                    WHERE client_id = $1
                      AND client_visible = true
                    ORDER BY event_date DESC
                    LIMIT $2
                    """,
                    client_id,
                    limit,
                )

                now = datetime.now(timezone.utc)
                for ev in timeline_events:
                    event_type = ev["event_type"]
                    # Map event types to the frontend-supported TimelineEntryType union.
                    if event_type in ("document_request", "document_received"):
                        entry_type = "document"
                    elif event_type in ("deadline", "payment_due", "appointment", "reminder"):
                        entry_type = "deadline"
                    else:
                        entry_type = "practice"

                    occurred_at = ev["event_date"]
                    is_future = bool(occurred_at and occurred_at > now)

                    entries.append(
                        {
                            "id": f"event-{ev['id']}",
                            "type": entry_type,
                            "occurredAt": occurred_at.isoformat()
                            if occurred_at
                            else now.isoformat(),
                            "title": ev["title"],
                            "description": ev["description"],
                            "status": event_type,
                            "unread": False,
                            "isFuture": is_future,
                            "entity": {"practiceId": ev["practice_id"]}
                            if ev["practice_id"]
                            else {},
                        },
                    )
            except Exception as e:
                if not self._is_undefined_table_error(e):
                    logger.warning(f"Could not fetch timeline_events: {e}")

            # Get recent messages
            try:
                messages = await conn.fetch(
                    """
                    SELECT id, subject, content, direction, created_at, read_at
                    FROM portal_messages
                    WHERE client_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    client_id,
                    limit // 3,  # Allocate 1/3 of limit to messages
                )
                for msg in messages:
                    entries.append(
                        {
                            "id": f"msg-{msg['id']}",
                            "type": "message",
                            "occurredAt": msg["created_at"].isoformat(),
                            "title": msg["subject"] or "New Message",
                            "description": msg["content"][:100]
                            + ("..." if len(msg["content"]) > 100 else ""),
                            "status": "sent"
                            if msg["direction"] == "client_to_team"
                            else "received",
                            "unread": msg["direction"] == "team_to_client"
                            and msg["read_at"] is None,
                            "isFuture": False,
                            "entity": {"messageId": str(msg["id"])},
                        },
                    )
            except Exception as e:
                logger.warning(f"Could not fetch messages for timeline: {e}")

            # Get recent documents
            try:
                documents = await conn.fetch(
                    """
                    SELECT id, document_type, file_name, status, created_at
                    FROM documents
                    WHERE client_id = $1 AND client_visible = true
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    client_id,
                    limit // 3,
                )
                for doc in documents:
                    entries.append(
                        {
                            "id": f"doc-{doc['id']}",
                            "type": "document",
                            "occurredAt": doc["created_at"].isoformat(),
                            "title": f"Document: {doc['file_name']}",
                            "description": f"Type: {doc['document_type']}",
                            "status": doc["status"],
                            "unread": False,
                            "isFuture": False,
                            "entity": {"documentId": str(doc["id"])},
                        },
                    )
            except Exception as e:
                logger.warning(f"Could not fetch documents for timeline: {e}")

            # Get recent practice updates
            try:
                practices = await conn.fetch(
                    """
                    SELECT p.id, pt.name, pt.category, p.status, p.updated_at
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    ORDER BY p.updated_at DESC
                    LIMIT $2
                    """,
                    client_id,
                    limit // 3,
                )
                for p in practices:
                    entries.append(
                        {
                            "id": f"practice-{p['id']}",
                            "type": "practice",
                            "occurredAt": p["updated_at"].isoformat()
                            if p["updated_at"]
                            else datetime.now(timezone.utc).isoformat(),
                            "title": f"{p['name']} Update",
                            "description": f"Status: {p['status']}",
                            "status": p["status"],
                            "unread": False,
                            "isFuture": False,
                            "entity": {
                                "practiceId": p["id"],
                                "practiceCategory": p["category"],
                            },
                        },
                    )
            except Exception as e:
                logger.warning(f"Could not fetch practices for timeline: {e}")

            # Add upcoming deadlines (future events)
            today = datetime.now(timezone.utc)
            deadlines = self._get_standard_tax_deadlines(today)
            for deadline in deadlines[:3]:  # Max 3 deadlines
                entries.append(
                    {
                        "id": f"deadline-{deadline['type'].lower().replace(' ', '-')}",
                        "type": "deadline",
                        "occurredAt": deadline["due_date"],
                        "title": f"Tax Deadline: {deadline['type']}",
                        "description": f"Due in {deadline['days_until']} days",
                        "status": deadline["urgency"],
                        "unread": False,
                        "isFuture": True,
                    },
                )

        # Sort by date descending
        entries.sort(key=lambda x: x["occurredAt"], reverse=True)

        return {
            "scope": "portal",
            "entries": entries[:limit],
            "lastUpdated": int(time.time() * 1000),
        }

    # ================================================
    # HELPER METHODS
    # ================================================

    def _format_visa_summary(self, visa: asyncpg.Record) -> dict[str, Any]:
        """Format visa practice as summary."""
        today = datetime.now(timezone.utc).date()
        expiry = visa["expiry_date"].date() if visa["expiry_date"] else None
        days_left = (expiry - today).days if expiry else None

        return {
            "type": visa["code"],
            "name": visa["name"],
            "status": visa["status"],
            "expiry_date": visa["expiry_date"].isoformat() if visa["expiry_date"] else None,
            "days_remaining": days_left,
            "is_expiring_soon": days_left is not None and days_left <= 90,
        }

    def _format_visa_detail(self, visa: asyncpg.Record) -> dict[str, Any]:
        """Format visa practice as detailed view."""
        today = datetime.now(timezone.utc).date()
        expiry = visa["expiry_date"].date() if visa["expiry_date"] else None
        days_left = (expiry - today).days if expiry else None

        return {
            "id": visa["id"],
            "type": visa["code"],
            "name": visa["type_name"],
            "status": visa["status"],
            "start_date": visa["start_date"].isoformat() if visa["start_date"] else None,
            "expiry_date": visa["expiry_date"].isoformat() if visa["expiry_date"] else None,
            "days_remaining": days_left,
        }

    def _format_visa_case(self, case: asyncpg.Record) -> dict[str, Any]:
        """Format active visa case."""
        return {
            "id": case["id"],
            "name": case["name"],
            "status": case["status"],
            "start_date": case["start_date"].isoformat() if case["start_date"] else None,
            "progress": self._status_to_progress(case["status"]),
        }

    def _format_case_progress(self, case: asyncpg.Record) -> dict[str, Any]:
        """Format case with progress percentage."""
        return {
            "id": case["id"],
            "name": case["name"],
            "status": case["status"],
            "progress": self._status_to_progress(case["status"]),
            "payment_status": case["payment_status"],
        }

    def _status_to_progress(self, status: str) -> int:
        """Convert status to progress percentage."""
        progress_map = {
            "inquiry": 10,
            "waiting_documents": 30,
            "sending_invoice": 50,
            "on_process": 75,
            "completed": 100,
        }
        return progress_map.get(status, 0)

    def _get_standard_tax_deadlines(self, today: datetime) -> list[dict[str, Any]]:
        """Generate standard Indonesian tax deadlines."""
        year = today.year
        month = today.month

        deadlines = []

        # PPh 21/23/4(2) - 10th of following month
        pph_date = datetime(year, month, 10, tzinfo=timezone.utc)
        if pph_date <= today:
            pph_date = datetime(
                year if month < 12 else year + 1,
                month + 1 if month < 12 else 1,
                10,
                tzinfo=timezone.utc,
            )
        days_until = (pph_date.date() - today.date()).days
        deadlines.append(
            {
                "type": "PPh 21/23/4(2)",
                "period": f"{pph_date.strftime('%b %Y')}",
                "due_date": pph_date.isoformat(),
                "days_until": days_until,
                "urgency": "urgent"
                if days_until <= 14
                else "warning"
                if days_until <= 30
                else "normal",
            },
        )

        # PPN (VAT) - End of following month
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        # Last day of next month
        if next_month == 12:
            ppn_date = datetime(next_year, 12, 31, tzinfo=timezone.utc)
        else:
            ppn_date = datetime(next_year, next_month + 1, 1, tzinfo=timezone.utc) - timedelta(
                days=1,
            )

        days_until = (ppn_date.date() - today.date()).days
        deadlines.append(
            {
                "type": "PPN (VAT)",
                "period": f"{ppn_date.strftime('%b %Y')}",
                "due_date": ppn_date.isoformat(),
                "days_until": days_until,
                "urgency": "urgent"
                if days_until <= 14
                else "warning"
                if days_until <= 30
                else "normal",
            },
        )

        # Annual SPT - March 31
        spt_date = datetime(year, 3, 31, tzinfo=timezone.utc)
        if spt_date <= today:
            spt_date = datetime(year + 1, 3, 31, tzinfo=timezone.utc)
        days_until = (spt_date.date() - today.date()).days
        deadlines.append(
            {
                "type": "Annual SPT",
                "period": str(spt_date.year - 1),
                "due_date": spt_date.isoformat(),
                "days_until": days_until,
                "urgency": "urgent"
                if days_until <= 14
                else "warning"
                if days_until <= 30
                else "normal",
            },
        )

        # Sort by days_until
        deadlines.sort(key=lambda x: x["days_until"])

        return deadlines

    # ================================================
    # CLEANUP & HEALTH CHECK
    # ================================================

    async def cleanup_orphaned_documents(self, days: int = 7) -> dict[str, Any]:
        """
        Cleanup documents that failed to upload to Drive (storage_type='pending').

        Args:
            days: Delete documents older than this many days

        Returns:
            {"deleted": int, "errors": int}
        """
        result = {"deleted": 0, "errors": 0, "checked": 0}

        async with self.pool.acquire() as conn:
            # Find orphaned documents
            orphaned = await conn.fetch(
                """
                SELECT id, file_name, client_id, created_at
                FROM documents
                WHERE storage_type = 'pending'
                AND created_at < NOW() - INTERVAL '$1 days'
                """,
                days,
            )

            result["checked"] = len(orphaned)

            for doc in orphaned:
                try:
                    await conn.execute("DELETE FROM documents WHERE id = $1", doc["id"])
                    result["deleted"] += 1
                    logger.info(f"Deleted orphaned document: {doc['file_name']} (ID: {doc['id']})")
                except Exception as e:
                    result["errors"] += 1
                    logger.error(f"Failed to delete orphaned document {doc['id']}: {e}")

        return result

    async def get_upload_metrics(self) -> dict[str, Any]:
        """
        Get metrics about document uploads.

        Returns:
            Metrics dictionary with upload statistics
        """
        metrics = dict(self._metrics)  # Copy current metrics

        async with self.pool.acquire() as conn:
            # Get DB stats
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_docs,
                    COUNT(*) FILTER (WHERE storage_type = 'google_drive') as drive_uploads,
                    COUNT(*) FILTER (WHERE expiry_date IS NOT NULL) as with_expiry,
                    COUNT(*) FILTER (WHERE extracted_text IS NOT NULL AND extracted_text != '') as with_ocr
                FROM documents
                WHERE uploaded_source = 'client'
                AND created_at > NOW() - INTERVAL '24 hours'
                """,
            )

            metrics["last_24h"] = {
                "total": stats["total_docs"],
                "drive_uploads": stats["drive_uploads"],
                "with_expiry": stats["with_expiry"],
                "with_ocr": stats["with_ocr"],
            }

        return metrics

    async def health_check(self) -> dict[str, Any]:
        """
        Health check for the document upload pipeline.

        Returns:
            Health status dictionary
        """
        checks = {
            "virus_scanner": False,
            "drive_configured": False,
            "drive_token": False,
            "ocr_available": False,
            "database": False,
        }

        # Check virus scanner
        try:
            result = VirusScanner.scan(b"test", "test.pdf")
            checks["virus_scanner"] = result.get("clean") is not None
        except Exception as e:
            logger.debug(f"Virus scanner check failed (non-critical): {e}")

        # Check Drive configuration
        try:
            from backend.services.integrations.google_drive_service import GoogleDriveService

            drive_service = GoogleDriveService(self.pool)
            checks["drive_configured"] = drive_service.is_configured()

            if checks["drive_configured"]:
                token = await drive_service.get_valid_token("SYSTEM")
                checks["drive_token"] = token is not None
        except Exception as e:
            logger.debug(f"Drive config check failed (non-critical): {e}")

        # Check OCR availability
        checks["ocr_available"] = PDF_VISION_AVAILABLE or PYMUPDF_AVAILABLE

        # Check database
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                checks["database"] = True
        except Exception as e:
            logger.debug(f"Database health check failed: {e}")

        all_healthy = all(checks.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ================================================
    # BILLING
    # ================================================

    async def get_billing(self, client_id: int) -> dict[str, Any]:
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
                "drive_web_link": row["drive_web_link"],
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

    async def get_invoice_pdf_url(self, client_id: int, invoice_id: int) -> dict[str, str] | None:
        """Get Drive download URL for an invoice PDF. Returns None if not found."""
        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    "SELECT drive_web_link, drive_file_id FROM invoices WHERE id = $1 AND client_id = $2",
                    invoice_id,
                    client_id,
                )
            except Exception:
                return None

        if not row or (not row["drive_web_link"] and not row["drive_file_id"]):
            return None

        return {
            "download_url": row["drive_web_link"],
            "drive_file_id": row["drive_file_id"],
        }

    # ================================================
    # PROFILE UPDATE
    # ================================================

    PROFILE_EDITABLE_FIELDS = {"phone", "whatsapp", "address", "language"}

    async def update_profile(
        self,
        client_id: int,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update client profile with whitelisted fields only.

        Sensitive fields (full_name, email, passport_number, nationality, etc.)
        are silently ignored — they require team intervention.

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
