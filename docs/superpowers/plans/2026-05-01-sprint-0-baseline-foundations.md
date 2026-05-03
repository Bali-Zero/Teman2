# Sprint 0 — Baseline Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data foundations (tier segmentation + outcome tracking migrations) that all subsequent Sprints (1-6) of the Era Post-Agentica injection require, before any Cell skill or Genoma sweep work begins.

**Architecture:** Two new SQL migrations in `apps/backend-rag/backend/db/migrations_v2/` (149_client_segments.sql + 150_renewal_alert_outcomes.sql), each idempotent with rollback marker, Squawk-lint clean. Backfill scripts run once post-migrate. No Python service code yet — that lives in Sprint 1+. Migrations are deployed via the existing `run-sql-v2-migrations-post-deploy` job in `.github/workflows/fly-deploy.yml`.

**Tech Stack:** PostgreSQL (Fly.io `nuzantara-postgres`), Python 3.11 + asyncpg, Squawk action for migration lint, pytest for verification.

**Reference spec:** `docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md` §3.4, §4 Sprint 0, §7.1 Sprint 0 metrics.

**Branch:** `feature/post-agentic-injection-2026-05-01` (parent: `main`)

**L2 Autonomous Operations applies:** commits/push/PR autonomous, deploy via `fly-deploy.yml` autonomous on green CI. No `fly ssh` needed for this plan (migrations are auto-applied post-deploy by existing workflow job).

---

## File Structure (created in this plan)

| File                                                                       | Responsibility                                                                                    |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `apps/backend-rag/backend/db/migrations_v2/149_client_segments.sql`        | Create `client_segments` table + indexes + initial backfill                                       |
| `apps/backend-rag/backend/db/migrations_v2/150_renewal_alert_outcomes.sql` | Create `renewal_alert_outcomes` table + FK + indexes + backfill                                   |
| `apps/backend-rag/scripts/compute_client_segments.py`                      | One-shot script: compute LTV + tier for all clients, populate `client_segments` (run post-deploy) |
| `apps/backend-rag/scripts/backfill_renewal_outcomes.py`                    | One-shot script: post-hoc inference of outcomes from historical `practices.status` transitions    |
| `apps/backend-rag/backend/tests/db/test_migration_149.py`                  | Verify table schema, indexes, idempotence                                                         |
| `apps/backend-rag/backend/tests/db/test_migration_150.py`                  | Verify table schema, FK, idempotence                                                              |
| `apps/backend-rag/backend/tests/scripts/test_compute_client_segments.py`   | Verify LTV computation logic on synthetic data                                                    |
| `apps/backend-rag/backend/tests/scripts/test_backfill_renewal_outcomes.py` | Verify post-hoc inference rules                                                                   |

**Out of scope for Sprint 0** (later sprints):

- `client_segments` weekly refresh cron — Sprint 1 (lives with Cell)
- `renewal_alert_outcomes` writes from Cell — Sprint 2-3
- Materialized view `renewal_baseline_2024_2026` — Sprint 4 (lives in Cell skill `measure_conversion`)

---

## Task 1: Branch state verification

**Files:**

- N/A (git verification only)

**Status (as of plan-patch 2026-05-01)**: branch `feature/post-agentic-injection-2026-05-01` already exists locally with 2 commits (design doc + plan), parented on `main` at `9bfc1a76c` (= origin/main). Plan execution starts on this branch.

- [ ] **Step 1: Verify currently on feature branch**

Run: `git branch --show-current`
Expected: `feature/post-agentic-injection-2026-05-01`

If output differs, run: `git checkout feature/post-agentic-injection-2026-05-01`

- [ ] **Step 2: Verify branch base is origin/main**

Run: `git log --oneline origin/main..HEAD`
Expected: 2 commits visible — `0a161fa7f` (spec) + `080978a5d` (plan).

If more or different commits appear, STOP and investigate before proceeding.

- [ ] **Step 3: Verify working tree is clean**

Run: `git status -s | grep -v '^?? research/'`
Expected: empty output (untracked `research/` dirs are unrelated and ignored).

- [ ] **Step 4: Push feature branch to origin (no PR yet)**

```bash
git push -u origin feature/post-agentic-injection-2026-05-01
```

Expected: branch created on GitHub with the 2 docs commits. PR opens after Task 6 once migration + script commits are added.

---

## Task 2: Migration 149 — `client_segments` table

**Files:**

- Create: `apps/backend-rag/backend/db/migrations_v2/149_client_segments.sql`
- Test: `apps/backend-rag/backend/tests/db/test_migration_149.py`

### Schema design

Table tracks LTV-based tier segmentation. Tier 1 = high-value (LTV ≥ $5000), Tier 2 = medium ($2000-4999), Tier 3 = low (<$2000). LTV = sum of `practices.total_invoiced_idr` for status='completed' practices, converted IDR→USD at static rate. (See Task 4 for full schema notes.)

- [ ] **Step 1: Write the failing test for migration file existence + schema**

Create `apps/backend-rag/backend/tests/db/test_migration_149.py`:

