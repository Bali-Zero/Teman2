"""EventBus handlers for crm-cell HGT pattern broadcasting.

Phase 3 TICKET A.2 — first production caller of ``CrmHGTBridge`` from
``crm_cell.hgt_publisher`` (PR #632, commit ``84953041b``).

Architecture (post 4-panel UNANIMOUS Option β, see
``docs/audits/2026-05-13-ticket-a2-spec-brainstorm/``):

- Handlers subscribe to existing PG_CHANNEL_MAP dotted event types
- Per-event aggregation via Redis sorted-set sliding window
  (ZADD + ZREMRANGEBYSCORE + ZCARD + EXPIRE in 1 pipeline round-trip)
- Pattern published via ``CrmHGTBridge.publish()`` only when threshold met
- Bridge instantiated once per process via module-level lazy singleton

UU PDP discipline (inherited from A.1):
- Pattern strings never contain client_id, email, NPWP, phone
- Bridge has defense-in-depth PII scan on procedure/precondition/
  success_criterion

Refusals respected (Phase 3 spec v2 §14):
- No polling/cron daemon (Option δ rejected per SYMBIOSIS.md:180 Law 3)
- No edits to ``packages/cell-core/cell_core/hgt/*`` (TICKET A.0 only)
- No edits to ``apps/evaluator/seo_cell/`` (refusal #13)
- No synchronous ``asyncio.run`` in HGT handler code (refusal #14)
- No new PG_CHANNEL_MAP entries v1 (Brevo deferred to A.2-followup)

Reference:
- Spec v2: ``research/symbiosis/2026-05-12-ticket-a2-narrow-spec.md``
- Canonical pattern: ``services/events/handlers/compliance_handlers.py``
- Parent Phase 3 spec v2: ``docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md``
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Module-level lazy singleton — instantiated on first handler call
_bridge: Any = None  # CrmHGTBridge | None | False (sentinel = init failed)


# ---------------------------------------------------------------------------
# Bridge initialization (lazy)
# ---------------------------------------------------------------------------


async def _get_bridge() -> Any:
    """Lazy CrmHGTBridge factory — runs once per process.

    Returns ``CrmHGTBridge`` instance on success, ``None`` on init failure
    (sentinel prevents retry). Logs warning on failure; handler degrades
    gracefully by returning early.
    """
    global _bridge
    if _bridge is None:
        try:
            import redis.asyncio as redis_async
            from crm_cell.hgt_publisher import CrmHGTBridge

            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            client = redis_async.from_url(redis_url, decode_responses=False)
            _bridge = CrmHGTBridge.from_redis(
                redis_client=client, cell_name="crm-cell"
            )
            logger.info(
                "crm_hgt_handlers: bridge initialized url=%s", redis_url
            )
        except Exception as exc:  # noqa: BLE001 — defense in depth
            logger.warning(
                "crm_hgt_handlers: bridge init failed: %r — patterns disabled this process",
                exc,
            )
            _bridge = False  # sentinel — no retry this process
    return _bridge if _bridge else None


# ---------------------------------------------------------------------------
# Redis sliding window helper
# ---------------------------------------------------------------------------


async def _ingest_event(
    redis_client: Any,
    window_key: str,
    event_id: str,
    ts_epoch: float,
    retention_seconds: int,
) -> int:
    """Add event to sliding window + prune expired. Returns current count.

    Single Redis pipeline round-trip:
    - ZADD member=event_id score=ts_epoch
    - ZREMRANGEBYSCORE -inf to (now - retention) (prune expired)
    - ZCARD (returns current window count)
    - EXPIRE (safety TTL to prevent zombie keys)

    Returns 0 on any Redis error (handler treats as "below threshold" —
    pattern won't publish on this event).
    """
    try:
        cutoff = ts_epoch - retention_seconds
        async with redis_client.pipeline(transaction=False) as pipe:
            pipe.zadd(window_key, {event_id: ts_epoch})
            pipe.zremrangebyscore(window_key, "-inf", cutoff)
            pipe.zcard(window_key)
            pipe.expire(window_key, retention_seconds + 60)
            results = await pipe.execute()
        return int(results[2])
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "crm_hgt_handlers: window state failed key=%s err=%r",
            window_key,
            exc,
        )
        return 0


# ---------------------------------------------------------------------------
# Pattern 1: practice.stage_cycle_time (window=7d, threshold=20)
# ---------------------------------------------------------------------------

_PRACTICE_WINDOW_SECONDS = 7 * 24 * 3600
_PRACTICE_THRESHOLD_N = 20
_PRACTICE_WINDOW_KEY = "crm.window.practice_stage_cycle_time"


async def on_practice_status_changed(payload: dict[str, Any]) -> None:
    """Aggregate practice stage transitions; emit cycle-time pattern.

    Subscribes to PG channel ``practice_changed`` (migration 075) →
    event type ``practice.status_changed``. Coexists with the existing
    ``services/crm/practice_status_listener.py`` (which handles M4+M5
    email automation) — both subscribe via EventBus.subscribe so
    multiple handlers per event type work in parallel without blocking
    each other.

    Pattern semantics: "practice transitions through stage X→Y at
    cadence N events/7d for visa category Z". Concrete pattern_id
    derived from new_status (e.g. ``practice_transition_on_process``).
    """
    bridge = await _get_bridge()
    if bridge is None:
        return

    practice_id = payload.get("practice_id")
    new_status = payload.get("new_status")
    if not (practice_id and new_status):
        return

    event_id = str(payload.get("event_id") or uuid.uuid4())
    ts_epoch = time.time()

    count = await _ingest_event(
        bridge._publisher._redis,  # noqa: SLF001 — bridge wraps publisher
        f"{_PRACTICE_WINDOW_KEY}:{new_status}",
        event_id,
        ts_epoch,
        _PRACTICE_WINDOW_SECONDS,
    )

    if count < _PRACTICE_THRESHOLD_N:
        logger.debug(
            "crm_hgt: practice window status=%s count=%d below threshold %d",
            new_status,
            count,
            _PRACTICE_THRESHOLD_N,
        )
        return

    # Threshold crossed → publish structural pattern
    try:
        from crm_cell.hgt_publisher import StructuralPattern
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "crm_hgt: StructuralPattern import failed: %r", exc
        )
        return

    pattern = StructuralPattern(
        pattern_id=f"practice_transition_{new_status}",
        procedure=(
            f"Practice transitions to status {new_status} sustained at "
            f"{count} events in 7d rolling window"
        ),
        precondition=(
            "active practice pipeline with ongoing status transitions"
        ),
        success_criterion=(
            f"practice_transition_{new_status} replicates above "
            f"{_PRACTICE_THRESHOLD_N} events in next 7d window"
        ),
        confidence=0.8,
        domain="crm",
    )
    await bridge.publish(pattern)


# ---------------------------------------------------------------------------
# Pattern 2: lkpm.ingestion_success_rate (window=90d, threshold=10)
# ---------------------------------------------------------------------------

_LKPM_WINDOW_SECONDS = 90 * 24 * 3600
_LKPM_THRESHOLD_N = 10
_LKPM_WINDOW_KEY = "crm.window.lkpm_ingestion_success_rate"


async def on_lkpm_ingest_completed(payload: dict[str, Any]) -> None:
    """Aggregate LKPM ingestion outcomes; emit success-rate pattern.

    Subscribes to PG channel ``lkpm_ingest_completed`` → event type
    ``lkpm.ingest_completed``. Coexists with
    ``compliance_handlers.on_lkpm_readypack_generated`` (logging-only) —
    both subscribe via EventBus.subscribe so multiple handlers per event
    type run in parallel.

    Pattern semantics: "LKPM bulk ingest sustains N successful
    completions per 90d window for active PT segment".
    """
    bridge = await _get_bridge()
    if bridge is None:
        return

    pt_count = payload.get("pt_count")
    receipt_count = payload.get("receipt_count")
    if pt_count is None and receipt_count is None:
        # No structural signal — skip
        return

    event_id = str(payload.get("event_id") or uuid.uuid4())
    ts_epoch = time.time()

    count = await _ingest_event(
        bridge._publisher._redis,  # noqa: SLF001
        _LKPM_WINDOW_KEY,
        event_id,
        ts_epoch,
        _LKPM_WINDOW_SECONDS,
    )

    if count < _LKPM_THRESHOLD_N:
        logger.debug(
            "crm_hgt: lkpm window count=%d below threshold %d",
            count,
            _LKPM_THRESHOLD_N,
        )
        return

    try:
        from crm_cell.hgt_publisher import StructuralPattern
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "crm_hgt: StructuralPattern import failed: %r", exc
        )
        return

    pattern = StructuralPattern(
        pattern_id="lkpm_ingestion_success_rate",
        procedure=(
            f"LKPM bulk ingest sustains {count} successful completions "
            f"in 90d rolling window"
        ),
        precondition="active PT segment with periodic LKPM submissions",
        success_criterion=(
            f"lkpm_ingestion_success_rate replicates above "
            f"{_LKPM_THRESHOLD_N} events in next 90d window"
        ),
        confidence=0.8,
        domain="crm",
    )
    await bridge.publish(pattern)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


HANDLERS: dict[str, Any] = {
    "practice.status_changed": on_practice_status_changed,
    "lkpm.ingest_completed": on_lkpm_ingest_completed,
}


def register_crm_hgt_handlers(bus: Any) -> None:
    """Subscribe all crm-cell HGT handlers to EventBus.

    Call from ``app_factory._background_init`` AFTER ``register_handlers``
    so the compliance handlers register first. Multiple subscribers per
    event type are supported by EventBus.subscribe.

    Pattern mirrors ``services/crm/partners/events.register_partner_handlers``.
    """
    for event_type, handler in HANDLERS.items():
        bus.subscribe(event_type, handler)
    logger.info(
        "crm_hgt_handlers registered (%d handlers): %s",
        len(HANDLERS),
        ", ".join(HANDLERS.keys()),
    )


__all__ = [
    "HANDLERS",
    "on_practice_status_changed",
    "on_lkpm_ingest_completed",
    "register_crm_hgt_handlers",
]
