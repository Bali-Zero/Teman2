"""Cross-implementation parity: SQL `research_os_instant_key` vs R1's `instant_sort_key`.

R1-build-spec.md section 4.1: for every admitted spelling the two MUST return the identical
string, and byte order over the key MUST agree with chronological order over the parsed
instant. R1's reference implementation
(`backend/tests/unit/research_os/research_os_reader_reference.py`, an unmerged sibling
branch's own executable spec, read from disk -- not re-implemented here) has zero
dependency on `packages/research-os-core`, so it is imported directly with no `sys.path`
bootstrap.

CI collection: identical finding to `test_migration_312_research_os_naga_claims.py`'s module
docstring -- collected under `backend/tests/`, run by the `Backend Shard N` job in
`.github/workflows/tests.yml` against its `postgres:15` service. No skip, no xfail.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_base import split_migration_sql
from backend.tests.unit.research_os.research_os_reader_reference import (
    instant_sort_key,
    parse_instant,
)

pytestmark = pytest.mark.integration

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"


def _dsn() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL", "postgresql://nuzantara@localhost:5432/nuzantara_test"
    )


def _forward(name: str) -> str:
    forward, _ = split_migration_sql((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
    return forward


@pytest.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute("SELECT pg_advisory_lock(hashtext('r2-migration-312-parity-test'))")
        await conn.execute(
            """
            DROP TABLE IF EXISTS research_os_naga_admission, research_os_objects CASCADE;
            DROP FUNCTION IF EXISTS public.research_os_instant_key(text);
            DROP FUNCTION IF EXISTS public.reject_research_os_objects_mutation();
            """
        )
        async with conn.transaction():
            await conn.execute(_forward("279_research_os_contract_core.sql"))
            await conn.execute(_forward("280_research_os_objects_truncate_guard.sql"))
            await conn.execute(_forward("312_research_os_naga_claims.sql"))
        yield conn
    finally:
        await conn.execute(
            "SELECT pg_advisory_unlock(hashtext('r2-migration-312-parity-test'))"
        )
        await conn.close()


def _r1_key_or_none(text: str) -> str | None:
    try:
        return instant_sort_key(text)
    except ValueError:
        return None


async def _sql_key(conn: asyncpg.Connection, text: str) -> str | None:
    return await conn.fetchval("SELECT public.research_os_instant_key($1)", text)


# ---------------------------------------------------------------------------
# Admitted spellings: SQL and R1 must return the IDENTICAL 27-byte string.
# ---------------------------------------------------------------------------

ADMITTED_SPELLINGS: list[str] = [
    "2026-09-11T10:00:00.1Z",
    "2026-09-11T10:00:00.100000Z",
    "2026-09-11T10:00:00.11Z",
    "2026-09-11T10:00:00Z",
    "2026-09-11T10:00:00+00:00",
    "2026-09-11t10:00:00Z",
    "2026-09-11T10:00:00z",
    "2026-09-11T10:00:00.000000Z",
    "2026-09-11T10:00:00.1234567Z",
    "2026-09-11T10:00:00.123456Z",
]


@pytest.mark.parametrize("text", ADMITTED_SPELLINGS, ids=ADMITTED_SPELLINGS)
async def test_admitted_spellings_match_r1_byte_for_byte(
    db: asyncpg.Connection, text: str
) -> None:
    sql_key = await _sql_key(db, text)
    r1_key = _r1_key_or_none(text)
    assert sql_key is not None, f"SQL rejected an admitted spelling: {text!r}"
    assert r1_key is not None, f"R1 rejected an admitted spelling: {text!r}"
    assert sql_key == r1_key, (text, sql_key, r1_key)
    assert len(sql_key) == 27, (text, sql_key)


# ---------------------------------------------------------------------------
# Calendar-invalid shapes: both must reject (SQL NULL, R1 raises ValueError).
# Two controls (valid leap days) are included to prove the parity holds on the ADMITTING
# side of the same boundary, not only on the rejecting side.
# ---------------------------------------------------------------------------

CALENDAR_CASES: list[tuple[str, str, bool]] = [
    # (id, text, expect_admitted)
    ("feb_30", "2026-02-30T10:00:00Z", False),
    ("non_leap_feb_29", "2025-02-29T10:00:00Z", False),
    ("leap_feb_29", "2024-02-29T10:00:00Z", True),
    ("century_non_leap_feb_29", "2100-02-29T10:00:00Z", False),
    ("century_leap_feb_29", "2000-02-29T10:00:00Z", True),
    ("month_00", "2026-00-11T10:00:00Z", False),
    ("month_13", "2026-13-11T10:00:00Z", False),
    ("day_00", "2026-09-00T10:00:00Z", False),
    ("day_32", "2026-09-32T10:00:00Z", False),
    ("hour_24", "2026-09-11T24:00:00Z", False),
    ("minute_60", "2026-09-11T10:60:00Z", False),
    ("second_60", "2026-09-11T10:00:60Z", False),
    ("year_0000", "0000-09-11T10:00:00Z", False),
]


@pytest.mark.parametrize(
    "text,expect_admitted",
    [(c[1], c[2]) for c in CALENDAR_CASES],
    ids=[c[0] for c in CALENDAR_CASES],
)
async def test_calendar_boundaries_agree_with_r1(
    db: asyncpg.Connection, text: str, expect_admitted: bool
) -> None:
    sql_key = await _sql_key(db, text)
    r1_key = _r1_key_or_none(text)
    if expect_admitted:
        assert sql_key is not None and r1_key is not None, (text, sql_key, r1_key)
    else:
        assert sql_key is None, (text, sql_key)
        assert r1_key is None, (text, r1_key)
    assert sql_key == r1_key, (text, sql_key, r1_key)


# ---------------------------------------------------------------------------
# Non-ASCII digits: measured, not assumed. R1's `_INSTANT_RE` uses bare `\d`, which under
# Python's default (non-ASCII) `re` flags matches any Unicode decimal-digit codepoint,
# Arabic-Indic included -- so the REGEX stage admits this spelling. But `instant_sort_key`
# then calls `datetime.fromisoformat`, which requires ASCII digits and raises
# `ValueError: Invalid isoformat string: ...`. Measured directly against R1's reference
# implementation before writing this test. SQL's `[0-9]` never matches these codepoints at
# the regex stage, so it returns NULL. BOTH REJECT -- there is no domain divergence to
# exclude or paper over here; this test pins that measured fact.
# ---------------------------------------------------------------------------

NON_ASCII_DIGIT_INSTANT = "٢٠٢٦-٠٩-١١T١٠:٠٠:٠٠Z"


async def test_non_ascii_digits_both_reject_no_divergence(db: asyncpg.Connection) -> None:
    sql_key = await _sql_key(db, NON_ASCII_DIGIT_INSTANT)
    assert sql_key is None
    with pytest.raises(ValueError):
        instant_sort_key(NON_ASCII_DIGIT_INSTANT)


# ---------------------------------------------------------------------------
# Byte order over the key agrees with chronological order over the parsed instant.
# ---------------------------------------------------------------------------

ORDERING_PAIRS: list[tuple[str, str, str]] = [
    ("frac_1_vs_100000_equal", "2026-09-11T10:00:00.1Z", "2026-09-11T10:00:00.100000Z"),
    ("frac_1_vs_11", "2026-09-11T10:00:00.1Z", "2026-09-11T10:00:00.11Z"),
    ("Z_vs_plus_00_00_equal", "2026-09-11T10:00:00Z", "2026-09-11T10:00:00+00:00"),
    ("lowercase_t_vs_T_equal", "2026-09-11t10:00:00Z", "2026-09-11T10:00:00Z"),
    ("lowercase_z_vs_Z_equal", "2026-09-11T10:00:00z", "2026-09-11T10:00:00Z"),
    (
        "absent_fraction_vs_explicit_zero_equal_the_classic_bug_pair",
        "2026-09-11T10:00:00Z",
        "2026-09-11T10:00:00.000000Z",
    ),
    (
        "seven_digit_fraction_truncates_not_rounds",
        "2026-09-11T10:00:00.1234567Z",
        "2026-09-11T10:00:00.123457Z",
    ),
]


@pytest.mark.parametrize(
    "earlier,later",
    [(c[1], c[2]) for c in ORDERING_PAIRS],
    ids=[c[0] for c in ORDERING_PAIRS],
)
async def test_byte_order_over_key_agrees_with_chronological_order(
    db: asyncpg.Connection, earlier: str, later: str
) -> None:
    row = await db.fetchrow(
        "SELECT (public.research_os_instant_key($1) COLLATE \"C\") AS ek, "
        "       (public.research_os_instant_key($2) COLLATE \"C\") AS lk",
        earlier,
        later,
    )
    ek, lk = row["ek"], row["lk"]
    assert ek is not None and lk is not None, (earlier, later, ek, lk)

    r1_ek, r1_lk = instant_sort_key(earlier), instant_sort_key(later)
    assert (ek, lk) == (r1_ek, r1_lk), (earlier, later, ek, lk, r1_ek, r1_lk)

    chronological = parse_instant(earlier) <= parse_instant(later)
    byte_order = ek <= lk
    assert byte_order == chronological, (
        f"byte order over keys disagrees with chronological order for the pair "
        f"{earlier!r} (key={ek!r}) vs {later!r} (key={lk!r})"
    )
