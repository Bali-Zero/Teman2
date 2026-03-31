"""Per-job circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED."""
import contextlib
import fcntl
import json
import os
import tempfile
import time
from typing import Literal

STATE_FILE = os.path.expanduser("~/.agent/decisions/circuit_breakers.json")
LOCK_FILE = os.path.expanduser("~/.agent/decisions/circuit_breakers.lock")
OPEN_TIMEOUT_S = 1800  # 30 min before HALF_OPEN test
CircuitState = Literal["CLOSED", "OPEN", "HALF_OPEN"]

# D4.1: Phase transition matrix — forward-only except T0 (success reset)
_PHASE_FORWARD: dict[str, str] = {
    "T0": "T1",
    "T1": "T2",
    "T2": "T3",
    "T3": "T4",
    "T4": "TERMINAL",
}
VALID_PHASES = frozenset(_PHASE_FORWARD) | {"TERMINAL"}


@contextlib.contextmanager
def _locked():
    """D0.3: Hold an exclusive flock across the full read-modify-write cycle.
    Prevents TOCTOU: previously _load() released before _atomic_save() acquired.
    """
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    lf = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN)
        lf.close()


def _load() -> dict:
    """Read state file without acquiring lock. Use inside _locked() context."""
    try:
        return json.loads(open(STATE_FILE).read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _atomic_save(data: dict) -> None:
    """Write state file atomically via tempfile + os.replace.
    Must be called while holding _locked() — the lock guards the read-modify-write,
    this function only guarantees the write itself is not torn.
    """
    dir_ = os.path.dirname(STATE_FILE)
    os.makedirs(dir_, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            fd = -1  # fd is now owned by the context manager
            json.dump(data, f, indent=2)
        os.replace(tmp, STATE_FILE)
    except Exception:
        if fd != -1:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_state(job: str) -> CircuitState:
    with _locked():
        data = _load()
        job_data = data.get(job, {})
        state = job_data.get("state", "CLOSED")
        opened_at = job_data.get("opened_at", 0)

        if state == "OPEN" and (time.time() - opened_at) > OPEN_TIMEOUT_S:
            job_data["state"] = "HALF_OPEN"
            job_data["opened_at"] = time.time()
            data[job] = job_data
            _atomic_save(data)
            return "HALF_OPEN"
        return state


def record_success(job: str) -> None:
    """Call after a successful run — resets to CLOSED. D4.1/NP-3: explicit phase reset to T0."""
    with _locked():
        data = _load()
        # Preserve _failure_timestamps (pruned) for audit; reset operational fields
        existing = data.get(job, {})
        timestamps = [t for t in existing.get("_failure_timestamps", [])
                      if time.time() - t <= 14 * 86400]
        data[job] = {
            "state": "CLOSED",
            "failures": 0,
            "opened_at": 0,
            "phase": "T0",  # D4.1: only authorized path to set T0 via set_phase()
            "phase_updated_at": time.time(),
            "_failure_timestamps": timestamps,
            "_writer": "circuit_breaker",
        }
        _atomic_save(data)


def record_failure(job: str) -> CircuitState:
    """Call after a failed run — may trip to OPEN. Returns new state."""
    with _locked():
        data = _load()
        job_data = data.get(job, {"state": "CLOSED", "failures": 0, "opened_at": 0})
        job_data["failures"] = job_data.get("failures", 0) + 1

        # D1.6: Inline _failure_timestamps pruning — keep only last 14 days
        now = time.time()
        timestamps = job_data.get("_failure_timestamps", [])
        timestamps.append(now)
        job_data["_failure_timestamps"] = [t for t in timestamps if now - t <= 14 * 86400]

        if job_data["failures"] >= 3 or job_data.get("state") == "HALF_OPEN":
            job_data["state"] = "OPEN"
            job_data["opened_at"] = now
        data[job] = job_data
        _atomic_save(data)
        return job_data["state"]


def _set_state(job: str, state: CircuitState) -> None:
    with _locked():
        data = _load()
        job_data = data.get(job, {})
        job_data["state"] = state
        if state == "HALF_OPEN":
            job_data["opened_at"] = time.time()
        data[job] = job_data
        _atomic_save(data)


def set_phase(job: str, new_phase: str) -> None:
    """D4.1: Enforce phase transition matrix. Must hold _locked() context externally.

    Valid forward path: T0 → T1 → T2 → T3 → T4 → TERMINAL
    Authorized retrograde: ANY → T0 (called only from record_success())
    Calling from outside record_success() to set T0 is allowed (e.g., manual reset),
    but any skip forward (T0→T2) or backward (T3→T1) is rejected with ValueError.

    Raises ValueError for invalid transitions so callers see a hard error (not silent skip).
    """
    if new_phase not in VALID_PHASES:
        raise ValueError(f"Unknown phase '{new_phase}'. Valid: {sorted(VALID_PHASES)}")

    with _locked():
        data = _load()
        current = data.get(job, {}).get("phase", "T0")

        # T0 is the success-reset target — always allowed (no backward constraint)
        if new_phase == "T0":
            pass
        # Forward must be exactly one step
        elif _PHASE_FORWARD.get(current) != new_phase:
            raise ValueError(
                f"Invalid phase transition for '{job}': {current} → {new_phase}. "
                f"Expected next: {_PHASE_FORWARD.get(current, 'N/A (TERMINAL is final)')}"
            )

        job_data = data.get(job, {})
        job_data["phase"] = new_phase
        job_data["phase_updated_at"] = time.time()
        data[job] = job_data
        _atomic_save(data)
