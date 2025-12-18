# Migrations Directory

## ⚠️ DEPRECATED: Legacy Migration Scripts

This directory contains **legacy migration scripts** that are being phased out in favor of the new centralized migration system.

## New Migration System

**Use the new system instead:**

- **Migration CLI**: `python -m db.migrate`
- **Base Classes**: `db.migration_base.py`
- **Manager**: `db.migration_manager.py`
- **Documentation**: See `MIGRATIONS.md`

## Migration Status

### ✅ Refactored (Use New System)

- `migration_001.py` - Uses new BaseMigration
- `migration_007.py` - Uses new BaseMigration
- `migration_010.py` - Uses new BaseMigration
- `migration_012.py` - Uses new BaseMigration
- `migration_013.py` - Uses new BaseMigration
- `migration_014.py` - Uses new BaseMigration
- `migration_015.py` - Uses new BaseMigration
- `migration_016.py` - Uses new BaseMigration

### ⚠️ Legacy Scripts (Deprecated)

Legacy helper scripts have been removed in favor of the standardized CLI above:

- `apply_migration_007.py`
- `apply_migration_010.py`
- `apply_migration_012.py`
- `apply_migration_013.py`
- `apply_migration_014.py`
- `apply_migration_015.py`
- `apply_migration_016.py`
- `migrate_crm_schema.py`
- `001_fix_missing_tables.py`
- `README_migrations.py`

Please switch to `python -m db.migrate` commands if you were relying on these files.

## Quick Start

### Apply All Pending Migrations

```bash
python -m db.migrate apply-all
```

### Check Status

```bash
python -m db.migrate status
```

### Apply Specific Migration

```bash
python migrations/migration_007.py
```

## Migration Order

Migrations are automatically applied in order based on their migration number. Dependencies are checked automatically.

## For More Information

See `MIGRATIONS.md` for complete documentation.


















