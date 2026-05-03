"""One-time import of historical cashout + bonus PDFs.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    DATABASE_URL="postgresql://nuzantara@localhost:5432/nuzantara_dev" \
        PYTHONPATH=. python scripts/import_historical_pdfs.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date
from pathlib import Path

import asyncpg

from backend.services.hr.owner_cashout.parser import CashoutRow
from backend.services.hr.owner_cashout.pdf_parser import parse_cashout_pdf, parse_bonus_pdf
from backend.services.hr.owner_cashout.sync_service import upsert_week

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DOWNLOADS = Path(os.path.expanduser("~/Downloads"))

CASHOUT_PDFS: list[dict] = [
    {"file": "Weekly Cashout 2026 - BZ 20 FEB 25.pdf", "week": date(2026, 2, 20)},
    {"file": "Weekly Cashout - BZ 3 MAR 26.pdf", "week": date(2026, 3, 3)},
    {"file": "CASHOUT 06 MARCH 2026.pdf", "week": date(2026, 3, 6)},
    {"file": "Weekly Cashout 2026 - BZ 27 MAR 26.pdf", "week": date(2026, 3, 27)},
    {"file": "Weekly Cashout 2026 FINAL DEDUCT - BZ 4 ARP 26.pdf", "week": date(2026, 4, 2)},
]

BONUS_PDFS: list[dict] = [
    {"file": "LIST BONUS FEBRUARY 2026.pdf", "month": 2, "year": 2026},
    {"file": "Monthly bonus GUYS - RECAP MAR.pdf", "month": 3, "year": 2026},
]

EMPLOYEE_MAP: dict[str, int] = {
    "SAHIRA": 5,
    "KRISNA": 4,
    "SURYA": 3,
    "ADIT": 1,
    "ARI": 2,
    "DAMAR": 7,
}


async def import_cashout(pool: asyncpg.Pool, dry_run: bool) -> int:
    total_rows = 0
    for entry in CASHOUT_PDFS:
        pdf_path = DOWNLOADS / entry["file"]
        if not pdf_path.exists():
            logger.warning("SKIP (not found): %s", pdf_path)
            continue

        rows = parse_cashout_pdf(pdf_path)
        logger.info(
            "CASHOUT %s: %d rows, total_income=%s, margin_bz=%s",
            entry["file"], len(rows),
            f"Rp{sum(r.total_income_idr for r in rows):,.0f}",
            f"Rp{sum(r.margin_bz_idr for r in rows):,.0f}",
        )

        if dry_run:
            for r in rows[:3]:
                logger.info("  sample: %s | %s | MBZ=%s", r.client_name, r.process, f"Rp{r.margin_bz_idr:,}")
            continue

        tab_name = f"PDF {entry['file']}"
        await upsert_week(
            pool,
            week_start=entry["week"],
            tab_bz=tab_name,
            tab_bs=None,
            rows=rows,
        )
        total_rows += len(rows)
        logger.info("  --> inserted week %s (%d rows)", entry["week"], len(rows))

    return total_rows


async def import_bonuses(pool: asyncpg.Pool, dry_run: bool) -> int:
    total_items = 0
    for entry in BONUS_PDFS:
        pdf_path = DOWNLOADS / entry["file"]
        if not pdf_path.exists():
            logger.warning("SKIP (not found): %s", pdf_path)
            continue

        employees = parse_bonus_pdf(pdf_path)
        for emp in employees:
            name = emp["employee_name"]
            employee_id = EMPLOYEE_MAP.get(name)
            items = emp["items"]
            total = emp["total_amount_idr"]

            logger.info(
                "BONUS %s %02d/%d: %s — %d tasks, total=%s",
                entry["file"], entry["month"], entry["year"],
                name, len(items), f"Rp{total:,}",
            )

            if dry_run:
                for it in items[:3]:
                    logger.info("  sample: %s | %s", it["client_name"], it["service_type"])
                continue

            history_id = await pool.fetchval(
                """
                INSERT INTO hr_bonus_historical
                    (employee_name, employee_id, bonus_month, bonus_year,
                     total_amount_idr, task_count, source_pdf,
                     accounting_total_data, accounting_not_paid, accounting_paid)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (employee_name, bonus_month, bonus_year) DO UPDATE SET
                    total_amount_idr = EXCLUDED.total_amount_idr,
                    task_count = EXCLUDED.task_count,
                    source_pdf = EXCLUDED.source_pdf,
                    imported_at = now()
                RETURNING id
                """,
                name, employee_id, entry["month"], entry["year"],
                total, len(items), entry["file"],
                (emp.get("accounting") or {}).get("total_data"),
                (emp.get("accounting") or {}).get("not_paid"),
                (emp.get("accounting") or {}).get("paid"),
            )

            await pool.execute(
                "DELETE FROM hr_bonus_historical_items WHERE history_id = $1",
                history_id,
            )
            for item in items:
                await pool.execute(
                    """
                    INSERT INTO hr_bonus_historical_items
                        (history_id, row_index, client_name, service_type, amount_idr)
                    VALUES ($1, $2, $3, $4, 0)
                    """,
                    history_id, item["row_index"], item["client_name"],
                    item.get("service_type"),
                )

            total_items += len(items)
            logger.info("  --> inserted %d items for %s", len(items), name)

    return total_items


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import historical PDFs")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no DB writes")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "postgresql://nuzantara@localhost:5432/nuzantara_dev")
    pool = await asyncpg.create_pool(db_url)

    logger.info("=== PHASE 1: CASHOUT PDFs ===")
    cashout_rows = await import_cashout(pool, args.dry_run)

    logger.info("=== PHASE 2: BONUS PDFs ===")
    bonus_items = await import_bonuses(pool, args.dry_run)

    logger.info("=== DONE === cashout_rows=%d, bonus_items=%d, dry_run=%s",
                cashout_rows, bonus_items, args.dry_run)

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
