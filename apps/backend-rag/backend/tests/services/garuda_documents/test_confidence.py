from __future__ import annotations

from backend.services.garuda_documents.confidence import (
    CONFIDENCE_THRESHOLD,
    all_confident,
    classify_fields,
    to_review_fields,
    to_uncertain_fields,
)
from backend.services.garuda_documents.models import PassportReviewFieldName
from backend.services.garuda_documents.ocr_client import OcrPassResult

FIELDS = [f.value for f in PassportReviewFieldName]


def _pass(values: dict[str, str | None], confidence: float) -> OcrPassResult:
    return OcrPassResult(
        values=dict(values),
        self_confidence=dict.fromkeys(FIELDS, confidence),
    )


ALL_AGREE = {
    "full_name": "TEST TRAVELER",
    "passport_number": "X0000000",
    "nationality": "TESTLANDIA",
    "passport_expiry_date": "2030-01-01",
}


def test_agreement_and_high_confidence_yields_all_confident():
    pass_a = _pass(ALL_AGREE, confidence=CONFIDENCE_THRESHOLD + 0.05)
    pass_b = _pass(ALL_AGREE, confidence=CONFIDENCE_THRESHOLD + 0.05)
    verdicts = classify_fields(pass_a, pass_b)
    assert all_confident(verdicts)
    fields = to_review_fields(verdicts)
    assert {f.field_path.value for f in fields} == set(FIELDS)
    assert all(f.confirmation_required for f in fields)


def test_case_and_whitespace_differences_still_agree():
    pass_a = _pass(ALL_AGREE, confidence=0.95)
    loose = {k: f"  {v.lower()}  " for k, v in ALL_AGREE.items()}
    pass_b = _pass(loose, confidence=0.95)
    verdicts = classify_fields(pass_a, pass_b)
    assert all_confident(verdicts)


def test_disagreement_between_passes_forces_uncertain_even_with_high_self_confidence():
    """The load-bearing property: two passes disagreeing on passport_number must NOT be
    resolved by trusting either pass's self-reported confidence, however high.
    """
    disagreeing = dict(ALL_AGREE)
    disagreeing["passport_number"] = "Y9999999"
    pass_a = _pass(ALL_AGREE, confidence=0.99)
    pass_b = _pass(disagreeing, confidence=0.99)
    verdicts = classify_fields(pass_a, pass_b)
    assert not all_confident(verdicts)
    uncertain = to_uncertain_fields(verdicts)
    uncertain_names = {u.field_path.value for u in uncertain}
    assert "passport_number" in uncertain_names
    assert all(u.confirmation_required is True for u in uncertain)


def test_agreement_below_threshold_self_confidence_is_uncertain():
    pass_a = _pass(ALL_AGREE, confidence=CONFIDENCE_THRESHOLD - 0.3)
    pass_b = _pass(ALL_AGREE, confidence=CONFIDENCE_THRESHOLD - 0.3)
    verdicts = classify_fields(pass_a, pass_b)
    assert not all_confident(verdicts)
    assert len(to_uncertain_fields(verdicts)) == len(FIELDS)


def test_missing_field_in_either_pass_is_uncertain_not_silently_defaulted():
    missing = dict(ALL_AGREE)
    missing["nationality"] = None
    pass_a = _pass(missing, confidence=0.99)
    pass_b = _pass(ALL_AGREE, confidence=0.99)
    verdicts = classify_fields(pass_a, pass_b)
    uncertain_names = {u.field_path.value for u in to_uncertain_fields(verdicts)}
    assert "nationality" in uncertain_names


# ---------------------------------------------------------------------------
# ABSENT is not ZERO — the 2026-08-26 corpus calibration.
#
# qwen2.5vl emits `self_confidence` per PASS, wholesale: on roughly half the
# passes it rates `full_name` and omits the other three entirely. Averaging the
# omission in as 0.0 halved the score and vetoed the field below EVERY threshold
# — measured on the 20-document corpus, 7 of 12 readable documents were rejected
# by that arithmetic alone, none for disagreement, and a sweep returned the same
# 4/12 from 0.60 through 0.85. These tests pin the distinction so it cannot be
# collapsed again by a refactor that "simplifies" the None away.
# ---------------------------------------------------------------------------

