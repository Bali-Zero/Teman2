"""
Test: analytics endpoints with an OPTIONAL assigned-filter must derive their
date-param placeholder indices from len(params), never hardcode $2/$3.

The bug (found live in prod 2026-07-08): get_revenue_summary / get_client_overview
/ get_clients_trend built a WHERE clause with an optional `assigned_to = $1`
filter, then referenced the date params as $2/$3. For an ADMIN (no assigned
filter → params == []), the date params are actually $1/$2, so $3 is never
bound and asyncpg raises IndeterminateDatatypeError ("could not determine data
type of parameter $1") → the endpoint 503s for every admin, while a filtered
team member (params == [email]) works. All three CRM analytics tabs were dead
for admins.

These tests are static source-analysis (same style as the sibling
test_crm_analytics_no_n_plus_one.py): they assert the fixed functions no longer
contain the hardcoded-index pattern (guilt) and DO derive indices from
len(params) (innocence of the fix).
"""

import ast
import re
from pathlib import Path

ROUTER_PATH = Path(__file__).parents[5] / "backend" / "app" / "routers" / "crm_analytics.py"

# The three endpoints that had the optional-filter + hardcoded-date-index bug.
AFFECTED_FUNCS = [
    "get_revenue_summary",
    "get_client_overview",
    "get_client_trend",
]


def _get_function_source(func_name: str) -> str:
    source = ROUTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == func_name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])  # type: ignore[attr-defined]
    return ""


def test_affected_functions_exist() -> None:
    for fn in AFFECTED_FUNCS:
        assert _get_function_source(fn), f"{fn} not found in crm_analytics.py"


def test_no_hardcoded_date_placeholder_after_optional_filter() -> None:
    """[guilt] No date comparison may hardcode $2/$3 in these functions.

    The buggy shape was: `created_at >= $2 AND created_at < $3` (or `>= $2`),
    where $2/$3 are wrong whenever the optional $1 filter is absent. After the
    fix, date placeholders are interpolated from len(params), so no literal
    `>= $2` / `< $3` should survive in the date-range comparisons.
    """
    for fn in AFFECTED_FUNCS:
        src = _get_function_source(fn)
        # Any created_at comparison against a *literal* $2 or $3 is the bug.
        offenders = re.findall(r"created_at\s*[<>]=?\s*\$[23]\b", src)
        assert not offenders, (
            f"{fn} still hardcodes a date placeholder ({offenders}) after an "
            "optional assigned-filter — this 503s for admins (params empty → "
            "date param is $1, not $2). Derive the index from len(params)."
        )


def test_date_placeholder_index_is_derived_from_params_length() -> None:
    """[innocence] The fix derives the index from len(params)/len(*_params).

    Each affected function must compute at least one `len(...) + 1` index used
    to build the date-range placeholder, proving the index tracks the actual
    parameter count rather than a hardcoded position.
    """
    for fn in AFFECTED_FUNCS:
        src = _get_function_source(fn)
        assert re.search(r"len\(\w*params\)\s*\+\s*1", src), (
            f"{fn} does not derive a date placeholder index from len(params) — "
            "the fix must compute `${len(params)+1}` so admins (no filter) bind "
            "$1 correctly."
        )


def test_month_params_no_longer_branch_on_params_truthiness() -> None:
    """[innocence] month_params must not use the `if params else` fallback.

    The old code did `[*params, start, end] if params else [start, end]`, which
    is exactly what mismatched the SQL indices. After the fix the params list is
    unconditional `[*params, start, end]` and the SQL index adapts instead.
    """
    src = _get_function_source("get_revenue_summary")
    assert "if params else" not in src, (
        "get_revenue_summary still branches month_params on `if params else` — "
        "unify to `[*params, start, end]` and adapt the SQL index."
    )
