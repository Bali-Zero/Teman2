"""
Enforcement tests for the public_endpoints registry.

Two directions of drift are caught:

B1 — "No undocumented public route": HybridAuthMiddleware.is_public_endpoint
     must return True ONLY for paths that resolve to a registry entry (plus
     the infra-protected docs/metrics paths the middleware handles
     separately). A path that becomes public-by-mistake via some other
     code path will fail this test.

B2 — "No stale registry entry": every entry in PUBLIC_ENDPOINTS must
     resolve to at least one mounted FastAPI route. Entries that point to
     removed or renamed routers surface here so they can be cleaned up.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.app.auth.public_endpoints import PUBLIC_ENDPOINTS, find_entry, is_public_path
from backend.app.setup.route_walk import iter_leaf_routes


class TestRegistryInvariants:
    def test_registry_is_not_empty(self):
        assert len(PUBLIC_ENDPOINTS) > 0

    def test_no_duplicate_prefixes(self):
        prefixes = [e.prefix for e in PUBLIC_ENDPOINTS]
        assert len(prefixes) == len(set(prefixes)), "Duplicate public-endpoint prefixes"

    def test_every_entry_has_reason(self):
        for e in PUBLIC_ENDPOINTS:
            assert e.reason, f"Entry {e.prefix} has empty reason"
            assert len(e.reason) >= 10, f"Entry {e.prefix} reason too short"

    def test_exact_match_root_does_not_swallow_paths(self):
        """`/` is exact-match only — it must NOT make /foo, /api, etc. public."""
        assert is_public_path("/")
        assert is_public_path("")
        # Bare paths that happen to start with "/" must NOT be public via root.
        assert not is_public_path("/arbitrary/non-public/path/xyz")
        assert not is_public_path("/api/admin/secret")


class TestB1_NoUndocumentedPublicRoutes:
    """Middleware's public-endpoint check must agree with the registry."""

    @pytest.fixture
    def middleware(self):
        from backend.middleware.hybrid_auth import HybridAuthMiddleware

        # HybridAuthMiddleware doesn't need a live app for is_public_endpoint
        return HybridAuthMiddleware(MagicMock())

    def _mock_request(self, path: str):
        req = MagicMock()
        req.url.path = path
        # Force _is_protected_infra_endpoint to return False — we're testing
        # the registry path, not the docs/metrics side door.
        req.headers.get.return_value = None
        req.client.host = "127.0.0.1"
        return req

    def test_registry_entries_are_public(self, middleware):
        """Every registry entry's prefix must be recognized as public."""
        for entry in PUBLIC_ENDPOINTS:
            # Skip the empty-string sentinel — requests always carry at least "/"
            if entry.prefix == "":
                continue
            req = self._mock_request(entry.prefix)
            assert middleware.is_public_endpoint(req), (
                f"Registry entry {entry.prefix!r} ({entry.category.value}) "
                f"is not recognized as public by middleware"
            )

    def test_lead_capture_is_public(self, middleware):
        """Regression: /api/lead/capture missing from the registry meant every
        anonymous WhatsApp-CTA click got 401 in prod (silently masked by the
        component's bare-wa.me fallback). Pin it as public, exact-match."""
        req = self._mock_request("/api/lead/capture")
        assert middleware.is_public_endpoint(req)
        # Exact match must not open sibling paths.
        req = self._mock_request("/api/lead/capture/admin")
        assert not middleware.is_public_endpoint(req)

    def test_magic_link_endpoints_are_public(self, middleware):
        """Regression (FASE 6): the passwordless magic-link endpoints must be
        public. They were registered as routes but missing from this registry,
        so prod returned 401 to unauthenticated clients requesting a link —
        the feature was dead-on-arrival until added here."""
        # Request: exact match, must not open sibling paths.
        assert middleware.is_public_endpoint(
            self._mock_request("/api/auth/request-magic-link")
        )
        assert not middleware.is_public_endpoint(
            self._mock_request("/api/auth/request-magic-link/extra")
        )
        # Verify: prefix match (token is a path param).
        assert middleware.is_public_endpoint(
            self._mock_request("/api/auth/verify-magic/some-raw-token")
        )

    def test_crm_internal_document_upload_is_public_only_for_service_key_path(
        self, middleware
    ):
        """The WA Mirror headless delivery path bypasses JWT middleware but still
        enforces X-CRM-Write-Key in-router. Do not open sibling internal paths."""
        assert middleware.is_public_endpoint(
            self._mock_request("/api/crm/internal/clients/123/documents/upload")
        )
        assert not middleware.is_public_endpoint(
            self._mock_request("/api/crm/internal/clients/123/documents/delete")
        )
        assert not middleware.is_public_endpoint(
            self._mock_request("/api/crm/internal/clients/123/documents/upload/extra")
        )

    def test_non_registered_paths_require_auth(self, middleware):
        """A selection of sensitive paths must NOT be public."""
        sensitive = [
            "/api/admin/users",
            "/api/crm/clients",
            "/api/hr/payroll/run",
            "/api/practices/123/close",
            "/api/memory/save",
            "/api/export/clients.csv",
            "/api/agentic-rag/query",  # removed 2026-04-03 F-7 fix
            "/api/agentic-rag/stream",  # removed 2026-04-03 F-7 fix
        ]
        for path in sensitive:
            req = self._mock_request(path)
            assert not middleware.is_public_endpoint(req), (
                f"Sensitive path {path!r} must require auth but registry treats it as public"
            )