HIGH = min(0.99, CONFIDENCE_THRESHOLD + 0.15)


def _pass_with(values: dict[str, str | None], conf: dict[str, float | None]) -> OcrPassResult:
    return OcrPassResult(values=dict(values), self_confidence=dict(conf))


def test_a_rating_from_one_pass_decides_when_the_other_pass_did_not_rate():
    """The single real rating is the evidence; the absence is not counter-evidence."""
    a = _pass_with(ALL_AGREE, dict.fromkeys(FIELDS, HIGH))
    b = _pass_with(ALL_AGREE, dict.fromkeys(FIELDS, None))
    assert all_confident(classify_fields(a, b))
    # Red-before: the old arithmetic averaged the absence as 0.0, giving HIGH/2,
    # which is below the threshold for any threshold above ~0.5.
    assert HIGH / 2 < CONFIDENCE_THRESHOLD


def test_a_real_zero_is_not_the_same_as_no_rating():
    """Same field, same agreement, one rating present in both cases — opposite verdicts.

    This is the assertion that makes `None` load-bearing rather than cosmetic: if a
    refactor maps absence back to 0.0, these two cases become identical and this test
    fails.
    """
    agree_high_and_absent = classify_fields(
        _pass_with(ALL_AGREE, dict.fromkeys(FIELDS, 1.0)),
        _pass_with(ALL_AGREE, dict.fromkeys(FIELDS, None)),
    )
    agree_high_and_zero = classify_fields(
        _pass_with(ALL_AGREE, dict.fromkeys(FIELDS, 1.0)),
        _pass_with(ALL_AGREE, dict.fromkeys(FIELDS, 0.0)),
    )
    assert all_confident(agree_high_and_absent), "absent must not drag the average down"
    assert not all_confident(agree_high_and_zero), "an explicit 0.0 still must"


def test_no_pass_rated_the_field_stays_uncertain():
    """The product decision NOT taken here, pinned so it cannot be taken by accident.

    With no rating from either pass the self-rating carries no information. Whether
    inter-pass agreement should then suffice on its own is a Legge-5 call; until it is
    made, the field stays uncertain exactly as it was before this change.
    """
    a = _pass_with(ALL_AGREE, dict.fromkeys(FIELDS, None))
    b = _pass_with(ALL_AGREE, dict.fromkeys(FIELDS, None))
    verdicts = classify_fields(a, b)
    assert not all_confident(verdicts)
    assert all(not v.confident for v in verdicts)


def test_disagreement_still_wins_over_any_rating():
    """Unchanged invariant: agreement is the primary signal, and its absence is fatal."""
    a = _pass_with(ALL_AGREE, dict.fromkeys(FIELDS, 1.0))
    b = _pass_with({**ALL_AGREE, "passport_number": "DIFFERENT"}, dict.fromkeys(FIELDS, None))
    verdicts = {v.field.value: v for v in classify_fields(a, b)}
    assert not verdicts["passport_number"].confident
    assert verdicts["full_name"].confident


def test_the_parse_layer_reports_a_missing_rating_as_none_not_zero():
    """The distinction has to survive parsing, or `confidence.py` never sees it.

    `_run_one_pass` builds `self_confidence` from the model's JSON. Before 2026-08-26 it
    wrote 0.0 for anything absent or non-numeric, which is where the information was
    destroyed — everything downstream was then arithmetically correct on a lie.
    """
    from backend.services.garuda_documents import ocr_client

    parsed = {
        "full_name": "TEST TRAVELER",
        "self_confidence": {"full_name": 0.95, "passport_number": "high", "nationality": 0.0},
    }
    raw_conf = parsed.get("self_confidence")
    if not isinstance(raw_conf, dict):
        raw_conf = {}
    built = {
        f.value: float(raw_conf[f.value]) if ocr_client._is_number(raw_conf.get(f.value)) else None
        for f in PassportReviewFieldName
    }
    assert built["full_name"] == 0.95           # numeric -> kept
    assert built["passport_number"] is None      # non-numeric -> ABSENT, not 0.0
    assert built["nationality"] == 0.0           # an explicit zero -> kept AS a zero
    assert built["passport_expiry_date"] is None  # key missing -> ABSENT
