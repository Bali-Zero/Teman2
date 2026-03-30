"""
Test: get_team_performance in crm_analytics.py must NOT use a per-member loop.

Step 1: Written BEFORE the fix — should FAIL on current code.
Step 2: After the fix (single GROUP BY query) it should PASS.
"""

import ast
import re
from pathlib import Path

ROUTER_PATH = (
    Path(__file__).parents[5]
    / "backend"
    / "app"
    / "routers"
    / "crm_analytics.py"
)


def _source() -> str:
    return ROUTER_PATH.read_text(encoding="utf-8")


def _get_function_source(func_name: str) -> str:
    """Extract the source lines of a top-level async function by name."""
    source = _source()
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == func_name:
            # end_lineno is available from Python 3.8+
            start = node.lineno - 1
            end = node.end_lineno  # type: ignore[attr-defined]
            return "\n".join(lines[start:end])
    return ""


# ---------------------------------------------------------------------------
# Test 1 — the N+1 loop pattern must NOT be present inside get_team_performance
# ---------------------------------------------------------------------------

def test_no_for_member_loop_in_get_team_performance() -> None:
    """Assert get_team_performance does NOT contain a per-member for-loop.

    Both 'for member in' and 'for tm in' are forbidden — they indicate the
    old N+1 pattern where 4 queries are issued per team member.
    """
    func_src = _get_function_source("get_team_performance")
    assert func_src, "get_team_performance function not found in crm_analytics.py"

    forbidden_patterns = [
        r"\bfor\s+member\s+in\b",
        r"\bfor\s+tm\s+in\b",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, func_src), (
            f"Found forbidden loop pattern '{pattern}' inside get_team_performance — "
            "the function still uses the N+1 per-member query loop. "
            "Rewrite to use a single GROUP BY aggregate query."
        )


# ---------------------------------------------------------------------------
# Test 2 — the single aggregate query keywords must be present
# ---------------------------------------------------------------------------

def test_group_by_aggregate_query_present() -> None:
    """Assert get_team_performance uses GROUP BY (single aggregate query)."""
    func_src = _get_function_source("get_team_performance")
    assert func_src, "get_team_performance function not found in crm_analytics.py"

    assert re.search(r"GROUP\s+BY", func_src, re.IGNORECASE), (
        "get_team_performance does not contain a GROUP BY clause — "
        "expected a single aggregate query replacing the per-member loop."
    )


# ---------------------------------------------------------------------------
# Test 3 — the function must still respect RBAC (admin vs non-admin)
# ---------------------------------------------------------------------------

def test_rbac_logic_preserved() -> None:
    """Assert RBAC check (is_crm_admin / user_is_admin) is still present."""
    func_src = _get_function_source("get_team_performance")
    assert func_src, "get_team_performance function not found in crm_analytics.py"

    assert "user_is_admin" in func_src, (
        "RBAC check 'user_is_admin' not found in get_team_performance — "
        "the refactor must preserve access control logic."
    )