class TestB2_RegistryEntriesResolveToRoutes:
    """Every public prefix must correspond to at least one mounted route."""

    @pytest.fixture(scope="class")
    def mounted_paths(self) -> set[str]:
        """
        Collect all paths FastAPI has mounted by booting a FastAPI app and
        walking app.routes. Using the real app is necessary because some
        routers are included with a runtime-computed prefix (e.g.,
        API_V1_STR → /api/v1 for visa_oracle, kbli_notebook*), which the
        manifest alone does not expose.
        """
        from fastapi import FastAPI

        from backend.app.setup.router_registration import include_routers

        app = FastAPI()
        try:
            include_routers(app)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"include_routers failed in this env: {exc}")

        paths: set[str] = set()
        for route in iter_leaf_routes(app):
            route_path = getattr(route, "path", None)
            if route_path:
                paths.add(route_path)

        return paths

    def test_every_entry_resolves(self, mounted_paths: set[str]):
        if len(mounted_paths) == 0:
            pytest.skip("Could not collect any mounted routes — router imports failed in this env")

        # FastAPI mounts dynamic-segment routes with literal `{name}` in the
        # path string (e.g. `/api/channels/{name}/health`). Registry entries
        # are concrete paths (e.g. `/api/channels/whatsapp/health`). To resolve
        # a literal entry against a templated mounted path, build a set of
        # regex patterns from mounted_paths and check whether each entry
        # matches any of them. This was a pre-existing bug in the test
        # surfaced when Sprint 0 fixed the earlier blocker that made pytest
        # stop before reaching this case.
        import re

        compiled_mounts: list[re.Pattern[str]] = []
        for p in mounted_paths:
            # Replace `{anything}` with a non-empty path-segment match.
            pattern = re.sub(r"\{[^/}]+\}", r"[^/]+", p)
            compiled_mounts.append(re.compile(rf"^{pattern}(?:/.*)?$"))

        unresolved: list[str] = []
        for entry in PUBLIC_ENDPOINTS:
            if entry.prefix in ("", "/"):
                # Root sentinels aren't declared as app routes
                continue
            hit = any(
                p == entry.prefix or p.startswith(entry.prefix) or pat.match(entry.prefix)
                for p in mounted_paths
                for pat in compiled_mounts
            ) or any(pat.match(entry.prefix) for pat in compiled_mounts)
            if not hit:
                unresolved.append(entry.prefix)

        if unresolved:
            pytest.fail(
                "Registry entries with no mounted route — either the router "
                "was renamed/removed, or the entry is stale:\n  "
                + "\n  ".join(unresolved)
                + f"\n\nTotal mounted paths collected: {len(mounted_paths)}",
            )


class TestHelperFunctions:
    def test_find_entry_returns_matching_entry(self):
        entry = find_entry("/api/blog/posts/123")
        assert entry is not None
        assert entry.prefix == "/api/blog/"

    def test_find_entry_returns_none_for_unknown(self):
        assert find_entry("/api/nonexistent/route") is None

    def test_find_entry_exact_match(self):
        entry = find_entry("/")
        assert entry is not None
        assert entry.match == "exact"
        assert entry.prefix == "/"


