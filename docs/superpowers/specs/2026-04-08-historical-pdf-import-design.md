# Historical PDF Import — Design Spec

**Date:** 2026-04-08
**Owner:** Zero
**Visibility:** OWNER ONLY — private financial data

## Problem

7 PDF files from Downloads contain historical cashout and bonus data predating the system. After deduplication: 5 cashout PDFs + 2 bonus PDFs need importing into the existing HR database.

## Source Files

### Cashout (5 unique PDFs — BZ entity, same schema as existing cashout)

| # | File | Title in PDF | Week date |
|---|------|-------------|-----------|
| 1 | `Weekly Cashout 2026 - BZ 20 FEB 25.pdf` | CASHOUT 20 FEBRUARI 2025 | 2026-02-20 |
| 2 | `Weekly Cashout - BZ 3 MAR 26.pdf` | CASHOUT 3 MARET 2026 | 2026-03-03 |
| 3 | `CASHOUT 06 MARCH 2026.pdf` | CASHOUT 6 MARET 2026 | 2026-03-06 |
| 4 | `Weekly Cashout 2026 - BZ 27 MAR 26.pdf` | CASHOUT 27 MARET 2026 | 2026-03-27 |
| 5 | `Weekly Cashout 2026 FINAL DEDUCT - BZ 4 ARP 26.pdf` | CASHOUT 2 APRIL 2026 | 2026-04-02 |

Columns: NAME, PROCESS, PNBP, URGENT, RPTKA/IMTA, TOTAL INCOME, MARGIN BS, MARGIN BZ, NOTE — identical to existing `owner_weekly_cashout_rows` schema.

Note: all PDFs are BZ only (no BS counterpart). Date "20 FEB 25" is actually Feb 2026 (confirmed by owner). All date typos (2025, 2027, 2028) are 2026.

### Bonus (2 unique PDFs — per-employee task lists)

| # | File | Period | Employees |
|---|------|--------|-----------|
| 1 | `LIST BONUS FEBRUARY 2026.pdf` | Feb 2026 | SAHIRA: 20 tasks, Rp 3,000,000. KRISNA: ~15 tasks |
| 2 | `LIST BONUS OF MARET 2026.pdf` (visible in "Monthly bonus GUYS - RECAP MAR.pdf") | Mar 2026 | SAHIRA: 14 tasks, Rp 2,000,000. KRISNA: 11 tasks |

Columns: NAME (client), SERVICE (visa type). No individual amounts — only TOTAL per employee at bottom.

Feb 2026 bonus includes accounting section for SAHIRA: Total data=282, Not Paid=24 (8.6%), Paid=258 (91.4%).

### Discarded duplicates (5 files)

- `LIST BONUS FEBRUARY 2027.pdf` — identical to Feb 2026
- `LIST BONUS FEBRUARY 2028.pdf` — identical to Feb 2026
- `Monthly bonus GUYS - RECAP MAR.pdf` — identical to Mar 2026 bonus
- `Weekly Cashout 2026 (Asya) - BZ 4 MAR 26.pdf` — duplicate of BZ 3 MAR 26 (Asya prepared it)
- `Weekly Cashout 2026 - GABUNGAN 3 - 13 MARET 2027.pdf` — summary combining individual weeks

## Architecture Decision

**Approach: Shadow History Tables + Staging Pipeline**

Rationale (consensus from 3 independent analyses — Gemini, Codex, DeepSeek):

1. **Do NOT modify `hr_bonus_ledger`** — its `practice_id NOT NULL` FK and trigger are correct constraints. Historical data has no practice_id by definition.
2. **Cashout PDFs → existing `owner_weekly_cashout_rows`** — schema is identical, reuse `upsert_week()`.
3. **Bonus PDFs → new `hr_bonus_historical` tables** — separate from production bonus ledger.
4. **No amount fabrication** — store employee total only, individual items at amount=0.
5. **Staging tables** for parse → review → promote pipeline (12 files of financial data warrant human review).

## Schema

### New tables

