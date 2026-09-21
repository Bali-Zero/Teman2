"""Guilt tests for Slice B2''-a': the kernel-held ``flock`` report lock + atomic JSON write.

Every clause about PROCESSES (concurrent races, SIGKILL/SIGTERM of the holder) is proved
with real subprocesses, synchronised through sentinel files on disk -- never a bare sleep as
the only synchronisation primitive. Clauses about the context manager's own mechanics
(release on normal exit / on an exception, a second in-process lock, inode stability) run
in-process, since no second process is needed to observe them.

Every wait below is bounded, two different ways: a `subprocess.wait(timeout=...)` on every
cross-process wait, AND `_bounded()` (SIGALRM) around every IN-PROCESS `acquire()` call --
because `subprocess.wait(timeout=...)` cannot see a hang that happens INSIDE this process's
own blocking `flock()` call (OBS-1, gate GATE-B2F-REPORT-6890.md: under mutation M2 --
`LOCK_NB` dropped -- `test_second_reportlock_in_the_same_process_refuses` hung the suite
because its second, contending `acquire()` runs in the pytest process itself, with nothing
external to time it out). A regression that makes a lock call BLOCK now fails that ONE test
within `_bounded`'s cap -- it never hangs the suite. `test_a_live_holder_is_refused_promptly_
not_serialized` additionally proves the SPEED of a refusal, not just its eventual truth: the
headline race test (a) cannot tell a refusal from a lock that merely serialised the
contenders (both look like "exactly one holder ever writes"), so M2 passes it unnoticed.
"""

from __future__ import annotations

import contextlib
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

_ACQUIRE_BOUND_S = 10.0


class BoundedAcquireTimeout(AssertionError):
    """Raised by `_bounded()` when an in-process call blocked past its cap -- turns a
    regression that would HANG the suite (e.g. M2: `LOCK_NB` dropped) into one FAILED test
    instead. Subclasses `AssertionError` so it reads as a normal pytest failure, not an error.
    """


@contextlib.contextmanager
def _bounded(seconds: float = _ACQUIRE_BOUND_S):
    """Interrupt a blocking syscall (a blocking `flock()`) via `SIGALRM`.

    PEP 475 retries a syscall on `EINTR` only while no exception is pending after the signal
    handler returns; raising inside the handler makes `PyErr_CheckSignals()` report a pending
    exception, so the retry loop breaks and the exception propagates out of the blocked C
    call -- it does not silently restart it. POSIX only, matching this module's own declared
    limit; not usable on Windows (no `SIGALRM`).
    """

    def _on_alarm(signum: int, frame: object) -> None:
        raise BoundedAcquireTimeout(
            f"blocked for more than {seconds}s -- a regression made a lock call BLOCK "
            "instead of refusing or succeeding"
        )

    previous = signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)

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

_KILL_POINT_SCRIPT = """
import os
import pathlib
import sys
import time
from pathlib import Path
from backend.scripts.visa_engine.report_lock import atomic_write_json

report = Path(sys.argv[1])
sentinel_dir = Path(sys.argv[2])
kill_point = sys.argv[3]
size = int(sys.argv[4])

atomic_write_json(report, {"stage": "first"})

fired = False
original_os_replace = os.replace
original_os_rename = os.rename
original_path_replace = pathlib.Path.replace
original_path_rename = pathlib.Path.rename

def _write_sentinel(name, content):
    # Written to a temp name in the same directory and moved into place with the UNPATCHED
    # os.replace (never the hooked one -- this can fire before `fired` is set, e.g. the
    # "no_replace" sentinel on the M4 mutation path where the hook never triggers at all, and
    # going through the patched os.replace there would mis-arm _hook a second time). A reader
    # polling on the target path's existence can now only ever observe it fully written --
    # os.replace is a single rename syscall on POSIX, so there is no window where the path
    # exists with partial or empty content (OBS-e, GATE-B2I-REPORT-6920.md).
    path = sentinel_dir / name
    tmp_path = sentinel_dir / f".{name}.tmp-{os.getpid()}"
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    original_os_replace(tmp_path, path)

def _hook(source, target, real_replace):
    global fired
    if fired:
        return real_replace(source, target)
    fired = True
    if kill_point == "before_replace":
        _write_sentinel("in_window", os.fspath(source))
        while True:
            time.sleep(3600)
    result = real_replace(source, target)
    _write_sentinel("replaced", "replaced")
    while True:
        time.sleep(3600)
    return result

def _os_replace(source, target, *args):
    return _hook(source, target, lambda src, dst: original_os_replace(src, dst, *args))

def _os_rename(source, target, *args):
    return _hook(source, target, lambda src, dst: original_os_rename(src, dst, *args))

def _path_replace(self, target):
    return _hook(self, target, lambda src, dst: original_path_replace(src, dst))

def _path_rename(self, target):
    return _hook(self, target, lambda src, dst: original_path_rename(src, dst))

os.replace = _os_replace
os.rename = _os_rename
pathlib.Path.replace = _path_replace
pathlib.Path.rename = _path_rename

atomic_write_json(report, {"blob": "x" * size, "stage": "second"})
_write_sentinel("no_replace", "no_replace")
sys.exit(3)
"""


