"""Event bridge from intel-scraper-cell runs into ObservedShellBus.

Each scraper run emits exactly ONE row of name ``intel.scraper.run`` to
``observed_shell_events`` (migration 151, already live on prod) via
:class:`backend.services.events.observed_shell.ObservedShellBus`. When
the DB pool is unavailable, the bus auto-falls-back to JSONL at
``~/logs/observed-shell.jsonl``.

The contract is a strict superset of the schema mandated in the Sprint
1 W1 spec — we add ``hgt_published_count`` since we already track it.

Field summary::

    {
      name: "intel.scraper.run",
      trace_id: <uuid str>,
      status: ok|degraded|failed,
      sources_attempted: int,
      articles_found: int,
      scars_added: int,
      hgt_published_count: int,
      duration_ms: int,
      started_at: <iso8601>,
      finished_at: <iso8601>,
    }

This module is deliberately thin: ObservedShellBus already implements
all error handling. The bridge only enforces the field contract and
status enum.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger("intel_scraper_cell.event_bridge")


# Match the ObservedShellBus VALID_STATUSES, but the cell only ever
# emits these three. Anything outside the set raises at the bridge
# layer so a typo in the scraper code is loud, not silent.
ALLOWED_STATUSES = ("ok", "degraded", "failed")


class _ObservedShellBusLike(Protocol):
    """Subset of ObservedShellBus used by the bridge."""

    async def emit(
        self,
        automation_name: str,
        status: str,
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        ...


class IntelScraperEventBridge:
    """Wraps :class:`ObservedShellBus` for the cell's run-event contract.

    Construct once per process, hand to :class:`IntelScraperCellRunner`
    so each ``finish_run()`` call lands one row.
    """

    AUTOMATION_NAME = "intel.scraper.run"

    def __init__(self, bus: _ObservedShellBusLike) -> None:
        self._bus = bus

    async def emit_run(
        self,
        *,
        trace_id: str,
        status: str,
        sources_attempted: int,
        articles_found: int,
        scars_added: int,
        hgt_published_count: int,
        duration_ms: int,
        started_at: str,
        finished_at: str,
    ) -> None:
        """Emit one ``intel.scraper.run`` row.

        Validation:
        * ``status`` must be in :data:`ALLOWED_STATUSES` — typos surface
          early. ObservedShellBus would coerce unknown statuses to
          'error', but the cell-level event contract is narrower than
          that, so we fail fast here. Test contract: a typo in status
          raises ValueError.
        * Counters are coerced to ``int`` (no float surprises).
        """
        if status not in ALLOWED_STATUSES:
            raise ValueError(
                f"intel.scraper.run status must be one of "
                f"{ALLOWED_STATUSES}, got {status!r}"
            )

        payload: dict[str, Any] = {
            "sources_attempted": int(sources_attempted),
            "articles_found": int(articles_found),
            "scars_added": int(scars_added),
            "hgt_published_count": int(hgt_published_count),
            "duration_ms": int(duration_ms),
            "started_at": started_at,
            "finished_at": finished_at,
        }
        await self._bus.emit(
            automation_name=self.AUTOMATION_NAME,
            status=status,
            payload=payload,
            trace_id=trace_id,
        )
        logger.info(
            "intel_scraper.run_event status=%s sources=%d articles=%d "
            "scars=%d hgt=%d duration_ms=%d trace_id=%s",
            status,
            payload["sources_attempted"],
            payload["articles_found"],
            payload["scars_added"],
            payload["hgt_published_count"],
            payload["duration_ms"],
            trace_id,
        )


__all__ = [
    "ALLOWED_STATUSES",
    "IntelScraperEventBridge",
]
