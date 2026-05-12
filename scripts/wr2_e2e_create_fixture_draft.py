#!/usr/bin/env python3
"""Create a synthetic war_room_drafts row for E2E testing.

Inserts a draft with fixed UUID 00000000-0000-0000-e2e0-000000000001,
client_id 'e2e_test_client', topic prefixed [E2E TEST], status
'drafts_imaged_checked'.

Idempotent: ON CONFLICT (id) UPDATE re-resets fields for re-run.
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("e2e-fixture")

FIXTURE_UUID = "00000000-0000-0000-e2e0-000000000001"
FIXTURE_CLIENT = "e2e_test_client"

SLIDES_JSON = {
    "carousel_id": "e2e-smoke",
    "slide_count": 2,
    "slides": [
        {"index": 1, "layout_family": "cover-photo",
         "heading": "[E2E TEST] WR2 Pipeline Smoke",
         "subheading": "Synthetic test draft",
         "body": "If you see this in Canva, the pipeline works."},
        {"index": 2, "layout_family": "statement-bomb",
         "statement": "E2E success."},
    ],
}


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2
    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        await conn.execute(
            """
            INSERT INTO war_room_drafts
              (id, topic, register, slides_json, status, created_at, updated_at)
            VALUES ($1, $2, $3, $4::jsonb, 'drafts_imaged_checked', NOW(), NOW())
            ON CONFLICT (id) DO UPDATE
              SET topic = EXCLUDED.topic,
                  slides_json = EXCLUDED.slides_json,
                  status = 'drafts_imaged_checked',
                  canva_edit_url = NULL,
                  canva_design_id = NULL,
                  lease_owner = NULL,
                  lease_acquired_at = NULL,
                  updated_at = NOW()
            """,
            FIXTURE_UUID, "[E2E TEST] WR2 Pipeline Smoke",
            "pedagogico", json.dumps(SLIDES_JSON),
        )
        logger.info("E2E fixture draft ready: id=%s", FIXTURE_UUID)
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
