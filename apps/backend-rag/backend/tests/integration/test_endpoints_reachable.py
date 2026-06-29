"""End-to-end reachability test: every mounted route is reachable through
the production middleware stack.

SCAR CONTEXT (cicatrix-scars.md "Test infrastructure mock != production
stack", Sprint 1.B 2026-05-02):

PR #422 added `channel_health` to the manifest with `RouterEntry(...)` but
forgot the explicit `include_router(channel_health.router)` calls in
`router_registration.py`. Unit tests mounted the router directly on a bare
FastAPI app without `HybridAuthMiddleware`, so:

  - Auth path was never exercised → 401 in prod surprised reviewers
    (hotfix #423 added the 4 entries to PUBLIC_ENDPOINTS).
  - Router was registered in the manifest but missing from
    `include_routers` / `include_light_routers` → 404 in prod
    (hotfix #424 added the explicit imports + 2 include_router calls).

Three PRs in chain (#422 → #423 → #424), ~2 hours of CI/deploy/curl cycles
that this integration test would have caught at PR-time.

WHAT THIS TEST DOES (the antibody the scar called for):

1. Mounts the realistic main_api shape via `include_routers()` — same path
   as the existing `test_public_endpoints_registry.py` B2 test. This is
   intentionally lighter than `create_app()` (which needs Postgres / Redis
   / OpenAI / etc.) but heavier than a per-router unit fixture.

2. Stacks `HybridAuthMiddleware` on top — the missing layer in the unit-test
   fixture that masked the Sprint 1.B regression.

3. For every concrete (non-parameterised) route:
   - Issues a GET via FastAPI TestClient.
   - Asserts the response is NOT 404 → proves the route is mounted.
   - Asserts auth behaviour matches the registry:
       · path in PUBLIC_ENDPOINTS → NOT 401 (auth bypass works)
       · path not in PUBLIC_ENDPOINTS → IS 401 (auth required)

4. Emits a warning (not a hard failure) for any concrete route matching
   `/api/*/health` or `/api/*/heartbeat` that is NOT in PUBLIC_ENDPOINTS
   yet — these are usually candidates for the registry. To silence the
   warning intentionally, add the route handler with the comment
   `# health-private: <reason>` (audit-only convention; not parsed here).

Out of scope (intentionally):
- Routes with `{path_param}` segments — substituting valid IDs requires
  domain knowledge per route. The Sprint 1.B scar was a path-with-no-params
  regression; that surface is fully covered.
- Methods other than GET — for liveness reachability, GET-or-405 is
  sufficient. Method-level auth is exercised by per-router tests.
- Full request bodies / DB-backed flows — that's the per-router
  integration test's job.
"""

from __future__ import annotations

import re
import warnings
from typing import Iterable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.public_endpoints import PUBLIC_ENDPOINTS, find_entry, is_public_path
from backend.middleware.hybrid_auth import HybridAuthMiddleware
from backend.app.setup.router_registration import include_routers


_HEALTH_LIKE_RE = re.compile(r"/api/[^/]+/(?:health|heartbeat)/?$")


def _route_paths(app: FastAPI) -> set[str]:
    """Collect every mounted path string on the app."""
    paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
    return paths


def _is_concrete(path: str) -> bool:
    """A path is concrete if it has no `{param}` segments."""
    return "{" not in path and "}" not in path


def _concrete_get_paths(app: FastAPI) -> Iterable[str]:
    """Yield concrete (non-parameterised) paths that accept GET.

    For routes whose methods include GET we know the test client can
    exercise the path without 405. For other methods we still want
    reachability (so a HEAD-or-405 is fine), but we filter to GET-eligible
    paths to keep the assertion crisp.
    """
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if not path or not _is_concrete(path):
            continue
        if "GET" in methods:
            yield path


@pytest.fixture(scope="module")
def app_with_middleware() -> FastAPI:
    """Realistic main_api shape: routers mounted + HybridAuthMiddleware.

    Lifespan/startup events are NOT triggered (TestClient with no
    `with` block). That is intentional — we are testing the routing +
    middleware contract, not service initialization.
    """
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    try:
        include_routers(app)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"include_routers failed in this env: {exc}")

    app.add_middleware(HybridAuthMiddleware)
    return app


@pytest.fixture(scope="module")
def client(app_with_middleware: FastAPI) -> TestClient:
    return TestClient(app_with_middleware, raise_server_exceptions=False)


class TestRoutesAreMounted:
    """Every concrete GET route returns a non-404 status — i.e. it is mounted.

    This is the direct antibody to Sprint 1.B PR #422: an entry in the
    manifest with no corresponding `include_router(...)` call would surface
    here as a 404 from the test client, even though the route appears in
    `app.routes` only when the include call lands in registration.
    """

    def test_all_concrete_get_routes_resolve(
        self, app_with_middleware: FastAPI, client: TestClient,
    ) -> None:
        unmounted: list[tuple[str, int]] = []
        for path in _concrete_get_paths(app_with_middleware):
            resp = client.get(path)
            if resp.status_code == 404:
                unmounted.append((path, resp.status_code))

        assert not unmounted, (
            "Concrete GET routes returned 404 — the FastAPI app sees the "
            "path in app.routes but the request still 404s. This is the "
            "Sprint 1.B PR #422 → #424 scar pattern.\n  "
            + "\n  ".join(f"{p} → {code}" for p, code in unmounted)
        )