```python
"""Verify migration 149 creates client_segments with expected schema.

Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.4
Cicatrix: 2026-04-19-migration-runner — ROLLBACK marker mandatory.
Cicatrix: 2026-04-26-atlas-paywalled — Squawk lint applies at PR time.
"""
from pathlib import Path

import pytest

MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "db"
    / "migrations_v2"
    / "149_client_segments.sql"
)


def test_migration_file_exists():
    assert MIGRATION_FILE.exists(), f"Migration file missing: {MIGRATION_FILE}"


def test_migration_has_rollback_marker():
    """Cicatrix 2026-04-19 enforces -- === ROLLBACK === marker."""
    sql = MIGRATION_FILE.read_text()
    assert "-- === ROLLBACK ===" in sql, (
        "Migration must include -- === ROLLBACK === marker (cicatrix 2026-04-19)"
    )


def test_migration_creates_client_segments_table():
    sql = MIGRATION_FILE.read_text()
    assert "CREATE TABLE IF NOT EXISTS client_segments" in sql


def test_migration_has_required_columns():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    for col in ("client_id", "tier", "lifetime_value_usd", "computed_at"):
        assert col in forward_section, f"Column {col} missing in forward section"


def test_migration_has_tier_check_constraint():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CHECK (tier IN (1, 2, 3))" in forward_section or "tier BETWEEN 1 AND 3" in forward_section


def test_migration_has_client_id_fk():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "REFERENCES clients(id)" in forward_section


def test_migration_has_indexes():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE INDEX IF NOT EXISTS idx_client_segments_tier" in forward_section
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_client_segments_client" in forward_section


def test_rollback_drops_table():
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    assert "DROP TABLE IF EXISTS client_segments" in rollback_section
```

- [ ] **Step 2: Run tests, verify all 7 fail**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/db/test_migration_149.py -v`
Expected: 7 FAILED with `FileNotFoundError` or AssertionError

- [ ] **Step 3: Create migration file**

Create `apps/backend-rag/backend/db/migrations_v2/149_client_segments.sql`:

```sql
-- 149_client_segments.sql
--
-- Tier segmentation table for Era Post-Agentica vertical-slice renewals.
-- See: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.4
--
-- Tier 1 = high-value (LTV ≥ $5000), Tier 2 = medium ($2000-4999), Tier 3 = low (<$2000).
-- LTV computed as sum of invoiced amounts on completed practices, all-time.
-- Initial population done by scripts/compute_client_segments.py post-deploy.
-- Weekly refresh handled by Cell skill `measure_conversion` from Sprint 4 onward.

-- Squawk-clean: brand-new empty table, no concurrent-index-creation warning needed.
CREATE TABLE IF NOT EXISTS client_segments (
    client_id INTEGER PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
    tier SMALLINT NOT NULL CHECK (tier IN (1, 2, 3)),
    lifetime_value_usd NUMERIC(12, 2) NOT NULL DEFAULT 0,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_client_segments_tier
    ON client_segments(tier);

CREATE UNIQUE INDEX IF NOT EXISTS uq_client_segments_client
    ON client_segments(client_id);

CREATE INDEX IF NOT EXISTS idx_client_segments_computed_at
    ON client_segments(computed_at);

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_client_segments_computed_at;
DROP INDEX IF EXISTS uq_client_segments_client;
DROP INDEX IF EXISTS idx_client_segments_tier;
DROP TABLE IF EXISTS client_segments;
```

- [ ] **Step 4: Re-run tests, verify all pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/db/test_migration_149.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/db/migrations_v2/149_client_segments.sql \
        apps/backend-rag/backend/tests/db/test_migration_149.py
git commit -m "feat(db): add migration 149 — client_segments table for tier/LTV segmentation"
```

---

## Task 3: Migration 150 — `renewal_alert_outcomes` table

**Files:**

- Create: `apps/backend-rag/backend/db/migrations_v2/150_renewal_alert_outcomes.sql`
- Test: `apps/backend-rag/backend/tests/db/test_migration_150.py`

### Schema design

Tracks outcome of every `renewal_alerts` row (existing CRM table created in migration_007). Outcome enum: `acted_by_team` | `client_renewed` | `client_ignored` | `expired_no_action`. Observed by: `cell` (auto-tracked from event bus) | `team_member` (manual log). Foreign key to `renewal_alerts(id)`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/db/test_migration_150.py`:

```python
"""Verify migration 150 creates renewal_alert_outcomes with FK to renewal_alerts.

Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.4
"""
from pathlib import Path

import pytest

MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "db"
    / "migrations_v2"
    / "150_renewal_alert_outcomes.sql"
)


def test_migration_file_exists():
    assert MIGRATION_FILE.exists()


def test_migration_has_rollback_marker():
    sql = MIGRATION_FILE.read_text()
    assert "-- === ROLLBACK ===" in sql


def test_migration_creates_outcomes_table():
    sql = MIGRATION_FILE.read_text()
    assert "CREATE TABLE IF NOT EXISTS renewal_alert_outcomes" in sql


def test_migration_has_required_columns():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    for col in ("alert_id", "outcome", "outcome_at", "observed_by"):
        assert col in forward_section, f"Column {col} missing"


def test_migration_has_outcome_check_constraint():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    for outcome_value in (
        "acted_by_team",
        "client_renewed",
        "client_ignored",
        "expired_no_action",
    ):
        assert outcome_value in forward_section, f"Outcome {outcome_value} missing in CHECK"


def test_migration_has_observed_by_check():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "'cell'" in forward_section
    assert "'team_member'" in forward_section


def test_migration_has_alert_id_fk():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "REFERENCES renewal_alerts" in forward_section


def test_migration_has_alert_id_index():
    sql = MIGRATION_FILE.read_text()
    forward_section = sql.split("-- === ROLLBACK ===")[0]
    assert "CREATE INDEX IF NOT EXISTS idx_renewal_alert_outcomes_alert" in forward_section


def test_rollback_drops_table():
    sql = MIGRATION_FILE.read_text()
    rollback_section = sql.split("-- === ROLLBACK ===")[1]
    assert "DROP TABLE IF EXISTS renewal_alert_outcomes" in rollback_section
```

- [ ] **Step 2: Run tests, verify all 9 fail**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/db/test_migration_150.py -v`
Expected: 9 FAILED

- [ ] **Step 3: Create migration file**

Create `apps/backend-rag/backend/db/migrations_v2/150_renewal_alert_outcomes.sql`:

