"""Guilt tests for Slice B2''-a': the kernel-held ``flock`` report lock + atomic JSON write.

Every clause about PROCESSES (concurrent races, SIGKILL/SIGTERM of the holder) is proved
with real subprocesses, synchronised through sentinel files on disk -- never a bare sleep as
the only synchronisation primitive. Clauses about the context manager's own mechanics
(release on normal exit / on an exception, a second in-process lock, inode stability) run
in-process, since no second process is needed to observe them. Every wait below is bounded:
a regression that would hang the module hangs a `subprocess.wait(timeout=...)` instead,
which raises and fails the test -- it never hangs the suite.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from backend.scripts.visa_engine.report_lock import ReportLock, ReportLockError, atomic_write_json

_REPO_ROOT_ENV = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[4])}

_LOSER_SCRIPT = """
import json, sys
from pathlib import Path
from backend.scripts.visa_engine.report_lock import ReportLock, ReportLockError

report = Path(sys.argv[1])
out_file = Path(sys.argv[2])
try:
    with ReportLock(report):
        out_file.write_text(json.dumps({"acquired": True}))
except ReportLockError as exc:
    out_file.write_text(json.dumps({"acquired": False, "message": str(exc)}))
"""

_HOLD_SCRIPT = """
import sys, time
from pathlib import Path
from backend.scripts.visa_engine.report_lock import ReportLock

report = Path(sys.argv[1])
ready_file = Path(sys.argv[2])

with ReportLock(report):
    ready_file.write_text("ready")
    time.sleep(30)
"""

_SLEEP_SCRIPT = "import time; time.sleep(30)"

_CONTENDER_SCRIPT = """
import os, sys, time
from pathlib import Path
from backend.scripts.visa_engine.report_lock import ReportLock, ReportLockError, atomic_write_json

report = Path(sys.argv[1])
worker_id = sys.argv[2]
rounds = int(sys.argv[3])
ready_file = Path(sys.argv[4])
go_file = Path(sys.argv[5])
log_path = Path(sys.argv[6])

ready_file.write_text("ready")
deadline = time.monotonic() + 20.0
while not go_file.exists():
    if time.monotonic() > deadline:
        raise SystemExit("timed out waiting for the go file")
    time.sleep(0.005)

