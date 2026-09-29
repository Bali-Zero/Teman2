import dataclasses
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.public_endpoints import find_entry
from backend.app.routers import tax_calendar_public
from backend.app.routers.tax_calendar_public import get_tax_calendar_today, router
from backend.middleware.rate_limiter import RateLimitMiddleware
from backend.services.compliance.business_days import holiday_years_loaded
from backend.services.compliance.obligations_register import (
    ClientProfile,
    ObligationRule,
    applies,
    load_catalog,
)
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
    today: date = date(2026, 1, 1),
    reviews: dict[str, PublicReview] | None = None,
    loaded_years: frozenset[int] | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_tax_calendar_today] = lambda: today
    if reviews is not None:
        app.dependency_overrides[tax_calendar_public.get_public_reviews] = lambda: reviews
    if loaded_years is not None:
        app.dependency_overrides[tax_calendar_public.get_loaded_holiday_years] = lambda: (
            loaded_years
        )
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


OWNER_CLEARED = {
    "pph21_payment",
    "spt_masa_pph21",
    "spt_masa_ppn",
    "spt_tahunan_badan",
    "rups_annual",
    "bpjs_kesehatan_monthly",
    "pse_registration",
    "wajib_lapor_ketenagakerjaan",
    "rptka_imta_expat",
}


def test_shipped_review_file_clears_exactly_the_owner_batch() -> None:
    assert set(tax_calendar_public.get_public_reviews()) == OWNER_CLEARED


def test_shipped_clearances_release_only_cleared_rules_and_withhold_the_rest() -> None:
    body = _client().post(URL, json=_company_payload()).json()
    profile = ClientProfile(company_type="PT_PMA", has_employees=True, employee_count=3, pkp=True)
    applicable = {r.id for r in load_catalog() if applies(r, profile)}

    assert {o["id"] for o in body["obligations"]} == applicable & OWNER_CLEARED
    assert body["obligations"]
    assert body["withheld_count"] == len(applicable - OWNER_CLEARED)
    assert body["withheld_count"] > 0
    for rule in load_catalog():
        if not rule.verified or rule.needs_review_reason is not None:
            assert rule.id not in {o["id"] for o in body["obligations"]}


def test_every_owner_cleared_rule_is_verified_and_review_free() -> None:
    for rule_id in OWNER_CLEARED:
        rule = _rule(rule_id)
        assert rule.verified and rule.needs_review_reason is None


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


def test_provisional_marks_only_dates_beyond_the_loaded_holiday_years() -> None:
    client = _client(date(2026, 9, 29), _clear("pph21_payment"), frozenset({2026}))
    body = client.post(URL, json=_company_payload()).json()
    by_id = {o["id"]: o["upcoming_due_dates"] for o in body["obligations"]}

    assert _rule("pph21_payment").due.roll == "next_business_day"
    dates_2026 = [d for d in by_id["pph21_payment"] if d["due_date"].startswith("2026")]
    dates_2027 = [d for d in by_id["pph21_payment"] if d["due_date"].startswith("2027")]
    assert dates_2026 and dates_2027
    assert all(d["provisional"] is False for d in dates_2026)
    assert all(d["provisional"] is True for d in dates_2027)


def test_a_year_that_becomes_loaded_is_no_longer_provisional() -> None:
    client = _client(date(2026, 9, 29), _clear("pph21_payment"), frozenset({2026, 2027}))
    body = client.post(URL, json=_company_payload()).json()
    dates = body["obligations"][0]["upcoming_due_dates"]

    assert any(d["due_date"].startswith("2027") for d in dates)
    assert all(d["provisional"] is False for d in dates)


def test_production_resolves_loaded_years_through_the_real_function() -> None:
    assert tax_calendar_public.get_loaded_holiday_years() == holiday_years_loaded()
    assert tax_calendar_public.holiday_years_loaded is holiday_years_loaded


def test_roll_none_rules_are_never_provisional(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = dataclasses.replace(
        _rule("pph21_payment"), due=dataclasses.replace(_rule("pph21_payment").due, roll="none")
    )
    monkeypatch.setattr(tax_calendar_public, "_catalog", lambda: (rule,))
    reviews = {rule.id: PublicReview(rule.id, "Test Signer", REVIEWED_ON, rule_fingerprint(rule))}
    client = _client(date(2026, 9, 29), reviews, frozenset({2026}))
    body = client.post(URL, json=_company_payload()).json()
    dates = body["obligations"][0]["upcoming_due_dates"]

    assert any(d["due_date"].startswith("2027") for d in dates)
    assert all(d["provisional"] is False for d in dates)


def test_annual_return_clamps_day_31_to_april_30() -> None:
    body = _client(date(2026, 9, 29)).post(URL, json=_company_payload()).json()
    annual = next(o for o in body["obligations"] if o["id"] == "spt_tahunan_badan")

    assert [d["due_date"] for d in annual["upcoming_due_dates"]] == ["2027-04-30"]


def test_every_returned_due_date_is_a_real_iso_date() -> None:
    payload = _company_payload(has_foreign_employees=True, serves_indonesian_users_online=True)
    body = _client(date(2026, 9, 29)).post(URL, json=payload).json()

    for obligation in body["obligations"]:
        for due in obligation["upcoming_due_dates"]:
            assert date.fromisoformat(due["due_date"]).isoformat() == due["due_date"]


def test_one_time_and_event_rules_come_back_without_dates() -> None:
    payload = _company_payload(has_foreign_employees=True, serves_indonesian_users_online=True)
    body = _client(date(2026, 9, 29)).post(URL, json=payload).json()
    by_id = {o["id"]: o for o in body["obligations"]}

    for rule_id in ("pse_registration", "wajib_lapor_ketenagakerjaan", "rptka_imta_expat"):
        assert by_id[rule_id]["upcoming_due_dates"] == []
