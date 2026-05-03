"""PDF content extraction handler with pypdf and Tesseract OCR fallback."""

import asyncio
import logging
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)


async def extract_pdf(file_data: bytes, filename: str) -> tuple[str, dict]:
    """Extract text from a PDF file.

    Tries pypdf first; falls back to Tesseract OCR for scanned PDFs.

    Args:
        file_data: Raw PDF bytes.
        filename: Original filename (used for logging).

    Returns:
        Tuple of (extracted_text, metadata_dict).
    """
    try:
        text, n_pages = await asyncio.to_thread(_extract_with_pypdf, file_data)
    except Exception as exc:
        logger.warning("pypdf failed for %s: %s", filename, exc)
        text = ""
        n_pages = 0

    if text.strip():
        return text, {"pages": n_pages, "extraction_method": "pypdf"}

    logger.info("pypdf returned no text for %s — falling back to Tesseract", filename)
    try:
        ocr_text = await _extract_with_tesseract(file_data, filename)
        return ocr_text, {"pages": n_pages, "extraction_method": "tesseract"}
    except Exception as exc:
        logger.error("Tesseract fallback failed for %s: %s", filename, exc)
        return "", {"pages": n_pages, "extraction_method": "failed", "error": str(exc)}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_with_pypdf(file_data: bytes) -> tuple[str, int]:
    """Blocking pypdf extraction — run inside asyncio.to_thread."""
    from pypdf import PdfReader  # local import keeps top-level fast

    reader = PdfReader(BytesIO(file_data))
    n_pages = len(reader.pages)
    parts: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        parts.append(page_text)
    return "\n".join(parts), n_pages


async def _extract_with_tesseract(file_data: bytes, filename: str) -> str:
    """Run Tesseract OCR on the PDF via subprocess."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_data)
        tmp_path = tmp.name

    result = await asyncio.to_thread(
        subprocess.run,
        ["tesseract", tmp_path, "stdout", "-l", "ind+eng"],
        capture_output=True,
        text=True,
    )

    # Clean up temp file
    await asyncio.to_thread(Path(tmp_path).unlink, True)

    if result.returncode != 0:
        logger.warning("Tesseract exited %d for %s: %s", result.returncode, filename, result.stderr)

    return result.stdout
