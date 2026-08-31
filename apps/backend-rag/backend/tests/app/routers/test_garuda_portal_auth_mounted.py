"""Acceptance #5/#6 (products/garuda-voa/L4-CONTINUATION.md): the magic-link
router answers on the REAL mounted application, and the GARUDA_PUBLIC_ENABLED
flag is checked per-request rather than at mount time.

Follows `test_garuda_voa_openapi_parity.py`'s precedent for "real mounted
app" (module docstring there): importing `backend.app.main_api` builds the
actual `create_api_app()` object uvicorn serves in production, as a
module-scope side effect paid once per pytest worker. A bare `FastAPI()` +
`include_router(...)` (what `test_garuda_portal_auth.py` uses for its
fast, store-focused journey tests) would not prove reachability through the
real router-manifest + registration wiring this file exists to check.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

# Building `main_api.app` is the point — see module docstring above and
# `test_garuda_voa_openapi_parity.py`'s identical precedent/cost note.
from backend.app import main_api as _main_api_module
from backend.app.routers import garuda_portal_auth
from backend.services.garuda_portal.magic_link import IssueOutcome

VALID_RESULT_ID = "r" * 22
VALID_RESULT_SESSION = "s" * 43
VALID_IDEMPOTENCY_KEY = "test-key-mounted-0123456789"


class _AlwaysIssuesStore:
    async def issue(self, **kwargs):
        return IssueOutcome(idempotency_replayed=False)

    async def exchange(self, **kwargs):  # pragma: no cover - not exercised here
        raise NotImplementedError


class _AlwaysOwnsStore:
    """A `CheckStore` double that recognises every (result_id,
    session_secret) pair -- this file tests router MOUNTING/manifest
    wiring, not the ownership check itself (that is
    `test_garuda_portal_auth.py`'s job), so the ownership gate added
    2026-08-30 must be made a no-op here rather than left unwired (which
    would 503 every request via `UnconfiguredCheckStore`)."""

    async def get(self, *, result_id, session_secret):
        return object()


@pytest.fixture
def mounted_client(monkeypatch):
    """The real `main_api.app`, with only the store dependencies overridden
    (the seams `magic_link.py`/`garuda_flow.public_api`'s own docstrings
    name as the intended wiring points) -- routing, manifest registration,
    and every other dependency are the production ones.
    """
    app = _main_api_module.app
    app.dependency_overrides[garuda_portal_auth.get_garuda_magic_link_store] = (
        lambda: _AlwaysIssuesStore()
    )
    app.dependency_overrides[garuda_portal_auth.get_garuda_check_store] = (
        lambda: _AlwaysOwnsStore()
    )
    try:
        yield app
    finally:
        app.dependency_overrides.pop(garuda_portal_auth.get_garuda_magic_link_store, None)
        app.dependency_overrides.pop(garuda_portal_auth.get_garuda_check_store, None)


async def _post_magic_link(app, *, enabled: bool) -> int:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/visa/voa/auth/magic-links",
            json={"result_id": VALID_RESULT_ID, "email": "visitor@example.com"},
            headers={"Idempotency-Key": VALID_IDEMPOTENCY_KEY},
            cookies={"garuda_result_session": VALID_RESULT_SESSION},
        )
        return response.status_code


@pytest.mark.asyncio
async def test_router_is_reachable_through_the_real_mounted_app(mounted_client, monkeypatch):
    """Acceptance #5: a request through `main_api.app` -- built via the
    manifest + `router_registration.py` wiring this PR added -- reaches
    the router at all (not a bare FastAPI() built only in a test file).
    Before this PR's mount, `garuda_portal_auth` had no manifest entry and
    no `include_router` call anywhere main_api assembles from, so this
    exact request would 404 at the FastAPI routing layer (no matching
    route), not at the handler's own GARUDA_PUBLIC_DISABLED branch.
    """
    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    status = await _post_magic_link(mounted_client, enabled=True)
    assert status == 202, (
        "expected the mounted requestMagicLink handler to answer 202 -- "
        f"got {status}, which would mean the router never mounted (404) or "
        "some other regression"
    )


@pytest.mark.asyncio
async def test_flag_is_checked_per_request_not_at_mount(mounted_client, monkeypatch):
    """Acceptance #6: GARUDA_PUBLIC_ENABLED off/on is re-read on EVERY
    request by the handler itself (`_public_enabled()`), not baked in at
    mount time -- the router mounts unconditionally (no `condition=` on its
    RouterEntry, matching garuda_voa_public/garuda_orders_router), so
    toggling the env var between two requests against the SAME already-
    mounted app must change the outcome without remounting anything.
    """
    monkeypatch.delenv("GARUDA_PUBLIC_ENABLED", raising=False)
    disabled_status = await _post_magic_link(mounted_client, enabled=False)
    assert disabled_status == 404

    monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", "true")
    enabled_status = await _post_magic_link(mounted_client, enabled=True)
    assert enabled_status == 202
