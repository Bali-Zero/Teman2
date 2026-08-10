#!/usr/bin/env python3
"""intake_gate_count_pusher: empty-email rows must be discarded, LOUDLY (W97).

THE DEFECT THIS EXISTS TO CATCH (measured live 2026-08-08):

`_compute_counts()`'s SQL guards `q.received_by IS NOT NULL` but NOT
`received_by <> ''` — an empty string is not NULL. Live `nuzantara_dev` carries
43 `intake_queue` rows with `received_by = ''` (unrouted/unassigned documents)
alongside 5846 rows with a real receiver, out of 5889 matching the gate
predicate (measured via a fresh read-only COUNT query, 2026-08-08). The pusher
built one payload item per row, including `{"user_email": "", ...}`, and
POSTed the whole list to the Fly bridge. FastAPI/Pydantic validates the
request body atomically (`DocCountItem.user_email` has `min_length=1`), so
ONE bad empty-email item 422s the ENTIRE push — not just that one row. Live
log evidence: `~/logs/intake-gate-count-pusher.log` shows this cron (every
300s) has 422'd continuously since at least 2026-08-07 22:28 WITA, meaning
EVERY real worker's gate-1 doc count silently stopped syncing to Fly.

THE FIX: `_filter_valid_rows()` splits query rows into valid (non-empty
`user_email` after `.strip()`) and discarded (empty/blank), and returns only
the valid list — WITH a `logger.warning` naming the discarded count (never a
silent list-shrink, per superscar #2 "W97 display-cap + pipe-mask": a filter
that shrinks a list must say "N of M discarded", not just shrink it quietly).

WHAT THIS ASSERTS
  1. GUILT — a row with `user_email = ""` (or whitespace-only) is dropped
     from the returned list, and the discard is logged via `logger.warning`
     with the discarded/total counts.
  2. INNOCENCE — rows with real, non-empty emails pass through UNCHANGED
     (email lowercased/stripped as the SQL already guarantees, pending_count
     preserved as int), and NO warning fires when nothing was discarded.
  3. Mixed batch: discarding one row's worth of noise must not touch a
     sibling row's own valid email/count (no cross-row bleed).

No live DB needed — `_filter_valid_rows` takes plain dict "rows" (asyncpg.Record
supports the same `row["col"]` mapping access this test exercises).

Run:  python3 scripts/tests/test_intake_gate_count_pusher.py
      pytest scripts/tests/test_intake_gate_count_pusher.py -q
"""

from __future__ import annotations

import logging
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from intake_gate_count_pusher import _filter_valid_rows  # noqa: E402


def test_guilt_empty_user_email_discarded_and_logged(caplog):
    """A row with an empty-string user_email is dropped, and the drop is logged."""
    rows = [
        {"user_email": "", "pending_count": 7},
    ]
    with caplog.at_level(logging.WARNING, logger="intake_gate_count_pusher"):
        result = _filter_valid_rows(rows)

    assert result == [], "empty-email row must NOT reach the push payload"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "discard must be LOGGED (W97) — silent shrink is the bug this fixes"
    assert "discarded 1/1" in warnings[0].getMessage()


def test_guilt_whitespace_only_user_email_discarded():
    """Whitespace-only ('   ') is blank too — .strip() must catch it, not just ''."""
    rows = [{"user_email": "   ", "pending_count": 3}]
    result = _filter_valid_rows(rows)
    assert result == []


def test_guilt_null_user_email_discarded():
    """Defense-in-depth: a None user_email (shouldn't happen post-SQL-filter,
    but the Python filter must not crash or admit it) is treated as blank."""
    rows = [{"user_email": None, "pending_count": 1}]
    result = _filter_valid_rows(rows)
    assert result == []


def test_innocence_real_emails_pass_through_unchanged(caplog):
    """Non-empty emails and their counts survive the filter untouched, and
    NO warning fires when there is nothing to discard."""
    rows = [
        {"user_email": "worker.one@balizero.com", "pending_count": 4},
        {"user_email": "worker.two@balizero.com", "pending_count": 0},
    ]
    with caplog.at_level(logging.WARNING, logger="intake_gate_count_pusher"):
        result = _filter_valid_rows(rows)

    assert result == [
        {"user_email": "worker.one@balizero.com", "pending_count": 4},
        {"user_email": "worker.two@balizero.com", "pending_count": 0},
    ]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert not warnings, "no discard happened — must NOT log a spurious warning"


def test_mixed_batch_discard_does_not_bleed_into_sibling_row():
    """One empty-email row among several valid ones: only the bad row is
    dropped, valid siblings keep their own email/count exactly."""
    rows = [
        {"user_email": "alice@balizero.com", "pending_count": 2},
        {"user_email": "", "pending_count": 99},
        {"user_email": "bob@balizero.com", "pending_count": 5},
    ]
    result = _filter_valid_rows(rows)

    assert result == [
        {"user_email": "alice@balizero.com", "pending_count": 2},
        {"user_email": "bob@balizero.com", "pending_count": 5},
    ]


def test_pending_count_is_coerced_to_int():
    """asyncpg returns count(*) as a native int already, but the filter must
    not silently accept a non-int without normalizing — mirrors the
    pre-existing `int(r["pending_count"])` cast in _compute_counts."""
    rows = [{"user_email": "carol@balizero.com", "pending_count": "8"}]
    result = _filter_valid_rows(rows)
    assert result == [{"user_email": "carol@balizero.com", "pending_count": 8}]
    assert isinstance(result[0]["pending_count"], int)


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
