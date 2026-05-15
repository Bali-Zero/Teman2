"""One-shot script: parse cashout PDFs and upsert into owner_weekly_cashout_*.

Usage:
    PYTHONPATH=. python scripts/ingest_cashout_pdfs.py PDF1 PDF2 ...

The week_start date is extracted from the PDF title row ("CASHOUT DD MMM YYYY").
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
from datetime import date
from pathlib import Path

import asyncpg
import pdfplumber

from backend.app.core.config import settings
from backend.services.hr.owner_cashout.pdf_parser import parse_cashout_pdf
from backend.services.hr.owner_cashout.sync_service import upsert_week

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("ingest_cashout")

_MONTH_MAP = {
    "januari": 1, "jan": 1,
    "februari": 2, "feb": 2, "february": 2,
    "maret": 3, "mar": 3, "march": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "jun": 6, "june": 6,
    "juli": 7, "jul": 7, "july": 7,
    "agustus": 8, "aug": 8, "august": 8,
    "september": 9, "sep": 9,
    "oktober": 10, "oct": 10, "october": 10,
    "november": 11, "nov": 11,
    "desember": 12, "december": 12, "des": 12, "dec": 12,
}

_DATE_RE = re.compile(
    r"CASHOUT\s+(\d{1,2})\s+([A-Z]+)\s+(\d{4})",
    re.IGNORECASE,
)


def extract_week_start(pdf_path: Path) -> date:
    """Read first page title to extract cashout date."""
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    m = _DATE_RE.search(text)
    if not m:
        raise ValueError(f"Cannot extract date from PDF title in {pdf_path.name!r}. Text: {text[:200]!r}")
    day = int(m.group(1))
    month_str = m.group(2).lower()
    year = int(m.group(3))
    month = _MONTH_MAP.get(month_str)
    if not month:
        raise ValueError(f"Unknown month {m.group(2)!r} in {pdf_path.name!r}")
    return date(year, month, day)


async def ingest_pdf(pool: asyncpg.Pool, pdf_path: Path) -> None:
    week_start = extract_week_start(pdf_path)
    rows = parse_cashout_pdf(pdf_path)
    logger.info("[%s] week_start=%s  rows=%d", pdf_path.name, week_start, len(rows))
    await upsert_week(
        pool,
        week_start=week_start,
        tab_bz=f"PDF:{pdf_path.name}",
        tab_bs=None,
        rows=rows,
    )
    logger.info("[%s] upserted OK", pdf_path.name)


async def main(paths: list[str]) -> None:
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    try:
        for p in paths:
            pdf_path = Path(p)
            if not pdf_path.exists():
                logger.error("File not found: %s", p)
                continue
            try:
                await ingest_pdf(pool, pdf_path)
            except Exception as e:
                logger.error("[%s] FAILED: %s", pdf_path.name, e)
    finally:
        await pool.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: PYTHONPATH=. python scripts/ingest_cashout_pdfs.py PDF1 [PDF2 ...]")
        sys.exit(1)
    asyncio.run(main(sys.argv[1:]))
