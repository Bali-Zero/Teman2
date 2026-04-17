"""
Portal document processing helpers.

Extracted from portal_service.py (Wave 1 refactor, PR #?):
- VirusScanner: file upload heuristics (MIME allowlist, pattern/extension scan)
- DocumentOCR: Gemini Vision OCR for PDFs and images
- ExpiryDetector: regex+keyword date extraction for passports/visas/etc.

All three classes are stateless (classmethod-only) and safe to import directly.
"""

import io
import re
from typing import Any

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


__all__ = [
    "VirusScanner",
    "DocumentOCR",
    "ExpiryDetector",
    "PDF_VISION_AVAILABLE",
    "PYMUPDF_AVAILABLE",
    "MAGIC_AVAILABLE",
]
