# Scripts Directory - Organized Structure

This directory contains all utility scripts for the Nuzantara project, organized by category.

## Structure

```
scripts/
├── e2e/                    # End-to-end test scripts (21 files)
│   ├── test_business_questions.py
│   ├── test_zantara_*.py
│   └── ...
├── ingestion/              # Data ingestion scripts (15 files)
│   ├── ingest_conversations.py
│   ├── ingest_team_data.py
│   ├── ingest_laws.py
│   └── ...
├── analysis/               # Analysis and reporting scripts (7 files)
│   ├── analyze_coverage.py
│   ├── analyze_qdrant_documents.py
│   └── ...
├── verify/                 # Verification scripts (15 files)
│   ├── verify_agentic_integration.py
│   ├── verify_all_collections.py
│   └── ...
├── checks/                 # Health check scripts (6 files)
│   ├── check_deployment.py
│   ├── check_conversation_memory.py
│   └── ...
├── monitoring/             # Monitoring scripts (4 files)
│   ├── health_check.py
│   ├── sentry_monitor.py
│   └── ...
├── automation/             # CI/CD and automation scripts (7 files)
│   ├── apply_migrations.py
│   ├── fix_test_coverage.py
│   └── ...
├── data/                   # Data management scripts (47 files)
│   ├── audit_*.py
│   ├── clean_*.py
│   ├── populate_*.py
│   ├── validate_*.py
│   └── ...
└── deprecated/             # Deprecated scripts (3 files)
    ├── test_direct_gemini_pro.py
    ├── test_gemini_ultra_extraction.py
    └── test_metadata_extraction.py
```

## Categories

### E2E (`e2e/`)
End-to-end test scripts that test the full system integration. These are manual test scripts, not part of the formal test suite.

### Ingestion (`ingestion/`)
Scripts for ingesting data into Qdrant collections. Includes conversation ingestion, team data, legal documents, etc.

### Analysis (`analysis/`)
Scripts for analyzing code coverage, Qdrant documents, embedding quality, etc.

### Verify (`verify/`)
Scripts for verifying system components, collections, integrations, etc.

### Checks (`checks/`)
Health check scripts for various system components.

### Monitoring (`monitoring/`)
Monitoring and alerting scripts (health checks, Sentry monitoring, etc.).

### Automation (`automation/`)
CI/CD scripts, migration runners, test automation, etc.

### Data (`data/`)
Data management scripts: audits, cleanup, population, validation, extraction, etc.

### Deprecated (`deprecated/`)
Scripts that are no longer actively used but kept for reference. Can be removed after review.

## Migration Notes

This structure was created on 2025-12-16 as part of the codebase cleanup initiative. Scripts were consolidated from:
- `/scripts/` (root)
- `/apps/backend-rag/scripts/`
- `/apps/backend-rag/backend/scripts/`

## Usage

Most scripts can be run directly:
```bash
python scripts/<category>/<script_name>.py
```

Some scripts may require environment variables or specific setup. Check individual script headers for details.

