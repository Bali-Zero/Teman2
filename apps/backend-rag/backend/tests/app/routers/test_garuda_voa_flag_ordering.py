"""GARUDA VOA "dark by flag" ordering — Gear-3 gate finding B (PR #4959).

With `GARUDA_PUBLIC_ENABLED` unset (production default), every GARUDA VOA
route across all three lanes must answer 404 `GARUDA_PUBLIC_DISABLED`
*before* touching anything downstream — no `Depends(get_repository)` 503,
no Pydantic-body-validation 422.

Two structural causes the gate measured on PR #4959, both proven wrong here
by exercising the REAL failure conditions rather than a body that happens
to validate:

1. `garuda_orders_router.py`'s handlers all take
   `repository: GarudaOrderRepository = Depends(get_repository)`, and
   FastAPI resolves parameter dependencies BEFORE the handler body runs —
   `_require_flag()` as the first statement inside the handler is too late.
   This app is built with NO `app.state.garuda_order_repository` at all
   (the finding's own words: "including the orders routes with no
   repository wired"), so before the fix these 503 instead of 404.

2. `garuda_voa_public.py`'s `create_eligibility_check` takes
   `payload: EligibilityCheckRequest` as a Pydantic body model — FastAPI
   validates the body before the handler runs too. An EMPTY body (`{}`)
   fails that validation, and `_ContractErrorRoute` turns
   `RequestValidationError` into a 422 INVALID_REQUEST — a response shape
   only a live, mounted GARUDA route can ever produce. Before the fix, a
   deliberately empty/invalid body proves this; the sibling test
   `test_garuda_voa_public.py::test_flag_disabled_by_default_returns_404_
   for_all_three_ops` stayed green throughout because it happens to POST a
   fully VALID body, so it never exercised this ordering bug.

Every route is hit with the crudest possible input on purpose — an empty
JSON body for POSTs, an arbitrary path segment for path params — because
the whole point is that NONE of that should matter: the flag gate must
answer before body shape or repository wiring are even considered.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import garuda_orders_router, garuda_portal_auth, garuda_voa_public

# (case id, method, path, kwargs) — deliberately malformed/empty bodies and
# an app with NOTHING wired onto app.state: no repository, no check store
# override, no session verifier, no payment provider, no magic-link store.
GARUDA_ROUTES: list[tuple[str, str, str, dict]] = [
    ("create_eligibility_check", "POST", "/api/visa/voa/eligibility-checks", {"json": {}}),
    ("get_eligibility_result", "GET", "/api/visa/voa/eligibility-checks/" + "r" * 22, {}),
    ("delete_eligibility_result", "DELETE", "/api/visa/voa/eligibility-checks/" + "r" * 22, {}),
    ("create_order_from_check", "POST", "/api/visa/voa/orders", {"json": {}}),
    ("get_order_and_practice", "GET", "/api/visa/voa/orders/ord_abc123", {}),
    (
        "observe_payment_browser_return",
        "POST",
        "/api/visa/voa/orders/ord_abc123/browser-return-observations",
        {"json": {}},
    ),
    ("receive_payment_webhook", "POST", "/api/visa/voa/webhooks/payment", {"content": b"{}"}),
    (
        "resolve_late_order",
        "POST",
        "/api/visa/voa/staff/orders/ord_abc123/late-resolution",
        {"json": {}},
    ),
    ("request_magic_link", "POST", "/api/visa/voa/auth/magic-links", {"json": {}}),
    ("exchange_magic_link", "POST", "/api/visa/voa/auth/sessions", {"json": {}}),
]


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(garuda_voa_public.router)
    app.include_router(garuda_orders_router.router)
    app.include_router(garuda_portal_auth.router)
    return app


@pytest.fixture(autouse=True)
def _garuda_public_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GARUDA_PUBLIC_ENABLED", raising=False)


@pytest.mark.parametrize(
    "case_id,method,path,kwargs",
    GARUDA_ROUTES,
    ids=[case[0] for case in GARUDA_ROUTES],
)
def test_dark_by_flag_beats_body_validation_and_repository_wiring(
    case_id: str, method: str, path: str, kwargs: dict
) -> None:
    client = TestClient(_app())
    response = client.request(method, path, **kwargs)
    assert response.status_code == 404, (
        f"{case_id} ({method} {path}) answered {response.status_code} with "
        f"GARUDA_PUBLIC_ENABLED unset — body {response.text!r}. A dark-"
        f"launched route must 404 before it ever reaches body validation or "
        f"a Depends() that needs app.state wiring; anything else is an "
        f"anonymous existence-and-liveness oracle on a route this same PR "
        f"is adding to the public allowlist."
    )
    # Two contract-error-body shapes coexist on purpose here, and unifying
    # them is a separate, out-of-scope concern from this test's ordering
    # claim: `garuda_voa_public.py` / `garuda_portal_auth.py` use the
    # `_ContractErrorRoute` + `_error()` shape (`{"code": ..., ...}` at the
    # top level); `garuda_orders_router.py` raises a bare `HTTPException`,
    # whose default FastAPI envelope nests the same payload under
    # `"detail"`. Both are asserted here because this test's job is
    # "flag beats body validation and repository wiring", not "all three
    # GARUDA routers share one error envelope".
    body = response.json()
    code = body.get("code") or (body.get("detail") or {}).get("code")
    assert code == "GARUDA_PUBLIC_DISABLED", body
