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

INNOCENCE half: the staff-only routes on the SAME root
(`/api/visa/voa/staff/orders/{order_id}/late-resolution`,
`garuda_orders_router.py::_require_staff_actor`, and the four
`garuda_staff_router.py` practice operations) must still be rejected by
`HybridAuthMiddleware` ITSELF -- not merely end up 401 for an unrelated
in-handler reason. A future edit that widens one of the entries above into
a blanket `/api/visa/voa/` prefix would make the middleware treat the staff
path as public too; the handler's OWN `_require_staff_actor` would still
401 an unauthenticated caller in that world, so a bare `status_code == 401`
assertion would stay green straight through that regression.

This file used to discriminate the two worlds by BODY: the middleware's
generic `{"detail": "Authentication required"}` vs the handler's
`{"code": "SESSION_REQUIRED", ...}`. That discriminator is GONE as of the
W3C contract-closure PR, on purpose -- the frozen contract
(`products/garuda-voa/contracts/openapi.yaml`) declares `401 ->
SESSION_REQUIRED` for all five staff operations, and the middleware now
serves exactly that envelope via `hybrid_auth.contract_401_envelope()` (a BODY
change only: still 401, still refused before the handler, still not public).
Two discriminators replace it, and neither can go blind the way a body
string can:

  1. STRUCTURAL -- `public_endpoints.find_entry(path) is None`. This reads
     the registry itself rather than a symptom of it, so it is red the
     instant an entry widens to cover a staff path, whatever the response
     looks like.
  2. LIVE -- `WWW-Authenticate: Bearer`, set ONLY by the middleware's own
     401 branch. No GARUDA router sets that header (`_error()` in
     `garuda_staff_router.py` / `garuda_orders_router.py` sets the privacy
     headers and nothing else), so its presence proves the refusal came from
     the gate and not from a handler that was allowed to run.

`X-Auth-Type != "public"` is kept as a third, weaker signal: the public
branch sets it on `call_next`'s response, so an HTTPException raised inside
a wrongly-public handler would skip it -- which is why it cannot be the
only assertion. See `public_endpoints.py`'s comment block for why every
entry above is EXACT or TEMPLATE (segment-count-matched), never a PREFIX.

GUILT-half discriminator: `X-Auth-Type: public`, set by
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
from backend.app.auth.public_endpoints import find_entry

_APP = _main_api_module.app

#: The frozen contract's 401 envelope for every staff operation --
#: `products/garuda-voa/contracts/openapi.yaml` (`SESSION_REQUIRED`), served
#: by `hybrid_auth.contract_401_envelope()` before the handler runs.
_STAFF_401_ENVELOPE = {
    "code": "SESSION_REQUIRED",
    "retryable": False,
    "message_key": "garuda_voa.error.session_required",
}

#: The contract attaches these to that same 401 via its
#: `x-public-privacy-response-headers` anchor. Serving the body without them
#: would leave a shared cache eligible to store a refusal for an
#: authenticated surface.
_STAFF_401_PRIVACY_HEADERS = {
    "Cache-Control": "no-store, private",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}

# (case id, method, path, kwargs) -- every staff route on the shared
# `/api/visa/voa` root. `late-resolution` is L3's; the four `practices`
# routes are `garuda_staff_router.py`'s.
STAFF_REQUESTS: list[tuple[str, str, str, dict]] = [
    (
        "resolve_late_order",
        "POST",
        "/api/visa/voa/staff/orders/ord_abc123/late-resolution",
        {"json": {"resolution": "honoured", "staff_reference": "ref-1"}},
    ),
    ("list_staff_practices", "GET", "/api/visa/voa/staff/practices", {}),
    ("get_staff_practice", "GET", "/api/visa/voa/staff/practices/prc_abc123", {}),
    (
        "assign_practice",
        "POST",
        "/api/visa/voa/staff/practices/prc_abc123/assignment",
        {"json": {"assigned_to": None}},
    ),
    (
        "transition_practice",
        "POST",
        "/api/visa/voa/staff/practices/prc_abc123/transitions",
        {"json": {"transition_id": "PR-02"}},
    ),
]

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
@pytest.mark.parametrize(
    "case_id,method,path,kwargs",
    STAFF_REQUESTS,
    ids=[case[0] for case in STAFF_REQUESTS],
)
async def test_staff_route_is_never_public(case_id, method, path, kwargs):
    """The routes on this shared root that must stay behind the API-key/JWT
    gate. See the module docstring for why the body alone no longer
    discriminates and what replaced it."""
    transport = ASGITransport(app=_APP)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path, **kwargs)

    assert response.status_code == 401, (
        f"{case_id} ({method} {path}) answered {response.status_code} -- a "
        f"staff route must be refused by the auth gate"
    )
    assert response.headers.get("X-Auth-Type") != "public"
    assert response.headers.get("WWW-Authenticate") == "Bearer", (
        f"{case_id}: WWW-Authenticate is {response.headers.get('WWW-Authenticate')!r}, not "
        f"'Bearer' -- that header is set ONLY by "
        f"HybridAuthMiddleware's own 401 branch, so its absence means an "
        f"unauthenticated request reached the handler, i.e. a future edit "
        f"widened a public_endpoints.py entry into a prefix covering this "
        f"staff-only path"
    )
    assert response.json() == _STAFF_401_ENVELOPE, (
        f"{case_id}: the refusal must carry the frozen contract's 401 "
        f"envelope, got {response.json()!r}"
    )
    for name, value in _STAFF_401_PRIVACY_HEADERS.items():
        assert response.headers.get(name) == value, (
            f"{case_id}: {name} is {response.headers.get(name)!r}, not the {value!r} "
            f"the contract attaches to this response"
        )


@pytest.mark.parametrize(
    "case_id,_method,path,_kwargs",
    STAFF_REQUESTS,
    ids=[case[0] for case in STAFF_REQUESTS],
)
def test_staff_route_has_no_public_endpoints_entry(case_id, _method, path, _kwargs):
    """The structural half of the innocence proof: read the registry, not a
    symptom of it. `find_entry` is the same matcher
    `HybridAuthMiddleware.is_public_endpoint` uses, so a `None` here is the
    direct statement that no public entry -- exact, template or prefix --
    covers this staff path."""
    entry = find_entry(path)
    assert entry is None, (
        f"{case_id}: {path} is matched by public_endpoints entry "
        f"{entry.prefix!r} (match={entry.match!r}) -- a staff route must "
        f"never be public"
    )
