"""DB→NLM Sync state — persistence, PID lock, circuit breaker.

State is stored as JSON at:
    apps/evaluator/nlm_deep_research/db_nlm_sync_state.json

PID lock prevents concurrent cron runs:
    apps/evaluator/nlm_deep_research/db_nlm_sync.lock
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

_DIR: Path = Path(__file__).resolve().parent
_DEFAULT_STATE_PATH: Path = _DIR / "db_nlm_sync_state.json"
_DEFAULT_LOCK_PATH: Path = _DIR / "db_nlm_sync.lock"

# --- Notebook IDs (populated after creation via `nlm notebook create`) ---
# These will be set on first run or via CLI args.
NB_OPS_ID: str = ""       # NB-11: Bali Zero Ops Live
NB_INTEL_ID: str = ""      # NB-12: Bali Zero Business Intelligence
NB_TELEMETRY_ID: str = ""  # NB-13: Bali Zero System Telemetry

# --- Source slots per notebook ---
MAX_SOURCES_PER_NB: int = 15


@dataclass
class SourceHash:
    """Tracks a single MD source document."""

    name: str
    sha256: str
    nlm_source_id: Optional[str] = None
    last_uploaded: Optional[str] = None  # ISO timestamp


@dataclass
class DBNLMSyncState:
    """Mutable runtime state for the DB→NLM sync pipeline."""

    # Notebook IDs (set on first run)
    nb_ops_id: str = ""
    nb_intel_id: str = ""
    nb_telemetry_id: str = ""

    # Per-source hashes: {source_name: SourceHash}
    source_hashes: dict[str, SourceHash] = field(default_factory=dict)

    # Run tracking
    last_run_at: Optional[datetime] = None
    last_run_status: str = "never"  # "success", "partial", "error", "never"
    runs_today: int = 0
    run_date: Optional[str] = None  # YYYY-MM-DD to reset runs_today

    # Circuit breaker (DB connection)
    cb_db_status: Literal["CLOSED", "OPEN", "HALF_OPEN"] = "CLOSED"
    cb_db_failure_count: int = 0
    cb_db_last_failure: Optional[datetime] = None

    # Circuit breaker (NLM upload)
    cb_nlm_status: Literal["CLOSED", "OPEN", "HALF_OPEN"] = "CLOSED"
    cb_nlm_failure_count: int = 0
    cb_nlm_last_failure: Optional[datetime] = None

    # Stats
    total_uploads: int = 0
    total_skipped: int = 0  # Skipped due to identical hash

    def is_source_changed(self, name: str, content: str) -> bool:
        """Check if source content has changed since last upload."""
        new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = self.source_hashes.get(name)
        if existing and existing.sha256 == new_hash:
            return False
        return True

    def record_upload(
        self, name: str, content: str, nlm_source_id: str,
    ) -> None:
        """Record a successful source upload."""
        self.source_hashes[name] = SourceHash(
            name=name,
            sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            nlm_source_id=nlm_source_id,
            last_uploaded=datetime.utcnow().isoformat(),
        )
        self.total_uploads += 1

    def record_skip(self) -> None:
        self.total_skipped += 1

    def record_db_failure(self) -> None:
        self.cb_db_failure_count += 1
        self.cb_db_last_failure = datetime.utcnow()
        if self.cb_db_failure_count >= 3:
            self.cb_db_status = "OPEN"

    def record_nlm_failure(self) -> None:
        self.cb_nlm_failure_count += 1
        self.cb_nlm_last_failure = datetime.utcnow()
        if self.cb_nlm_failure_count >= 3:
            self.cb_nlm_status = "OPEN"

    def reset_db_cb(self) -> None:
        self.cb_db_status = "CLOSED"
        self.cb_db_failure_count = 0

    def reset_nlm_cb(self) -> None:
        self.cb_nlm_status = "CLOSED"
        self.cb_nlm_failure_count = 0

    def increment_run(self) -> None:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if self.run_date != today:
            self.run_date = today
            self.runs_today = 0
        self.runs_today += 1
        self.last_run_at = datetime.utcnow()


class DBNLMStatePersistence:
    """Load/save DBNLMSyncState to/from JSON."""

    def __init__(self, path: Path = _DEFAULT_STATE_PATH) -> None:
        self.path = path

    def load(self) -> DBNLMSyncState:
        if not self.path.exists():
            logger.info("db_nlm_sync_state.json not found — returning fresh state")
            return DBNLMSyncState()
        try:
            data = json.loads(self.path.read_text())
            state = DBNLMSyncState(
                nb_ops_id=data.get("nb_ops_id", ""),
                nb_intel_id=data.get("nb_intel_id", ""),
                nb_telemetry_id=data.get("nb_telemetry_id", ""),
                last_run_at=(
                    datetime.fromisoformat(data["last_run_at"])
                    if data.get("last_run_at")
                    else None
                ),
                last_run_status=data.get("last_run_status", "never"),
                runs_today=data.get("runs_today", 0),
                run_date=data.get("run_date"),
                cb_db_status=data.get("cb_db_status", "CLOSED"),
                cb_db_failure_count=data.get("cb_db_failure_count", 0),
                cb_db_last_failure=(
                    datetime.fromisoformat(data["cb_db_last_failure"])
                    if data.get("cb_db_last_failure")
                    else None
                ),
                cb_nlm_status=data.get("cb_nlm_status", "CLOSED"),
                cb_nlm_failure_count=data.get("cb_nlm_failure_count", 0),
                cb_nlm_last_failure=(
                    datetime.fromisoformat(data["cb_nlm_last_failure"])
                    if data.get("cb_nlm_last_failure")
                    else None
                ),
                total_uploads=data.get("total_uploads", 0),
                total_skipped=data.get("total_skipped", 0),
            )
            # Rebuild source_hashes
            for name, sh in data.get("source_hashes", {}).items():
                state.source_hashes[name] = SourceHash(
                    name=sh.get("name", name),
                    sha256=sh.get("sha256", ""),
                    nlm_source_id=sh.get("nlm_source_id"),
                    last_uploaded=sh.get("last_uploaded"),
                )
            return state
        except Exception:
            logger.exception("Failed to load db_nlm_sync_state.json — fresh state")
            return DBNLMSyncState()

    def save(self, state: DBNLMSyncState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nb_ops_id": state.nb_ops_id,
            "nb_intel_id": state.nb_intel_id,
            "nb_telemetry_id": state.nb_telemetry_id,
            "source_hashes": {
                name: {
                    "name": sh.name,
                    "sha256": sh.sha256,
                    "nlm_source_id": sh.nlm_source_id,
                    "last_uploaded": sh.last_uploaded,
                }
                for name, sh in state.source_hashes.items()
            },
            "last_run_at": (
                state.last_run_at.isoformat() if state.last_run_at else None
            ),
            "last_run_status": state.last_run_status,
            "runs_today": state.runs_today,
            "run_date": state.run_date,
            "cb_db_status": state.cb_db_status,
            "cb_db_failure_count": state.cb_db_failure_count,
            "cb_db_last_failure": (
                state.cb_db_last_failure.isoformat()
                if state.cb_db_last_failure
                else None
            ),
            "cb_nlm_status": state.cb_nlm_status,
            "cb_nlm_failure_count": state.cb_nlm_failure_count,
            "cb_nlm_last_failure": (
                state.cb_nlm_last_failure.isoformat()
                if state.cb_nlm_last_failure
                else None
            ),
            "total_uploads": state.total_uploads,
            "total_skipped": state.total_skipped,
        }
        self.path.write_text(json.dumps(data, indent=2))
        logger.debug("db_nlm_sync_state.json saved")


class DBNLMLockError(Exception):
    """Raised when the PID lock cannot be acquired."""


class DBNLMPIDLock:
    """File-based PID lock preventing concurrent sync runs."""

    def __init__(self, lock_path: Path = _DEFAULT_LOCK_PATH) -> None:
        self.lock_path = lock_path

    def acquire(self) -> None:
        if self.lock_path.exists():
            pid_str = self.lock_path.read_text().strip()
            try:
                pid = int(pid_str)
                os.kill(pid, 0)
                raise DBNLMLockError(
                    f"DB→NLM sync already running (PID {pid}). Exiting."
                )
            except (ProcessLookupError, PermissionError):
                logger.warning("Stale lock (PID %s dead) — cleaning up", pid_str)
                self.lock_path.unlink(missing_ok=True)
        self.lock_path.write_text(str(os.getpid()))

    def release(self) -> None:
        self.lock_path.unlink(missing_ok=True)

    def __enter__(self) -> "DBNLMPIDLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
