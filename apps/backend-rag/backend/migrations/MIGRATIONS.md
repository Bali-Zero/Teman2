# Database Migrations Guide

## Overview

This directory contains **legacy** database migration scripts for NUZANTARA PRIME.
The live automated loader uses `backend/db/migrations_v2/*.sql` — not this directory.
Files here are applied manually or kept as historical reference.

---

## Migration System Architecture

### Two-tier system

| Tier | Directory | Loader | When used |
|------|-----------|--------|-----------|
| **V2 (active)** | `backend/db/migrations_v2/*.sql` | `MigrationManager.discover_migrations()` | Every deploy via `release_command` |
| **Legacy (manual)** | `backend/migrations/migration_*.py` | None (manual apply) | Historical / ad-hoc |

### V2 Components

1. **BaseMigration** (`backend/db/migration_base.py`): Base class for all migrations
   - Transaction management
   - Migration tracking in `_schema_versions`
   - SQL safety validation
   - `verify_apply` / `verify_rollback` hooks
   - **Rollback enforcement for post-2026-04-18 migrations** (see §Rollback Policy)

2. **MigrationManager** (`backend/db/migration_manager.py`): Centralized migration manager
   - Discovers `*.sql` in `migrations_v2/`
   - Advisory lock prevents concurrent runs
   - Legacy-DB detection (fake-applies migration 001 if tables exist)

3. **Migration CLI** (`backend/db/migrate.py`): Command-line tool

---

## File Naming Convention (ENFORCED from 2026-04-18)

### For new migrations in `migrations_v2/`

```
NNN_description.sql
```

- `NNN`: 3-digit zero-padded sequential number
- `description`: snake_case, no spaces
- Example: `112_client_tier_system.sql`

### For legacy `.py` files in this directory

```
migration_NNNx_description.py
```

- `NNN`: 3-digit zero-padded number
- `x`: optional letter suffix `a/b/c` when multiple migrations share the same number
- Example: `migration_080a_visa_oracle_sessions.py`

**Banned patterns (will fail `test_migration_contract.py`):**
- `migration_NNN.py` when another file with the same NNN exists (bare duplicates)
- Two files with identical `NNNx` prefix
- `.sql` files in this directory without a 3-digit number prefix

### Letter suffix ordering rule

When multiple migrations share the same number, use `a/b/c` in **chronological git-commit order**:
- `a` = oldest commit date
- `b` = next
- `c` = newest

---

## Rollback Policy (ENFORCED from 2026-04-18)

### Pre-cutoff legacy migrations (001–111)

Grandfathered — no rollback required. All stems are in `LEGACY_NO_ROLLBACK_WHITELIST`
in `backend/db/migration_base.py`.

### Post-cutoff migrations (> 111)

**Every new migration using `BaseMigration` MUST supply `rollback_sql`.**

```python
class Migration112ClientTierSystem(BaseMigration):
    def __init__(self):
        super().__init__(
            migration_number=112,
            sql_file="112_client_tier_system.sql",
            description="Add client tier column",
            rollback_sql="ALTER TABLE clients DROP COLUMN IF EXISTS tier;",
        )
```

**If the migration is truly irreversible** (data loss, schema normalization),
raise `MigrationIrreversibleError` in a rollback wrapper and document why:

```python
from backend.db.migration_base import MigrationIrreversibleError

# In custom rollback hook or in description:
# "This migration drops the deprecated legacy_data column.
#  Compensating recovery: restore from nightly Tigris backup."
```

The constructor raises `ValueError` if rollback_sql is omitted for post-cutoff migrations.
The CI contract test (`test_migration_contract.py`) also catches this via AST analysis.

---

## Usage (V2 Loader)

### Check Migration Status

```bash
cd apps/backend-rag && source venv/bin/activate
PYTHONPATH=. python -m backend.db.migrate status
```

### Dry Run (Preview)

```bash
PYTHONPATH=. python -m backend.db.migrate apply-all --dry-run
```

### Apply All Pending

```bash
PYTHONPATH=. python -m backend.db.migrate apply-all
```

---

## Creating New Migrations (V2 — the right way)

### Step 1: Create SQL file in `backend/db/migrations_v2/`

```sql
-- ================================================
-- Migration 112: Brief Description
-- Created: YYYY-MM-DD
-- Purpose: Detailed description
-- Rollback: ALTER TABLE ... (or "irreversible — see note")
-- Idempotency: YES
-- ================================================

BEGIN;

-- Your SQL here
-- Use IF NOT EXISTS for idempotency

COMMIT;
```

### Step 2: If using BaseMigration wrapper (optional for complex logic)

```python
from backend.db.migration_base import BaseMigration

class Migration112(BaseMigration):
    def __init__(self):
        super().__init__(
            migration_number=112,
            sql_file="112_description.sql",
            description="Human-readable description",
            rollback_sql="DROP TABLE IF EXISTS new_table;",  # REQUIRED
        )

    async def verify_apply(self, conn) -> bool:
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'new_table')"
        )
        return bool(result)

    async def verify_rollback(self, conn) -> bool:
        result = await conn.fetchval(
            "SELECT NOT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'new_table')"
        )
        return bool(result)
```

### Step 3: Test

```bash
PYTHONPATH=. pytest backend/tests/db/test_migration_contract.py -v
PYTHONPATH=. python -m backend.db.migrate apply-all --dry-run
```

---

## Legacy File Types (do NOT create new ones)

| Pattern | Count | Status |
|---------|-------|--------|
| `migration_*.py` | ~104 | Legacy manual-apply — DO NOT ADD |
| `apply_migration_*.py` | 16 | Legacy runner scripts — DO NOT ADD |
| `*.sql` (unnumbered) | 3 | Legacy bare SQL — DO NOT ADD |

These exist for historical reference. The V2 SQL loader is the single path forward.

---

## Migration Tracking

V2 migrations tracked in `_schema_versions` table:

```sql
CREATE TABLE _schema_versions (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) UNIQUE NOT NULL,
    migration_number INTEGER NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    checksum VARCHAR(64) NOT NULL,
    description TEXT,
    execution_time_ms INTEGER,
    rollback_sql TEXT,
    applied_by VARCHAR(255) DEFAULT 'system'
);
```

Legacy migrations tracked in `schema_migrations` (BaseMigration legacy).

---

## Production Deployment (Fly.io)

Migrations applied automatically on deploy:

```toml
# fly.toml
[deploy]
  release_command = "python -m backend.db.migrate apply-all"
```

**NEVER run migrations directly on prod without `--dry-run` first.**
**NEVER touch `alembic/env.py`** (separate Alembic system, off-limits per CLAUDE.md).

---

## Last Updated

2026-04-18 — Migration drift cleanup (Air A4 session)
- Renamed 16 duplicate files (groups 021, 080, 084, 085, 092, 098, 100)
- Added `MigrationIrreversibleError` + `LEGACY_NO_ROLLBACK_WHITELIST`
- Added `verify_apply` / `verify_rollback` hooks to `BaseMigration`
- Added rollback enforcement for post-cutoff migrations
- CI tests: `test_migration_base_rollback.py`, `test_migration_contract.py`