log_fd = os.open(str(log_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)

def _log(line):
    os.write(log_fd, (line + "\\n").encode("utf-8"))

for r in range(rounds):
    try:
        with ReportLock(report):
            start = time.time()
            atomic_write_json(report, {"holder": worker_id, "round": r})
            time.sleep(0.01)
            end = time.time()
        _log(f"WIN {worker_id} {r} {start!r} {end!r}")
    except ReportLockError as exc:
        msg = str(exc)
        assert "\\n" not in msg, "a refusal must be ONE line, never a traceback"
        _log(f"LOSE {worker_id} {r}")
    time.sleep(0.002)

os.close(log_fd)
"""

_ATOMIC_WRITE_HOLD_SCRIPT = """
import sys
from pathlib import Path
from backend.scripts.visa_engine.report_lock import atomic_write_json

report = Path(sys.argv[1])
ready_file = Path(sys.argv[2])
size = int(sys.argv[3])

atomic_write_json(report, {"stage": "first"})
ready_file.write_text("ready")
atomic_write_json(report, {"stage": "second", "blob": "x" * size})
"""


def _wait_for(path: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {path} to appear")
        time.sleep(0.02)


def _run_script(script: str, *args: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-c", script, *args],
        env=_REPO_ROOT_ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _spawn_live_process() -> subprocess.Popen[bytes]:
    return subprocess.Popen([sys.executable, "-c", _SLEEP_SCRIPT])


# ---------------------------------------------------------------------------
# (a) N=2 and N=4 processes released together by a barrier file, >= 20 rounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 4])
def test_n_processes_released_by_a_barrier_race_and_exactly_one_holds_at_a_time(
    tmp_path: Path, n: int
) -> None:
    report = tmp_path / "report.json"
    log_path = tmp_path / "race.log"
    go_file = tmp_path / "go"
    rounds = 20

    ready_files = [tmp_path / f"ready-{i}" for i in range(n)]
    procs = [
        _run_script(
            _CONTENDER_SCRIPT,
            str(report),
            str(i),
            str(rounds),
            str(ready_files[i]),
            str(go_file),
            str(log_path),
        )
        for i in range(n)
    ]
    try:
        for ready_file in ready_files:
            _wait_for(ready_file, timeout=15.0)
        go_file.write_text("go")  # release all N contenders together

        for proc in procs:
            rc = proc.wait(timeout=30.0)
            assert rc == 0, proc.stderr.read().decode("utf-8", errors="replace")
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10.0)

    wins: list[tuple[float, float, str, str]] = []
    for line in log_path.read_text().splitlines():
        parts = line.split()
        if parts[0] == "WIN":
            _, worker_id, round_no, start, end = parts
            wins.append((float(start), float(end), worker_id, round_no))

    assert len(wins) >= 1
    wins.sort()
    for (_, end1, *_rest1), (start2, *_rest2) in zip(wins, wins[1:], strict=False):
        assert end1 <= start2, "two holders overlapped -- mutual exclusion violated"

    # the winner's file is intact: it always matches the chronologically LAST hold.
    last_end, _, last_worker, last_round = max(wins, key=lambda w: w[1])
    assert json.loads(report.read_text()) == {"holder": last_worker, "round": int(last_round)}


# ---------------------------------------------------------------------------
# (b) / (c) context-manager mechanics -- no second process needed
# ---------------------------------------------------------------------------


def test_lock_is_released_on_normal_exit(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    lock_path = report.with_name(report.name + ".lock")

    with ReportLock(report):
        assert lock_path.exists()

    # released -- a fresh acquire succeeds at once
    lock = ReportLock(report)
    lock.acquire()
    lock.release()


def test_lock_is_released_on_an_exception_inside_the_locked_section(tmp_path: Path) -> None:
    report = tmp_path / "report.json"

    with pytest.raises(RuntimeError, match="boom"):
        with ReportLock(report):
            raise RuntimeError("boom")

    lock = ReportLock(report)
    lock.acquire()
    lock.release()


# ---------------------------------------------------------------------------
# (d) / (e) SIGKILL / SIGTERM of the holder -- the kernel releases at once
# ---------------------------------------------------------------------------


def test_sigkill_of_the_holder_releases_the_lock_at_once_no_flag(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    ready_file = tmp_path / "ready"

    holder = _run_script(_HOLD_SCRIPT, str(report), str(ready_file))
    try:
        _wait_for(ready_file)
        os.kill(holder.pid, signal.SIGKILL)
        rc = holder.wait(timeout=10.0)
        assert rc == -signal.SIGKILL

        lock = ReportLock(report)  # no flag, no stale-check: this must just work
        lock.acquire()
        lock.release()
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10.0)


def test_sigterm_of_the_holder_releases_the_lock_at_once_no_flag(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    ready_file = tmp_path / "ready"

    holder = _run_script(_HOLD_SCRIPT, str(report), str(ready_file))
    try:
        _wait_for(ready_file)
        os.kill(holder.pid, signal.SIGTERM)
        rc = holder.wait(timeout=10.0)
        assert rc == -signal.SIGTERM

        lock = ReportLock(report)
        lock.acquire()
        lock.release()
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10.0)


# ---------------------------------------------------------------------------
# (f) a leftover lockfile's CONTENT is never consulted
# ---------------------------------------------------------------------------


def test_leftover_lockfile_content_is_never_consulted(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    lock_path = report.with_name(report.name + ".lock")

    lock_path.write_bytes(b"")
    lock = ReportLock(report)
    lock.acquire()  # empty content must not be read as "stale" or refuse anything
    assert json.loads(lock_path.read_text())["pid"] == os.getpid()
    lock.release()

    lock_path.write_bytes(b"{not valid json at all")
    lock = ReportLock(report)
    lock.acquire()  # unparseable content must not be read as "stale" or refuse anything
    assert json.loads(lock_path.read_text())["pid"] == os.getpid()
    lock.release()

    live = _spawn_live_process()
    try:
        lock_path.write_text(json.dumps({"pid": live.pid, "started_at": "now"}), encoding="utf-8")
        lock = ReportLock(report)
        lock.acquire()  # a live-but-unrelated pid in the file must not refuse this
        assert json.loads(lock_path.read_text())["pid"] == os.getpid()
        lock.release()
    finally:
        live.kill()
        live.wait(timeout=10.0)


# ---------------------------------------------------------------------------
# (g) two ReportLock objects on one path, in ONE process
# ---------------------------------------------------------------------------


def test_second_reportlock_in_the_same_process_refuses(tmp_path: Path) -> None:
    report = tmp_path / "report.json"

    first = ReportLock(report)
    first.acquire()
    try:
        second = ReportLock(report)
        with pytest.raises(ReportLockError):
            second.acquire()
    finally:
        first.release()


# ---------------------------------------------------------------------------
# (h) the lockfile persists; its inode is unchanged across acquire/release cycles
# ---------------------------------------------------------------------------


def test_lockfile_persists_and_its_inode_is_unchanged_across_cycles(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    lock_path = report.with_name(report.name + ".lock")

    lock = ReportLock(report)
    lock.acquire()
    ino_held = lock_path.stat().st_ino
    lock.release()

    assert lock_path.exists()
    assert lock_path.stat().st_ino == ino_held

    lock2 = ReportLock(report)
    lock2.acquire()
    assert lock_path.stat().st_ino == ino_held
    lock2.release()
    assert lock_path.stat().st_ino == ino_held


# ---------------------------------------------------------------------------
# (i) release() after a REFUSED acquire leaves the live owner's hold intact
# ---------------------------------------------------------------------------


def test_release_after_a_refused_acquire_leaves_the_live_owner_intact(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    ready_file = tmp_path / "ready"

    holder = _run_script(_HOLD_SCRIPT, str(report), str(ready_file))
    try:
        _wait_for(ready_file)

        waiter = ReportLock(report)
        with pytest.raises(ReportLockError):
            waiter.acquire()
        waiter.release()  # must be a no-op -- the live holder must be untouched

        loser_out = tmp_path / "loser-out.json"
        loser = _run_script(_LOSER_SCRIPT, str(report), str(loser_out))
        assert loser.wait(timeout=10.0) == 0
        result = json.loads(loser_out.read_text())
        assert result["acquired"] is False  # the original holder still owns the lock
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10.0)


# ---------------------------------------------------------------------------
# (j) atomicity -- two proofs that can fail
# ---------------------------------------------------------------------------


def test_sigkill_inside_atomic_write_never_corrupts_the_target(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    ready_file = tmp_path / "ready"
    size = 20_000_000  # large enough that the temp file's write is still in flight

    writer = _run_script(_ATOMIC_WRITE_HOLD_SCRIPT, str(report), str(ready_file), str(size))
    try:
        _wait_for(ready_file)

        deadline = time.monotonic() + 10.0
        tmp_hit: Path | None = None
        while time.monotonic() < deadline:
            matches = list(tmp_path.glob("report.json.*.tmp"))
            if matches:
                tmp_hit = matches[0]
                break
        assert tmp_hit is not None, (
            "the writer never created a temp file -- atomic_write_json is no longer "
            "writing through a per-process temp name"
        )
        os.kill(writer.pid, signal.SIGKILL)
        writer.wait(timeout=10.0)
    finally:
        if writer.poll() is None:
            writer.kill()
            writer.wait(timeout=10.0)

    # os.replace never ran: the PREVIOUS write survives, parseable and unchanged.
    assert json.loads(report.read_text()) == {"stage": "first"}


def test_concurrent_reader_always_parses_during_repeated_large_rewrites(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    atomic_write_json(report, {"stage": "seed", "round": -1})

    stop = threading.Event()
    errors: list[str] = []
    read_count = 0

    def _reader() -> None:
        nonlocal read_count
        while not stop.is_set():
            try:
                data = json.loads(report.read_text())
            except json.JSONDecodeError as exc:
                errors.append(str(exc))
                return
            assert isinstance(data, dict)
            read_count += 1

    reader_thread = threading.Thread(target=_reader)
    reader_thread.start()

    size = 4_000_000
    iterations = 50
    try:
        for i in range(iterations):
            atomic_write_json(report, {"stage": "spin", "round": i, "blob": "y" * size})
    finally:
        stop.set()
        reader_thread.join(timeout=15.0)

    assert errors == [], f"a concurrent read observed a partial write: {errors[0]}"
    assert read_count >= 10, f"only {read_count} reads completed -- not enough overlap to prove anything"
