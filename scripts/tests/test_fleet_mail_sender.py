"""Guilt + innocence for `fleet_mail.sh`'s sender identity + rate cap (2026-09-18).

Companion to test_fleet_mail_to.py (the `--to` addressing half) and
test_fleet_mail_retract.py (sender-side cleanup). Measured 2026-09-18 on M5: 416 live
broadcasts, 368 of them (89%) from `Air-M5:fleet-watch` — the DEFAULT label every anonymous
session inherited, indistinguishable from one another and from nobody's control. This file
covers the two mechanisms that end that:

  A. `broadcast` REQUIRES an explicit sender label (`--from <label>` or `FLEET_MAIL_FROM` env) —
     missing either dies exit 2, before anything is written. Direct (session-dir) mail is
     UNCHANGED (keeps the old `fleet-watch` default, no `--from` required).
  C. A sender is capped at `FLEET_MAIL_MAX_PER_HOUR` (default 6) LIVE broadcasts per hour;
     the (N+1)th within the window dies exit 3 with a one-line reason naming the count.
     `--urgent` bypasses the cap for that one send and marks the message `urgent: true`.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import time

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "fleet_mail.sh"


def _send(mailbox_dir: pathlib.Path, *extra_args: str, session: str = "broadcast",
          env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, NUZ_MAILBOX_DIR=str(mailbox_dir))
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SCRIPT), "local", session, *extra_args, "hello"],
        capture_output=True, text=True, timeout=30, env=env,
    )


def _broadcast_files(mailbox_dir: pathlib.Path) -> list[pathlib.Path]:
    return sorted((mailbox_dir / "broadcast").glob("*.md"))


def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"{SCRIPT} missing — the test's own subject is gone"


# ── A: identity ──────────────────────────────────────────────────────────────


def test_broadcast_without_from_dies_with_exit_2(tmp_path) -> None:
    """GUILT: neither --from nor FLEET_MAIL_FROM given -- no send."""
    mailbox = tmp_path / "mailbox"
    proc = _send(mailbox, "--to", "all")
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    assert "--from" in proc.stderr
    assert not (mailbox / "broadcast").exists()


def test_broadcast_with_from_flag_writes_the_from_line(tmp_path) -> None:
    """INNOCENCE: --from <label> lands as `from: <host>:<label>`."""
    mailbox = tmp_path / "mailbox"
    proc = _send(mailbox, "--to", "all", "--from", "queue-unstick")
    assert proc.returncode == 0, proc.stderr
    files = _broadcast_files(mailbox)
    assert len(files) == 1
    text = files[0].read_text()
    from_line = text.splitlines()[0]
    assert from_line.startswith("from: ")
    assert from_line.endswith(":queue-unstick")


def test_broadcast_with_fleet_mail_from_env_is_accepted(tmp_path) -> None:
    """FLEET_MAIL_FROM env satisfies the identity requirement exactly like --from."""
    mailbox = tmp_path / "mailbox"
    proc = _send(mailbox, "--to", "all", env_extra={"FLEET_MAIL_FROM": "cron-x"})
    assert proc.returncode == 0, proc.stderr
    text = _broadcast_files(mailbox)[0].read_text()
    assert text.splitlines()[0].endswith(":cron-x")


def test_direct_mail_does_not_require_from(tmp_path) -> None:
    """Direct (session-dir) mail is UNCHANGED: no --from needed, old default kept."""
    mailbox = tmp_path / "mailbox"
    proc = _send(mailbox, session="sess-alpha-0001")
    assert proc.returncode == 0, proc.stderr
    files = list((mailbox / "sess-alpha-0001").glob("*.md"))
    assert len(files) == 1
    assert files[0].read_text().splitlines()[0].endswith(":fleet-watch")


def test_from_label_is_sanitized_to_a_safe_charset(tmp_path) -> None:
    """A shell metacharacter in the label is stripped, not rejected -- same posture as
    --key/--to."""
    mailbox = tmp_path / "mailbox"
    proc = _send(mailbox, "--to", "all", "--from", "bad; rm -rf /tmp/x")
    assert proc.returncode == 0, proc.stderr
    from_line = _broadcast_files(mailbox)[0].read_text().splitlines()[0]
    from_value = from_line[len("from:"):].strip()
    assert ";" not in from_value and " " not in from_value and "/" not in from_value


# ── C: rate cap ──────────────────────────────────────────────────────────────


def test_sixth_send_within_the_hour_succeeds_seventh_dies_exit_3(tmp_path) -> None:
    mailbox = tmp_path / "mailbox"
    env_extra = {"FLEET_MAIL_MAX_PER_HOUR": "6"}
    for i in range(6):
        proc = _send(mailbox, "--to", "all", "--from", "capped", env_extra=env_extra)
        assert proc.returncode == 0, (i, proc.stderr)
    assert len(_broadcast_files(mailbox)) == 6

    seventh = _send(mailbox, "--to", "all", "--from", "capped", env_extra=env_extra)
    assert seventh.returncode == 3, (seventh.stdout, seventh.stderr)
    assert "6" in seventh.stderr
    assert len(_broadcast_files(mailbox)) == 6, "the refused send must not write a file"


def test_cap_is_per_sender_label_not_global(tmp_path) -> None:
    """INNOCENCE: a DIFFERENT sender is never blocked by another sender's cap."""
    mailbox = tmp_path / "mailbox"
    env_extra = {"FLEET_MAIL_MAX_PER_HOUR": "6"}
    for _ in range(6):
        _send(mailbox, "--to", "all", "--from", "noisy", env_extra=env_extra)
    proc = _send(mailbox, "--to", "all", "--from", "quiet", env_extra=env_extra)
    assert proc.returncode == 0, proc.stderr


