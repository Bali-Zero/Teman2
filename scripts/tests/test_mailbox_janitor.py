"""Tests for scripts/mailbox_janitor.py — the mailbox's only deleter.

Every scenario is driven through `run(...)` with an explicit `now` so age
math is deterministic; one test drives `main([...])` end to end to cover the
CLI/JSON/receipt surface.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mailbox_janitor as mj  # noqa: E402

NOW = 1_800_000_000.0  # fixed epoch used as "now" across tests
DAY = 86400.0


def _ts(epoch: float) -> str:
    return time.strftime("%Y%m%dT%H%M%S", time.gmtime(epoch))


def _touch(path: Path, *, mtime: float = None, content: str = "x") -> Path:
    path.write_text(content, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _session_dir(root: Path, name: str, *, mtime: float = None) -> Path:
    d = root / name
    d.mkdir(mode=0o700)
    if mtime is not None:
        os.utime(d, (mtime, mtime))
    return d


def _freeze_mtime(path: Path, mtime: float) -> None:
    """Set a directory's mtime as the LAST setup step — creating or writing
    a child file bumps the parent directory's mtime to wall-clock "now",
    which would silently override any earlier os.utime() on the dir."""
    os.utime(path, (mtime, mtime))


def test_live_md_kept_in_broadcast_and_session(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()
    _touch(root / "broadcast" / "announce.md", mtime=NOW)
    sess = _session_dir(root, "sess-a", mtime=NOW)
    _touch(sess / "hello.md", mtime=NOW)

    result = mj.run(root, apply=False, now=NOW)

    assert result["kept_live_md"] == 2
    assert result["pruned_marked"] == 0
    assert result["errors"] == 0
    assert (root / "broadcast" / "announce.md").exists()
    assert (sess / "hello.md").exists()


def test_marked_file_pruned_when_old_kept_when_recent(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()
    sess = _session_dir(root, "sess-a", mtime=NOW)

    old_ts = _ts(NOW - 15 * DAY)
    recent_ts = _ts(NOW - 13 * DAY)

    old_session_file = sess / "m1.md.delivered-{}".format(old_ts)
    recent_session_file = sess / "m2.md.delivered-{}".format(recent_ts)
    old_broadcast_file = root / "broadcast" / "b1.md.expired-{}".format(old_ts)
    recent_broadcast_file = root / "broadcast" / "b2.md.expired-{}".format(recent_ts)
    for f in (old_session_file, recent_session_file, old_broadcast_file, recent_broadcast_file):
        _touch(f, mtime=NOW)

    result = mj.run(root, apply=True, now=NOW, marked_days=14)

    assert result["pruned_marked"] == 2
    assert result["kept_marked_recent"] == 2
    assert not old_session_file.exists()
    assert not old_broadcast_file.exists()
    assert recent_session_file.exists()
    assert recent_broadcast_file.exists()


def test_muted_trailing_z_and_retracted_recognized(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()
    sess = _session_dir(root, "sess-a", mtime=NOW)

    old_ts = _ts(NOW - 20 * DAY)
    muted = sess / "m1.md.muted-{}Z".format(old_ts)
    retracted = sess / "m2.md.retracted-{}".format(old_ts)
    _touch(muted, mtime=NOW)
    _touch(retracted, mtime=NOW)

    result = mj.run(root, apply=True, now=NOW, marked_days=14)

    assert result["pruned_marked"] == 2
    assert not muted.exists()
    assert not retracted.exists()


def test_unparsable_timestamp_falls_back_to_mtime(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()
    sess = _session_dir(root, "sess-a", mtime=NOW)

    # Malformed timestamp digits still match \d{8}T\d{6} shape only if all
    # digits; use a value that matches the regex but fails strptime range
    # checks (month 99) so age falls back to mtime.
    bad_ts = "99999999T999999"
    f = sess / "m1.md.delivered-{}".format(bad_ts)
    _touch(f, mtime=NOW - 15 * DAY)

    result = mj.run(root, apply=True, now=NOW, marked_days=14)

    assert result["pruned_marked"] == 1
    assert not f.exists()


def test_broadcast_seen_kept_when_referencing_live_broadcast(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    bdir = root / "broadcast"
    bdir.mkdir()
    _touch(bdir / "still-live.md", mtime=NOW)

    sess = _session_dir(root, "sess-a", mtime=NOW - 30 * DAY)
    marker = sess / ".broadcast_seen"
    _touch(marker, content="still-live.md\n", mtime=NOW - 30 * DAY)

    result = mj.run(root, apply=True, now=NOW, seen_days=3)

    assert result["seen_kept_live_ref"] == 1
    assert result["seen_removed"] == 0
    assert marker.exists()


def test_broadcast_seen_removed_when_names_absent_and_dir_old(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()

    sess = _session_dir(root, "sess-a", mtime=NOW - 10 * DAY)
    marker = sess / ".broadcast_seen"
    _touch(marker, content="gone-long-ago.md\n", mtime=NOW - 10 * DAY)
    _freeze_mtime(sess, NOW - 10 * DAY)

    result = mj.run(root, apply=True, now=NOW, seen_days=3)

    assert result["seen_removed"] == 1
    assert not marker.exists()
    assert result["dirs_removed"] == 1
    assert not sess.exists()


def test_broadcast_seen_kept_when_dir_younger_than_cutoff(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()

    sess = _session_dir(root, "sess-a", mtime=NOW - 1 * DAY)
    marker = sess / ".broadcast_seen"
    _touch(marker, content="gone-long-ago.md\n", mtime=NOW - 1 * DAY)
    _freeze_mtime(sess, NOW - 1 * DAY)

    result = mj.run(root, apply=True, now=NOW, seen_days=3)

    assert result["seen_kept_recent"] == 1
    assert marker.exists()
    assert result["dirs_removed"] == 0
    assert sess.exists()


def test_oversize_broadcast_seen_kept_as_unknown(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()

    sess = _session_dir(root, "sess-a", mtime=NOW - 10 * DAY)
    marker = sess / ".broadcast_seen"
    _touch(marker, content="x" * 70_000, mtime=NOW - 10 * DAY)

    result = mj.run(root, apply=True, now=NOW, seen_days=3)

    assert result["kept_unknown"] == 1
    assert result["seen_removed"] == 0
    assert marker.exists()
    assert result["dirs_removed"] == 0
    assert sess.exists()


def test_symlinked_file_and_dir_skipped_and_survive(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()

    sess = _session_dir(root, "sess-a", mtime=NOW - 30 * DAY)
    real_file = tmp_path / "outside.md"
    _touch(real_file, mtime=NOW)
    link_file = sess / "link.md"
    link_file.symlink_to(real_file)

    real_dir = tmp_path / "outside-dir"
    real_dir.mkdir()
    link_dir = root / "link-session"
    link_dir.symlink_to(real_dir)

    result = mj.run(root, apply=True, now=NOW, seen_days=3, marked_days=14)

    assert result["skipped_symlink"] >= 2
    assert link_file.exists()
    assert link_file.is_symlink()
    assert link_dir.exists()
    assert link_dir.is_symlink()
    # the symlinked file keeps its session dir non-empty, so it's not rmdir'd
    assert sess.exists()


def test_broadcast_dir_never_removed_even_if_empty_and_old(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    bdir = root / "broadcast"
    bdir.mkdir()
    os.utime(bdir, (NOW - 100 * DAY, NOW - 100 * DAY))

    result = mj.run(root, apply=True, now=NOW, seen_days=3)

    assert result["dirs_removed"] == 0
    assert bdir.exists()
    assert bdir.is_dir()


def test_dry_run_changes_nothing_on_disk(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()

    sess = _session_dir(root, "sess-a", mtime=NOW - 30 * DAY)
    old_ts = _ts(NOW - 30 * DAY)
    marked = sess / "m1.md.delivered-{}".format(old_ts)
    _touch(marked, mtime=NOW)
    marker = sess / ".broadcast_seen"
    _touch(marker, content="gone.md\n", mtime=NOW - 30 * DAY)
    _freeze_mtime(sess, NOW - 30 * DAY)

    before_listing = sorted(p.name for p in root.iterdir())
    before_sess_listing = sorted(p.name for p in sess.iterdir())

    result = mj.run(root, apply=False, now=NOW, marked_days=14, seen_days=3)

    assert result["pruned_marked"] == 1
    assert result["seen_removed"] == 1
    assert result["dirs_removed"] == 1
    assert result["root_entries_after"] == result["root_entries_before"]
    assert sorted(p.name for p in root.iterdir()) == before_listing
    assert sess.exists()
    assert sorted(p.name for p in sess.iterdir()) == before_sess_listing


def test_refusal_missing_root_via_main(tmp_path, capsys):
    missing = tmp_path / "does-not-exist"
    rc = mj.main(["--root", str(missing)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "refused" in captured.err


def test_refusal_symlink_root_via_main(tmp_path, capsys):
    real = tmp_path / "real-mailbox"
    real.mkdir()
    link = tmp_path / "link-mailbox"
    link.symlink_to(real)
    rc = mj.main(["--root", str(link)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "refused" in captured.err


def test_receipt_appends_one_json_line_mode_0600(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()
    receipt = tmp_path / "receipt.jsonl"

    rc = mj.main(
        [
            "--root",
            str(root),
            "--now-epoch",
            repr(NOW),
            "--json",
            "--receipt",
            str(receipt),
        ]
    )

    assert rc == 0
    lines = receipt.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["root"] == str(root)
    mode = stat.S_IMODE(os.stat(receipt).st_mode)
    assert mode == 0o600


def test_nested_dir_kept_and_session_dir_not_removed(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()

    sess = _session_dir(root, "sess-a", mtime=NOW - 30 * DAY)
    nested = sess / "nested-dir"
    nested.mkdir()
    os.utime(nested, (NOW - 30 * DAY, NOW - 30 * DAY))

    result = mj.run(root, apply=True, now=NOW, seen_days=3)

    assert result["kept_unknown"] >= 1
    assert result["dirs_removed"] == 0
    assert sess.exists()
    assert nested.exists()


def test_apply_removes_marker_and_dir_in_one_pass(tmp_path):
    """Unlinking a child bumps the parent dir mtime to wall-clock now; the
    janitor must judge the dir by the mtime it had BEFORE the pass, or an old
    dir that just lost its dead mail survives another seen_days."""
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()
    sess = _session_dir(root, "sess-old")
    _touch(sess / "note.md.delivered-{}".format(_ts(NOW - 20 * DAY)))
    _touch(sess / ".broadcast_seen", content="gone.md\n", mtime=NOW - 10 * DAY)
    _freeze_mtime(sess, NOW - 10 * DAY)

    dry = mj.run(root, apply=False, now=NOW)
    applied = mj.run(root, apply=True, now=NOW)

    assert dry["pruned_marked"] == applied["pruned_marked"] == 1
    assert dry["seen_removed"] == applied["seen_removed"] == 1
    assert dry["dirs_removed"] == applied["dirs_removed"] == 1
    assert not sess.exists()
    assert applied["root_entries_after"] == 1


def test_broadcast_seen_kept_when_marker_appended_recently(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()
    sess = _session_dir(root, "sess-long-lived")
    marker = sess / ".broadcast_seen"
    _touch(marker, content="gone.md\n", mtime=NOW - 1 * DAY)
    _freeze_mtime(sess, NOW - 30 * DAY)

    result = mj.run(root, apply=True, now=NOW, seen_days=3)

    assert result["seen_removed"] == 0
    assert result["seen_kept_recent"] == 1
    assert marker.exists()
    assert sess.exists()
    assert result["dirs_removed"] == 0


def test_broadcast_seen_kept_when_name_goes_live_before_unlink(tmp_path, monkeypatch):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()
    sess = _session_dir(root, "sess-race")
    marker = sess / ".broadcast_seen"
    _touch(marker, content="late.md\n", mtime=NOW - 10 * DAY)
    _freeze_mtime(sess, NOW - 10 * DAY)

    real_realpath = mj.os.path.realpath

    def post_after_snapshot(path, *a, **kw):
        _touch(root / "broadcast" / "late.md")
        return real_realpath(path, *a, **kw)

    monkeypatch.setattr(mj.os.path, "realpath", post_after_snapshot)
    result = mj.run(root, apply=True, now=NOW, seen_days=3)

    assert result["seen_removed"] == 0
    assert result["seen_kept_live_ref"] == 1
    assert marker.exists()


def test_fifo_child_keeps_session_dir_without_errors(tmp_path):
    root = tmp_path / "mailbox"
    root.mkdir()
    (root / "broadcast").mkdir()
    sess = _session_dir(root, "sess-fifo")
    os.mkfifo(sess / "pipe")
    _freeze_mtime(sess, NOW - 30 * DAY)

    result = mj.run(root, apply=True, now=NOW)

    assert result["errors"] == 0
    assert result["dirs_removed"] == 0
    assert result["kept_unknown"] == 1
    assert sess.exists()
