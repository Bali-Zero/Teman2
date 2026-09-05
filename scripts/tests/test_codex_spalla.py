"""Guilt/innocence for `.claude/scripts/codex-spalla.sh` against codex-cli 0.153.x.

Ledger 2026-09-01 (`.claude/skills/modus/PENDING-ARMS.md`): the wrapper passed
`--full-auto`, removed in codex-cli 0.149.1 — and 0.151.0 printed the usage
error at EXIT 0, so every caller judging by return code read "codex never ran"
as a clean review. The wrapper's exit code, not only its transcript, must
distinguish "ran and found nothing" from "never ran".

Pinned here, against a fake `codex` on PATH:

1. argv pin: the wrapper never passes `--full-auto`, in either mode.
2. rc propagation: a codex that exits 2 makes the WRAPPER exit 2.
3. the 0.151.0 disease: codex prints a clap usage error at exit 0 → wrapper
   exits 6 (no verdict line), never 0.
4. fail-loud seat lib: a repo without `scripts/lib/codex_seat.sh` → exit 1.
5. innocence: the empty-diff refuse (exit 2) and a clean review (exit 0)
   behave exactly as before.
6. `--self-test`: verdict → 0; garbage-at-0 → 6; and it needs no diff.

Every run sets HOME=<tmp> (telemetry/transcripts land in the tmpdir, never in
the real ~/logs) and drives the wrapper from a tmp git repo, so the wrapper's
repo-root resolution finds a controlled tree.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPALLA = REPO_ROOT / ".claude" / "scripts" / "codex-spalla.sh"
SEAT_LIB = REPO_ROOT / "scripts" / "lib" / "codex_seat.sh"

FAKE_CODEX = """#!/usr/bin/env bash
# Fake codex CLI for codex-spalla tests. Behaviour via $FAKE_CODEX_SCENARIO.
printf '%s\\n' "$*" >> "$FAKE_CODEX_ARGV_LOG"
if [[ "${1:-}" == "login" ]]; then
    echo "Logged in using ChatGPT"
    exit 0
fi
case "${FAKE_CODEX_SCENARIO:-verdict}" in
    verdict)
        echo "LGTM"
        echo "fake codex answered"
        ;;
    usage-error-rc0)
        # The 0.151.0 shape: a clap usage error printed at exit ZERO.
        echo "error: unexpected argument '--full-auto' found"
        exit 0
        ;;
    fail2)
        # The 0.149.1/0.153.x shape: same error, honest exit 2.
        echo "error: unexpected argument '--full-auto' found"
        exit 2
        ;;
