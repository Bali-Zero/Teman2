"""Guilt + innocence for `fleet_mail.sh`'s `--to` addressing (2026-09-18, Zero's order).

Companion to test_fleet_mail_hosts.py (host allowlist) and
infra/claude-hooks/test_mailbox_inject.py (the reader half — covers the
delivery-side matching this file does not). A plain `broadcast` used to
reach EVERY session on every machine — "una follia" per Zero — so
`broadcast` now REQUIRES `--to <target>`: this file is the sender-side half
of that contract (die on missing `--to`, write the `to:` front-matter
line correctly for one or several repeated `--to` values).
"""

from __future__ import annotations

import os
import pathlib
import subprocess

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "fleet_mail.sh"


def _send(mailbox_dir: pathlib.Path, *extra_args: str, session: str = "broadcast") -> subprocess.CompletedProcess:
    # --from (2026-09-18): broadcast now also requires a sender label; this file's own
    # concern is --to, so every call here carries a fixed label unless the test itself is
    # deliberately probing the --to contract on its own (missing --to still dies exit 2
    # before the --from check ever runs — see fleet_mail.sh's ordering).
    env = dict(os.environ, NUZ_MAILBOX_DIR=str(mailbox_dir))
    return subprocess.run(
        ["bash", str(SCRIPT), "local", session, *extra_args, "--from", "test-sender", "hello"],
        capture_output=True, text=True, timeout=30, env=env,
    )


def _only_broadcast_file(mailbox_dir: pathlib.Path) -> pathlib.Path:
    files = list((mailbox_dir / "broadcast").glob("*.md"))
    assert len(files) == 1, files
    return files[0]


def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"{SCRIPT} missing — the test's own subject is gone"


def test_broadcast_without_to_dies_with_exit_2(tmp_path) -> None:
    """GUILT: no address, no send — a broadcast with no `--to` used to reach
    every session on every machine."""
    proc = _send(tmp_path / "mailbox")
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    assert "--to" in proc.stderr
    assert not (tmp_path / "mailbox" / "broadcast").exists()


def test_broadcast_with_one_to_writes_the_to_line(tmp_path) -> None:
    """INNOCENCE: a single `--to` is accepted and lands as one `to:` line
    right after `from:` (mailbox_inject.py's front-matter parser reads the
    first MAX_FRONT_MATTER_LINES lines in order)."""
    mailbox = tmp_path / "mailbox"
    proc = _send(mailbox, "--to", "host:pro")
    assert proc.returncode == 0, proc.stderr
    text = _only_broadcast_file(mailbox).read_text()
    lines = text.splitlines()
    assert lines[0].startswith("from:")
    assert lines[1] == "to: host:pro"


def test_broadcast_with_repeated_to_joins_with_commas(tmp_path) -> None:
    """A repeated `--to` collapses into ONE comma-separated `to:` line, not
    several lines — matching what mailbox_inject.py's `_parse_to_targets`
    expects to split on."""
    mailbox = tmp_path / "mailbox"
    proc = _send(mailbox, "--to", "host:pro", "--to", "lane:wr2", "--to", "all")
    assert proc.returncode == 0, proc.stderr
    text = _only_broadcast_file(mailbox).read_text()
    lines = text.splitlines()
    assert lines[1] == "to: host:pro,lane:wr2,all"
    assert sum(1 for ln in lines if ln.startswith("to:")) == 1


def test_direct_mail_does_not_require_to(tmp_path) -> None:
    """Direct (session-dir) mail is UNCHANGED: no `--to` needed, and none is
    written when omitted."""
    mailbox = tmp_path / "mailbox"
    proc = _send(mailbox, session="sess-alpha-0001")
    assert proc.returncode == 0, proc.stderr
    files = list((mailbox / "sess-alpha-0001").glob("*.md"))
    assert len(files) == 1
    assert "to:" not in files[0].read_text()


def test_to_value_is_sanitized_to_a_safe_charset(tmp_path) -> None:
    """`--to` is embedded unquoted in the remote command text for non-local
    hosts (same surface `--key`/`--ttl` already protect) — a shell
    metacharacter must be stripped, not rejected outright, matching the
    existing sanitization pattern."""
    mailbox = tmp_path / "mailbox"
    proc = _send(mailbox, "--to", "host:pro; rm -rf /tmp/x")
    assert proc.returncode == 0, proc.stderr
    text = _only_broadcast_file(mailbox).read_text()
    to_line = next(ln for ln in text.splitlines() if ln.startswith("to:"))
    to_value = to_line[len("to:"):].strip()
    assert ";" not in to_value and " " not in to_value and "/" not in to_value
