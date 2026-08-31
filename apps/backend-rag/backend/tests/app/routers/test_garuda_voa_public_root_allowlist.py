"""GARUDA VOA public-root allowlist (orchestrator PR, 2026-08-25).

GUILT half: every public route registered in `public_endpoints.py` under the
shared `/api/visa/voa` root (createEligibilityCheck / getEligibilityResult /
deleteEligibilityResult -- L2, garuda_voa_public.py -- and
createOrderFromCheck / getOrderAndPractice / observePaymentBrowserReturn /
receivePaymentWebhook -- L3, garuda_orders_router.py) answers WITHOUT any
API key or JWT, through the REAL mounted application (`main_api.app` --
`test_garuda_voa_public.py`'s bare `FastAPI()` double would stay green even
though production returned 401 for every one of these paths; confirmed live
against nuzantara-rag.fly.dev on 2026-08-25 before this PR's registry
entries existed). `garuda_portal_auth.py`'s magic-link pair already has an
equivalent mounted test (`test_garuda_portal_auth_mounted.py`) from the PR
that discovered this gap for the shared `/api/visa/voa` root -- this file is
the same proof for the two lanes that PR flagged as out of scope.

INNOCENCE half: the staff-only sibling on the SAME root
(`/api/visa/voa/staff/orders/{order_id}/late-resolution`,
`garuda_orders_router.py::_require_staff_actor`) must still be rejected by
`HybridAuthMiddleware` ITSELF -- not merely end up 401 for an unrelated
in-handler reason. A future edit that widens one of the entries above into
a blanket `/api/visa/voa/` prefix would make the middleware treat the staff
path as public too; the handler's OWN `_require_staff_actor` would still
401 an unauthenticated caller in that world, so a bare `status_code == 401`
assertion would stay green straight through that regression. Asserting the
middleware's OWN failure body (`{"detail": "Authentication required"}`,
never the handler's `{"code": "SESSION_REQUIRED", ...}` shape) is what
turns this test red instead -- see `public_endpoints.py`'s comment block
for why every entry above is EXACT or TEMPLATE (segment-count-matched),
never a PREFIX, so this can only happen via a deliberate, reviewable change
to the registry's matching mode.

Discriminator: `X-Auth-Type: public`, set by
`HybridAuthMiddleware.dispatch` on every response that takes its
public-endpoint branch (`backend/middleware/hybrid_auth.py`). This is
decoupled from whatever status code the router's own business logic
returns -- the persistence store / payment provider / db pool are all
unwired in this test process by design (same posture as
`test_garuda_portal_auth_mounted.py`); the only thing under test here is
whether the auth *gate* was bypassed, never whether the funnel's downstream
services answer.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

# Building `main_api.app` is the point -- see
# `test_garuda_portal_auth_mounted.py`'s identical precedent/cost note.
from backend.app import main_api as _main_api_module

_APP = _main_api_module.app

# (case id, method, path, kwargs passed straight to httpx.AsyncClient.request)
PUBLIC_REQUESTS: list[tuple[str, str, str, dict]] = [
    ("create_eligibility_check", "POST", "/api/visa/voa/eligibility-checks", {"json": {}}),
    ("get_eligibility_result", "GET", "/api/visa/voa/eligibility-checks/abc123", {}),
    ("delete_eligibility_result", "DELETE", "/api/visa/voa/eligibility-checks/abc123", {}),
    ("create_order_from_check", "POST", "/api/visa/voa/orders", {"json": {}}),
    ("get_order_and_practice", "GET", "/api/visa/voa/orders/ord_abc123", {}),
    (
        "observe_payment_browser_return",
        "POST",
        "/api/visa/voa/orders/ord_abc123/browser-return-observations",
        {"json": {}},
    ),
    ("receive_payment_webhook", "POST", "/api/visa/voa/webhooks/payment", {"content": b"{}"}),
]


@pytest.fixture(autouse=True)
def _garuda_public_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id,method,path,kwargs",
    PUBLIC_REQUESTS,
    ids=[case[0] for case in PUBLIC_REQUESTS],
)
async def test_public_voa_route_bypasses_the_api_key_gate(case_id, method, path, kwargs):
    transport = ASGITransport(app=_APP)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path, **kwargs)
    assert response.headers.get("X-Auth-Type") == "public", (
        f"{case_id} ({method} {path}) did not take HybridAuthMiddleware's "
        f"public-endpoint branch -- got status {response.status_code}, "
        f"headers {dict(response.headers)}. This is exactly the defect this "
        f"PR fixes: without a public_endpoints.py entry this path 401s in "
        f"production before ever reaching the handler."
    )


@pytest.mark.asyncio
async def test_staff_late_resolution_route_is_never_public():
    """The one route on this shared root that must stay behind the
    API-key/JWT gate. See module docstring for why the assertion checks the
    FAILURE BODY, not just the status code."""
    transport = ASGITransport(app=_APP)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/visa/voa/staff/orders/ord_abc123/late-resolution",
            json={"resolution": "honoured", "staff_reference": "ref-1"},
        )
    assert response.status_code == 401
    assert response.headers.get("X-Auth-Type") != "public"
    assert response.json() == {"detail": "Authentication required"}, (
        "the staff route must be rejected by HybridAuthMiddleware itself "
        "(detail == 'Authentication required') -- a body shaped like the "
        "handler's own SESSION_REQUIRED error would mean the middleware let "
        "an unauthenticated request THROUGH to the handler, i.e. a future "
        "edit widened a public_endpoints.py entry into a prefix that now "
        "covers this staff-only path"
    )
