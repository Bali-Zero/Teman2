"""Unit tests for the text-layer fast-path (INTAKE_TEXTLAYER_FASTPATH).

Born-digital PDF pages carry a selectable text layer that preprocess.py
extracts into ``PageImage.text``. When present, ``classify.ocr_pages`` must use
that text VERBATIM and SKIP the local vision model entirely (the ~120s/page
cost). Scanned pages (text=None) still go through vision unchanged. The vision
helper is monkeypatched -- no GPU/model needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.intake import classify as cls
from backend.services.intake.preprocess import PageImage


def _counting_vision(calls: list[dict[str, Any]], answer: str = "scanned text"):
    async def fake(
        model: str,
        png_b64: str,
        prompt: str = "",
        num_predict: int = 0,
    ) -> tuple[str, str | None]:
        calls.append({"model": model})
        return answer, ""

    return fake


# Synthetic, non-PII born-digital text (>100 non-whitespace chars).
_DIGITAL_TEXT = (
    "KEMENTERIAN INVESTASI BKPM NOMOR INDUK BERUSAHA NIB 1234567890123 "
    "LEMBAGA OSS PERIZINAN BERUSAHA BERBASIS RISIKO PT CONTOH SEJAHTERA ABADI"
)


def test_pageimage_text_defaults_none() -> None:
    # Additive field: old call-sites (3 positional args) keep working.
    p = PageImage(index=0, png_bytes=b"\x89PNG", enhanced=False)
    assert p.text is None


@pytest.mark.asyncio
async def test_textlayer_page_skips_vision(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(cls, "_ollama_vision", _counting_vision(calls))

    page = PageImage(index=0, png_bytes=b"", enhanced=False, text=_DIGITAL_TEXT)
    out = await cls.ocr_pages([page])

    assert calls == []  # vision NEVER called for a text-layer page
    assert out[0]["via"] == "textlayer"
    assert out[0]["model"] == "textlayer"
    assert out[0]["text"] == _DIGITAL_TEXT
    assert out[0]["confidence"] > 0.0


@pytest.mark.asyncio
async def test_scanned_page_still_calls_vision(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(cls, "_ollama_vision", _counting_vision(calls, "OCR result"))

    page = PageImage(index=0, png_bytes=b"\x89PNGfake", enhanced=False, text=None)
    out = await cls.ocr_pages([page])

    assert len(calls) >= 1  # vision IS called when there is no text layer
    assert out[0]["via"] == "response"
    assert out[0]["text"] == "OCR result"


@pytest.mark.asyncio
async def test_blank_textlayer_falls_through_to_vision(monkeypatch) -> None:
    # A page whose text is empty/whitespace must NOT short-circuit -- vision runs.
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(cls, "_ollama_vision", _counting_vision(calls, "OCR result"))

    page = PageImage(index=0, png_bytes=b"\x89PNGfake", enhanced=False, text="   ")
    out = await cls.ocr_pages([page])

    assert len(calls) >= 1
    assert out[0]["via"] == "response"
