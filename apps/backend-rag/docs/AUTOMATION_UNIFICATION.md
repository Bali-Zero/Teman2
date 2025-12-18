# Automation Unification - AREA 4

This document describes the unified automation systems that replace fragmented scripts.

## Overview

Three major automation areas have been unified:

1. **Health Checks** - Unified Health Check Service
2. **Migrations** - Automatic Migration Runner
3. **Ingestion** - Unified Ingestion CLI

---

## 1. Unified Health Check Service

### Location
- **Service**: `backend/services/unified_health_service.py`
- **CLI Script**: `scripts/unified_health_check.py`

### Replaces
- `scripts/health_check.py`
- `apps/backend-rag/scripts/health_check.py`
- `backend/self_healing/backend_agent.py` (monitoring part)

### Features
- Comprehensive health checks for all services
- System metrics monitoring (CPU, memory, disk)
- Integration with ServiceRegistry
- Caching for performance
- Continuous monitoring mode
- JSON output support

### Usage

#### Single Check
```bash
python apps/backend-rag/scripts/unified_health_check.py
```

#### JSON Output
```bash
python apps/backend-rag/scripts/unified_health_check.py --json
```

#### Continuous Monitoring
```bash
python apps/backend-rag/scripts/unified_health_check.py --continuous --interval 30
```

### Programmatic Usage
```python
from services.unified_health_service import UnifiedHealthService

service = UnifiedHealthService()
await service.initialize()

report = await service.run_all_checks()
print(service.format_report(report))

await service.close()
```

---

## 2. Automatic Migration Runner

### Location
- **Service**: `backend/services/migration_runner.py`
- **CLI Script**: `scripts/migrate.py`

### Replaces
- `migrations/apply_migration_007.py`
- `migrations/apply_migration_010.py`
- `migrations/apply_migration_012.py`
- `migrations/apply_migration_013.py`
- `migrations/apply_migration_014.py`
- `migrations/apply_migration_015.py`
- `migrations/apply_migration_016.py`

### Features
- Automatic discovery of migrations
- Dependency resolution (topological sort)
- Version tracking in database
- Dry-run mode for validation
- Rollback support (via BaseMigration)

### Usage

#### Check Status
```bash
python apps/backend-rag/scripts/migrate.py status
```

#### Apply All Pending Migrations
```bash
python apps/backend-rag/scripts/migrate.py apply-all
```

#### Dry Run (Validate Without Executing)
```bash
python apps/backend-rag/scripts/migrate.py apply-all --dry-run
```

### Programmatic Usage
```python
from services.migration_runner import MigrationRunner

async with MigrationRunner() as runner:
    # Check status
    status = await runner.status()
    
    # Apply all pending
    result = await runner.apply_all(dry_run=False)
```

---

## 3. Unified Ingestion CLI

### Location
- **CLI**: `backend/cli/ingestion_cli.py`
- **Wrapper Script**: `scripts/ingest.py`

### Replaces
- `scripts/ingest_team_data.py`
- `scripts/ingest_conversations.py`
- `scripts/ingest_synthetic_data.py`
- `apps/backend-rag/scripts/ingest_*.py`

### Features
- Single CLI for all ingestion types
- Team members ingestion
- Conversations ingestion
- Legal documents ingestion
- General document ingestion
- List available types

### Usage

#### List Available Types
```bash
python apps/backend-rag/scripts/ingest.py list
```

#### Ingest Team Members
```bash
python apps/backend-rag/scripts/ingest.py ingest team-members
python apps/backend-rag/scripts/ingest.py ingest team-members --source /path/to/team_members.json
```

#### Ingest Conversations
```bash
python apps/backend-rag/scripts/ingest.py ingest conversations --source /path/to/conversations.json
```

#### Ingest Legal Documents
```bash
python apps/backend-rag/scripts/ingest.py ingest laws --file /path/to/law.pdf
python apps/backend-rag/scripts/ingest.py ingest laws --directory /path/to/laws/
```

#### Ingest General Documents
```bash
python apps/backend-rag/scripts/ingest.py ingest document --file /path/to/doc.pdf --title "My Document"
```

### Programmatic Usage
```python
from cli.ingestion_cli import IngestionCLI

cli = IngestionCLI()

# Ingest team members
result = await cli.ingest_team_members()

# Ingest conversations
result = await cli.ingest_conversations(source="/path/to/data")

# Ingest legal documents
result = await cli.ingest_laws(file_path="/path/to/law.pdf")
```

---

## Migration Guide

### Health Checks

**Old Way:**
```bash
python scripts/health_check.py
python apps/backend-rag/scripts/health_check.py
```

**New Way:**
```bash
python apps/backend-rag/scripts/unified_health_check.py
```

### Migrations

**Old Way:**
```bash
python migrations/apply_migration_007.py
python migrations/apply_migration_010.py
# ... repeat for each migration
```

**New Way:**
```bash
python apps/backend-rag/scripts/migrate.py status
python apps/backend-rag/scripts/migrate.py apply-all
```

### Ingestion

**Old Way:**
```bash
python scripts/ingest_team_data.py
python scripts/ingest_conversations.py /path/to/data
python apps/backend-rag/scripts/ingest_laws.py /path/to/law.pdf
```

**New Way:**
```bash
python apps/backend-rag/scripts/ingest.py ingest team-members
python apps/backend-rag/scripts/ingest.py ingest conversations --source /path/to/data
python apps/backend-rag/scripts/ingest.py ingest laws --file /path/to/law.pdf
```

---

## Benefits

1. **Single Source of Truth** - One service/CLI per area instead of multiple scripts
2. **Consistency** - Unified interfaces and error handling
3. **Maintainability** - Easier to update and extend
4. **Discoverability** - Clear commands and help text
5. **Integration** - Services can be imported and used programmatically
6. **Versioning** - Automatic tracking for migrations
7. **Validation** - Dry-run modes for safe testing

---

## Future Enhancements

- [ ] Health check webhooks/notifications
- [ ] Migration rollback CLI command
- [ ] Ingestion progress bars
- [ ] Batch ingestion with parallel processing
- [ ] Health check metrics export (Prometheus format)

