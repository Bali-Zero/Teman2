"""Per-record source-read ledger (ledger L1736).

`fold_pack_seq17.py` proved the failure mode: ``RESTAMP_VERIFIED_AT`` was a
Python constant the fold script *asserted*, unprovable from the artifact --
nothing on disk showed anyone actually looked at any of the 18 portals at
that instant. The fix is procedural, not a patch to that already-shipped
fold: write the evidence DURING the reading, one line per source record
(the URL, the HTTP status observed, the sentence checked against the pack's
rule text, and the clock), so ``verified_at`` becomes the timestamp of a
file that already exists rather than a constant a script asserts.

Usage in the next portal re-attestation: as each source is read, call
``append_entry`` once per record. When folding the next RulePack sequence,
``verified_at_from_ledger`` derives the stamp from those entries -- the
EARLIEST reader's instant across every record being attested, never the
latest, and never a hand-picked constant -- and raises if any required
record has no entry, so a fold can never attest a source nobody actually
read.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SourceReadEntry:
    source_record_id: str
    url: str
    http_status: int
    checked_sentence: str
    read_at: str  # ISO 8601, UTC, e.g. "2026-08-30T13:16:40Z"

    def __post_init__(self) -> None:
        if not self.source_record_id:
            raise ValueError("source_record_id is required")
        if not self.url:
            raise ValueError("url is required")
        if not (100 <= self.http_status <= 599):
            raise ValueError(f"http_status out of range: {self.http_status}")
        if not self.checked_sentence.strip():
            raise ValueError(
                "checked_sentence is required -- the entry must name what was checked"
            )
        _parse_instant(self.read_at)  # raises if unparseable/naive


def _parse_instant(value: str) -> datetime:
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"read_at is not a valid ISO 8601 instant: {value!r}") from exc
    if instant.tzinfo is None:
        raise ValueError(f"read_at must be timezone-aware: {value!r}")
    return instant.astimezone(timezone.utc)


def append_entry(ledger_path: Path, entry: SourceReadEntry) -> None:
    """Appends one JSON line. The ledger FILE is the evidence -- a fold reads
    it back rather than trusting a value asserted in Python."""
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry), sort_keys=True) + "\n")


def read_entries(ledger_path: Path) -> list[SourceReadEntry]:
    entries: list[SourceReadEntry] = []
    with ledger_path.open(encoding="utf-8") as fh:
        for line_number, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{ledger_path}:{line_number}: not valid JSON") from exc
            entries.append(SourceReadEntry(**raw))
    return entries


def verified_at_from_ledger(ledger_path: Path, record_ids: set[str] | frozenset[str]) -> str:
    """Returns the EARLIEST ``read_at`` among the ledger's entries for
    ``record_ids`` -- never the latest: a re-attestation is only as fresh as
    its slowest reader, and stamping the latest would claim currency for a
    record nobody re-checked at that instant.

    Raises if any of ``record_ids`` has no ledger entry (nothing was written
    for it -- a fold must never attest a source that was not read), or if the
    ledger carries two entries for the same record with DIFFERENT ``read_at``
    values (ambiguous evidence must never be silently resolved by picking one).
    """
    entries = read_entries(ledger_path)
    stamps_by_record: dict[str, set[str]] = {}
    for entry in entries:
        stamps_by_record.setdefault(entry.source_record_id, set()).add(entry.read_at)

    missing = sorted(set(record_ids) - stamps_by_record.keys())
    if missing:
        raise ValueError(f"no ledger entry for source record(s): {missing}")

    ambiguous = {
        rid: sorted(stamps)
        for rid, stamps in stamps_by_record.items()
        if rid in record_ids and len(stamps) > 1
    }
    if ambiguous:
        raise ValueError(f"conflicting read_at values for source record(s): {ambiguous}")

    earliest = min(
        _parse_instant(next(iter(stamps_by_record[rid]))) for rid in record_ids
    )
    return earliest.strftime("%Y-%m-%dT%H:%M:%SZ")
