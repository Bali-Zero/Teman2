"""GARUDA VOA step 8 — the staff prefix through the REAL deployed app.

`test_staff_router_transitions.py` proves `garuda_staff_router.py`'s OWN
auth logic (`require_garuda_staff`/`_require_actor`) rejects a
credential-less caller with 401 SESSION_REQUIRED, but it does that against
a bare router mounted on a throwaway `FastAPI()` -- it never runs through
`HybridAuthMiddleware`, which is what actually decides, on the real
deployed app, whether a request reaches the router's own auth at all.

Cross-family refuter finding #7 (`step8-refute-findings.md`): the default
`public_endpoints.py` matcher is `startswith` (prefix), and the only test
covering that registry against GARUDA VOA paths
(`test_garuda_voa_public_root_allowlist.py`) predates this router -- it
never exercised `/api/visa/voa/staff/**`.

Team-lead's disposition (2026-09-02, this round): a credential-less
request is answered by `HybridAuthMiddleware`'s own GENERIC 401 -- accept
that. This file asserts status 401 and the ABSENCE of `X-Auth-Type: public`
(the header `HybridAuthMiddleware` sets ONLY on a request it treated as
public), nothing about the response body -- the contract's own
`SESSION_REQUIRED` envelope is `garuda_staff_router.py`'s to produce for a
PRESENT-but-ineligible credential (covered by
`test_staff_router_transitions.py::test_no_credential_is_401_session_required`
against the bare router), and asserting that shape here too would just
re-test the same router logic through a slower fixture for no new
coverage.

Builds `main_api.app` the same way `test_garuda_voa_openapi_parity.py`
does and for the same reason (see that file's own docstring): a bare
`include_router` would never run through the real middleware stack this
file exists to prove something about. `pytest.importorskip` is forbidden
here for the same reason it is forbidden there.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import main_api as _main_api_module
from backend.app.auth.public_endpoints import PUBLIC_ENDPOINTS, find_entry

_STAFF_PREFIX = "/api/visa/voa/staff/"


def test_no_public_endpoints_entry_covers_the_staff_prefix() -> None:
    """Guilt+innocence anchor for the registry itself: a NEW blanket
    `/api/visa/voa/` (or `/api/visa/voa/staff/`) prefix entry -- the exact
    shape `garuda_orders_router.py`'s own public_endpoints.py comment block
    already rejected once for its sibling staff route
    (`/staff/orders/{order_id}/late-resolution`) -- would silently make
    every staff practice route public. `find_entry` is the SAME function
    `HybridAuthMiddleware.is_public_endpoint` calls in production, so this
    checks the real decision path, not a re-derivation of it.
    """

    probe_paths = (
        "/api/visa/voa/staff/practices",
        "/api/visa/voa/staff/practices/prc_test000000000001",
        "/api/visa/voa/staff/practices/prc_test000000000001/assignment",
        "/api/visa/voa/staff/practices/prc_test000000000001/transitions",
    )
    for path in probe_paths:
        entry = find_entry(path)
        assert entry is None, (
            f"{path} matches a PUBLIC_ENDPOINTS entry ({entry}) -- a staff-only "
            "GARUDA VOA route must never be reachable without a credential"
        )


def test_no_registered_prefix_entry_starts_with_the_staff_root() -> None:
    """A second, narrower guilt anchor at the REGISTRY level (not just the
    matcher's verdict on today's four paths above): no entry in
    `PUBLIC_ENDPOINTS` may itself be a prefix of `/api/visa/voa/staff/` --
    that shape would cover every CURRENT and every FUTURE staff route
    without needing today's four paths to be re-enumerated here."""

    for entry in PUBLIC_ENDPOINTS:
        if entry.match == "prefix":
            assert not _STAFF_PREFIX.startswith(entry.prefix), (
                f"PUBLIC_ENDPOINTS entry {entry.prefix!r} ({entry.reason}) is a "
                f"prefix of {_STAFF_PREFIX!r} -- it would make the entire staff "
                "surface public"
            )


def _client() -> TestClient:
    return TestClient(_main_api_module.app, raise_server_exceptions=False)


def test_no_credential_get_practices_is_401_not_public() -> None:
    resp = _client().get("/api/visa/voa/staff/practices")
    assert resp.status_code == 401
    assert resp.headers.get("X-Auth-Type") != "public"


def test_no_credential_get_one_practice_is_401_not_public() -> None:
    resp = _client().get("/api/visa/voa/staff/practices/prc_test000000000001")
    assert resp.status_code == 401
    assert resp.headers.get("X-Auth-Type") != "public"


def test_no_credential_post_assignment_is_401_not_public() -> None:
    resp = _client().post(
        "/api/visa/voa/staff/practices/prc_test000000000001/assignment",
        json={"assigned_to": None},
    )
    assert resp.status_code == 401
    assert resp.headers.get("X-Auth-Type") != "public"


def test_no_credential_post_transition_is_401_not_public() -> None:
    resp = _client().post(
        "/api/visa/voa/staff/practices/prc_test000000000001/transitions",
        json={"transition_id": "PR-02"},
    )
    assert resp.status_code == 401
    assert resp.headers.get("X-Auth-Type") != "public"


def test_customer_magic_link_cookie_alone_is_401_not_public() -> None:
    """A customer's `garuda_session` magic-link cookie is not a CRM cookie
    session (`HybridAuthMiddleware` decodes `nz_access_token`, a different
    cookie name entirely) -- it must not be read as one, and it must not be
    treated as a public-endpoint bypass either."""

    resp = _client().get(
        "/api/visa/voa/staff/practices",
        cookies={"garuda_session": "customer-session-value"},
    )
    assert resp.status_code == 401
    assert resp.headers.get("X-Auth-Type") != "public"