```sql
-- 150_renewal_alert_outcomes.sql
--
-- Outcome tracking for renewal_alerts (created in migration_007).
-- Captures whether an alert led to action: by team, client renewal, ignored, or expired.
-- See: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.4 + §7
--
-- Initial backfill: scripts/backfill_renewal_outcomes.py infers outcomes from
-- historical practices.status transitions and records observed_by='team_member'
-- for all backfilled rows. From Sprint 2 onward, Cell writes observed_by='cell'.

CREATE TABLE IF NOT EXISTS renewal_alert_outcomes (
    id BIGSERIAL PRIMARY KEY,
    alert_id INTEGER NOT NULL REFERENCES renewal_alerts(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL CHECK (outcome IN (
        'acted_by_team',
        'client_renewed',
        'client_ignored',
        'expired_no_action'
    )),
    outcome_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    observed_by TEXT NOT NULL CHECK (observed_by IN ('cell', 'team_member')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_renewal_alert_outcomes_alert
    ON renewal_alert_outcomes(alert_id);

CREATE INDEX IF NOT EXISTS idx_renewal_alert_outcomes_outcome
    ON renewal_alert_outcomes(outcome);

CREATE INDEX IF NOT EXISTS idx_renewal_alert_outcomes_outcome_at
    ON renewal_alert_outcomes(outcome_at);

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_renewal_alert_outcomes_outcome_at;
DROP INDEX IF EXISTS idx_renewal_alert_outcomes_outcome;
DROP INDEX IF EXISTS idx_renewal_alert_outcomes_alert;
DROP TABLE IF EXISTS renewal_alert_outcomes;
```

- [ ] **Step 4: Re-run tests, verify all pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/db/test_migration_150.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/db/migrations_v2/150_renewal_alert_outcomes.sql \
        apps/backend-rag/backend/tests/db/test_migration_150.py
git commit -m "feat(db): add migration 150 — renewal_alert_outcomes for outcome tracking"
```

---

## Task 4: LTV computation script — `compute_client_segments.py`

**Files:**

- Create: `apps/backend-rag/backend/tests/scripts/__init__.py` (NEW dir)
- Create: `apps/backend-rag/scripts/compute_client_segments.py`
- Test: `apps/backend-rag/backend/tests/scripts/test_compute_client_segments.py`

### Schema verified against real codebase (2026-05-01)

The real `practices` table has:

- `total_invoiced_idr NUMERIC(16,2)` — sum of all invoiced amounts in IDR (verified in `services/crm/partners/commission_engine.py:89`)
- `completed_at TIMESTAMPTZ` — set when `status` transitions to `completed` (same source)
- `status TEXT` — practice_state_machine values (`inquiry`, `waiting_documents`, `sending_invoice`, `on_process`, `completed`, `cancelled`)
- `payment_status TEXT` — `unpaid`, `paid`, `partial` (verified m075 trigger)
- `client_id INTEGER`

The `invoices` table is FK-linked to `practices` and stores `amount_idr NUMERIC` per invoice (verified in `services/invoicing/invoice_service.py`).

**Decision**: use `practices.total_invoiced_idr` as the canonical amount source (no per-invoice JOIN needed; the column is already pre-aggregated by triggers). All amounts are IDR — single-currency simplifies logic. Convert to USD via static rate at computation time only.

### Logic

For each client in `clients` table:

1. Sum `practices.total_invoiced_idr` for status='completed' practices
2. Convert IDR sum to USD via static rate `1 USD = 15500 IDR` (refreshed quarterly)
3. Determine tier: ≥$5000 → 1, $2000-4999 → 2, <$2000 → 3
4. UPSERT into `client_segments`

Conservative defaults: clients with no completed practices → tier 3, LTV $0.

**Defensive column check**: before running queries, the script verifies `practices.total_invoiced_idr` and `practices.completed_at` exist via `information_schema.columns`. If absent (schema drift), aborts with clear error rather than producing wrong data silently.

- [ ] **Step 1: Create test directory + **init**.py**

```bash
mkdir -p apps/backend-rag/backend/tests/scripts
```

Create `apps/backend-rag/backend/tests/scripts/__init__.py` (empty file):

```python

```

- [ ] **Step 2: Write the failing test for LTV/tier logic**

Create `apps/backend-rag/backend/tests/scripts/test_compute_client_segments.py`:

```python
"""Test LTV computation + tier assignment logic.

Tests synthetic in-memory data only. Real-DB integration test happens via
deploy verification (Task 7-8).

Schema reality (verified 2026-05-01 against repo code):
- practices.total_invoiced_idr NUMERIC(16,2)  — IDR only, single currency
- practices.completed_at TIMESTAMPTZ          — set on status='completed' transition
- practices.status TEXT                       — 'completed' | 'on_process' | etc.
"""
import pytest

# Import will fail until script exists — that's the point of TDD step 3
from scripts.compute_client_segments import compute_ltv_usd, assign_tier


class TestComputeLtvUsd:
    def test_completed_practice_idr_converts_to_usd(self):
        # 31,000,000 IDR @ 15500 IDR/USD = $2000
        practices = [{"total_invoiced_idr": 31_000_000, "status": "completed"}]
        assert compute_ltv_usd(practices) == pytest.approx(2000.0, rel=1e-3)

    def test_multiple_completed_practices_sum(self):
        # 31M + 15.5M = 46.5M IDR = $3000
        practices = [
            {"total_invoiced_idr": 31_000_000, "status": "completed"},
            {"total_invoiced_idr": 15_500_000, "status": "completed"},
        ]
        assert compute_ltv_usd(practices) == pytest.approx(3000.0, rel=1e-3)

    def test_only_completed_status_counts(self):
        practices = [
            {"total_invoiced_idr": 15_500_000, "status": "completed"},  # $1000
            {"total_invoiced_idr": 31_000_000, "status": "on_process"},  # not counted
            {"total_invoiced_idr": 46_500_000, "status": "cancelled"},  # not counted
            {"total_invoiced_idr": 15_500_000, "status": "sending_invoice"},  # not counted
        ]
        assert compute_ltv_usd(practices) == pytest.approx(1000.0, rel=1e-3)

    def test_no_practices_returns_zero(self):
        assert compute_ltv_usd([]) == 0.0

    def test_null_total_invoiced_idr_treated_as_zero(self):
        practices = [{"total_invoiced_idr": None, "status": "completed"}]
        assert compute_ltv_usd(practices) == 0.0

    def test_zero_total_invoiced_idr(self):
        practices = [{"total_invoiced_idr": 0, "status": "completed"}]
        assert compute_ltv_usd(practices) == 0.0


