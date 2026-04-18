"""
EventBus handlers for compliance + intel events.

Channels registered (PG NOTIFY):
  compliance_alert_created   — {alert_id, client_id, category, severity}
  compliance_alert_outcome   — {alert_id, outcome, actioned_by}
  intel_validation_complete  — {staging_id, status, score}
  lkpm_readypack_generated   — {client_id, period, drive_url}
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
        from backend.services.cache.invalidation import invalidate_cache
        await invalidate_cache(f"zantara:compliance_alerts:{client_id}:*")
        await invalidate_cache("zantara:compliance_metrics:*")
    except ImportError:
        logger.debug("cache invalidation module missing, skipping")


async def on_compliance_alert_outcome(payload: dict[str, Any]) -> None:
    alert_id = payload.get("alert_id")
    logger.info("outcome recorded for alert %s: %s", alert_id, payload.get("outcome"))
    try:
        from backend.services.cache.invalidation import invalidate_cache
        await invalidate_cache("zantara:compliance_metrics:*")
    except ImportError:
        pass


async def on_intel_validation_complete(payload: dict[str, Any]) -> None:
    staging_id = payload.get("staging_id")
    try:
        from backend.services.cache.invalidation import invalidate_cache
        await invalidate_cache(f"zantara:intel_validation:{staging_id}:*")
    except ImportError:
        pass


async def on_lkpm_readypack_generated(payload: dict[str, Any]) -> None:
    logger.info(
        "lkpm_readypack_generated: client=%s period=%s drive=%s",
        payload.get("client_id"), payload.get("period"), payload.get("drive_url"),
    )


HANDLERS = {
    "compliance_alert_created": on_compliance_alert_created,
    "compliance_alert_outcome": on_compliance_alert_outcome,
    "intel_validation_complete": on_intel_validation_complete,
    "lkpm_readypack_generated": on_lkpm_readypack_generated,
}
