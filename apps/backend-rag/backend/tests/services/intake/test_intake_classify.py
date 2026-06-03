"""Unit tests for FASE 3a intake preprocess + classify (strict-local OCR).

Fast + deterministic: the live Ollama vision call is monkeypatched so CI never
needs a GPU/model. Two empirically-grounded behaviours are locked:

  * anti-hallucination: undeterminable text -> unknown + 0.0 (never a guess);
  * 0-byte-to-cloud: classify.py / preprocess.py contain NO gemini / cloud path.

The live-model behaviour (qwen3-vl thinking-leak, qwen2.5vl fallback) is
exercised separately by the on-Pro E2E run, not here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.services.intake import classify as cls
from backend.services.intake import preprocess as pre


# ---------------------------------------------------------------------------
# classify_document -- pure text, no model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_text_is_unknown():
    r = await cls.classify_document("")
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0
    assert r["source_page"] is None


@pytest.mark.asyncio
async def test_whitespace_text_is_unknown():
    r = await cls.classify_document("   \n  \t ")
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
async def test_garbage_text_is_unknown_not_guessed():
    # Anti-hallucination: noise with no doc-evidence must NOT be classified.
    r = await cls.classify_document("xkcd 9981 lorem ipsum qwerty zzz 4471")
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
async def test_weak_single_keyword_below_floor_is_unknown():
    # "imigrasi" alone (weight 0.2) is below the 0.30 floor -> unknown.
    r = await cls.classify_document("kantor imigrasi kelas satu")
    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
async def test_npwp_classified():
    r = await cls.classify_document(
        "KEMENTERIAN KEUANGAN REPUBLIK INDONESIA DIREKTORAT JENDERAL PAJAK "
        "NOMOR POKOK WAJIB PAJAK NPWP 09.123.456.7-901.000"
    )
    assert r["type"] == "npwp"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_passport_classified_via_mrz():
    r = await cls.classify_document(
        "REPUBLIC OF INDONESIA PASSPORT PASPOR\nP<IDNSUKARNO<<KARNO<<<<<<<<<<<<<"
    )
    assert r["type"] == "passport"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_akta_classified():
    r = await cls.classify_document(
        "AKTA PENDIRIAN PERSEROAN TERBATAS PT MAJU JAYA NOMOR 17 "
        "DIHADAPAN NOTARIS ANGGARAN DASAR"
    )
    assert r["type"] == "akta_pendirian"
    assert r["confidence"] >= 0.30


@pytest.mark.asyncio
async def test_sk_kemenkumham_classified():
    r = await cls.classify_document(
        "KEPUTUSAN MENTERI HUKUM DAN HAK ASASI MANUSIA TENTANG PENGESAHAN "
        "BADAN HUKUM PERSEROAN AHU-0012345.AH.01.01"
    )
    assert r["type"] == "sk_kemenkumham"


@pytest.mark.asyncio
async def test_source_page_attribution():
    # Evidence lives on page 1 (index 1), not page 0.
    pages = [
        {"page": 0, "text": "halaman sampul tanpa isi"},
        {"page": 1, "text": "NOMOR INDUK BERUSAHA NIB lembaga oss perizinan berusaha"},
    ]
    r = await cls.classify_document(None, pages)
    assert r["type"] == "nib"
    assert r["source_page"] == 1


# ---------------------------------------------------------------------------
# ocr_pages -- monkeypatched vision call (deterministic)
# ---------------------------------------------------------------------------


class _FakePage:
    def __init__(self, index: int, data: bytes):
        self.index = index
        self.png_bytes = data
        self.enhanced = False


@pytest.mark.asyncio
async def test_ocr_pages_uses_primary_response(monkeypatch):
    async def fake_vision(model, b64):
        return ("NOMOR POKOK WAJIB PAJAK", "")  # response present

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "response"
    assert "WAJIB PAJAK" in out[0]["text"]
    assert out[0]["confidence"] > 0.0


@pytest.mark.asyncio
async def test_ocr_pages_salvages_thinking_when_response_empty(monkeypatch):
    async def fake_vision(model, b64):
        # qwen3-vl pattern: empty response, transcription buried in thinking.
        return ("", "Got it, let's transcribe the text: KARTU TANDA PENDUDUK NIK 3201")

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "thinking"
    assert "TANDA PENDUDUK" in out[0]["text"]


@pytest.mark.asyncio
async def test_ocr_pages_cascades_to_fallback(monkeypatch):
    calls = []

    async def fake_vision(model, b64):
        calls.append(model)
        if model == cls._OCR_PRIMARY_DEFAULT:
            return ("", "")  # primary yields nothing usable
        return ("KEMENTERIAN KEUANGAN", "")  # fallback succeeds

    monkeypatch.setattr(cls, "_resolve_ocr_model", lambda: cls._OCR_PRIMARY_DEFAULT)
    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["via"] == "fallback"
    assert out[0]["model"] == cls._OCR_FALLBACK
    assert calls == [cls._OCR_PRIMARY_DEFAULT, cls._OCR_FALLBACK]


@pytest.mark.asyncio
async def test_ocr_pages_unreadable_yields_empty_not_invented(monkeypatch):
    async def fake_vision(model, b64):
        return ("", "")  # both primary and fallback see nothing

    monkeypatch.setattr(cls, "_ollama_vision", fake_vision)
    out = await cls.ocr_pages([_FakePage(0, b"x")])
    assert out[0]["text"] == ""
    assert out[0]["confidence"] == 0.0
    assert out[0]["via"] == "empty"


# ---------------------------------------------------------------------------
# preprocess -- mime detection (no model)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preprocess_detects_png_and_returns_page(tmp_path):
    from PIL import Image

    p = tmp_path / "doc.png"
    Image.new("RGB", (200, 100), "white").save(p, format="PNG")
    r = await pre.preprocess_blob(str(p))
    assert r.mime == "image/png"
    assert r.n_pages == 1
    assert r.pages[0].png_bytes


@pytest.mark.asyncio
async def test_preprocess_missing_file_graceful():
    r = await pre.preprocess_blob("/nonexistent/path/blob.pdf")
    assert r.n_pages == 0
    assert r.notes and "read_failed" in r.notes


# ---------------------------------------------------------------------------
# 0-byte-to-cloud guard (STRICT-LOCAL)
# ---------------------------------------------------------------------------

_SOURCE_FILES = [
    Path(cls.__file__),
    Path(pre.__file__),
]
_CLOUD_TOKENS = re.compile(r"gemini|cross-border|openai|anthropic|googleapis", re.IGNORECASE)


def test_no_cloud_path_in_source():
    """classify.py / preprocess.py must contain NO cloud token at all.

    This is the literal `grep -i gemini` / `grep CROSS-BORDER` == empty check the
    intake spec runs: STRICT-LOCAL means the source carries zero cloud tokens,
    not even in comments. If a future edit reintroduces a cloud fallback, this
    fails before it can ship.
    """
    for f in _SOURCE_FILES:
        text = f.read_text()
        for lineno, line in enumerate(text.splitlines(), 1):
            m = _CLOUD_TOKENS.search(line)
            assert m is None, f"cloud token '{m.group(0)}' in {f.name}:{lineno}: {line.strip()}"
    # Also assert the literal upper-case marker the spec greps for.
    for f in _SOURCE_FILES:
        assert "CROSS-BORDER" not in f.read_text()