class TestAssignTier:
    def test_tier_1_at_5000(self):
        assert assign_tier(5000.0) == 1

    def test_tier_1_above_5000(self):
        assert assign_tier(7500.0) == 1

    def test_tier_2_at_2000(self):
        assert assign_tier(2000.0) == 2

    def test_tier_2_at_4999(self):
        assert assign_tier(4999.99) == 2

    def test_tier_3_below_2000(self):
        assert assign_tier(1999.99) == 3

    def test_tier_3_at_zero(self):
        assert assign_tier(0.0) == 3
```

- [ ] **Step 3: Run tests, verify all fail with ImportError**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/scripts/test_compute_client_segments.py -v`
Expected: FAILED with `ModuleNotFoundError: No module named 'scripts.compute_client_segments'`

- [ ] **Step 4: Create script**

Create `apps/backend-rag/scripts/compute_client_segments.py`:

```python
#!/usr/bin/env python3
"""Compute client_segments rows: LTV per client + tier assignment.

Run once post-deploy of migration 149. Idempotent: re-running updates rows.
From Sprint 4 onward, Cell skill `measure_conversion` will trigger weekly
re-computation; this script is the bootstrap.

Schema reality (verified 2026-05-01):
    practices.total_invoiced_idr NUMERIC  — pre-aggregated IDR amount
    practices.completed_at TIMESTAMPTZ    — completion timestamp
    practices.status TEXT                 — 'completed' | etc.

Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §4 Sprint 0.2

Usage:
    DATABASE_URL=postgres://... python scripts/compute_client_segments.py
    python scripts/compute_client_segments.py --dry-run  # preview only
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

import asyncpg

logger = logging.getLogger("compute_client_segments")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Static USD conversion. Refresh rate quarterly; design choice: simplicity > FX accuracy.
IDR_PER_USD: float = 15_500.0


def compute_ltv_usd(practices: list[dict[str, Any]]) -> float:
    """Sum completed practice IDR amounts converted to USD.

    Args:
        practices: list of dicts with keys total_invoiced_idr (numeric|None), status (str).

    Returns:
        Total LTV in USD; 0.0 if no completed practices or all amounts null/zero.
    """
    total_idr: float = 0.0
    for p in practices:
        if p.get("status") != "completed":
            continue
        amount = p.get("total_invoiced_idr")
        if amount is None:
            continue
        total_idr += float(amount)
    return total_idr / IDR_PER_USD if total_idr else 0.0


def assign_tier(ltv_usd: float) -> int:
    """Map LTV to tier 1/2/3.

    Tier 1: >= $5000 (high-value)
    Tier 2: $2000-4999 (medium)
    Tier 3: <$2000 (low) — also default for new/unknown clients.
    """
    if ltv_usd >= 5000:
        return 1
    if ltv_usd >= 2000:
        return 2
    return 3


async def verify_schema(conn: asyncpg.Connection) -> None:
    """Defensive check: required columns must exist before running queries.

    Aborts with clear error if schema drift renamed/removed required columns.
    """
    required = [
        ("practices", "total_invoiced_idr"),
        ("practices", "completed_at"),
        ("practices", "status"),
        ("practices", "client_id"),
        ("clients", "id"),
        ("clients", "deleted_at"),
        ("client_segments", "client_id"),  # Migration 149 must be applied first
    ]
    missing: list[str] = []
    for table, column in required:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = $1 AND column_name = $2
            )
            """,
            table,
            column,
        )
        if not exists:
            missing.append(f"{table}.{column}")
    if missing:
        raise RuntimeError(
            f"Schema verification failed. Missing columns: {missing}. "
            "Migration 149 may not be applied, or schema drift occurred. "
            "Aborting to avoid wrong data."
        )


async def compute_for_all_clients(
    conn: asyncpg.Connection, dry_run: bool = False,
) -> dict[str, int]:
    """Compute and upsert client_segments for every client. Returns counts per tier."""
    rows = await conn.fetch(
        """
        SELECT
            c.id AS client_id,
            COALESCE(json_agg(json_build_object(
                'total_invoiced_idr', p.total_invoiced_idr,
                'status', p.status
            )) FILTER (WHERE p.id IS NOT NULL), '[]'::json) AS practices_json
        FROM clients c
        LEFT JOIN practices p ON p.client_id = c.id
        WHERE c.deleted_at IS NULL
        GROUP BY c.id
        """,
    )

    counts: dict[str, int] = {"tier_1": 0, "tier_2": 0, "tier_3": 0, "total": 0}
    for row in rows:
        practices = list(row["practices_json"])
        ltv = compute_ltv_usd(practices)
        tier = assign_tier(ltv)
        counts[f"tier_{tier}"] += 1
        counts["total"] += 1

        if dry_run:
            continue

        await conn.execute(
            """
            INSERT INTO client_segments (client_id, tier, lifetime_value_usd, computed_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (client_id) DO UPDATE
                SET tier = EXCLUDED.tier,
                    lifetime_value_usd = EXCLUDED.lifetime_value_usd,
                    computed_at = EXCLUDED.computed_at
            """,
            row["client_id"],
            tier,
            ltv,
        )

    return counts


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return 1

    conn = await asyncpg.connect(db_url)
    try:
        await verify_schema(conn)
        counts = await compute_for_all_clients(conn, dry_run=args.dry_run)
        mode = "DRY-RUN" if args.dry_run else "WRITE"
        logger.info(
            f"[{mode}] processed {counts['total']} clients: "
            f"tier_1={counts['tier_1']}, tier_2={counts['tier_2']}, tier_3={counts['tier_3']}",
        )
        return 0
    except RuntimeError as exc:
        logger.error(str(exc))
        return 2
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 5: Re-run tests, verify all 12 pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/scripts/test_compute_client_segments.py -v`
Expected: 12 PASSED

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/scripts/compute_client_segments.py \
        apps/backend-rag/backend/tests/scripts/__init__.py \
        apps/backend-rag/backend/tests/scripts/test_compute_client_segments.py
