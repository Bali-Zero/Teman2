"""Contract tests for the stateless GARUDA internal preview CLI."""

from __future__ import annotations

import io
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.services.garuda_flow.internal_preview_cli import (
    MAX_REQUEST_BYTES,
    InternalPreviewRequest,
    InternalPreviewResponse,
    build_internal_preview,
    run_cli,
)

_NOW = datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc)
_TODAY = _NOW.date()


def _request(**overrides: object) -> InternalPreviewRequest:
    payload: dict[str, object] = {
        "case_type": "issuance",
        "nationality": "usa",
        "entry_date": "2026-08-24",
        "passport_expiry_date": "2027-08-24",
        "purpose": "tourism",
        "travellers": 1,
        "self_pay": True,
    }
    payload.update(overrides)
    return InternalPreviewRequest.model_validate_json(json.dumps(payload))


def _run(raw: bytes) -> tuple[int, dict[str, object]]:
    stdout = io.StringIO()
    exit_code = run_cli(io.BytesIO(raw), stdout)
    lines = stdout.getvalue().splitlines()
    assert len(lines) == 1
    return exit_code, json.loads(lines[0])


def test_accepted_issuance_uses_real_pricing_and_no_internal_checkpoints() -> None:
    response = build_internal_preview(_request(), today=_TODAY, generated_at=_NOW)

    assert response.decision == "ACCEPT"
    assert response.reason_codes == []
    assert response.internal_checkpoints == []
    assert response.price_idr is not None
    assert response.price_source == "B1 Visa on Arrival (VOA)"
    assert response.price_status == "confirmed"
    assert response.price_warning is None
    assert response.generated_at == _NOW
    assert response.submit_by_date is not None
    assert response.submit_by_date < response.entry_date
    assert response.calendar_status == "confirmed"
    assert response.calendar_coverage_start == date(2026, 7, 28)
    assert response.computed_stay_end == response.expiry_date
    assert "last_legal_day" not in response.model_dump()


def test_unavailable_price_is_explicit_and_requires_staff_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "backend.services.garuda_flow.internal_preview_cli.price_for_case",
        lambda _case_type: (None, None),
    )

    response = build_internal_preview(_request(), today=_TODAY, generated_at=_NOW)

    assert response.decision == "ACCEPT"
    assert response.price_idr is None
    assert response.price_source is None
    assert response.price_status == "unavailable"
    assert response.price_warning is not None
    assert "staff must confirm the price rather than invent one" in response.price_warning


@pytest.mark.parametrize(
    ("purpose", "travellers", "expected_decision", "expected_codes"),
    [
        ("tourism", 1, "ACCEPT", []),
        ("family", 1, "DECLINE", ["PURPOSE_NOT_ELIGIBLE"]),
        ("transit", 1, "DECLINE", ["PURPOSE_NOT_ELIGIBLE"]),
        ("business-meeting", 1, "DECLINE", ["PURPOSE_NOT_ELIGIBLE"]),
        ("tourism", 2, "DECLINE", ["GROUP_CASE"]),
        (
            "business-meeting",
            2,
            "DECLINE",
            ["PURPOSE_NOT_ELIGIBLE", "GROUP_CASE"],
        ),
    ],
)
def test_purpose_and_group_reason_codes_are_unique_stable_and_prose_free(
    purpose: str,
    travellers: int,
    expected_decision: str,
    expected_codes: list[str],
) -> None:
    response = build_internal_preview(
        _request(purpose=purpose, travellers=travellers),
        today=_TODAY,
        generated_at=_NOW,
    )

    assert response.decision == expected_decision
    assert response.reason_codes == expected_codes
    assert len(response.reason_codes) == len(set(response.reason_codes))

    payload = response.model_dump_json()
    for internal_text in (
        "not a simple-tourism case",
        "work/business purpose",
        "not a single adult traveler",
        "family/group case",
        "D-14",
        "D14",
    ):
        assert internal_text not in payload


