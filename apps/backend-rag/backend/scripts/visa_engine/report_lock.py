"""Slice B2''-a' -- exclusive one-writer-per-report lock (KERNEL-HELD) + atomic JSON write.

R-FLOCK (2026-09-19): this module replaces the pid-file PROTOCOL of the previous attempt
(#6884) with a lock the kernel arbitrates end to end. ``fcntl.flock(fd, LOCK_EX | LOCK_NB)``
on ``<report>.lock``, the fd held open for the whole run: there is no gap between "the
lockfile exists" and "the lockfile is populated" the way there was with an ``O_EXCL``
create followed by a separate payload write, because nothing is EVER derived from what the
lockfile contains -- only from ``flock``'s own result -- and the kernel releases the lock on
ANY death of the holder, SIGKILL and SIGTERM both included. There is therefore no stale
state, no break-flag, no pid-liveness check and no pid-reuse trap.

THE INVARIANT: no decision in this module is ever derived from the lockfile's content.
The lockfile is NEVER unlinked, by anyone -- unlink + flock is the classic two-holder race
(a waiter still holding the old inode and a newcomer creating a fresh one both "hold" a
lock), so a leftover ``<report>.lock`` sitting on disk means nothing and is never cleaned up
by this module.

Declared limits (one sentence each, repeated in the PR body):
- The lock is ADVISORY: a writer that never takes ``ReportLock`` is not stopped by it.
- Local filesystems only -- ``flock`` over NFS/SMB is not guaranteed to be exclusive.
- POSIX only (``fcntl``); on Windows the import of this module fails, closed.
- A SIGKILL landing inside ``atomic_write_json``'s write leaves an orphan
  ``<report>.<pid>.tmp`` that nothing in this module reaps.
- File descriptors are non-inheritable by default and the runner does not fork; a forking
  caller would extend the hold to its children.
- A read-only directory, a lockfile at mode ``0o400`` or a foreign-owned directory raise a
  raw ``PermissionError`` out of ``os.open`` instead of ``ReportLockError`` -- a caller that
  only catches ``ReportLockError`` (the runner, Slice B2''-b) will NOT catch this.
- The lock is keyed on the report's PATH TEXT (``with_name``), not on the report's on-disk
  identity: a symlinked or hard-linked report FILE reachable under a second name yields a
  second, independent lock path and therefore a second holder on the same report.
Stale locks, SIGTERM handling and pid reuse are NOT declared limits: those states do not
exist for a kernel-held lock (see the module's tests for SIGKILL, SIGTERM and a leftover
lockfile carrying a live unrelated pid).

Nothing in this repo imports this module yet (Slice B2''-b, the runner, is the first
consumer, from a fresh ``origin/main`` that contains this module's merge).
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any


class ReportLockError(RuntimeError):
    """Another run already holds the kernel ``flock`` on this report."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def atomic_write_json(path: Path, obj: Mapping[str, Any]) -> None:
    """Write JSON atomically: a per-process temp name in the same directory, then
    ``os.replace`` -- a reader never sees a partial file, and two writers racing on the
    same ``path`` never share one fixed temp name.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _informational_pid(fd: int) -> int | None:
    """Best-effort pid for the ERROR MESSAGE only -- never for a decision (see the module
    invariant). Any failure to read or parse the lockfile yields ``None``; the caller still
    refuses unconditionally on ``flock``'s own result.
    """

    try:
        raw = os.pread(fd, 65536, 0)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        return None
    pid = data.get("pid") if isinstance(data, dict) else None
    return pid if isinstance(pid, int) else None


class ReportLock:
    """Exclusive, kernel-held lock beside a report path.

    ``acquire()`` opens ``<report>.lock`` (creating it if needed, mode 0o600) and takes
    ``fcntl.flock(fd, LOCK_EX | LOCK_NB)`` on it. On ``BlockingIOError`` the fd is closed and
    ``ReportLockError`` is raised naming the lock path (a pid read from the file may be
    appended, informational only -- see the module invariant). After acquiring, the lockfile
    is truncated and rewritten with ``{"pid", "started_at"}`` for an operator's eyes; nothing
    in this class ever reads that payload back to make a decision. ``release()`` drops the
    flock and closes the fd; it is a no-op when the lock is not held (a refused ``acquire()``
    never sets the held flag, so releasing after a refusal never touches the live owner).
    The lockfile itself is never removed.

    Use as a context manager::

        with ReportLock(report_path):
            ...  # exclusive section
    """

    def __init__(self, report_path: Path) -> None:
        report_path = Path(report_path)
        self.path = report_path.with_name(f"{report_path.name}.lock")
        self._fd: int | None = None
        self._acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pid = _informational_pid(fd)
            os.close(fd)
            suffix = f" (pid {pid} per the lockfile)" if pid is not None else ""
            raise ReportLockError(
                f"another run owns {self.path}{suffix} -- refusing to run two writers "
                "against the same report"
            ) from None
        except BaseException:
            os.close(fd)
            raise

        payload = json.dumps({"pid": os.getpid(), "started_at": _utcnow().isoformat()}).encode("utf-8")
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, payload)
        self._fd = fd
        self._acquired = True

    def release(self) -> None:
        if not self._acquired:
            return
        fd = self._fd
        self._fd = None
        self._acquired = False
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def __enter__(self) -> ReportLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
