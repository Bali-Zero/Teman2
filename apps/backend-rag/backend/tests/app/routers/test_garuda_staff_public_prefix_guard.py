"""GARUDA VOA step 8 staff surface — round-2 disposition item D.

Two halves, same discipline as `test_garuda_voa_public_root_allowlist.py`
(that file's own module docstring is the precedent this one follows for
"a bare `FastAPI()` double would stay green even though production
returned 401" — see it for the fuller argument).

INNOCENCE half: `listStaffPractices` and `transitionPractice` — a
credential-less caller reaches `main_api.app` (the REAL mounted
application, middleware included) and must be rejected by
`HybridAuthMiddleware` ITSELF, never merely by this router's own
`require_garuda_staff` returning 401 further downstream.

The discriminator USED to be the body: the middleware's generic
`{"detail": "Authentication required"}`, never this router's own
`{"code": "SESSION_REQUIRED", ...}` contract envelope. That is retired as
of the W3C contract-closure PR — the middleware now serves exactly the
frozen contract's SESSION_REQUIRED envelope AND its three privacy headers
on `/api/visa/voa/staff/**` (`hybrid_auth.contract_401_envelope`, a
response-SHAPE change only: still 401, still refused before the handler,
still not public), because the kita client reads `code` and was seeing
`undefined`. What replaces it here:

  - `WWW-Authenticate: Bearer` — set ONLY by the middleware's own 401
    branch. No GARUDA router sets it, so its presence is the live proof
    that the refusal came from the gate and not from a handler that was
    allowed to run.
  - the GUILT half below, which was always the structural statement and is
    untouched by any of this.

`X-Auth-Type != "public"` is kept as a weaker third signal: the public
branch sets it on `call_next`'s response, so an `HTTPException` raised
inside a wrongly-public handler would skip it.

GUILT half (the registry itself, not a live request): no
`PublicEndpoint` entry anywhere in `public_endpoints.py` may use
`match="prefix"` (or the field's own default, when `match=` is omitted
entirely — `PublicEndpoint.match: str = "prefix"`, per that module's own
docstring) with a `prefix` that is `/api/visa/voa` itself or a leading
segment of `/api/visa/voa/staff/` — this is the class of edit
`public_endpoints.py`'s own inline comment at the GARUDA VOA auth block
already argues against for a DIFFERENT sub-path (`/api/visa/voa/auth/`);
this test makes the same argument enforceable for `/staff/` too, and for
any future GARUDA VOA entry, not only the ones that exist on disk today.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import main_api as _main_api_module
from backend.app.auth.public_endpoints import PUBLIC_ENDPOINTS

_APP = _main_api_module.app

#: `products/garuda-voa/contracts/openapi.yaml` — the 401 body every staff
#: operation declares, plus the three headers its
#: `x-public-privacy-response-headers` anchor attaches to that response.
_STAFF_401_BODY = {
    "code": "SESSION_REQUIRED",
    "retryable": False,
    "message_key": "garuda_voa.error.session_required",
}
_STAFF_401_PRIVACY_HEADERS = {
    "Cache-Control": "no-store, private",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}

_STAFF_REQUESTS: list[tuple[str, str, str, dict]] = [
    ("list_staff_practices", "GET", "/api/visa/voa/staff/practices", {}),
    (
        "get_staff_practice",
        "GET",
        "/api/visa/voa/staff/practices/prac_abc123",
        {},
    ),
    (
        "assign_practice",
        "POST",
        "/api/visa/voa/staff/practices/prac_abc123/assignment",
        {"json": {"assigned_to": None}},
    ),
    (
        "transition_practice",
        "POST",
        "/api/visa/voa/staff/practices/prac_abc123/transitions",
        {"json": {"transition_id": "PR-02"}},
    ),
]


@pytest.fixture(autouse=True)
def _garuda_public_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id,method,path,kwargs", _STAFF_REQUESTS, ids=[case[0] for case in _STAFF_REQUESTS]
)
async def test_staff_route_without_credential_is_rejected_by_middleware(
    case_id, method, path, kwargs
):
    transport = ASGITransport(app=_APP)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path, **kwargs)
    assert response.status_code == 401, (
        f"{case_id} ({method} {path}) returned {response.status_code}, not 401 -- expected "
        f"the credential-less caller to be rejected."
    )
    assert response.headers.get("X-Auth-Type") != "public", (
        f"{case_id} ({method} {path}) took HybridAuthMiddleware's public-endpoint branch -- "
        f"a public_endpoints.py entry now covers a GARUDA VOA staff path."
    )
    assert response.headers.get("WWW-Authenticate") == "Bearer", (
        f"{case_id} ({method} {path}) carries WWW-Authenticate "
        f"{response.headers.get('WWW-Authenticate')!r}, not 'Bearer' -- that header is set "
        f"ONLY by HybridAuthMiddleware's own 401 branch, so anything else means the request "
        f"reached the handler, i.e. the request WAS authenticated (or the middleware let it "
        f"through some other way) before this router's own check ran."
    )
    assert response.json() == _STAFF_401_BODY, (
        f"{case_id} ({method} {path}) was refused with {response.json()!r}, not the frozen "
        f"contract's 401 envelope."
    )
    for name, value in _STAFF_401_PRIVACY_HEADERS.items():
        assert response.headers.get(name) == value, (
            f"{case_id} ({method} {path}): {name} is {response.headers.get(name)!r}, not the "
            f"{value!r} the contract attaches to this response -- serving the contract's body "
            f"without its Cache-Control would let a shared cache store a refusal for an "
            f"authenticated surface."
        )


@pytest.mark.asyncio
async def test_customer_magic_link_cookie_alone_is_rejected_by_middleware() -> None:
    """A customer's `garuda_session` magic-link cookie is a different
    cookie NAME than `cookie_auth.JWT_COOKIE_NAME`
    (`garuda_portal_auth.py`'s own module docstring) -- HybridAuthMiddleware
    never decodes it into `request.state.user`, so it must be rejected the
    SAME way a bare credential-less request is, never treated as a staff
    session."""

    transport = ASGITransport(app=_APP)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/visa/voa/staff/practices",
            cookies={"garuda_session": "customer-session-value"},
        )
    assert response.status_code == 401
    assert response.headers.get("X-Auth-Type") != "public"


def test_no_garuda_voa_public_endpoint_uses_a_prefix_match_covering_staff():
    """Registry-level guilt/innocence, not a live request: censuses every
    `PublicEndpoint` whose `prefix` mentions the GARUDA VOA root, and fails
    if any of them resolves to `match == "prefix"` (explicit or via the
    dataclass default) rather than `"exact"`/`"template"`."""

    voa_root = "/api/visa/voa"
    offenders = [
        entry
        for entry in PUBLIC_ENDPOINTS
        if entry.prefix.startswith(voa_root) and entry.match == "prefix"
    ]
    assert offenders == [], (
        "found a prefix-matched public_endpoints.py entry under the GARUDA VOA root -- this "
        "would make HybridAuthMiddleware treat any path starting with that prefix as "
        f"anonymous, including /staff/ routes: {[e.prefix for e in offenders]}"
    )

    # Innocence: the census itself must be non-trivial (at least the
    # eligibility-checks/orders/webhooks/auth entries this repo already
    # carries) -- an empty `offenders` list from a query that also matches
    # nothing at all would pass for the wrong reason.
    voa_entries = [entry for entry in PUBLIC_ENDPOINTS if entry.prefix.startswith(voa_root)]
    assert len(voa_entries) >= 6, (
        f"expected several GARUDA VOA public_endpoints.py entries (eligibility-checks, "
        f"orders x3, webhooks, auth x2) -- found {len(voa_entries)}: is `voa_root` matching "
        f"the wrong prefix, or did entries move?"
    )