esac
"""


def _make_fake_codex(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "codex"
    fake.write_text(FAKE_CODEX)
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def _make_repo(
    tmp_path: Path, *, with_seat_lib: bool = True, dirty: bool = True
) -> Path:
    """A git repo on branch `main`; optionally the real seat lib committed in,
    optionally three tracked files dirtied (enough diff lines/files to clear
    both anti-pattern guards without the 5s countdown)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (
        ["git", "init", "-b", "main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    if with_seat_lib:
        lib_dir = repo / "scripts" / "lib"
        lib_dir.mkdir(parents=True)
        shutil.copy(SEAT_LIB, lib_dir / "codex_seat.sh")
    tracked = []
    for i in range(3):
        f = repo / f"file{i}.txt"
        f.write_text("baseline\n")
        tracked.append(f)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True
    )
    if dirty:
        for f in tracked:
            f.write_text("baseline\n" + "".join(f"change {n}\n" for n in range(4)))
    return repo


def _run_spalla(
    tmp_path: Path, repo: Path, scenario: str, *args: str
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    bin_dir = _make_fake_codex(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    argv_log = tmp_path / "argv.log"
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "FAKE_CODEX_SCENARIO": scenario,
            "FAKE_CODEX_ARGV_LOG": str(argv_log),
            # No seats on purpose: seat-picking must find nothing and leave
            # CODEX_HOME unset; the login probe is answered by the fake.
            "CODEX_SEAT_DIRS": str(tmp_path / "no-seats"),
        }
    )
    proc = subprocess.run(
        [str(SPALLA), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc, argv_log, home


def _telemetry(home: Path) -> dict[str, object]:
    lines = (home / "logs" / "codex-spalla.jsonl").read_text().strip().splitlines()
    assert lines, "telemetry line missing"
    return json.loads(lines[-1])


def test_review_mode_never_passes_full_auto_and_succeeds(tmp_path: Path) -> None:
    """Argv pin + innocence: review mode dispatches read-only, no removed flag,
    and a verdict-bearing answer is a clean exit 0."""
    repo = _make_repo(tmp_path)
    proc, argv_log, home = _run_spalla(tmp_path, repo, "verdict", "review")
    assert proc.returncode == 0, proc.stderr
    argv = argv_log.read_text()
    assert "--full-auto" not in argv
    assert "exec --sandbox read-only" in argv
    assert "RESULT_PATH=" in proc.stdout
    assert _telemetry(home)["exit_code"] == 0


def test_exec_mode_uses_workspace_write_without_full_auto(tmp_path: Path) -> None:
    """Argv pin: exec mode keeps full-auto's old semantics as an explicit
    workspace-write sandbox, without the removed flag."""
    repo = _make_repo(tmp_path)
    proc, argv_log, _home = _run_spalla(tmp_path, repo, "verdict", "exec")
    assert proc.returncode == 0, proc.stderr
    argv = argv_log.read_text()
    assert "--full-auto" not in argv
    assert "exec --sandbox workspace-write" in argv


def test_codex_exit_2_propagates(tmp_path: Path) -> None:
    """Guilt: codex failing honestly (exit 2) must make the wrapper exit 2 —
    'ran and failed' is never read as 'clean'."""
    repo = _make_repo(tmp_path)
    proc, _argv_log, home = _run_spalla(tmp_path, repo, "fail2", "review")
    assert proc.returncode == 2, proc.stderr
    assert _telemetry(home)["exit_code"] == 2


def test_zero_exit_without_verdict_exits_6(tmp_path: Path) -> None:
    """Guilt, the 0.151.0 disease: a usage error printed at exit 0 is the
    'never ran' shape — the wrapper must answer 6, never 0."""
    repo = _make_repo(tmp_path)
    proc, _argv_log, home = _run_spalla(tmp_path, repo, "usage-error-rc0", "review")
    assert proc.returncode == 6, proc.stderr
    assert "never judged" in proc.stderr
    assert _telemetry(home)["exit_code"] == 6


def test_missing_seat_lib_fails_loud(tmp_path: Path) -> None:
    """Guilt: without scripts/lib/codex_seat.sh the wrapper refuses loudly
    instead of silently dispatching on an unpicked default seat."""
    repo = _make_repo(tmp_path, with_seat_lib=False)
    proc, _argv_log, _home = _run_spalla(tmp_path, repo, "verdict", "review")
    assert proc.returncode == 1, proc.stderr
    assert "codex seat lib" in proc.stderr


def test_empty_diff_still_refused(tmp_path: Path) -> None:
    """Innocence: the pre-existing empty-diff hard refuse is unchanged."""
    repo = _make_repo(tmp_path, dirty=False)
    proc, _argv_log, _home = _run_spalla(tmp_path, repo, "verdict", "review")
    assert proc.returncode == 2, proc.stderr
    assert "REFUSED" in proc.stderr


def test_self_test_needs_no_diff_and_returns_0_on_verdict(tmp_path: Path) -> None:
    """Innocence: --self-test runs on a clean tree (no diff required) and a
    verdict-bearing answer is exit 0."""
    repo = _make_repo(tmp_path, dirty=False)
    proc, _argv_log, home = _run_spalla(tmp_path, repo, "verdict", "--self-test")
    assert proc.returncode == 0, proc.stderr
    assert "RESULT_PATH=" in proc.stdout
    entry = _telemetry(home)
    assert entry["mode"] == "self-test"
    assert entry["exit_code"] == 0


def test_self_test_without_verdict_exits_6(tmp_path: Path) -> None:
    """Guilt: --self-test must catch the silent never-ran shape on its own."""
    repo = _make_repo(tmp_path, dirty=False)
    proc, _argv_log, home = _run_spalla(
        tmp_path, repo, "usage-error-rc0", "--self-test"
    )
    assert proc.returncode == 6, proc.stderr
    entry = _telemetry(home)
    assert entry["mode"] == "self-test"
    assert entry["exit_code"] == 6


def test_fixtures_are_honest() -> None:
    """Sanity on the fixture itself: the fake distinguishes the three shapes,
    and the real seat lib the tests copy actually exists in this checkout."""
    assert SPALLA.is_file()
    assert SEAT_LIB.is_file()
    for scenario in ("verdict", "usage-error-rc0", "fail2"):
        assert f"    {scenario})" in FAKE_CODEX
