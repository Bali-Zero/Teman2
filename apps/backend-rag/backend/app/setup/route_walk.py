"""Version-agnostic route enumeration for FastAPI apps and routers.

fastapi 0.137.0 refactored ``router.routes`` from a flat list of
``APIRoute`` objects into a TREE: ``include_router`` now inserts opaque
``_IncludedRouter`` nodes (no ``.path``, no ``.routes``) whose children are
only reachable via ``effective_route_contexts()``. Any code that iterates
``app.routes`` directly sees ONLY the app-level routes (the 4 docs routes,
in practice) and goes silently blind — proven empirically on group PR
#2337, where the reachability/auth-contract antibodies stopped seeing the
API surface.

``iter_leaf_routes`` is the single sanctioned walker: it yields every
concrete route-like object with a FULL composed path, on both the flat
(<=0.136) and the tree (>=0.137) shapes. The yielded objects duck-type the
attributes our consumers read (``path``, ``methods``, ``name``,
``endpoint``, ``include_in_schema``, ``tags``); on >=0.137 the tree leaves
are ``_EffectiveRouteContext`` objects, which carry all of them with the
prefix-composed path (verified: nested include_router prefixes compose).

The blind-guard tripwire in
``backend/tests/setup/test_route_walk_blind_guard.py`` asserts a route-count
floor over the real app so a future fastapi refactor that breaks
enumeration again FAILS LOUD instead of silently shrinking coverage.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def iter_leaf_routes(app_or_router: Any) -> Iterator[Any]:
    """Yield every concrete route reachable from an app or router.

    Traverses fastapi>=0.137 ``_IncludedRouter`` tree nodes via their
    ``effective_route_contexts()`` accessor (leaves carry full composed
    paths); passes classic ``Route``/``APIRoute``/``Mount`` objects through
    unchanged, so behaviour on fastapi<=0.136 is byte-for-byte the old flat
    iteration.
    """
    routes = getattr(app_or_router, "routes", None)
    if routes is None:
        routes = app_or_router
    for route in routes:
        ctx_fn = getattr(route, "effective_route_contexts", None)
        # Expand ONLY genuine tree nodes: _IncludedRouter has the contexts
        # accessor and NO .path. Anything with a .path (real routes, Mount,
        # test doubles/Mocks) passes through as a leaf unchanged.
        if callable(ctx_fn) and not hasattr(route, "path"):
            yield from ctx_fn()
        else:
            yield route


def iter_route_paths(app_or_router: Any) -> Iterator[str]:
    """Yield the path string of every leaf route that has one."""
    for route in iter_leaf_routes(app_or_router):
        path = getattr(route, "path", None)
        if path:
            yield path