def test_declined_case_emits_only_neutral_reason_codes() -> None:
    response = build_internal_preview(
        _request(passport_expiry_date="2026-09-01"),
        today=_TODAY,
        generated_at=_NOW,
    )

    assert response.decision == "DECLINE"
    assert "PASSPORT_VALIDITY" in response.reason_codes
    payload = response.model_dump_json()
    assert "passport not valid" not in payload.lower()


def test_extension_exposes_only_d10_d3_d1_internal_checkpoints() -> None:
    response = build_internal_preview(
        _request(
            case_type="extension",
            entry_date="2026-07-25",
            voa_expiry_date="2026-09-05",
        ),
        today=_TODAY,
        generated_at=_NOW,
    )

    assert response.decision == "ACCEPT"
    assert [checkpoint.label for checkpoint in response.internal_checkpoints] == [
        "D-10",
        "D-3",
        "D-1",
    ]
    assert all(checkpoint.kind == "internal" for checkpoint in response.internal_checkpoints)
    assert all(checkpoint.note is None for checkpoint in response.internal_checkpoints)
    assert "D-14" not in response.model_dump_json()
    assert response.published_filing_deadline == date(2026, 8, 29)
    assert response.price_source == "B1 Visa on Arrival Extension"
    assert response.calendar_status == "not_applicable"
    assert response.calendar_warning is None


def test_post_coverage_issuance_is_uncovered_with_manual_warning() -> None:
    response = build_internal_preview(
        _request(
            entry_date="2027-01-05",
            passport_expiry_date="2028-01-05",
        ),
        today=date(2026, 12, 20),
        generated_at=datetime(2026, 12, 20, 1, 0, tzinfo=timezone.utc),
    )

    assert response.decision == "DECLINE"
    assert response.reason_codes == ["ARRIVAL_DATE_UNCONFIRMED"]
    assert response.submit_by_date is None
    assert response.calendar_status == "uncovered"
    assert response.calendar_warning
    assert "fail-closed" not in response.calendar_warning


def test_january_2026_issuance_is_uncovered_and_has_no_submit_date() -> None:
    response = build_internal_preview(
        _request(
            entry_date="2026-01-01",
            passport_expiry_date="2027-01-01",
        ),
        today=date(2025, 12, 30),
        generated_at=datetime(2025, 12, 30, 1, 0, tzinfo=timezone.utc),
    )

    assert response.decision == "DECLINE"
    assert response.reason_codes == ["ARRIVAL_DATE_UNCONFIRMED"]
    assert response.calendar_status == "uncovered"
    assert response.submit_by_date is None


def test_issuance_on_coverage_start_is_uncovered_because_prior_day_is_unknown() -> None:
    response = build_internal_preview(
        _request(
            entry_date="2026-07-28",
            passport_expiry_date="2027-07-28",
        ),
        today=date(2026, 7, 27),
        generated_at=datetime(2026, 7, 27, 1, 0, tzinfo=timezone.utc),
    )

    assert response.calendar_status == "uncovered"
    assert response.submit_by_date is None


def test_day_after_coverage_start_has_a_fully_supported_submit_date() -> None:
    response = build_internal_preview(
        _request(
            entry_date="2026-07-29",
            passport_expiry_date="2027-07-29",
        ),
        today=date(2026, 7, 28),
        generated_at=datetime(2026, 7, 28, 1, 0, tzinfo=timezone.utc),
    )

    assert response.decision == "ACCEPT"
    assert response.calendar_status == "confirmed"
    assert response.submit_by_date == date(2026, 7, 28)


def test_extension_after_calendar_coverage_is_not_applicable_not_uncovered() -> None:
    response = build_internal_preview(
        _request(
            case_type="extension",
            entry_date="2027-01-02",
            passport_expiry_date="2028-01-02",
            voa_expiry_date="2027-02-10",
        ),
        today=date(2027, 1, 10),
        generated_at=datetime(2027, 1, 10, 1, 0, tzinfo=timezone.utc),
    )

    assert response.decision == "ACCEPT"
    assert response.calendar_status == "not_applicable"
    assert response.calendar_warning is None


