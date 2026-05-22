"""W37 (2026-05-23): durable Postgres incident ledger.

Writes/updates rows in the `incident_ledger` table (migration 194). The
Supervisor's dispatch path INSERTs a row when an action is dispatched; the
actuator's `_emit_actuation_event` UPDATEs the same row when the actuator
emits done/failed.

Design constraints:

- BEST-EFFORT semantics. The Supervisor + Actuators MUST NOT crash if
  Postgres is unreachable. Every public function in this module swallows
  exceptions and returns silently. The append-only
  ~/logs/organism/decisions.jsonl + actuator WAL files remain the
  authoritative trail when the ledger is unavailable.
- Optional asyncpg dependency. The organism package does NOT require
  asyncpg as a hard dependency (most tests use fakeredis only). The module
  imports asyncpg lazily and degrades to a no-op if the import fails OR if
  the LEDGER_DATABASE_URL env var is unset.
- Module-scoped lazy pool. We do NOT eagerly open a pool at import time;
  the pool is created on first use and reused across calls. Tests can
  inject a fake pool via `set_pool_for_tests()`.

Resolution heuristic for app/machine_id from actuator params: most W27/W31
actuators accept `app` and `machine`/`machine_id` keys directly. For
non-fly actuators we default to `app="organism"` and leave machine_id
NULL.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Mapping, Optional

log = logging.getLogger(__name__)

# Lazy globals — initialised on first call.
_POOL: Optional[Any] = None
_POOL_INIT_TRIED: bool = False
_DSN_ENV = "LEDGER_DATABASE_URL"
_DSN_ENV_FALLBACK = "DATABASE_URL"


def _resolve_dsn() -> Optional[str]:
    dsn = os.environ.get(_DSN_ENV) or os.environ.get(_DSN_ENV_FALLBACK)
    if dsn and dsn.strip():
        return dsn.strip()
    return None


async def _get_pool() -> Optional[Any]:
    """Return a cached asyncpg pool or None if unavailable.

    Single-attempt initialisation: once we fail (no DSN, asyncpg missing,
    connect failure), we stop trying to avoid log spam on every dispatch.
    Operators must restart the supervisor after fixing the underlying
    issue.
    """
    global _POOL, _POOL_INIT_TRIED
    if _POOL is not None:
        return _POOL
    if _POOL_INIT_TRIED:
        return None
    _POOL_INIT_TRIED = True

    dsn = _resolve_dsn()
    if not dsn:
        log.info(
            "incident_ledger: no LEDGER_DATABASE_URL/DATABASE_URL — ledger disabled",
        )
        return None
    try:
        import asyncpg  # type: ignore
    except Exception as exc:  # pragma: no cover — environment-dependent
        log.warning(
            "incident_ledger: asyncpg import failed (%s) — ledger disabled", exc,
        )
        return None
    try:
        _POOL = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
        log.info("incident_ledger: pool created")
        return _POOL
    except Exception as exc:
        log.warning(
            "incident_ledger: pool create failed (%s) — ledger disabled", exc,
        )
        return None


def set_pool_for_tests(pool: Optional[Any]) -> None:
    """Inject a fake pool (or None) — tests only.

    Resets the init-attempted flag so a subsequent _get_pool() call returns
    the injected value without re-running the env+import probe.
    """
    global _POOL, _POOL_INIT_TRIED
    _POOL = pool
    _POOL_INIT_TRIED = pool is None  # if pool=None, we want lazy retry suppressed


async def reset_for_tests() -> None:
    """Close the pool (if real) and clear cached state. Tests only."""
    global _POOL, _POOL_INIT_TRIED
    if _POOL is not None:
        try:
            close = getattr(_POOL, "close", None)
            if close is not None:
                res = close()
                if hasattr(res, "__await__"):
                    await res
        except Exception:
            pass
    _POOL = None
    _POOL_INIT_TRIED = False


def _resolve_app_machine(
    actuator: str,
    params: Mapping[str, Any],
) -> tuple[str, Optional[str]]:
    """Extract (app, machine_id) from actuator params.

    Best-effort: fly_machines_* actuators expose `app` + `machine`/`machine_id`.
    Other actuators fall back to ("organism", None).
    """
    app = params.get("app")
    if not isinstance(app, str) or not app:
        app = "organism"
    machine = params.get("machine") or params.get("machine_id")
    if not isinstance(machine, str) or not machine:
        machine = None
    return app, machine


def _resolve_cell_id(
    params: Mapping[str, Any],
    event_payload: Optional[Mapping[str, Any]] = None,
) -> str:
    """Extract cell_id from params or originating event payload."""
    cell_id = params.get("cell_id")
    if isinstance(cell_id, str) and cell_id:
        return cell_id
    if event_payload:
        cell_id = event_payload.get("cell_id")
        if isinstance(cell_id, str) and cell_id:
            return cell_id
    return "unknown"


def _resolve_consecutive_red(
    params: Mapping[str, Any],
    event_payload: Optional[Mapping[str, Any]] = None,
) -> Optional[int]:
    """Pull streak count from params/event_payload if present."""
    for src in (params, event_payload or {}):
        val = src.get("consecutive_red")
        if isinstance(val, int):
            return val
        if isinstance(val, str):
            try:
                return int(val)
            except ValueError:
                continue
    return None


async def record_dispatch(
    *,
    correlation_id: str,
    actuator: str,
    outcome: str,
    params: Mapping[str, Any],
    event_payload: Optional[Mapping[str, Any]] = None,
) -> None:
    """INSERT a row when an action is dispatched (or deferred/rejected).

    Best-effort: swallows all exceptions.
    """
    pool = await _get_pool()
    if pool is None:
        return
    try:
        app, machine_id = _resolve_app_machine(actuator, params)
        cell_id = _resolve_cell_id(params, event_payload)
        consecutive_red = _resolve_consecutive_red(params, event_payload)
        await pool.execute(
            """
            INSERT INTO incident_ledger
                (correlation_id, cell_id, app, machine_id,
                 actuator, outcome, consecutive_red)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            correlation_id, cell_id, app, machine_id,
            actuator, outcome, consecutive_red,
        )
    except Exception:
        log.exception(
            "incident_ledger.record_dispatch failed (non-fatal) corr=%s",
            correlation_id,
        )


async def record_outcome(
    *,
    correlation_id: str,
    actuator: str,
    outcome: str,
    error: Optional[str] = None,
) -> None:
    """UPDATE the matching row when the actuator emits done/failed.

    Matches the most-recent row with the given (correlation_id, actuator)
    pair whose completed_at is still NULL. If none exists (e.g. dispatch
    INSERT failed earlier), the UPDATE silently no-ops. Best-effort.
    """
    pool = await _get_pool()
    if pool is None:
        return
    if outcome not in {"done", "failed"}:
        log.warning(
            "incident_ledger.record_outcome: unexpected outcome=%s — coercing to 'failed'",
            outcome,
        )
        outcome = "failed"
    try:
        await pool.execute(
            """
            UPDATE incident_ledger
               SET outcome = $1,
                   completed_at = now(),
                   error = $2
             WHERE id = (
                 SELECT id FROM incident_ledger
                  WHERE correlation_id = $3
                    AND actuator = $4
                    AND completed_at IS NULL
                  ORDER BY started_at DESC
                  LIMIT 1
             )
            """,
            outcome, error, correlation_id, actuator,
        )
    except Exception:
        log.exception(
            "incident_ledger.record_outcome failed (non-fatal) corr=%s",
            correlation_id,
        )
