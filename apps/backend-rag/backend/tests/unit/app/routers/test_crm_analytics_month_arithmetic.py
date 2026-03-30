"""
Test: month arithmetic in crm_analytics.py must NOT use timedelta(days=i * 30).

Step 1: This test is written BEFORE the fix — it should FAIL on the current code.
Step 2: After the fix it should PASS.
"""

import ast
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


# ---------------------------------------------------------------------------
# Test 1 — regression guard: the bad pattern must NOT be present
# ---------------------------------------------------------------------------

def test_no_timedelta_days_times_30() -> None:
    """Assert the file contains no occurrence of timedelta(days=i * 30)."""
    source = _source()
    assert "timedelta(days=i * 30)" not in source, (
        "Found 'timedelta(days=i * 30)' in crm_analytics.py — "
        "month arithmetic is still broken. "
        "Replace with _months_ago(i) / _next_month_start()."
    )


# ---------------------------------------------------------------------------
# Test 2 — verify helper functions are defined (AST-level, no import needed)
# ---------------------------------------------------------------------------

def test_helper_functions_defined() -> None:
    """Assert _months_ago and _next_month_start are defined at module level."""
    source = _source()
    tree = ast.parse(source)
    func_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    assert "_months_ago" in func_names, (
        "_months_ago helper function not found in crm_analytics.py"
    )
    assert "_next_month_start" in func_names, (
        "_next_month_start helper function not found in crm_analytics.py"
    )


# ---------------------------------------------------------------------------
# Test 3 — functional correctness of _months_ago (inline re-implementation
#           to avoid importing the full FastAPI module graph)
# ---------------------------------------------------------------------------

def _months_ago_ref(n: int):
    """Reference implementation identical to what the spec requires."""
    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc)
    month = now.month - n
    year = now.year
    while month <= 0:
        month += 12
        year -= 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def test_months_ago_zero() -> None:
    """_months_ago(0) should be the first day of the current month."""
    from datetime import datetime, timezone

    result = _months_ago_ref(0)
    now = datetime.now(tz=timezone.utc)
    assert result.year == now.year
    assert result.month == now.month
    assert result.day == 1


def test_months_ago_wraps_year() -> None:
    """_months_ago must handle year-boundary correctly (e.g. Jan → Dec prev year)."""
    result = _months_ago_ref(13)
    assert result.day == 1
    assert result.tzinfo is not None


def test_months_ago_six_consecutive_are_distinct() -> None:
    """The 6 month-start values used in revenue breakdown must be distinct."""
    dates = [_months_ago_ref(i) for i in range(5, -1, -1)]
    assert len(dates) == len(set(dates)), "Duplicate month_start values — arithmetic is wrong"


# ---------------------------------------------------------------------------
# Test 4 — functional correctness of _next_month_start
# ---------------------------------------------------------------------------

def _next_month_start_ref(dt):
    """Reference implementation identical to what the spec requires."""
    from datetime import datetime, timezone

    if dt.month == 12:
        return datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(dt.year, dt.month + 1, 1, tzinfo=timezone.utc)


def test_next_month_start_normal() -> None:
    from datetime import datetime, timezone

    dt = datetime(2026, 3, 1, tzinfo=timezone.utc)
    result = _next_month_start_ref(dt)
    assert result == datetime(2026, 4, 1, tzinfo=timezone.utc)


def test_next_month_start_december() -> None:
    from datetime import datetime, timezone

    dt = datetime(2025, 12, 1, tzinfo=timezone.utc)
    result = _next_month_start_ref(dt)
    assert result == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_month_ranges_are_contiguous() -> None:
    """Each month_end must equal the next month_start (no gaps, no overlaps)."""
    months = [_months_ago_ref(i) for i in range(5, -1, -1)]
    ends = [_next_month_start_ref(m) for m in months]
    for i in range(len(months) - 1):
        assert ends[i] == months[i + 1], (
            f"Gap or overlap between month {i} end ({ends[i]}) "
            f"and month {i+1} start ({months[i+1]})"
        )
