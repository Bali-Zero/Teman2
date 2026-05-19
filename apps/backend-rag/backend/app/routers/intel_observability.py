"""Intel Lake + WR2 pipeline observability — Phase D 2026-05-20.

Single endpoint returning a machine-readable JSON snapshot of pipeline
health. Consumed by:
  - admin dashboard `/observability` page (Pro-only)
  - runbook section "che cosa controllare giornalmente"
  - synthetic probe failure diagnostics
  - external monitoring (Telegram alert wrapper)

Design choices:
  - Read-only — no mutations, no auth (no secrets exposed in response).
  - Cheap PG queries only (no Qdrant, no LLM, no NotebookLM).
  - Total query time target ≤500ms (5 short SELECTs, all index-backed).
  - Phase D scope: NOT a replacement for Langfuse / Sentry — just a
    single pane for the 2 most-watched pipelines.

Sample response:

    {
      "intel_lake": {
        "outbox_depth": 12,
        "outbox_oldest_unconsumed_seconds": 47,
        "router_last_classified_at": "2026-05-20T03:55:12+00:00",
        "nb_pusher_last_pushed_at": "2026-05-20T03:54:01+00:00",
        "items_last_1h": 35,
        "items_needs_review_last_24h": 142
      },
      "wr2": {
        "drafts_by_state": {"BRIEFED": 3, "STORYBOARDED": 1, "PUBLISHED": 87},
        "drafts_last_24h": 4,
        "last_published_at": "2026-05-19T16:39:00+00:00"
      },
      "probes": {
        "intel_lake_last_pass": "2026-05-20T03:00:00+00:00",
        "wr2_last_pass": "2026-05-19T22:00:00+00:00"
      },
      "checked_at": "2026-05-20T04:30:00+00:00",
      "health": "green"
    }

Health classification (single-line summary for dashboard traffic-light):
  - green   : all SLO met
  - yellow  : outbox_depth > 100 OR no router activity in 1h OR no probe
              pass in 12h
  - red     : outbox_depth > 1000 OR no router activity in 6h OR no probe
              pass in 24h OR last probe FAILED
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intel/health", tags=["intel-observability"])


def _classify_health(intel: dict[str, Any], wr2: dict[str, Any], probes: dict[str, Any]) -> str:
    """Traffic-light classification — keep logic obvious for dashboard."""
    outbox_depth = intel.get("outbox_depth", 0)
    if outbox_depth > 1000:
        return "red"

    router_last = intel.get("router_last_classified_at")
    now = datetime.now(timezone.utc)
    if router_last:
        try:
            dt = datetime.fromisoformat(router_last)
            age_h = (now - dt).total_seconds() / 3600
            if age_h > 6:
                return "red"
            if age_h > 1:
                return "yellow"
        except ValueError:
            pass

    if outbox_depth > 100:
        return "yellow"

    return "green"


@router.get("/pipeline")
async def get_pipeline_health(request: Request) -> dict[str, Any]:
    """Single-pane pipeline health snapshot.

    Returns 503 if DB pool unavailable. Returns 200 with partial data on
    individual query failure (degraded reporting > silent failure).
    """
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="db pool not initialized")

    intel: dict[str, Any] = {}
    wr2: dict[str, Any] = {}
    probes: dict[str, Any] = {}

    async with pool.acquire() as conn:
        # ── Intel Lake ────────────────────────────────────────────────
        try:
            row = await conn.fetchrow(
                """
                SELECT
                    count(*) FILTER (WHERE consumed_at IS NULL) AS outbox_depth,
                    EXTRACT(EPOCH FROM (now() - min(created_at) FILTER (WHERE consumed_at IS NULL)))::int AS outbox_oldest_unconsumed_seconds
                FROM events_outbox
                WHERE channel = 'intel_lake_event'
                  AND created_at > now() - interval '7 days'
                """
            )
            intel["outbox_depth"] = int(row["outbox_depth"] or 0)
            intel["outbox_oldest_unconsumed_seconds"] = (
                int(row["outbox_oldest_unconsumed_seconds"])
                if row["outbox_oldest_unconsumed_seconds"] is not None
                else None
            )
        except Exception as e:
            logger.warning("intel.outbox query failed: %s", e)
            intel["outbox_error"] = str(e)[:200]

        try:
            row = await conn.fetchrow(
                """
                SELECT
                    max(last_seen_at) FILTER (WHERE routing_status IN ('blog','wr2','nb-intel','archive','skip')) AS router_last_classified_at,
                    count(*) FILTER (WHERE first_seen_at > now() - interval '1 hour') AS items_last_1h,
                    count(*) FILTER (WHERE routing_status = 'needs_review' AND first_seen_at > now() - interval '24 hours') AS items_needs_review_last_24h
                FROM intel_items
                WHERE first_seen_at > now() - interval '7 days'
                """
            )
            intel["router_last_classified_at"] = (
                row["router_last_classified_at"].isoformat()
                if row["router_last_classified_at"]
                else None
            )
            intel["items_last_1h"] = int(row["items_last_1h"] or 0)
            intel["items_needs_review_last_24h"] = int(row["items_needs_review_last_24h"] or 0)
        except Exception as e:
            logger.warning("intel.items query failed: %s", e)
            intel["items_error"] = str(e)[:200]

        try:
            row = await conn.fetchrow(
                """
                SELECT max(pushed_at) AS nb_pusher_last_pushed_at
                FROM intel_item_nb_pushes
                WHERE status = 'pushed'
                """
            )
            intel["nb_pusher_last_pushed_at"] = (
                row["nb_pusher_last_pushed_at"].isoformat()
                if row["nb_pusher_last_pushed_at"]
                else None
            )
        except Exception as e:
            logger.warning("intel.nb_pushes query failed: %s", e)
            intel["nb_pushes_error"] = str(e)[:200]

        # ── WR2 ───────────────────────────────────────────────────────
        try:
            rows = await conn.fetch(
                """
                SELECT status, count(*) AS n
                FROM war_room_drafts
                WHERE created_at > now() - interval '14 days'
                  AND (topic IS NULL OR topic NOT LIKE '[PROBE-SANDBOX-%')
                GROUP BY status
                """
            )
            wr2["drafts_by_state"] = {r["status"]: int(r["n"]) for r in rows}
        except Exception as e:
            logger.warning("wr2.drafts_by_state query failed: %s", e)
            wr2["drafts_by_state_error"] = str(e)[:200]

        try:
            row = await conn.fetchrow(
                """
                SELECT
                    count(*) FILTER (WHERE created_at > now() - interval '24 hours') AS drafts_last_24h
                FROM war_room_drafts
                WHERE topic IS NULL OR topic NOT LIKE '[PROBE-SANDBOX-%'
                """
            )
            wr2["drafts_last_24h"] = int(row["drafts_last_24h"] or 0)
        except Exception as e:
            logger.warning("wr2.drafts_last_24h query failed: %s", e)
            wr2["drafts_last_24h_error"] = str(e)[:200]

        try:
            row = await conn.fetchrow(
                "SELECT max(published_at) AS last_published_at FROM war_room_posts"
            )
            wr2["last_published_at"] = (
                row["last_published_at"].isoformat() if row["last_published_at"] else None
            )
        except Exception as e:
            logger.warning("wr2.last_published_at query failed: %s", e)
            wr2["last_published_at_error"] = str(e)[:200]

        # ── Probes (sandbox tenant — Phase C) ─────────────────────────
        # Last probe pass timestamp via system_settings if probe writer
        # records it; otherwise NULL. Phase C probes don't persist a
        # last-pass timestamp yet — Phase D LaunchAgent wrapper will.
        try:
            row = await conn.fetchrow(
                """
                SELECT value FROM system_settings WHERE key = 'probe_intel_lake_last_pass'
                """
            )
            probes["intel_lake_last_pass"] = row["value"] if row else None
        except Exception:
            probes["intel_lake_last_pass"] = None

        try:
            row = await conn.fetchrow(
                """
                SELECT value FROM system_settings WHERE key = 'probe_wr2_last_pass'
                """
            )
            probes["wr2_last_pass"] = row["value"] if row else None
        except Exception:
            probes["wr2_last_pass"] = None

    health = _classify_health(intel, wr2, probes)
    return {
        "intel_lake": intel,
        "wr2": wr2,
        "probes": probes,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "health": health,
    }
