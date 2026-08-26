r"""The Research OS bitemporal query cannot be served by a text index — proof, not opinion.

WHY THIS EXISTS. P06 (NAGA claim ledger) needs the query `05-test-matrix.md` specifies
after RULING B1: valid-time interval AND system-time cutoff AND exclusion of rows that
have a successor edge. `research_os_objects` stores the whole canonical object in one
`payload JSONB` column (migration 279), so the obvious move is a B-tree expression index
on `payload->'time'->>'valid_from'` / `->>'valid_to'`.

That obvious move is WRONG, and wrong in the one place a bitemporal query lives: the
interval boundary. **The canonical form's fractional part is OPTIONAL.** At microsecond
zero it is omitted entirely (`...T00:00:00Z`); otherwise it is emitted at full width
(`...T00:00:00.500000Z`). `.` is 0x2E and `Z` is 0x5A, so within a single second the
instant at microsecond zero — the EARLIEST one — sorts LAST as text. Two rows written by
the same compliant serialiser come back in inverted order, and a half-open
`valid_from <= T` predicate drops a row that is chronologically inside the interval.

And the correct expression cannot be indexed: `text::timestamptz` resolves through
`timestamptz_in`, which PostgreSQL marks STABLE (it depends on the `DateStyle` and
`TimeZone` GUCs), and an index expression must be IMMUTABLE. So the two available moves
are "index the wrong thing" and "index nothing".

TWO CORRECTIONS ARE BAKED INTO THIS MODULE. Both were found by cross-family refuters
attacking earlier versions of it, and both are recorded here rather than quietly fixed,
because the shape of the mistakes is the point.

**First (PR #5036 -> #5039).** The original argued from three spellings of one instant —
`...T00:00:00Z`, `...+00:00`, `...T00:00:00.000Z` — on the claim that `UtcDateTime` does
not canonicalise the serialised text. That claim is FALSE for the compliant write path:
`model_dump(mode="json")` collapses all three. The mechanism was unreachable; the
conclusion survived only via the optional-fraction mechanism described above, which needs
no misbehaviour at all.

**Second (within #5039).** The first correction proved the new mechanism against a LOCAL
STAND-IN — a bare `BaseModel` carrying one `UtcDateTime` field — and called it "the real
serialiser". It was not. A refuter simulated the actual cure where a cure would actually
land (a serialiser on the canonical model layer) and showed the real writer switching to
fixed precision **while every synchronous test in this module stayed green**. The module's
whole promise — "when the limitation is lifted these go red" — held only for a cure that
happened to touch the stand-in. So every value below now derives from the REAL canonical
models, `ClaimTime` and `ValidTime`, and the PostgreSQL tests now INSERT real JSONB rows
and order by the real `->>` expression instead of comparing text parameters that never
touched a payload.

LATENT, NOT LIVE — measured, and load-bearing on how urgent this is. There are ZERO
production writers of `research_os_objects` in the tree: the only `INSERT INTO
research_os_objects` anywhere is inside migration 280's own test, there is no ORM
declaration over it, no `COPY` writer, no dynamically-built table name, and no non-test
caller of the Research OS adapters. No stored row can be mis-ordered today because no
stored row exists. This is a defect waiting at the entrance of the lane that will write
the first one, which is exactly when it is cheapest to fix.

**Third (round 2, and it narrows the promise rather than widening the code).** An earlier
version of this paragraph promised that these tests go red whenever the limitation is
lifted, by either of the two cures the PENDING-ARMS row proposes. That is FALSE for cure
(b). Giving the substrate a normalised/generated column or an IMMUTABLE parse helper lifts
the limitation by routing AROUND the text expression, which stays exactly as defective as
it is today — so every assertion here correctly stays GREEN. The same refuter noted three
further blind spots, recorded rather than chased: a cure at the storage/adapter boundary
(this module inserts `_claim_time_payload()` output directly, so an adapter that
normalised on write would be bypassed), a cure on the outer `Claim` model rather than
`ClaimTime`, and `valid_to`, which no test here exercises. Closing those means testing the
real end-to-end write path, and there is no writer to test yet — it is the spec the
PENDING-ARMS row owes, not a fourth correction of this file.

So, scoped honestly: these tests assert a CURRENT LIMITATION and go red for a cure applied
to CANONICAL SERIALISATION — the (a)-shaped cure, pinning the sub-second width on write.
For that cure a red here is GOOD NEWS and they must be deleted in the same change. For a
(b)-shaped cure they stay green, and a GREEN suite is therefore compatible with the
limitation having been lifted: confirm the arming from the migration or adapter that lifts
it, never from this module alone. See the PENDING-ARMS row "Research OS valid-time is not
text-orderable".

The decision itself is deliberately NOT taken here: `research_os_objects` and
`UtcDateTime` are Work Packet 04's surface — migration 279's own table comment says
"Work Packet 04 owns this table; domain packets build adapters/projections on top,
never a parallel core". A P06 lane pinning the defect is in scope; a P06 lane changing
P04's canonical timestamp contract is not.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import jsonschema
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

from research_os.models.claim import ClaimTime  # noqa: E402
from research_os.primitives import ValidTime  # noqa: E402

# Arbitrary, fixed, and irrelevant to every assertion here — `ClaimTime` requires it.
_RECORDED_AT = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _instant(microsecond: int) -> datetime:
    return datetime(2026, 1, 15, 0, 0, 0, microsecond, tzinfo=timezone.utc)


def _claim_time_payload(microsecond: int) -> dict[str, object]:
    """Exactly what the sanctioned write path puts in `payload['time']`."""

    return ClaimTime(valid_from=_instant(microsecond), recorded_at=_RECORDED_AT).model_dump(
        mode="json"
    )


def _at(microsecond: int) -> str:
    """The canonical TEXT the real model emits for `valid_from`."""

    return str(_claim_time_payload(microsecond)["valid_from"])


# One second, three instants, all produced by the REAL canonical model. EARLIEST first.
_ZERO_US = _at(0)
_QUARTER = _at(250_000)
_HALF = _at(500_000)

# The three spellings the FIRST version of this module was built on. Kept because the
# hazard they describe is real for a producer that does not route through pydantic.
_RAW_Z = "2026-01-15T00:00:00Z"
_RAW_OFFSET = "2026-01-15T00:00:00+00:00"
_RAW_FRACTIONAL = "2026-01-15T00:00:00.000Z"


def test_the_compliant_write_path_canonicalises_the_three_spellings() -> None:
    """Pins the first correction, so the record cannot silently revert.

    If this goes red, `UtcDateTime` has stopped normalising and the original (weaker, but
    then LIVE) three-spelling framing applies again on top of everything below.

    The expected value is DERIVED, not the literal `...T00:00:00Z`. A round-2 refuter
    caught the literal form failing under a fixed-width cure — canonicalisation still
    worked, the hardcoded expectation was simply coupled to the old representation, and it
    was counted as a fifth "red" when it was collateral. This assertion is about COLLAPSE,
    so it must survive any cure that keeps collapsing.
    """

    canonical = {
        str(
            ClaimTime(valid_from=raw, recorded_at=_RECORDED_AT).model_dump(mode="json")[
                "valid_from"
            ]
        )
        for raw in (_RAW_Z, _RAW_OFFSET, _RAW_FRACTIONAL)
    }
    assert len(canonical) == 1, f"the three spellings no longer collapse: {canonical}"
    assert canonical == {_at(0)}, "collapsed, but not onto the model's own zero-microsecond form"


def test_the_real_canonical_models_omit_the_fraction_at_microsecond_zero() -> None:
    """The structural fact the whole defect rests on: the fraction is OPTIONAL.

    Asserted on BOTH canonical time models, so the finding cannot be dismissed as a quirk
    of whichever one a reader happens to open, and across the width of the field.
    """

    assert "." not in _ZERO_US, _ZERO_US
    assert _at(1).endswith(".000001Z")
    assert _HALF.endswith(".500000Z")

    # `ValidTime` is the generic bitemporal primitive; `ClaimTime` is what a NAGA claim
    # carries. They must agree, or the defect would be model-specific.
    for microsecond in (0, 500_000):
        generic = ValidTime(valid_from=_instant(microsecond), valid_to=None).model_dump(
            mode="json"
        )["valid_from"]
        assert generic == _at(microsecond)


def test_canonical_order_inverts_inside_a_single_second() -> None:
    """THE defect, reachable with no misbehaviour: two compliant writes, wrong order.

    `.` is 0x2E, `Z` is 0x5A. The instant at microsecond zero is chronologically FIRST
    and lexicographically LAST, so `ORDER BY payload->'time'->>'valid_from'` returns the
    interval's own lower bound out of place.
    """

    assert _instant(0) < _instant(500_000), "premise: two instants, in this order"
    assert not (_ZERO_US < _HALF), "text order agreed with the clock — see module docstring"


def test_a_half_open_lower_bound_drops_a_row_at_the_boundary() -> None:
    """The failure mode, stated as the predicate a bitemporal store actually runs.

    `valid_from <= T` with both sides produced by the compliant serialiser does NOT admit
    a row whose `valid_from` fell on a whole second, although it precedes `T`.
    """

    assert _instant(0) <= _instant(250_000), "premise: the row IS inside, by the clock"
    assert not (_ZERO_US <= _QUARTER), "text agreed with the clock — see module docstring"


def test_the_published_schema_permits_both_terminators_and_is_silent_on_width() -> None:
    """The three-spelling hazard is not "a misbehaving writer" — the CONTRACT grants it.

    `_UTC_OFFSET_PATTERN` (`primitives.py:84`) reaches the emitted JSON Schema through a
    `WithJsonSchema` block, so it documents the published contract rather than validating
    input. Validated here against the REAL schema with a real validator, not asserted in
    prose: an independent producer building against it is entitled to both terminators and
    to any sub-second width.
    """

    schema = ClaimTime.model_json_schema()

    # Both terminators, and sub-second widths from none to nine digits. The width range is
    # deliberate: an earlier version tested only 0, 3 and 6 digits while the docstring
    # claimed "any width", which a round-2 refuter correctly called an over-claim — a
    # pattern admitting exactly those three would have kept it green.
    for text in (
        _RAW_Z,
        _RAW_OFFSET,
        _RAW_FRACTIONAL,
        _HALF,
        "2026-01-15T00:00:00.1Z",
        "2026-01-15T00:00:00.123456789Z",
        "2026-01-15T00:00:00.5+00:00",
    ):
        jsonschema.validate({"valid_from": text, "recorded_at": _RAW_Z}, schema)

    # Guilt control: without it the loop above would pass just as happily against a schema
    # that constrains nothing at all. `+0000` violates the published pattern and MUST be
    # refused, which is what proves the pattern is being enforced rather than ignored.
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {"valid_from": "2026-01-15T00:00:00+0000", "recorded_at": _RAW_Z}, schema
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_returns_stored_rows_in_the_wrong_order(
    db_tx: asyncpg.Connection,
) -> None:
    """End-to-end: real JSONB rows, the real `->>` expression, the wrong answer.

    This is the assertion the earlier version of this module only CLAIMED to make. It
    compared text parameters that never reached a payload, which proves how PostgreSQL
    compares two strings — not that a stored object comes back out of order.
    """

    await db_tx.execute("CREATE TEMP TABLE valid_time_rows (payload jsonb NOT NULL) ON COMMIT DROP")
    # Inserted deliberately out of order, so a passing result cannot be insertion order.
    for microsecond in (500_000, 0, 250_000):
        await db_tx.execute(
            "INSERT INTO valid_time_rows (payload) VALUES ($1::jsonb)",
            json.dumps({"time": _claim_time_payload(microsecond)}),
        )

    rows = await db_tx.fetch(
        "SELECT payload -> 'time' ->> 'valid_from' AS vf FROM valid_time_rows "
        "ORDER BY payload -> 'time' ->> 'valid_from'"
    )
    got = [r["vf"] for r in rows]

    # One assertion, not two: `got != chronological` is implied by the equality below, and
    # a round-2 refuter correctly called the pair redundant. The message carries what the
    # weaker assertion used to say, so a future reader still learns what a red means here.
    assert got == [_QUARTER, _HALF, _ZERO_US], (
        f"expected the earliest row ({_ZERO_US}) to sort LAST, got {got!r}. If this now "
        "returns chronological order, the sub-second width may have been pinned on write "
        "and this whole module should be deleted."
    )

    # The same defect as the predicate a bitemporal read actually runs. By the clock two
    # rows precede the cutoff; the text comparison admits one and silently drops the other.
    admitted = await db_tx.fetchval(
        "SELECT count(*) FROM valid_time_rows WHERE payload -> 'time' ->> 'valid_from' <= $1",
        _QUARTER,
    )
    assert admitted == 1, (
        f"expected the whole-second row to be silently dropped, {admitted} rows admitted"
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
