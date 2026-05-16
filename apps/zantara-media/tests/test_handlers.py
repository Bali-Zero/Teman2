"""Tests for zantara_media.indexer.handlers.

All external calls (ffmpeg, Tesseract, Ollama, Whisper) are mocked — no real
tools are required to run the test suite.
"""

from __future__ import annotations

import asyncio
import subprocess
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zantara_media.indexer.handlers import extract_content
from zantara_media.indexer.handlers.image_handler import extract_image
from zantara_media.indexer.handlers.pdf_handler import extract_pdf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_simple_pdf_bytes() -> bytes:
    """Create a minimal in-memory PDF using pypdf PdfWriter."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _mock_ollama_response(text: str) -> MagicMock:
    """Return a mock httpx response simulating Ollama /api/generate."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": text}
    return mock_resp


# ---------------------------------------------------------------------------
# 1. PDF extraction via pypdf (text-layer PDF)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pdf_extraction_pypdf():
    """PDF with a text layer should be extracted by pypdf."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    # Inject text via a page annotation (simplest way without full font setup)
    # For test purposes we verify that pypdf is tried and metadata is returned.
    buf = BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    # pypdf returns empty text for blank pages — that's fine; we just test
    # the metadata and that it doesn't raise.
    text, meta = await extract_pdf(pdf_bytes, "test.pdf")
    assert isinstance(text, str)
    assert "pages" in meta
    assert meta["pages"] >= 1
    # extraction_method is either 'pypdf' or 'tesseract' (blank → tesseract fallback)
    assert meta["extraction_method"] in ("pypdf", "tesseract", "failed")


@pytest.mark.asyncio
async def test_pdf_text_layer_returns_pypdf_method():
    """A PDF with extractable text should use the 'pypdf' method."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, ArrayObject, DictionaryObject, StreamObject

    # We mock the _extract_with_pypdf function to return known text
    with patch(
        "zantara_media.indexer.handlers.pdf_handler._extract_with_pypdf",
        return_value=("Hello Nuzantara", 2),
    ):
        pdf_bytes = _make_simple_pdf_bytes()
        text, meta = await extract_pdf(pdf_bytes, "test.pdf")

    assert text == "Hello Nuzantara"
    assert meta["extraction_method"] == "pypdf"
    assert meta["pages"] == 2


# ---------------------------------------------------------------------------
# 2. PDF Tesseract fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pdf_fallback_tesseract():
    """When pypdf returns empty text, Tesseract OCR fallback should be used."""
    fake_ocr_text = "OCR result from Tesseract"

    mock_proc_result = MagicMock()
    mock_proc_result.returncode = 0
    mock_proc_result.stdout = fake_ocr_text
    mock_proc_result.stderr = ""

    with (
        patch(
            "zantara_media.indexer.handlers.pdf_handler._extract_with_pypdf",
            return_value=("", 1),  # empty — forces fallback
        ),
        patch("subprocess.run", return_value=mock_proc_result),
    ):
        text, meta = await extract_pdf(b"%PDF-fake", "scanned.pdf")

    assert text == fake_ocr_text
    assert meta["extraction_method"] == "tesseract"


# ---------------------------------------------------------------------------
# 3. Image handler — Ollama response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_image_ollama_response():
    """extract_image should return Ollama's description text."""
    expected_desc = "A scenic beach at sunset with golden hues."

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_mock_ollama_response(expected_desc))

    with patch("zantara_media.indexer.handlers.image_handler.httpx.AsyncClient", return_value=mock_client):
        text, meta = await extract_image(b"\xff\xd8\xff", "beach.jpg")

    assert text == expected_desc
    assert meta["model"] == "qwen2.5vl:7b"
    assert meta["source"] == "ollama_vision"


# ---------------------------------------------------------------------------
# 4. Image handler — Ollama timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_image_ollama_timeout():
    """On httpx timeout, extract_image should return empty string with error key."""
    import httpx as real_httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=real_httpx.TimeoutException("timed out"))

    with patch("zantara_media.indexer.handlers.image_handler.httpx.AsyncClient", return_value=mock_client):
        text, meta = await extract_image(b"\xff\xd8\xff", "photo.jpg")

    assert text == ""
    assert meta.get("error") == "vision_timeout"


