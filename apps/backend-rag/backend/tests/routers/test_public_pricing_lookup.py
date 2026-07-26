"""GET /api/pricing/service — the one pricing route the public website can reach.

Before this route existed there was no pricing endpoint on the light `_API`
process at all, so every price on balizero.com was a hand-maintained literal and
Golden Rule #11 ("prices come from PricingTool only") was unenforceable on the
client surface. These tests pin the three properties that make it safe to expose:

  guilt      it returns the real catalogue row for an exact key
  innocence  it refuses to guess — an almost-right key is 404, never a near-miss
  blast      only THIS path is auth-exempt; /all, /search, /scenario are not
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.public_endpoints import PUBLIC_ENDPOINTS, find_entry
from backend.app.routers import dynamic_pricing
from backend.services.pricing.pricing_service import get_pricing_service

# A key that must exist in the shipped catalogue. Chosen deliberately: it is the
# key the Second Home landing page renders, i.e. the row whose absence from any
# public surface is what motivated this route.
REAL_KEY = "E33 Second Home (5 Years)"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(dynamic_pricing.router)
    return TestClient(app)


# ── guilt ─────────────────────────────────────────────────────────────────────


def test_returns_the_catalogue_row_for_an_exact_key(client: TestClient) -> None:
    resp = client.get("/api/pricing/service", params={"key": REAL_KEY})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == REAL_KEY
    assert body["price"], "a catalogue row must carry a renderable price"


def test_price_matches_the_ssot_exactly(client: TestClient) -> None:
    """The route must not reformat, round, or re-render the SSOT price."""
    svc = get_pricing_service()
    expected = svc.get_service_by_key(REAL_KEY)
    assert expected is not None, "fixture key vanished from the catalogue"

    body = client.get("/api/pricing/service", params={"key": REAL_KEY}).json()
    assert body["price"] == expected["price"]


# ── innocence: it refuses to guess ────────────────────────────────────────────


@pytest.mark.parametrize(
    "near_miss",
    [
        "E33 Second Home",  # prefix of the real key
        "E33 Second Home (5 Year)",  # one character off
        "e33 second home (5 years)",  # case differs
        " E33 Second Home (5 Years)",  # leading space
        "Second Home",  # keyword a human would type into /search
        "E33",  # the visa code alone
    ],
)
def test_near_miss_keys_are_404_never_a_guessed_row(
    client: TestClient, near_miss: str
) -> None:
    """`/search` scores and guesses; this route must not.

    A page rendering "the price" from an approximate match would publish a
    number for a service the visitor did not ask about. 404 lets the caller
    fall back to its pinned literal, which is the safe failure.
    """
    resp = client.get("/api/pricing/service", params={"key": near_miss})
    assert resp.status_code == 404, (
        f"{near_miss!r} resolved to {resp.text} — the lookup guessed"
    )


def test_unknown_key_is_404(client: TestClient) -> None:
    resp = client.get("/api/pricing/service", params={"key": "No Such Service 12345"})
    assert resp.status_code == 404


def test_empty_key_is_rejected_by_validation(client: TestClient) -> None:
    assert client.get("/api/pricing/service", params={"key": ""}).status_code == 422


# ── blast radius: exactly one public pricing path ─────────────────────────────


def test_the_lookup_is_registered_public() -> None:
    assert find_entry("/api/pricing/service") is not None


@pytest.mark.parametrize(
    "sibling",
    ["/api/pricing/all", "/api/pricing/search", "/api/pricing/scenario"],
)
def test_sibling_pricing_routes_stay_authenticated(sibling: str) -> None:
    """The registry entry is exact-match so the whole /api/pricing family does
    not become anonymous. `/all` dumps the entire catalogue and `/scenario`
    aggregates Oracle collections — neither belongs on the public surface."""
    assert find_entry(sibling) is None, f"{sibling} became public"


def test_no_prefix_entry_swallows_the_pricing_family() -> None:
    """Guards the shape, not just today's paths: a later `prefix` entry on
    /api/pricing would silently re-open the siblings this test protects."""
    offenders = [
        e
        for e in PUBLIC_ENDPOINTS
        if e.match != "exact" and "/api/pricing" in e.prefix
    ]
    assert not offenders, f"prefix-matched pricing entries: {offenders}"


# ── the service-layer contract the route depends on ───────────────────────────


def test_lookup_returns_none_when_the_catalogue_is_not_loaded() -> None:
    """503-vs-404 hinges on this: the caller must be able to tell "no such
    service" from "the price source is down"."""
    svc = get_pricing_service()
    original = svc.loaded
    try:
        svc.loaded = False
        assert svc.get_service_by_key(REAL_KEY) is None
    finally:
        svc.loaded = original
