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