def _wait_for(path: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {path} to appear")
        time.sleep(0.02)


def _wait_for_any(
    paths: tuple[Path, ...], process: subprocess.Popen[bytes], timeout: float
) -> Path | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() <= deadline:
        for path in paths:
            try:
                # st_size > 0, not bare existence: a sentinel created with open("w") before
                # its content is written would otherwise be observable at size 0 in the gap,
                # and an empty path read back as "" resolves to Path('.') -- which exists and
                # (as a directory) reports a nonzero size of its own, so every later assertion
                # keyed on "the marker exists" would pass VACUOUSLY (OBS-e,
                # GATE-B2I-REPORT-6920.md). Defense in depth: the writer (`_write_sentinel`)
                # is now atomic too, so this branch should never observe a zero-byte marker in
                # practice -- but the reader must not TRUST that on the writer's word alone.
                if path.stat().st_size > 0:
                    return path
            except FileNotFoundError:
                pass
        if process.poll() is not None:
            return None
        time.sleep(0.02)
    return None


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

    with _bounded():
        with ReportLock(report):
            assert lock_path.exists()

    # released -- a fresh acquire succeeds at once
    lock = ReportLock(report)
    with _bounded():
        lock.acquire()
    lock.release()


def test_lock_is_released_on_an_exception_inside_the_locked_section(tmp_path: Path) -> None:
    report = tmp_path / "report.json"

    with pytest.raises(RuntimeError, match="boom"):
        with _bounded():
            with ReportLock(report):
                raise RuntimeError("boom")

    lock = ReportLock(report)
    with _bounded():
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
        with _bounded():
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
        with _bounded():
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
    with _bounded():
        lock.acquire()  # empty content must not be read as "stale" or refuse anything
    assert json.loads(lock_path.read_text())["pid"] == os.getpid()
    lock.release()

    lock_path.write_bytes(b"{not valid json at all")
    lock = ReportLock(report)
    with _bounded():
        lock.acquire()  # unparseable content must not be read as "stale" or refuse anything
    assert json.loads(lock_path.read_text())["pid"] == os.getpid()
    lock.release()

    live = _spawn_live_process()
    try:
        lock_path.write_text(json.dumps({"pid": live.pid, "started_at": "now"}), encoding="utf-8")
        lock = ReportLock(report)
        with _bounded():
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
    """OBS-1: `second.acquire()` contends against `first` in THIS process with nothing else
    to release it -- under M2 (`LOCK_NB` dropped) it would block forever, a genuine deadlock
    no `subprocess.wait(timeout=...)` anywhere else in this suite could see. `_bounded()` is
    what turns that into a failed test instead of a hung one.
    """
    report = tmp_path / "report.json"

    first = ReportLock(report)
    with _bounded():
        first.acquire()
    try:
        second = ReportLock(report)
        with _bounded(), pytest.raises(ReportLockError):
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
    with _bounded():
        lock.acquire()
    ino_held = lock_path.stat().st_ino
    lock.release()

    assert lock_path.exists()
    assert lock_path.stat().st_ino == ino_held

    lock2 = ReportLock(report)
    with _bounded():
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
        with _bounded(), pytest.raises(ReportLockError):
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
# blocking-lock detector -- a REFUSAL must be PROMPT, not eventually-true (OBS-1 cure #2)
# ---------------------------------------------------------------------------


def test_a_live_holder_is_refused_promptly_not_serialized(tmp_path: Path) -> None:
    """Test (a)'s headline race cannot distinguish "exactly one holder every round" from
    "every contender eventually gets a turn, one at a time" -- a blocking `flock()` (M2)
    produces the SECOND shape and (a) still passes it, because mutual exclusion still holds
    under serialization. This test asserts the shape a kernel-held NON-BLOCKING lock must
    have instead: while a holder is alive, a contender is turned away FAST, never left
    waiting on the holder's eventual release.
    """
    report = tmp_path / "report.json"
    ready_file = tmp_path / "ready"

    holder = _run_script(_HOLD_SCRIPT, str(report), str(ready_file))
    try:
        _wait_for(ready_file)

        waiter = ReportLock(report)
        start = time.monotonic()
        with _bounded(2.0), pytest.raises(ReportLockError):
            waiter.acquire()
        elapsed = time.monotonic() - start
        waiter.release()
        assert elapsed < 2.0, (
            f"refusal took {elapsed:.3f}s while the holder was alive -- a blocking lock "
            "would serialise behind it instead of refusing"
        )
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10.0)