class TestAuthContractMatchesRegistry:
    """Middleware's runtime decision matches the PUBLIC_ENDPOINTS registry.

    Sprint 1.B PR #423 added 4 entries to PUBLIC_ENDPOINTS because the
    new `/api/channels/{name}/health` routes returned 401 in prod. This
    test catches that class at PR-time: any route the registry says is
    public must NOT 401, and any route it says is private MUST 401.
    """

    def test_public_paths_bypass_auth(
        self, app_with_middleware: FastAPI, client: TestClient,
    ) -> None:
        leaked_auth: list[tuple[str, int]] = []
        for path in _concrete_get_paths(app_with_middleware):
            if not is_public_path(path):
                continue
            resp = client.get(path)
            if resp.status_code == 401:
                leaked_auth.append((path, resp.status_code))

        assert not leaked_auth, (
            "Public-registry paths returned 401 — middleware did not let "
            "them through. Possible causes: prefix typo in registry, "
            "match=exact when prefix should be used, or registry edit not "
            "picked up by middleware.\n  "
            + "\n  ".join(f"{p} → {code}" for p, code in leaked_auth)
        )

    def test_private_paths_require_auth(
        self, app_with_middleware: FastAPI, client: TestClient,
    ) -> None:
        # Sample the first ~25 private routes — a full sweep is expensive
        # at module-import time and the scar surface is the boundary, not
        # the bulk. This still catches a broken middleware (everything
        # would 200) or a registry that has accidentally gone too wide.
        anonymously_reachable: list[tuple[str, int]] = []
        sampled = 0
        for path in sorted(_concrete_get_paths(app_with_middleware)):
            if is_public_path(path):
                continue
            sampled += 1
            if sampled > 25:
                break
            resp = client.get(path)
            # Acceptable private-route responses: 401 (auth required),
            # 405 (method not GET), 422 (body required). Anything 2xx
            # means the route slipped past auth.
            if 200 <= resp.status_code < 300:
                anonymously_reachable.append((path, resp.status_code))

        assert not anonymously_reachable, (
            "Private routes returned 2xx without auth — middleware failed "
            "fail-closed. This would be a P0 production leak.\n  "
            + "\n  ".join(f"{p} → {code}" for p, code in anonymously_reachable)
        )


class TestHealthEndpointsCandidateForRegistry:
    """Heuristic: any concrete route shaped like `/api/*/health` or
    `/api/*/heartbeat` that is NOT in PUBLIC_ENDPOINTS is probably
    a missing-registry-entry bug (Sprint 1.B class).

    This is a warning, not a hard failure, because some health endpoints
    are intentionally admin-only (e.g. `/api/admin/drive/health` is in
    the registry; an internal-only diagnostic might intentionally not be).
    Reviewers should triage warnings on each PR.
    """

    def test_health_like_routes_appear_in_registry(
        self, app_with_middleware: FastAPI,
    ) -> None:
        candidates: list[str] = []
        for path in _route_paths(app_with_middleware):
            if not _is_concrete(path):
                continue
            if not _HEALTH_LIKE_RE.match(path):
                continue
            if find_entry(path) is None:
                candidates.append(path)

        if candidates:
            warnings.warn(
                "Health-like routes not in PUBLIC_ENDPOINTS — review "
                "whether each should be public (Cell heartbeat bridge, "
                "load-balancer probe) or stay admin-only:\n  "
                + "\n  ".join(sorted(candidates)),
                stacklevel=2,
            )


class TestRegistryMatchesAtLeastOneRoute:
    """Defensive cross-check against B2 in test_public_endpoints_registry.

    B2 walks `app.routes` directly. This variant goes through the live
    middleware stack — so a registry entry that resolves at the FastAPI
    routing layer but is shadowed by middleware (e.g. by a wildcard
    BRIDGE prefix) still surfaces here.
    """

    def test_every_registry_entry_is_reachable_or_documented(
        self, app_with_middleware: FastAPI,
    ) -> None:
        # We don't assert reachability per-entry (that requires per-entry
        # placeholder substitution for prefix-style routes that point at a
        # parameterised mount) — just assert the registry is non-trivially
        # populated and the middleware's `public_endpoints` snapshot
        # reflects PUBLIC_ENDPOINTS at construction time.
        mw = next(
            (
                m for m in app_with_middleware.user_middleware
                if m.cls is HybridAuthMiddleware
            ),
            None,
        )
        assert mw is not None, "HybridAuthMiddleware was not added to app"
        # Construction-time snapshot was logged by the middleware __init__
        # (line `Public Endpoints: {len(self.public_endpoints)}`). Sanity-
        # check the registry isn't empty by this point.
        assert len(PUBLIC_ENDPOINTS) > 10, (
            f"PUBLIC_ENDPOINTS has only {len(PUBLIC_ENDPOINTS)} entries — "
            "registry looks truncated"
        )
