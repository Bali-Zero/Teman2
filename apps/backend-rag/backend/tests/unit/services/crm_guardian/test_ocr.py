"""Unit tests for CRM-Guardian Phase 1.5 OCR module.

Focus: pure logic that doesn't require live tesseract/Ollama. Integration
tests for the actual extractor cascade live separately and exercise the
real subprocess + Ollama paths (run-on-Pro only, gated by env var).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.crm_guardian.ocr import (
    MAX_TEXT_CHARS_PER_FILE,
    PRIORITY_DOC_TYPES,
    ExtractionResult,
    OcrHealth,
    _truncate,
    check_health,
    extract_file_content,
)

# ---------------------------------------------------------------------------
# Priority list / constants
# ---------------------------------------------------------------------------


def test_priority_doc_types_include_critical_categories():
    """Identity-bearing + compliance-bearing doc_types must all be in scope."""
    required = {
        "passport",
        "evisa",
        "visa",
        "kitas",
        "kitap",  # identity + visa
        "nib",
        "npwp",
        "akta",
        "sk",  # corporate
        "lkpm",
        "spt",
        "bukti_potong",
        "tax_record",  # tax/lkpm
    }
    assert required.issubset(PRIORITY_DOC_TYPES), (
        f"Missing priority doc_types: {required - PRIORITY_DOC_TYPES}"
    )


def test_priority_doc_types_excludes_misc():
    """Random files (photos, drafts) MUST NOT trigger OCR — too expensive."""
    excluded = {"other", "photo", "draft", "screenshot", "memo"}
    overlap = PRIORITY_DOC_TYPES & excluded
    assert not overlap, f"Misc doc_types leaked into priority: {overlap}"


# ---------------------------------------------------------------------------
# _truncate helper
# ---------------------------------------------------------------------------


def test_truncate_short_text_passthrough():
    text = "hello world"
    out, truncated = _truncate(text)
    assert out == text
    assert truncated is False


def test_truncate_long_text_caps_to_limit():
    text = "a" * (MAX_TEXT_CHARS_PER_FILE + 500)
    out, truncated = _truncate(text)
    assert len(out) == MAX_TEXT_CHARS_PER_FILE
    assert truncated is True


def test_truncate_custom_limit():
    text = "abcdefghij"
    out, truncated = _truncate(text, limit=5)
    assert out == "abcde"
    assert truncated is True


# ---------------------------------------------------------------------------
# ExtractionResult invariants
# ---------------------------------------------------------------------------


def test_extraction_result_content_hash_deterministic():
    r1 = ExtractionResult(
        text="Akta Pendirian PT Bali Zero",
        extractor="tesseract",
        confidence=0.85,
        page_count=3,
        duration_ms=1234,
        truncated=False,
    )
    r2 = ExtractionResult(
        text="Akta Pendirian PT Bali Zero",
        extractor="pdfminer",
        confidence=None,
        page_count=3,
        duration_ms=99,
        truncated=False,
    )
    # Same text → same hash regardless of extractor
    assert r1.content_hash == r2.content_hash
    assert len(r1.content_hash) == 64  # sha256 hex


def test_extraction_result_content_hash_differs_on_text_change():
    r1 = ExtractionResult(
        text="version A",
        extractor="tesseract",
        confidence=0.8,
        page_count=1,
        duration_ms=10,
        truncated=False,
    )
    r2 = ExtractionResult(
        text="version B",
        extractor="tesseract",
        confidence=0.8,
        page_count=1,
        duration_ms=10,
        truncated=False,
    )
    assert r1.content_hash != r2.content_hash


# ---------------------------------------------------------------------------
# extract_file_content — gating on doc_type / mime
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_skips_non_priority_doc_type():
    """Files with doc_type='other' must skip OCR even if PDF (saves budget)."""
    health = OcrHealth(
        tesseract_ok=True,
        tesseract_version="t",
        pdfminer_ok=True,
        pypdfium2_ok=True,
        ollama_vision_ok=True,
        ollama_vision_model="qwen2.5vl:7b",
        detail="all-ok",
    )
    result = await extract_file_content(
        file_bytes=b"%PDF-1.4 fake",
        mime_type="application/pdf",
        doc_type="other",
        health=health,
    )
    assert result.extractor == "skipped"
    assert result.text == ""
    assert "non_priority" in (result.notes or "")


@pytest.mark.asyncio
async def test_extract_skips_unsupported_mime():
    health = OcrHealth(
        tesseract_ok=True,
        tesseract_version="t",
        pdfminer_ok=True,
        pypdfium2_ok=True,
        ollama_vision_ok=False,
        ollama_vision_model=None,
        detail="no-vision-fallback",
    )
    # Word doc — out of scope (the worker can route .docx via Drive export,
    # but ocr.py only handles PDF + image)
    result = await extract_file_content(
        file_bytes=b"PK\x03\x04 docx bytes",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        doc_type="akta",
        health=health,
    )
    assert result.extractor == "skipped"
    assert "unsupported_mime" in (result.notes or "")


@pytest.mark.asyncio
async def test_extract_pdfminer_native_text_skips_ocr():
    """When pdfminer recovers ≥200 chars from text layer, OCR cascade skips."""
    health = OcrHealth(
        tesseract_ok=True,
        tesseract_version="t",
        pdfminer_ok=True,
        pypdfium2_ok=True,
        ollama_vision_ok=False,
        ollama_vision_model=None,
        detail="no-vision-fallback",
    )
    long_text = "Akta Pendirian " * 30  # >200 chars

    with patch(
        "backend.services.crm_guardian.ocr._extract_pdfminer",
        new=AsyncMock(return_value=(long_text, 5)),
    ):
        result = await extract_file_content(
            file_bytes=b"%PDF-1.4",
            mime_type="application/pdf",
            doc_type="akta",
            health=health,
        )

    assert result.extractor == "pdfminer"
    assert long_text.strip() in result.text
    assert result.page_count == 5
    assert result.confidence is None  # pdfminer doesn't self-score


@pytest.mark.asyncio
async def test_extract_pdfminer_empty_falls_through_to_tesseract():
    """Scanned PDF (no text layer) must trigger tesseract path."""
    health = OcrHealth(
        tesseract_ok=True,
        tesseract_version="t",
        pdfminer_ok=True,
        pypdfium2_ok=True,
        ollama_vision_ok=False,
        ollama_vision_model=None,
        detail="no-vision-fallback",
    )

    with (
        patch(
            "backend.services.crm_guardian.ocr._extract_pdfminer",
            new=AsyncMock(return_value=("", 2)),
        ),
        patch(
            "backend.services.crm_guardian.ocr._rasterize_pdf_pages",
            new=AsyncMock(return_value=[b"png1", b"png2"]),
        ),
        patch(
            "backend.services.crm_guardian.ocr._tesseract_ocr_png",
            new=AsyncMock(return_value=("scanned passport text", 0.78)),
        ),
    ):
        result = await extract_file_content(
            file_bytes=b"%PDF-1.4 scanned",
            mime_type="application/pdf",
            doc_type="passport",
            health=health,
        )

    assert result.extractor == "tesseract"
    assert "scanned passport text" in result.text
    # 2 pages, both returned the same mocked string
    assert result.text.count("scanned passport text") == 2
    assert result.confidence == pytest.approx(0.78, abs=0.01)
    assert result.page_count == 2


@pytest.mark.asyncio
async def test_extract_low_tesseract_conf_triggers_vision_fallback():
    """Tesseract conf < 0.40 + Ollama up → qwen2.5vl wins if better."""
    health = OcrHealth(
        tesseract_ok=True,
        tesseract_version="t",
        pdfminer_ok=True,
        pypdfium2_ok=True,
        ollama_vision_ok=True,
        ollama_vision_model="qwen2.5vl:7b",
        detail="all-ok",
    )

    with (
        patch(
            "backend.services.crm_guardian.ocr._extract_pdfminer",
            new=AsyncMock(return_value=("", 1)),
        ),
        patch(
            "backend.services.crm_guardian.ocr._rasterize_pdf_pages",
            new=AsyncMock(return_value=[b"png1"]),
        ),
        patch(
            "backend.services.crm_guardian.ocr._tesseract_ocr_png",
            new=AsyncMock(return_value=("blurry text", 0.25)),  # under threshold
        ),
        patch(
            "backend.services.crm_guardian.ocr._qwen25vl_extract",
            new=AsyncMock(return_value=("Crisp passport number A1234567", 0.65)),
        ),
    ):
        result = await extract_file_content(
            file_bytes=b"%PDF-1.4 blurry",
            mime_type="application/pdf",
            doc_type="passport",
            health=health,
        )

    assert result.extractor == "qwen25vl"
    assert "Crisp passport number A1234567" in result.text
    assert result.confidence == pytest.approx(0.65, abs=0.01)


@pytest.mark.asyncio
async def test_extract_low_conf_no_vision_returns_tesseract():
    """If vision unavailable, return the tesseract result even with low conf."""
    health = OcrHealth(
        tesseract_ok=True,
        tesseract_version="t",
        pdfminer_ok=True,
        pypdfium2_ok=True,
        ollama_vision_ok=False,
        ollama_vision_model=None,
        detail="no-vision-fallback",
    )

    with (
        patch(
            "backend.services.crm_guardian.ocr._extract_pdfminer",
            new=AsyncMock(return_value=("", 1)),
        ),
        patch(
            "backend.services.crm_guardian.ocr._rasterize_pdf_pages",
            new=AsyncMock(return_value=[b"png1"]),
        ),
        patch(
            "backend.services.crm_guardian.ocr._tesseract_ocr_png",
            new=AsyncMock(return_value=("weak text", 0.20)),
        ),
    ):
        result = await extract_file_content(
            file_bytes=b"%PDF",
            mime_type="application/pdf",
            doc_type="passport",
            health=health,
        )

    assert result.extractor == "tesseract"
    assert result.text == "weak text"
    assert result.confidence == pytest.approx(0.20, abs=0.01)


@pytest.mark.asyncio
async def test_extract_image_path_goes_straight_to_tesseract():
    """JPG passport scan → no pdfminer, direct tesseract on bytes."""
    health = OcrHealth(
        tesseract_ok=True,
        tesseract_version="t",
        pdfminer_ok=True,
        pypdfium2_ok=True,
        ollama_vision_ok=False,
        ollama_vision_model=None,
        detail="no-vision-fallback",
    )

    with patch(
        "backend.services.crm_guardian.ocr._tesseract_ocr_png",
        new=AsyncMock(return_value=("passport surname JOHN DOE", 0.85)),
    ):
        result = await extract_file_content(
            file_bytes=b"\xff\xd8\xff fake jpeg",
            mime_type="image/jpeg",
            doc_type="passport",
            health=health,
        )

    assert result.extractor == "tesseract"
    assert "JOHN DOE" in result.text
    assert result.page_count == 1


@pytest.mark.asyncio
async def test_extract_no_ocr_stack_returns_skipped_for_scanned_pdf():
    """No tesseract + scanned PDF → can't recover, but pdfminer remnants kept."""
    health = OcrHealth(
        tesseract_ok=False,
        tesseract_version=None,
        pdfminer_ok=True,
        pypdfium2_ok=False,
        ollama_vision_ok=False,
        ollama_vision_model=None,
        detail="no-tesseract,no-pypdfium2,no-vision-fallback",
    )

    with patch(
        "backend.services.crm_guardian.ocr._extract_pdfminer",
        new=AsyncMock(return_value=("", 3)),
    ):
        result = await extract_file_content(
            file_bytes=b"%PDF scanned",
            mime_type="application/pdf",
            doc_type="akta",
            health=health,
        )

    assert result.extractor == "skipped"
    assert "no_ocr_stack" in (result.notes or "")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_health_caches_result():
    """Repeated check_health() returns same instance unless force=True."""
    # First call: real probe (this test may be slow on cold cache)
    h1 = await check_health()
    h2 = await check_health()
    assert h1 is h2  # cached singleton

    h3 = await check_health(force=True)
    # Forced re-probe returns a new instance with the same field values
    # (assuming the system didn't change between probes)
    assert h3.tesseract_ok == h1.tesseract_ok
    assert h3.pdfminer_ok == h1.pdfminer_ok