def test_urgent_bypasses_the_cap_and_marks_the_message(tmp_path) -> None:
    mailbox = tmp_path / "mailbox"
    env_extra = {"FLEET_MAIL_MAX_PER_HOUR": "6"}
    for _ in range(6):
        _send(mailbox, "--to", "all", "--from", "urgent-sender", env_extra=env_extra)
    proc = _send(mailbox, "--to", "all", "--from", "urgent-sender", "--urgent", env_extra=env_extra)
    assert proc.returncode == 0, proc.stderr
    files = _broadcast_files(mailbox)
    assert len(files) == 7
    urgent_files = [f for f in files if "urgent: true" in f.read_text()]
    assert len(urgent_files) == 1


def test_an_expired_sibling_is_not_counted_toward_the_cap(tmp_path) -> None:
    """A file already renamed `.expired-<ts>` (mailbox_inject.py's own self-cleaning suffix)
    no longer matches the `*.md` glob this cap counts against -- it must not consume quota."""
    mailbox = tmp_path / "mailbox"
    env_extra = {"FLEET_MAIL_MAX_PER_HOUR": "2"}
    for _ in range(2):
        _send(mailbox, "--to", "all", "--from", "expiring", env_extra=env_extra)
    files = _broadcast_files(mailbox)
    assert len(files) == 2
    # Simulate the reader's own self-cleaning rename on one of the two.
    files[0].rename(str(files[0]) + ".expired-20260101T000000")

    proc = _send(mailbox, "--to", "all", "--from", "expiring", env_extra=env_extra)
    assert proc.returncode == 0, (
        "only 1 LIVE (.md) sibling remains after the expiry rename -- under the cap of 2"
    )


def test_a_sibling_outside_the_hour_window_is_not_counted(tmp_path) -> None:
    """A LIVE file older than an hour must not count against the cap -- mtime, not count of
    all-time sends, is what bounds the window."""
    mailbox = tmp_path / "mailbox"
    env_extra = {"FLEET_MAIL_MAX_PER_HOUR": "1"}
    proc1 = _send(mailbox, "--to", "all", "--from", "aging", env_extra=env_extra)
    assert proc1.returncode == 0, proc1.stderr
    old_file = _broadcast_files(mailbox)[0]
    two_hours_ago = time.time() - 7200
    os.utime(old_file, (two_hours_ago, two_hours_ago))

    proc2 = _send(mailbox, "--to", "all", "--from", "aging", env_extra=env_extra)
    assert proc2.returncode == 0, (
        "the only existing sibling is 2h old -- outside the 1h window, must not count"
    )
