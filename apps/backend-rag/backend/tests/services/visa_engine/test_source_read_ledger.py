"""L1736: `verified_at` must come from evidence written during the read, not
from a constant a fold script asserts. Pins the ledger primitive that lets
the NEXT RulePack re-attestation (seq-18+) derive its stamp that way.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.visa_engine.source_read_ledger import (
    SourceReadEntry,
    append_entry,
    read_entries,
    verified_at_from_ledger,
)


def _entry(record_id: str, read_at: str, **overrides: object) -> SourceReadEntry:
    defaults = dict(
        source_record_id=record_id,
        url="https://imigrasi.go.id/e31b/daftar-visa-indonesia",
        http_status=200,
        checked_sentence="C1 Tourism Extension requires an active passport with 6 months validity.",
        read_at=read_at,
    )
    defaults.update(overrides)
    return SourceReadEntry(**defaults)  # type: ignore[arg-type]


def test_entry_rejects_missing_checked_sentence() -> None:
    with pytest.raises(ValueError, match="checked_sentence"):
        _entry("r1", "2026-08-30T13:16:40Z", checked_sentence="   ")


def test_entry_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _entry("r1", "2026-08-30T13:16:40")


def test_entry_rejects_bad_http_status() -> None:
    with pytest.raises(ValueError, match="http_status"):
        _entry("r1", "2026-08-30T13:16:40Z", http_status=999)


def test_append_and_read_round_trips(tmp_path: Path) -> None:
    ledger = tmp_path / "seq18-read-ledger.jsonl"
    e1 = _entry("r1", "2026-08-30T13:16:40Z")
    e2 = _entry("r2", "2026-08-30T13:17:05Z", url="https://imigrasi.go.id/e33")

    append_entry(ledger, e1)
    append_entry(ledger, e2)

    got = read_entries(ledger)
    assert got == [e1, e2]


def test_verified_at_is_the_earliest_reader_not_the_latest(tmp_path: Path) -> None:
    """The bug this closes: a re-stamp must never claim the LATEST read's
    freshness for a record actually read earlier."""
    ledger = tmp_path / "ledger.jsonl"
    append_entry(ledger, _entry("r1", "2026-08-30T13:16:40Z"))
    append_entry(ledger, _entry("r2", "2026-08-30T13:20:00Z"))  # read later
    append_entry(ledger, _entry("r3", "2026-08-30T09:00:00Z"))  # read earliest

    stamp = verified_at_from_ledger(ledger, {"r1", "r2", "r3"})

    assert stamp == "2026-08-30T09:00:00Z"


def test_verified_at_raises_when_a_record_was_never_read(tmp_path: Path) -> None:
    """The exact class of bug L1736 names: a fold must never attest a source
    nobody actually read -- an asserted constant could always claim it was."""
    ledger = tmp_path / "ledger.jsonl"
    append_entry(ledger, _entry("r1", "2026-08-30T13:16:40Z"))

    with pytest.raises(ValueError, match="no ledger entry"):
        verified_at_from_ledger(ledger, {"r1", "r2"})


def test_verified_at_raises_on_conflicting_entries_for_the_same_record(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    append_entry(ledger, _entry("r1", "2026-08-30T13:16:40Z"))
    append_entry(ledger, _entry("r1", "2026-08-30T14:00:00Z"))  # re-read, different clock

    with pytest.raises(ValueError, match="conflicting"):
        verified_at_from_ledger(ledger, {"r1"})


def test_read_entries_raises_on_malformed_line(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("not json\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        read_entries(ledger)