```sql
-- Migration 099: Historical bonus import

-- 1. Header: one row per employee per month
CREATE TABLE IF NOT EXISTS hr_bonus_historical (
    id SERIAL PRIMARY KEY,
    employee_name TEXT NOT NULL,            -- raw from PDF (SAHIRA, KRISNA)
    employee_id INTEGER REFERENCES hr_employees(id),  -- resolved, nullable
    bonus_month SMALLINT NOT NULL CHECK (bonus_month BETWEEN 1 AND 12),
    bonus_year SMALLINT NOT NULL CHECK (bonus_year BETWEEN 2020 AND 2100),
    total_amount_idr BIGINT NOT NULL CHECK (total_amount_idr >= 0),
    task_count INTEGER NOT NULL DEFAULT 0,
    source_pdf TEXT NOT NULL,
    accounting_total_data INTEGER,          -- from Feb PDF accounting section
    accounting_not_paid INTEGER,
    accounting_paid INTEGER,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,
    UNIQUE (employee_name, bonus_month, bonus_year)
);

-- 2. Line items: one row per task in PDF
CREATE TABLE IF NOT EXISTS hr_bonus_historical_items (
    id SERIAL PRIMARY KEY,
    history_id INTEGER NOT NULL REFERENCES hr_bonus_historical(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    client_name TEXT NOT NULL,
    service_type TEXT,
    amount_idr BIGINT NOT NULL DEFAULT 0,   -- 0 = derived from total not available
    UNIQUE (history_id, row_index)
);

CREATE INDEX IF NOT EXISTS idx_hr_bonus_hist_period
    ON hr_bonus_historical(bonus_year, bonus_month);
```

### Existing tables used (no changes)

- `owner_weekly_cashout_weeks` — new rows for 5 historical weeks
- `owner_weekly_cashout_rows` — new rows via existing `upsert_week()`

The only change to existing code: add `source TEXT DEFAULT 'sheets'` column to `owner_weekly_cashout_weeks` to distinguish PDF imports from Google Sheet syncs. This is optional but recommended for auditability.

## Import Pipeline

### Stage 1: Parse (automated)

- Tool: `pdfplumber` (Python, no system deps, good at grid-based tables)
- Cashout PDFs: extract table rows → same `CashoutRow` dataclass used by sheet parser
- Bonus PDFs: extract per-employee sections → `(employee_name, [(client, service)])`
- Output: JSON files in `data/imports/` for review

### Stage 2: Review (human)

- Print summary to terminal: row counts, totals, any parsing anomalies
- Owner confirms before DB insert
- Checkpoint: script pauses for confirmation

### Stage 3: Insert (automated, idempotent)

**Cashout:**
1. Create `owner_weekly_cashout_weeks` entry for each week date
2. Insert rows via existing `upsert_week()` — idempotent (delete+replace by week_start)
3. Entity = 'BZ' for all (no BS PDFs available)

**Bonus:**
1. Resolve employee names: `SAHIRA` → employee_id, `KRISNA` → employee_id (hardcoded mapping, only 2 employees)
2. Insert `hr_bonus_historical` header with total
3. Insert `hr_bonus_historical_items` for each task line
4. Idempotent via `UNIQUE (employee_name, bonus_month, bonus_year)` — ON CONFLICT DO UPDATE

### Stage 4: Verify

- Query inserted data, print summary
- Compare totals against PDF values
- Log to `owner_cashout_sync_log` with `triggered_by = 'pdf_import'`

## Frontend

No frontend changes in this iteration. Historical bonus data is accessible via direct DB query or future `/hr/bonus-history` endpoint. The cashout data appears automatically in the existing Owner Cashout pages (same tables).

## Files to create/modify

| Action | Path | Purpose |
|--------|------|---------|
| Create | `backend/migrations/migration_099_hr_bonus_historical.py` | New tables |
| Create | `backend/services/hr/owner_cashout/pdf_parser.py` | pdfplumber extraction |
| Create | `scripts/import_historical_pdfs.py` | One-time import script |
| Modify | `backend/services/hr/owner_cashout/constants.py` | Add PDF_WEEKS mapping |

## Employee name mapping

```python
BONUS_EMPLOYEE_MAP = {
    "SAHIRA": <employee_id>,   # resolve from hr_employees
    "KRISNA": <employee_id>,   # resolve from hr_employees
}
```

## Out of scope

- BS (Bali Services) cashout from PDFs — no BS PDFs provided
- Frontend `/hr/bonus-history` page — deferred
- Per-item bonus amount derivation from rate table — not needed, store total only
- Automated PDF discovery — this is a one-time import of 7 specific files
