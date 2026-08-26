r"""The Research OS bitemporal query cannot be served by a text index — proof, not opinion.

WHY THIS EXISTS. P06 (NAGA claim ledger) needs the query `05-test-matrix.md` specifies
after RULING B1: valid-time interval AND system-time cutoff AND exclusion of rows that
have a successor edge. `research_os_objects` stores the whole canonical object in one
`payload JSONB` column (migration 279), so the obvious move is a B-tree expression index
on `payload->'time'->>'valid_from'` / `->>'valid_to'`.

That obvious move is WRONG, and wrong in the one place a bitemporal query lives: the
interval boundary.

CORRECTION (2026-08-26, cross-family refuter, applied in a follow-up PR because the
merge queue had already frozen the original). The FIRST version of this module named the
wrong mechanism. It claimed `UtcDateTime` "does NOT canonicalise the serialised text"
and built its whole case on three spellings of one instant — `...T00:00:00Z`,
`...T00:00:00+00:00`, `...T00:00:00.000Z`. **That claim is false for the compliant write
path**: `model_dump(mode="json")` collapses all three to `2026-01-15T00:00:00Z`, so those
three strings never reach a payload written the sanctioned way. The refuter was right, and
a mutation test could not have caught it — the tests were internally consistent, they
simply pinned a mechanism nothing could reach.

The CONCLUSION survives, through a mechanism that is strictly stronger because it needs no
misbehaviour at all: **the canonical form's fractional part is OPTIONAL.** At microsecond
zero it is omitted entirely (`...T00:00:00Z`); otherwise it is emitted at full width
(`...T00:00:00.500000Z`). `.` is 0x2E and `Z` is 0x5A, so within a single second the
instant at microsecond zero — the EARLIEST one — sorts LAST as text. Two rows written by
the same compliant serialiser, one second apart at most, come back in inverted order, and
a half-open `valid_from <= T` predicate drops a row that is chronologically inside the
interval. `test_the_compliant_write_path_canonicalises_the_three_spellings` now pins the
refuter's finding, so if a future pydantic stops canonicalising, the older and weaker
framing becomes live again and we are told.

Every literal below is DERIVED from the real serialiser rather than typed in, precisely so
this module cannot repeat the mistake of pinning a belief about the canonical form instead
of the canonical form itself.

Worth knowing while reading the cure: the PUBLISHED contract does not close either hole.
`_UTC_OFFSET_PATTERN = r"(?:Z|\+00:00)$"` (`primitives.py:84`) sits inside a
`WithJsonSchema` block, so it documents the emitted JSON Schema rather than validating
input — and it explicitly ALLOWS both terminators while saying nothing whatsoever about
sub-second width. An independent producer building against that schema is entitled to
both spellings and to any fraction. Pydantic narrows the terminator by accident of its
default serialiser; nothing narrows the width.

And the correct expression cannot be indexed: `text::timestamptz` resolves through
`timestamptz_in`, which PostgreSQL marks STABLE (it depends on the `DateStyle` and
`TimeZone` GUCs), and an index expression must be IMMUTABLE. So the two available moves
are "index the wrong thing" and "index nothing".

LATENT, NOT LIVE — measured 2026-08-26, and load-bearing on how urgent this is. There are
ZERO production writers of `research_os_objects` in the tree: the only `INSERT INTO
research_os_objects` anywhere is inside migration 280's own test. No stored row can be
mis-ordered today because no stored row exists. This is a defect waiting at the entrance
of the lane that will write the first one, which is exactly when it is cheapest to fix.

These tests assert a CURRENT LIMITATION, deliberately: when the limitation is lifted — by
pinning the sub-second width on write, or by giving the substrate an IMMUTABLE-safe
normalised representation — they go red and must be deleted in the same change that lifts
it. A red here is GOOD NEWS. See the PENDING-ARMS row "Research OS valid-time is not
text-orderable".

The decision itself is deliberately NOT taken here: `research_os_objects` and
`UtcDateTime` are Work Packet 04's surface — migration 279's own table comment says
"Work Packet 04 owns this table; domain packets build adapters/projections on top,
never a parallel core". A P06 lane pinning the defect is in scope; a P06 lane changing
P04's canonical timestamp contract is not.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pytest


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "packages" / "research-os-core").is_dir():
            return candidate
    raise RuntimeError("cannot locate repository root from the research_os test path")


# `backend/tests/db/conftest.py` does not put research-os-core on sys.path — only
# `backend/tests/unit/research_os/conftest.py` does, and this module lives in the db tree
# because half its assertions need a real PostgreSQL. Same walk, same idiom, kept local
# rather than widening a shared conftest from a P06 lane.
sys.path.insert(0, str(_repo_root() / "packages" / "research-os-core"))

from pydantic import BaseModel  # noqa: E402
from research_os.primitives import UtcDateTime  # noqa: E402


class _Instant(BaseModel):
    """The narrowest possible stand-in for the `time` block of a canonical object."""

    t: UtcDateTime


def _canonical(value: datetime | str) -> str:
    """The exact text the sanctioned write path puts in `payload`."""

    return str(_Instant(t=value).model_dump(mode="json")["t"])


def _at(microsecond: int) -> str:
    return _canonical(datetime(2026, 1, 15, 0, 0, 0, microsecond, tzinfo=timezone.utc))


# One second, three instants, all written by the compliant path. EARLIEST is first.
_ZERO_US = _at(0)
_QUARTER = _at(250_000)
_HALF = _at(500_000)

# The three spellings the ORIGINAL version of this module was built on. Kept because the
# hazard they describe is real for a non-compliant writer — see the test that uses them.
_RAW_Z = "2026-01-15T00:00:00Z"
_RAW_OFFSET = "2026-01-15T00:00:00+00:00"
_RAW_FRACTIONAL = "2026-01-15T00:00:00.000Z"


def test_the_compliant_write_path_canonicalises_the_three_spellings() -> None:
    """Pins the refuter's correction, so the record cannot silently revert.

    If this ever goes red, `UtcDateTime` has stopped normalising and the original
    (weaker, but then LIVE) three-spelling framing applies again on top of everything
    below. That is a change worth being told about, not a detail.
    """

    assert {_canonical(_RAW_Z), _canonical(_RAW_OFFSET), _canonical(_RAW_FRACTIONAL)} == {_RAW_Z}


def test_the_canonical_form_omits_the_fraction_at_microsecond_zero() -> None:
    """The structural fact the whole defect rests on: the fraction is OPTIONAL.

    Not a quirk of one value — asserted across the width of the field.
    """

    assert "." not in _ZERO_US, _ZERO_US
    assert _at(1).endswith(".000001Z")
    assert _HALF.endswith(".500000Z")


def test_canonical_order_inverts_inside_a_single_second() -> None:
    """THE defect, reachable with no misbehaviour: two compliant writes, wrong order.

    `.` is 0x2E, `Z` is 0x5A. The instant at microsecond zero is chronologically FIRST
    and lexicographically LAST, so `ORDER BY payload->'time'->>'valid_from'` returns the
    interval's own lower bound out of place.
    """

    earlier = datetime.fromisoformat(_ZERO_US.replace("Z", "+00:00"))
    later = datetime.fromisoformat(_HALF.replace("Z", "+00:00"))

    assert earlier < later, "premise: these are two different instants, in this order"
    assert not (_ZERO_US < _HALF), "text order agreed with the clock — see module docstring"


def test_a_half_open_lower_bound_drops_a_row_at_the_boundary() -> None:
    """The failure mode, stated as the predicate a bitemporal store actually runs.

    `valid_from <= T` with both sides produced by the compliant serialiser does NOT admit
    a row whose `valid_from` fell on a whole second, although it precedes `T`. A silently
    missing row at an interval edge — precisely the class `fixtures/bitemporal/*` exist to
    catch.
    """

    lower_bound = datetime.fromisoformat(_ZERO_US.replace("Z", "+00:00"))
    cutoff = datetime.fromisoformat(_QUARTER.replace("Z", "+00:00"))

    assert lower_bound <= cutoff, "premise: the row IS inside the interval, by the clock"
    assert not (_ZERO_US <= _QUARTER), "text agreed with the clock — see module docstring"


def test_a_schema_conformant_writer_can_still_store_three_spellings() -> None:
    r"""The original finding, correctly scoped — and it is NOT merely a misbehaving writer.

    `UtcDateTime` advertises `_UTC_OFFSET_PATTERN = r"(?:Z|\+00:00)$"`
    (`primitives.py:84`, reached from the `WithJsonSchema` block at `:365`). That block is
    the PUBLISHED JSON Schema, not a runtime validator, and it explicitly permits BOTH
    terminators. So a writer that emits `+00:00` and persists its own bytes — instead of
    routing through `model_dump(mode="json")` — conforms to the published contract and
    still stores a string that sorts wrongly against a `Z` one.

    Latent today (zero production writers, see the module docstring). Kept pinned because
    the schema is the thing an independent producer would build against, and it grants
    exactly the ambiguity pydantic happens to close.
    """

    assert len({_RAW_Z, _RAW_OFFSET, _RAW_FRACTIONAL}) == 3
    assert _RAW_OFFSET < _RAW_Z
    assert _RAW_FRACTIONAL < _RAW_Z
    assert not (_RAW_Z <= _RAW_OFFSET)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_orders_the_canonical_forms_wrongly_as_text(
    db_tx: asyncpg.Connection,
) -> None:
    """The same facts, measured in the engine that would run the query.

    `$1::timestamptz` would make asyncpg infer a timestamptz PARAMETER and reject a str
    outright. The point is precisely that these arrive as TEXT — which is also what `->>`
    yields in the real query — so the parameter is pinned to text and PostgreSQL does the
    parsing.
    """

    clock_says_before, text_says_before = await db_tx.fetchrow(
        "SELECT $1::text::timestamptz < $2::text::timestamptz, $1::text < $2::text",
        _ZERO_US,
        _HALF,
    )
    assert clock_says_before is True
    assert text_says_before is False, (
        "PostgreSQL put the canonical forms in chronological order as text — if this "
        "passes, the sub-second width may now be fixed and this module should be deleted"
    )

    boundary_admits = await db_tx.fetchval("SELECT $1::text <= $2::text", _ZERO_US, _QUARTER)
    assert boundary_admits is False, (
        "the half-open lower bound admitted the boundary row — same conclusion as above"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_correct_cast_is_stable_and_therefore_unindexable(
    db_tx: asyncpg.Connection,
) -> None:
    """Closes the obvious rebuttal: "just cast to timestamptz in the index".

    Asserted twice — once from the catalogue (`provolatile`), once by asking PostgreSQL to
    actually build such an index and requiring it to refuse. The catalogue value alone
    would let a future PostgreSQL relabel slip past silently.
    """

    volatility = await db_tx.fetchval(
        "SELECT provolatile FROM pg_proc WHERE proname = 'timestamptz_in' LIMIT 1"
    )
    # pg_proc.provolatile is the `"char"` type, which asyncpg surfaces as BYTES, not str —
    # comparing it to "s" fails on a healthy database and would have read as "the
    # volatility changed". Normalise before asserting.
    if isinstance(volatility, (bytes, bytearray)):
        volatility = volatility.decode()
    assert volatility == "s", (
        f"timestamptz_in is marked {volatility!r}, not STABLE. If it became IMMUTABLE, "
        "the index this module says is impossible may now be buildable — re-check "
        "before deleting anything."
    )

    await db_tx.execute(
        "CREATE TEMP TABLE valid_time_index_probe (payload jsonb NOT NULL) ON COMMIT DROP"
    )
    with pytest.raises(asyncpg.exceptions.InvalidObjectDefinitionError) as excinfo:
        await db_tx.execute(
            "CREATE INDEX valid_time_probe_idx ON valid_time_index_probe "
            "(((payload -> 'time' ->> 'valid_from')::timestamptz))"
        )
    assert "IMMUTABLE" in str(excinfo.value), (
        "the index was refused for a reason other than immutability — read the error "
        f"before concluding anything: {excinfo.value}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_text_expression_index_builds_fine_which_is_the_trap(
    db_tx: asyncpg.Connection,
) -> None:
    """The dangerous half: the WRONG index is perfectly legal.

    Nothing stops a future lane from creating it, and nothing about it looks broken — it
    simply answers boundary queries incorrectly. That asymmetry (wrong is easy, right is
    impossible) is the whole reason this module is a test and not a comment.
    """

    await db_tx.execute(
        "CREATE TEMP TABLE text_index_probe (payload jsonb NOT NULL) ON COMMIT DROP"
    )
    await db_tx.execute(
        "CREATE INDEX text_probe_idx ON text_index_probe ((payload -> 'time' ->> 'valid_from'))"
    )
    indexed = await db_tx.fetchval(
        "SELECT count(*) FROM pg_indexes WHERE indexname = 'text_probe_idx'"
    )
    assert indexed == 1
