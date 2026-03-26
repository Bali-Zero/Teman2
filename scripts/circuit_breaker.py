"""Per-job circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED."""
import fcntl
import json
import os
import tempfile
import time
from typing import Literal

STATE_FILE = os.path.expanduser("~/.agent/decisions/circuit_breakers.json")
OPEN_TIMEOUT_S = 1800  # 30 min before HALF_OPEN test
CircuitState = Literal["CLOSED", "OPEN", "HALF_OPEN"]


def _load() -> dict:
    try:
        return json.loads(open(STATE_FILE).read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _atomic_save(data: dict) -> None:
    """Atomic file write via fcntl + tempfile + os.replace.
    Prevents torn writes when two processes write concurrently.
    Does NOT protect against concurrent read-modify-write races in callers.
    """
    dir_ = os.path.dirname(STATE_FILE)
    os.makedirs(dir_, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            fd = -1  # fd is now owned by the context manager
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(data, f, indent=2)
        os.replace(tmp, STATE_FILE)
    except Exception:
        if fd != -1:
            os.close(fd)  # close raw fd if fdopen never took ownership
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_state(job: str) -> CircuitState:
    data = _load()
    job_data = data.get(job, {})
    state = job_data.get("state", "CLOSED")
    opened_at = job_data.get("opened_at", 0)

    if state == "OPEN" and (time.time() - opened_at) > OPEN_TIMEOUT_S:
        # Transition to HALF_OPEN for a test
        _set_state(job, "HALF_OPEN")
        return "HALF_OPEN"
    return state


def record_success(job: str) -> None:
    """Call after a successful run — resets to CLOSED."""
    data = _load()
    data[job] = {"state": "CLOSED", "failures": 0, "opened_at": 0}
    _atomic_save(data)


def record_failure(job: str) -> CircuitState:
    """Call after a failed run — may trip to OPEN. Returns new state."""
    data = _load()
    job_data = data.get(job, {"state": "CLOSED", "failures": 0, "opened_at": 0})
    job_data["failures"] = job_data.get("failures", 0) + 1

    if job_data["failures"] >= 3 or job_data.get("state") == "HALF_OPEN":
        job_data["state"] = "OPEN"
        job_data["opened_at"] = time.time()
    data[job] = job_data
    _atomic_save(data)
    return job_data["state"]


def _set_state(job: str, state: CircuitState) -> None:
    data = _load()
    job_data = data.get(job, {})
    job_data["state"] = state
    if state == "HALF_OPEN":
        job_data["opened_at"] = time.time()
    data[job] = job_data
    _atomic_save(data)