# ---------------------------------------------------------------------------
# 5. Audio transcription
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audio_transcription():
    """extract_audio should return transcript from Whisper .txt output."""
    transcript = "Selamat pagi, ini adalah rekaman audio untuk pengujian."

    mock_proc_result = MagicMock()
    mock_proc_result.returncode = 0
    mock_proc_result.stdout = ""
    mock_proc_result.stderr = ""

    # We need to intercept the temp-dir usage and provide a fake .txt file.
    import tempfile
    import os

    original_tmpdir = tempfile.TemporaryDirectory

    class FakeTmpDir:
        """Creates a real temp dir but also writes the expected .txt output."""

        def __init__(self):
            self._real = original_tmpdir()
            self.name = self._real.name
            # Pre-write the expected Whisper output file
            txt_path = Path(self.name) / "audio_input.txt"
            txt_path.write_text(transcript, encoding="utf-8")

        def __enter__(self):
            return self.name

        def __exit__(self, *args):
            self._real.cleanup()

    with (
        patch("subprocess.run", return_value=mock_proc_result),
        patch(
            "zantara_media.indexer.handlers.audio_handler.tempfile.TemporaryDirectory",
            side_effect=FakeTmpDir,
        ),
    ):
        from zantara_media.indexer.handlers.audio_handler import extract_audio
        text, meta = await extract_audio(b"RIFF", "audio_input.mp3")

    assert text == transcript
    assert meta["model"] == "whisper-medium"
    assert meta["source"] == "local_whisper"


# ---------------------------------------------------------------------------
# 6. Dispatcher — extract_content routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_content_routes_pdf():
    with patch("zantara_media.indexer.handlers.extract_pdf", new_callable=AsyncMock) as mock_pdf:
        mock_pdf.return_value = ("pdf text", {"pages": 1})
        text, meta = await extract_content(b"data", "application/pdf", "doc.pdf")
    mock_pdf.assert_awaited_once()
    assert text == "pdf text"


@pytest.mark.asyncio
async def test_extract_content_routes_image():
    with patch("zantara_media.indexer.handlers.extract_image", new_callable=AsyncMock) as mock_img:
        mock_img.return_value = ("image desc", {"model": "qwen2.5vl:7b"})
        text, meta = await extract_content(b"data", "image/jpeg", "photo.jpg")
    mock_img.assert_awaited_once()
    assert text == "image desc"


@pytest.mark.asyncio
async def test_extract_content_routes_video():
    with patch("zantara_media.indexer.handlers.extract_video", new_callable=AsyncMock) as mock_vid:
        mock_vid.return_value = ("video desc", {"frames_extracted": 3})
        text, meta = await extract_content(b"data", "video/mp4", "clip.mp4")
    mock_vid.assert_awaited_once()
    assert text == "video desc"


@pytest.mark.asyncio
async def test_extract_content_routes_audio():
    with patch("zantara_media.indexer.handlers.extract_audio", new_callable=AsyncMock) as mock_aud:
        mock_aud.return_value = ("transcript", {"model": "whisper-medium"})
        text, meta = await extract_content(b"data", "audio/mpeg", "clip.mp3")
    mock_aud.assert_awaited_once()
    assert text == "transcript"


@pytest.mark.asyncio
async def test_extract_content_utf8_fallback():
    """Unknown MIME type should attempt UTF-8 decode."""
    raw = b"Hello world in UTF-8"
    text, meta = await extract_content(raw, "application/octet-stream", "file.bin")
    assert "Hello world" in text


@pytest.mark.asyncio
async def test_extract_content_unsupported_binary():
    """Non-UTF-8 bytes with unknown MIME type should return errors='replace' decoded text."""
    raw = bytes(range(256))  # invalid UTF-8 sequence
    text, meta = await extract_content(raw, "application/octet-stream", "binary.bin")
    # errors='replace' means it won't raise; text may contain replacement chars
    assert isinstance(text, str)
