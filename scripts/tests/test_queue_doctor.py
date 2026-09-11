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
import socket
import stat
import subprocess
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR = REPO_ROOT / "scripts" / "queue_doctor.py"


def _write_exe(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _run_doctor(
    tmp: Path, *, gh_body: str, ssh_body: str, lock: Path, spool: Path | None = None
) -> subprocess.CompletedProcess[str]:
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
    if spool is not None:
        env["QUEUE_DOCTOR_SPOOL"] = str(spool)
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
    'printf "spool_dir OK\\n"\n'
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
    assert "last flush age:" in proc.stdout
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


def test_missing_spool_file_is_not_reported_as_an_empty_queue(tmp_path: Path) -> None:
    lock = tmp_path / "no-such-lock"
    missing_pending = (
        'printf "spool_dir OK\\n"\n'
        'printf "pending MISSING\\n"\n'
        'printf "last_flush %s\\n" \'{"ts": 1786000000}\'\n'
        'printf "p0_today %s\\n" 0\n'
    )

    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=missing_pending, lock=lock)

    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert "CANNOT-VERIFY" in proc.stdout
    assert "missing or invalid counters: pending" in proc.stdout
    assert "pending (waiting for digest flush): 0" not in proc.stdout


def test_malformed_last_flush_metadata_is_cannot_verify(tmp_path: Path) -> None:
    lock = tmp_path / "no-such-lock"
    malformed_flush = (
        'printf "spool_dir OK\\n"\n'
        'printf "pending %s\\n" 0\n'
        'printf "last_flush %s\\n" not-json\n'
        'printf "p0_today %s\\n" 0\n'
    )

    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=malformed_flush, lock=lock)

    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert "CANNOT-VERIFY" in proc.stdout
    assert "invalid last_flush metadata" in proc.stdout


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


def test_lock_pid_read_failure_is_cannot_verify(tmp_path: Path) -> None:
    lock = tmp_path / "suite.lock"
    lock.mkdir()
    (lock / "pid").mkdir()  # opening a directory as a file raises OSError

    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=_HEALTHY_SSH, lock=lock)

    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert "CANNOT-VERIFY" in proc.stdout
    assert "could not read holder pid" in proc.stdout
    assert "STALE" not in proc.stdout


def test_lock_stat_failure_is_cannot_verify(tmp_path: Path) -> None:
    lock = tmp_path / "suite.lock"
    lock.mkdir()
    fifo = tmp_path / "holder-pid.fifo"
    os.mkfifo(fifo)
    (lock / "pid").symlink_to(fifo)
    writer_errors: list[BaseException] = []

    def remove_lock_before_stat() -> None:
        try:
            with fifo.open("w", encoding="utf-8") as fh:
                (lock / "pid").unlink()
                lock.rmdir()
                fh.write(str(os.getpid()))
        except BaseException as exc:  # pragma: no cover - asserted below
            writer_errors.append(exc)

    writer = threading.Thread(target=remove_lock_before_stat, daemon=True)
    writer.start()
    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=_HEALTHY_SSH, lock=lock)
    writer.join(timeout=5)

    assert not writer.is_alive(), "FIFO writer did not finish"
    assert not writer_errors, writer_errors
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert "CANNOT-VERIFY" in proc.stdout
    assert "could not stat lock directory" in proc.stdout
    assert "held for -1 min" not in proc.stdout


# --- transport: which machine did the numbers come from? (2026-08-31) ---
#
# The spool host is named by an ssh ALIAS. When that alias points back at the
# machine running the doctor, ssh is the wrong transport -- Pro cannot ssh to
# itself, so the probe abstained on every run and the P0 spool went structurally
# unmeasured on the one machine that owns it. The fix must not overreach the
# other way: every organism machine HAS a ~/.organism/tg_spool, so "the path
# exists locally" can never be the reason to read it locally.

_GDASH = "-G"


def _ssh_fake(*, resolves_to: str | None, user: str | None, remote_body: str) -> str:
    """A fake ssh that answers `ssh -G <alias>` separately from a real call.

    `resolves_to=None` => the alias cannot be resolved at all (ssh -G fails).
    """
    if resolves_to is None:
        g = "exit 1\n"
    else:
        g = f'printf "hostname {resolves_to}\\n"; printf "user {user}\\n"; exit 0\n'
    return (
        f'if [ "$1" = "{_GDASH}" ]; then\n{g}fi\n'
        + remote_body
    )


def _local_spool(tmp: Path, *, pending_lines: int, p0_today: int) -> Path:
    spool = tmp / "spool"
    spool.mkdir()
    if pending_lines:
        (spool / "pending.jsonl").write_text("{}\n" * pending_lines, encoding="utf-8")
    (spool / "last_flush.json").write_text('{"ts": 1786000000}', encoding="utf-8")
    today = __import__("datetime").date.today().isoformat()
    (spool / "archive-p0.jsonl").write_text(f'{{"ts":"{today}"}}\n' * p0_today, encoding="utf-8")
    return spool


