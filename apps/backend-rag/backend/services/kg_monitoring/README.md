# KG Monitoring Service - Phase 8

Automated monitoring and auto-ingestion service for Knowledge Graph data sources.

## Overview

This service monitors Indonesian legal websites for new regulations and updates:

- **JDIH Kemenkumham** (https://jdih.kemenkumham.go.id/) - Legal database
- **Peraturan BPK** (https://peraturan.bpk.go.id/) - Government regulations

## Components

### 1. `scraper.py` - Legal Website Scraper

- Async HTTP scraping with retry logic
- Rate limiting and polite crawling
- Content extraction with BeautifulSoup
- Structured document output

### 2. `change_detector.py` - Change Detection

- MD5 hash-based change detection
- PostgreSQL storage for document states
- Change classification (new, updated, deleted)
- Historical tracking with timestamps

### 3. `auto_ingestion.py` - LLM Extraction & Ingestion

- LLM-based content extraction
- Structured data parsing
- Qdrant ingestion with embeddings
- Batch processing

### 4. `quality_check.py` - Quality Validation

- Multi-dimensional quality scoring
- Content validation rules
- Automated rejection criteria
- Quality report generation

## Usage

### Running as a Cron Job

```bash
# Check only (no ingestion)
python scripts/kg_monitoring/cron_runner.py --check-only

# Full run with ingestion
python scripts/kg_monitoring/cron_runner.py

# Single source
python scripts/kg_monitoring/cron_runner.py --source jdih_kemenkumham

# Verbose logging
python scripts/kg_monitoring/cron_runner.py --verbose
```

### Running as a Service

```bash
# Start the service
python scripts/kg_monitoring/service.py --port 8080 --interval 60

# Health check
curl http://localhost:8080/health

# Trigger manual run
curl -X POST http://localhost:8080/run
```

### Using in Code

```python
from backend.services.kg_monitoring import (
    LegalScraper,
    ChangeDetector,
    AutoIngestionService,
    QualityCheckService,
)

# Initialize components
scraper = LegalScraper()
detector = ChangeDetector(db_pool=pool, alert_on_change=True)
ingestion = AutoIngestionService(
    llm_client=llm,
    qdrant_client=qdrant,
    quality_service=QualityCheckService(),
)

# Scrape documents
docs = await scraper.scrape_source("jdih_kemenkumham", max_pages=5)

# Detect changes
changes = await detector.detect_changes(docs, "jdih_kemenkumham")

# Ingest new/changed documents
for change in changes:
    if change.change_type in ("new", "updated"):
        doc = next(d for d in docs if d.document_id == change.document_id)
        await scraper.fetch_document_detail(doc)
        result = await ingestion.ingest_document(doc)
```

## Database Schema

### kg_monitored_documents

```sql
CREATE TABLE kg_monitored_documents (
    document_id VARCHAR(32) PRIMARY KEY,
    source_id VARCHAR(64) NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    content_hash VARCHAR(32) NOT NULL,
    first_seen TIMESTAMP WITH TIME ZONE NOT NULL,
    last_checked TIMESTAMP WITH TIME ZONE NOT NULL,
    last_changed TIMESTAMP WITH TIME ZONE,
    change_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE
);
```

### kg_change_events

```sql
CREATE TABLE kg_change_events (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(32) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL,
    old_hash VARCHAR(32),
    new_hash VARCHAR(32),
    title TEXT,
    url TEXT,
    details JSONB DEFAULT '{}',
    notified BOOLEAN DEFAULT FALSE
);
```

### kg_ingestion_results

```sql
CREATE TABLE kg_ingestion_results (
    document_id VARCHAR(32) PRIMARY KEY,
    source_id VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    extracted_data JSONB,
    qdrant_id VARCHAR(64),
    error_message TEXT,
    processing_time_ms FLOAT
);
```

## Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@localhost/dbname
REDIS_URL=redis://localhost:6379/0
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx
QDRANT_URL=http://localhost:6333
LLM_API_KEY=your_api_key
```

## Testing

```bash
# Run all tests
pytest apps/backend-rag/backend/tests/services/kg_monitoring/ -v

# Run specific test file
pytest apps/backend-rag/backend/tests/services/kg_monitoring/test_scraper.py -v

# Run with coverage
pytest apps/backend-rag/backend/tests/services/kg_monitoring/ --cov=backend.services.kg_monitoring
```

## Monitoring & Alerts

The service sends alerts via Slack when:

- New documents are detected
- Documents are updated
- Ingestion failures occur
- Quality checks fail

Configure `SLACK_WEBHOOK_URL` to enable alerts.

## Cron Configuration

```bash
# Run daily at 6 AM
0 6 * * * cd /path/to/project && python scripts/kg_monitoring/cron_runner.py >> /var/log/kg_monitoring.log 2>&1
```

## Directory Structure

```
backend/services/kg_monitoring/
├── __init__.py           # Module exports
├── scraper.py            # Website scraping
├── change_detector.py    # Change detection
├── auto_ingestion.py     # LLM extraction & ingestion
└── quality_check.py      # Quality validation

scripts/kg_monitoring/
├── __init__.py
├── cron_runner.py        # Cron job script
└── service.py            # Standalone service

backend/tests/services/kg_monitoring/
├── __init__.py
├── test_scraper.py
├── test_change_detector.py
├── test_auto_ingestion.py
├── test_quality_check.py
└── test_integration.py
```

## Phase 8 Deliverables

- ✅ Monitoring service + scraper
- ✅ Change detection with hash storage
- ✅ Auto-ingestion with LLM extraction
- ✅ Quality validation
- ✅ Slack webhook integration
- ✅ Cron job configuration
- ✅ 15+ tests
