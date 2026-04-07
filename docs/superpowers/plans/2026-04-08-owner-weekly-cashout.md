# Owner Weekly Cashout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importare le pratiche settimanali dal Google Sheet "WEEKLY CASHOUT" in una sezione privata di `kita.balizero.com/hr` visibile solo all'owner, con overview aggregato e drill-down per settimana.

**Architecture:** Service Account legge lo sheet, cron settimanale (Air) + endpoint manuale upserta i dati in 3 tabelle Postgres isolate, FastAPI espone 6 endpoint owner-gated, Next.js mostra overview + drill-down.

**Tech Stack:** FastAPI + asyncpg + Google Sheets API v4 + Next.js 15 (App Router) + Recharts + Tailwind.

**Spec:** `docs/superpowers/specs/2026-04-07-owner-weekly-cashout-design.md`

---

## File Structure

### Backend (apps/backend-rag)

**Create:**
- `backend/migrations/migration_098_owner_weekly_cashout.py` — schema DB (3 tabelle)
- `backend/app/deps/owner.py` — dependency `require_owner()` + `OWNER_EMAILS` constant
- `backend/services/hr/owner_cashout/__init__.py` — package marker
- `backend/services/hr/owner_cashout/constants.py` — `TAB_TO_WEEK`, `JUNK_TABS`, `SHEET_ID`
- `backend/services/hr/owner_cashout/parser.py` — `parse_idr`, `parse_bz_tab`, `parse_bs_tab`, `CashoutRow` dataclass
- `backend/services/hr/owner_cashout/sheet_reader.py` — SA client wrapper (read-only)
- `backend/services/hr/owner_cashout/sync_service.py` — `run_sync()`, `upsert_week()`, sync log helpers
- `backend/services/hr/owner_cashout/repository.py` — query helpers per API (overview, weeks, drill-down, visa-types)
- `backend/services/hr/owner_cashout/telegram_alert.py` — alert helper per chat 1125336968
- `backend/app/routers/hr_owner_cashout.py` — 6 endpoint FastAPI
- `scripts/sync_owner_cashout.py` — entrypoint CLI per cron Air
- `backend/tests/services/hr/owner_cashout/__init__.py`
- `backend/tests/services/hr/owner_cashout/test_parser.py`
- `backend/tests/services/hr/owner_cashout/test_sync_service.py`
- `backend/tests/services/hr/owner_cashout/test_repository.py`
- `backend/tests/app/deps/test_owner.py`
- `backend/tests/app/routers/test_hr_owner_cashout.py`
- `backend/tests/services/hr/owner_cashout/fixtures/bz_22_aug_sample.json` — golden fixture per parser
- `backend/tests/services/hr/owner_cashout/fixtures/bs_22_aug_sample.json`

**Modify:**
- `backend/app/deps/__init__.py` — export `require_owner` se esiste init, altrimenti nulla
- `backend/app/dependencies.py` — re-export `require_owner`
- `backend/app/setup/router_registration.py` — registra nuovo router
- `backend/app/main_cloud.py` o `backend/app/main.py` — (verifica se richiede mount esplicito, altrimenti nulla)

### Frontend (apps/mouth)

**Create:**
- `src/app/(workspace)/hr/owner-cashout/page.tsx` — overview page
- `src/app/(workspace)/hr/owner-cashout/[weekId]/page.tsx` — drill-down page
- `src/lib/api/hr/owner-cashout.ts` — typed fetch wrappers
- `src/types/owner-cashout.ts` — TypeScript types
- `src/lib/auth/owner.ts` — `OWNER_EMAILS` set + `isOwner(email)` helper
- `src/components/hr/OwnerCashoutOverview.tsx` — overview component (KPI cards + charts + table)
- `src/components/hr/OwnerCashoutDrillDown.tsx` — drill-down component
- `src/components/hr/OwnerCashoutRefreshButton.tsx` — manual refresh + status

**Modify:**
- `src/app/(workspace)/hr/layout.tsx` — aggiungi voce sidebar "Owner Cashout" gated

### Ops

**Create:**
- `infra/air/cron/owner_cashout.cron` — crontab entry per Air

**Modify:** (manual step, not code)
- Air crontab (`crontab -e`)
- Air secrets env (`~/.zshrc.secrets` or systemd-style env file)

---

## Task Breakdown

### Task 1: Create worktree and branch

**Files:** none (git operation)

- [ ] **Step 1.1: Create feature branch from main**

Run:
```bash
cd /Users/nuzantara/Desktop/nuzantara
git checkout main && git pull origin main
git checkout -b feat/owner-weekly-cashout
```

Expected: branch created, clean tree.

- [ ] **Step 1.2: Verify nothing pending**

Run:
```bash
git status
```

Expected: `nothing to commit, working tree clean`.

---

### Task 2: Migration 098 — schema

**Files:**
- Create: `apps/backend-rag/backend/migrations/migration_098_owner_weekly_cashout.py`

- [ ] **Step 2.1: Write migration file**

Create `apps/backend-rag/backend/migrations/migration_098_owner_weekly_cashout.py`:

```python
"""
Migration 098: Owner Weekly Cashout — Private weekly practice tracking for owner

Tables:
  - owner_weekly_cashout_weeks: one row per ISO-like week, totals
  - owner_weekly_cashout_rows: one row per client practice, per entity (BZ|BS)
  - owner_cashout_sync_log: history of sync runs

Visibility: OWNER ONLY. Isolated from hr_employees / payroll tables.
"""

MIGRATION_ID = "098_owner_weekly_cashout"

UP_SQL = """
CREATE TABLE IF NOT EXISTS owner_weekly_cashout_weeks (
    id SERIAL PRIMARY KEY,
    week_start DATE NOT NULL UNIQUE,
    tab_name_bz TEXT,
    tab_name_bs TEXT,
    total_practices INT NOT NULL DEFAULT 0,
    total_income_idr BIGINT NOT NULL DEFAULT 0,
    total_margin_bz_idr BIGINT NOT NULL DEFAULT 0,
    total_margin_bs_idr BIGINT NOT NULL DEFAULT 0,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_owner_cashout_weeks_start
    ON owner_weekly_cashout_weeks(week_start DESC);

CREATE TABLE IF NOT EXISTS owner_weekly_cashout_rows (
    id SERIAL PRIMARY KEY,
    week_id INT NOT NULL REFERENCES owner_weekly_cashout_weeks(id) ON DELETE CASCADE,
    entity TEXT NOT NULL CHECK (entity IN ('BZ', 'BS')),
    row_index INT NOT NULL,
    client_name TEXT NOT NULL,
    process TEXT,
    pnbp_idr BIGINT NOT NULL DEFAULT 0,
    urgent_idr BIGINT NOT NULL DEFAULT 0,
    rptka_imta_idr BIGINT NOT NULL DEFAULT 0,
    total_income_idr BIGINT NOT NULL DEFAULT 0,
    margin_bs_idr BIGINT NOT NULL DEFAULT 0,
    margin_bz_idr BIGINT NOT NULL DEFAULT 0,
    final_price_idr BIGINT NOT NULL DEFAULT 0,
    note TEXT,
    UNIQUE (week_id, entity, row_index)
);

CREATE INDEX IF NOT EXISTS idx_owner_cashout_rows_week
    ON owner_weekly_cashout_rows(week_id);
CREATE INDEX IF NOT EXISTS idx_owner_cashout_rows_process
    ON owner_weekly_cashout_rows(process);

CREATE TABLE IF NOT EXISTS owner_cashout_sync_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
    weeks_processed INT NOT NULL DEFAULT 0,
    weeks_skipped INT NOT NULL DEFAULT 0,
    rows_upserted INT NOT NULL DEFAULT 0,
    unknown_tabs TEXT,
    error TEXT,
    triggered_by TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_owner_cashout_sync_log_started
    ON owner_cashout_sync_log(started_at DESC);
"""

DOWN_SQL = """
DROP TABLE IF EXISTS owner_cashout_sync_log;
DROP TABLE IF EXISTS owner_weekly_cashout_rows;
DROP TABLE IF EXISTS owner_weekly_cashout_weeks;
"""


async def up(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(UP_SQL)


async def down(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(DOWN_SQL)
```

- [ ] **Step 2.2: Apply migration locally (dev Postgres)**

Run:
```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.migrations import migration_098_owner_weekly_cashout as m

async def main():
    url = os.environ.get('DATABASE_URL') or 'postgresql://postgres:postgres@localhost:5432/nuzantara_dev'
    pool = await asyncpg.create_pool(url)
    await m.up(pool)
    async with pool.acquire() as c:
        rows = await c.fetch(\"\"\"SELECT table_name FROM information_schema.tables
                              WHERE table_name LIKE 'owner_%cashout%' OR table_name = 'owner_cashout_sync_log'\"\"\")
        print('TABLES:', [r['table_name'] for r in rows])
    await pool.close()

asyncio.run(main())
"
```

Expected: `TABLES: ['owner_cashout_sync_log', 'owner_weekly_cashout_rows', 'owner_weekly_cashout_weeks']` (order may vary).

- [ ] **Step 2.3: Test down migration**

Run:
```bash
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.migrations import migration_098_owner_weekly_cashout as m

async def main():
    url = os.environ.get('DATABASE_URL') or 'postgresql://postgres:postgres@localhost:5432/nuzantara_dev'
    pool = await asyncpg.create_pool(url)
    await m.down(pool)
    async with pool.acquire() as c:
        rows = await c.fetch(\"\"\"SELECT table_name FROM information_schema.tables
                              WHERE table_name LIKE 'owner_%cashout%' OR table_name = 'owner_cashout_sync_log'\"\"\")
        print('TABLES:', [r['table_name'] for r in rows])
    await pool.close()

asyncio.run(main())
"
```

Expected: `TABLES: []`

- [ ] **Step 2.4: Re-apply up for subsequent tasks**

Run (same up command as step 2.2).

- [ ] **Step 2.5: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_098_owner_weekly_cashout.py
git commit -m "feat(hr): migration 098 owner weekly cashout schema"
```

---

### Task 3: Owner dependency

**Files:**
- Create: `apps/backend-rag/backend/app/deps/owner.py`
- Create: `apps/backend-rag/backend/tests/app/deps/test_owner.py`
- Modify: `apps/backend-rag/backend/app/dependencies.py`

- [ ] **Step 3.1: Write failing test**

Create `apps/backend-rag/backend/tests/app/deps/__init__.py` (empty) and `backend/tests/app/deps/test_owner.py`:

```python
"""Tests for owner-only dependency."""
import pytest
from fastapi import HTTPException

from backend.app.deps.owner import OWNER_EMAILS, require_owner


def test_owner_emails_contains_zero():
    assert "zero@balizero.com" in OWNER_EMAILS


def test_owner_emails_contains_antonellosiano():
    assert "antonellosiano@balizero.com" in OWNER_EMAILS


def test_owner_emails_is_frozenset():
    assert isinstance(OWNER_EMAILS, frozenset)


