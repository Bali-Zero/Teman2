from collections import Counter

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.services.visa_oracle_testing import (
    ResultPayload,
    StartPayload,
    authorize_record,
    make_assignments,
    scenario,
    validate_submission,
)


def test_campaign_has_five_per_day_and_shared_reference():
    cases = make_assignments()
    assert len(cases) == len({c["id"] for c in cases}) == 90
    assert {c["day"] for c in cases} == {"2026-10-05", "2026-10-06", "2026-10-07"}
    assert set(Counter((c["slot"], c["day"]) for c in cases).values()) == {5}
    assert set(Counter(c["slot"] for c in cases).values()) == {15}
    for day in {c["day"] for c in cases}:
        shared = [c["scenario"] for c in cases if c["day"] == day and c["index"] == 0]
        assert len(shared) == 6 and all(s == shared[0] for s in shared)
        assert all(
            c["scenario"]["inputs"] != shared[0]["inputs"]
            for c in cases
            if c["day"] == day and c["index"]
        )
    assert len({str(c["scenario"]["inputs"]) for c in cases if c["index"]}) > 60
    for day in {c["day"] for c in cases}:
        contrast = [c for c in cases if c["day"] == day and c["index"]]
        assert len({str(c["scenario"]["inputs"]) for c in contrast}) == 24


def test_cross_tester_writes_are_rejected_and_self_review_is_allowed():
    # Guilt: writing another tester's record is rejected, for both plain writes
    # and review (owner decision 2026-09-30: cross-member review is not wanted).
    with pytest.raises(HTTPException) as e:
        authorize_record("member-a", "member-b")
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        authorize_record("member-a", "member-b", review=True)
    assert e.value.status_code == 403
    # Innocence: a tester may write and review their OWN record (self-review).
    authorize_record("member-a", "member-a")
    authorize_record("member-a", "member-a", review=True)
    # The site admin's override bypasses ownership entirely, for auditing.
    authorize_record("member-a", "member-b", review=True, override=True)


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


def test_evidence_pixels_survive_but_private_image_metadata_does_not():
    import base64
    import io

    from PIL import Image, PngImagePlugin

    image = Image.new("RGB", (20, 10), (23, 45, 67))
    exif = Image.Exif()
    exif[270] = "synthetic-private-device-metadata"
    jpeg = io.BytesIO()
    image.save(jpeg, format="JPEG", exif=exif)
    png = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Comment", "synthetic-private-device-metadata")
    image.save(png, format="PNG", pnginfo=metadata)
    for raw in (jpeg.getvalue(), png.getvalue()):
        payload = ResultPayload(
            synthetic_only=True, screenshot_base64=base64.b64encode(raw).decode()
        )
        clean = base64.b64decode(payload.screenshot_base64)
        assert b"synthetic-private-device-metadata" not in clean
        with Image.open(io.BytesIO(clean)) as decoded:
            assert decoded.size == (20, 10)
            assert not decoded.getexif()
            assert "Comment" not in decoded.info
        retry = ResultPayload(synthetic_only=True, screenshot_base64=payload.screenshot_base64)
        assert retry.screenshot_base64 == payload.screenshot_base64


def test_purpose_fixtures_only_include_relevant_sponsor_context():
    # The purpose day (index 3) is outside the rescheduled three-day campaign; its
    # fixtures are still generated by scenario(), so they stay under test.
    investment = scenario(3, 2, 4)
    assert "Kontras sengaja" in investment["focus"]
    assert investment["inputs"]["investment_pt_pma"] == "no"
    assert investment["inputs"]["investment_capital_idr"] == "0"
    for tester in range(6):
        for variant in range(4):
            profile = scenario(3, variant, tester)["inputs"]
            if profile["category"] not in {"family", "retirement"}:
                assert "family_sponsor_confirmed" not in profile
