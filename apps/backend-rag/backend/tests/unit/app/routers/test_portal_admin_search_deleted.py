"""
Tests for portal_admin.search_clients — soft-deleted client exclusion.

SCAR CONTEXT (found via live prod E2E sweep, 2026-07-08):
The superuser impersonation picker (/api/portal/admin/clients/search) did NOT
filter `deleted_at IS NULL`. The DB holds 10,221 soft-deleted clients vs 1,683
live; with `ORDER BY updated_at DESC` the recently-deleted ones sorted to the
TOP of the picker. An admin selecting a soft-deleted client then hit:
  - 500 on /portal/visa and /portal/company — the dashboard mixin filters
    `deleted_at IS NULL`, raises "Client N not found", and the router swallows
    the ValueError into a generic 500.
  - a DATA LEAK on /portal/dashboard/summary, /matters, /taxes — those do NOT
    filter deleted_at, so they return the soft-deleted client's data.

Fixing the SOURCE (the search query) removes both symptoms: the admin never
sees a deleted client to impersonate.

Static source-analysis test (no DB fixture needed): both SQL branches of
search_clients MUST constrain `deleted_at IS NULL`.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROUTER_PATH = (
    Path(__file__).resolve().parents[5]
    / "backend"
    / "app"
    / "routers"
    / "portal_admin.py"
)


def _search_func_source() -> str:
    tree = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "search_clients":
            src = ast.get_source_segment(
                ROUTER_PATH.read_text(encoding="utf-8"), node
            )
            assert src, "could not extract search_clients source"
            return src
    raise AssertionError("search_clients handler not found")


def test_both_sql_branches_exclude_soft_deleted() -> None:
    """GUILT: every `FROM clients` SELECT in the picker filters deleted_at.

    The handler has two query branches (with query_text / without). BOTH must
    exclude soft-deleted clients, else the picker leaks 10k+ deleted clients.
    """
    src = _search_func_source()
    # Count the SELECT ... FROM clients occurrences (the two branches).
    from_clients = src.count("FROM\n                clients") + src.count(
        "FROM clients"
    )
    assert from_clients >= 2, (
        f"Expected 2 `FROM clients` query branches, found {from_clients} — "
        "test anchor drifted; re-check search_clients."
    )
    # Every branch must constrain deleted_at IS NULL.
    deleted_guards = src.count("deleted_at IS NULL")
    assert deleted_guards >= 2, (
        f"search_clients has {deleted_guards} `deleted_at IS NULL` guards but "
        f"{from_clients} `FROM clients` branches — a branch leaks soft-deleted "
        "clients into the impersonation picker (live prod: 10,221 deleted)."
    )


def test_still_returns_live_clients_shape() -> None:
    """INNOCENCE: the fix doesn't gut the query — it still SELECTs the three
    picker fields and orders results (i.e. we constrained, not replaced)."""
    src = _search_func_source()
    assert "id, email, full_name" in src, "picker must still return id/email/full_name"
    assert "ORDER BY" in src, "picker must still order results"
    assert "LIMIT" in src, "picker must still limit results"
