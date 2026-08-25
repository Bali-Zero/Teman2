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


def _inked_scan(tmp_path, pages, name="inked.pdf"):
    """A scan whose pages carry INK but no text layer.

    The blank-page rule is measured on pixels, so a fixture of empty pages
    cannot exercise it: an empty page is legitimately blank and is skipped by
    design. Pages that must count as MISSING have to look written.
    """
    document = fitz.open()
    for inked in pages:
        page = document.new_page(width=200, height=200)
        if inked:
            page.draw_rect(fitz.Rect(20, 20, 180, 180), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / name
    document.save(str(path))
    document.close()
    assert sum(len(page.get_text()) for page in fitz.open(str(path))) == 0
    return str(path)


@pytest.fixture
def inked_scan(tmp_path):
    """Three pages that all look written."""
    return _inked_scan(tmp_path, [True, True, True])


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


def test_a_transient_page_failure_is_retried_and_the_document_survives_whole(
    monkeypatch,
    inked_scan,
):
    """REVERSED 2026-08-25.

    This test used to assert that a failed page simply drops out and the rest
    of the document is returned -- "most of a decree beats none of it". Its
    first live run disproved it: a real three-page decree came back as 1,204 of
    6,109 characters because pages 2 and 3 timed out against a cold vision
    model, and it was stored looking whole. The cure is not to salvage the
    survivors, it is to RETRY the page (which is what recovered it by hand) and
    to refuse the document if the page is still missing.
    """
    service = PDFVisionService()
    calls = {"n": 0}

    async def cold_then_warm(prompt, image_base64):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("vision model still loading")
        return "HALAMAN"

    async def no_gemini(prompt, image_base64):
        return None

    monkeypatch.setattr(service, "_analyze_via_ollama", cold_then_warm)
    monkeypatch.setattr(service, "_analyze_via_gemini", no_gemini)
    result = asyncio.run(service.transcribe_scanned_pdf(inked_scan))
    assert result == "HALAMAN\n\nHALAMAN\n\nHALAMAN"
    assert calls["n"] == 4  # one page cost two attempts, the other two cost one


# ---------------------------------------------------------------------------
# GUILT -- the completeness contract (added 2026-08-25)
# ---------------------------------------------------------------------------


def test_a_page_that_never_transcribes_refuses_the_whole_document(monkeypatch, inked_scan):
    """The defect this cures: 1,204 of 6,109 characters, stored as a decree."""
    service = PDFVisionService()
    seen: list[int] = []

    async def silent_on_the_second_page(prompt, image_base64):
        seen.append(1)
        # call 1 = page 1; calls 2 and 3 = page 2's two attempts, both silent;
        # call 4 = page 3.
        return None if len(seen) in (2, 3) else "ISI HALAMAN"

    async def no_gemini(prompt, image_base64):
        return None

    monkeypatch.setattr(service, "_analyze_via_ollama", silent_on_the_second_page)
    monkeypatch.setattr(service, "_analyze_via_gemini", no_gemini)

    with pytest.raises(vision_module.IncompleteTranscriptionError) as excinfo:
        asyncio.run(service.transcribe_scanned_pdf(inked_scan))

    error = excinfo.value
    assert error.missing_pages == [2]
    assert error.page_count == 3
    assert error.transcribed_chars > 0
    assert "2" in str(error)


def test_the_refusal_reaches_the_async_parser_as_a_parse_error(monkeypatch, inked_scan):
    """`extract_text_from_pdf_ocr_async` degrades to "" on every other failure.
    On THIS one it must not: "" would report nothing found while a partial
    document had in fact been read."""
    from backend.core import parsers
    from backend.core.parsers import DocumentParseError

    async def refuse(self, pdf_path, max_pages=None, **kwargs):
        raise vision_module.IncompleteTranscriptionError(pdf_path, [2], 3, 1204)

    monkeypatch.setattr(PDFVisionService, "transcribe_scanned_pdf", refuse)
    with pytest.raises(DocumentParseError) as excinfo:
        asyncio.run(parsers.extract_text_from_pdf_ocr_async(inked_scan))
    assert "Incomplete" in str(excinfo.value)
    assert "[2]" in str(excinfo.value)


def test_the_sync_last_resort_names_the_missing_pages_not_no_text(monkeypatch, inked_scan):
    from backend.core import parsers
    from backend.core.parsers import DocumentParseError

    async def refuse(self, pdf_path, max_pages=None, **kwargs):
        raise vision_module.IncompleteTranscriptionError(pdf_path, [2, 3], 3, 1204)

    monkeypatch.setattr(PDFVisionService, "transcribe_scanned_pdf", refuse)
    monkeypatch.setattr(parsers, "extract_text_from_pdf_ocr", lambda path: "")
    with pytest.raises(DocumentParseError) as excinfo:
        parsers.extract_text_from_pdf(inked_scan)
    message = str(excinfo.value)
    assert "Incomplete" in message
    assert "No text extracted" not in message


# ---------------------------------------------------------------------------
# INNOCENCE -- the contract must not refuse honest documents
# ---------------------------------------------------------------------------


def test_a_genuinely_blank_page_does_not_refuse_the_document(monkeypatch, tmp_path):
    """The empty verso of a two-sided scan is silent because it is empty."""
    path = _inked_scan(tmp_path, [True, False], name="one-blank.pdf")
    service = PDFVisionService()
    answers = iter(["ISI"])

    async def only_the_inked_page_answers(prompt, image_base64):
        return next(answers, None)

    async def no_gemini(prompt, image_base64):
        return None

    monkeypatch.setattr(service, "_analyze_via_ollama", only_the_inked_page_answers)
    monkeypatch.setattr(service, "_analyze_via_gemini", no_gemini)
    assert asyncio.run(service.transcribe_scanned_pdf(path)) == "ISI"


def test_a_page_bearing_ink_that_stays_silent_is_never_called_blank(monkeypatch, tmp_path):
    """The guilty twin of the test above: same shape, inked second page."""
    path = _inked_scan(tmp_path, [True, True], name="both-inked.pdf")
    service = PDFVisionService()
    answers = iter(["ISI"])

    async def only_the_first_page_answers(prompt, image_base64):
        return next(answers, None)

    async def no_gemini(prompt, image_base64):
        return None

    monkeypatch.setattr(service, "_analyze_via_ollama", only_the_first_page_answers)
    monkeypatch.setattr(service, "_analyze_via_gemini", no_gemini)
    with pytest.raises(vision_module.IncompleteTranscriptionError):
        asyncio.run(service.transcribe_scanned_pdf(path))


def test_allow_partial_returns_the_survivors_for_a_caller_that_asked(monkeypatch, tmp_path):
    path = _inked_scan(tmp_path, [True, True], name="partial-ok.pdf")
    service = PDFVisionService()
    answers = iter(["ISI"])

    async def only_the_first_page_answers(prompt, image_base64):
        return next(answers, None)

    async def no_gemini(prompt, image_base64):
        return None

    monkeypatch.setattr(service, "_analyze_via_ollama", only_the_first_page_answers)
    monkeypatch.setattr(service, "_analyze_via_gemini", no_gemini)
    result = asyncio.run(service.transcribe_scanned_pdf(path, allow_partial=True))
    assert result == "ISI"


def test_a_page_that_cannot_even_be_rendered_counts_as_missing(monkeypatch, tmp_path):
    """An unmeasurable page must not be given the benefit of the doubt."""
    path = _inked_scan(tmp_path, [True, True], name="unrenderable.pdf")
    service = PDFVisionService()
    real_render = service._render_page_to_image

    def render_page_two_blows_up(pdf_path, page_number):
        if page_number == 2:
            raise OSError("pixmap allocation failed")
        return real_render(pdf_path, page_number)

    async def answer(prompt, image_base64):
        return "ISI"

    async def no_gemini(prompt, image_base64):
        return None

    monkeypatch.setattr(service, "_render_page_to_image", render_page_two_blows_up)
    monkeypatch.setattr(service, "_analyze_via_ollama", answer)
    monkeypatch.setattr(service, "_analyze_via_gemini", no_gemini)
    with pytest.raises(vision_module.IncompleteTranscriptionError) as excinfo:
        asyncio.run(service.transcribe_scanned_pdf(path))
    assert excinfo.value.missing_pages == [2]


def test_a_whole_document_costs_exactly_one_attempt_per_page(monkeypatch, inked_scan):
    """The retry must not double every call on the happy path."""
    service = PDFVisionService()
    calls = {"n": 0}

    async def always_answers(prompt, image_base64):
        calls["n"] += 1
        return "ISI"

    async def no_gemini(prompt, image_base64):
        return None

    monkeypatch.setattr(service, "_analyze_via_ollama", always_answers)
    monkeypatch.setattr(service, "_analyze_via_gemini", no_gemini)
    assert asyncio.run(service.transcribe_scanned_pdf(inked_scan)) is not None
    assert calls["n"] == 3


def test_the_ink_measurement_separates_a_written_line_from_an_empty_page(tmp_path):
    """Measured 2026-08-25: one short line on A4 = 0.049% ink, a bare page
    number = 0.003%, an empty page = 0.000%, a real scanned decree 4.7-8.4%."""
    document = fitz.open()
    document.new_page(width=595, height=842)  # page 1: empty
    written = document.new_page(width=595, height=842)
    written.insert_text((72, 400), "Pasal 5 dihapus.", fontsize=11)
    path = tmp_path / "ink.pdf"
    document.save(str(path))
    document.close()

    service = PDFVisionService()
    empty_ratio = service._page_ink_ratio(service._render_page_to_image(str(path), 1))
    written_ratio = service._page_ink_ratio(service._render_page_to_image(str(path), 2))

    assert empty_ratio < vision_module.BLANK_PAGE_INK_RATIO
    assert written_ratio > vision_module.BLANK_PAGE_INK_RATIO


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
