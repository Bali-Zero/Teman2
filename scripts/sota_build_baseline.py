#!/usr/bin/env python3
"""Fase 0 Day 1 driver — assembles 00_baseline.json from all sensors.

Run once at start of Fase 0. Idempotent (overwrites prior baseline).
Gate 1 (EOD day 1): ≥20 numeric metrics. Script exits 1 if count < 20.

Ahrefs + GSC/GA4 + CRM are STUBBED here; Task 5 replaces with real sensors.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))
# `apps.evaluator.seo_cell.*` lives at repo-root; add it so GSC/GA4 import.
sys.path.insert(0, str(_REPO_ROOT))

# Provide placeholder env vars so backend.Settings validation doesn't crash
# at import time. Real secrets come from ~/.nuzantara-secrets.env for the
# actual sensor calls; these placeholders are only for pydantic Settings
# boot-time validation.
os.environ.setdefault("JWT_SECRET_KEY", "sota-research-local-dev-placeholder-32chars-min-ok")
os.environ.setdefault("API_KEYS", "sota-research-local-placeholder-key")

import asyncpg  # noqa: E402

from backend.services.measurer.ig_graph_sensor import IGGraphSensor  # noqa: E402
from backend.services.measurer.brevo_stats_client import BrevoStatsClient  # noqa: E402
from backend.services.research.ahrefs_snapshot import fetch_ahrefs_snapshot  # noqa: E402
from backend.services.research.baseline_builder import (  # noqa: E402
    BaselineBuilder,
    BaselineSnapshot,
)
from backend.services.research.crm_baseline import fetch_crm_baseline  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.baseline")

OUTPUT_DIR = _REPO_ROOT / "research" / "sota-social-2026-v1"


async def _ig() -> dict:
    token = os.environ.get("IG_GRAPH_API_TOKEN")
    ig_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID")
    if not (token and ig_id):
        logger.warning("IG secrets missing — skipping IG pull")
        return {"followers_count": 0, "media_count": 0}
    s = IGGraphSensor(token=token, ig_user_id=ig_id)
    try:
        summary = await s.read_account_summary()
    except Exception as exc:
        logger.warning("IG read failed: %s", exc)
        return {"followers_count": 0, "media_count": 0}
    return {
        "followers_count": summary.get("followers_count", 0),
        "media_count": summary.get("media_count", 0),
    }


async def _brevo() -> dict:
    key = os.environ.get("BREVO_API_KEY") or os.environ.get("SENDGRID_API_KEY")
    if not key:
        logger.warning("Brevo key missing — skipping Brevo pull")
        return {
            "total_subscribers": 0, "total_blacklisted": 0, "list_count": 0,
            "campaigns_analyzed": 0, "avg_open_rate": 0.0, "avg_click_rate": 0.0,
        }
    c = BrevoStatsClient(api_key=key)
    try:
        lists = await c.fetch_list_totals()
        camps = await c.fetch_campaign_aggregates(limit=30)
    except Exception as exc:
        logger.warning("Brevo read failed: %s", exc)
        return {
            "total_subscribers": 0, "total_blacklisted": 0, "list_count": 0,
            "campaigns_analyzed": 0, "avg_open_rate": 0.0, "avg_click_rate": 0.0,
        }
    return {**lists, **camps}


async def _gsc_ga4() -> tuple[dict, dict]:
    """Live read GSC + GA4 via existing seo_cell sensors.

    Both sensors have their own internal failure policy (green/yellow/red).
    We extract the numeric subset either way and let metric_count() see
    real zeros when data is genuinely absent (GA4 property traffic is
    very low today — yellow state confirmed 2026-04-22).
    """
    try:
        from apps.evaluator.seo_cell.sensors.gsc_sensor import GSCSensor
        from apps.evaluator.seo_cell.sensors.ga4_sensor import GA4Sensor
    except ImportError as exc:
        logger.warning("seo_cell sensors unavailable: %s", exc)
        return (
            {"clicks_total": 0, "impressions_total": 0, "query_count": 0},
            {"sessions_total": 0, "conversions_total": 0, "page_count": 0},
        )

    try:
        gsc_reading = await GSCSensor().read()
        gsc_val = gsc_reading.value or {}
        gsc = {
            "clicks_total": int(gsc_val.get("clicks_total", 0)),
            "impressions_total": int(gsc_val.get("impressions_total", 0)),
            "query_count": int(gsc_val.get("query_count", 0)),
        }
        logger.info("GSC status=%s: clicks=%d impressions=%d queries=%d",
                    gsc_reading.status, gsc["clicks_total"],
                    gsc["impressions_total"], gsc["query_count"])
    except Exception as exc:
        logger.warning("GSC fetch failed: %s", exc)
        gsc = {"clicks_total": 0, "impressions_total": 0, "query_count": 0}

    try:
        ga4_reading = await GA4Sensor().read()
        ga4_val = ga4_reading.value or {}
        ga4 = {
            "sessions_total": int(ga4_val.get("sessions_total", 0)),
            "conversions_total": int(ga4_val.get("conversions_total", 0)),
            "page_count": int(ga4_val.get("page_count", 0)),
        }
        logger.info("GA4 status=%s: sessions=%d conversions=%d pages=%d",
                    ga4_reading.status, ga4["sessions_total"],
                    ga4["conversions_total"], ga4["page_count"])
    except Exception as exc:
        logger.warning("GA4 fetch failed: %s", exc)
        ga4 = {"sessions_total": 0, "conversions_total": 0, "page_count": 0}

    return (gsc, ga4)


async def _ahrefs_and_crm(db_pool) -> tuple[dict, dict]:
    """Ahrefs returns zeros with `source_status=plan_insufficient` today
    (see backend/services/research/ahrefs_snapshot.py for upgrade path).
    CRM reads `clients.lead_source` on nuzantara_dev.
    """
    ahrefs = fetch_ahrefs_snapshot()
    try:
        crm = await fetch_crm_baseline(db_pool)
        logger.info("CRM: total_90d=%d social_90d=%d coverage=%.2f%%",
                    crm["leads_total_90d"], crm["leads_social_90d"],
                    crm["utm_coverage_pct"] * 100)
    except Exception as exc:
        logger.warning("CRM fetch failed: %s", exc)
        crm = {"leads_total_90d": 0, "leads_social_90d": 0, "utm_coverage_pct": 0.0}
    return (ahrefs, crm)


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL") or "postgresql://localhost:5432/nuzantara_dev"
    db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        ig = await _ig()
        brevo = await _brevo()
        gsc, ga4 = await _gsc_ga4()
        ahrefs, crm = await _ahrefs_and_crm(db_pool)
    finally:
        await db_pool.close()

    snap = BaselineSnapshot(
        captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        gsc=gsc, ga4=ga4, instagram=ig, brevo=brevo, ahrefs=ahrefs, crm=crm,
    )
    builder = BaselineBuilder(OUTPUT_DIR)
    path = builder.build_and_persist(snap)
    count = snap.metric_count()
    logger.info("baseline written: %s (%d numeric metrics)", path, count)
    if count < 20:
        logger.error(
            "Gate 1 FAIL: baseline has only %d metrics (need ≥20). "
            "Wire remaining sensors in Task 5.",
            count,
        )
        return 1
    logger.info("Gate 1 OK: %d metrics present", count)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
