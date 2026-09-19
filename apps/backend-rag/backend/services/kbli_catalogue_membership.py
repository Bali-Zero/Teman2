"""Is this KBLI code in the KBLI 2025 catalogue at all?

`inspect_kbli` resolves a code against `kg_nodes.entity_id = 'kbli:<code>'`. The graph
holds MORE codes than KBLI 2025 does: measured on prod 2026-09-19, 1,568 such nodes exist
and 1,558 are canonical. The other ten are KBLI-2020 numbers the 2025 revision does not
carry, and every one of them was answered with a normal 200 — `74100` as
`licensing_status: REGULATED` with a `PT PMA` entity-form requirement, `26120` with a full
semiconductor description and six related codes — so a client who typed a number read a
plausible answer about an activity they cannot register.

Four of the ten already carried `licensing_status = NOT_IN_KBLI_2025`, written by
`backend/scripts/kbli_documents_phantom_cure.py`. The router does not INTERPRET that label:
it reaches the client only because `licensing_status` is passed through verbatim, as an
undocumented enum on a page whose title, description and related codes all still read like
a live activity. A label nothing consumes is not a cure, which is why the verdict is
computed here and applied at read time rather than trusted from a property.

WHERE THE TRUTH LIVES. The membership test is a DATABASE question, not a file question.
`kbli_documents` minus the rows already labelled `NOT_IN_KBLI_2025` is EXACTLY the
canonical 1,559 — verified in both directions on prod, zero elements on either side of the
difference. So the router answers it on the connection it already holds. Shipping the
canonical JSON into the container would have created a second source of truth free to
drift from the first, and a request-time file read besides.

WHICH WAY THIS FAILS. A naive membership test turns every code into a phantom the moment
the catalogue table is unreadable — 1,559 tombstones from one bad deploy, which is a far
worse failure than the ten codes it set out to fix. So absence of a row is evidence only
when the catalogue is evidently PRESENT: the size comes back in the same round trip and
below `CATALOGUE_FLOOR` the verdict is `UNKNOWN` and the caller changes nothing. The
asymmetry is deliberate — we would rather keep serving ten phantoms than erase a catalogue.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

# The value `kbli_documents_phantom_cure.py` writes for a code it has proven absent.
# Duplicated rather than imported: this is a request-time service and that is a one-shot
# operator script. `test_kbli_catalogue_membership.py` asserts the two stay equal, so the
# duplication cannot drift silently.
PHANTOM_LICENSING_STATUS: Final = "NOT_IN_KBLI_2025"

# Below this many rows the catalogue is not credible enough to convict a code of not
# existing. The live table holds 1,563 (1,559 canonical + 4 already-labelled phantoms);
# the floor sits far enough below that a partial load or a truncated table trips it while
# ordinary catalogue churn never does.
CATALOGUE_FLOOR: Final = 1_000

CANONICAL: Final = "CANONICAL"
ABSENT: Final = "ABSENT"
UNKNOWN: Final = "UNKNOWN"

# One round trip, two answers: how big the catalogue is, and whether this code is in it.
# Asked with `fetch` (not `fetchval`/`fetchrow`) on purpose — see the module test for why
# the shape matters to callers' fakes.
CATALOGUE_MEMBERSHIP_QUERY: Final = """
    SELECT
        (SELECT count(*) FROM kbli_documents) AS catalogue_size,
        (SELECT count(*) FROM kbli_documents
          WHERE kode_kbli = $1
            AND coalesce(metadata->>'licensing_status', '') <> $2) AS canonical_rows
"""


def catalogue_verdict(rows: Sequence[Any] | None) -> str:
    """Read the membership query's result.

    `UNKNOWN` whenever the answer is not legible — no rows, a missing key, a
    non-integer count, or a catalogue below the floor. Only a legible answer from an
    evidently-present catalogue can return `ABSENT`.
    """
    if not rows:
        return UNKNOWN

    row = rows[0]
    try:
        size = int(row["catalogue_size"])
        present = int(row["canonical_rows"])
    except (KeyError, TypeError, ValueError, IndexError):
        return UNKNOWN

    if size < CATALOGUE_FLOOR:
        return UNKNOWN
    return CANONICAL if present > 0 else ABSENT


def is_absent_from_catalogue(rows: Sequence[Any] | None) -> bool:
    """True only on a positive finding of absence. `UNKNOWN` is not absence."""
    return catalogue_verdict(rows) == ABSENT


# What the client reads instead of a licensing answer. Stated as OUR catalogue's finding:
# we can say a number is not in the KBLI 2025 catalogue we hold, and we say where to look
# next. We do NOT name a successor code — the 2020→2025 crosswalk is not in our data, and
# semantic search already answers it (searching "hotel bintang lima" returns 55101, the
# real 2025 code, not the phantom 55111).
TOMBSTONE_DESCRIPTION: Final = (
    "This code is not in the KBLI 2025 catalogue. It is a KBLI 2020 number that the 2025 "
    "revision does not carry, so it cannot be registered on OSS today, and no licensing, "
    "risk or ownership answer is given for it. Search by business activity to find the "
    "KBLI 2025 code that covers what you do. — Kode ini tidak ada dalam KBLI 2025."
)

# Appended to the node's own name so the title cannot be mistaken for a live activity.
# Same wording as `kbli_documents_phantom_cure.py`'s `VINTAGE_SUFFIX`, asserted equal by
# the module test.
TOMBSTONE_TITLE_SUFFIX: Final = " [KBLI 2020 — tidak ada dalam KBLI 2025]"

# `risk_profile` is a plain string on the wire. "Unknown" would read as "we did not look";
# this reads as "the question does not apply".
TOMBSTONE_RISK_PROFILE: Final = "Not applicable — code absent from KBLI 2025"
