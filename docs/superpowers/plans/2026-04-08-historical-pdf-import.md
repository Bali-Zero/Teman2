# Historical PDF Import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import 5 cashout PDFs + 2 bonus PDFs (Feb-Apr 2026 historical data) into existing HR database.

**Architecture:** pdfplumber extracts tables from PDFs. Cashout rows go into existing `owner_weekly_cashout_*` tables via `upsert_week()`. Bonus rows go into new `hr_bonus_historical` + `_items` tables (no FK to practices). One-time script with human review checkpoint.

**Tech Stack:** Python 3.11, pdfplumber (already in requirements), asyncpg, existing CashoutRow dataclass + upsert_week()

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `backend/migrations/migration_099_hr_bonus_historical.py` | DDL for 2 new tables |
| Create | `backend/services/hr/owner_cashout/pdf_parser.py` | pdfplumber extraction for cashout + bonus PDFs |
| Create | `backend/tests/services/hr/owner_cashout/test_pdf_parser.py` | Unit tests for PDF parsing |
| Create | `scripts/import_historical_pdfs.py` | One-time import script (parse → review → insert) |

---

### Task 1: Migration 099 — historical bonus tables

**Files:**
- Create: `backend/migrations/migration_099_hr_bonus_historical.py`

- [ ] **Step 1.1: Write migration**

Create `backend/migrations/migration_099_hr_bonus_historical.py`:

```python
"""
Migration 099: Historical bonus import tables

For pre-system bonus data imported from PDF files.
No FK to practices (historical data has no practice_id).
"""

MIGRATION_ID = "099_hr_bonus_historical"

UP_SQL = """
CREATE TABLE IF NOT EXISTS hr_bonus_historical (
    id SERIAL PRIMARY KEY,
    employee_name TEXT NOT NULL,
    employee_id INTEGER,
    bonus_month SMALLINT NOT NULL CHECK (bonus_month BETWEEN 1 AND 12),
    bonus_year SMALLINT NOT NULL CHECK (bonus_year BETWEEN 2020 AND 2100),
    total_amount_idr BIGINT NOT NULL CHECK (total_amount_idr >= 0),
    task_count INTEGER NOT NULL DEFAULT 0,
    source_pdf TEXT NOT NULL,
    accounting_total_data INTEGER,
    accounting_not_paid INTEGER,
    accounting_paid INTEGER,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,
    UNIQUE (employee_name, bonus_month, bonus_year)
);

CREATE TABLE IF NOT EXISTS hr_bonus_historical_items (
    id SERIAL PRIMARY KEY,
    history_id INTEGER NOT NULL REFERENCES hr_bonus_historical(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    client_name TEXT NOT NULL,
    service_type TEXT,
    amount_idr BIGINT NOT NULL DEFAULT 0,
    UNIQUE (history_id, row_index)
);

CREATE INDEX IF NOT EXISTS idx_hr_bonus_hist_period
    ON hr_bonus_historical(bonus_year, bonus_month);
CREATE INDEX IF NOT EXISTS idx_hr_bonus_hist_items_parent
    ON hr_bonus_historical_items(history_id);
"""

DOWN_SQL = """
DROP TABLE IF EXISTS hr_bonus_historical_items;
DROP TABLE IF EXISTS hr_bonus_historical;
"""


async def up(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(UP_SQL)


async def down(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(DOWN_SQL)
```

- [ ] **Step 1.2: Apply migration locally**

Run:
```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python3 -c "
import asyncio, asyncpg
from backend.migrations import migration_099_hr_bonus_historical as m

async def main():
    pool = await asyncpg.create_pool('postgresql://nuzantara@localhost:5432/nuzantara_dev')
    await m.up(pool)
    print('migration 099 applied')
    await pool.close()

asyncio.run(main())
"
```

Expected: `migration 099 applied`

- [ ] **Step 1.3: Verify tables exist**

Run:
```bash
PYTHONPATH=. python3 -c "
import asyncio, asyncpg

async def main():
    pool = await asyncpg.create_pool('postgresql://nuzantara@localhost:5432/nuzantara_dev')
    async with pool.acquire() as c:
        for t in await c.fetch(\"SELECT tablename FROM pg_tables WHERE tablename LIKE 'hr_bonus_hist%' ORDER BY 1\"):
            print(t['tablename'])
    await pool.close()

asyncio.run(main())
"
```

Expected:
```
hr_bonus_historical
hr_bonus_historical_items
```

