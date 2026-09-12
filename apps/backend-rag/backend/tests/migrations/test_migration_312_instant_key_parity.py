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
from backend.services.research_os.naga_persistence import _WRITE_INSTANT_RE
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
# Non-ASCII digits. R1's `_INSTANT_RE` uses bare `\d`, which under Python's default
# (non-ASCII) `re` flags matches any Unicode decimal-digit codepoint, Arabic-Indic included,
# so the REGEX stage admits these spellings; SQL's POSIX `[0-9]` never matches them and
# returns NULL. What happens next depends on WHERE the non-ASCII digit sits, and the two
# cases below do NOT behave the same. An earlier version of this file measured only the
# first and concluded "both reject, no domain divergence" -- that conclusion was FALSE for
# the second case, which no test exercised. Found by the Kimi K3 council seat, re-measured
# here before the words were changed.
#
#   (1) non-ASCII in the DATE (or clock): `instant_sort_key` reaches
#       `datetime.fromisoformat`, which is ASCII-only, and raises. SQL NULLs. Both reject.
#   (2) non-ASCII in the FRACTION ONLY: `fromisoformat` only ever sees the ASCII date and
#       clock, so it does NOT raise; the fraction goes to `int()`, which DOES accept Unicode
#       digits. R1's reference therefore returns a key while SQL returns NULL -- a real
#       domain divergence on R1's surface, pinned here rather than papered over.
#
# R2 cannot cure (2) at its source: `_INSTANT_RE` lives in R1's reference module, outside
# this window's writable perimeter. R2 fences it instead, at the only place it could reach
# storage -- `naga_persistence._WRITE_INSTANT_RE` spells digits `[0-9]`, exactly as the key
# does, so this slice can never write a row the key cannot index. The fence is asserted by
# `test_naga_persistence_unit.py::test_validate_object_rejects_malformed_write_path_instants`
# and by the last assertion below. The residual is reported to the staff room: a foreign
# writer of `research_os_objects` (today only `consul_executor`) is NOT behind this fence.
# ---------------------------------------------------------------------------

NON_ASCII_DIGIT_INSTANT = "٢٠٢٦-٠٩-١١T١٠:٠٠:٠٠Z"
NON_ASCII_FRACTION_INSTANT = "2026-09-11T10:00:00.١Z"


async def test_non_ascii_digits_in_the_date_both_reject(db: asyncpg.Connection) -> None:
    sql_key = await _sql_key(db, NON_ASCII_DIGIT_INSTANT)
    assert sql_key is None
    with pytest.raises(ValueError):
        instant_sort_key(NON_ASCII_DIGIT_INSTANT)


async def test_non_ascii_digits_in_the_fraction_diverge_and_the_writer_fences_it(
    db: asyncpg.Connection,
) -> None:
    """The one measured divergence between R1's reference and the storage key, and its fence."""

    sql_key = await _sql_key(db, NON_ASCII_FRACTION_INSTANT)
    assert sql_key is None, "migration 312 uses POSIX [0-9] and must NULL this spelling"

    # R1's reference does NOT reject it -- the divergence, stated as a measurement.
    assert instant_sort_key(NON_ASCII_FRACTION_INSTANT) == "2026-09-11T10:00:00.100000Z"

    # R2's write path is the fence: nothing this slice writes can carry that spelling.
    assert _WRITE_INSTANT_RE.match(NON_ASCII_FRACTION_INSTANT) is None
    assert _WRITE_INSTANT_RE.match("2026-09-11T10:00:00.1Z") is not None


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
