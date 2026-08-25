"""A scanned PDF must actually reach a vision model.

Until 2026-08-25 no scanned PDF could be read by this codebase, by two
independent mechanisms, and both failures were silent:

* ``parsers.extract_text_from_pdf`` called ``PDFVisionService.extract_text()``
  as its "last resort vision" step. That method is declared "(for test
  compatibility)" and, absent an AI client, re-reads the PDF with PyMuPDF --
  the step that had just returned nothing. No page was ever rendered, no vision
  model was ever asked. The user-visible failure read "No text extracted from
  PDF (even with OCR/Vision)", i.e. it claimed everything had been tried.
* ``parsers.extract_text_from_pdf_ocr_async`` gated on ``_available``, which
  consults the GEMINI client only, so it gave up whenever cloud vision was
  unconfigured -- the default, since cross-border vision is gated under UU PDP
  Art. 56 -- without ever asking the armed local Ollama engine.

Measured on a real 3-page scanned ministerial decree: 0 characters before,
6,109 after.
"""

import asyncio

import fitz
import pytest

from backend.services.multimodal import pdf_vision_service as vision_module
from backend.services.multimodal.pdf_vision_service import PDFVisionService


@pytest.fixture
def scanned_pdf(tmp_path):
    """A two-page PDF with no text layer, i.e. what a scan looks like."""
    document = fitz.open()
    for _ in range(2):
        document.new_page(width=200, height=200)
    path = tmp_path / "scan.pdf"
    document.save(str(path))
    document.close()
    assert sum(len(page.get_text()) for page in fitz.open(str(path))) == 0
    return str(path)


def _service(monkeypatch, *, ollama=None, gemini=None):
    service = PDFVisionService()

    async def fake_ollama(prompt, image_base64):
        return ollama

    async def fake_gemini(prompt, image_base64):
        return gemini

    monkeypatch.setattr(service, "_analyze_via_ollama", fake_ollama)
    monkeypatch.setattr(service, "_analyze_via_gemini", fake_gemini)
    return service


# ---------------------------------------------------------------------------
# GUILT
# ---------------------------------------------------------------------------


def test_the_local_engine_is_asked_and_its_text_is_returned(monkeypatch, scanned_pdf):
    service = _service(monkeypatch, ollama="KEPUTUSAN MENTERI")
    result = asyncio.run(service.transcribe_scanned_pdf(scanned_pdf))
    assert result == "KEPUTUSAN MENTERI\n\nKEPUTUSAN MENTERI"


def test_the_gemini_client_being_unavailable_does_not_stop_the_local_engine(
    monkeypatch,
    scanned_pdf,
):
    """The old async path gave up here without ever asking Ollama."""
    monkeypatch.setattr(
        PDFVisionService,
        "_available",
        property(lambda self: False),
        raising=False,
    )
    service = _service(monkeypatch, ollama="TEKS")
    assert asyncio.run(service.transcribe_scanned_pdf(scanned_pdf)) is not None


def test_the_async_parser_entry_point_delegates_to_the_real_engine(monkeypatch, scanned_pdf):
    from backend.core import parsers

    async def fake_transcribe(self, pdf_path, max_pages=None):
        return "TRANSCRIBED"

    monkeypatch.setattr(PDFVisionService, "transcribe_scanned_pdf", fake_transcribe)
    assert asyncio.run(parsers.extract_text_from_pdf_ocr_async(scanned_pdf)) == "TRANSCRIBED"


def test_the_sync_last_resort_reaches_the_vision_engine(monkeypatch, scanned_pdf):
    """extract_text_from_pdf must end at a rendered page, not at PyMuPDF again."""
    from backend.core import parsers

    async def fake_transcribe(self, pdf_path, max_pages=None):
        return "SCANNED CONTENT"

    monkeypatch.setattr(PDFVisionService, "transcribe_scanned_pdf", fake_transcribe)
    monkeypatch.setattr(parsers, "extract_text_from_pdf_ocr", lambda path: "")
    assert parsers.extract_text_from_pdf(scanned_pdf) == "SCANNED CONTENT"


# ---------------------------------------------------------------------------
# INNOCENCE
# ---------------------------------------------------------------------------


def test_total_failure_returns_none_rather_than_an_error_string(monkeypatch, scanned_pdf):
    """`analyze_page` reports failure by RETURNING a string; that string must
    never become the document's text."""
    service = _service(monkeypatch, ollama=None, gemini=None)
    assert asyncio.run(service.transcribe_scanned_pdf(scanned_pdf)) is None


def test_the_sovereignty_gate_still_governs_the_cloud_fallback(monkeypatch, scanned_pdf):
    """Ollama silent + cloud gate shut must degrade to None, never to a cloud call."""
    from backend.services.multimodal import cloud_vision_gate

    monkeypatch.setattr(cloud_vision_gate, "cloud_vision_allowed", lambda: False)
    service = PDFVisionService()

    async def silent_ollama(prompt, image_base64):
        return None

    monkeypatch.setattr(service, "_analyze_via_ollama", silent_ollama)
    assert asyncio.run(service.transcribe_scanned_pdf(scanned_pdf)) is None


def test_a_page_that_fails_does_not_lose_the_rest_of_the_document(monkeypatch, scanned_pdf):
    service = PDFVisionService()
    calls = {"n": 0}

    async def flaky(prompt, image_base64):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("render blew up")
        return "PAGE TWO"

    async def no_gemini(prompt, image_base64):
        return None

    monkeypatch.setattr(service, "_analyze_via_ollama", flaky)
    monkeypatch.setattr(service, "_analyze_via_gemini", no_gemini)
    assert asyncio.run(service.transcribe_scanned_pdf(scanned_pdf)) == "PAGE TWO"


def test_the_cloud_rate_limit_pause_never_runs_on_the_local_path(monkeypatch, scanned_pdf):
    """The old async loop slept 4s per page unconditionally -- 400s wasted on a
    100-page scan the local engine handled without any quota."""
    slept: list[float] = []

    async def recording_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(vision_module.asyncio, "sleep", recording_sleep)
    service = _service(monkeypatch, ollama="TEKS")
    asyncio.run(service.transcribe_scanned_pdf(scanned_pdf))
    assert slept == []


def test_max_pages_is_honoured(monkeypatch, scanned_pdf):
    service = _service(monkeypatch, ollama="X")
    assert asyncio.run(service.transcribe_scanned_pdf(scanned_pdf, max_pages=1)) == "X"


def test_an_unopenable_file_returns_none_not_an_exception(monkeypatch, tmp_path):
    broken = tmp_path / "not-a.pdf"
    broken.write_bytes(b"definitely not a pdf")
    assert asyncio.run(PDFVisionService().transcribe_scanned_pdf(str(broken))) is None
