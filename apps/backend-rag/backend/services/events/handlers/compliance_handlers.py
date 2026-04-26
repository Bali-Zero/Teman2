"""EventBus handlers for compliance + intel events.

These handlers subscribe to EventBus event types, not raw PG channel names.
The raw channel mapping lives in ``backend.services.events.event_bus``.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def on_compliance_alert_created(payload: dict[str, Any]) -> None:
    """Invalidate cache namespaces when a new alert is generated."""
    client_id = payload.get("client_id")
    if client_id is None:
        return
    try:
        from backend.core.cache import invalidate_cache
        await invalidate_cache(f"zantara:compliance_alerts:{client_id}:*")
        await invalidate_cache("zantara:compliance_metrics:*")
    except Exception as exc:
        logger.debug("compliance cache invalidation skipped: %s", exc)


async def on_compliance_alert_outcome(payload: dict[str, Any]) -> None:
    alert_id = payload.get("alert_id")
    logger.info("outcome recorded for alert %s: %s", alert_id, payload.get("outcome"))
    try:
        from backend.core.cache import invalidate_cache
        await invalidate_cache("zantara:compliance_metrics:*")
    except Exception as exc:
        logger.debug("compliance outcome cache invalidation skipped: %s", exc)


async def on_intel_validation_complete(payload: dict[str, Any]) -> None:
    staging_id = payload.get("staging_id")
    if staging_id is None:
        return
    try:
        from backend.core.cache import invalidate_cache
        await invalidate_cache(f"zantara:intel_validation:{staging_id}:*")
    except Exception as exc:
        logger.debug("intel validation cache invalidation skipped: %s", exc)


async def on_lkpm_readypack_generated(payload: dict[str, Any]) -> None:
    logger.info(
        "lkpm_readypack_generated: client=%s period=%s drive=%s",
        payload.get("client_id"), payload.get("period"), payload.get("drive_url"),
    )


HANDLERS = {
    # PG channel ``compliance_alert`` maps to this event type.
    "compliance.alert": on_compliance_alert_created,
    # No PG trigger currently emits outcomes, but in-process callers should use
    # the same dotted event namespace as the rest of EventBus.
    "compliance.alert_outcome": on_compliance_alert_outcome,
    # PG channel ``intel_event`` maps here; this handler only acts when the
    # payload carries a staging_id from validator flows.
    "intel.event": on_intel_validation_complete,
    # PG channel ``lkpm_ingest_completed`` maps here.
    "lkpm.ingest_completed": on_lkpm_readypack_generated,
}
