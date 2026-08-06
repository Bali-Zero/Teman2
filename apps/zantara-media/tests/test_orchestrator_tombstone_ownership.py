"""A deletion with no file resource cannot be attributed, and was archived anyway.

TRAUMA (measured on Pro, 2026-08-06, the first run after the GARUDA credential
was repaired — the run this test exists because of):

    24,687 changes processed, every one of them a tombstone
    24,686 Qdrant writes answered HTTP 404
         1 write succeeded
    6h 00m wall clock, and `run_indexer` returned a success dict

`garuda_assets` holds **0 points**. It never held those files, because they
were never GARUDA files: Drive reports a *removal* with no file resource, so
the change carries no parents, so the `if change.file and not
is_under_garuda(...)` filter one branch above could not judge it and let it
fall straight through. Every deletion anywhere in that Drive account arrived
at the tombstone branch wearing a GARUDA badge.

The per-call code was not wrong to be quiet — `qdrant_writer.mark_archived`
swallows a 404 deliberately ("point never indexed, not an error"). The defect
is that nobody counted. One 404 is bookkeeping; 24,686 in a row is the organ
telling you it has no subject, and the run reported success on top of it.

    GUILT      — a removal for a file the index never held is NOT ours
    INNOCENCE  — a removal for a file the index DOES hold still is
    INNOCENCE  — a trashed file keeps its parents, is filtered upstream, and
                 must never be sent to the index for a second opinion
"""

from __future__ import annotations

import asyncio

from zantara_media.indexer.drive_client import Change, DriveFile
from zantara_media.indexer.orchestrator import tombstone_is_ours


class _Index:
    """Stub for the Postgres writer: only the membership question it answers."""

    def __init__(self, known: dict[str, int] | None = None) -> None:
        self.known = known or {}
        self.asked: list[str] = []

    async def get_drive_version(self, file_id: str):
        self.asked.append(file_id)
        return self.known.get(file_id)


def _removal(file_id: str) -> Change:
    """What Drive sends for a deletion: an id, and nothing else."""
    return Change(
        change_type="file",
        file_id=file_id,
        file=None,
        removed=True,
        is_tombstone=True,
    )


def _trashed(file_id: str) -> Change:
    """A trashed file keeps its resource — and therefore its parents."""
    f = DriveFile(
        id=file_id,
        name="whatever.jpg",
        mime_type="image/jpeg",
        parents=["1c9QnRb22XdcrFH8ukxgJeWW41soZhzVq"],
        size=1,
        modified_time=None,  # unused by the rule under test
        version=3,
        trashed=True,
    )
    return Change(
        change_type="file",
        file_id=file_id,
        file=f,
        removed=False,
        is_tombstone=True,
    )


# ------------------------------------------------------------------- guilt
def test_a_removal_we_never_indexed_is_not_ours():
    """The 24,686. Nothing about the change says GARUDA, and the index has
    never heard of it — archiving it is a write with no subject."""
    idx = _Index()
    assert asyncio.run(tombstone_is_ours(_removal("1oRalm9UmOSq"), idx)) is False
    assert idx.asked == ["1oRalm9UmOSq"], "the index must actually be consulted"


# --------------------------------------------------------------- innocence
def test_a_removal_of_a_file_we_did_index_is_ours():
    """The whole point of tombstones. Narrowing must not cost us the real
    ones: a file this index holds, then deleted in Drive, must be archived."""
    idx = _Index({"1realGarudaAsset": 7})
    assert asyncio.run(tombstone_is_ours(_removal("1realGarudaAsset"), idx)) is True


def test_a_trashed_file_is_ours_without_asking_the_index():
    """It still carries its parents, so `is_under_garuda` upstream has already
    ruled. Asking again would be a second opinion on a settled question — and
    on a first run, before anything is indexed, it would answer NO and throw
    away the tombstone for a file we are about to stop tracking."""
    idx = _Index()
    assert asyncio.run(tombstone_is_ours(_trashed("1trashedButOurs"), idx)) is True
    assert idx.asked == [], "the index was consulted about an attributable change"


def test_a_version_of_zero_still_counts_as_held():
    """`0` is a version, not an absence. A truthiness test here would disown
    every file the index recorded at version 0 — the falsy-vs-None trap."""
    idx = _Index({"1zeroVersion": 0})
    assert asyncio.run(tombstone_is_ours(_removal("1zeroVersion"), idx)) is True
