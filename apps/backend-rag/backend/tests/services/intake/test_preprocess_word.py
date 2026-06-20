"""Unit tests for Word (.docx/.doc) text extraction in preprocess_blob.

Word documents arriving via WhatsApp were previously vision-only fodder: the
pipeline OCR'd the raw .docx zip bytes to garbage -> classify "unknown" -> a
real contract/akta silently lost (the 9 Word docs found in adit's intake,
2026-06-20). preprocess_blob now branches on the wordprocessing mimes and emits
a single born-digital PageImage(text=...) -- reusing the exact text-layer
contract the PDF fast-path already feeds to classify.ocr_pages.

python-docx is monkeypatched (via the parsers.extract_text_from_docx import) so
no real .docx file or library round-trip is needed.
"""

from __future__ import annotations

import pytest

from backend.services.intake import preprocess as pre
from backend.services.intake.preprocess import PageImage

_DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_DOC_MIME = "application/msword"

# Synthetic, non-PII Word body text.
_WORD_TEXT = (
    "SURAT PERJANJIAN KERJA SAMA antara PT CONTOH SEJAHTERA dan MITRA ABADI "
    "tentang penyediaan jasa konsultasi perizinan berusaha tahun 2026."
)


def test_word_mimes_constant_covers_docx_and_doc() -> None:
    assert _DOCX_MIME in pre._WORD_MIMES
    assert _DOC_MIME in pre._WORD_MIMES


@pytest.mark.asyncio
async def test_docx_emits_textlayer_page(monkeypatch, tmp_path) -> None:
    # Arrange: a file present on disk + a stubbed docx text extractor.
    blob = tmp_path / "contract.docx"
    blob.write_bytes(b"PK\x03\x04 fake docx zip bytes")

    monkeypatch.setattr(
        "backend.core.parsers.extract_text_from_docx",
        lambda path: _WORD_TEXT,
    )

    # Act
    result = await pre.preprocess_blob(str(blob), declared_mime=_DOCX_MIME)

    # Assert: one born-digital page, text set verbatim, no image bytes, mime kept.
    assert result.n_pages == 1
    page = result.pages[0]
    assert isinstance(page, PageImage)
    assert page.text == _WORD_TEXT
    assert page.png_bytes == b""  # no image to OCR
    assert result.mime == _DOCX_MIME
    assert result.notes == "word_textlayer"


@pytest.mark.asyncio
async def test_unreadable_word_degrades_gracefully(monkeypatch, tmp_path) -> None:
    # A legacy/corrupt .doc that python-docx cannot parse must NOT crash the
    # stage: it degrades to a single empty page (text=None) so classify routes
    # it to human review as "unknown".
    blob = tmp_path / "legacy.doc"
    blob.write_bytes(b"\xd0\xcf\x11\xe0 legacy OLE bytes")

    def _boom(path: str) -> str:
        raise ValueError("python-docx cannot read legacy .doc")

    monkeypatch.setattr("backend.core.parsers.extract_text_from_docx", _boom)

    result = await pre.preprocess_blob(str(blob), declared_mime=_DOC_MIME)

    assert result.n_pages == 1
    page = result.pages[0]
    assert page.text is None
    assert page.png_bytes == b""
    assert result.notes == "word_extract_failed"


@pytest.mark.asyncio
async def test_empty_docx_text_degrades(monkeypatch, tmp_path) -> None:
    # An empty/whitespace-only extraction is treated as "no usable text" -> the
    # graceful empty-page path, never a textlayer page with blank content.
    blob = tmp_path / "blank.docx"
    blob.write_bytes(b"PK\x03\x04 fake")

    monkeypatch.setattr(
        "backend.core.parsers.extract_text_from_docx",
        lambda path: "   \n  ",
    )

    result = await pre.preprocess_blob(str(blob), declared_mime=_DOCX_MIME)

    assert result.pages[0].text is None
    assert result.notes == "word_extract_failed"
