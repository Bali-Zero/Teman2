"""The prod-Postgres backup has THREE nested wall-clock caps, and the outermost one wins.

`cron-wrapper.sh` wraps the whole job in `gtimeout <per-job default>`; inside it,
`fly-pg-backup.sh` caps the dump with `DUMP_TIMEOUT` and the download with `SFTP_TIMEOUT`.
If the outer cap is not larger than the sum of the inner ones, the inner caps are decoration:
the wrapper kills the job before they can ever fire, and raising them changes nothing.

That is not hypothetical. On 2026-07-26 all three were 900: the dump alone measured ~815s
(~570-660 KB/s on an unchanged 2749MB database, with exactly one pg_dump alive on the machine
and the primary's own `cpu` health check failing), leaving ~85s for an SFTP + Tigris upload +
gunzip verify that historically need ~90s. Raising only `DUMP_TIMEOUT` would have looked like a
fix and changed nothing at all.

These tests assert the ORDERING, not the specific numbers — the numbers are free to move as the
machine's speed changes; what must never regress is that the outer cap can accommodate the inner
ones. Guilt (an inverted pair is caught) and innocence (the real files pass) are both asserted,
because a check that only ever sees the passing case proves nothing about what it would reject.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CRON_WRAPPER = REPO_ROOT / "scripts" / "cron-wrapper.sh"
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "fly-pg-backup.sh"

# Anchored so a value mentioned in prose or in another job's row cannot be mistaken for the
# assignment (the substring-instead-of-entity failure this repo files under superscar #3).
_OUTER_RE = re.compile(r"^\s*fly_pg_backup\)\s*_job_default=(\d+)\s*;;", re.M)
_INNER_RE = r"^{name}=(\d+)"


def _outer_cap(text: str) -> int:
    matches = _OUTER_RE.findall(text)
    assert matches, "no `fly_pg_backup) _job_default=<n>` row found in cron-wrapper.sh"
    assert len(matches) == 1, f"ambiguous: {len(matches)} fly_pg_backup rows, expected exactly 1"
    return int(matches[0])


def _inner_cap(text: str, name: str) -> int:
    matches = re.findall(_INNER_RE.format(name=name), text, re.M)
    assert matches, f"no `{name}=<n>` assignment found in fly-pg-backup.sh"
    assert len(matches) == 1, f"ambiguous: {len(matches)} {name} assignments, expected exactly 1"
    return int(matches[0])


def _violates(outer: int, dump: int, sftp: int) -> bool:
    """True when the outer cap cannot accommodate the inner ones (inner caps are decoration)."""
    return outer < dump + sftp


def test_outer_cap_can_accommodate_both_inner_caps() -> None:
    """INNOCENCE: the caps as actually committed are coherent."""
    outer = _outer_cap(CRON_WRAPPER.read_text())
    backup = BACKUP_SCRIPT.read_text()
    dump = _inner_cap(backup, "DUMP_TIMEOUT")
    sftp = _inner_cap(backup, "SFTP_TIMEOUT")

    assert not _violates(outer, dump, sftp), (
        f"cron-wrapper's fly_pg_backup cap ({outer}s) is below DUMP_TIMEOUT ({dump}s) + "
        f"SFTP_TIMEOUT ({sftp}s) = {dump + sftp}s. The wrapper fires first, so the inner "
        f"caps can never be reached and raising them is a no-op."
    )


def test_inverted_pair_is_caught() -> None:
    """GUILT: the exact shape that shipped on 2026-07-26 is rejected."""
    assert _violates(outer=900, dump=900, sftp=900)
    # and the near-miss that motivated this file: inner raised, outer forgotten
    assert _violates(outer=900, dump=2400, sftp=900)


def test_dump_cap_covers_the_slowest_observed_run() -> None:
    """A ceiling below a MEASURED duration is a scheduled failure, not a safety margin.

    ~815s was observed on 2026-07-26 with a single dump running; the cap must clear it with
    room, since that day was not the worst a shared-cpu machine can do.
    """
    dump = _inner_cap(BACKUP_SCRIPT.read_text(), "DUMP_TIMEOUT")
    assert dump >= 1600, (
        f"DUMP_TIMEOUT={dump}s leaves no margin over the ~815s dump measured 2026-07-26; "
        f"a 2x slower day would kill the backup at ~97% of the work."
    )


def test_parsers_reject_ambiguity_rather_than_guessing() -> None:
    """A parser that silently picks the first of several matches is a proxy that can lie."""
    two_rows = "    fly_pg_backup)      _job_default=900 ;;\n    fly_pg_backup)      _job_default=99 ;;\n"
    try:
        _outer_cap(two_rows)
    except AssertionError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("two conflicting rows were silently resolved instead of rejected")

    # prose mentioning the name must not be read as an assignment
    prose_only = "# DUMP_TIMEOUT=900 was the old value\n"
    try:
        _inner_cap(prose_only, "DUMP_TIMEOUT")
    except AssertionError as exc:
        assert "no `DUMP_TIMEOUT=<n>` assignment" in str(exc)
    else:
        raise AssertionError("a commented-out value was read as the live assignment")
