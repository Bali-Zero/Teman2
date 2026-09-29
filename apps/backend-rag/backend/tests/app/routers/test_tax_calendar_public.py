import dataclasses
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.public_endpoints import find_entry
from backend.app.routers import tax_calendar_public
from backend.app.routers.tax_calendar_public import get_tax_calendar_today, router
from backend.middleware.rate_limiter import RateLimitMiddleware
from backend.services.compliance.obligations_register import ObligationRule, load_catalog
from backend.services.compliance.tax_calendar_public_review import (
    PublicReview,
    rule_fingerprint,
)

URL = "/api/public/tax-calendar/obligations"
REVIEWED_ON = date(2026, 9, 30)


def _rule(rule_id: str) -> ObligationRule:
    return next(r for r in load_catalog() if r.id == rule_id)


def _clear(*rule_ids: str, fingerprint: str | None = None) -> dict[str, PublicReview]:
    return {
        rid: PublicReview(
            rid, "Test Signer", REVIEWED_ON, fingerprint or rule_fingerprint(_rule(rid))
        )
        for rid in rule_ids
    }


def _client(
    today: date = date(2026, 1, 1), reviews: dict[str, PublicReview] | None = None
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_tax_calendar_today] = lambda: today
    if reviews is not None:
        app.dependency_overrides[tax_calendar_public.get_public_reviews] = lambda: reviews
    return TestClient(app)


def _company_payload(**overrides: object) -> dict[str, object]:
    return {
        "taxpayer_type": "company",
        "company_type": "PT_PMA",
        "has_employees": True,
        "employee_count": 3,
        "pkp": True,
        **overrides,
    }


def test_shipped_review_file_clears_nothing_so_nothing_is_public() -> None:
    body = _client().post(URL, json=_company_payload()).json()

    assert body["obligations"] == []
    assert body["withheld_count"] > 0


def test_cleared_rule_is_returned_with_future_dates_and_reviewed_on() -> None:
    response = _client(reviews=_clear("pph21_payment")).post(URL, json=_company_payload())

    assert response.status_code == 200
    body = response.json()
    assert [o["id"] for o in body["obligations"]] == ["pph21_payment"]
    item = body["obligations"][0]
    assert item["reviewed_on"] == "2026-09-30"
    assert item["upcoming_due_dates"]
    assert all(d["due_date"] >= "2026-01-01" for d in item["upcoming_due_dates"])
    assert body["withheld_count"] > 0


def test_wrong_fingerprint_withholds_the_rule() -> None:
    reviews = _clear("pph21_payment", fingerprint="0" * 64)
    body = _client(reviews=reviews).post(URL, json=_company_payload()).json()

    assert body["obligations"] == []


def test_edited_rule_no_longer_matches_its_fingerprint() -> None:
    rule = _rule("pph21_payment")
    edited = dataclasses.replace(rule, notes="edited after review")

    assert rule_fingerprint(edited) != rule_fingerprint(rule)


def test_review_cannot_clear_a_needs_review_or_unverified_rule() -> None:
    assert _rule("lkpm_quarterly").needs_review_reason is not None
    assert not _rule("pmse_vat_assessment").verified
    reviews = _clear("lkpm_quarterly", "pmse_vat_assessment")
    payload = _company_payload(pmse_vat_appointed=True, serves_indonesian_users_online=True)
    body = _client(reviews=reviews).post(URL, json=payload).json()

    assert body["obligations"] == []


def test_payload_has_no_verification_flags_and_no_withheld_rule() -> None:
    response = _client(reviews=_clear("pph21_payment")).post(URL, json=_company_payload())

    body = response.json()
    assert set(body) == {"obligations", "withheld_count"}
    assert set(body["obligations"][0]) == {
        "id",
        "name",
        "authority",
        "legal_source",
        "frequency",
        "reviewed_on",
        "upcoming_due_dates",
    }
    assert "lkpm_quarterly" not in response.text
    assert "Test Signer" not in response.text


def test_individual_gets_no_company_scoped_rules() -> None:
    response = _client().post(
        "/api/public/tax-calendar/obligations", json={"taxpayer_type": "individual"}
    )

    assert response.status_code == 200
    assert response.json()["obligations"] == []


def test_individual_gets_no_company_scoped_rule_even_when_every_rule_is_cleared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relaxed = tuple(
        dataclasses.replace(r, verified=True, needs_review_reason=None) for r in load_catalog()
    )
    reviews = {
        r.id: PublicReview(r.id, "Test Signer", REVIEWED_ON, rule_fingerprint(r)) for r in relaxed
    }
    monkeypatch.setattr(tax_calendar_public, "_catalog", lambda: relaxed)
    company_scoped = {r.id for r in relaxed if any(p.attr == "company_type" for p in r.applies_if)}
    assert "halal_certification" in company_scoped

    company = _client(reviews=reviews).post(URL, json=_company_payload(has_employees=False))
    individual = _client(reviews=reviews).post(URL, json={"taxpayer_type": "individual"})

    assert "halal_certification" in {o["id"] for o in company.json()["obligations"]}
    assert individual.json() == {"obligations": [], "withheld_count": 0}


@pytest.mark.parametrize("value", ["02-30", "04-31", "06-31", "09-31", "11-31", "02-31"])
def test_fiscal_year_end_must_be_a_real_calendar_day(value: str) -> None:
    response = _client().post(URL, json=_company_payload(fiscal_year_end=value))

    assert response.status_code == 422


@pytest.mark.parametrize("value", ["12-31", "02-29", "02-28", "04-30", "01-01"])
def test_real_fiscal_year_ends_are_accepted(value: str) -> None:
    response = _client().post(URL, json=_company_payload(fiscal_year_end=value))

    assert response.status_code == 200


def test_taxpayer_type_is_the_only_required_field() -> None:
    response = _client().post(
        "/api/public/tax-calendar/obligations", json={"taxpayer_type": "company"}
    )

    assert response.status_code == 200


def test_unknown_field_is_rejected() -> None:
    response = _client().post(
        "/api/public/tax-calendar/obligations",
        json={"taxpayer_type": "individual", "unexpected": True},
    )

    assert response.status_code == 422


def test_horizon_and_injected_clock_are_deterministic() -> None:
    client = _client(date(2026, 1, 1), _clear("pph21_payment"))
    response = client.post(
        "/api/public/tax-calendar/obligations", json=_company_payload(horizon_days=10)
    )

    assert response.status_code == 200
    assert response.json()["obligations"]
    for obligation in response.json()["obligations"]:
        for due in obligation["upcoming_due_dates"]:
            assert "2026-01-01" <= due["due_date"] < "2026-01-11"


def test_route_is_public_and_has_a_dedicated_rate_limit() -> None:
    entry = find_entry("/api/public/tax-calendar/obligations")

    assert entry is not None
    assert entry.requires_route_auth is False
    assert RateLimitMiddleware.RATE_LIMITS["/api/public/tax-calendar/obligations"] == (30, 60)
