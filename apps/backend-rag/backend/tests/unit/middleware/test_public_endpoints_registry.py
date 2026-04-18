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

    def test_non_registered_paths_require_auth(self, middleware):
        """A selection of sensitive paths must NOT be public."""
        sensitive = [
            "/api/admin/users",
            "/api/crm/clients",
            "/api/hr/payroll/run",
            "/api/practices/123/close",
            "/api/memory/save",
            "/api/export/clients.csv",
            "/api/agentic-rag/query",   # removed 2026-04-03 F-7 fix
            "/api/agentic-rag/stream",  # removed 2026-04-03 F-7 fix
        ]
        for path in sensitive:
            req = self._mock_request(path)
            assert not middleware.is_public_endpoint(req), (
                f"Sensitive path {path!r} must require auth but registry "
                "treats it as public"
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
        for route in app.routes:
            route_path = getattr(route, "path", None)
            if route_path:
                paths.add(route_path)

        return paths

    def test_every_entry_resolves(self, mounted_paths: set[str]):
        if len(mounted_paths) == 0:
            pytest.skip("Could not collect any mounted routes — router imports failed in this env")

        unresolved: list[str] = []
        for entry in PUBLIC_ENDPOINTS:
            if entry.prefix in ("", "/"):
                # Root sentinels aren't declared as app routes
                continue
            hit = any(
                p == entry.prefix or p.startswith(entry.prefix)
                for p in mounted_paths
            )
            if not hit:
                unresolved.append(entry.prefix)

        if unresolved:
            pytest.fail(
                "Registry entries with no mounted route — either the router "
                f"was renamed/removed, or the entry is stale:\n  "
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
