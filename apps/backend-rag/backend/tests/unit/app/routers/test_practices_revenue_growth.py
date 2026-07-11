"""
Tests for GET /api/crm/practices/stats/revenue-growth.

SCAR CONTEXT: The frontend (crm.api.ts::getRevenueGrowth, useDashboardStats)
calls /api/crm/practices/stats/revenue-growth inside a Promise.all with NO
catch. The backend had no such route → 404 → the whole Promise.all rejected →
the entire dashboard stats block (Header.tsx, NotificationBell.tsx, every
workspace page) died. This test locks the contract the FE + crm.api.test.ts
already assert.

Two axes:
  - guilt:    the route exists and returns the FE-expected shape
  - innocence: the SQL derives month placeholders from params length, so admin
              (no RBAC filter) and team-member (RBAC filter) both bind cleanly
              (no IndeterminateDatatypeError — same class as PR #2142).
"""

from __future__ import annotations

import ast
from pathlib import Path

ROUTER_PATH = (
    Path(__file__).resolve().parents[5]
    / "backend"
    / "app"
    / "routers"
    / "crm_practices.py"
)


def _route_source() -> str:
    """The source of the revenue-growth handler, isolated."""
    src = ROUTER_PATH.read_text(encoding="utf-8")
    assert '"/stats/revenue-growth"' in src, (
        "Route /stats/revenue-growth is MISSING — the FE getRevenueGrowth() "
        "call 404s and rejects the dashboard Promise.all."
    )
    return src


def _revenue_growth_func() -> ast.FunctionDef:
    tree = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and any(
            isinstance(d, ast.Call)
            and any(
                isinstance(a, ast.Constant) and a.value == "/stats/revenue-growth"
                for a in d.args
            )
            for d in node.decorator_list
        ):
            return node
    raise AssertionError("revenue-growth async handler not found")


def test_route_exists() -> None:
    """GUILT: the route is registered on the practices router."""
    _route_source()


def test_returns_fe_contract_keys() -> None:
    """GUILT: the handler returns the exact keys crm.api.test.ts asserts."""
    func = _revenue_growth_func()
    src = ast.get_source_segment(ROUTER_PATH.read_text(encoding="utf-8"), func) or ""
    for key in (
        "current_month",
        "previous_month",
        "growth_percentage",
        "monthly_breakdown",
    ):
        assert key in src, f"revenue-growth response missing FE-contract key: {key}"


def test_no_hardcoded_date_placeholder_after_optional_filter() -> None:
    """INNOCENCE (PR #2142 class): no `>= $2`/`< $3` hardcoded after an
    optional RBAC filter — placeholders must be derived from params length so
    the admin path (empty params) binds without IndeterminateDatatypeError."""
    import re

    func = _revenue_growth_func()
    src = ast.get_source_segment(ROUTER_PATH.read_text(encoding="utf-8"), func) or ""
    hardcoded = re.findall(r"created_at\s*[<>]=?\s*\$[23]\b", src)
    assert not hardcoded, (
        f"Hardcoded $2/$3 date placeholder after optional RBAC filter "
        f"(PR #2142 regression class): {hardcoded}"
    )


def test_date_placeholder_index_is_derived_from_params_length() -> None:
    """INNOCENCE: placeholder indices come from len(params), not literals."""
    import re

    func = _revenue_growth_func()
    src = ast.get_source_segment(ROUTER_PATH.read_text(encoding="utf-8"), func) or ""
    assert re.search(r"len\(\w*params\)\s*\+\s*1", src), (
        "Expected a params-derived placeholder index (len(params) + 1) so the "
        "admin (no-filter) and team-member (filter) paths both bind cleanly."
    )
