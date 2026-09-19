"""Slice B2''-a -- exclusive one-writer-per-report lock + atomic JSON write.

Extracted unchanged from the B2' live runner (``enumerate_live.py``), where the gate
(GATE-B2B-REPORT-6871.md, Check 5) proved this behaviour against two REAL processes: a
second runner refuses with one line naming the lock path and the owning pid, never a
traceback; the lock releases on both a normal exit and an exception; a stale lock (owning
pid not running) is refused unless ``--break-stale-lock``, in which case it is removed and a
fresh lock is created in its place; ``break_stale=True`` against a LIVE pid still refuses.

Declared limit (gate OBS-A): SIGTERM has no handler here, so ``finally``/``__exit__`` never
runs and a SIGTERM'd holder leaves its lock behind -- clean and breakable on the stale path
(the owning pid is dead by the time anyone else looks), never a deadlock, but not released
either. Do not add a signal handler in this module.

Nothing in this repo imports this module yet (Slice B2''-b, the runner, is the first
consumer, from a fresh ``origin/main`` that contains this module's merge).
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any


class ReportLockError(RuntimeError):
    """Another runner already owns this report's lock, or the lock is stale."""


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # e.g. EPERM: the pid exists, just isn't ours to signal
    return True


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def atomic_write_json(path: Path, obj: Mapping[str, Any]) -> None:
    """Write JSON atomically: a per-process temp name in the same directory, then
    ``os.replace`` -- a reader never sees a partial file, and two writers racing on the
    same ``path`` never share one fixed temp name (the exclusive lock above is what
    actually prevents the race; this is the second, independent layer).
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


class ReportLock:
    """Exclusive lock beside a report path: O_EXCL create, holds pid + start time as
    JSON, released in ``__exit__`` on normal exit AND on exception. A live-owned lock
    refuses the second holder with ONE line naming the lock path and the owning pid --
    never a raw traceback. A stale lock (owning pid not running) is refused unless
    ``break_stale=True``, in which case it is removed and a fresh lock is created in its
    place; ``break_stale=True`` against a LIVE pid still refuses.

    Use as a context manager::

        with ReportLock(report_path, break_stale=args.break_stale_lock):
            ...  # exclusive section
    """

    def __init__(self, report_path: Path, *, break_stale: bool = False) -> None:
        self.path = report_path.with_name(f"{report_path.name}.lock")
        self._break_stale = break_stale
        self._acquired = False

    def _read(self) -> dict[str, Any] | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _create(self) -> int:
        return os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"pid": os.getpid(), "started_at": _utcnow().isoformat()}).encode("utf-8")
        try:
            fd = self._create()
        except FileExistsError as exc:
            existing = self._read()
            pid = existing.get("pid") if existing else None
            if isinstance(pid, int) and _pid_alive(pid):
                raise ReportLockError(
                    f"another run owns {self.path} (pid {pid}) -- refusing to run two "
                    "writers against the same report"
                ) from exc
            if not self._break_stale:
                raise ReportLockError(
                    f"stale lock {self.path} (pid {pid!r} not running) -- pass "
                    "break_stale=True (--break-stale-lock) to remove it and proceed"
                ) from exc
            self.path.unlink(missing_ok=True)
            try:
                fd = self._create()
            except FileExistsError as exc:
                raise ReportLockError(
                    f"lock {self.path} was recreated by another process while breaking "
                    "the stale lock -- refusing"
                ) from exc
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        self._acquired = True

    def release(self) -> None:
        if self._acquired:
            self.path.unlink(missing_ok=True)
            self._acquired = False

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
