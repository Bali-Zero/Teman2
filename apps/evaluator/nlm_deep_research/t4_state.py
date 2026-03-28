"""T4 Monitor state — persistence, PID lock, budget tracking.

State is stored as JSON at:
    apps/evaluator/nlm_deep_research/t4_state.json

PID lock prevents concurrent cron runs:
    apps/evaluator/nlm_deep_research/t4.lock
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

_DEFAULT_STATE_PATH: Path = Path(__file__).resolve().parent / "t4_state.json"
_DEFAULT_LOCK_PATH: Path = Path(__file__).resolve().parent / "t4.lock"

MAX_T4_SLOTS: int = 11
NEWS_HALF_LIFE_DAYS: int = 15


@dataclass
class T4State:
    """Mutable runtime state for the T4 monitor."""

    seen_ids: set[str] = field(default_factory=set)
    active_t4_sources: list[str] = field(default_factory=list)
    last_run_at: Optional[datetime] = None
    cb_status: Literal["CLOSED", "OPEN", "HALF_OPEN"] = "CLOSED"
    cb_failure_count: int = 0
    cb_last_failure: Optional[datetime] = None
    x_enabled: bool = True
    x_enabled_until: Optional[datetime] = None
    run_lock_pid: Optional[int] = None

    def is_over_budget(self, max_slots: int = MAX_T4_SLOTS) -> bool:
        return len(self.active_t4_sources) >= max_slots

    def evict_oldest(self) -> str:
        """Remove and return the oldest (first) active T4 source ID."""
        if not self.active_t4_sources:
            raise IndexError("No active T4 sources to evict")
        return self.active_t4_sources.pop(0)

    def mark_seen(self, article_id: str) -> None:
        self.seen_ids.add(article_id)

    def is_seen(self, article_id: str) -> bool:
        return article_id in self.seen_ids

    def add_source(self, nlm_source_id: str) -> None:
        self.active_t4_sources.append(nlm_source_id)


class T4StatePersistence:
    """Load/save T4State to/from JSON."""

    def __init__(self, path: Path = _DEFAULT_STATE_PATH) -> None:
        self.path = path

    def load(self) -> T4State:
        if not self.path.exists():
            logger.info("t4_state.json not found — returning fresh state")
            return T4State()
        try:
            data = json.loads(self.path.read_text())
            return T4State(
                seen_ids=set(data.get("seen_ids", [])),
                active_t4_sources=data.get("active_t4_sources", []),
                last_run_at=(
                    datetime.fromisoformat(data["last_run_at"])
                    if data.get("last_run_at")
                    else None
                ),
                cb_status=data.get("cb_status", "CLOSED"),
                cb_failure_count=data.get("cb_failure_count", 0),
                cb_last_failure=(
                    datetime.fromisoformat(data["cb_last_failure"])
                    if data.get("cb_last_failure")
                    else None
                ),
                x_enabled=data.get("x_enabled", True),
                x_enabled_until=(
                    datetime.fromisoformat(data["x_enabled_until"])
                    if data.get("x_enabled_until")
                    else None
                ),
                run_lock_pid=data.get("run_lock_pid"),
            )
        except Exception:
            logger.exception("Failed to load t4_state.json — returning fresh state")
            return T4State()

    def save(self, state: T4State) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "seen_ids": sorted(state.seen_ids),
            "active_t4_sources": state.active_t4_sources,
            "last_run_at": state.last_run_at.isoformat() if state.last_run_at else None,
            "cb_status": state.cb_status,
            "cb_failure_count": state.cb_failure_count,
            "cb_last_failure": (
                state.cb_last_failure.isoformat() if state.cb_last_failure else None
            ),
            "x_enabled": state.x_enabled,
            "x_enabled_until": (
                state.x_enabled_until.isoformat() if state.x_enabled_until else None
            ),
            "run_lock_pid": state.run_lock_pid,
        }
        self.path.write_text(json.dumps(data, indent=2))
        logger.debug("t4_state.json saved (%d seen_ids)", len(state.seen_ids))


class T4LockError(Exception):
    """Raised when the PID lock cannot be acquired."""


class T4PIDLock:
    """File-based PID lock preventing concurrent T4 monitor runs."""

    def __init__(self, lock_path: Path = _DEFAULT_LOCK_PATH) -> None:
        self.lock_path = lock_path

    def acquire(self) -> None:
        if self.lock_path.exists():
            pid_str = self.lock_path.read_text().strip()
            try:
                pid = int(pid_str)
                os.kill(pid, 0)  # signal 0 = check if process exists
                raise T4LockError(
                    f"T4 monitor already running (PID {pid}). Exiting."
                )
            except (ProcessLookupError, PermissionError):
                logger.warning("Stale lock (PID %s dead) — cleaning up", pid_str)
                self.lock_path.unlink(missing_ok=True)
        self.lock_path.write_text(str(os.getpid()))

    def release(self) -> None:
        self.lock_path.unlink(missing_ok=True)

    def __enter__(self) -> "T4PIDLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
