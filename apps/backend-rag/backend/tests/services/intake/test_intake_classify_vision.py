"""Unit tests for the vision classify fallback (catalog v2).

The Ollama vision helper is monkeypatched — no GPU/model needed. Locked
behaviours:

  * the fallback fires ONLY when the keyword score is below the 0.30 floor
    AND a first-page image is available;
  * only an EXACT DOC_TYPES member (case-insensitive, single token) is
    accepted — a sentence or an off-list word degrades to unknown;
  * confidence is CAPPED at VISION_CLASSIFY_CONF (review band — a vision-only
    type can never auto-commit);
  * any error/timeout degrades to unknown — the fallback NEVER raises.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.intake import classify as cls

# Below-floor text: "imigrasi" alone scores 0.2 (< 0.30) for kitas.
_WEAK_TEXT = "kantor imigrasi kelas satu"
# Strong text: classifies as npwp on keywords alone.
_STRONG_TEXT = (
    "KEMENTERIAN KEUANGAN REPUBLIK INDONESIA DIREKTORAT JENDERAL PAJAK "
    "NOMOR POKOK WAJIB PAJAK NPWP 09.123.456.7-901.000"
)


def _fake_vision(answer: str, calls: list[dict[str, Any]]):
    async def fake(
        model: str,
        png_b64: str,
        prompt: str = "",
        num_predict: int = 0,
    ) -> tuple[str, str | None]:
        calls.append({"model": model, "prompt": prompt, "num_predict": num_predict})
        return answer, ""

    return fake


# ---------------------------------------------------------------------------
# _parse_vision_answer — exact-member contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("kitas", "kitas"),
        ("KITAS", "kitas"),
        (" passport.\n", "passport"),
        ("akta_pendirian", "akta_pendirian"),
        ("unknown", "unknown"),
        ("this is a passport", None),  # sentence -> rejected
        ("visa", "visa"),
        ("family_card", "family_card"),
        ("birth_certificate", "birth_certificate"),
        ("marriage_certificate", "marriage_certificate"),
        ("receipt", None),  # off-list word -> rejected
        ("", None),
        (None, None),
    ],
)
def test_parse_vision_answer(raw: str | None, expected: str | None) -> None:
    assert cls._parse_vision_answer(raw) == expected


# ---------------------------------------------------------------------------
# classify_document gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vision_fires_below_floor_and_caps_confidence(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(cls, "_ollama_vision", _fake_vision("kitas", calls))

    r = await cls.classify_document(_WEAK_TEXT, first_page_png=b"\x89PNG-fake")

    assert r["type"] == "kitas"
    assert r["confidence"] == cls.VISION_CLASSIFY_CONF  # capped, review band
    assert r["via"] == "vision_fallback"
    assert len(calls) == 1  # exactly ONE vision call
    assert "EXACTLY ONE word" in calls[0]["prompt"]


@pytest.mark.asyncio
async def test_vision_not_called_when_keywords_classify(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(cls, "_ollama_vision", _fake_vision("kitas", calls))

    r = await cls.classify_document(_STRONG_TEXT, first_page_png=b"\x89PNG-fake")

    assert r["type"] == "npwp"
    assert "via" not in r
    assert calls == []  # gate: never fires above the floor


@pytest.mark.asyncio
async def test_vision_not_called_without_image(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(cls, "_ollama_vision", _fake_vision("kitas", calls))

    r = await cls.classify_document(_WEAK_TEXT)

    assert r["type"] == "unknown"
    assert calls == []


@pytest.mark.asyncio
async def test_vision_off_list_answer_stays_unknown(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        cls, "_ollama_vision", _fake_vision("this looks like a passport", calls)
    )

    r = await cls.classify_document(_WEAK_TEXT, first_page_png=b"\x89PNG-fake")

    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_vision_unknown_answer_stays_unknown(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(cls, "_ollama_vision", _fake_vision("unknown", calls))

    r = await cls.classify_document(_WEAK_TEXT, first_page_png=b"\x89PNG-fake")

    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
async def test_vision_error_degrades_to_unknown_never_raises(monkeypatch):
    async def boom(*args: Any, **kwargs: Any) -> tuple[str, str | None]:
        raise RuntimeError("ollama down")

    monkeypatch.setattr(cls, "_ollama_vision", boom)

    r = await cls.classify_document(_WEAK_TEXT, first_page_png=b"\x89PNG-fake")

    assert r["type"] == "unknown"
    assert r["confidence"] == 0.0


@pytest.mark.asyncio
async def test_vision_salvages_thinking_only_model(monkeypatch):
    # Defensive: a reasoning VLM that answers in `thinking` with an exact token.
    async def thinking_only(
        model: str, png_b64: str, prompt: str = "", num_predict: int = 0
    ) -> tuple[str, str | None]:
        return "", "npwp"

    monkeypatch.setattr(cls, "_ollama_vision", thinking_only)

    r = await cls.classify_document(_WEAK_TEXT, first_page_png=b"\x89PNG-fake")

    assert r["type"] == "npwp"
    assert r["confidence"] == cls.VISION_CLASSIFY_CONF


# ---------------------------------------------------------------------------
# keyword enrichment (catalog v2) — new high-value phrases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generic_mrz_lead_in_scores_passport():
    # A non-Indonesian passport: no "p<idn", but the TD3 MRZ "P<" is present.
    r = await cls.classify_document("P<DEUMUSTERMANN<<ERIKA<<<<<<<<<<<<<<<")
    assert r["scores"].get("passport", 0.0) >= 0.35


@pytest.mark.asyncio
async def test_english_kitas_title_classifies():
    # An English-title "LIMITED STAY PERMIT CARD" is a KITAS = an *itas* card.
    # Since the 2026-06-17 stay-permit override, the classifier emits the
    # SPECIFIC subtype (itas) rather than the generic "kitas" — the override
    # fires on the "stay permit" / "limited stay" markers and never on passport.
    r = await cls.classify_document("LIMITED STAY PERMIT CARD REPUBLIC OF INDONESIA")
    assert r["type"] == "itas"
    assert r["type"] != "passport"
    assert r["via"] == "stay_permit_override"
    assert r["confidence"] >= 0.30
