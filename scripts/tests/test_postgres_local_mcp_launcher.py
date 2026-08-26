"""Guilt + innocence for `scripts/mcp/postgres-local-mcp.sh`.

Why this file exists: on 2026-08-26 the `postgres-nuzantara-local` MCP failed with
`Command failed with no output` — no auth error, no SQL error, nothing to read — and
a research lane recorded "no live counts anywhere" because of it. The root cause was
never reproduced and is NOT claimed here. What IS tested is that the launcher can no
longer fail SILENTLY.

Two silent-failure modes are covered, and the second was found by an adversarial
review of the FIRST version of this script — which had the hole it was written to
close:

  (a) EMPTY/FAILED lookup. The old one-liner was
        PGPASSWORD=$(security find-generic-password ... -w) exec npx ...
      A substitution in an assignment PREFIX discards its exit status, so a failed
      lookup became an empty password and the shell carried on.
  (b) HANG. `security` blocks forever on a GUI keychain-authorization prompt.
      Execution freezes BEFORE any diagnostic exists — which reproduces the exact
      original symptom. `test_hanging_keychain_*` is the regression test.

Per superscar #3 every guard gets both halves. Note also that three earlier tests
were pure source-greps that would have passed with the guard inverted; they are
behavioural here — a test that reads the source only proves the source contains a
string, never that the string does anything.
"""

from __future__ import annotations

import os
import stat
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "mcp" / "postgres-local-mcp.sh"


def _bin(tmp_path: Path, security_body: str) -> Path:
    d = tmp_path / "bin"
    d.mkdir(exist_ok=True)
    (d / "security").write_text("#!/bin/sh\n" + security_body)
    (d / "security").chmod(0o755)
    # npx stub RECORDS its argv, so tests can assert what was actually passed
    # rather than grepping the launcher's source for a literal.
    (d / "npx").write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$NPX_ARGV_FILE"\necho NPX_REACHED\nexit 0\n'
    )
    (d / "npx").chmod(0o755)
    return d


def _run(tmp_path: Path, security_body: str, extra_env: dict | None = None, timeout: int = 60):
    d = _bin(tmp_path, security_body)
    env = dict(
        os.environ,
        NUZ_SECURITY_BIN=str(d / "security"),
        NUZ_NPX_BIN=str(d / "npx"),
        NPX_ARGV_FILE=str(tmp_path / "npx_argv.txt"),
        NUZ_MCP_LOG_DIR=str(tmp_path / "logs"),
    )
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True, text=True, timeout=timeout,
        stdin=subprocess.DEVNULL, env=env,
    )


GOOD = "echo 'pw-not-a-real-secret'\nexit 0\n"


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file(), f"{SCRIPT} missing — the test's own subject is gone"
    assert os.access(SCRIPT, os.X_OK)


def test_empty_keychain_result_fails_loudly_instead_of_launching(tmp_path: Path) -> None:
    """GUILT — exit 0 with no output: the case the old one-liner swallowed."""
    proc = _run(tmp_path, "exit 0\n")
    assert proc.returncode == 71, (proc.returncode, proc.stderr)
    assert "EMPTY password" in proc.stderr
    assert "NPX_REACHED" not in proc.stdout


def test_failing_keychain_fails_loudly(tmp_path: Path) -> None:
    """GUILT — locked keychain / missing item must be named, not silent."""
    proc = _run(tmp_path, "echo 'not found' >&2\nexit 44\n")
    assert proc.returncode == 70, (proc.returncode, proc.stderr)
    assert "keychain lookup failed" in proc.stderr
    assert "NPX_REACHED" not in proc.stdout


def test_hanging_keychain_times_out_loudly_and_does_not_launch(tmp_path: Path) -> None:
    """GUILT — the hole the FIRST version of this script had.

    `security` waiting on a GUI authorization prompt never returns. Without a
    time-box the launcher freezes before emitting anything: no stdout, no stderr,
    no exit code — indistinguishable from the original incident this file exists
    for. Must fail LOUDLY inside the timeout instead.
    """
    started = time.time()
    # `exec` so the stub IS the hanging process, not a shell wrapping one — a
    # real `security` does not fork, and a stub that does would test the wrong
    # thing (measured: killing the wrapper left `sleep` holding the caller's
    # stdout, so the caller hung anyway).
    proc = _run(tmp_path, "exec sleep 120\n", {"NUZ_KEYCHAIN_TIMEOUT": "2"}, timeout=45)
    elapsed = time.time() - started
    assert proc.returncode == 72, (proc.returncode, proc.stderr)
    assert "TIMED OUT" in proc.stderr
    assert elapsed < 30, f"did not time-box the hang: {elapsed:.1f}s"
    assert "NPX_REACHED" not in proc.stdout


def test_healthy_credential_launches_the_server(tmp_path: Path) -> None:
    """INNOCENCE — the guards must not have become a blanket refusal."""
    proc = _run(tmp_path, GOOD)
    assert "NPX_REACHED" in proc.stdout, (proc.returncode, proc.stdout, proc.stderr)