git commit -m "feat(scripts): add compute_client_segments.py — LTV (IDR→USD) + tier assignment with schema verification"
```

---

## Task 5: Backfill outcome inference — `backfill_renewal_outcomes.py`

**Files:**

- Create: `apps/backend-rag/scripts/backfill_renewal_outcomes.py`
- Test: `apps/backend-rag/backend/tests/scripts/test_backfill_renewal_outcomes.py`

### Schema verified (2026-05-01)

- `practices.completed_at TIMESTAMPTZ` — exists (verified `services/crm/partners/commission_engine.py:89`)
- `practices.status TEXT` — exists
- `interactions.practice_id INTEGER` — exists, FK-linked to practices (verified `app/routers/crm_interactions.py:165`)
- `renewal_alerts` schema: `id, practice_id, client_id, alert_type, description, target_date, alert_date, notify_team_member, status, last_notified_at, created_at` (verified `services/misc/autonomous_scheduler.py:585`)

Same defensive `verify_schema()` pattern as Task 4.

### Inference rules

For each existing `renewal_alerts` row, infer outcome from `practices` history:

- If `practices.status = 'completed'` AND `practices.completed_at` ∈ [`alert_date`, `target_date + 30d`] → outcome = `client_renewed`
- If `practices.status` had any team interaction (interactions table has rows) AND no completion → `acted_by_team`
- If `target_date < NOW()` AND no completion AND no interaction → `expired_no_action`
- Else → `client_ignored`

All backfilled rows: `observed_by = 'team_member'`, `notes = 'backfill 2026-05'`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/scripts/test_backfill_renewal_outcomes.py`:

```python
"""Test post-hoc inference of renewal outcomes from historical state."""
from datetime import datetime, timedelta, timezone

import pytest

from scripts.backfill_renewal_outcomes import infer_outcome


def _alert(target_date_offset_days: int = 0) -> dict:
    """Helper: build a synthetic alert row with target_date offset from now."""
    now = datetime.now(tz=timezone.utc)
    return {
        "id": 1,
        "alert_date": now - timedelta(days=30),
        "target_date": now + timedelta(days=target_date_offset_days),
    }


class TestInferOutcome:
    def test_practice_completed_in_window_returns_client_renewed(self):
        alert = _alert(target_date_offset_days=10)
        practice = {
            "status": "completed",
            "completed_at": alert["alert_date"] + timedelta(days=15),
        }
        interactions_count = 2
        assert infer_outcome(alert, practice, interactions_count) == "client_renewed"

    def test_practice_not_completed_with_interactions_returns_acted_by_team(self):
        alert = _alert(target_date_offset_days=10)
        practice = {"status": "on_process", "completed_at": None}
        interactions_count = 5
        assert infer_outcome(alert, practice, interactions_count) == "acted_by_team"

    def test_expired_no_completion_no_interactions_returns_expired_no_action(self):
        alert = _alert(target_date_offset_days=-30)  # target was 30d ago
        practice = {"status": "on_process", "completed_at": None}
        interactions_count = 0
        assert infer_outcome(alert, practice, interactions_count) == "expired_no_action"

    def test_no_completion_no_interactions_not_expired_returns_client_ignored(self):
        alert = _alert(target_date_offset_days=10)  # future target
        practice = {"status": "on_process", "completed_at": None}
        interactions_count = 0
        assert infer_outcome(alert, practice, interactions_count) == "client_ignored"

    def test_completed_outside_window_returns_client_ignored(self):
        # Completed 200 days after alert — outside 30d post-target window
        alert = _alert(target_date_offset_days=10)
        practice = {
            "status": "completed",
            "completed_at": alert["target_date"] + timedelta(days=200),
        }
        interactions_count = 0
        assert infer_outcome(alert, practice, interactions_count) == "client_ignored"

    def test_completed_before_alert_returns_client_ignored(self):
        # Completed BEFORE alert was sent — alert was redundant
        alert = _alert(target_date_offset_days=10)
        practice = {
            "status": "completed",
            "completed_at": alert["alert_date"] - timedelta(days=5),
        }
        interactions_count = 0
        assert infer_outcome(alert, practice, interactions_count) == "client_ignored"
```

