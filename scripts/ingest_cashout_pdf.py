"""One-shot script: parse a cashout PDF and upsert into DB.

Usage:
    PYTHONPATH=. python scripts/ingest_cashout_pdf.py <pdf_path> <week_start YYYY-MM-DD>

Example:
    PYTHONPATH=. python scripts/ingest_cashout_pdf.py \
        "/Users/nuzantara/Downloads/Weekly Cashout 2026 (Asya) - BZ 10 APR 2026.pdf" \
        2026-04-10
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "apps/backend-rag/.env")

from backend.services.hr.owner_cashout.pdf_parser import parse_cashout_pdf
from backend.services.hr.owner_cashout.sync_service import upsert_week

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(pdf_path: str, week_start_str: str) -> None:
    pdf = Path(pdf_path)
    if not pdf.exists():
        logger.error("PDF not found: %s", pdf)
        sys.exit(1)

    week_start = date.fromisoformat(week_start_str)
    tab_name = pdf.stem  # use filename as tab label

    logger.info("Parsing PDF: %s", pdf.name)
    rows = parse_cashout_pdf(pdf)
    logger.info("Parsed %d rows", len(rows))

    db_url = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    try:
        week_id = await upsert_week(
            pool,
            week_start=week_start,
            tab_bz=tab_name,
            tab_bs=None,
            rows=rows,
        )
        logger.info("✅ Upserted week_id=%d (week_start=%s, rows=%d)", week_id, week_start, len(rows))
    finally:
        await pool.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <pdf_path> <YYYY-MM-DD>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