def test_the_password_is_never_written_to_stderr_or_the_log(tmp_path: Path) -> None:
    """A diagnostic that echoes the credential turns every failure into a secret
    leak (superscar #4). Length may be logged; the value never."""
    secret = "s3cr3t-must-never-appear"
    proc = _run(tmp_path, f"echo '{secret}'\nexit 0\n")
    assert secret not in proc.stderr
    assert secret not in proc.stdout
    for lg in (tmp_path / "logs").glob("*.log"):
        assert secret not in lg.read_text(), f"credential leaked into {lg}"


def test_the_credential_never_touches_disk(tmp_path: Path) -> None:
    """The fetch goes through a FIFO, not a temp file. A regular file holding the
    password — even briefly, even 0600 — is at-rest exposure this can avoid."""
    secret = "disk-check-secret-value"
    _run(tmp_path, f"echo '{secret}'\nexit 0\n")
    # Skip the stub bin dir: the test WRITES the secret into its own fake
    # `security` script, so walking it finds the probe's own fixture and calls it
    # a leak. Measured — the first version of this test failed for exactly that
    # reason, which is the probe being broken, not the world.
    for root, _dirs, files in os.walk(tmp_path):
        if "bin" in Path(root).parts:
            continue
        for f in files:
            p = Path(root) / f
            try:
                if secret in p.read_text(errors="ignore"):
                    pytest.fail(f"credential found at rest in {p}")
            except OSError:
                pass


def test_log_file_is_owner_only(tmp_path: Path) -> None:
    """The log can carry connection errors. Asserted on the real mode bits — an
    earlier version of this suite checked only contents, so deleting `umask 077`
    and the chmod would have passed."""
    _run(tmp_path, GOOD)
    logs = list((tmp_path / "logs").glob("*.log"))
    assert logs, "no log file was created"
    for lg in logs:
        mode = stat.S_IMODE(lg.stat().st_mode)
        assert mode & 0o077 == 0, f"{lg} is group/other-accessible: {oct(mode)}"


def test_stdout_carries_no_diagnostics(tmp_path: Path) -> None:
    """stdout IS the JSON-RPC channel: one stray human-readable line corrupts the
    protocol and the client sees a parse failure, not a message."""
    proc = _run(tmp_path, GOOD)
    stray = [ln for ln in proc.stdout.splitlines() if ln.strip() and ln.strip() != "NPX_REACHED"]
    assert not stray, f"non-protocol output on stdout: {stray}"


@pytest.mark.parametrize(
    "conn",
    [
        "postgresql://u@127.0.0.1:15432/nuzantara_dev?sslmode=disable",  # with /dbname
        "postgresql://u@127.0.0.1:15432?sslmode=disable",                # no /dbname
        "postgresql://u@127.0.0.1:15432",                                # bare
    ],
)
def test_production_proxy_port_is_refused_behaviourally(tmp_path: Path, conn: str) -> None:
    """GUILT — 15432 is a flyctl proxy to PRODUCTION.

    Behavioural, not a source-grep: the previous version of this test asserted
    three literals were present in the file and would have passed with the guard
    inverted. It also missed that `*:15432/*` matches ONLY the first URI shape —
    a libpq URI may end the port with `?query` or with nothing, and both sailed
    through (reproduced live by an adversarial review).
    """
    proc = _run(tmp_path, GOOD, {"NUZ_PG_MCP_CONN": conn})
    assert proc.returncode == 78, (conn, proc.returncode, proc.stderr)
    assert "PRODUCTION" in proc.stderr
    assert "NPX_REACHED" not in proc.stdout


def test_local_port_5432_is_allowed(tmp_path: Path) -> None:
    """INNOCENCE for the port guard — it must not reject the legitimate target."""
    proc = _run(tmp_path, GOOD, {"NUZ_PG_MCP_CONN": "postgresql://u@127.0.0.1:5432/nuzantara_dev"})
    assert "NPX_REACHED" in proc.stdout, (proc.returncode, proc.stderr)


def test_the_version_actually_reaches_npx(tmp_path: Path) -> None:
    """Behavioural pin check: the previous version grepped the source, which could
    not distinguish 'pinned in source' from 'dropped before reaching npx'. The npx
    stub records its argv, so this reads what was really passed."""
    proc = _run(tmp_path, GOOD, {"NUZ_PG_MCP_VERSION": "0.6.2"})
    assert "NPX_REACHED" in proc.stdout
    argv = (tmp_path / "npx_argv.txt").read_text().splitlines()
    assert "@modelcontextprotocol/server-postgres@0.6.2" in argv, argv


def test_unwritable_log_dir_warns_instead_of_dying_silently(tmp_path: Path) -> None:
    """The setup phase used to discard its own errors with `2>/dev/null || true`,
    throwing away the one fact that explains why the log is unusable. It must warn
    on stderr and still start — degrade, not die, and never in silence."""
    blocked = tmp_path / "blocked"
    blocked.write_text("i am a file, not a directory")
    proc = _run(tmp_path, GOOD, {"NUZ_MCP_LOG_DIR": str(blocked / "logs")})
    assert "WARNING" in proc.stderr, proc.stderr
    assert "NPX_REACHED" in proc.stdout, "must still launch when only the log is broken"