# ---------------------------------------------------------------------------
# (j) atomicity -- two proofs that can fail
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kill_point", ["before_replace", "after_replace"])
def test_sigkill_inside_atomic_write_never_corrupts_the_target(
    tmp_path: Path, kill_point: str
) -> None:
    """The child parks itself inside the replace hook, making SIGKILL deterministic.
    The 60-second bound covers startup and the first write; load cannot make the bound
    misjudge the write window. History: GATE-B2G/B2H reports.
    """
    report = tmp_path / "report.json"
    sentinel_dir = tmp_path / "sentinels"
    sentinel_dir.mkdir()
    size = 1_000_000
    in_window = sentinel_dir / "in_window"
    replaced = sentinel_dir / "replaced"
    no_replace = sentinel_dir / "no_replace"
    writer = _run_script(
        _KILL_POINT_SCRIPT, str(report), str(sentinel_dir), kill_point, str(size)
    )
    try:
        # 60s covers startup and the first write; load can only delay reaching the parked
        # window, so this bound cannot mistake a shorter write window for a failure.
        marker = _wait_for_any((in_window, replaced, no_replace), writer, timeout=60.0)
        if marker is None:
            if writer.poll() is None:
                pytest.fail("writer never reached the write window in 60 s")
            _, stderr = writer.communicate(timeout=10.0)
            tail = stderr.decode(errors="replace")[-500:]
            pytest.fail(f"writer exited before the write window (code {writer.returncode}): {tail}")
        if marker == no_replace:
            pytest.fail(
                "atomic_write_json returned without ever calling replace/rename: the target "
                "is written IN PLACE, so a SIGKILL mid-write tears it"
            )
        if marker == in_window:
            try:
                data = json.loads(report.read_text())
            except json.JSONDecodeError as exc:
                pytest.fail(
                    f"the target did not parse while the writer was parked BEFORE its "
                    f"replace: {exc}"
                )
            assert data["stage"] == "first", (
                "target already reflects the second write although the writer is still "
                "parked BEFORE replacing it into place"
            )
            source = Path(in_window.read_text())
            assert source != report, (
                "the source path IS the target -- atomic_write_json is not writing through "
                "a separate temp file"
            )
            assert source.exists(), (
                "the temp source no longer exists although the writer is parked BEFORE "
                "replacing it into place"
            )
            assert source.stat().st_size > 0, (
                "the temp source is empty although the writer already wrote its content "
                "before parking"
            )
        os.kill(writer.pid, signal.SIGKILL)
        writer.wait(timeout=10.0)
        assert writer.returncode == -signal.SIGKILL
        data = json.loads(report.read_text())
        if marker == in_window:
            assert data["stage"] == "first", "target changed although the writer was killed BEFORE replace"
        else:
            assert data["stage"] == "second", "target incomplete although replace had returned"
            assert len(data["blob"]) == size
    finally:
        if writer.poll() is None:
            writer.kill()
            writer.wait(timeout=10.0)


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

    # 40 MB: measured empirically against the M4 mutation (plain chunked write, no
    # temp+os.replace) -- 4 MB was NOT reliably red (0/5 runs caught a torn read on this
    # host/filesystem, APFS serialises small single-buffer writes against concurrent
    # readers closely enough to hide the race); 40 MB is red 5/5.
    size = 40_000_000
    iterations = 50
    try:
        for i in range(iterations):
            atomic_write_json(report, {"stage": "spin", "round": i, "blob": "y" * size})
    finally:
        stop.set()
        reader_thread.join(timeout=15.0)

    assert errors == [], f"a concurrent read observed a partial write: {errors[0]}"
    assert read_count >= 10, f"only {read_count} reads completed -- not enough overlap to prove anything"