@pytest.mark.asyncio
async def test_require_owner_allows_zero():
    user = {"email": "zero@balizero.com", "role": "admin"}
    result = await require_owner(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_owner_allows_antonellosiano():
    user = {"email": "antonellosiano@balizero.com", "role": "admin"}
    result = await require_owner(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_owner_denies_other_admin():
    user = {"email": "asya@balizero.com", "role": "admin"}
    with pytest.raises(HTTPException) as exc:
        await require_owner(user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_owner_denies_missing_email():
    user = {"role": "admin"}
    with pytest.raises(HTTPException) as exc:
        await require_owner(user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_owner_denies_client():
    user = {"email": "random@example.com", "role": "client"}
    with pytest.raises(HTTPException) as exc:
        await require_owner(user=user)
    assert exc.value.status_code == 403
```

- [ ] **Step 3.2: Run test (should fail: module not found)**

Run:
```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/app/deps/test_owner.py -v
```

Expected: ImportError / ModuleNotFoundError for `backend.app.deps.owner`.

- [ ] **Step 3.3: Create owner.py**

Create `apps/backend-rag/backend/app/deps/owner.py`:

```python
"""Owner-only access dependency.

Only zero@balizero.com and antonellosiano@balizero.com (alias of zero)
are allowed. All other admins (asya, adit, etc.) receive 403.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException

from backend.app.deps.auth import get_current_user

logger = logging.getLogger(__name__)

OWNER_EMAILS: frozenset[str] = frozenset({
    "zero@balizero.com",
    "antonellosiano@balizero.com",
})


async def require_owner(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Gate an endpoint to owner-only access.

    Raises:
        HTTPException 403: if caller is not an owner
    """
    email = user.get("email")
    if email not in OWNER_EMAILS:
        logger.warning(
            "Owner-only access denied email=%s role=%s",
            email,
            user.get("role"),
        )
        raise HTTPException(
            status_code=403,
            detail="Owner access required",
        )
    return user
```

- [ ] **Step 3.4: Run tests (should pass)**

Run:
```bash
PYTHONPATH=. pytest backend/tests/app/deps/test_owner.py -v
```

Expected: 7 passed.

- [ ] **Step 3.5: Re-export from dependencies.py**

Edit `backend/app/dependencies.py`:

Find:
```python
from backend.app.deps.auth import (
    get_current_portal_client,
    get_current_user,
    get_current_user_email,
    get_current_user_optional,
    require_team_member,
    security,
)
```

Add right after:
```python
from backend.app.deps.owner import OWNER_EMAILS, require_owner
```

Then in the `__all__` list, after `"require_team_member",` add:
```python
    "require_owner",
    "OWNER_EMAILS",
```

- [ ] **Step 3.6: Verify import chain**

Run:
```bash
PYTHONPATH=. python -c "from backend.app.dependencies import require_owner, OWNER_EMAILS; print('OK', len(OWNER_EMAILS))"
```

Expected: `OK 2`

- [ ] **Step 3.7: Commit**

```bash
git add backend/app/deps/owner.py backend/app/dependencies.py backend/tests/app/deps/
git commit -m "feat(hr): add require_owner dependency for owner-only endpoints"
```

---

### Task 4: Constants module

**Files:**
- Create: `apps/backend-rag/backend/services/hr/owner_cashout/__init__.py`
- Create: `apps/backend-rag/backend/services/hr/owner_cashout/constants.py`

- [ ] **Step 4.1: Create package**

Create `backend/services/hr/owner_cashout/__init__.py`:

```python
"""Owner Weekly Cashout — private, owner-only HR feature.

Imports the WEEKLY CASHOUT google sheet into Postgres and exposes
aggregated + drill-down views via FastAPI, gated by require_owner.
"""
```

- [ ] **Step 4.2: Create constants.py**

Create `backend/services/hr/owner_cashout/constants.py`:

```python
"""Constants for owner weekly cashout sync.

TAB_TO_WEEK is the source of truth for which sheet tabs map to which
weeks. New tabs must be added here manually (alert via Telegram on unknown
tabs during sync).
"""
from __future__ import annotations

from datetime import date

SHEET_ID: str = "1OZzgvDLgf3yd9eUh5CyADjHCHLoXmE5nIRoJlut_jBE"

# Verified against sheet 2026-04-07
TAB_TO_WEEK: dict[str, date] = {
    "BZ 22 AUG":          date(2025, 8, 22),
    "BS 22 AUG":          date(2025, 8, 22),
    "BZ 29 AUG":          date(2025, 8, 29),
    "BS 29 AUG":          date(2025, 8, 29),
    "BZ 05 SEPT":         date(2025, 9, 5),
    "BS 05 SEPT":         date(2025, 9, 5),
    "BZ 12 SEPT":         date(2025, 9, 12),
    "BS 12 SEPT":         date(2025, 9, 12),
    "BZ 19 SEPT":         date(2025, 9, 19),
    "BS 19 SEPT":         date(2025, 9, 19),
    "BZ 26 SEPT":         date(2025, 9, 26),
    "BS 26 SEPT":         date(2025, 9, 26),
    "BZ 03 OCT":          date(2025, 10, 3),
    "BS 03 OCT":          date(2025, 10, 3),
    "BZ 10 OCT":          date(2025, 10, 10),
    "BS 10 OCT":          date(2025, 10, 10),
    "BZ 17 OCT":          date(2025, 10, 17),
    "BS 17 OCT":          date(2025, 10, 17),
    "BZ 24 OCT":          date(2025, 10, 24),
    "BS 24 OCT":          date(2025, 10, 24),
    "BZ 31 OCT":          date(2025, 10, 31),
    "BS 31 OCT":          date(2025, 10, 31),
    "BZ 07 NOV":          date(2025, 11, 7),
    "BS 07 NOV":          date(2025, 11, 7),
    "BZ 14 NOV":          date(2025, 11, 14),
    "BS 14 NOV":          date(2025, 11, 14),
    "BZ 21 NOV":          date(2025, 11, 21),
    "BS 21 NOV":          date(2025, 11, 21),
    "BZ 28 NOV":          date(2025, 11, 28),
    "BS 28 NOV":          date(2025, 11, 28),
    "BZ 05 DEC":          date(2025, 12, 5),
    "BS 05 DEC":          date(2025, 12, 5),
    "BZ 12 DEC":          date(2025, 12, 12),
    "BS 12 DEC":          date(2025, 12, 12),
    "BZ 19 DEC":          date(2025, 12, 19),
    "BS 19 DEC":          date(2025, 12, 19),
    "BZ 26 DES & 2 JAN":  date(2025, 12, 26),  # combo 2-week tab
    "BS 26 DES & 2 JAN":  date(2025, 12, 26),
    "BZ 09 JAN 26":       date(2026, 1, 9),
    "BS 09 JAN 26":       date(2026, 1, 9),
    "BZ 16-23 JAN 26":    date(2026, 1, 16),   # combo 2-week tab
    "BS 16-23 JAN 26":    date(2026, 1, 16),
    "BZ 30 JAN":          date(2026, 1, 30),
}

# Tabs that must be skipped (junk, duplicates, backups).
JUNK_TABS: frozenset[str] = frozenset({
    "Sheet18",
    "Copy of BZ 31 OCT",
    "BS 19 DEC 25 - 09 JAN 26",
})
```

- [ ] **Step 4.3: Verify import**

Run:
```bash
PYTHONPATH=. python -c "
from backend.services.hr.owner_cashout.constants import TAB_TO_WEEK, JUNK_TABS, SHEET_ID
assert len(TAB_TO_WEEK) == 43  # 22 BZ + 21 BS (BS 30 JAN missing)
assert len(JUNK_TABS) == 3
print('OK', len(TAB_TO_WEEK), 'tabs mapped')
"
```

Expected: `OK 43 tabs mapped`

- [ ] **Step 4.4: Commit**

```bash
git add backend/services/hr/owner_cashout/__init__.py backend/services/hr/owner_cashout/constants.py
git commit -m "feat(hr): owner cashout constants (sheet id, tab→week lookup)"
```

---

### Task 5: Parser — dataclass + parse_idr

**Files:**
- Create: `apps/backend-rag/backend/services/hr/owner_cashout/parser.py`
- Create: `apps/backend-rag/backend/tests/services/hr/owner_cashout/__init__.py`
- Create: `apps/backend-rag/backend/tests/services/hr/owner_cashout/test_parser.py`

- [ ] **Step 5.1: Write failing tests for parse_idr**

Create `backend/tests/services/hr/owner_cashout/__init__.py` (empty).

Create `backend/tests/services/hr/owner_cashout/test_parser.py`:

```python
"""Tests for owner cashout sheet parser."""
from backend.services.hr.owner_cashout.parser import (
    CashoutRow,
    parse_bs_tab,
    parse_bz_tab,
    parse_idr,
)


class TestParseIdr:
    def test_standard_format(self):
        assert parse_idr("Rp1,000,000") == 1_000_000

    def test_large_amount(self):
        assert parse_idr("Rp10,500,000") == 10_500_000

    def test_empty_string(self):
        assert parse_idr("") == 0

    def test_none(self):
        assert parse_idr(None) == 0

    def test_whitespace_only(self):
        assert parse_idr("   ") == 0

    def test_dash_placeholder(self):
        assert parse_idr("-") == 0
        assert parse_idr("—") == 0

    def test_plain_number_no_prefix(self):
        assert parse_idr("500000") == 500_000

    def test_with_dot_separator(self):
        assert parse_idr("Rp1.000.000") == 1_000_000

    def test_invalid_returns_zero(self):
        assert parse_idr("not a number") == 0
```

- [ ] **Step 5.2: Run test (should fail)**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_parser.py::TestParseIdr -v
```

Expected: ImportError.

- [ ] **Step 5.3: Create parser.py skeleton + parse_idr**

Create `backend/services/hr/owner_cashout/parser.py`:

```python
"""Parser for WEEKLY CASHOUT sheet rows.

BZ schema (9 cols): NAME | PROCESS | PNBP | URGENT | RPTKA/IMTA | TOTAL_INCOME | MARGIN_BS | MARGIN_BZ | NOTE
BS schema (7 cols): NAME | PROCESS | PNBP | URGENT | RPTKA/IMTA | MARGIN_BS | FINAL_PRICE
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CashoutRow:
    entity: str  # 'BZ' | 'BS'
    row_index: int
    client_name: str
    process: str | None
    pnbp_idr: int
    urgent_idr: int
    rptka_imta_idr: int
    total_income_idr: int  # only BZ, 0 for BS
    margin_bs_idr: int
    margin_bz_idr: int     # only BZ, 0 for BS
    final_price_idr: int   # only BS, 0 for BZ
    note: str | None


def parse_idr(value: Any) -> int:
    """Parse IDR string like 'Rp1,000,000' to int.

    Returns 0 for empty/None/invalid.
    """
    if value is None:
        return 0
    s = str(value).strip()
    if not s or s in ("-", "—"):
        return 0
    cleaned = s.replace("Rp", "").replace(",", "").replace(".", "").strip()
    if not cleaned:
        return 0
    try:
        return int(cleaned)
    except ValueError:
        logger.warning("[CASHOUT] Failed to parse IDR: %r", value)
        return 0


def parse_bz_tab(rows: list[list[str]]) -> list[CashoutRow]:
    raise NotImplementedError


def parse_bs_tab(rows: list[list[str]]) -> list[CashoutRow]:
    raise NotImplementedError
```

- [ ] **Step 5.4: Run parse_idr tests (should pass)**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_parser.py::TestParseIdr -v
```

Expected: 9 passed.

- [ ] **Step 5.5: Commit**

```bash
git add backend/services/hr/owner_cashout/parser.py backend/tests/services/hr/owner_cashout/
git commit -m "feat(hr): owner cashout parser skeleton + parse_idr"
```

---

### Task 6: Parser — parse_bz_tab

**Files:**
- Modify: `apps/backend-rag/backend/services/hr/owner_cashout/parser.py`
- Modify: `apps/backend-rag/backend/tests/services/hr/owner_cashout/test_parser.py`
- Create: `apps/backend-rag/backend/tests/services/hr/owner_cashout/fixtures/bz_22_aug_sample.json`

- [ ] **Step 6.1: Write fixture (real sheet data)**

Create `backend/tests/services/hr/owner_cashout/fixtures/bz_22_aug_sample.json`:

```json
{
  "description": "Real sample from BZ 22 AUG tab",
  "rows": [
    ["NEW CASHOUT 22 AUGUST 2025"],
    ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "TOTAL INCOME", "MARGIN BS", "MARGIN BZ", "NOTE"],
    ["JULIANNA JANOSI", "BRIDGING VISA", "Rp1,000,000", "", "", "Rp5,000,000", "Rp3,000,000", "Rp1,000,000"],
    [],
    ["EVA MARIE CASTEL", "C1", "Rp1,000,000", "", "", "Rp2,700,000", "Rp600,000", "Rp1,100,000"],
    ["JAVIER EMILIANO JOSE ZOLE", "C1", "Rp1,000,000", "", "", "Rp2,700,000", "Rp600,000", "Rp1,100,000"],
    [],
    ["JAMES ANTHONY KOSTRO", "C10", "Rp2,000,000", "", "", "Rp3,500,000", "Rp800,000", "Rp700,000"],
    [],
    ["RYAN RALPH HEATHCOTE", "D12 2 YEARS", "Rp7,000,000", "", "", "Rp9,800,000", "Rp800,000", "Rp2,000,000", "DISCOUNT 200K"],
    ["MOHAMED REDA BOUZIANE", "D12 1 YEAR - URGENT", "Rp5,000,000", "Rp1,000,000", "", "Rp7,500,000", "Rp800,000", "Rp700,000"]
  ]
}
```

- [ ] **Step 6.2: Write failing tests for parse_bz_tab**

Append to `backend/tests/services/hr/owner_cashout/test_parser.py`:

```python
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> list[list[str]]:
    data = json.loads((FIXTURES / name).read_text())
    return data["rows"]


class TestParseBzTab:
    def test_skips_title_and_header(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        # Title (row 1), header (row 2) must be skipped
        assert all(r.client_name not in ("NEW CASHOUT 22 AUGUST 2025", "NAME") for r in result)

    def test_skips_empty_rows(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        assert all(r.client_name for r in result)

    def test_extracts_all_clients(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        assert len(result) == 6
        names = {r.client_name for r in result}
        assert "JULIANNA JANOSI" in names
        assert "EVA MARIE CASTEL" in names
        assert "JAMES ANTHONY KOSTRO" in names
        assert "MOHAMED REDA BOUZIANE" in names

    def test_parses_amounts_for_first_row(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        julianna = next(r for r in result if r.client_name == "JULIANNA JANOSI")
        assert julianna.process == "BRIDGING VISA"
        assert julianna.pnbp_idr == 1_000_000
        assert julianna.urgent_idr == 0
        assert julianna.rptka_imta_idr == 0
        assert julianna.total_income_idr == 5_000_000
        assert julianna.margin_bs_idr == 3_000_000
        assert julianna.margin_bz_idr == 1_000_000
        assert julianna.final_price_idr == 0  # BZ doesn't populate this
        assert julianna.entity == "BZ"

    def test_extracts_note_when_present(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        ryan = next(r for r in result if r.client_name == "RYAN RALPH HEATHCOTE")
        assert ryan.note == "DISCOUNT 200K"

    def test_urgent_amount_parsed(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        urgent = next(r for r in result if "MOHAMED" in r.client_name)
        assert urgent.urgent_idr == 1_000_000

    def test_row_index_preserves_sheet_position(self):
        rows = load_fixture("bz_22_aug_sample.json")
        result = parse_bz_tab(rows)
        julianna = next(r for r in result if r.client_name == "JULIANNA JANOSI")
        assert julianna.row_index == 3  # 1-indexed, row 3 in sheet

    def test_empty_rows_list(self):
        assert parse_bz_tab([]) == []

    def test_only_header_no_data(self):
        rows = [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS"],
        ]
        assert parse_bz_tab(rows) == []
```

- [ ] **Step 6.3: Run tests (should fail: NotImplementedError)**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_parser.py::TestParseBzTab -v
```

Expected: 9 failures (NotImplementedError).

- [ ] **Step 6.4: Implement parse_bz_tab**

Replace `parse_bz_tab` body in `backend/services/hr/owner_cashout/parser.py`:

```python
def parse_bz_tab(rows: list[list[str]]) -> list[CashoutRow]:
    """Parse a BZ weekly tab. Rows 1-2 are title+header, data starts at row 3.

    Empty rows are visual separators and must be skipped.
    """
    out: list[CashoutRow] = []
    # rows[0] = title, rows[1] = header, data from rows[2]
    for i, row in enumerate(rows[2:], start=3):
        # Pad row to 9 columns to avoid IndexError
        padded = (list(row) + [""] * 9)[:9]
        name = str(padded[0]).strip() if padded[0] else ""
        if not name:
            continue  # separator row
        out.append(
            CashoutRow(
                entity="BZ",
                row_index=i,
                client_name=name,
                process=(str(padded[1]).strip() or None),
                pnbp_idr=parse_idr(padded[2]),
                urgent_idr=parse_idr(padded[3]),
                rptka_imta_idr=parse_idr(padded[4]),
                total_income_idr=parse_idr(padded[5]),
                margin_bs_idr=parse_idr(padded[6]),
                margin_bz_idr=parse_idr(padded[7]),
                final_price_idr=0,
                note=(str(padded[8]).strip() or None),
            )
        )
    return out
```

- [ ] **Step 6.5: Run tests (should pass)**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_parser.py::TestParseBzTab -v
```

Expected: 9 passed.

- [ ] **Step 6.6: Commit**

```bash
git add backend/services/hr/owner_cashout/parser.py backend/tests/services/hr/owner_cashout/
git commit -m "feat(hr): parse_bz_tab with real sheet fixture"
```

---

### Task 7: Parser — parse_bs_tab

**Files:**
- Modify: `apps/backend-rag/backend/services/hr/owner_cashout/parser.py`
- Modify: `apps/backend-rag/backend/tests/services/hr/owner_cashout/test_parser.py`
- Create: `apps/backend-rag/backend/tests/services/hr/owner_cashout/fixtures/bs_22_aug_sample.json`

- [ ] **Step 7.1: Write BS fixture**

Create `backend/tests/services/hr/owner_cashout/fixtures/bs_22_aug_sample.json`:

```json
{
  "description": "Real sample from BS 22 AUG tab",
  "rows": [
    ["NEW CASHOUT 22 AUG"],
    ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "MARGIN BS", "FINAL PRICE"],
    ["JULIANNA JANOSI", "BRIDGING VISA", "Rp1,000,000", "", "", "Rp3,000,000", "Rp4,000,000"],
    [],
    ["EVA MARIE CASTEL", "C1", "Rp1,000,000", "", "", "Rp600,000", "Rp1,600,000"],
    ["JAVIER EMILIANO JOSE", "C1", "Rp1,000,000", "", "", "Rp600,000", "Rp1,600,000"]
  ]
}
```

- [ ] **Step 7.2: Write failing tests**

Append to `backend/tests/services/hr/owner_cashout/test_parser.py`:

```python
class TestParseBsTab:
    def test_extracts_clients(self):
        rows = load_fixture("bs_22_aug_sample.json")
        result = parse_bs_tab(rows)
        assert len(result) == 3
        names = [r.client_name for r in result]
        assert "JULIANNA JANOSI" in names
        assert "EVA MARIE CASTEL" in names

    def test_parses_bs_schema_amounts(self):
        rows = load_fixture("bs_22_aug_sample.json")
        result = parse_bs_tab(rows)
        julianna = next(r for r in result if r.client_name == "JULIANNA JANOSI")
        assert julianna.entity == "BS"
        assert julianna.process == "BRIDGING VISA"
        assert julianna.pnbp_idr == 1_000_000
        assert julianna.margin_bs_idr == 3_000_000
        assert julianna.final_price_idr == 4_000_000
        assert julianna.total_income_idr == 0  # BS doesn't populate this
        assert julianna.margin_bz_idr == 0     # BS doesn't populate this
        assert julianna.note is None

    def test_skips_empty_rows(self):
        rows = load_fixture("bs_22_aug_sample.json")
        result = parse_bs_tab(rows)
        assert all(r.client_name for r in result)

    def test_row_index_preserved(self):
        rows = load_fixture("bs_22_aug_sample.json")
        result = parse_bs_tab(rows)
        julianna = next(r for r in result if r.client_name == "JULIANNA JANOSI")
        assert julianna.row_index == 3

    def test_empty_input(self):
        assert parse_bs_tab([]) == []
```

- [ ] **Step 7.3: Run tests (should fail)**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_parser.py::TestParseBsTab -v
```

Expected: 5 failures.

- [ ] **Step 7.4: Implement parse_bs_tab**

Replace `parse_bs_tab` body in `backend/services/hr/owner_cashout/parser.py`:

```python
def parse_bs_tab(rows: list[list[str]]) -> list[CashoutRow]:
    """Parse a BS weekly tab. Schema has 7 columns (no TOTAL INCOME / MARGIN BZ)."""
    out: list[CashoutRow] = []
    for i, row in enumerate(rows[2:], start=3):
        padded = (list(row) + [""] * 7)[:7]
        name = str(padded[0]).strip() if padded[0] else ""
        if not name:
            continue
        out.append(
            CashoutRow(
                entity="BS",
                row_index=i,
                client_name=name,
                process=(str(padded[1]).strip() or None),
                pnbp_idr=parse_idr(padded[2]),
                urgent_idr=parse_idr(padded[3]),
                rptka_imta_idr=parse_idr(padded[4]),
                total_income_idr=0,
                margin_bs_idr=parse_idr(padded[5]),
                margin_bz_idr=0,
                final_price_idr=parse_idr(padded[6]),
                note=None,
            )
        )
    return out
```

- [ ] **Step 7.5: Run all parser tests**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_parser.py -v
```

Expected: all tests pass (9 IDR + 9 BZ + 5 BS = 23 passed).

- [ ] **Step 7.6: Commit**

```bash
git add backend/services/hr/owner_cashout/parser.py backend/tests/services/hr/owner_cashout/
git commit -m "feat(hr): parse_bs_tab with BS-specific schema"
```

---

### Task 8: Sheet reader (Service Account)

**Files:**
- Create: `apps/backend-rag/backend/services/hr/owner_cashout/sheet_reader.py`

- [ ] **Step 8.1: Create sheet_reader.py**

Create `backend/services/hr/owner_cashout/sheet_reader.py`:

```python
"""Google Sheets reader for WEEKLY CASHOUT using Service Account.

Uses OWNER_CASHOUT_SA_JSON env var (raw JSON) OR OWNER_CASHOUT_SA_FILE (path).
Scope: spreadsheets.readonly — this service is read-only by design.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
ENV_JSON = "OWNER_CASHOUT_SA_JSON"
ENV_FILE = "OWNER_CASHOUT_SA_FILE"


class SheetReader:
    """Thin read-only wrapper around Google Sheets API v4."""

    def __init__(self) -> None:
        self._service: Any | None = None

    def _resolve_credentials_path(self) -> str:
        file_path = os.environ.get(ENV_FILE)
        if file_path and os.path.isfile(file_path):
            return file_path

        raw = os.environ.get(ENV_JSON)
        if not raw:
            raise RuntimeError(
                f"Missing service account credentials. Set {ENV_FILE} or {ENV_JSON}."
            )

        # Validate JSON
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"{ENV_JSON} is not valid JSON: {e}") from e

        if parsed.get("type") != "service_account":
            raise RuntimeError(f"{ENV_JSON} is not a service account key")

        # Write to temp file for google lib
        tf = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="owner_cashout_sa_"
        )
        tf.write(raw)
        tf.close()
        return tf.name

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        creds_path = self._resolve_credentials_path()
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES
        )
        self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        logger.info("[CASHOUT] Sheets service initialized (SA)")
        return self._service

    def list_tabs(self, spreadsheet_id: str) -> list[str]:
        """Return the titles of all tabs in the spreadsheet."""
        svc = self._get_service()
        meta = (
            svc.spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def read_range(self, spreadsheet_id: str, range_: str) -> list[list[str]]:
        """Read a range and return raw rows.

        Note: Google returns rows of variable length (trailing empties trimmed).
        Callers must pad rows before indexing.
        """
        svc = self._get_service()
        result = (
            svc.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_)
            .execute()
        )
        return result.get("values", [])
```

- [ ] **Step 8.2: Integration smoke test (real sheet)**

Run (uses the SA key already on disk — path from the spec):
```bash
OWNER_CASHOUT_SA_FILE="/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json" \
PYTHONPATH=. python -c "
from backend.services.hr.owner_cashout.sheet_reader import SheetReader
from backend.services.hr.owner_cashout.constants import SHEET_ID

r = SheetReader()
tabs = r.list_tabs(SHEET_ID)
print(f'Total tabs: {len(tabs)}')
assert 'BZ 22 AUG' in tabs
assert 'Sheet18' in tabs
print('list_tabs OK')

rows = r.read_range(SHEET_ID, 'BZ 22 AUG!A1:I10')
print(f'First 10 rows of BZ 22 AUG: {len(rows)} returned')
assert rows[1][0] == 'NAME'
print('read_range OK')
"
```

Expected: `Total tabs: 46`, `list_tabs OK`, `read_range OK`.

- [ ] **Step 8.3: Commit**

```bash
git add backend/services/hr/owner_cashout/sheet_reader.py
git commit -m "feat(hr): google sheets SA reader for owner cashout"
```

---

### Task 9: Telegram alert helper

**Files:**
- Create: `apps/backend-rag/backend/services/hr/owner_cashout/telegram_alert.py`

- [ ] **Step 9.1: Create telegram_alert.py**

Create `backend/services/hr/owner_cashout/telegram_alert.py`:

```python
"""Telegram alerts for owner cashout sync failures / anomalies.

Uses the same TELEGRAM_BOT_TOKEN env var as the rest of the project.
Chat ID is hardcoded to Zero's private chat (verified 2026-04-07).

Best-effort: never raises — we don't want alerting to break sync.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

OWNER_CHAT_ID = "1125336968"  # Zero's @zero0101010101010 chat w/ @Balizerobot
TG_TIMEOUT_S = 10.0


async def send_alert(message: str) -> None:
    """Send a Telegram message to owner chat. Never raises."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("[CASHOUT] TELEGRAM_BOT_TOKEN missing — skipping alert")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": OWNER_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=TG_TIMEOUT_S) as client:
            r = await client.post(url, json=payload)
            if r.status_code != 200:
                logger.warning(
                    "[CASHOUT] Telegram alert failed: %s %s",
                    r.status_code,
                    r.text[:200],
                )
    except Exception as e:
        logger.warning("[CASHOUT] Telegram alert exception: %s", e)
```

- [ ] **Step 9.2: Import check**

Run:
```bash
PYTHONPATH=. python -c "from backend.services.hr.owner_cashout.telegram_alert import send_alert; print('OK')"
```

Expected: `OK`

- [ ] **Step 9.3: Commit**

```bash
git add backend/services/hr/owner_cashout/telegram_alert.py
git commit -m "feat(hr): telegram alert helper for owner cashout sync"
```

---

### Task 10: Sync service — upsert_week

**Files:**
- Create: `apps/backend-rag/backend/services/hr/owner_cashout/sync_service.py`
- Create: `apps/backend-rag/backend/tests/services/hr/owner_cashout/test_sync_service.py`

- [ ] **Step 10.1: Write failing test for upsert_week**

Create `backend/tests/services/hr/owner_cashout/test_sync_service.py`:

```python
"""Tests for owner cashout sync service (upsert_week + run_sync)."""
from datetime import date

import asyncpg
import pytest

from backend.services.hr.owner_cashout.parser import CashoutRow
from backend.services.hr.owner_cashout.sync_service import upsert_week


@pytest.fixture
async def db_pool(monkeypatch):
    import os
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nuzantara_dev"
    )
    pool = await asyncpg.create_pool(url)
    # Clean slate for this test run
    async with pool.acquire() as c:
        await c.execute("DELETE FROM owner_weekly_cashout_rows")
        await c.execute("DELETE FROM owner_weekly_cashout_weeks")
    yield pool
    await pool.close()


def make_bz_row(name: str, margin_bz: int, total_income: int) -> CashoutRow:
    return CashoutRow(
        entity="BZ",
        row_index=3,
        client_name=name,
        process="C1",
        pnbp_idr=1_000_000,
        urgent_idr=0,
        rptka_imta_idr=0,
        total_income_idr=total_income,
        margin_bs_idr=600_000,
        margin_bz_idr=margin_bz,
        final_price_idr=0,
        note=None,
    )


def make_bs_row(name: str, margin_bs: int, final_price: int) -> CashoutRow:
    return CashoutRow(
        entity="BS",
        row_index=3,
        client_name=name,
        process="C1",
        pnbp_idr=1_000_000,
        urgent_idr=0,
        rptka_imta_idr=0,
        total_income_idr=0,
        margin_bs_idr=margin_bs,
        margin_bz_idr=0,
        final_price_idr=final_price,
        note=None,
    )


@pytest.mark.asyncio
async def test_upsert_week_inserts_week_and_rows(db_pool):
    rows_bz = [
        make_bz_row("CLIENT A", 1_000_000, 2_700_000),
        make_bz_row("CLIENT B", 1_100_000, 2_700_000),
    ]
    rows_bs = [make_bs_row("CLIENT A", 600_000, 1_600_000)]

    week_id = await upsert_week(
        db_pool,
        week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG",
        tab_bs="BS 22 AUG",
        rows=rows_bz + rows_bs,
    )

    async with db_pool.acquire() as c:
        week = await c.fetchrow(
            "SELECT * FROM owner_weekly_cashout_weeks WHERE id = $1", week_id
        )
        assert week["week_start"] == date(2025, 8, 22)
        assert week["tab_name_bz"] == "BZ 22 AUG"
        assert week["tab_name_bs"] == "BS 22 AUG"
        assert week["total_practices"] == 2  # 2 BZ clients
        assert week["total_income_idr"] == 5_400_000
        assert week["total_margin_bz_idr"] == 2_100_000
        assert week["total_margin_bs_idr"] == 600_000

        rows = await c.fetch(
            "SELECT entity, client_name FROM owner_weekly_cashout_rows WHERE week_id = $1 ORDER BY entity, client_name",
            week_id,
        )
        assert len(rows) == 3  # 2 BZ + 1 BS


@pytest.mark.asyncio
async def test_upsert_week_is_idempotent(db_pool):
    rows_bz = [make_bz_row("CLIENT A", 1_000_000, 2_700_000)]

    id1 = await upsert_week(
        db_pool, week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG", tab_bs="BS 22 AUG", rows=rows_bz,
    )
    id2 = await upsert_week(
        db_pool, week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG", tab_bs="BS 22 AUG", rows=rows_bz,
    )

    assert id1 == id2
    async with db_pool.acquire() as c:
        count = await c.fetchval(
            "SELECT COUNT(*) FROM owner_weekly_cashout_rows WHERE week_id = $1", id1
        )
        assert count == 1  # not duplicated


@pytest.mark.asyncio
async def test_upsert_week_replaces_rows_on_rerun(db_pool):
    # First run: 2 clients
    rows_first = [
        make_bz_row("CLIENT A", 1_000_000, 2_700_000),
        make_bz_row("CLIENT B", 1_100_000, 2_700_000),
    ]
    await upsert_week(
        db_pool, week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG", tab_bs=None, rows=rows_first,
    )

    # Second run: only 1 client (client B removed from sheet)
    rows_second = [make_bz_row("CLIENT A", 1_000_000, 2_700_000)]
    week_id = await upsert_week(
        db_pool, week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG", tab_bs=None, rows=rows_second,
    )

    async with db_pool.acquire() as c:
        names = [
            r["client_name"]
            for r in await c.fetch(
                "SELECT client_name FROM owner_weekly_cashout_rows WHERE week_id = $1",
                week_id,
            )
        ]
        assert names == ["CLIENT A"]

        week = await c.fetchrow(
            "SELECT total_practices, total_margin_bz_idr FROM owner_weekly_cashout_weeks WHERE id = $1",
            week_id,
        )
        assert week["total_practices"] == 1
        assert week["total_margin_bz_idr"] == 1_000_000
```

- [ ] **Step 10.2: Run test (should fail: sync_service not found)**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_sync_service.py -v
```

Expected: ImportError.

- [ ] **Step 10.3: Create sync_service.py with upsert_week**

Create `backend/services/hr/owner_cashout/sync_service.py`:

```python
"""Sync service for owner weekly cashout.

Reads the WEEKLY CASHOUT sheet, parses BZ/BS tabs, upserts to Postgres atomically
per week. Logs each run to owner_cashout_sync_log.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import asyncpg

from backend.services.hr.owner_cashout.constants import (
    JUNK_TABS,
    SHEET_ID,
    TAB_TO_WEEK,
)
from backend.services.hr.owner_cashout.parser import (
    CashoutRow,
    parse_bs_tab,
    parse_bz_tab,
)
from backend.services.hr.owner_cashout.sheet_reader import SheetReader
from backend.services.hr.owner_cashout.telegram_alert import send_alert

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    status: str                  # 'success' | 'partial' | 'failed'
    weeks_processed: int
    weeks_skipped: int
    rows_upserted: int
    unknown_tabs: list[str]
    error: str | None = None


async def upsert_week(
    pool: asyncpg.Pool,
    *,
    week_start: date,
    tab_bz: str | None,
    tab_bs: str | None,
    rows: list[CashoutRow],
) -> int:
    """Atomically replace a week's data. Returns week_id."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            week_id: int = await conn.fetchval(
                """
                INSERT INTO owner_weekly_cashout_weeks
                    (week_start, tab_name_bz, tab_name_bs, last_synced_at)
                VALUES ($1, $2, $3, now())
                ON CONFLICT (week_start) DO UPDATE SET
                    tab_name_bz = EXCLUDED.tab_name_bz,
                    tab_name_bs = EXCLUDED.tab_name_bs,
                    last_synced_at = now()
                RETURNING id
                """,
                week_start, tab_bz, tab_bs,
            )

            await conn.execute(
                "DELETE FROM owner_weekly_cashout_rows WHERE week_id = $1",
                week_id,
            )

            if rows:
                records = [
                    (
                        week_id, r.entity, r.row_index, r.client_name, r.process,
                        r.pnbp_idr, r.urgent_idr, r.rptka_imta_idr, r.total_income_idr,
                        r.margin_bs_idr, r.margin_bz_idr, r.final_price_idr, r.note,
                    )
                    for r in rows
                ]
                await conn.executemany(
                    """
                    INSERT INTO owner_weekly_cashout_rows
                        (week_id, entity, row_index, client_name, process,
                         pnbp_idr, urgent_idr, rptka_imta_idr, total_income_idr,
                         margin_bs_idr, margin_bz_idr, final_price_idr, note)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    """,
                    records,
                )

            await conn.execute(
                """
                UPDATE owner_weekly_cashout_weeks SET
                    total_practices = (
                        SELECT COUNT(*) FROM owner_weekly_cashout_rows
                        WHERE week_id = $1 AND entity = 'BZ'
                    ),
                    total_income_idr = COALESCE((
                        SELECT SUM(total_income_idr) FROM owner_weekly_cashout_rows
                        WHERE week_id = $1 AND entity = 'BZ'
                    ), 0),
                    total_margin_bz_idr = COALESCE((
                        SELECT SUM(margin_bz_idr) FROM owner_weekly_cashout_rows
                        WHERE week_id = $1 AND entity = 'BZ'
                    ), 0),
                    total_margin_bs_idr = COALESCE((
                        SELECT SUM(margin_bs_idr) FROM owner_weekly_cashout_rows
                        WHERE week_id = $1 AND entity = 'BS'
                    ), 0)
                WHERE id = $1
                """,
                week_id,
            )
            return week_id


async def run_sync(pool: asyncpg.Pool, *, triggered_by: str) -> SyncResult:
    raise NotImplementedError  # implemented in Task 11
```

- [ ] **Step 10.4: Run upsert_week tests (should pass)**

Prereq: local Postgres with migration 098 applied (Task 2).

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_sync_service.py -v -k "not run_sync"
```

Expected: 3 passed.

- [ ] **Step 10.5: Commit**

```bash
git add backend/services/hr/owner_cashout/sync_service.py backend/tests/services/hr/owner_cashout/test_sync_service.py
git commit -m "feat(hr): upsert_week atomic replace with recomputed totals"
```

---

### Task 11: Sync service — run_sync

**Files:**
- Modify: `apps/backend-rag/backend/services/hr/owner_cashout/sync_service.py`
- Modify: `apps/backend-rag/backend/tests/services/hr/owner_cashout/test_sync_service.py`

- [ ] **Step 11.1: Write failing tests for run_sync**

Append to `backend/tests/services/hr/owner_cashout/test_sync_service.py`:

```python
from unittest.mock import patch


class FakeReader:
    def __init__(self, tabs: dict[str, list[list[str]]]):
        self.tabs = tabs

    def list_tabs(self, sheet_id: str) -> list[str]:
        return list(self.tabs.keys())

    def read_range(self, sheet_id: str, range_: str) -> list[list[str]]:
        # range_ is like "BZ 22 AUG!A1:I200"
        tab = range_.split("!")[0]
        return self.tabs.get(tab, [])


@pytest.mark.asyncio
async def test_run_sync_happy_path(db_pool):
    from backend.services.hr.owner_cashout.sync_service import run_sync

    fake_tabs = {
        "BZ 22 AUG": [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "TOTAL INCOME", "MARGIN BS", "MARGIN BZ", "NOTE"],
            ["A BC", "C1", "Rp1,000,000", "", "", "Rp2,700,000", "Rp600,000", "Rp1,100,000"],
        ],
        "BS 22 AUG": [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "MARGIN BS", "FINAL PRICE"],
            ["A BC", "C1", "Rp1,000,000", "", "", "Rp600,000", "Rp1,600,000"],
        ],
        "Sheet18": [["junk"]],
    }

    with patch(
        "backend.services.hr.owner_cashout.sync_service.SheetReader",
        return_value=FakeReader(fake_tabs),
    ):
        result = await run_sync(db_pool, triggered_by="test")

    assert result.status == "success"
    assert result.weeks_processed == 1
    assert result.rows_upserted == 2
    assert result.unknown_tabs == []


@pytest.mark.asyncio
async def test_run_sync_unknown_tab_triggers_partial(db_pool):
    from backend.services.hr.owner_cashout.sync_service import run_sync

    fake_tabs = {
        "BZ 22 AUG": [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "TOTAL INCOME", "MARGIN BS", "MARGIN BZ", "NOTE"],
            ["A BC", "C1", "Rp1,000,000", "", "", "Rp2,700,000", "Rp600,000", "Rp1,100,000"],
        ],
        "BS 22 AUG": [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "MARGIN BS", "FINAL PRICE"],
            ["A BC", "C1", "Rp1,000,000", "", "", "Rp600,000", "Rp1,600,000"],
        ],
        "BZ 13 FEB 26": [  # unknown, not in TAB_TO_WEEK
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "TOTAL INCOME", "MARGIN BS", "MARGIN BZ", "NOTE"],
            ["X Y", "C1", "Rp1,000,000", "", "", "Rp2,700,000", "Rp600,000", "Rp1,100,000"],
        ],
    }

    with patch(
        "backend.services.hr.owner_cashout.sync_service.SheetReader",
        return_value=FakeReader(fake_tabs),
    ), patch(
        "backend.services.hr.owner_cashout.sync_service.send_alert",
    ) as mock_alert:
        result = await run_sync(db_pool, triggered_by="test")

    assert result.status == "partial"
    assert "BZ 13 FEB 26" in result.unknown_tabs
    assert result.weeks_skipped >= 1
    assert result.weeks_processed == 1
    mock_alert.assert_called_once()


@pytest.mark.asyncio
async def test_run_sync_writes_log_row(db_pool):
    from backend.services.hr.owner_cashout.sync_service import run_sync

    fake_tabs = {
        "BZ 22 AUG": [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "TOTAL INCOME", "MARGIN BS", "MARGIN BZ", "NOTE"],
            ["A BC", "C1", "Rp1,000,000", "", "", "Rp2,700,000", "Rp600,000", "Rp1,100,000"],
        ],
    }

    with patch(
        "backend.services.hr.owner_cashout.sync_service.SheetReader",
        return_value=FakeReader(fake_tabs),
    ):
        await run_sync(db_pool, triggered_by="manual:zero@balizero.com")

    async with db_pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT * FROM owner_cashout_sync_log ORDER BY started_at DESC LIMIT 1"
        )
        assert row["status"] in ("success", "partial")
        assert row["triggered_by"] == "manual:zero@balizero.com"
        assert row["finished_at"] is not None
```

- [ ] **Step 11.2: Run tests (should fail: NotImplementedError)**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_sync_service.py -v -k run_sync
```

Expected: 3 failures.

- [ ] **Step 11.3: Implement run_sync**

Replace `run_sync` stub in `backend/services/hr/owner_cashout/sync_service.py` with:

```python
async def _create_sync_log(
    pool: asyncpg.Pool, triggered_by: str
) -> int:
    async with pool.acquire() as c:
        return await c.fetchval(
            """
            INSERT INTO owner_cashout_sync_log (status, triggered_by)
            VALUES ('running', $1)
            RETURNING id
            """,
            triggered_by,
        )


async def _finalize_sync_log(
    pool: asyncpg.Pool,
    log_id: int,
    *,
    status: str,
    weeks_processed: int,
    weeks_skipped: int,
    rows_upserted: int,
    unknown_tabs: list[str],
    error: str | None,
) -> None:
    async with pool.acquire() as c:
        await c.execute(
            """
            UPDATE owner_cashout_sync_log SET
                finished_at = now(),
                status = $2,
                weeks_processed = $3,
                weeks_skipped = $4,
                rows_upserted = $5,
                unknown_tabs = $6,
                error = $7
            WHERE id = $1
            """,
            log_id,
            status,
            weeks_processed,
            weeks_skipped,
            rows_upserted,
            ",".join(unknown_tabs) if unknown_tabs else None,
            error,
        )


async def run_sync(pool: asyncpg.Pool, *, triggered_by: str) -> SyncResult:
    """Read sheet, parse all known tabs, upsert to DB, log result."""
    log_id = await _create_sync_log(pool, triggered_by)
    weeks_processed = 0
    weeks_skipped = 0
    rows_upserted = 0
    unknown_tabs: list[str] = []

    try:
        reader = SheetReader()
        all_tabs = reader.list_tabs(SHEET_ID)

        # Group tabs by week_start
        weeks: dict[date, dict[str, str]] = {}
        for tab in all_tabs:
            if tab in JUNK_TABS:
                continue
            if tab not in TAB_TO_WEEK:
                unknown_tabs.append(tab)
                weeks_skipped += 1
                continue
            week_start = TAB_TO_WEEK[tab]
            entry = weeks.setdefault(week_start, {})
            if tab.startswith("BZ"):
                entry["bz"] = tab
            elif tab.startswith("BS"):
                entry["bs"] = tab

        for week_start in sorted(weeks.keys()):
            entry = weeks[week_start]
            tab_bz = entry.get("bz")
            tab_bs = entry.get("bs")
            all_rows: list[CashoutRow] = []

            if tab_bz:
                raw = reader.read_range(SHEET_ID, f"{tab_bz}!A1:I200")
                all_rows.extend(parse_bz_tab(raw))
            if tab_bs:
                raw = reader.read_range(SHEET_ID, f"{tab_bs}!A1:G200")
                all_rows.extend(parse_bs_tab(raw))

            await upsert_week(
                pool,
                week_start=week_start,
                tab_bz=tab_bz,
                tab_bs=tab_bs,
                rows=all_rows,
            )
            weeks_processed += 1
            rows_upserted += len(all_rows)

        if unknown_tabs:
            status = "partial"
            msg = (
                "⚠️ *Owner Cashout sync*: tab sconosciute rilevate.\n"
                f"Tabs: `{', '.join(unknown_tabs)}`\n"
                "Aggiungi entry a `TAB_TO_WEEK` in "
                "`backend/services/hr/owner_cashout/constants.py` e rifai sync."
            )
            await send_alert(msg)
        else:
            status = "success"

        await _finalize_sync_log(
            pool, log_id,
            status=status,
            weeks_processed=weeks_processed,
            weeks_skipped=weeks_skipped,
            rows_upserted=rows_upserted,
            unknown_tabs=unknown_tabs,
            error=None,
        )
        return SyncResult(
            status=status,
            weeks_processed=weeks_processed,
            weeks_skipped=weeks_skipped,
            rows_upserted=rows_upserted,
            unknown_tabs=unknown_tabs,
        )

    except Exception as e:
        logger.exception("[CASHOUT] sync failed")
        await _finalize_sync_log(
            pool, log_id,
            status="failed",
            weeks_processed=weeks_processed,
            weeks_skipped=weeks_skipped,
            rows_upserted=rows_upserted,
            unknown_tabs=unknown_tabs,
            error=str(e)[:500],
        )
        await send_alert(
            f"❌ *Owner Cashout sync failed*\n```\n{str(e)[:400]}\n```"
        )
        return SyncResult(
            status="failed",
            weeks_processed=weeks_processed,
            weeks_skipped=weeks_skipped,
            rows_upserted=rows_upserted,
            unknown_tabs=unknown_tabs,
            error=str(e)[:500],
        )
```

- [ ] **Step 11.4: Run all sync_service tests**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_sync_service.py -v
```

Expected: 6 passed.

- [ ] **Step 11.5: Commit**

```bash
git add backend/services/hr/owner_cashout/sync_service.py backend/tests/services/hr/owner_cashout/test_sync_service.py
git commit -m "feat(hr): run_sync with unknown tab detection and sync log"
```

---

### Task 12: End-to-end sync against real sheet (one-off)

**Files:** none (verification only)

- [ ] **Step 12.1: Run sync against real sheet into dev DB**

Run:
```bash
OWNER_CASHOUT_SA_FILE="/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json" \
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.services.hr.owner_cashout.sync_service import run_sync

async def main():
    url = os.environ.get('DATABASE_URL') or 'postgresql://postgres:postgres@localhost:5432/nuzantara_dev'
    pool = await asyncpg.create_pool(url)
    result = await run_sync(pool, triggered_by='manual:zero@balizero.com')
    print(result)
    async with pool.acquire() as c:
        summary = await c.fetch('''
            SELECT week_start, total_practices, total_margin_bz_idr, total_margin_bs_idr
            FROM owner_weekly_cashout_weeks ORDER BY week_start
        ''')
        for r in summary:
            print(f\"  {r['week_start']}: {r['total_practices']} practices, \"
                  f\"MBZ={r['total_margin_bz_idr']:>12,} \"
                  f\"MBS={r['total_margin_bs_idr']:>12,}\")
    await pool.close()

asyncio.run(main())
"
```

Expected:
- `status='success'` or `'partial'` (if unknown tabs)
- ~22 weeks listed with non-zero totals
- If status=partial, note unknown tabs for future fix

- [ ] **Step 12.2: Sanity-check first week totals**

Run:
```bash
PYTHONPATH=. python -c "
import asyncio, asyncpg, os

async def main():
    url = os.environ.get('DATABASE_URL') or 'postgresql://postgres:postgres@localhost:5432/nuzantara_dev'
    pool = await asyncpg.create_pool(url)
    async with pool.acquire() as c:
        r = await c.fetchrow('''
            SELECT total_practices, total_income_idr, total_margin_bz_idr, total_margin_bs_idr
            FROM owner_weekly_cashout_weeks WHERE week_start = '2025-08-22'
        ''')
        print('BZ 22 AUG totals:', dict(r))
        sample = await c.fetch('''
            SELECT client_name, process, margin_bz_idr, margin_bs_idr
            FROM owner_weekly_cashout_rows
            WHERE week_id = (SELECT id FROM owner_weekly_cashout_weeks WHERE week_start = '2025-08-22')
              AND entity = 'BZ'
            ORDER BY row_index LIMIT 5
        ''')
        for s in sample:
            print(dict(s))
    await pool.close()

asyncio.run(main())
"
```

Expected: realistic numbers matching the sheet; clients like JULIANNA JANOSI, EVA MARIE CASTEL, etc.

No commit for this task (verification only).

---

### Task 13: Repository helpers for API

**Files:**
- Create: `apps/backend-rag/backend/services/hr/owner_cashout/repository.py`
- Create: `apps/backend-rag/backend/tests/services/hr/owner_cashout/test_repository.py`

- [ ] **Step 13.1: Write failing repository tests**

Create `backend/tests/services/hr/owner_cashout/test_repository.py`:

```python
"""Tests for owner cashout read-side repository."""
from datetime import date

import asyncpg
import pytest

from backend.services.hr.owner_cashout.parser import CashoutRow
from backend.services.hr.owner_cashout.repository import (
    get_overview,
    get_visa_types,
    get_week_details,
    list_weeks,
)
from backend.services.hr.owner_cashout.sync_service import upsert_week


@pytest.fixture
async def populated_pool():
    import os
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nuzantara_dev"
    )
    pool = await asyncpg.create_pool(url)
    async with pool.acquire() as c:
        await c.execute("DELETE FROM owner_weekly_cashout_rows")
        await c.execute("DELETE FROM owner_weekly_cashout_weeks")

    def bz(name, process, mbz, ti):
        return CashoutRow(
            entity="BZ", row_index=3, client_name=name, process=process,
            pnbp_idr=1_000_000, urgent_idr=0, rptka_imta_idr=0,
            total_income_idr=ti, margin_bs_idr=600_000, margin_bz_idr=mbz,
            final_price_idr=0, note=None,
        )

    def bs(name, mbs, fp):
        return CashoutRow(
            entity="BS", row_index=3, client_name=name, process="C1",
            pnbp_idr=1_000_000, urgent_idr=0, rptka_imta_idr=0,
            total_income_idr=0, margin_bs_idr=mbs, margin_bz_idr=0,
            final_price_idr=fp, note=None,
        )

    await upsert_week(
        pool, week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG", tab_bs="BS 22 AUG",
        rows=[
            bz("A", "C1", 1_100_000, 2_700_000),
            bz("B", "C1", 1_100_000, 2_700_000),
            bz("C", "D12 1 YEAR", 1_700_000, 7_500_000),
            bs("A", 600_000, 1_600_000),
        ],
    )
    await upsert_week(
        pool, week_start=date(2025, 8, 29),
        tab_bz="BZ 29 AUG", tab_bs="BS 29 AUG",
        rows=[
            bz("D", "C1", 1_100_000, 2_700_000),
            bz("E", "D12 1 YEAR", 1_700_000, 7_500_000),
        ],
    )

    yield pool
    await pool.close()


@pytest.mark.asyncio
async def test_get_overview_kpis(populated_pool):
    result = await get_overview(populated_pool)
    assert result["total_weeks"] == 2
    assert result["first_week"] == date(2025, 8, 22)
    assert result["last_week"] == date(2025, 8, 29)
    assert result["kpi"]["margin_bz_total_idr"] == 6_700_000  # 1.1+1.1+1.7+1.1+1.7 (all in millions)
    assert result["kpi"]["margin_bz_last_week_idr"] == 2_800_000  # D + E
    assert result["kpi"]["practices_total"] == 5
    assert result["kpi"]["practices_last_week"] == 2


@pytest.mark.asyncio
async def test_get_overview_trend_ordered(populated_pool):
    result = await get_overview(populated_pool)
    trend = result["trend"]
    assert len(trend) == 2
    assert trend[0]["week_start"] == date(2025, 8, 22)
    assert trend[1]["week_start"] == date(2025, 8, 29)


@pytest.mark.asyncio
async def test_list_weeks_returns_newest_first(populated_pool):
    weeks = await list_weeks(populated_pool)
    assert len(weeks) == 2
    assert weeks[0]["week_start"] == date(2025, 8, 29)
    assert weeks[1]["week_start"] == date(2025, 8, 22)


@pytest.mark.asyncio
async def test_get_week_details_drill_down(populated_pool):
    weeks = await list_weeks(populated_pool)
    first_week_id = weeks[1]["id"]  # 22 AUG
    detail = await get_week_details(populated_pool, first_week_id)
    assert detail["week"]["week_start"] == date(2025, 8, 22)
    assert len(detail["rows_bz"]) == 3
    assert len(detail["rows_bs"]) == 1
    subs = {s["process"]: s for s in detail["subtotals_by_process"]}
    assert "C1" in subs
    assert subs["C1"]["count"] == 2
    assert subs["C1"]["margin_bz_idr"] == 2_200_000
    assert subs["D12 1 YEAR"]["count"] == 1


@pytest.mark.asyncio
async def test_get_week_details_not_found(populated_pool):
    assert await get_week_details(populated_pool, 999_999) is None


@pytest.mark.asyncio
async def test_get_visa_types_top_ranked_by_margin(populated_pool):
    result = await get_visa_types(populated_pool)
    top = result["top"]
    # D12 1 YEAR: 1 * 1.7M + 1 * 1.7M = 3.4M (rank 1)
    # C1: 2 * 1.1M + 1 * 1.1M = 3.3M (rank 2)
    assert top[0]["process"] == "D12 1 YEAR"
    assert top[0]["margin_bz_total_idr"] == 3_400_000
    assert top[1]["process"] == "C1"
    assert top[1]["margin_bz_total_idr"] == 3_300_000
```

- [ ] **Step 13.2: Run tests (should fail)**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_repository.py -v
```

Expected: ImportError.

- [ ] **Step 13.3: Create repository.py**

Create `backend/services/hr/owner_cashout/repository.py`:

```python
"""Read-side repository for owner cashout API endpoints.

All functions return plain dicts suitable for JSON serialization.
"""
from __future__ import annotations

from typing import Any

import asyncpg


async def get_overview(pool: asyncpg.Pool) -> dict[str, Any]:
    async with pool.acquire() as c:
        meta = await c.fetchrow(
            """
            SELECT
                COUNT(*) AS total_weeks,
                MIN(week_start) AS first_week,
                MAX(week_start) AS last_week,
                COALESCE(SUM(total_margin_bz_idr), 0) AS mbz_total,
                COALESCE(SUM(total_margin_bs_idr), 0) AS mbs_total,
                COALESCE(SUM(total_practices), 0) AS practices_total
            FROM owner_weekly_cashout_weeks
            """
        )

        last_week_row = await c.fetchrow(
            """
            SELECT total_margin_bz_idr, total_practices
            FROM owner_weekly_cashout_weeks
            ORDER BY week_start DESC LIMIT 1
            """
        )

        trend_rows = await c.fetch(
            """
            SELECT week_start, total_margin_bz_idr AS margin_bz,
                   total_margin_bs_idr AS margin_bs, total_practices AS practices
            FROM owner_weekly_cashout_weeks
            ORDER BY week_start ASC
            """
        )

    return {
        "total_weeks": meta["total_weeks"],
        "first_week": meta["first_week"],
        "last_week": meta["last_week"],
        "kpi": {
            "margin_bz_total_idr": int(meta["mbz_total"]),
            "margin_bz_last_week_idr": int(last_week_row["total_margin_bz_idr"]) if last_week_row else 0,
            "margin_bs_total_idr": int(meta["mbs_total"]),
            "practices_total": int(meta["practices_total"]),
            "practices_last_week": int(last_week_row["total_practices"]) if last_week_row else 0,
        },
        "trend": [
            {
                "week_start": r["week_start"],
                "margin_bz": int(r["margin_bz"]),
                "margin_bs": int(r["margin_bs"]),
                "practices": int(r["practices"]),
            }
            for r in trend_rows
        ],
    }


async def list_weeks(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    async with pool.acquire() as c:
        rows = await c.fetch(
            """
            SELECT id, week_start, tab_name_bz, tab_name_bs, total_practices,
                   total_income_idr, total_margin_bz_idr, total_margin_bs_idr,
                   last_synced_at
            FROM owner_weekly_cashout_weeks
            ORDER BY week_start DESC
            """
        )
    return [dict(r) for r in rows]


async def get_week_details(
    pool: asyncpg.Pool, week_id: int
) -> dict[str, Any] | None:
    async with pool.acquire() as c:
        week = await c.fetchrow(
            """
            SELECT id, week_start, tab_name_bz, tab_name_bs, total_practices,
                   total_income_idr, total_margin_bz_idr, total_margin_bs_idr,
                   last_synced_at
            FROM owner_weekly_cashout_weeks WHERE id = $1
            """,
            week_id,
        )
        if not week:
            return None

        rows = await c.fetch(
            """
            SELECT entity, row_index, client_name, process, pnbp_idr, urgent_idr,
                   rptka_imta_idr, total_income_idr, margin_bs_idr, margin_bz_idr,
                   final_price_idr, note
            FROM owner_weekly_cashout_rows
            WHERE week_id = $1
            ORDER BY entity, row_index
            """,
            week_id,
        )

        subtotals = await c.fetch(
            """
            SELECT process, COUNT(*) AS count,
                   COALESCE(SUM(margin_bz_idr), 0) AS margin_bz_idr
            FROM owner_weekly_cashout_rows
            WHERE week_id = $1 AND entity = 'BZ' AND process IS NOT NULL
            GROUP BY process
            ORDER BY margin_bz_idr DESC
            """,
            week_id,
        )

    rows_bz = [dict(r) for r in rows if r["entity"] == "BZ"]
    rows_bs = [dict(r) for r in rows if r["entity"] == "BS"]

    return {
        "week": dict(week),
        "rows_bz": rows_bz,
        "rows_bs": rows_bs,
        "subtotals_by_process": [
            {
                "process": s["process"],
                "count": int(s["count"]),
                "margin_bz_idr": int(s["margin_bz_idr"]),
            }
            for s in subtotals
        ],
    }


async def get_visa_types(pool: asyncpg.Pool, *, limit: int = 10) -> dict[str, Any]:
    async with pool.acquire() as c:
        rows = await c.fetch(
            """
            SELECT process,
                   COUNT(*) AS count,
                   COALESCE(SUM(margin_bz_idr), 0) AS margin_bz_total
            FROM owner_weekly_cashout_rows
            WHERE entity = 'BZ' AND process IS NOT NULL
            GROUP BY process
            ORDER BY margin_bz_total DESC
            LIMIT $1
            """,
            limit,
        )
    return {
        "top": [
            {
                "process": r["process"],
                "count": int(r["count"]),
                "margin_bz_total_idr": int(r["margin_bz_total"]),
            }
            for r in rows
        ]
    }
```

- [ ] **Step 13.4: Run repository tests (should pass)**

Run:
```bash
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/test_repository.py -v
```

Expected: 6 passed.

- [ ] **Step 13.5: Commit**

```bash
git add backend/services/hr/owner_cashout/repository.py backend/tests/services/hr/owner_cashout/test_repository.py
git commit -m "feat(hr): owner cashout read repository (overview, weeks, drill-down, visa-types)"
```

---

### Task 14: API router

**Files:**
- Create: `apps/backend-rag/backend/app/routers/hr_owner_cashout.py`
- Create: `apps/backend-rag/backend/tests/app/routers/test_hr_owner_cashout.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`

- [ ] **Step 14.1: Create router**

Create `backend/app/routers/hr_owner_cashout.py`:

```python
"""Owner-only HR endpoints for weekly cashout.

All routes gated by require_owner. 403 for non-owner team members.
"""
from __future__ import annotations

import logging
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from backend.app.deps.database import get_database_pool
from backend.app.deps.owner import require_owner
from backend.services.hr.owner_cashout import repository, sync_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/hr/owner/cashout",
    tags=["hr-owner-cashout"],
)


@router.get("/overview")
async def get_overview(
    pool: asyncpg.Pool = Depends(get_database_pool),
    _user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    return await repository.get_overview(pool)


@router.get("/weeks")
async def list_weeks(
    pool: asyncpg.Pool = Depends(get_database_pool),
    _user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    return {"weeks": await repository.list_weeks(pool)}


@router.get("/weeks/{week_id}")
async def get_week(
    week_id: int,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    detail = await repository.get_week_details(pool, week_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Week not found")
    return detail


@router.get("/visa-types")
async def get_visa_types(
    pool: asyncpg.Pool = Depends(get_database_pool),
    _user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    return await repository.get_visa_types(pool)


@router.post("/sync", status_code=202)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    pool: asyncpg.Pool = Depends(get_database_pool),
    user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    email = user.get("email", "owner")

    async def _runner() -> None:
        try:
            await sync_service.run_sync(
                pool, triggered_by=f"manual:{email}"
            )
        except Exception:
            logger.exception("[CASHOUT] background sync failed")

    background_tasks.add_task(_runner)
    return {"status": "started"}


@router.get("/sync-status")
async def get_sync_status(
    pool: asyncpg.Pool = Depends(get_database_pool),
    _user: dict[str, Any] = Depends(require_owner),
) -> dict[str, Any]:
    async with pool.acquire() as c:
        row = await c.fetchrow(
            """
            SELECT id, started_at, finished_at, status, weeks_processed,
                   weeks_skipped, rows_upserted, unknown_tabs, error, triggered_by
            FROM owner_cashout_sync_log
            ORDER BY started_at DESC LIMIT 1
            """
        )
    return {"last_sync": dict(row) if row else None}
```

- [ ] **Step 14.2: Write router tests**

Create `backend/tests/app/routers/__init__.py` (if not exists) and `backend/tests/app/routers/test_hr_owner_cashout.py`:

```python
"""Integration tests for owner cashout router with auth gating."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.deps.auth import get_current_user
from backend.app.deps.database import get_database_pool
from backend.app.routers.hr_owner_cashout import router


def make_app(user_email: str) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def fake_user():
        return {"email": user_email, "role": "admin"}

    async def fake_pool():
        return AsyncMock()

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_database_pool] = fake_pool
    return app


@pytest.mark.asyncio
async def test_overview_denies_non_owner():
    app = make_app("asya@balizero.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/hr/owner/cashout/overview")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_overview_allows_owner():
    app = make_app("zero@balizero.com")
    fake_result = {
        "total_weeks": 22, "first_week": None, "last_week": None,
        "kpi": {"margin_bz_total_idr": 0, "margin_bz_last_week_idr": 0,
                "margin_bs_total_idr": 0, "practices_total": 0, "practices_last_week": 0},
        "trend": [],
    }
    with patch(
        "backend.services.hr.owner_cashout.repository.get_overview",
        new=AsyncMock(return_value=fake_result),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/hr/owner/cashout/overview")
    assert r.status_code == 200
    assert r.json()["total_weeks"] == 22


@pytest.mark.asyncio
async def test_overview_allows_alias_owner():
    app = make_app("antonellosiano@balizero.com")
    with patch(
        "backend.services.hr.owner_cashout.repository.get_overview",
        new=AsyncMock(return_value={"total_weeks": 0, "first_week": None,
                                    "last_week": None, "kpi": {}, "trend": []}),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/hr/owner/cashout/overview")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_weeks_list_gated():
    app = make_app("random@example.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/hr/owner/cashout/weeks")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_week_detail_404():
    app = make_app("zero@balizero.com")
    with patch(
        "backend.services.hr.owner_cashout.repository.get_week_details",
        new=AsyncMock(return_value=None),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/hr/owner/cashout/weeks/999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_sync_trigger_gated():
    app = make_app("adit@balizero.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/hr/owner/cashout/sync")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_sync_trigger_owner_returns_202():
    app = make_app("zero@balizero.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/hr/owner/cashout/sync")
    assert r.status_code == 202
    assert r.json()["status"] == "started"
```

- [ ] **Step 14.3: Run router tests**

Run:
```bash
PYTHONPATH=. pytest backend/tests/app/routers/test_hr_owner_cashout.py -v
```

Expected: 7 passed.

- [ ] **Step 14.4: Register router**

Find `backend/app/setup/router_registration.py`. Locate how other HR routers are registered (e.g. `from backend.app.routers import hr`). Add next to them:

```python
from backend.app.routers import hr_owner_cashout
```

And in the `register_routers(app)` function (where `app.include_router(hr.router)` appears), add:

```python
app.include_router(hr_owner_cashout.router)
```

- [ ] **Step 14.5: Verify router mounted in running app**

Run:
```bash
PYTHONPATH=. python -c "
from backend.app.setup.app_factory import create_app
app = create_app()
paths = [r.path for r in app.routes if hasattr(r, 'path')]
matches = [p for p in paths if '/hr/owner/cashout' in p]
print('Matched routes:', len(matches))
for p in matches:
    print(' ', p)
assert len(matches) == 6, f'expected 6, got {len(matches)}'
"
```

Expected: 6 routes printed (overview, weeks, weeks/{week_id}, visa-types, sync, sync-status).

- [ ] **Step 14.6: Import chain validation**

Run (per `CLAUDE.md` deploy checklist):
```bash
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

Expected: `OK`

- [ ] **Step 14.7: Commit**

```bash
git add backend/app/routers/hr_owner_cashout.py backend/app/setup/router_registration.py backend/tests/app/routers/test_hr_owner_cashout.py
git commit -m "feat(hr): owner cashout API router (6 endpoints, owner-gated)"
```

---

### Task 15: CLI entrypoint for cron

**Files:**
- Create: `apps/backend-rag/scripts/sync_owner_cashout.py`

- [ ] **Step 15.1: Create CLI script**

Create `apps/backend-rag/scripts/sync_owner_cashout.py`:

```python
"""CLI entrypoint for owner cashout sync (cron on Air).

Usage:
    PYTHONPATH=. python scripts/sync_owner_cashout.py [--triggered-by cron]

Env:
    DATABASE_URL                  — Postgres URL
    OWNER_CASHOUT_SA_FILE / _JSON — Service Account credentials
    TELEGRAM_BOT_TOKEN            — for failure alerts
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

import asyncpg

from backend.services.hr.owner_cashout.sync_service import run_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("sync_owner_cashout")


async def main(triggered_by: str) -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        logger.error("DATABASE_URL not set")
        return 2

    pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
    try:
        result = await run_sync(pool, triggered_by=triggered_by)
        logger.info(
            "sync done status=%s weeks=%d rows=%d unknown=%s",
            result.status,
            result.weeks_processed,
            result.rows_upserted,
            result.unknown_tabs,
        )
        return 0 if result.status == "success" else 1
    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--triggered-by", default="cron")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.triggered_by)))
```

- [ ] **Step 15.2: Smoke test locally**

Run:
```bash
OWNER_CASHOUT_SA_FILE="/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json" \
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/nuzantara_dev" \
PYTHONPATH=. python scripts/sync_owner_cashout.py --triggered-by manual:test
```

Expected: log line `sync done status=success weeks=22 rows=<n>` and exit code 0.

- [ ] **Step 15.3: Commit**

```bash
git add scripts/sync_owner_cashout.py
git commit -m "feat(hr): CLI entrypoint for owner cashout sync cron"
```

---

### Task 16: Frontend — types and API client

**Files:**
- Create: `apps/mouth/src/types/owner-cashout.ts`
- Create: `apps/mouth/src/lib/api/hr/owner-cashout.ts`
- Create: `apps/mouth/src/lib/auth/owner.ts`

- [ ] **Step 16.1: Create TS types**

Create `apps/mouth/src/types/owner-cashout.ts`:

```typescript
export interface OwnerCashoutKpi {
  margin_bz_total_idr: number;
  margin_bz_last_week_idr: number;
  margin_bs_total_idr: number;
  practices_total: number;
  practices_last_week: number;
}

export interface OwnerCashoutTrendPoint {
  week_start: string; // ISO date
  margin_bz: number;
  margin_bs: number;
  practices: number;
}

export interface OwnerCashoutOverview {
  total_weeks: number;
  first_week: string | null;
  last_week: string | null;
  kpi: OwnerCashoutKpi;
  trend: OwnerCashoutTrendPoint[];
}

export interface OwnerCashoutWeek {
  id: number;
  week_start: string;
  tab_name_bz: string | null;
  tab_name_bs: string | null;
  total_practices: number;
  total_income_idr: number;
  total_margin_bz_idr: number;
  total_margin_bs_idr: number;
  last_synced_at: string;
}

export interface OwnerCashoutRow {
  entity: "BZ" | "BS";
  row_index: number;
  client_name: string;
  process: string | null;
  pnbp_idr: number;
  urgent_idr: number;
  rptka_imta_idr: number;
  total_income_idr: number;
  margin_bs_idr: number;
  margin_bz_idr: number;
  final_price_idr: number;
  note: string | null;
}

export interface OwnerCashoutSubtotal {
  process: string;
  count: number;
  margin_bz_idr: number;
}

export interface OwnerCashoutWeekDetail {
  week: OwnerCashoutWeek;
  rows_bz: OwnerCashoutRow[];
  rows_bs: OwnerCashoutRow[];
  subtotals_by_process: OwnerCashoutSubtotal[];
}

export interface OwnerCashoutVisaType {
  process: string;
  count: number;
  margin_bz_total_idr: number;
}

export interface OwnerCashoutSyncLog {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: "running" | "success" | "partial" | "failed";
  weeks_processed: number;
  weeks_skipped: number;
  rows_upserted: number;
  unknown_tabs: string | null;
  error: string | null;
  triggered_by: string;
}
```

- [ ] **Step 16.2: Create auth helper**

Create `apps/mouth/src/lib/auth/owner.ts`:

```typescript
export const OWNER_EMAILS = new Set([
  "zero@balizero.com",
  "antonellosiano@balizero.com",
]);

export function isOwner(email: string | null | undefined): boolean {
  return !!email && OWNER_EMAILS.has(email);
}
```

- [ ] **Step 16.3: Create API client**

Find how existing HR API clients are structured by reading `apps/mouth/src/lib/api/hr/hr.ts` briefly — they use a shared fetch helper. Create `apps/mouth/src/lib/api/hr/owner-cashout.ts` following the same pattern:

```typescript
import type {
  OwnerCashoutOverview,
  OwnerCashoutVisaType,
  OwnerCashoutWeek,
  OwnerCashoutWeekDetail,
  OwnerCashoutSyncLog,
} from "@/types/owner-cashout";

const BASE = "/api/hr/owner/cashout";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function getOverview(): Promise<OwnerCashoutOverview> {
  return fetchJson<OwnerCashoutOverview>(`${BASE}/overview`);
}

export async function listWeeks(): Promise<{ weeks: OwnerCashoutWeek[] }> {
  return fetchJson<{ weeks: OwnerCashoutWeek[] }>(`${BASE}/weeks`);
}

export async function getWeekDetail(
  weekId: number
): Promise<OwnerCashoutWeekDetail> {
  return fetchJson<OwnerCashoutWeekDetail>(`${BASE}/weeks/${weekId}`);
}

export async function getVisaTypes(): Promise<{ top: OwnerCashoutVisaType[] }> {
  return fetchJson<{ top: OwnerCashoutVisaType[] }>(`${BASE}/visa-types`);
}

export async function triggerSync(): Promise<{ status: string }> {
  return fetchJson<{ status: string }>(`${BASE}/sync`, { method: "POST" });
}

export async function getSyncStatus(): Promise<{
  last_sync: OwnerCashoutSyncLog | null;
}> {
  return fetchJson<{ last_sync: OwnerCashoutSyncLog | null }>(
    `${BASE}/sync-status`
  );
}
```

- [ ] **Step 16.4: Verify types compile**

Run:
```bash
cd apps/mouth
npx tsc --noEmit src/types/owner-cashout.ts src/lib/auth/owner.ts src/lib/api/hr/owner-cashout.ts
```

Expected: no errors.

- [ ] **Step 16.5: Commit**

```bash
git add apps/mouth/src/types/owner-cashout.ts apps/mouth/src/lib/api/hr/owner-cashout.ts apps/mouth/src/lib/auth/owner.ts
git commit -m "feat(hr): frontend types and API client for owner cashout"
```

---

### Task 17: Overview page

**Files:**
- Create: `apps/mouth/src/components/hr/OwnerCashoutRefreshButton.tsx`
- Create: `apps/mouth/src/app/(workspace)/hr/owner-cashout/page.tsx`

- [ ] **Step 17.1: Create refresh button component**

Create `apps/mouth/src/components/hr/OwnerCashoutRefreshButton.tsx`:

```tsx
"use client";

import React, { useState } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import * as api from "@/lib/api/hr/owner-cashout";

interface Props {
  onRefreshed?: () => void;
}

export function OwnerCashoutRefreshButton({ onRefreshed }: Props) {
  const [busy, setBusy] = useState(false);

  const handleClick = async () => {
    setBusy(true);
    try {
      await api.triggerSync();
      toast.success("Sync started. Refresh in ~10s.");
      setTimeout(() => {
        onRefreshed?.();
        setBusy(false);
      }, 10000);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Sync failed");
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className="inline-flex items-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-100 rounded-lg border border-zinc-700 text-sm disabled:opacity-50"
    >
      <RefreshCw size={14} className={busy ? "animate-spin" : ""} />
      {busy ? "Syncing…" : "Refresh"}
    </button>
  );
}
```

- [ ] **Step 17.2: Create overview page**

Create `apps/mouth/src/app/(workspace)/hr/owner-cashout/page.tsx`:

```tsx
"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Banknote,
  ChevronRight,
  Lock,
  TrendingUp,
  Users as UsersIcon,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import * as api from "@/lib/api/hr/owner-cashout";
import type {
  OwnerCashoutOverview,
  OwnerCashoutVisaType,
  OwnerCashoutWeek,
} from "@/types/owner-cashout";
import { OwnerCashoutRefreshButton } from "@/components/hr/OwnerCashoutRefreshButton";

function formatIDR(v: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(v);
}

function formatShort(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

function KpiCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="text-xs text-zinc-400 mb-1">{label}</div>
      <div className="text-2xl font-bold text-zinc-100">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

export default function OwnerCashoutPage() {
  const [overview, setOverview] = useState<OwnerCashoutOverview | null>(null);
  const [weeks, setWeeks] = useState<OwnerCashoutWeek[]>([]);
  const [visa, setVisa] = useState<OwnerCashoutVisaType[]>([]);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, wk, vt, st] = await Promise.all([
        api.getOverview(),
        api.listWeeks(),
        api.getVisaTypes(),
        api.getSyncStatus(),
      ]);
      setOverview(ov);
      setWeeks(wk.weeks);
      setVisa(vt.top);
      setLastSync(
        st.last_sync
          ? `${st.last_sync.status} · ${new Date(st.last_sync.started_at).toLocaleString("en-GB")}`
          : "never"
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !overview) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-zinc-800 rounded w-64 animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 h-28 animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-800 rounded-xl p-6 text-red-400">
        <h2 className="font-semibold mb-2">Error</h2>
        <p>{error}</p>
      </div>
    );
  }

  if (!overview) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100 flex items-center gap-2">
            <Lock size={20} className="text-amber-400" />
            Owner Cashout
          </h1>
          <div className="text-xs text-zinc-500 mt-1">
            Last sync: {lastSync}
          </div>
        </div>
        <OwnerCashoutRefreshButton onRefreshed={load} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Margin BZ Total"
          value={formatIDR(overview.kpi.margin_bz_total_idr)}
          sub={`${overview.total_weeks} weeks`}
        />
        <KpiCard
          label="Margin BZ Last Week"
          value={formatIDR(overview.kpi.margin_bz_last_week_idr)}
          sub={`${overview.kpi.practices_last_week} practices`}
        />
        <KpiCard
          label="Margin BS Total"
          value={formatIDR(overview.kpi.margin_bs_total_idr)}
        />
        <KpiCard
          label="Total Practices"
          value={String(overview.kpi.practices_total)}
        />
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={16} className="text-emerald-400" />
          <h2 className="text-sm font-semibold text-zinc-200">
            Margin trend (weekly)
          </h2>
        </div>
        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer>
            <LineChart data={overview.trend}>
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
              <XAxis dataKey="week_start" stroke="#71717a" fontSize={11} />
              <YAxis
                stroke="#71717a"
                fontSize={11}
                tickFormatter={formatShort}
              />
              <Tooltip
                contentStyle={{
                  background: "#18181b",
                  border: "1px solid #27272a",
                }}
                formatter={(v: number) => formatIDR(v)}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="margin_bz"
                stroke="#34d399"
                name="Margin BZ"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="margin_bs"
                stroke="#fbbf24"
                name="Margin BS"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Banknote size={16} className="text-emerald-400" />
          <h2 className="text-sm font-semibold text-zinc-200">
            Top visa types by MBZ
          </h2>
        </div>
        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer>
            <BarChart data={visa} layout="vertical">
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
              <XAxis
                type="number"
                stroke="#71717a"
                fontSize={11}
                tickFormatter={formatShort}
              />
              <YAxis
                type="category"
                dataKey="process"
                stroke="#71717a"
                fontSize={11}
                width={130}
              />
              <Tooltip
                contentStyle={{
                  background: "#18181b",
                  border: "1px solid #27272a",
                }}
                formatter={(v: number) => formatIDR(v)}
              />
              <Bar dataKey="margin_bz_total_idr" fill="#34d399" name="MBZ" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="flex items-center gap-2 p-5 border-b border-zinc-800">
          <UsersIcon size={16} className="text-emerald-400" />
          <h2 className="text-sm font-semibold text-zinc-200">
            Weekly breakdown
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead className="text-xs text-zinc-500 uppercase border-b border-zinc-800">
            <tr>
              <th className="text-left px-4 py-3">Week</th>
              <th className="text-right px-4 py-3">Practices</th>
              <th className="text-right px-4 py-3">Total income</th>
              <th className="text-right px-4 py-3">Margin BZ</th>
              <th className="text-right px-4 py-3">Margin BS</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="text-zinc-300">
            {weeks.map((w) => (
              <tr
                key={w.id}
                className="border-b border-zinc-800 hover:bg-zinc-800/40"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/hr/owner-cashout/${w.id}`}
                    className="hover:text-emerald-400"
                  >
                    {new Date(w.week_start).toLocaleDateString("en-GB", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    })}
                  </Link>
                </td>
                <td className="text-right px-4 py-3">{w.total_practices}</td>
                <td className="text-right px-4 py-3">
                  {formatIDR(w.total_income_idr)}
                </td>
                <td className="text-right px-4 py-3 text-emerald-400">
                  {formatIDR(w.total_margin_bz_idr)}
                </td>
                <td className="text-right px-4 py-3 text-amber-400">
                  {formatIDR(w.total_margin_bs_idr)}
                </td>
                <td className="px-4 py-3 text-zinc-600">
                  <Link href={`/hr/owner-cashout/${w.id}`}>
                    <ChevronRight size={16} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 17.3: Type-check**

Run:
```bash
cd apps/mouth && npx tsc --noEmit
```

Expected: no new errors related to these files. (If pre-existing errors elsewhere, scroll up and verify none mention `owner-cashout`.)

- [ ] **Step 17.4: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/hr/owner-cashout/page.tsx apps/mouth/src/components/hr/OwnerCashoutRefreshButton.tsx
git commit -m "feat(hr): owner cashout overview page (kpi + trend + visa + weekly table)"
```

---

### Task 18: Drill-down page

**Files:**
- Create: `apps/mouth/src/app/(workspace)/hr/owner-cashout/[weekId]/page.tsx`

- [ ] **Step 18.1: Create drill-down page**

Create `apps/mouth/src/app/(workspace)/hr/owner-cashout/[weekId]/page.tsx`:

```tsx
"use client";

import React, { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";

import * as api from "@/lib/api/hr/owner-cashout";
import type {
  OwnerCashoutRow,
  OwnerCashoutWeekDetail,
} from "@/types/owner-cashout";

const SHEET_URL =
  "https://docs.google.com/spreadsheets/d/1OZzgvDLgf3yd9eUh5CyADjHCHLoXmE5nIRoJlut_jBE/edit";

function formatIDR(v: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(v);
}

function EntityTable({
  title,
  rows,
  showTotalIncome,
  showFinalPrice,
}: {
  title: string;
  rows: OwnerCashoutRow[];
  showTotalIncome: boolean;
  showFinalPrice: boolean;
}) {
  if (rows.length === 0) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      <h3 className="text-sm font-semibold text-zinc-200 p-5 border-b border-zinc-800">
        {title}
      </h3>
      <table className="w-full text-sm">
        <thead className="text-xs text-zinc-500 uppercase border-b border-zinc-800">
          <tr>
            <th className="text-left px-4 py-3">Client</th>
            <th className="text-left px-4 py-3">Visa</th>
            <th className="text-right px-4 py-3">PNBP</th>
            <th className="text-right px-4 py-3">Urgent</th>
            {showTotalIncome && (
              <th className="text-right px-4 py-3">Income</th>
            )}
            <th className="text-right px-4 py-3">MBS</th>
            <th className="text-right px-4 py-3">MBZ</th>
            {showFinalPrice && (
              <th className="text-right px-4 py-3">Final</th>
            )}
            <th className="text-left px-4 py-3">Note</th>
          </tr>
        </thead>
        <tbody className="text-zinc-300">
          {rows.map((r, idx) => (
            <tr
              key={`${r.entity}-${r.row_index}-${idx}`}
              className="border-b border-zinc-800 last:border-b-0"
            >
              <td className="px-4 py-2">{r.client_name}</td>
              <td className="px-4 py-2 text-zinc-400">{r.process || "—"}</td>
              <td className="text-right px-4 py-2">{formatIDR(r.pnbp_idr)}</td>
              <td className="text-right px-4 py-2">
                {r.urgent_idr > 0 ? formatIDR(r.urgent_idr) : "—"}
              </td>
              {showTotalIncome && (
                <td className="text-right px-4 py-2">
                  {formatIDR(r.total_income_idr)}
                </td>
              )}
              <td className="text-right px-4 py-2 text-amber-400">
                {formatIDR(r.margin_bs_idr)}
              </td>
              <td className="text-right px-4 py-2 text-emerald-400">
                {formatIDR(r.margin_bz_idr)}
              </td>
              {showFinalPrice && (
                <td className="text-right px-4 py-2">
                  {formatIDR(r.final_price_idr)}
                </td>
              )}
              <td className="px-4 py-2 text-xs text-zinc-500">
                {r.note || ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function OwnerCashoutWeekDetailPage({
  params,
}: {
  params: Promise<{ weekId: string }>;
}) {
  const { weekId } = use(params);
  const [detail, setDetail] = useState<OwnerCashoutWeekDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const d = await api.getWeekDetail(Number(weekId));
        if (mounted) setDetail(d);
      } catch (e) {
        if (mounted)
          setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [weekId]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-zinc-800 rounded w-80 animate-pulse" />
        <div className="h-64 bg-zinc-900 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="bg-red-900/20 border border-red-800 rounded-xl p-6 text-red-400">
        <Link
          href="/hr/owner-cashout"
          className="inline-flex items-center gap-2 text-sm mb-3"
        >
          <ArrowLeft size={14} /> Back
        </Link>
        <p>{error || "Week not found"}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <Link
            href="/hr/owner-cashout"
            className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-200 mb-2"
          >
            <ArrowLeft size={14} /> Back to Owner Cashout
          </Link>
          <h1 className="text-2xl font-bold text-zinc-100">
            Week of{" "}
            {new Date(detail.week.week_start).toLocaleDateString("en-GB", {
              day: "2-digit",
              month: "long",
              year: "numeric",
            })}
          </h1>
          <div className="text-xs text-zinc-500 mt-1">
            Tabs: {detail.week.tab_name_bz || "—"} /{" "}
            {detail.week.tab_name_bs || "—"}
          </div>
        </div>
        <a
          href={SHEET_URL}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-100 rounded-lg border border-zinc-700 text-sm"
        >
          <ExternalLink size={14} /> Open in Sheets
        </a>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="text-xs text-zinc-400">Practices</div>
          <div className="text-xl font-bold text-zinc-100">
            {detail.week.total_practices}
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="text-xs text-zinc-400">Total Income</div>
          <div className="text-xl font-bold text-zinc-100">
            {formatIDR(detail.week.total_income_idr)}
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="text-xs text-zinc-400">Margin BZ</div>
          <div className="text-xl font-bold text-emerald-400">
            {formatIDR(detail.week.total_margin_bz_idr)}
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="text-xs text-zinc-400">Margin BS</div>
          <div className="text-xl font-bold text-amber-400">
            {formatIDR(detail.week.total_margin_bs_idr)}
          </div>
        </div>
      </div>

      {detail.subtotals_by_process.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-200 mb-3">
            Subtotals by visa type
          </h2>
          <div className="flex flex-wrap gap-2">
            {detail.subtotals_by_process.map((s) => (
              <div
                key={s.process}
                className="px-3 py-2 bg-zinc-800 rounded-lg border border-zinc-700 text-xs"
              >
                <span className="text-zinc-400">{s.process}: </span>
                <span className="text-zinc-100">{s.count}</span>
                <span className="text-zinc-500"> · </span>
                <span className="text-emerald-400">
                  {formatIDR(s.margin_bz_idr)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <EntityTable
        title="Bali Zero"
        rows={detail.rows_bz}
        showTotalIncome={true}
        showFinalPrice={false}
      />
      <EntityTable
        title="Bali Services"
        rows={detail.rows_bs}
        showTotalIncome={false}
        showFinalPrice={true}
      />
    </div>
  );
}
```

- [ ] **Step 18.2: Type-check**

Run:
```bash
cd apps/mouth && npx tsc --noEmit
```

Expected: no new errors.

- [ ] **Step 18.3: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/hr/owner-cashout/\[weekId\]/page.tsx
git commit -m "feat(hr): owner cashout drill-down page with subtotals + entity tables"
```

---

### Task 19: Sidebar gating

**Files:**
- Modify: `apps/mouth/src/app/(workspace)/hr/layout.tsx`

- [ ] **Step 19.1: Modify hr/layout.tsx**

The existing layout uses `api.getProfile()` and an `adminOnly` flag in `allNavItems`. We add a parallel `ownerOnly` flag and check via `isOwner(user.email)`.

Edit `apps/mouth/src/app/(workspace)/hr/layout.tsx`:

**Change 1** — add imports. Find:
```typescript
import {
  Banknote,
  Gift,
  Calendar,
  Settings,
  LayoutDashboard,
  Users,
} from "lucide-react";
import { api } from "@/lib/api";
import { isHRAdmin } from "@/lib/hr/admin";
```

Replace with:
```typescript
import {
  Banknote,
  Gift,
  Calendar,
  Lock,
  Settings,
  LayoutDashboard,
  Users,
} from "lucide-react";
import { api } from "@/lib/api";
import { isHRAdmin } from "@/lib/hr/admin";
import { isOwner } from "@/lib/auth/owner";
```

**Change 2** — extend nav items with `ownerOnly`. Find:
```typescript
const allNavItems = [
  { href: "/hr", label: "Dashboard", icon: LayoutDashboard, adminOnly: false },
  { href: "/hr/employees", label: "Employees", icon: Users, adminOnly: true },
  { href: "/hr/bonuses", label: "Bonuses", icon: Gift, adminOnly: false },
  { href: "/hr/payroll", label: "Payroll", icon: Banknote, adminOnly: false },
  { href: "/hr/leave", label: "Leave", icon: Calendar, adminOnly: false },
  { href: "/hr/settings", label: "Settings", icon: Settings, adminOnly: true },
];
```

Replace with:
```typescript
type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  adminOnly: boolean;
  ownerOnly?: boolean;
};

const allNavItems: NavItem[] = [
  { href: "/hr", label: "Dashboard", icon: LayoutDashboard, adminOnly: false },
  { href: "/hr/employees", label: "Employees", icon: Users, adminOnly: true },
  { href: "/hr/bonuses", label: "Bonuses", icon: Gift, adminOnly: false },
  { href: "/hr/payroll", label: "Payroll", icon: Banknote, adminOnly: false },
  { href: "/hr/leave", label: "Leave", icon: Calendar, adminOnly: false },
  { href: "/hr/settings", label: "Settings", icon: Settings, adminOnly: true },
  { href: "/hr/owner-cashout", label: "Owner Cashout", icon: Lock, adminOnly: false, ownerOnly: true },
];
```

**Change 3** — track owner state and filter. Find:
```typescript
  const [isAdmin, setIsAdmin] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api
      .getProfile()
      .then((user) => {
        setIsAdmin(isHRAdmin(user));
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const navItems = loaded
    ? allNavItems.filter((item) => !item.adminOnly || isAdmin)
    : allNavItems.filter((item) => !item.adminOnly);
```

Replace with:
```typescript
  const [isAdmin, setIsAdmin] = useState(false);
  const [isOwnerUser, setIsOwnerUser] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api
      .getProfile()
      .then((user) => {
        setIsAdmin(isHRAdmin(user));
        setIsOwnerUser(isOwner(user?.email));
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const navItems = loaded
    ? allNavItems.filter((item) => {
        if (item.adminOnly && !isAdmin) return false;
        if (item.ownerOnly && !isOwnerUser) return false;
        return true;
      })
    : allNavItems.filter((item) => !item.adminOnly && !item.ownerOnly);
```

**Verified:** `UserProfile` (in `apps/mouth/src/types/index.ts:13`) has `email: string`, so `user.email` is the correct access path.

- [ ] **Step 19.3: Type-check and build**

Run:
```bash
cd apps/mouth && npx tsc --noEmit && pnpm build 2>&1 | tail -20
```

Expected: build succeeds, no type errors.

- [ ] **Step 19.4: Commit**

```bash
git add apps/mouth/src/app/\(workspace\)/hr/layout.tsx
git commit -m "feat(hr): owner-gated sidebar link for cashout section"
```

---

### Task 20: Backend full test run + deploy

**Files:** none (verification)

- [ ] **Step 20.1: Run full backend test suite for HR owner cashout**

Run:
```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/hr/owner_cashout/ backend/tests/app/deps/test_owner.py backend/tests/app/routers/test_hr_owner_cashout.py -v
```

Expected: all passed.

- [ ] **Step 20.2: Core pre-deploy tests**

Run (from CLAUDE.md §11):
```bash
python -c "from backend.app.dependencies import get_current_user, require_owner; print('OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q
```

Expected: `OK`, tests pass.

- [ ] **Step 20.3: Apply migration 098 to Fly Postgres**

Run:
```bash
fly ssh console -a nuzantara-rag -C "bash -c 'cd /app && PYTHONPATH=. python -c \"
import asyncio, os, asyncpg
from backend.migrations import migration_098_owner_weekly_cashout as m

async def main():
    pool = await asyncpg.create_pool(os.environ[\\\"DATABASE_URL\\\"])
    await m.up(pool)
    print(\\\"migration 098 applied\\\")
    await pool.close()

asyncio.run(main())
\"'"
```

Expected: `migration 098 applied`.

- [ ] **Step 20.4: Set SA secret on Fly**

Run:
```bash
fly secrets set \
  OWNER_CASHOUT_SA_JSON="$(cat /Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json)" \
  -a nuzantara-rag
```

Expected: secret staged, app restarts automatically.

- [ ] **Step 20.5: Deploy backend**

Run:
```bash
cd apps/backend-rag && fly deploy --strategy rolling --app nuzantara-rag
```

Expected: deploy succeeds.

- [ ] **Step 20.6: Trigger initial sync via API**

Run (requires a valid owner JWT — obtain via web login or existing session cookie):
```bash
# Alternative: run sync manually from the container
fly ssh console -a nuzantara-rag -C "bash -c 'cd /app && PYTHONPATH=. python scripts/sync_owner_cashout.py --triggered-by manual:deploy'"
```

Expected: log line `sync done status=success weeks=22 rows=<n>`.

- [ ] **Step 20.7: Verify via curl (after web login)**

After logging in to `kita.balizero.com` as owner, open browser devtools and copy the `nz_access_token` cookie. Then:
```bash
curl -s https://nuzantara-rag.fly.dev/api/hr/owner/cashout/overview \
  -H "Cookie: nz_access_token=<token>" | jq '.kpi, .total_weeks'
```

Expected: valid KPI JSON.

---

### Task 21: Frontend deploy + QA

**Files:** none (deploy + visual QA)

- [ ] **Step 21.1: Push frontend branch**

Run:
```bash
cd /Users/nuzantara/Desktop/nuzantara
git push -u origin feat/owner-weekly-cashout
```

Expected: Vercel auto-deploys preview.

- [ ] **Step 21.2: Open preview and verify owner-only visibility**

In browser:
1. Visit Vercel preview URL `https://kita-git-feat-owner-weekly-cashout-balizero.vercel.app` (actual URL from Vercel log)
2. Log in as `zero@balizero.com`
3. Navigate to `/hr` — confirm "Owner Cashout" appears in sidebar
4. Click — overview page loads, KPI cards populated, line chart renders, weekly table lists ~22 rows
5. Click first row → drill-down loads with clients, subtotals, "Open in Sheets" link
6. Click "Refresh" → toast "Sync started"; after 10s data reloads

- [ ] **Step 21.3: QA screenshots (per CLAUDE.md §10)**

Using `mcp__claude-in-chrome__*` tools, capture:
- Overview page full viewport
- Drill-down page full viewport

Verify:
- Colors follow zinc+emerald theme
- No broken layouts
- No console errors

- [ ] **Step 21.4: Confirm non-owner sees nothing**

In another browser/profile:
1. Log in as `asya@balizero.com` (or any non-owner)
2. Visit `/hr` — confirm "Owner Cashout" link is **not** in sidebar
3. Manually navigate to `/hr/owner-cashout` — confirm API returns 403 and page shows error

- [ ] **Step 21.5: Merge to main and deploy production**

Run:
```bash
gh pr create --title "feat(hr): owner weekly cashout" --body "$(cat <<'EOF'
## Summary
- Imports WEEKLY CASHOUT Google Sheet into private `kita.balizero.com/hr/owner-cashout` section
- Owner-only (zero@/antonellosiano@balizero.com), 403 for other admins
- Weekly cron on Air + manual refresh button
- 3 isolated Postgres tables, atomic upsert per week

## Test plan
- [x] All backend tests green
- [x] Migration 098 up/down tested
- [x] Real sheet sync end-to-end (22 weeks imported)
- [x] Preview deploy: owner sees, non-owner blocked (sidebar + API)
- [x] QA screenshots reviewed

Spec: docs/superpowers/specs/2026-04-07-owner-weekly-cashout-design.md
Plan: docs/superpowers/plans/2026-04-08-owner-weekly-cashout.md
EOF
)"
```

After merge, verify production `https://kita.balizero.com/hr/owner-cashout` same flow as preview.

---

### Task 22: Air cron setup

**Files:**
- Create: `infra/air/cron/owner_cashout.cron` (documentation)

- [ ] **Step 22.1: Document crontab entry**

Create `infra/air/cron/owner_cashout.cron`:

```
# Owner Weekly Cashout sync — Monday 09:00 WITA
# Required env: DATABASE_URL, OWNER_CASHOUT_SA_FILE (or _JSON), TELEGRAM_BOT_TOKEN
# Runs from ~/Desktop/projects/nuzantara repo on Air (venv, not .venv)

0 9 * * 1 cd ~/Desktop/projects/nuzantara/apps/backend-rag && \
    bash -c 'source venv/bin/activate && \
    export DATABASE_URL="$(cat ~/.nuzantara/database_url)" && \
    export OWNER_CASHOUT_SA_FILE="$HOME/.nuzantara/owner_cashout_sa.json" && \
    export TELEGRAM_BOT_TOKEN="$(cat ~/.nuzantara/telegram_bot_token)" && \
    PYTHONPATH=. python scripts/sync_owner_cashout.py --triggered-by cron' \
    >> ~/logs/owner_cashout_sync.log 2>&1
```

- [ ] **Step 22.2: Install on Air (manual SSH)**

On Air (via `ssh air`):

1. Copy SA key:
   ```bash
   scp /Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json \
       air:~/.nuzantara/owner_cashout_sa.json
   chmod 600 ~/.nuzantara/owner_cashout_sa.json
   ```

2. Create `~/.nuzantara/database_url` and `~/.nuzantara/telegram_bot_token` (file per secret, chmod 600).

3. Append cron entry:
   ```bash
   (crontab -l 2>/dev/null; cat ~/Desktop/projects/nuzantara/infra/air/cron/owner_cashout.cron) | crontab -
   crontab -l | grep owner_cashout
   ```

4. Manual test run:
   ```bash
   cd ~/Desktop/projects/nuzantara/apps/backend-rag && \
       bash -c 'source venv/bin/activate && \
       export DATABASE_URL="$(cat ~/.nuzantara/database_url)" && \
       export OWNER_CASHOUT_SA_FILE="$HOME/.nuzantara/owner_cashout_sa.json" && \
       export TELEGRAM_BOT_TOKEN="$(cat ~/.nuzantara/telegram_bot_token)" && \
       PYTHONPATH=. python scripts/sync_owner_cashout.py --triggered-by manual:air-test'
   ```

   Expected: `sync done status=success weeks=22 rows=<n>`

- [ ] **Step 22.3: Commit doc**

```bash
git add infra/air/cron/owner_cashout.cron
git commit -m "docs(infra): air crontab entry for owner cashout weekly sync"
```

- [ ] **Step 22.4: Force failure to test Telegram alert**

On Air, run with an invalid DATABASE_URL:
```bash
cd ~/Desktop/projects/nuzantara/apps/backend-rag && \
    bash -c 'source venv/bin/activate && \
    export DATABASE_URL="postgresql://invalid:invalid@localhost:9999/bogus" && \
    export OWNER_CASHOUT_SA_FILE="$HOME/.nuzantara/owner_cashout_sa.json" && \
    export TELEGRAM_BOT_TOKEN="$(cat ~/.nuzantara/telegram_bot_token)" && \
    PYTHONPATH=. python scripts/sync_owner_cashout.py --triggered-by manual:failure-test'
```

Expected: script exits non-zero, Telegram message received in chat 1125336968 with "Owner Cashout sync failed".

---

## Spec Coverage Check

| Spec requirement | Task(s) |
|---|---|
| SA auth (verified file path) | Task 8, 20.4, 22.2 |
| Owner privacy gate (2 emails) | Task 3, 14 |
| 3 Postgres tables | Task 2 |
| TAB_TO_WEEK lookup (22 weeks) | Task 4 |
| JUNK_TABS skip | Task 4 |
| parse_idr (Rp format, edge cases) | Task 5 |
| parse_bz_tab (9 cols, schema BZ) | Task 6 |
| parse_bs_tab (7 cols, schema BS) | Task 7 |
| Atomic upsert per week | Task 10 |
| Idempotent sync | Task 10, 11 |
| Unknown tab → alert + continue | Task 11, 22.4 |
| Telegram alerts (chat 1125336968) | Task 9, 22.4 |
| Sync log table writes | Task 11 |
| 6 API endpoints | Task 14 |
| Owner-only FastAPI gate | Task 14 |
| CLI entrypoint for cron | Task 15 |
| Weekly cron Mon 09:00 WITA | Task 22 |
| Overview page (KPI+trend+visa+table) | Task 17 |
| Drill-down page (entity tables + subtotals) | Task 18 |
| Manual refresh button | Task 17 (button), 14 (endpoint) |
| Open in Sheets link | Task 18 |
| Sidebar gating | Task 19 |
| No payload in logs | Enforced by: sync_service only logs counts (Task 11), router logs only errors (Task 14) |
| Frontend QA screenshots | Task 21.3 |
| Rollback: tables isolated | Task 2 (no FK), DOWN_SQL |

All requirements covered.
