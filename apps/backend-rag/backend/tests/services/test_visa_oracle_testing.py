from collections import Counter

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.services.visa_oracle_testing import (
    ResultPayload,
    StartPayload,
    authorize_record,
    make_assignments,
    validate_submission,
)


def test_campaign_has_five_per_day_and_shared_reference():
    cases = make_assignments()
    assert len(cases) == len({c["id"] for c in cases}) == 150
    assert set(Counter((c["slot"], c["day"]) for c in cases).values()) == {5}
    assert set(Counter(c["slot"] for c in cases).values()) == {25}
    for day in {c["day"] for c in cases}:
        shared = [c["scenario"] for c in cases if c["day"] == day and c["index"] == 0]
        assert len(shared) == 6 and all(s == shared[0] for s in shared)
        assert all(
            c["scenario"]["inputs"] != shared[0]["inputs"]
            for c in cases
            if c["day"] == day and c["index"]
        )
    assert len({str(c["scenario"]["inputs"]) for c in cases if c["index"]}) > 80
    for day in {c["day"] for c in cases}:
        contrast = [c for c in cases if c["day"] == day and c["index"]]
        assert len({str(c["scenario"]["inputs"]) for c in contrast}) == 24


def test_cross_tester_write_and_self_review_are_rejected():
    with pytest.raises(HTTPException) as e:
        authorize_record("member-a", "member-b")
    assert e.value.status_code == 403
    with pytest.raises(HTTPException):
        authorize_record("member-a", "member-a", review=True)
    authorize_record("member-a", "member-a")


def test_attestation_and_unknown_fields_fail_closed():
    fields = {
        "text": "Expected direction needs expert review",
        "basis": "needs_review",
        "browser": "Firefox",
        "device": "desktop",
        "displayed_version": "unknown",
        "synthetic_only": True,
    }
    StartPayload(**fields)
    with pytest.raises(ValidationError):
        StartPayload(**{**fields, "synthetic_only": False})
    with pytest.raises(ValidationError):
        StartPayload(**{**fields, "actor_id": "other"})


def test_draft_is_not_submission_and_missing_evidence_is_not_validated():
    draft = ResultPayload(synthetic_only=True)
    with pytest.raises(HTTPException):
        validate_submission(draft)
    complete = ResultPayload(
        steps="Entered fixture exactly; recorded all inputs",
        actual_state="blocked",
        actual="Next control stays disabled after valid selection",
        comment="Check validation at next button",
        category="navigation",
        severity="medium",
        certainty="observation",
        reproducibility="same",
        source_notes="No sources shown",
        uncertainty="Not reached",
        evidence_ref="synthetic-capture.png",
        synthetic_only=True,
    )
    validate_submission(complete)


def test_active_content_and_oversized_screenshots_are_rejected():
    with pytest.raises(ValidationError):
        ResultPayload(synthetic_only=True, screenshot_base64="PHN2Zz48L3N2Zz4=")
    with pytest.raises(ValidationError):
        ResultPayload(synthetic_only=True, screenshot_base64="A" * 900000)


def test_reproduction_is_a_confirmed_issue_not_an_expert_review_placeholder():
    from backend.services.visa_oracle_testing import ReviewPayload

    with pytest.raises(ValidationError):
        ReviewPayload(
            verdict="not_issue",
            comment="Works as designed",
            reproduced=True,
            reproduction_evidence="Repeated the same fixture twice",
        )
