# Database Migrations Guide

## Overview

This directory contains database migration scripts for NUZANTARA PRIME. Migrations are managed through a centralized system that tracks applied migrations and ensures they are executed in the correct order.

## Migration System Architecture

### Components

1. **BaseMigration** (`db/migration_base.py`): Base class for all migrations
   - Provides transaction management
   - Tracks applied migrations
   - Validates SQL safety
   - Handles errors with automatic rollback

2. **MigrationManager** (`db/migration_manager.py`): Centralized migration manager
   - Discovers all migrations
   - Tracks applied migrations
   - Applies migrations in order
   - Checks dependencies

3. **Migration CLI** (`db/migrate.py`): Command-line tool for managing migrations

## Migration Files

### Structure

- **SQL Files**: `db/migrations/*.sql` - SQL migration scripts
- **Python Scripts**: `migrations/migration_*.py` - Python migration wrappers

### Naming Convention

- SQL files: `NNN_description.sql` (e.g., `007_crm_system_schema.sql`)
- Python scripts: `migration_NNN.py` (e.g., `migration_007.py`)

## Migration Order and Dependencies

### Current Migrations

| Number | File | Description | Dependencies |
|--------|------|-------------|--------------|
| 001 | `001_fix_missing_tables.sql` | Create cultural_knowledge, query_clusters tables | None |
| 007 | `007_crm_system_schema.sql` | Create CRM system tables | None |
| 010 | `010_fix_team_members_schema.sql` | Fix team_members schema alignment | 007 |
| 012 | `012_fix_production_schema.sql` | Add conversation_id to interactions | 007 |
| 013 | `013_agentic_rag_tables.sql` | Create Agentic RAG tables | None |
| 014 | `014_knowledge_graph_tables.sql` | Create Knowledge Graph tables | None |
| 015 | `015_add_drive_columns.sql` | Add Drive columns to parent_documents | 013 |
| 016 | `016_add_summary_to_parent_docs.sql` | Add summary to parent_documents | 013 |

### Dependency Graph

```
001 (no deps)
007 (no deps)
  ├─> 010
  └─> 012
013 (no deps)
  ├─> 015
  └─> 016
014 (no deps)
```

## Usage

### Check Migration Status

```bash
python -m db.migrate status
```

### List All Migrations

```bash
python -m db.migrate list
```

### Apply All Pending Migrations

```bash
python -m db.migrate apply-all
```

### Dry Run (Preview)

```bash
python -m db.migrate apply-all --dry-run
```

### Apply Specific Migration

```bash
python migrations/migration_007.py
```

### Show Migration Info

```bash
python -m db.migrate info 7
```

## Creating New Migrations

### Step 1: Create SQL File

Create a new SQL file in `db/migrations/`:

```sql
-- ================================================
-- Migration NNN: Brief Description
-- Created: YYYY-MM-DD
-- Purpose: Detailed description
-- Idempotency: YES/NO
-- Dependencies: [List migration numbers if any]
-- ================================================

BEGIN;

-- Your SQL here
-- Use IF NOT EXISTS for idempotency

COMMIT;
```

### Step 2: Create Python Wrapper

Create `migrations/migration_NNN.py`:

```python
#!/usr/bin/env python3
"""
Migration NNN: Brief Description
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.migration_base import BaseMigration
import asyncpg


class MigrationNNN(BaseMigration):
    """Brief Description"""

    def __init__(self):
        super().__init__(
            migration_number=NNN,
            sql_file="NNN_description.sql",
            description="Detailed description",
            dependencies=[7]  # Optional: list dependencies
        )

    async def verify(self, conn: asyncpg.Connection) -> bool:
        """Verify migration was applied correctly"""
        # Add verification logic
        return True


async def main():
    migration = MigrationNNN()
    success = await migration.apply()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
```

### Step 3: Test Migration

```bash
# Test locally
python migrations/migration_NNN.py

# Verify status
python -m db.migrate status
```

## Migration Best Practices

### 1. Idempotency

Always make migrations idempotent (safe to run multiple times):

```sql
-- ✅ GOOD: Idempotent
CREATE TABLE IF NOT EXISTS users (...);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ❌ BAD: Not idempotent
CREATE TABLE users (...);
CREATE INDEX idx_users_email ON users(email);
```

### 2. Transactions

Always wrap migrations in transactions:

```sql
BEGIN;
-- Migration SQL
COMMIT;
```

### 3. Dependencies

Declare dependencies explicitly:

```python
dependencies=[7, 10]  # Must apply migrations 7 and 10 first
```

### 4. Verification

Always implement verification:

```python
async def verify(self, conn: asyncpg.Connection) -> bool:
    """Verify migration was applied correctly"""
    result = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'new_table'
        )
    """)
    return bool(result)
```

### 5. SQL Safety

Never include dangerous operations:

- ❌ `DROP DATABASE`
- ❌ `DROP SCHEMA`
- ❌ `TRUNCATE` (unless explicitly needed and documented)

### 6. Error Handling

Migrations automatically handle errors with rollback. If you need custom error handling:

```python
try:
    await migration.apply()
except MigrationError as e:
    logger.error(f"Migration failed: {e}")
    # Handle error
```

## Troubleshooting

### Migration Already Applied

If a migration shows as "already applied" but you need to re-run it:

1. Check `schema_migrations` table:
```sql
SELECT * FROM schema_migrations WHERE migration_name = '007_crm_system_schema';
```

2. If needed, remove the entry (use with caution):
```sql
DELETE FROM schema_migrations WHERE migration_name = '007_crm_system_schema';
```

### Migration Failed

1. Check logs for error details
2. Verify database connection
3. Check dependencies are applied
4. Verify SQL syntax

### Dependency Error

If you get "depends on migration X, but X has not been applied":

1. Check migration status: `python -m db.migrate status`
2. Apply missing dependencies first
3. Verify dependency numbers are correct

## Migration Tracking

Migrations are tracked in the `schema_migrations` table:

```sql
CREATE TABLE schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) UNIQUE NOT NULL,
    migration_number INTEGER NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    checksum VARCHAR(64) NOT NULL,
    description TEXT,
    execution_time_ms INTEGER
);
```

## Rollback

Rollback is not automatically supported. To rollback:

1. Create a new migration that reverses the changes
2. Or manually modify the database and remove the migration entry

## Production Deployment

### Fly.io

Migrations are applied automatically during deployment via release commands in `fly.toml`:

```toml
[deploy]
  release_command = "python -m db.migrate apply-all"
```

### Manual Application

```bash
# SSH into Fly.io instance
fly ssh console --app nuzantara-rag

# Apply migrations
python -m db.migrate apply-all
```

## Testing Migrations

Run migration tests:

```bash
pytest tests/test_migrations.py -v
```

## Support

For issues or questions:
1. Check migration logs
2. Review `docs/CLEANUP_REPORT_MIGRATIONS.md`
3. Contact DevOps team


















