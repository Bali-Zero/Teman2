#!/usr/bin/env python3
"""Every-6h cron — pull metrics for every post published in last 168h.

Triggered by infra/launchagents/com.balizero.sota.m13-collect.plist.
Kill switch: system_settings.sota_m13_collect_enabled = 'true'.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "apps" / "backend-rag"))

import asyncpg

from backend.services.measurer.ig_graph_sensor import IGGraphSensor
from backend.services.measurer.m13_feedback_loop import (
    M13CollectionHorizon,
    M13FeedbackLoop,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("sota.m13.collect")


async def kill_switch_on(conn) -> bool:
    value = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'sota_m13_collect_enabled'"
    )
    return value == "true"


async def main() -> int:
    dsn = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            if not await kill_switch_on(conn):
                logger.info("kill switch OFF — exiting")
                return 0

        m13 = M13FeedbackLoop(db_pool=pool)

        async with pool.acquire() as conn:
            posts = await conn.fetch(
                """
                SELECT id, platform, post_external_id, published_at
                  FROM war_room_posts
                 WHERE published_at > NOW() - INTERVAL '168 hours'
                """
            )

        for post in posts:
            age = datetime.now(timezone.utc) - post["published_at"]
            if age < timedelta(hours=24):
                continue  # too young for first horizon
            if age < timedelta(hours=72):
                horizon = M13CollectionHorizon.T_24H
            elif age < timedelta(hours=168):
                horizon = M13CollectionHorizon.T_72H
            else:
                horizon = M13CollectionHorizon.T_168H

            if post["platform"] == "instagram":
                token = os.environ.get("IG_GRAPH_API_TOKEN")
                ig_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID")
                if not (token and ig_id):
                    logger.warning("IG creds missing, skipping post %s", post["id"])
                    continue
                sensor = IGGraphSensor(token=token, ig_user_id=ig_id)
                try:
                    insights = await sensor._fetch_insights(
                        post["post_external_id"], "IMAGE"
                    )
                except Exception as e:
                    logger.warning(
                        "insights fetch failed for %s: %s", post["id"], e
                    )
                    continue
                await m13.collect_post_metrics(
                    post_id=post["id"],
                    horizon=horizon,
                    metrics=insights,
                    source="ig_graph",
                )
                logger.info("collected %s @ %s", post["id"], horizon.name)
            # TODO: linkedin, tiktok horizons in future sprints
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
