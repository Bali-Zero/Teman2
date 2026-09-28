from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.public_endpoints import find_entry
from backend.app.routers.tax_calendar_public import get_tax_calendar_today, router
from backend.middleware.rate_limiter import RateLimitMiddleware


def _client(today: date = date(2026, 1, 1)) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_tax_calendar_today] = lambda: today
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


def test_pt_pma_with_employees_and_pkp_gets_lkpm_pph21_and_ppn_due_dates() -> None:
    response = _client().post("/api/public/tax-calendar/obligations", json=_company_payload())

    assert response.status_code == 200
    obligations = {item["id"]: item for item in response.json()["obligations"]}
    for rule_id in ("lkpm_quarterly", "pph21_payment", "spt_masa_ppn"):
        assert rule_id in obligations
        assert obligations[rule_id]["upcoming_due_dates"]
        assert all(
            item["due_date"] >= "2026-01-01" for item in obligations[rule_id]["upcoming_due_dates"]
        )


def test_individual_gets_no_company_scoped_rules() -> None:
    response = _client().post(
        "/api/public/tax-calendar/obligations", json={"taxpayer_type": "individual"}
    )

    assert response.status_code == 200
    assert response.json()["obligations"] == []


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
    client = _client(date(2026, 1, 1))
    response = client.post(
        "/api/public/tax-calendar/obligations", json=_company_payload(horizon_days=10)
    )

    assert response.status_code == 200
    for obligation in response.json()["obligations"]:
        for due in obligation["upcoming_due_dates"]:
            assert "2026-01-01" <= due["due_date"] < "2026-01-11"


def test_route_is_public_and_has_a_dedicated_rate_limit() -> None:
    entry = find_entry("/api/public/tax-calendar/obligations")

    assert entry is not None
    assert entry.requires_route_auth is False
    assert RateLimitMiddleware.RATE_LIMITS["/api/public/tax-calendar/obligations"] == (30, 60)
