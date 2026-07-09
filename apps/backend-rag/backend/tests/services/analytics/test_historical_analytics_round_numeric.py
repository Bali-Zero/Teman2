"""Regression guard: SQL ROUND() in historical_analytics must never receive a
bare double-precision first arg.

Postgres has ROUND(numeric, int) but NOT ROUND(double precision, int). The
`get_response_times` query used `ROUND(AVG(EXTRACT(EPOCH ...) / 86400), 2)`,
where EXTRACT(EPOCH ...) is double precision -> live HTTP 500:

    function round(double precision, integer) does not exist

The fix casts the numeric arg to ::numeric before ROUND. This test is a static
guard over the module's SQL: every ROUND(...) whose first argument contains an
EXTRACT(EPOCH ...) expression must route that expression through an explicit
::numeric cast. It fails on the pre-fix source and passes on the fixed source,
independently of a live DB (so it runs in CI without Postgres).
"""

from __future__ import annotations

import re
from pathlib import Path

# __file__ = .../backend/tests/services/analytics/test_...py
#   parents[0]=analytics parents[1]=services parents[2]=tests parents[3]=backend
_MODULE = (
    Path(__file__).resolve().parents[3]
    / "services"
    / "analytics"
    / "historical_analytics.py"
)


def _source() -> str:
    return _MODULE.read_text(encoding="utf-8")


def _round_call_bodies(sql: str) -> list[str]:
    """Return the substring inside each top-level ROUND( ... ) call.

    Uses paren-depth counting so nested AVG()/EXTRACT()/PERCENTILE_CONT() are
    kept whole rather than split on the first inner comma.
    """
    bodies: list[str] = []
    for m in re.finditer(r"ROUND\s*\(", sql, flags=re.IGNORECASE):
        i = m.end()
        depth = 1
        start = i
        while i < len(sql) and depth > 0:
            c = sql[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            i += 1
        bodies.append(sql[start : i - 1])
    return bodies


def test_module_exists() -> None:
    assert _MODULE.is_file(), f"analytics module not found at {_MODULE}"


def test_every_extract_epoch_round_is_numeric_cast() -> None:
    """Any ROUND() whose body references EXTRACT(EPOCH ...) must cast to ::numeric.

    This is the exact class that caused the live 500 on /api/analytics/response-times.
    """
    sql = _source()
    offenders: list[str] = []
    for body in _round_call_bodies(sql):
        if re.search(r"EXTRACT\s*\(\s*EPOCH", body, flags=re.IGNORECASE):
            if "::numeric" not in body.lower():
                offenders.append(body.strip()[:120])
    assert not offenders, (
        "ROUND() over EXTRACT(EPOCH ...) without ::numeric cast — "
        "Postgres has no ROUND(double precision, int):\n" + "\n".join(offenders)
    )


def test_response_times_query_casts_all_epoch_rounds() -> None:
    """Belt-and-suspenders: the specific six duration metrics are cast."""
    sql = _source()
    # The six response-time ROUNDs all divide by 86400 (seconds/day).
    for body in _round_call_bodies(sql):
        if "86400" in body:
            assert "::numeric" in body.lower(), (
                f"day-duration ROUND missing ::numeric cast: {body.strip()[:120]}"
            )
