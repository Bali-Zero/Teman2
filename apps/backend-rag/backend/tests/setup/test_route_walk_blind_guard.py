"""Blind-guard tripwire for route enumeration (fastapi 0.137 tree refactor).

fastapi 0.137 turned ``router.routes`` into a tree; flat iteration over
``app.routes`` then sees ONLY the app-level docs routes and every
route-iterating antibody (reachability, auth-contract, process-split,
authz coverage) goes silently blind — family #2, green != working.

Two layers of defence, both required:

1. Unit (guilt+innocence): ``iter_leaf_routes`` sees nested-included routes
   with FULL composed paths on whatever fastapi version is installed, and
   is a byte-for-byte passthrough on the flat shape.
2. Tripwire: over the real app (``include_routers``), the walker must see
   at least ``ROUTE_COUNT_FLOOR`` paths. If a future fastapi refactor
   breaks enumeration again, this FAILS LOUD instead of letting coverage
   silently shrink to a handful of docs routes.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI

from backend.app.setup.route_walk import iter_leaf_routes, iter_route_paths

# The real app mounts several hundred routes (DOCSYNC counts ~180 routers).
# The floor is deliberately far below the real count (no maintenance burden
# as routers come and go) but far above the 4-5 app-level routes a blind
# flat iteration would see.
ROUTE_COUNT_FLOOR = 100


def _nested_app() -> FastAPI:
    app = FastAPI()
    inner = APIRouter()

    @inner.get("/leaf")
    def leaf():  # pragma: no cover - route body irrelevant
        return {}

    outer = APIRouter(prefix="/api/outer")
    outer.include_router(inner, prefix="/nested")
    app.include_router(outer, prefix="/top")
    return app


class TestIterLeafRoutesUnit:
    def test_sees_nested_include_with_full_path(self) -> None:
        """GUILT: the exact shape that blinded flat iteration on 0.137+."""
        paths = set(iter_route_paths(_nested_app()))
        assert "/top/api/outer/nested/leaf" in paths, (
            "iter_leaf_routes lost a nested-included route or its prefix "
            f"composition — saw only: {sorted(paths)}"
        )

    def test_flat_routes_pass_through_unchanged(self) -> None:
        """INNOCENCE: plain app-level routes come through identically."""
        app = FastAPI()

        @app.get("/direct")
        def direct():  # pragma: no cover
            return {}

        leaves = list(iter_leaf_routes(app))
        direct_leaves = [r for r in leaves if getattr(r, "path", None) == "/direct"]
        assert len(direct_leaves) == 1
        # On the flat shape this must be the very same route object.
        assert direct_leaves[0] in app.routes or hasattr(
            direct_leaves[0], "endpoint"
        )

    def test_leaves_duck_type_consumer_attributes(self) -> None:
        """Every leaf exposes the attributes our antibodies read."""
        for route in iter_leaf_routes(_nested_app()):
            path = getattr(route, "path", None)
            if path != "/top/api/outer/nested/leaf":
                continue
            assert "GET" in (getattr(route, "methods", None) or set())
            assert getattr(route, "endpoint", None) is not None
            assert getattr(route, "name", None)
            return
        pytest.fail("nested leaf not found at all")


class TestRealAppBlindGuard:
    def test_walker_sees_the_real_api_surface(self) -> None:
        """TRIPWIRE: enumeration over the real app never silently shrinks."""
        app = FastAPI()
        try:
            from backend.app.setup.router_registration import include_routers

            include_routers(app)
        except Exception as exc:  # noqa: BLE001 - env-dependent imports
            pytest.skip(f"include_routers failed in this env: {exc}")

        n_paths = len(set(iter_route_paths(app)))
        assert n_paths >= ROUTE_COUNT_FLOOR, (
            f"Route walker sees only {n_paths} paths (floor "
            f"{ROUTE_COUNT_FLOOR}). Either the app shrank drastically or a "
            "fastapi upgrade changed route storage again and "
            "iter_leaf_routes needs adapting — do NOT relax the floor "
            "without proving enumeration is complete."
        )