- [ ] **Step 2: Run tests, verify all fail with ImportError**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/scripts/test_backfill_renewal_outcomes.py -v`
Expected: FAILED with `ModuleNotFoundError`

- [ ] **Step 3: Create script**

Create `apps/backend-rag/scripts/backfill_renewal_outcomes.py`:

```python
#!/usr/bin/env python3
"""Backfill renewal_alert_outcomes from historical practices state.

One-shot script run after migration 150 deploys. Infers outcome for every
existing row in renewal_alerts based on practices.status transitions and
interactions count. Writes observed_by='team_member' for all rows
(notes='backfill 2026-05').

Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §4 Sprint 0.3

Usage:
    DATABASE_URL=postgres://... python scripts/backfill_renewal_outcomes.py
    python scripts/backfill_renewal_outcomes.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

logger = logging.getLogger("backfill_renewal_outcomes")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

POST_TARGET_WINDOW_DAYS = 30  # Completion within target_date + 30d counts as "renewed by alert"


def infer_outcome(
    alert: dict[str, Any], practice: dict[str, Any], interactions_count: int,
) -> str:
    """Apply inference rules to determine outcome for a backfill row.

    Rules:
        - practice completed within [alert_date, target_date + 30d] → 'client_renewed'
        - any interactions exist on the practice → 'acted_by_team'
        - target_date in past, no completion, no interactions → 'expired_no_action'
        - else → 'client_ignored'
    """
    now = datetime.now(tz=timezone.utc)
    alert_date = alert["alert_date"]
    target_date = alert["target_date"]

    if isinstance(target_date, datetime):
        target_dt = target_date if target_date.tzinfo else target_date.replace(tzinfo=timezone.utc)
    else:
        target_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)

    if isinstance(alert_date, datetime):
        alert_dt = alert_date if alert_date.tzinfo else alert_date.replace(tzinfo=timezone.utc)
    else:
        alert_dt = datetime.combine(alert_date, datetime.min.time(), tzinfo=timezone.utc)

    completed_at = practice.get("completed_at")
    if completed_at:
        completed_dt = (
            completed_at if completed_at.tzinfo else completed_at.replace(tzinfo=timezone.utc)
        )
        window_end = target_dt + timedelta(days=POST_TARGET_WINDOW_DAYS)
        if alert_dt <= completed_dt <= window_end:
            return "client_renewed"

    if interactions_count > 0:
        return "acted_by_team"

    if target_dt < now:
        return "expired_no_action"

    return "client_ignored"


async def backfill_all(conn: asyncpg.Connection, dry_run: bool = False) -> dict[str, int]:
    """Iterate all renewal_alerts, infer outcome, INSERT into renewal_alert_outcomes."""
    alerts = await conn.fetch(
        """
        SELECT
            ra.id,
            ra.alert_date,
            ra.target_date,
            ra.practice_id,
            p.status AS practice_status,
            p.completed_at,
            (SELECT COUNT(*) FROM interactions i WHERE i.practice_id = ra.practice_id) AS interactions_count
        FROM renewal_alerts ra
        LEFT JOIN practices p ON p.id = ra.practice_id
        WHERE NOT EXISTS (
            SELECT 1 FROM renewal_alert_outcomes rao WHERE rao.alert_id = ra.id
        )
        """,
    )

    counts: dict[str, int] = {
        "client_renewed": 0,
        "acted_by_team": 0,
        "client_ignored": 0,
        "expired_no_action": 0,
        "total": 0,
    }
    for a in alerts:
        practice = {
            "status": a["practice_status"],
            "completed_at": a["completed_at"],
        }
        outcome = infer_outcome(dict(a), practice, a["interactions_count"])
        counts[outcome] += 1
        counts["total"] += 1

        if dry_run:
            continue

        await conn.execute(
            """
            INSERT INTO renewal_alert_outcomes
                (alert_id, outcome, outcome_at, observed_by, notes)
            VALUES ($1, $2, NOW(), 'team_member', 'backfill 2026-05')
            """,
            a["id"],
            outcome,
        )

    return counts


async def verify_schema(conn: asyncpg.Connection) -> None:
    """Defensive check: required columns must exist before backfill."""
    required = [
        ("practices", "completed_at"),
        ("practices", "status"),
        ("renewal_alerts", "id"),
        ("renewal_alerts", "alert_date"),
        ("renewal_alerts", "target_date"),
        ("renewal_alerts", "practice_id"),
        ("interactions", "practice_id"),
        ("renewal_alert_outcomes", "alert_id"),  # Migration 150 must be applied
    ]
    missing: list[str] = []
    for table, column in required:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = $1 AND column_name = $2
            )
            """,
            table,
            column,
        )
        if not exists:
            missing.append(f"{table}.{column}")
    if missing:
        raise RuntimeError(
            f"Schema verification failed. Missing columns: {missing}. "
            "Migration 150 may not be applied. Aborting."
        )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return 1

    conn = await asyncpg.connect(db_url)
    try:
        await verify_schema(conn)
        counts = await backfill_all(conn, dry_run=args.dry_run)
        mode = "DRY-RUN" if args.dry_run else "WRITE"
        logger.info(
            f"[{mode}] backfilled {counts['total']} outcomes: "
            f"renewed={counts['client_renewed']}, acted={counts['acted_by_team']}, "
            f"ignored={counts['client_ignored']}, expired={counts['expired_no_action']}",
        )
        return 0
    except RuntimeError as exc:
        logger.error(str(exc))
        return 2
    finally:
        await conn.close()


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 4: Re-run tests, verify all 6 pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/scripts/test_backfill_renewal_outcomes.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/scripts/backfill_renewal_outcomes.py \
        apps/backend-rag/backend/tests/scripts/test_backfill_renewal_outcomes.py
git commit -m "feat(scripts): add backfill_renewal_outcomes.py — post-hoc outcome inference"
```

---

## Task 6: Open PR and verify Squawk lint passes

**Files:**

- N/A (PR operation only)

- [ ] **Step 1: Push branch with all 4 commits**

```bash
git push origin feature/post-agentic-injection-2026-05-01
```

Expected: 4 commits pushed (Task 1 push was empty branch; this delivers the 4 task commits).

- [ ] **Step 2: Open PR**

```bash
gh pr create --base main --title "feat(post-agentic): Sprint 0 — baseline foundations (migrations 149+150 + backfill scripts)" --body "$(cat <<'EOF'
## Summary

Sprint 0 of Era Post-Agentica injection (per design doc commit 0a161fa7f). Delivers data foundations needed by all subsequent sprints:

- **Migration 149**: `client_segments` table for LTV-based tier 1/2/3 segmentation
- **Migration 150**: `renewal_alert_outcomes` table for outcome tracking on existing `renewal_alerts`
- **Script**: `compute_client_segments.py` populates initial tiers (run post-deploy)
- **Script**: `backfill_renewal_outcomes.py` post-hoc infers outcomes from historical `practices.status` transitions