class TestVisaCheckPublicRegistration:
    """Guilt+innocence for the /api/visa/* Visa Check v1 funnel.

    Regression (PR #108, 2026-04-25): routers/visa_check.py was mounted but
    never registered here, so HybridAuthMiddleware 401'd every anonymous
    call and the public funnel was dead in prod. The 5 routes must resolve
    as public via exact/template matches only — no blanket /api/visa/ prefix.
    """

    @pytest.fixture
    def middleware(self):
        from backend.middleware.hybrid_auth import HybridAuthMiddleware

        return HybridAuthMiddleware(MagicMock())

    def _mock_request(self, path: str, method: str = "GET"):
        req = MagicMock()
        req.url.path = path
        req.method = method
        req.headers.get.return_value = None
        req.client.host = "127.0.0.1"
        return req

    def test_visa_check_endpoints_are_public(self, middleware):
        """Guilt: all 5 visa_check routes resolve as public."""
        public_paths = [
            "/api/visa/check/start",
            "/api/visa/clock",
            "/api/visa/match",
            "/api/visa/clock/a1b2c3d4e5f6",
            "/api/visa/match/a1b2c3d4e5f6",
        ]
        for path in public_paths:
            assert middleware.is_public_endpoint(self._mock_request(path)), (
                f"Visa Check path {path!r} must be public"
            )

    def test_visa_check_entries_use_exact_or_template_match(self):
        """Entries must not be prefix matches — no blanket /api/visa/ opening."""
        for prefix, expected_match in (
            ("/api/visa/check/start", "exact"),
            ("/api/visa/clock", "exact"),
            ("/api/visa/match", "exact"),
            ("/api/visa/clock/{hash}", "template"),
            ("/api/visa/match/{hash}", "template"),
        ):
            entry = next(e for e in PUBLIC_ENDPOINTS if e.prefix == prefix)
            assert entry.match == expected_match
            assert entry.category.value == "visa_oracle"

    def test_visa_check_near_miss_paths_are_not_public(self, middleware):
        """Innocence: sibling/lookalike paths must still require auth."""
        not_public = [
            "/api/visaevil/match",  # near-miss prefix lookalike
            "/api/visa",  # bare root, not a route
            "/api/visa/",  # trailing-slash root, not a route
            "/api/visa/clockadmin",  # exact-match sibling of /api/visa/clock
            "/api/visa/match/abc/def",  # template is single-segment only
            "/api/visa/unknown",  # unregistered sibling under /api/visa/
        ]
        for path in not_public:
            assert not middleware.is_public_endpoint(self._mock_request(path)), (
                f"Path {path!r} must NOT be public"
            )

    def test_visa_check_rate_limit_class(self):
        """Anonymous visa_check traffic is rate-limited per-IP via the generic
        "/api/" bucket (120 req/min) — same class as /api/v1/visa-oracle/*."""
        from backend.middleware.rate_limiter import RateLimitMiddleware

        rl = RateLimitMiddleware(app=MagicMock())
        for path in (
            "/api/visa/check/start",
            "/api/visa/clock",
            "/api/visa/match",
            "/api/visa/clock/a1b2c3d4e5f6",
            "/api/visa/match/a1b2c3d4e5f6",
        ):
            assert rl._get_rate_limit(path) == (120, 60)

    @pytest.mark.asyncio
    async def test_anonymous_post_passes_dispatch_without_csrf(self, middleware):
        """CSRF posture: validate_csrf() is only invoked inside the cookie-JWT
        branch of authenticate_request, which dispatch() never reaches for
        registered-public paths (Step 1 short-circuit). An anonymous POST with
        no cookie and no X-CSRF-Token header must therefore pass the middleware.
        """
        from unittest.mock import AsyncMock

        req = self._mock_request("/api/visa/match", method="POST")
        req.headers = {}  # real dict: no cookies, no X-CSRF-Token, no user-agent
        req.cookies = {}
        response = MagicMock()
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(req, call_next)

        call_next.assert_awaited_once()
        assert result is response
        assert result.headers["X-Auth-Type"] == "public"
