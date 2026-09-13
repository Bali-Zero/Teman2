"""Guilt + innocence for `fleet_mail.sh retract` (2026-09-02).

Companion to test_fleet_mail_hosts.py (host allowlist) and
infra/claude-hooks/test_mailbox_inject.py (the reader half — never touched by
this change). Covers the SENDER-side cleanup added to cure the measured
disease: 97% of live `queue_unstick:<PR#>` broadcasts on Pro (2026-09-02
audit, research/operations/2026-09-02-mailbox-broadcast-staleness-audit.md)
were for PRs already resolved, yet lingered under the fleet-wide 48h TTL.

`retract --key <k>` renames every LIVE broadcast whose `key:` front matter
matches to `.retracted-<ts>` — the same self-cleaning pattern
`infra/claude-hooks/mailbox_inject.py` already uses for
`.superseded-`/`.expired-`/`.delivered-`/`.skipped-oversize-`, so a retracted
file drops out of every future scan for every session immediately.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "fleet_mail.sh"


def _send(mailbox_dir: pathlib.Path, key: str, body: str) -> None:
    env = dict(os.environ, NUZ_MAILBOX_DIR=str(mailbox_dir))
    proc = subprocess.run(
        ["bash", str(SCRIPT), "local", "broadcast", "--key", key, body],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert proc.returncode == 0, proc.stderr


def _retract(mailbox_dir: pathlib.Path, key: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, NUZ_MAILBOX_DIR=str(mailbox_dir))
    return subprocess.run(
        ["bash", str(SCRIPT), "local", "retract", "--key", key],
        capture_output=True, text=True, timeout=30, env=env,
    )


def _broadcast_dir(mailbox_dir: pathlib.Path) -> pathlib.Path:
    return mailbox_dir / "broadcast"


def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"{SCRIPT} missing — the test's own subject is gone"


def test_retract_removes_only_the_matching_key(tmp_path) -> None:
    """GUILT (the target key is gone) + INNOCENCE (an unrelated key survives)
    in one test, because they are two assertions over the SAME retract call —
    a fix that satisfies only one half is exactly what a censused guard
    without both halves (cicatrix family #3) would miss."""
    mailbox = tmp_path / "mailbox"
    _send(mailbox, "queue_unstick:9001", "PR #9001 is DIRTY")
    _send(mailbox, "queue_unstick:9002", "PR #9002 is DIRTY")

    proc = _retract(mailbox, "queue_unstick:9001")
    assert proc.returncode == 0, proc.stderr
    assert "retracted 1 message(s)" in proc.stdout

    live = [p.name for p in _broadcast_dir(mailbox).glob("*.md")]
    retracted = list(_broadcast_dir(mailbox).glob("*.retracted-*"))
    assert len(live) == 1, live
    assert len(retracted) == 1, retracted

    # The survivor is 9002's file, still readable with its original content —
    # retract must never touch a non-matching message.
    survivor = _broadcast_dir(mailbox).glob("*.md")
    text = next(survivor).read_text()
    assert "key: queue_unstick:9002" in text
    assert "PR #9002 is DIRTY" in text

    # The retracted file is RENAMED, not deleted — content preserved, in the
    # same self-cleaning-tag spirit as mailbox_inject.py's own `.superseded-`.
    retracted_text = retracted[0].read_text()
    assert "key: queue_unstick:9001" in retracted_text
    assert "PR #9001 is DIRTY" in retracted_text


def test_retract_no_matching_key_is_a_silent_noop(tmp_path) -> None:
    mailbox = tmp_path / "mailbox"
    _send(mailbox, "queue_unstick:9003", "PR #9003 is DIRTY")

    proc = _retract(mailbox, "queue_unstick:does-not-exist")
    assert proc.returncode == 0, proc.stderr
    assert "retracted 0 message(s)" in proc.stdout
    live = [p.name for p in _broadcast_dir(mailbox).glob("*.md")]
    assert len(live) == 1, "the unrelated message must survive untouched"


def test_retract_second_call_is_idempotent(tmp_path) -> None:
    mailbox = tmp_path / "mailbox"
    _send(mailbox, "queue_unstick:9004", "PR #9004 is DIRTY")

    first = _retract(mailbox, "queue_unstick:9004")
    assert "retracted 1 message(s)" in first.stdout
    second = _retract(mailbox, "queue_unstick:9004")
    assert second.returncode == 0, second.stderr
    assert "retracted 0 message(s)" in second.stdout, (
        "an already-retracted file must not be found again — it no longer "
        "has a .md suffix"
    )


def test_retract_missing_key_flag_dies(tmp_path) -> None:
    mailbox = tmp_path / "mailbox"
    env = dict(os.environ, NUZ_MAILBOX_DIR=str(mailbox))
    proc = subprocess.run(
        ["bash", str(SCRIPT), "local", "retract"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert proc.returncode != 0
    assert "retract needs --key" in proc.stderr


def test_retract_missing_broadcast_dir_is_a_noop(tmp_path) -> None:
    """No message was ever sent — the broadcast dir may not even exist yet.
    A retract must not create it, error on it, or crash."""
    mailbox = tmp_path / "mailbox"
    proc = _retract(mailbox, "queue_unstick:9005")
    assert proc.returncode == 0, proc.stderr
    assert "retracted 0 message(s)" in proc.stdout


def test_retract_ignores_a_symlinked_message_file(tmp_path) -> None:
    """Containment, same posture as mailbox_inject.py's own symlink refusal
    (module docstring point 3): a message file that is a SYMLINK is never
    followed, so an attacker-planted symlink cannot be used to rename or
    read a file outside the mailbox root via this path."""
    mailbox = tmp_path / "mailbox"
    bdir = _broadcast_dir(mailbox)
    bdir.mkdir(parents=True, mode=0o700)
    outside = tmp_path / "outside.md"
    outside.write_text("key: queue_unstick:9006\n\nshould never be touched")
    link = bdir / "20260101T000000-0001.md"
    link.symlink_to(outside)

    proc = _retract(mailbox, "queue_unstick:9006")
    assert proc.returncode == 0, proc.stderr
    assert "retracted 0 message(s)" in proc.stdout
    assert link.is_symlink(), "the symlink itself must be untouched"
    assert outside.read_text() == "key: queue_unstick:9006\n\nshould never be touched"


def test_retract_sanitizes_the_key_to_a_safe_charset(tmp_path) -> None:
    """The key is embedded in a remote command string for non-local hosts
    (same surface `--key`/`--ttl` sanitization already protects on the send
    path) — a key containing shell metacharacters must be neutralised, not
    rejected outright, matching the existing MSG_KEY sanitization pattern."""
    mailbox = tmp_path / "mailbox"
    env = dict(os.environ, NUZ_MAILBOX_DIR=str(mailbox))
    proc = subprocess.run(
        ["bash", str(SCRIPT), "local", "retract", "--key", "queue_unstick:1; rm -rf /tmp/x"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert ";" not in proc.stdout.split("key '")[1]


def _routing_stub(tmp_path, up: set[str]) -> str:
    """An `ssh` that succeeds only for hosts in `up`. UNLIKE
    test_fleet_mail_hosts.py's `_routing_stub`, this one is SILENT on the
    probe call (`ssh ... <host> true`, no output beyond exit 0) and only
    echoes REACHED:<host> for a call carrying a real remote command —
    matching real OpenSSH: a remote `true` produces no stdout at all. Without
    this distinction, `ssh_target()`'s `SSH_HOST="$(ssh_target "$HOST")"`
    captures the PROBE's own stdout too (command substitution captures
    everything the function prints, not just its final `echo "$host"`),
    corrupting `$SSH_HOST` into a multi-line value — reproduced empirically
    while writing this test: it makes the real (second) ssh call fail, and
    only 'passes' test_fleet_mail_hosts.py's own weaker assertion because the
    resulting die() message happens to still contain the substring
    'REACHED:<host>'. Not fixed there (out of this PR's scope — pre-existing,
    unrelated to the retract feature); avoided here by construction."""
    d = tmp_path / "stub-bin"
    d.mkdir(exist_ok=True)
    ssh = d / "ssh"
    ssh.write_text(
        "#!/bin/sh\n"
        "host=''\n"
        "while [ $# -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -o) shift 2;;\n"
        "    -*) shift;;\n"
        "    *) host=\"$1\"; shift; break;;\n"
        "  esac\n"
        "done\n"
        "match=0\n"
        f"for u in {' '.join(sorted(up)) or '__none__'}; do\n"
        "  [ \"$host\" = \"$u\" ] && match=1\n"
        "done\n"
        "if [ \"$match\" = 1 ]; then\n"
        "  if [ $# -eq 1 ] && [ \"$1\" = true ]; then exit 0; fi\n"
        "  echo \"REACHED:$host\"\n"
        "  exit 0\n"
        "fi\n"
        "echo 'stub ssh: unreachable' >&2\n"
        "exit 255\n"
    )
    ssh.chmod(0o755)
    return f"{d}{os.pathsep}{os.environ.get('PATH', '')}"


def test_retract_on_a_remote_host_reaches_ssh_with_no_stdin_body_needed(tmp_path) -> None:
    """Unlike `send` (which pipes BODY over stdin), `retract` needs no
    message body — this proves the remote invocation does not hang waiting
    on stdin the way the pre-fix `send` path once did (round-1 refuter
    finding on the send side, see the header comment above PY_SEND)."""
    path = _routing_stub(tmp_path, {"pro"})
    env = dict(os.environ, PATH=path)
    proc = subprocess.run(
        ["bash", str(SCRIPT), "pro", "retract", "--key", "queue_unstick:9007"],
        capture_output=True, text=True, timeout=10, env=env, stdin=subprocess.DEVNULL,
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "REACHED:pro" in proc.stdout + proc.stderr, (proc.stdout, proc.stderr)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