Both migrations include `-- === ROLLBACK ===` marker (cicatrix 2026-04-19) and pass Squawk lint (cicatrix 2026-04-26).

Spec: `docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md` §3.4, §4 Sprint 0.

## Test plan

- [x] Unit tests for migrations: 7 (149) + 9 (150) assertions on schema, FK, indexes, rollback
- [x] Unit tests for compute_client_segments: 11 cases (LTV math + tier boundaries)
- [x] Unit tests for backfill_renewal_outcomes: 6 cases (inference rules)
- [ ] Squawk lint passes on both migrations (CI check)
- [ ] Migration auto-applies via `run-sql-v2-migrations-post-deploy` job after merge

## Out of scope (later sprints)

- Weekly re-computation of `client_segments` (Sprint 4, lives with Cell)
- Cell skill writes to `renewal_alert_outcomes` (Sprint 2-3)
- Materialized view `renewal_baseline_2024_2026` (Sprint 4)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected output: PR URL, e.g. `https://github.com/Balizero1987/nuzantara/pull/XXX`

- [ ] **Step 3: Verify Squawk lint runs**

Run: `gh pr checks --watch`

Wait for the `migration-lint` job to complete. Expected: green check on Squawk.

If Squawk fails on a legitimate destructive op (it shouldn't here — these are pure CREATE TABLE), use `-- squawk-ignore: <rule>` per-statement. New empty tables should pass without ignores.

- [ ] **Step 4: Verify CI tests pass**

Run: `gh pr checks <PR_NUMBER>`

All checks should be green (or yellow if non-blocking). Squawk + tests are the must-pass.

---

## Task 7: Merge PR and verify post-deploy migrations apply

**Files:**

- N/A (deploy verification only)

- [ ] **Step 1: Merge PR (auto-merge on green CI)**

```bash
PR_NUM=$(gh pr list --head feature/post-agentic-injection-2026-05-01 --json number -q '.[0].number')
gh pr merge "$PR_NUM" --squash --auto
```

Expected: PR merges to main, fly-deploy.yml triggers automatically.

- [ ] **Step 2: Watch fly-deploy run**

```bash
RUN_ID=$(gh run list --workflow="fly-deploy.yml" --branch=main --limit=1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN_ID"
```

Expected: ~5-7 minutes total. Critical jobs:

- `pre-deploy-gate`: green
- `run-migrations`: green (applies migration 149+150 against OLD image — may show "skipping, not in pre-deploy filesystem" for these specific files, that's expected)
- `deploy`: green (rolling deploy)
- `run-sql-v2-migrations-post-deploy`: **green and shows `Applied: 30+ migrations` including 149 and 150** (cicatrix 2026-04-29 PR #336+339+340)

- [ ] **Step 3: Verify migrations applied on prod**

Run:

```bash
fly ssh console --app nuzantara-rag --machine $(fly machines list --app nuzantara-rag --json | jq -r '.[] | select(.config.metadata.fly_process_group=="api") | .id' | head -1) -C "psql \$DATABASE_URL -c \"SELECT migration_number, applied_at FROM schema_migrations WHERE migration_number IN (149, 150) ORDER BY migration_number;\""
```

Expected output:

```
 migration_number |          applied_at
------------------+-------------------------------
              149 | 2026-05-01 ...
              150 | 2026-05-01 ...
```

- [ ] **Step 4: Verify both tables exist with correct schema**

Run:

```bash
fly ssh console --app nuzantara-rag --machine <api-machine-id> -C "psql \$DATABASE_URL -c '\d client_segments'"
fly ssh console --app nuzantara-rag --machine <api-machine-id> -C "psql \$DATABASE_URL -c '\d renewal_alert_outcomes'"
```

Expected: schema dump matching the CREATE TABLE statements (columns, indexes, FK, CHECK constraints).

---

## Task 8: Run backfill scripts on prod

**Files:**

- N/A (one-shot data ops)

- [ ] **Step 1: Dry-run compute_client_segments on prod**

```bash
fly ssh console --app nuzantara-rag --machine <api-machine-id> -C "cd /app/apps/backend-rag && python scripts/compute_client_segments.py --dry-run"
```

Expected output: `[DRY-RUN] processed N clients: tier_1=X, tier_2=Y, tier_3=Z`

Verify: total ≥ 1000 (Bali Zero has 5000+ clients — expect most populated). If total < 100, abort and investigate.

- [ ] **Step 2: Real run compute_client_segments on prod**

```bash
fly ssh console --app nuzantara-rag --machine <api-machine-id> -C "cd /app/apps/backend-rag && python scripts/compute_client_segments.py"
```

Expected: `[WRITE] processed N clients: ...`

- [ ] **Step 3: Verify client_segments populated**

```bash
fly ssh console --app nuzantara-rag --machine <api-machine-id> -C "psql \$DATABASE_URL -c 'SELECT tier, COUNT(*), SUM(lifetime_value_usd) FROM client_segments GROUP BY tier ORDER BY tier;'"
```

Expected: 3 rows (one per tier), total count matches Sprint 0 success criteria from design doc §7.1: ≥ 1000 clients segmented.

- [ ] **Step 4: Dry-run backfill_renewal_outcomes**

```bash
fly ssh console --app nuzantara-rag --machine <api-machine-id> -C "cd /app/apps/backend-rag && python scripts/backfill_renewal_outcomes.py --dry-run"
```

Expected: `[DRY-RUN] backfilled N outcomes: renewed=A, acted=B, ignored=C, expired=D`

Sanity check: A+B+C+D == N. The renewed+acted ratio gives the **manual baseline conversion rate** for §7.2.1 of the spec.

- [ ] **Step 5: Real run backfill_renewal_outcomes**

```bash
fly ssh console --app nuzantara-rag --machine <api-machine-id> -C "cd /app/apps/backend-rag && python scripts/backfill_renewal_outcomes.py"
```

- [ ] **Step 6: Verify outcomes populated**

```bash
fly ssh console --app nuzantara-rag --machine <api-machine-id> -C "psql \$DATABASE_URL -c 'SELECT outcome, COUNT(*), MIN(outcome_at), MAX(outcome_at) FROM renewal_alert_outcomes GROUP BY outcome ORDER BY outcome;'"
```

Expected: 4 rows (one per outcome), all `observed_by='team_member'`, `notes='backfill 2026-05'`.

---

## Task 9: Send completion notification + update tracking

**Files:**

- Modify: `MEMORY.md` index (add Sprint 0 completion line if user policy)

- [ ] **Step 1: Send Telegram digest with Sprint 0 baseline metrics**

Run:

```bash
fly ssh console --app nuzantara-rag --machine <api-machine-id> -C "psql \$DATABASE_URL -c \"
SELECT
    'Tier 1: ' || COUNT(*) FILTER (WHERE tier=1) || ' clients, $' || COALESCE(SUM(lifetime_value_usd) FILTER (WHERE tier=1)::int, 0) || ' total LTV' AS line
FROM client_segments
UNION ALL
SELECT 'Tier 2: ' || COUNT(*) FILTER (WHERE tier=2) || ' clients' FROM client_segments
UNION ALL
SELECT 'Tier 3: ' || COUNT(*) FILTER (WHERE tier=3) || ' clients' FROM client_segments
UNION ALL
SELECT 'Outcomes: renewed=' || COUNT(*) FILTER (WHERE outcome='client_renewed') ||
       ', acted=' || COUNT(*) FILTER (WHERE outcome='acted_by_team') ||
       ', ignored=' || COUNT(*) FILTER (WHERE outcome='client_ignored') ||
       ', expired=' || COUNT(*) FILTER (WHERE outcome='expired_no_action')
FROM renewal_alert_outcomes;\""
```

Copy output and send via existing Telegram bot to chat 1125336968:

```bash
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
    -d "chat_id=1125336968" \
    -d "text=✅ Sprint 0 Era Post-Agentica complete

migrations 149+150 applied
client_segments populated
renewal_alert_outcomes backfilled

[paste output above]"
```

(Token env var: see CLAUDE.md §15 GitHub Secrets / Pro `~/.nuzantara-secrets.env`.)

- [ ] **Step 2: Update task list (manual MEMORY entry NOT auto)**

This Sprint 0 completion is a milestone — save as MOS memory:

```bash
~/.claude/scripts/mem save decision "Sprint 0 Era Post-Agentica complete 2026-05-01: migrations 149 (client_segments) + 150 (renewal_alert_outcomes) deployed; backfill scripts run on prod; baseline conversion rate computed from historical data" 9
```

- [ ] **Step 3: Branch cleanup**

```bash
git checkout main
git pull origin main
git branch -d feature/post-agentic-injection-2026-05-01  # delete local branch (PR was squash-merged)
git push origin --delete feature/post-agentic-injection-2026-05-01  # cleanup remote
```

---

## Verification: Sprint 0 success criteria (from spec §7.1)

After Task 9 completes, all must be true:

- [ ] `client_segments` table populated with ≥ 1000 rows (verified Task 8.3)
- [ ] `SELECT tier, COUNT(*) FROM client_segments GROUP BY tier;` returns coherent distribution (Task 8.3)
- [ ] `renewal_alert_outcomes` populated with backfilled rows (Task 8.6)
- [ ] All 4 outcome categories represented (Task 8.6)

If any criterion fails, do NOT proceed to Sprint 1. Investigate via `fly ssh` + Postgres console + relevant logs (`fly logs --app nuzantara-rag`).

---

## Open gates BEFORE Sprint 1 starts

The design doc §6 lists 3 gates requiring explicit Zero decision. Sprint 1 can proceed without these decisions, but Sprint 3 cannot. Surface them now to maximize lead time:

1. **§6.1 PII policy** — BLOCKING for Sprint 3. Confirm Consiglio v2 mono-LLM Ollama for PII decisions, or alternative.
2. **§6.2 Tier segmentation logic** — Sprint 0 used LTV-only. After Task 8.3 reveals distribution, Zero may want to revise (e.g., add anzianità, settore, geografia dimensions). If revision required: budget +2-3 days before Sprint 1 to re-run `compute_client_segments.py` with new logic.
3. **§6.3 Sandbox whitelist initial scope** — `[propose_outreach, draft_wa_message]` (proposal+draft, NO autonomous send) is the conservative default. Sprint 5 may relax. Confirm or adjust.

---

## Cicatrix safety checklist (verified during plan execution)

- [x] Migrations include `-- === ROLLBACK ===` marker (cicatrix 2026-04-19, Tasks 2 + 3)
- [x] Squawk lint passes on both migrations (cicatrix 2026-04-26, Task 6)
- [x] Post-deploy migration job validated via `fly_process_group="api"` (cicatrix 2026-04-29, Task 7.2)
- [x] No `PYTHONPATH=.` in `fly ssh` commands (cicatrix 2026-04-29 PR #340, Tasks 7.4, 8.1-8.5 — these use direct `python` invocation, not `python -m`)
- [x] PII redaction respected: scripts only access `clients` and `practices`, not free-text fields with potential NPWP/NIB (cicatrix 2026-04-21 Sentry PII)
- [x] WIP commits per task to avoid file-loss scar (cicatrix 2026-04-29 untracked-files-lost — every Task ends with explicit `git commit`)

---

**End of Sprint 0 plan.** Sprint 1 plan will be written after this completes successfully + Zero responds on §6.2 (if any tier revisions needed).
