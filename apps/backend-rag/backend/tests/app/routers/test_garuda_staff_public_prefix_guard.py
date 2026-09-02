"""GARUDA VOA step 8 staff surface — round-2 disposition item D.

Two halves, same discipline as `test_garuda_voa_public_root_allowlist.py`
(that file's own module docstring is the precedent this one follows for
"a bare `FastAPI()` double would stay green even though production
returned 401" — see it for the fuller argument).

INNOCENCE half: `listStaffPractices` and `transitionPractice` — a
credential-less caller reaches `main_api.app` (the REAL mounted
application, middleware included) and must be rejected by
`HybridAuthMiddleware` ITSELF, never merely by this router's own
`require_garuda_staff` returning 401 further downstream. The
discriminator is the middleware's own failure shape (`X-Auth-Type` never
`"public"`, and the JSON body is the middleware's generic
`{"detail": "Authentication required"}`, never this router's own
`{"code": "SESSION_REQUIRED", ...}` contract envelope) — a body shaped
like the router's own error would mean the request reached the handler,
i.e. a future `public_endpoints.py` edit already widened a prefix over
`/staff/` without this test catching it structurally.

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

_STAFF_REQUESTS: list[tuple[str, str, str, dict]] = [
    ("list_staff_practices", "GET", "/api/visa/voa/staff/practices", {}),
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
    assert response.json() == {"detail": "Authentication required"}, (
        f"{case_id} ({method} {path}) was rejected with a body shaped like this router's OWN "
        f"SESSION_REQUIRED contract envelope, not the middleware's generic failure -- that "
        f"means the request reached the handler, i.e. the request WAS authenticated (or the "
        f"middleware let it through some other way) before this router's own check ran."
    )


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