def test_alias_resolving_to_this_machine_is_read_locally_not_over_ssh(tmp_path: Path) -> None:
    """Guilt for the original defect: if the doctor still reached for ssh here,
    the fake's non-`-G` branch exits 9 and the probe would say CANNOT-VERIFY."""
    spool = _local_spool(tmp_path, pending_lines=3, p0_today=2)
    ssh = _ssh_fake(
        resolves_to=socket.gethostname(),  # always in the local identity set
        user=os.environ.get("USER") or "nobody",
        remote_body="exit 9\n",  # any real ssh call is a failure of the fix
    )
    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=ssh,
                       lock=tmp_path / "no-such-lock", spool=spool)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "source: local" in proc.stdout
    assert "pending (waiting for digest flush): 3" in proc.stdout
    assert "P0 archived today: 2" in proc.stdout
    assert "CANNOT-VERIFY" not in proc.stdout


def test_a_machine_that_merely_has_a_spool_dir_is_not_the_spool_host(tmp_path: Path) -> None:
    """The overreach this fix must not commit: Mini also has a spool directory.
    A local read there would report MINI's numbers under PRO's name."""
    spool = _local_spool(tmp_path, pending_lines=99, p0_today=99)  # the wrong answer
    ssh = _ssh_fake(
        resolves_to="not-this-machine.invalid",  # RFC 2606: can never be local
        user="someone",
        remote_body=('printf "spool_dir OK\\n"\n'
                     'printf "pending %s\\n" 4\n'
                     'printf "last_flush %s\\n" \'{"ts": 1786000000}\'\n'
                     'printf "p0_today %s\\n" 6\n'),
    )
    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=ssh,
                       lock=tmp_path / "no-such-lock", spool=spool)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "source: ssh fakehost" in proc.stdout
    assert "pending (waiting for digest flush): 4" in proc.stdout
    for wrong in ("pending (waiting for digest flush): 99", "P0 archived today: 99"):
        assert wrong not in proc.stdout, "the local spool was read for a REMOTE host"


def test_an_unresolvable_alias_falls_back_to_ssh_never_to_a_local_guess(tmp_path: Path) -> None:
    spool = _local_spool(tmp_path, pending_lines=99, p0_today=99)
    ssh = _ssh_fake(
        resolves_to=None,
        user=None,
        remote_body=('printf "spool_dir OK\\n"\n'
                     'printf "pending %s\\n" 4\n'
                     'printf "last_flush %s\\n" \'{"ts": 1786000000}\'\n'
                     'printf "p0_today %s\\n" 6\n'),
    )
    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=ssh,
                       lock=tmp_path / "no-such-lock", spool=spool)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "source: ssh fakehost" in proc.stdout
    assert "resolved no hostname" in proc.stdout
    for wrong in ("pending (waiting for digest flush): 99", "P0 archived today: 99"):
        assert wrong not in proc.stdout, "an unresolvable alias fell through to a local read"


def test_alias_resolving_here_but_as_another_user_stays_on_ssh(tmp_path: Path) -> None:
    """Same host, different account = a different HOME = a different spool."""
    spool = _local_spool(tmp_path, pending_lines=99, p0_today=99)
    ssh = _ssh_fake(
        resolves_to=socket.gethostname(),
        user="somebody-else",
        remote_body=('printf "spool_dir OK\\n"\n'
                     'printf "pending %s\\n" 4\n'
                     'printf "last_flush %s\\n" \'{"ts": 1786000000}\'\n'
                     'printf "p0_today %s\\n" 6\n'),
    )
    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=ssh,
                       lock=tmp_path / "no-such-lock", spool=spool)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "source: ssh fakehost" in proc.stdout
    assert "as user 'somebody-else'" in proc.stdout


# --- a drained spool is a measurement, not an abstention (2026-08-31) ---


def test_absent_pending_file_reads_as_drained_not_as_unmeasurable(tmp_path: Path) -> None:
    """tg_digest_flush.py RENAMES pending.jsonl away to claim it and recreates
    it only when a send fails, so between flushes it is absent on a HEALTHY
    machine. Reading that as CANNOT-VERIFY made the probe red exactly when
    nothing was wrong."""
    spool = _local_spool(tmp_path, pending_lines=0, p0_today=2)  # no pending.jsonl
    ssh = _ssh_fake(resolves_to=socket.gethostname(),
                    user=os.environ.get("USER") or "nobody", remote_body="exit 9\n")
    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=ssh,
                       lock=tmp_path / "no-such-lock", spool=spool)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "DRAINED" in proc.stdout
    assert "CANNOT-VERIFY" not in proc.stdout


def test_absent_spool_directory_is_still_unmeasurable(tmp_path: Path) -> None:
    """The guard against over-correcting: a file missing INSIDE the spool is a
    state; the spool itself missing is an unmeasured host."""
    ssh = _ssh_fake(resolves_to=socket.gethostname(),
                    user=os.environ.get("USER") or "nobody", remote_body="exit 9\n")
    proc = _run_doctor(tmp_path, gh_body=_HEALTHY_GH, ssh_body=ssh,
                       lock=tmp_path / "no-such-lock", spool=tmp_path / "no-spool-here")
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert "CANNOT-VERIFY" in proc.stdout
    assert "spool directory" in proc.stdout
