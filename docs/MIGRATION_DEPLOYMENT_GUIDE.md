# Migration Deployment Guide

## Overview

This guide explains how to use the new migration system in development and production environments.

## Development

### Prerequisites

1. PostgreSQL database running locally or accessible
2. `DATABASE_URL` environment variable set:
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
   ```

### Check Migration Status

```bash
cd apps/backend-rag/backend
python -m db.migrate status
```

### Apply All Pending Migrations

```bash
cd apps/backend-rag/backend
python -m db.migrate apply-all
```

### Apply Specific Migration

```bash
cd apps/backend-rag/backend
python migrations/migration_007.py
```

### Dry Run (Preview)

```bash
cd apps/backend-rag/backend
python -m db.migrate apply-all --dry-run
```

## Production (Fly.io)

### Automatic Migration Application

Migrations are automatically applied during deployment via the `release_command` in `fly.toml`:

```toml
[deploy]
  release_command = "cd backend && python -m db.migrate apply-all"
```

### Manual Migration Application

If you need to apply migrations manually:

```bash
# SSH into Fly.io instance
fly ssh console --app nuzantara-rag

# Apply migrations
cd backend
python -m db.migrate apply-all
```

### Check Migration Status in Production

```bash
fly ssh console --app nuzantara-rag -C "cd backend && python -m db.migrate status"
```

## Migration Scripts

### Legacy Scripts (Removed)

Older helper scripts (`apply_migration_*.py`, `migrate_crm_schema.py`, `001_fix_missing_tables.py`)
have been deleted. Run `python -m db.migrate ...` or the specific `migration_XXX.py` modules instead.

### New Scripts

All new migrations use the `BaseMigration` class:

- `migration_001.py` - Fix missing tables
- `migration_007.py` - CRM system schema
- `migration_010.py` - Fix team_members schema
- `migration_012.py` - Fix production schema
- `migration_013.py` - Agentic RAG tables
- `migration_014.py` - Knowledge Graph tables
- `migration_015.py` - Add Drive columns
- `migration_016.py` - Add summary to parent_documents

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

### Database Connection Error

If you get "Cannot connect to database":

1. Verify `DATABASE_URL` is set correctly
2. Check database is running
3. Verify network connectivity
4. Check firewall rules

## Best Practices

1. **Always test migrations locally first**
2. **Use dry-run before production deployment**
3. **Check migration status before and after deployment**
4. **Keep migrations idempotent** (safe to run multiple times)
5. **Document breaking changes** in migration description

## Migration Tracking

Migrations are tracked in the `schema_migrations` table:

```sql
SELECT 
    migration_number,
    migration_name,
    executed_at,
    description,
    execution_time_ms
FROM schema_migrations
ORDER BY migration_number;
```

## Rollback

Rollback is not automatically supported. To rollback:

1. Create a new migration that reverses the changes
2. Or manually modify the database and remove the migration entry

## Support

For issues or questions:
1. Check migration logs
2. Review `docs/MIGRATIONS.md`
3. Review `docs/CLEANUP_REPORT_MIGRATIONS.md`
4. Contact DevOps team


