def test_extension_rejects_future_entry_date() -> None:
    request = _request(
        case_type="extension",
        entry_date=(_TODAY + timedelta(days=1)).isoformat(),
        voa_expiry_date=(_TODAY + timedelta(days=30)).isoformat(),
    )

    with pytest.raises(ValueError, match="entry date"):
        build_internal_preview(request, today=_TODAY, generated_at=_NOW)


def test_extension_rejects_printed_expiry_before_entry() -> None:
    request = _request(
        case_type="extension",
        entry_date="2026-08-01",
        voa_expiry_date="2026-07-31",
    )

    with pytest.raises(ValueError, match="precedes entry"):
        build_internal_preview(request, today=_TODAY, generated_at=_NOW)


def test_extension_rejects_printed_expiry_beyond_b1_max_total_stay() -> None:
    request = _request(
        case_type="extension",
        entry_date="2026-06-01",
        voa_expiry_date="2026-08-01",
    )

    with pytest.raises(ValueError, match="maximum stay"):
        build_internal_preview(request, today=_TODAY, generated_at=_NOW)


def test_extension_rejects_printed_expiry_exactly_at_b1_max_total_stay_boundary() -> None:
    # GUILT case: entry 2026-07-01 + 60 days (B1's inclusive-count max, day 1 = arrival
    # day per imigrasi.go.id) lands on 2026-08-30 — that is day 61 of stay, one day
    # PAST the legal maximum, so it must be rejected. A naive `> max_total_stay_days`
    # comparison on the day-DIFFERENCE lets this exact boundary through as ACCEPT
    # because the difference (60) is not strictly greater than the max (60).
    request = _request(
        case_type="extension",
        entry_date="2026-07-01",
        voa_expiry_date="2026-08-30",
    )

    with pytest.raises(ValueError, match="maximum stay"):
        build_internal_preview(request, today=_TODAY, generated_at=_NOW)


def test_extension_accepts_printed_expiry_one_day_inside_b1_max_total_stay_boundary() -> None:
    # INNOCENCE case: entry 2026-07-01 + 59 days = 2026-08-29 is day 60 of stay —
    # the legal maximum itself, still valid — and must remain ACCEPT.
    request = _request(
        case_type="extension",
        entry_date="2026-07-01",
        voa_expiry_date="2026-08-29",
    )

    response = build_internal_preview(request, today=_TODAY, generated_at=_NOW)

    assert response.decision == "ACCEPT"


def test_past_printed_expiry_reaches_engine_and_declines_as_expired() -> None:
    response = build_internal_preview(
        _request(
            case_type="extension",
            entry_date="2026-07-01",
            voa_expiry_date="2026-08-18",
        ),
        today=_TODAY,
        generated_at=_NOW,
    )

    assert response.decision == "DECLINE"
    assert "EXPIRES_TOO_SOON" in response.reason_codes


def test_internal_preview_response_has_strict_typed_calendar_schema() -> None:
    schema = InternalPreviewResponse.model_json_schema()
    assert schema["additionalProperties"] is False

    response = build_internal_preview(_request(), today=_TODAY, generated_at=_NOW)
    payload = response.model_dump(mode="json")
    assert payload["calendar_status"] in {"confirmed", "uncovered", "not_applicable"}
    assert isinstance(payload["calendar_coverage_start"], str)


def test_strict_malformed_request_is_sanitized_and_nonzero() -> None:
    exit_code, payload = _run(
        json.dumps(
            {
                "case_type": "issuance",
                "nationality": "USA",
                "entry_date": "2026-08-24",
                "passport_expiry_date": "2027-08-24",
                "purpose": "tourism",
                "travellers": "1",
                "self_pay": True,
                "unexpected": "must-not-be-echoed",
            }
        ).encode()
    )

    assert exit_code != 0
    assert payload == {"ok": False, "error": "invalid_request"}
    assert "must-not-be-echoed" not in json.dumps(payload)


def test_oversized_request_is_sanitized_and_nonzero() -> None:
    exit_code, payload = _run(b"{" + b"x" * MAX_REQUEST_BYTES)

    assert exit_code != 0
    assert payload == {"ok": False, "error": "request_too_large"}
