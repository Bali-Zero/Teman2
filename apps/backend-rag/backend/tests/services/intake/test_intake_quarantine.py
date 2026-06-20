"""LEVA 1 — noise pre-filter → quarantine: pure-function verdict tests.

The noise verdict (``is_noise_proposal`` / ``_ocr_char_count``) is a pure
function of the classify-stage output — no DB, no re-OCR — so it is tested here
without a live Postgres. Per the cicatrix #3 antidote, a classifying guard is
NOT merged without BOTH an *innocence* test (it must NOT fire on a legitimate
neighbour — a real document) AND a *guilt* test (it MUST fire on the genuine
noise it exists to catch). The 2026-06-12 backlog poisoning (782 empty-OCR
``unknown`` rows) is the guilt case this lever targets.
"""

from __future__ import annotations

from backend.services.intake.routing import (
    QUARANTINE_MIN_OCR_CHARS,
    _ocr_char_count,
    is_noise_proposal,
    quarantine_enabled,
)


def _classify(doc_type_pages_text):
    """Build a classify stage_output dict from a list of per-page text strings."""
    pages, texts = doc_type_pages_text
    return {
        "ocr_text_per_page": [{"text": t, "confidence": 0.0 if not t.strip() else 0.7} for t in texts],
        "n_pages": len(texts),
    }


# --------------------------------------------------------------------------- #
# GUILT — the noise this lever exists to park
# --------------------------------------------------------------------------- #
def test_guilt_unknown_empty_ocr_is_noise():
    """unknown type + zero legible OCR (the 2026-06-12 empty-OCR class) → noise."""
    classify_out = {"ocr_text_per_page": [{"text": "", "confidence": 0.0}], "n_pages": 1}
    assert is_noise_proposal("unknown", classify_out) is True


def test_guilt_unknown_whitespace_only_is_noise():
    """unknown type + whitespace-only transcript → noise (stripped len 0)."""
    classify_out = {"ocr_text_per_page": [{"text": "   \n  \t "}], "n_pages": 1}
    assert is_noise_proposal("unknown", classify_out) is True


def test_guilt_unknown_below_char_floor_is_noise():
    """unknown type + a few illegible chars under the floor → noise."""
    short = "x" * (QUARANTINE_MIN_OCR_CHARS - 1)
    classify_out = {"ocr_text_per_page": [{"text": short}], "n_pages": 1}
    assert is_noise_proposal("unknown", classify_out) is True


def test_guilt_unknown_no_pages_is_noise():
    """unknown type + no OCR pages at all (blob_path_missing) → noise."""
    assert is_noise_proposal("unknown", {"ocr_text_per_page": [], "n_pages": 0}) is True


# --------------------------------------------------------------------------- #
# INNOCENCE — legitimate neighbours that must STAY in human review
# --------------------------------------------------------------------------- #
def test_innocence_typed_document_never_noise():
    """A classified document (passport) is NEVER noise, even with little text."""
    classify_out = {"ocr_text_per_page": [{"text": "P<IDN"}], "n_pages": 1}
    assert is_noise_proposal("passport", classify_out) is False


def test_innocence_unknown_but_legible_stays_in_review():
    """unknown type but a real legible transcript → NOT noise (mis-typed doc)."""
    legible = "Surat keterangan domisili nomor 123/IV/2026 atas nama ..."
    assert len(legible) >= QUARANTINE_MIN_OCR_CHARS
    classify_out = {"ocr_text_per_page": [{"text": legible}], "n_pages": 1}
    assert is_noise_proposal("unknown", classify_out) is False


def test_innocence_unknown_text_spread_across_pages():
    """Per-page text below floor each, but summed over floor → legible, not noise."""
    half = "y" * (QUARANTINE_MIN_OCR_CHARS - 5)
    classify_out = {"ocr_text_per_page": [{"text": half}, {"text": half}], "n_pages": 2}
    assert _ocr_char_count(classify_out) >= QUARANTINE_MIN_OCR_CHARS
    assert is_noise_proposal("unknown", classify_out) is False


def test_innocence_typed_with_empty_ocr_still_not_noise():
    """A vision-classified doc with empty keyword-OCR is typed → not noise."""
    classify_out = {"ocr_text_per_page": [{"text": ""}], "n_pages": 1}
    assert is_noise_proposal("nib", classify_out) is False


# --------------------------------------------------------------------------- #
# char-count helper robustness (defensive against malformed stage_output)
# --------------------------------------------------------------------------- #
def test_char_count_tolerates_malformed_pages():
    classify_out = {
        "ocr_text_per_page": [
            {"text": "abc"},
            {"no_text_key": True},
            {"text": None},
            "not-a-dict",
            {"text": 12345},  # non-str
        ],
        "n_pages": 5,
    }
    # Only "abc" (3) is a valid legible string.
    assert _ocr_char_count(classify_out) == 3


def test_char_count_missing_key_is_zero():
    assert _ocr_char_count({}) == 0
    assert _ocr_char_count({"ocr_text_per_page": None}) == 0


# --------------------------------------------------------------------------- #
# kill-switch — default OFF
# --------------------------------------------------------------------------- #
def test_quarantine_disabled_by_default(monkeypatch):
    monkeypatch.delenv("INTAKE_QUARANTINE_ENABLED", raising=False)
    assert quarantine_enabled() is False


def test_quarantine_enabled_when_truthy(monkeypatch):
    for val in ("1", "true", "yes", "on", "ON", "True"):
        monkeypatch.setenv("INTAKE_QUARANTINE_ENABLED", val)
        assert quarantine_enabled() is True


def test_quarantine_disabled_when_falsy(monkeypatch):
    for val in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("INTAKE_QUARANTINE_ENABLED", val)
        assert quarantine_enabled() is False
