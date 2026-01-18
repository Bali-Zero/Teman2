# Migration Scripts

This directory contains utility scripts for database operations that are **not** schema migrations.

## Structure

- **`migration_*.py`** - Schema migrations (in parent directory)
- **`apply_migration_*.py`** - Migration wrappers (in parent directory)
- **`scripts/`** - Utility scripts (this directory)

## Script Categories

### Seed Scripts

- `seed_*.py` - Data seeding scripts (visa types, practice types, etc.)
- Run manually when needed, not part of migration pipeline

### Update Scripts

- `update_*.py` - Data update scripts (visa type updates, etc.)
- Run manually for data corrections

### Utility Scripts

- `show_*.py` - Display/query scripts (visa summary, etc.)
- `fix_*.py` - One-time fixes
- `integrate_*.py` - Integration scripts

## Usage

These scripts should be run manually, not as part of the automatic migration pipeline.

Example:

```bash
cd apps/backend-rag
PYTHONPATH=. python -m backend.migrations.scripts.seed_visa_types
```

## Migration Pipeline

Only `migration_*.py` files in the parent directory are part of the automatic migration pipeline.
