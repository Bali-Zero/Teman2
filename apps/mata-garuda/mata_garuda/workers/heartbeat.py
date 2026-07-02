"""Mata Garuda — minimal organism heartbeat emitter (Stage 1, 2026-06-29).

Writes the same `~/.organism/last_seen/<organ_id>.json` sidecar the receptor
(scripts/organism_stale_detector.py, PR #1805/#1808) reads, so a green-but-dead
mata_garuda singleton (e.g. gap_consumer running exit-0 while acking ~5% of its
backlog) surfaces as `unhealthy` instead of being invisible.

We deliberately do NOT import apps/cell's emit_organ_last_seen: mata_garuda's
CLAUDE.md §1 forbids importing from other monorepo apps (stack-isolated,
pydantic-only). This is a ~20-line copy of the SAME schema (W1.1 convention),
not a new format — schema parity is load-bearing (superscar #9: two divergent
sidecar formats already exist; do not add a third).

Schema:
    {"ts": <float epoch>, "status": "ok"|"degraded"|"fail",
     "organ_id": "<full.id>", "metadata": {...}}

Best-effort: never raises back to the producer (the cron's real work must not
depend on the sidecar landing). A missing/stale file already reads as dead.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Mapping

logger = logging.getLogger("mata_garuda.workers.heartbeat")

# Override via env for tests / non-standard homes; default matches the receptor.
_DEFAULT_DIR = os.path.expanduser("~/.organism/last_seen")


def emit_heartbeat(
    organ_id: str,
    status: str,
    metadata: Mapping[str, Any] | None = None,
    *,
    out_dir: str | None = None,
) -> bool:
    """Write the sidecar JSON for `organ_id`. Returns True on success.

    Never raises: any I/O / serialization failure is logged at WARNING and
    swallowed (the receptor treats absent sidecar as dead anyway).
    """
    target_dir = out_dir or os.environ.get("ORGANISM_LAST_SEEN_DIR") or _DEFAULT_DIR
    try:
        os.makedirs(target_dir, exist_ok=True)
        payload: dict[str, Any] = {
            "ts": time.time(),
            "status": str(status),
            "organ_id": str(organ_id),
            "metadata": dict(metadata) if metadata else {},
        }
        tmp = os.path.join(target_dir, f".{organ_id}.json.tmp")
        final = os.path.join(target_dir, f"{organ_id}.json")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload))
        os.replace(tmp, final)  # atomic — never a half-written sidecar
        return True
    except Exception as exc:  # noqa: BLE001 — emitter must stay robust
        logger.warning("mata_garuda heartbeat emit failed for %s: %s", organ_id, exc)
        return False



# ── cron-gate helpers (env-driven; absent env → no-op, full back-compat) ──────
# These absorb the two behaviors the 7 class-C ~/scripts shell wrappers carried
# (W7 flock single-instance + gap_consumer 06-22 operating window), so those
# crons can drop the wrapper and run the venv python directly (W84 TCC-safe +
# repo-tracked, cicatrix #1). fcntl is stdlib — respects mata_garuda's
# pydantic-only stack rule.
_FLOCK_TAKEN_EXIT = 75  # matches the shell wrapper's --conflict-exit-code 75


def _window_closed(spec: str) -> bool:
    """spec is 'A-B' (local hours, [A, B)). Return True if NOW is outside it.
    A malformed spec never gates (returns False) — fail-open, like no window."""
    try:
        a_str, _, b_str = spec.partition("-")
        a, b = int(a_str), int(b_str)
    except (ValueError, AttributeError):
        return False
    hour = datetime.now().hour
    return hour < a or hour >= b


def _acquire_flock(name: str):
    """Take a non-blocking exclusive lock on /tmp/matagaruda-<name>.lock.
    Returns the open file handle (keep it alive to hold the lock) or None if the
    lock is already held by another run. fcntl is POSIX — macOS/Linux only."""
    import fcntl  # local import: only crons that set MG_FLOCK pay for it
    path = f"/tmp/matagaruda-{name}.lock"
    fh = open(path, "w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        return None


def run_with_heartbeat(
    organ_id: str,
    fn: "Callable[[], int | None]",
    *,
    metadata: Mapping[str, Any] | None = None,
    out_dir: str | None = None,
) -> int:
    """Run a `main()`-style worker and ALWAYS emit a heartbeat at the end.

    Stage 2 (2026-06-30): the repo-direct mata_garuda crons expose `main() -> int`
    (an exit code), not a stats dict. This wrapper makes the green-but-dead case
    visible uniformly: `ok` on exit 0 / None, `fail` on non-zero exit or on an
    exception (then re-raised so launchd still records the failure). The sidecar
    is written in a `finally`, so even a crashing worker leaves a `fail` trail —
    the opposite of exit-code-only monitoring, which goes silent on hard crash.

    Returns the worker's exit code (None → 0). Re-raises any exception from `fn`.
    """
    # ── operating-window gate (MG_WINDOW=A-B local hours) ────────────────────
    _window = os.environ.get("MG_WINDOW", "").strip()
    if _window and _window_closed(_window):
        emit_heartbeat(organ_id, "ok",
                       metadata={"skipped": "outside_window", "window": _window},
                       out_dir=out_dir)
        logger.info("%s outside operating window %s — skipping", organ_id, _window)
        return 0

    # ── single-instance gate (MG_FLOCK=<name>) — W7 anti cron-stacking ───────
    _flock_name = os.environ.get("MG_FLOCK", "").strip()
    _flock_fh = None
    if _flock_name:
        _flock_fh = _acquire_flock(_flock_name)
        if _flock_fh is None:
            emit_heartbeat(organ_id, "ok",
                           metadata={"skipped": "flock_held", "flock": _flock_name},
                           out_dir=out_dir)
            logger.info("%s another instance holds flock %s — skipping",
                        organ_id, _flock_name)
            return _FLOCK_TAKEN_EXIT

    status = "ok"
    meta: dict[str, Any] = dict(metadata) if metadata else {}
    rc = 0
    try:
        result = fn()
        rc = int(result) if result is not None else 0
        meta["exit_code"] = rc
        status = "ok" if rc == 0 else "fail"
        return rc
    except BaseException as exc:  # noqa: BLE001 — emit then re-raise, never swallow
        status = "fail"
        meta["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        emit_heartbeat(organ_id, status, metadata=meta, out_dir=out_dir)


def status_from_stats(stats: Mapping[str, int]) -> str:
    """Derive a heartbeat status from a worker's run stats.

    Convention: a run that read items but ack'd ~none is the green-but-dead
    signature (gap_consumer 95%-unacked). `errors` dominate → fail.
    """
    read = int(stats.get("read", 0))
    errors = int(stats.get("errors", 0))
    if errors and errors >= max(1, read):
        return "fail"
    resolved = int(stats.get("resolved", 0))
    skipped = int(stats.get("skipped", 0))
    progressed = resolved + skipped + int(stats.get("failed", 0))
    if read > 0 and progressed == 0:
        # read a backlog but moved nothing forward → degraded (the dead-but-green case)
        return "degraded"
    return "ok"