- [ ] **Step 1.4: Commit**

```bash
git add backend/migrations/migration_099_hr_bonus_historical.py
git commit -m "feat(hr): migration 099 — historical bonus tables for PDF import"
```

---

### Task 2: PDF parser — cashout extraction

**Files:**
- Create: `backend/services/hr/owner_cashout/pdf_parser.py`
- Create: `backend/tests/services/hr/owner_cashout/test_pdf_parser.py`

- [ ] **Step 2.1: Write test for cashout PDF parsing**

Create `backend/tests/services/hr/owner_cashout/test_pdf_parser.py`:

```python
"""Tests for PDF parser (cashout + bonus)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.services.hr.owner_cashout.pdf_parser import (
    parse_cashout_pdf,
    parse_bonus_pdf,
)

DOWNLOADS = Path(os.path.expanduser("~/Downloads"))

# --- Cashout PDF tests ---

CASHOUT_PDF = DOWNLOADS / "Weekly Cashout 2026 - BZ 27 MAR 26.pdf"


@pytest.mark.skipif(not CASHOUT_PDF.exists(), reason="PDF not in Downloads")
class TestParseCashoutPdf:
    def test_returns_rows(self):
        rows = parse_cashout_pdf(CASHOUT_PDF)
        assert len(rows) > 0

    def test_first_row_has_client_name(self):
        rows = parse_cashout_pdf(CASHOUT_PDF)
        assert rows[0].client_name != ""

    def test_all_rows_are_bz_entity(self):
        rows = parse_cashout_pdf(CASHOUT_PDF)
        for r in rows:
            assert r.entity == "BZ"

    def test_amounts_are_positive(self):
        rows = parse_cashout_pdf(CASHOUT_PDF)
        total_income = sum(r.total_income_idr for r in rows)
        assert total_income > 0

    def test_row_count_matches_pdf(self):
        # BZ 27 MAR 26 has 30 data rows (from visual inspection)
        rows = parse_cashout_pdf(CASHOUT_PDF)
        assert len(rows) >= 25  # allow some tolerance

    def test_parse_idr_reused(self):
        rows = parse_cashout_pdf(CASHOUT_PDF)
        # First row: VIKTOR SZABO, C1, Rp1.000.000 PNBP
        r = rows[0]
        assert r.pnbp_idr == 1_000_000


# --- Bonus PDF tests ---

BONUS_PDF = DOWNLOADS / "LIST BONUS FEBRUARY 2026.pdf"


@pytest.mark.skipif(not BONUS_PDF.exists(), reason="PDF not in Downloads")
class TestParseBonusPdf:
    def test_returns_employees(self):
        result = parse_bonus_pdf(BONUS_PDF)
        assert len(result) >= 2  # SAHIRA + KRISNA

    def test_sahira_present(self):
        result = parse_bonus_pdf(BONUS_PDF)
        names = [e["employee_name"] for e in result]
        assert "SAHIRA" in names

    def test_krisna_present(self):
        result = parse_bonus_pdf(BONUS_PDF)
        names = [e["employee_name"] for e in result]
        assert "KRISNA" in names

    def test_sahira_has_tasks(self):
        result = parse_bonus_pdf(BONUS_PDF)
        sahira = [e for e in result if e["employee_name"] == "SAHIRA"][0]
        assert len(sahira["items"]) >= 15

    def test_sahira_total(self):
        result = parse_bonus_pdf(BONUS_PDF)
        sahira = [e for e in result if e["employee_name"] == "SAHIRA"][0]
        assert sahira["total_amount_idr"] == 3_000_000

    def test_items_have_client_and_service(self):
        result = parse_bonus_pdf(BONUS_PDF)
        sahira = [e for e in result if e["employee_name"] == "SAHIRA"][0]
        item = sahira["items"][0]
        assert "client_name" in item
        assert "service_type" in item
        assert item["client_name"] != ""
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run:
```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_pdf_parser.py -v
```

Expected: ImportError (module not found)

- [ ] **Step 2.3: Implement pdf_parser.py**

Create `backend/services/hr/owner_cashout/pdf_parser.py`:

```python
"""PDF parser for historical cashout and bonus data.

Uses pdfplumber to extract structured tables from PDF files.
Cashout PDFs reuse the same CashoutRow dataclass as the sheet parser.
Bonus PDFs produce a list of employee dicts with task items.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pdfplumber

from backend.services.hr.owner_cashout.parser import CashoutRow, parse_idr

logger = logging.getLogger(__name__)


def parse_cashout_pdf(pdf_path: Path | str) -> list[CashoutRow]:
    """Extract BZ cashout rows from a PDF file.

    Expects a table with columns:
    NAME | PROCESS | PNBP | URGENT | RPTKA/IMTA | TOTAL INCOME | MARGIN BS | MARGIN BZ | NOTE
    """
    pdf_path = Path(pdf_path)
    rows: list[CashoutRow] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                for i, row in enumerate(table):
                    if not row or len(row) < 7:
                        continue
                    # Skip header rows
                    cell0 = str(row[0] or "").strip().upper()
                    if cell0 in ("", "NAME", "CASHOUT", "NO") or "MARET" in cell0 or "FEBRUARI" in cell0 or "APRIL" in cell0:
                        continue
                    # Skip total/summary rows
                    if "TOTAL" in cell0:
                        continue

                    name = str(row[0] or "").strip()
                    if not name:
                        continue

                    padded = (list(row) + [None] * 9)[:9]
                    rows.append(
                        CashoutRow(
                            entity="BZ",
                            row_index=len(rows) + 1,
                            client_name=name,
                            process=_clean_str(padded[1]),
                            pnbp_idr=parse_idr(padded[2]),
                            urgent_idr=parse_idr(padded[3]),
                            rptka_imta_idr=parse_idr(padded[4]),
                            total_income_idr=parse_idr(padded[5]),
                            margin_bs_idr=parse_idr(padded[6]),
                            margin_bz_idr=parse_idr(padded[7]),
                            final_price_idr=0,
                            note=_clean_str(padded[8]),
                        )
                    )

    logger.info("[PDF] Parsed %d cashout rows from %s", len(rows), pdf_path.name)
    return rows


def parse_bonus_pdf(pdf_path: Path | str) -> list[dict[str, Any]]:
    """Extract bonus task lists per employee from a PDF file.

    Returns a list of dicts:
    [
        {
            "employee_name": "SAHIRA",
            "total_amount_idr": 3000000,
            "accounting": {"total_data": 282, "not_paid": 24, "paid": 258} | None,
            "items": [{"client_name": "...", "service_type": "...", "row_index": 1}, ...]
        },
        ...
    ]
    """
    pdf_path = Path(pdf_path)
    employees: list[dict[str, Any]] = []
    current_employee: str | None = None
    current_items: list[dict[str, Any]] = []
    current_accounting: dict[str, int] | None = None
    current_total: int = 0
    row_counter = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            tables = page.extract_tables()

            for table in tables:
                if not table:
                    continue
                for row in table:
                    if not row or not row[0]:
                        continue
                    cell0 = str(row[0]).strip().upper()

                    # Detect employee header
                    if cell0 in ("SAHIRA", "KRISNA", "KRISNA "):
                        # Save previous employee
                        if current_employee and current_items:
                            employees.append({
                                "employee_name": current_employee,
                                "total_amount_idr": current_total,
                                "accounting": current_accounting,
                                "items": current_items,
                            })
                        current_employee = cell0.strip()
                        current_items = []
                        current_accounting = None
                        current_total = 0
                        row_counter = 0
                        continue

                    # Skip headers
                    if cell0 in ("NAME", "SERVICE", "ACCOUNTING TASK", "ATTACKER TASK"):
                        continue

                    # Detect accounting stats
                    if cell0.startswith("TOTAL DATA"):
                        val = str(row[1] or "").strip() if len(row) > 1 else ""
                        # Parse "20 + 262 = 282" pattern
                        m = re.search(r"=\s*(\d+)", val)
                        if m:
                            current_accounting = current_accounting or {}
                            current_accounting["total_data"] = int(m.group(1))
                        continue
                    if cell0.startswith("- NOT PAID"):
                        val = str(row[1] or "").strip() if len(row) > 1 else ""
                        m = re.search(r"=\s*(\d+)", val)
                        if m:
                            current_accounting = current_accounting or {}
                            current_accounting["not_paid"] = int(m.group(1))
                        continue
                    if cell0.startswith("- PAID"):
                        val = str(row[1] or "").strip() if len(row) > 1 else ""
                        m = re.search(r"=\s*(\d+)", val)
                        if m:
                            current_accounting = current_accounting or {}
                            current_accounting["paid"] = int(m.group(1))
                        continue
                    if cell0.startswith("CALCULATE"):
                        continue
                    if cell0.startswith("KREDIT"):
                        continue

                    # Detect total line
                    total_match = re.search(r"TOTAL\s*=\s*([\d.,]+)", cell0)
                    if total_match:
                        current_total = parse_idr(total_match.group(1))
                        continue

                    # Regular task row: NAME | SERVICE
                    service = _clean_str(row[1]) if len(row) > 1 else None
                    if service is None and cell0:
                        # Some rows have name only
                        service = None

                    row_counter += 1
                    current_items.append({
                        "client_name": str(row[0]).strip(),
                        "service_type": service,
                        "row_index": row_counter,
                    })

        # Don't forget last employee
        if current_employee and current_items:
            employees.append({
                "employee_name": current_employee,
                "total_amount_idr": current_total,
                "accounting": current_accounting,
                "items": current_items,
            })

    logger.info("[PDF] Parsed %d employee bonus sections from %s", len(employees), pdf_path.name)
    return employees


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None
```

- [ ] **Step 2.4: Run tests**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_pdf_parser.py -v
```

Expected: all tests pass (requires PDFs in ~/Downloads)

- [ ] **Step 2.5: Commit**

```bash
git add backend/services/hr/owner_cashout/pdf_parser.py backend/tests/services/hr/owner_cashout/test_pdf_parser.py
git commit -m "feat(hr): PDF parser for historical cashout + bonus data (pdfplumber)"
```

---

### Task 3: Import script

**Files:**
- Create: `scripts/import_historical_pdfs.py`

- [ ] **Step 3.1: Write the import script**

Create `scripts/import_historical_pdfs.py`:

```python
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

# --- Source PDFs ---

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

# Employee name → hr_employees.id (from Fly DB)
EMPLOYEE_MAP: dict[str, int] = {
    "SAHIRA": 5,
    "KRISNA": 4,
}


async def import_cashout(pool: asyncpg.Pool, dry_run: bool) -> int:
    """Parse and import cashout PDFs into owner_weekly_cashout_*."""
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
    """Parse and import bonus PDFs into hr_bonus_historical + _items."""
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

            # Upsert header
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

            # Delete old items and re-insert
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
```

- [ ] **Step 3.2: Dry-run test**

Run:
```bash
cd apps/backend-rag && source .venv/bin/activate
DATABASE_URL="postgresql://nuzantara@localhost:5432/nuzantara_dev" \
    PYTHONPATH=. python scripts/import_historical_pdfs.py --dry-run
```

Expected: prints parsed summary for each PDF without inserting. Verify row counts and sample data look correct.

- [ ] **Step 3.3: Live import (local DB)**

Run:
```bash
DATABASE_URL="postgresql://nuzantara@localhost:5432/nuzantara_dev" \
    PYTHONPATH=. python scripts/import_historical_pdfs.py
```

Expected: inserts data, prints row counts.

- [ ] **Step 3.4: Verify cashout data**

Run:
```bash
PYTHONPATH=. python3 -c "
import asyncio, asyncpg

async def main():
    pool = await asyncpg.create_pool('postgresql://nuzantara@localhost:5432/nuzantara_dev')
    async with pool.acquire() as c:
        rows = await c.fetch('SELECT week_start, tab_name_bz, total_practices, total_margin_bz_idr FROM owner_weekly_cashout_weeks WHERE week_start >= \\'2026-02-01\\' ORDER BY week_start')
        for r in rows:
            print(f'{r[\"week_start\"]}  {r[\"total_practices\"]:3d}p  MBZ={r[\"total_margin_bz_idr\"]:>15,}  {r[\"tab_name_bz\"]}')
    await pool.close()
asyncio.run(main())
"
```

Expected: 5 new weeks (Feb 20, Mar 3, Mar 6, Mar 27, Apr 2) with practice counts and margin totals.

- [ ] **Step 3.5: Verify bonus data**

Run:
```bash
PYTHONPATH=. python3 -c "
import asyncio, asyncpg

async def main():
    pool = await asyncpg.create_pool('postgresql://nuzantara@localhost:5432/nuzantara_dev')
    async with pool.acquire() as c:
        headers = await c.fetch('SELECT employee_name, bonus_month, bonus_year, total_amount_idr, task_count FROM hr_bonus_historical ORDER BY bonus_year, bonus_month, employee_name')
        for h in headers:
            print(f'{h[\"employee_name\"]:10s}  {h[\"bonus_month\"]:02d}/{h[\"bonus_year\"]}  {h[\"task_count\"]:3d} tasks  Rp{h[\"total_amount_idr\"]:>12,}')
        items_count = await c.fetchval('SELECT count(*) FROM hr_bonus_historical_items')
        print(f'Total items: {items_count}')
    await pool.close()
asyncio.run(main())
"
```

Expected: 4 rows (KRISNA Feb + Mar, SAHIRA Feb + Mar), item count matching PDF task counts.

- [ ] **Step 3.6: Commit**

```bash
git add scripts/import_historical_pdfs.py
git commit -m "feat(hr): one-time import script for historical cashout + bonus PDFs"
```

---

### Task 4: Apply migration + import on Fly production

**Files:** none (ops only)

**CHECKPOINT: requires owner confirmation before each step.**

- [ ] **Step 4.1: Apply migration 099 on Fly**

Same technique as migration 098 — inline SQL via `fly ssh console`:

```bash
fly ssh console -a nuzantara-rag -C "python3 -c \"
import asyncio, os, asyncpg

q = chr(39)
SQL = f'''
CREATE TABLE IF NOT EXISTS hr_bonus_historical (
    id SERIAL PRIMARY KEY,
    employee_name TEXT NOT NULL,
    employee_id INTEGER,
    bonus_month SMALLINT NOT NULL CHECK (bonus_month BETWEEN 1 AND 12),
    bonus_year SMALLINT NOT NULL CHECK (bonus_year BETWEEN 2020 AND 2100),
    total_amount_idr BIGINT NOT NULL CHECK (total_amount_idr >= 0),
    task_count INTEGER NOT NULL DEFAULT 0,
    source_pdf TEXT NOT NULL,
    accounting_total_data INTEGER,
    accounting_not_paid INTEGER,
    accounting_paid INTEGER,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,
    UNIQUE (employee_name, bonus_month, bonus_year)
);
CREATE TABLE IF NOT EXISTS hr_bonus_historical_items (
    id SERIAL PRIMARY KEY,
    history_id INTEGER NOT NULL REFERENCES hr_bonus_historical(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    client_name TEXT NOT NULL,
    service_type TEXT,
    amount_idr BIGINT NOT NULL DEFAULT 0,
    UNIQUE (history_id, row_index)
);
CREATE INDEX IF NOT EXISTS idx_hr_bonus_hist_period ON hr_bonus_historical(bonus_year, bonus_month);
CREATE INDEX IF NOT EXISTS idx_hr_bonus_hist_items_parent ON hr_bonus_historical_items(history_id);
'''

async def main():
    pool = await asyncpg.create_pool(os.environ['DATABASE_URL'])
    async with pool.acquire() as conn:
        await conn.execute(SQL)
    print('migration 099 applied')
    await pool.close()

asyncio.run(main())
\""
```

Expected: `migration 099 applied`

- [ ] **Step 4.2: Deploy backend with pdf_parser**

```bash
cd apps/backend-rag && fly deploy --strategy rolling --app nuzantara-rag
```

- [ ] **Step 4.3: Run import on Fly (cashout + bonus)**

The import script needs the PDF files, which are local. Two options:
1. Run locally against Fly DB via proxy: `fly proxy 15432:5432 -a nuzantara-postgres` then use `DATABASE_URL=postgresql://...@localhost:15432/...`
2. Parse locally, insert via Fly API

Recommended: fly proxy approach.

```bash
# Terminal 1: start proxy
fly proxy 15432:5432 -a nuzantara-postgres &

# Terminal 2: run import
cd apps/backend-rag && source .venv/bin/activate
DATABASE_URL="postgresql://backend_rag_v2:<password>@localhost:15432/nuzantara" \
    PYTHONPATH=. python scripts/import_historical_pdfs.py --dry-run

# Review output, then:
DATABASE_URL="postgresql://backend_rag_v2:<password>@localhost:15432/nuzantara" \
    PYTHONPATH=. python scripts/import_historical_pdfs.py
```

- [ ] **Step 4.4: Verify on production**

Open `kita.balizero.com/hr/owner-cashout` — the 5 new weeks should appear in the weekly table (Feb 20, Mar 3, Mar 6, Mar 27, Apr 2).

- [ ] **Step 4.5: Commit and push**

```bash
git add -A
git commit -m "feat(hr): import 5 cashout + 2 bonus historical PDFs (Feb-Apr 2026)"
git push origin main
```
