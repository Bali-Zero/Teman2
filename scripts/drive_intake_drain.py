"""Drive-intake drain caller — cron entrypoint that arms drain_drive (FASE 1B).

Runs ON the Pro (LaunchAgent com.balizero.drive-intake-drain, every 10 min):
connects to the LOCAL intake Postgres and drains Drive changes scoped to
INTAKE_DRIVE_SCOPE_FOLDER_ID (the Dropbox-Intake/ folder id) into intake_queue.
Mirrors scripts/wa_media_pull_worker.py (same DB, same sovereign-local stance).
ZERO CRM writes — enqueue only; the worker + FASE-5 review do the rest.

Env:
- LOCAL_DATABASE_URL            (default postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev)
- INTAKE_DRIVE_SCOPE_FOLDER_ID  (REQUIRED by the adapter — fail-safe skip if missing)
- INTAKE_DRIVE_DRAIN_LIMIT      (default 200 changes per tick)

State JSON for the sentinel family: ~/.agent/decisions/state/drive_intake_drain.last.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

import asyncpg  # noqa: E402

from backend.services.intake.drive_adapter import drain_drive  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("drive_intake_drain")

STATE_FILE = Path.home() / ".agent" / "decisions" / "state" / "drive_intake_drain.last.json"


async def main() -> int:
    db_url = os.getenv(
        "LOCAL_DATABASE_URL", "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
    )
    limit = int(os.getenv("INTAKE_DRIVE_DRAIN_LIMIT", "200"))

    started = time.time()
    pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=2)
    try:
        counters = await drain_drive(pool, limit=limit)
    finally:
        await pool.close()

    elapsed = round(time.time() - started, 1)
    state = {
        "job": "drive_intake_drain",
        "ts": int(time.time()),
        "status": "ok" if counters.get("errors", 0) == 0 else "partial",
        "elapsed": elapsed,
        **counters,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state) + "\n")
    logger.info("drain tick done: %s", state)
    return 0 if counters.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
