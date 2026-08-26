"""The Research OS bitemporal query cannot be served by a text index — proof, not opinion.

WHY THIS EXISTS. P06 (NAGA claim ledger) needs the query `05-test-matrix.md` now
specifies after RULING B1: valid-time interval AND system-time cutoff AND exclusion of
rows that have a successor edge. `research_os_objects` stores the whole canonical
object in one `payload JSONB` column (migration 279), so the obvious move is a B-tree
expression index on `payload->'time'->>'valid_from'` / `->>'valid_to'`.

That obvious move is WRONG, and wrong in the one place a bitemporal query lives: the
interval boundary. `UtcDateTime`
(`packages/research-os-core/research_os/primitives.py:362`) validates that a timestamp
is timezone-aware and UTC — it does NOT canonicalise the serialised text. `...T00:00:00Z`
and `...T00:00:00+00:00` and `...T00:00:00.000Z` are all accepted, all the same instant,
and all different STRINGS. Lexicographic order over those strings is not chronological
order, so `->>` comparisons silently disagree with the clock.

And the correct expression cannot be indexed: `text::timestamptz` resolves through
`timestamptz_in`, which PostgreSQL marks STABLE (it depends on the `DateStyle` and
`TimeZone` GUCs), and an index expression must be IMMUTABLE. So the two available moves
are "index the wrong thing" and "index nothing".

These tests pin all three facts so the next lane meets them as a red test rather than
as a boundary bug in a bitemporal store nobody suspects. They assert a CURRENT
LIMITATION, deliberately: when the limitation is lifted — by canonicalising the wire
form on write, or by giving the substrate an IMMUTABLE-safe normalised representation —
these tests go red and must be deleted in the same change that lifts it. A red here is
GOOD NEWS. See the PENDING-ARMS row "Research OS valid-time is not text-orderable".

The decision itself is deliberately NOT taken here: `research_os_objects` and
`UtcDateTime` are Work Packet 04's surface — migration 279's own table comment says
"Work Packet 04 owns this table; domain packets build adapters/projections on top,
never a parallel core". A P06 lane pinning the defect is in scope; a P06 lane changing
P04's canonical timestamp contract is not.
"""

from __future__ import annotations

import asyncpg
import pytest

# Three spellings of ONE instant, all valid under UtcDateTime.
_Z = "2026-01-15T00:00:00Z"
_OFFSET = "2026-01-15T00:00:00+00:00"
_FRACTIONAL = "2026-01-15T00:00:00.000Z"


def test_the_three_spellings_are_textually_distinct() -> None:
    """Premise check. If a future canonicaliser collapses these, the rest is moot."""

    assert len({_Z, _OFFSET, _FRACTIONAL}) == 3


def test_lexicographic_order_disagrees_with_the_clock() -> None:
    """Pure-Python half: no database needed to see the ordering is wrong.

    `+` is 0x2B and `.` is 0x2E, both below `Z` at 0x5A — so two spellings of the
    SAME instant sort strictly before the `Z` form.
    """

    assert _OFFSET < _Z
    assert _FRACTIONAL < _Z


def test_a_half_open_lower_bound_would_drop_a_row_at_the_boundary() -> None:
    """The failure mode, stated as the predicate a bitemporal store actually runs.

    `valid_from <= T` with `T` supplied in `Z` form does NOT admit a row whose
    `valid_from` was persisted in `+00:00` form — although they are the same instant.
    This is a silently missing row at an interval edge, which is precisely what
    `fixtures/bitemporal/*` exist to catch.
    """

    assert not (_Z <= _OFFSET)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_agrees_the_spellings_are_one_instant_but_not_one_string(
    db_tx: asyncpg.Connection,
) -> None:
    """The same facts, measured in the engine that would run the query."""

    # `$1::timestamptz` makes asyncpg infer a timestamptz PARAMETER and reject a str
    # outright ("expected a datetime.date or datetime.datetime instance"). The point
    # here is precisely that these arrive as TEXT, so pin the parameter to text first
    # and let PostgreSQL do the parsing — which is also what `->>` yields in the real
    # query.
    same_instant, text_says_before = await db_tx.fetchrow(
        "SELECT $1::text::timestamptz = $2::text::timestamptz, $1::text < $2::text",
        _OFFSET,
        _Z,
    )
    assert same_instant is True
    assert text_says_before is True

    boundary_admits = await db_tx.fetchval(
        "SELECT $1::text <= $2::text", _Z, _OFFSET
    )
    assert boundary_admits is False, (
        "text comparison admitted the boundary row — if this passes, the canonical "
        "wire form may now be normalised and this whole module should be deleted"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_correct_cast_is_stable_and_therefore_unindexable(
    db_tx: asyncpg.Connection,
) -> None:
    """Closes the obvious rebuttal: "just cast to timestamptz in the index".

    Asserted twice — once from the catalogue (`provolatile`), once by asking
    PostgreSQL to actually build such an index and requiring it to refuse. The
    catalogue value alone would let a future PostgreSQL relabel slip past silently.
    """

    volatility = await db_tx.fetchval(
        "SELECT provolatile FROM pg_proc WHERE proname = 'timestamptz_in' LIMIT 1"
    )
    # pg_proc.provolatile is the `"char"` type, which asyncpg surfaces as BYTES, not
    # str — comparing it to "s" fails on a healthy database and would have read as
    # "the volatility changed". Normalise before asserting.
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

    Nothing stops a future lane from creating it, and nothing about it looks broken —
    it simply answers boundary queries incorrectly. That asymmetry (wrong is easy,
    right is impossible) is the whole reason this module is a test and not a comment.
    """

    await db_tx.execute(
        "CREATE TEMP TABLE text_index_probe (payload jsonb NOT NULL) ON COMMIT DROP"
    )
    await db_tx.execute(
        "CREATE INDEX text_probe_idx ON text_index_probe "
        "((payload -> 'time' ->> 'valid_from'))"
    )
    indexed = await db_tx.fetchval(
        "SELECT count(*) FROM pg_indexes WHERE indexname = 'text_probe_idx'"
    )
    assert indexed == 1
