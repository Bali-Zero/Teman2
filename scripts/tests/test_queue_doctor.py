"""Corpus for scripts/queue_doctor.py — a read-only reporter, tested for the
one property a reporter must have: it never fabricates a measurement.

Guilt  = a probe source is broken and the doctor SAYS CANNOT-VERIFY + exit 4.
Innocence = healthy fakes at every boundary and the doctor reads them, exit 0.
Lock states = free / held-alive / held-stale are told apart correctly.

The fakes sit at the SUBPROCESS boundary (fake gh/ssh executables on PATH),
not inside the module — the W114 lesson: a fake that shares the code's own
imagination proves nothing, so the fakes speak the real wire shapes (gh api
graphql JSON, the ssh count lines the real remote script prints).
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR = REPO_ROOT / "scripts" / "queue_doctor.py"


def _write_exe(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _run_doctor(tmp: Path, *, gh_body: str, ssh_body: str, lock: Path) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp / "bin"
    bin_dir.mkdir(exist_ok=True)
    _write_exe(bin_dir / "gh", gh_body)
    _write_exe(bin_dir / "ssh", ssh_body)
    # pgrep must stay real: the lock probe counts wrapper processes with it.
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "QUEUE_DOCTOR_LOCK": str(lock),
        "QUEUE_DOCTOR_SSH": "fakehost",
        "QUEUE_DOCTOR_REPO": "Fake-Org/fake-repo",
    }
    return subprocess.run(
        [sys.executable, str(DOCTOR)], capture_output=True, text=True, env=env, timeout=60
    )


_HEALTHY_GH = (
    "cat <<'EOF'\n"
    + json.dumps(
        {
            "data": {
                "repository": {
                    "mergeQueue": {
                        "entries": {
                            "totalCount": 1,
                            "nodes": [
                                {"position": 1, "pullRequest": {"number": 4242, "title": "a queued PR"}}
                            ],
                        }
                    },
                    "pullRequests": {
                        "nodes": [
                            {"number": 4243, "autoMergeRequest": {"enabledAt": "x"}},
                            {"number": 4244, "autoMergeRequest": None},
                        ]
                    },
                }
            }
        }
    )
    + "\nEOF\n"
)

_HEALTHY_SSH = (
    'printf "pending %s\\n" 4\n'
    'printf "last_flush %s\\n" \'{"ts": 1786000000}\'\n'
    'printf "p0_today %s\\n" 6\n'
)


def test_healthy_boundaries_read_clean(tmp_path: Path) -> None:
    lock = tmp_path / "no-such-lock"  # absent dir = free lock
    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=_HEALTHY_SSH, lock=lock)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "#4242 pos 1" in proc.stdout
    assert "armed but not yet queued: 1 [4243]" in proc.stdout
    assert "free — no holder, no queue" in proc.stdout
    assert "pending (waiting for digest flush): 4" in proc.stdout
    assert "P0 archived today: 6" in proc.stdout
    assert "CANNOT-VERIFY" not in proc.stdout


def test_broken_sources_say_cannot_verify_never_zero(tmp_path: Path) -> None:
    lock = tmp_path / "no-such-lock"
    proc = _run_doctor(tmp_path, gh_body="exit 9\n", ssh_body="exit 9\n", lock=lock)
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert proc.stdout.count("CANNOT-VERIFY") >= 2  # merge queue AND spool
    # the reporter must not invent numbers for what it could not measure:
    assert "in queue: 0" not in proc.stdout
    assert "pending (waiting for digest flush): 0" not in proc.stdout
    assert "INCOMPLETE" in proc.stdout


def test_lock_held_by_live_pid_reads_alive(tmp_path: Path) -> None:
    lock = tmp_path / "suite.lock"
    lock.mkdir()
    (lock / "pid").write_text(str(os.getpid()), encoding="utf-8")
    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=_HEALTHY_SSH, lock=lock)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ALIVE" in proc.stdout
    assert "do NOT rm the lockdir" not in proc.stdout


def test_lock_held_by_dead_pid_reads_stale_and_warns_hands_off(tmp_path: Path) -> None:
    lock = tmp_path / "suite.lock"
    lock.mkdir()
    # spawn-and-reap a child so the pid is REAL but certainly dead (no pid-guessing)
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    (lock / "pid").write_text(str(child.pid), encoding="utf-8")
    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=_HEALTHY_SSH, lock=lock)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "STALE" in proc.stdout
    assert "do NOT rm the lockdir by hand" in proc.stdout
