"""Guilt and innocence suite for Zero's 2026-10-14 ruling ('E33F everywhere').

Proves:
1. PricingService.search_service skips internal rows and returns the three E33F rows
   for 'retirement', 'retire', 'pension', 'pensiun', 'pensiunan', 'senior'.
2. PricingService.format_for_llm_context omits internal rows for every service_type
   while keeping E33F and other non-internal rows.
3. VisaOracleService.recommend_visas(purpose='retire') ranks E33F rows and never
   returns internal rows, while keeping 'Retirement KITAP + MERP' and other
   purposes unchanged.
4. GET /api/pricing/all and GET /api/pricing/search omit internal rows at every depth,
   while GET /api/pricing/service returns 404 for internal keys and 200 for public keys.
5. In-process resolution (get_service_by_key, pricing_adapter, compliance renewal_rules,
   raw catalogue JSON) still resolves all three internal Retirement rows with unchanged
   prices.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user
from backend.app.routers import dynamic_pricing as dynamic_pricing_router
from backend.services.compliance.renewal_rules import RENEWAL_RULES
from backend.services.compliance.revenue_estimator import estimate_renewal_revenue
from backend.services.pricing.pricing_service import (
    PricingService,
    _is_internal_service,
)
from backend.services.visa_engine.models import PricingKey
from backend.services.visa_engine.pricing_adapter import resolve_pricing_key
from backend.services.visa_oracle.visa_oracle_service import VisaOracleService

INTERNAL_RETIREMENT_ROWS: dict[str, str] = {
    "Retirement (Offshore)": "14.000.000 IDR",
    "Retirement (Altus/Onshore)": "16.000.000 IDR",
    "Retirement (Extend)": "10.000.000 IDR",
}

E33F_ROWS: dict[str, str] = {
    "E33F Second Home Senior (1 Year, Offshore)": "14.000.000 IDR",
    "E33F Second Home Senior (1 Year, Altus/Onshore)": "16.000.000 IDR",
    "E33F Second Home Senior (Extend)": "10.000.000 IDR",
}

CATALOG_PATH = Path(__file__).resolve().parents[3] / "data" / "bali_zero_official_prices_2026.json"


@pytest.fixture
def pricing_service() -> PricingService:
    return PricingService()


@pytest.fixture
def client(pricing_service: PricingService, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        dynamic_pricing_router,
        "get_pricing_service",
        lambda: pricing_service,
    )
    app = FastAPI()
    app.include_router(dynamic_pricing_router.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "test@balizero.com",
        "role": "admin",
    }
    return TestClient(app)


# ---------------------------------------------------------------------------
# (1) PricingService.search_service — Guilt & Innocence (EN + ID parity)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "retirement",
        "retire",
        "pension",
        "pensioner",
        "pensiun",
        "pensiunan",
        "senior",
    ],
)
def test_search_service_guilt_returns_e33f_and_never_internal_rows(
    pricing_service: PricingService,
    query: str,
) -> None:
    res = pricing_service.search_service(query)
    kitas = res.get("results", {}).get("kitas_permits", {})
    for e33f_key, expected_price in E33F_ROWS.items():
        assert e33f_key in kitas, f"{query!r} did not return {e33f_key!r}"
        assert kitas[e33f_key]["price"] == expected_price

    for internal_key in INTERNAL_RETIREMENT_ROWS:
        assert internal_key not in kitas, f"{query!r} leaked internal row {internal_key!r}"


def test_search_service_innocence_kitap_and_non_f_e33_rows_unaffected(
    pricing_service: PricingService,
) -> None:
    raw_catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    expected_kitap_price = raw_catalog["services"]["kitap_permits"]["Retirement KITAP + MERP"][
        "price"
    ]
    assert expected_kitap_price == "45.000.000 IDR"

    for q in ("KITAP", "merp"):
        res = pricing_service.search_service(q)
        kitap = res.get("results", {}).get("kitap_permits", {})
        assert "Retirement KITAP + MERP" in kitap
        assert kitap["Retirement KITAP + MERP"]["price"] == expected_kitap_price

    e33_res = pricing_service.search_service("E33")
    kitas = e33_res.get("results", {}).get("kitas_permits", {})
    assert "E33 Second Home (5 Years)" in kitas
    assert "E33E Second Home Senior (5 Years)" in kitas
    assert "E33E Second Home Senior (Extend)" in kitas
    assert "E33G Remote Worker (Altus/Onshore)" in kitas
    assert "E33G Remote Worker (Offshore)" in kitas
    assert "E33G Remote Worker (Extend)" in kitas


# ---------------------------------------------------------------------------
# (2) PricingService.format_for_llm_context — Guilt & Innocence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "service_type",
    [None, "all", "visa", "kitas", "business", "tax", "other", "urgent"],
)
def test_format_for_llm_context_guilt_never_cites_internal_rows(
    pricing_service: PricingService,
    service_type: str | None,
) -> None:
    text = pricing_service.format_for_llm_context(service_type)
    for internal_key in INTERNAL_RETIREMENT_ROWS:
        assert internal_key not in text


def test_format_for_llm_context_innocence_includes_e33f_and_public_rows(
    pricing_service: PricingService,
) -> None:
    for st in (None, "all", "kitas"):
        text = pricing_service.format_for_llm_context(st)
        for e33f_key in E33F_ROWS:
            assert e33f_key in text
        assert "Retirement KITAP + MERP" in text
        assert "Working KITAS (Offshore)" in text


# ---------------------------------------------------------------------------
# (3) VisaOracleService.recommend_visas — Guilt & Innocence
# ---------------------------------------------------------------------------


def test_visa_oracle_recommend_retire_ranks_e33f_and_omits_internal_rows(
    pricing_service: PricingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "backend.services.visa_oracle.visa_oracle_service.get_pricing_service",
        lambda: pricing_service,
    )
    oracle = VisaOracleService()
    for duration in ("medium", "long"):
        recs = oracle.recommend_visas(
            nationality="Australian",
            purpose="retire",
            duration=duration,
            family=False,
        )
        assert recs
        names = [r["visa_name"] for r in recs]
        assert any("E33F" in n for n in names)
        for internal_key in INTERNAL_RETIREMENT_ROWS:
            assert internal_key not in names


# ---------------------------------------------------------------------------
# (4) Routers: /api/pricing/all, /api/pricing/search, /api/pricing/service
# ---------------------------------------------------------------------------


def _collect_all_dict_keys(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            found.add(str(k))
            found.update(_collect_all_dict_keys(v))
    elif isinstance(node, list):
        for item in node:
            found.update(_collect_all_dict_keys(item))
    return found


def test_router_all_and_search_omit_internal_rows_at_every_depth(
    client: TestClient,
) -> None:
    all_resp = client.get("/api/pricing/all")
    assert all_resp.status_code == 200
    all_body = all_resp.json()
    all_keys = _collect_all_dict_keys(all_body)
    for internal_key in INTERNAL_RETIREMENT_ROWS:
        assert internal_key not in all_keys
    for e33f_key, expected_price in E33F_ROWS.items():
        assert all_body["services"]["kitas_permits"][e33f_key]["price"] == expected_price
    assert "Retirement KITAP + MERP" in all_body["services"]["kitap_permits"]

    for query in ("retirement", "pensiun", "pensiunan", "senior"):
        search_resp = client.get("/api/pricing/search", params={"q": query})
        assert search_resp.status_code == 200
        search_body = search_resp.json()
        search_keys = _collect_all_dict_keys(search_body)
        for internal_key in INTERNAL_RETIREMENT_ROWS:
            assert internal_key not in search_keys
        kitas_hits = search_body["results"]["kitas_permits"]
        for e33f_key, expected_price in E33F_ROWS.items():
            assert kitas_hits[e33f_key]["price"] == expected_price


def test_router_service_404_for_internal_and_200_for_public(
    client: TestClient,
) -> None:
    for internal_key in INTERNAL_RETIREMENT_ROWS:
        resp = client.get("/api/pricing/service", params={"key": internal_key})
        assert resp.status_code == 404

    for e33f_key, expected_price in E33F_ROWS.items():
        resp = client.get("/api/pricing/service", params={"key": e33f_key})
        assert resp.status_code == 200
        assert resp.json()["price"] == expected_price


# ---------------------------------------------------------------------------
# (5) In-process Innocence: get_service_by_key, pricing_adapter, renewal_rules, raw JSON
# ---------------------------------------------------------------------------


def test_in_process_get_service_by_key_and_raw_catalogue_keep_internal_rows(
    pricing_service: PricingService,
) -> None:
    raw_catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    raw_kitas = raw_catalog["services"]["kitas_permits"]

    for internal_key, expected_price in INTERNAL_RETIREMENT_ROWS.items():
        assert internal_key in raw_kitas
        assert raw_kitas[internal_key]["price"] == expected_price
        assert raw_kitas[internal_key]["internal"] is True

        resolved = pricing_service.get_service_by_key(internal_key)
        assert resolved is not None
        assert resolved["price"] == expected_price
        assert _is_internal_service(pricing_service, internal_key, resolved) is True


def test_in_process_pricing_adapter_and_compliance_renewal_rules_keep_resolving(
    pricing_service: PricingService,
) -> None:
    # seq-009..027 signed packs resolve 'Retirement (Offshore)' via resolve_pricing_key
    res = resolve_pricing_key(
        PricingKey(category="kitas_permits", item_key="Retirement (Offshore)"),
        pricing_catalog=pricing_service,
        evaluated_at=datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc),
    )
    assert res.status == "AVAILABLE"
    assert res.amount == 14_000_000

    # compliance renewal_rules uses 'Retirement (Extend)' via get_all_prices()
    rule = RENEWAL_RULES["kitas_retirement_extend"]
    assert rule.renewal_pricing_key == "Retirement (Extend)"
    rev = estimate_renewal_revenue(rule, pricing_service.get_all_prices())
    assert rev == 10_000_000.0
