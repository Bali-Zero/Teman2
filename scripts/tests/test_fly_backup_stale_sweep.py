"""fly-pg-backup.sh must sweep stale dumps off the primary's volume BEFORE dumping.

Measured 2026-09-10: 18 `nuz-backup-*.sql.gz` (6.6 GB, 2026-06-06 .. 2026-08-29) plus
their `.err` twins were still on the primary's /data — every one left by a run that was
killed before its own step-1c cleanup. The primary sat at 45% volume use against 16% on
the replicas, and Fly's disk-capacity check flips the primary read-only at 90%.

These tests pin the sweep's SHAPE, not its wording: it runs before the dump, it targets
only `/data/nuz-backup-*` at depth 1, it never touches files younger than a day (a
concurrent run's fresh dump is safe), and its count is logged so the nightly log can
prove it bit. Guilt and innocence both asserted (superscar #3).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "fly-pg-backup.sh"

_FIND_DELETE_RE = re.compile(
    r"find /data -maxdepth 1 -name \\\"nuz-backup-\*\\\" -mtime \+0 -delete"
)
_FIND_LIST_RE = re.compile(
    r"find /data -maxdepth 1 -name \\\"nuz-backup-\*\\\" -mtime \+0 -print"
)
_DUMP_ANCHOR = "# Step 1: pg_dump inside the primary"
_SWEEP_ANCHOR = "# Step 0: sweep stale dumps"


def _script() -> str:
    return BACKUP_SCRIPT.read_text(encoding="utf-8")


def _assert_sweep_shape(text: str) -> None:
    assert _SWEEP_ANCHOR in text, "no stale-dump sweep section"
    assert text.index(_SWEEP_ANCHOR) < text.index(_DUMP_ANCHOR), (
        "sweep must run before the dump"
    )
    assert len(_FIND_LIST_RE.findall(text)) == 1, "exactly one bounded stale listing"
    assert len(_FIND_DELETE_RE.findall(text)) == 1, "exactly one bounded stale delete"
    assert 'log "Sweeping $STALE_COUNT stale dump artefact(s)' in text, (
        "count must be logged"
    )
    # The delete is the ONLY unbounded-in-scope rm on the primary: any other
    # `-delete`/`rm -rf` under /data would widen the blast radius past the
    # backup's own artefacts.
    assert "rm -rf /data" not in text
    assert text.count("-delete") == 1


def test_real_script_sweeps_stale_dumps_before_dumping() -> None:
    _assert_sweep_shape(_script())


def test_sweep_never_touches_a_fresh_dump() -> None:
    text = _script()
    for match in (_FIND_LIST_RE, _FIND_DELETE_RE):
        assert "-mtime +0" in match.pattern.replace("\\+", "+")
    assert "-mtime -1" not in text
    assert "-mmin" not in text


def test_script_without_sweep_is_caught() -> None:
    text = _script()
    start = text.index(_SWEEP_ANCHOR)
    end = text.index(_DUMP_ANCHOR)
    stripped = text[:start] + text[end:]
    try:
        _assert_sweep_shape(stripped)
    except AssertionError as exc:
        assert "no stale-dump sweep section" in str(exc)
    else:  # pragma: no cover - guilt case must fail
        raise AssertionError("a script without the sweep passed the shape check")


def test_sweep_after_dump_is_caught() -> None:
    text = _script()
    start = text.index(_SWEEP_ANCHOR)
    end = text.index(_DUMP_ANCHOR)
    sweep_block = text[start:end]
    moved = text[:start] + text[end:] + "\n" + sweep_block
    try:
        _assert_sweep_shape(moved)
    except AssertionError as exc:
        assert "sweep must run before the dump" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("a sweep placed after the dump passed the shape check")
