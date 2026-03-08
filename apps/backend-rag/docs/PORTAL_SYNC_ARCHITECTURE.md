# Portal Sync Architecture

> CRM ↔ Client Portal unified data layer for Nuzantara/Bali Zero

**Version:** 1.0.0
**Date:** 2026-02-02
**Author:** Claude Opus 4.5
**Status:** ✅ Production Ready

---

## Overview

This document describes the architecture for synchronizing data between the internal CRM system (kita.balizero.com) and the client-facing Portal (my.balizero.com).

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERNAL TEAM                             │
│                   kita.balizero.com                          │
├─────────────────────────────────────────────────────────────────┤
│  CRM Dashboard  │  Practices  │  Documents  │  Tax Management   │
└────────┬────────┴──────┬──────┴──────┬──────┴────────┬──────────┘
         │               │             │               │
         ▼               ▼             ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                          │
├─────────────────────────────────────────────────────────────────┤
│  clients          │  practices      │  documents                │
│  + client_visible │  + client_visible│ + client_visible         │
│                   │  + client_summary│ + uploaded_source        │
├───────────────────┼─────────────────┼───────────────────────────┤
│  tax_obligations  │  visa_records   │  timeline_events          │
│  + status         │  + expiry_date  │  + client_visible         │
│  + due_date       │  + status       │  + event_type             │
└────────┬──────────┴────────┬────────┴────────┬──────────────────┘
         │                   │                 │
         ▼                   ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Portal API Layer                              │
│                  /api/portal/*                                   │
├─────────────────────────────────────────────────────────────────┤
│  TaxService       │  VisaService    │  TimelineService          │
│  /taxes           │  /visa          │  /timeline                │
└────────┬──────────┴────────┬────────┴────────┬──────────────────┘
         │                   │                 │
         ▼                   ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT PORTAL                             │
│                    my.balizero.com                               │
├─────────────────────────────────────────────────────────────────┤
│  Dashboard  │  Tax Calendar  │  Visa Status  │  My Documents    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Migration: `002_portal_sync_tables.sql`

**Location:** `backend/db/migrations_v2/002_portal_sync_tables.sql`

#### 1. Timeline Events

Persistent, client-visible events for tracking progress.

```sql
CREATE TABLE timeline_events (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4(),
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL,

    event_type VARCHAR(30) NOT NULL,  -- deadline, milestone, reminder, etc.
    title VARCHAR(255) NOT NULL,
    description TEXT,
    event_date TIMESTAMP WITH TIME ZONE NOT NULL,

    client_visible BOOLEAN DEFAULT true,
    icon VARCHAR(50),
    color VARCHAR(20) DEFAULT 'info',  -- info, warning, success, error
    action_url TEXT,
    action_label VARCHAR(100),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Event Types:**

- `deadline` - Tax payment or filing deadline
- `milestone` - Practice milestone achieved
- `document_request` - Document requested from client
- `document_received` - Document received from client
- `status_change` - Practice status changed
- `reminder` - Auto-generated reminder (30/14/7/1 days before)
- `completion` - Tax paid or practice completed

#### 2. Tax Obligations

Per-client tax deadline tracking.

```sql
CREATE TABLE tax_obligations (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4(),
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    tax_type VARCHAR(20) NOT NULL,    -- pph_21, pph_23, ppn, spt_annual, etc.
    name VARCHAR(100) NOT NULL,
    frequency VARCHAR(20) NOT NULL,    -- monthly, quarterly, annual, one_time

    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    due_date DATE NOT NULL,

    status VARCHAR(20) DEFAULT 'upcoming',  -- upcoming, pending, filed, paid, overdue
    amount_due NUMERIC(15, 2),
    amount_paid NUMERIC(15, 2),

    filing_document_id INTEGER REFERENCES documents(id),
    payment_proof_id INTEGER REFERENCES documents(id),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Tax Types:**
| Code | Description |
|------|-------------|
| `pph_21` | Employee income tax (monthly) |
| `pph_23` | Service withholding tax (monthly) |
| `pph_4_2` | Final income tax |
| `ppn` | Value Added Tax (monthly) |
| `spt_annual` | Annual tax return |
| `npwp` | Tax ID registration |

#### 3. Visa Records

Immigration status tracking.

```sql
CREATE TABLE visa_records (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4(),
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    visa_type VARCHAR(30) NOT NULL,   -- kitas_work, kitas_investor, tourist, etc.
    status VARCHAR(20) NOT NULL,       -- none, applied, processing, active, expiring_soon, expired

    issue_date DATE,
    expiry_date DATE,
    visa_number VARCHAR(100),
    sponsor_name VARCHAR(255),
    sponsor_type VARCHAR(20),          -- company, individual

    practice_id INTEGER REFERENCES practices(id),
    visa_document_id INTEGER REFERENCES documents(id),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Visa Types:**
| Code | Description |
|------|-------------|
| `tourist` | Tourist visa (30/60 days) |
| `business` | Business visa |
| `social` | Social/cultural visa |
| `kitas_work` | Work permit (1-2 years) |
| `kitas_investor` | Investor visa |
| `kitas_retirement` | Retirement visa |
| `kitas_spouse` | Spouse dependent visa |
| `kitap` | Permanent stay permit |
| `evoa` | Electronic Visa on Arrival |

---

## Services

### TaxService

**Location:** `backend/services/portal/tax_service.py`

```python
class TaxService:
    """Service for managing client tax obligations."""

    async def get_client_taxes(
        self, client_id: int, include_completed: bool = False
    ) -> list[TaxObligation]:
        """Get all tax obligations for a client."""

    async def get_tax_summary(self, client_id: int) -> TaxSummary:
        """Get aggregated tax summary for dashboard card."""

    async def create_obligation(
        self, client_id: int, tax_type: str, ...
    ) -> TaxObligation:
        """Create a new tax obligation with timeline event."""

    async def update_status(
        self, obligation_id: int, new_status: str, amount_paid: float = None
    ) -> Optional[TaxObligation]:
        """Update obligation status and create timeline event."""
```

**TaxSummary Response:**

```json
{
  "total_due": 15000000.0,
  "next_deadline": "2026-02-15",
  "days_until_deadline": 13,
  "pending_count": 3,
  "overdue_count": 0,
  "status": "attention" // ok | attention | critical
}
```

**Status Logic:**

- `ok`: Next deadline > 14 days, no overdue
- `attention`: Next deadline ≤ 14 days
- `critical`: Next deadline ≤ 7 days OR overdue_count > 0

### VisaService

**Location:** `backend/services/portal/visa_service.py`

```python
class VisaService:
    """Service for managing client visa records."""

    async def get_active_visa(self, client_id: int) -> Optional[VisaRecord]:
        """Get the currently active visa for a client."""

    async def get_visa_history(self, client_id: int) -> list[VisaRecord]:
        """Get all visa records for a client."""

    async def get_visa_summary(self, client_id: int) -> VisaSummary:
        """Get visa summary for dashboard card."""

    async def create_visa_record(self, client_id: int, visa_type: str, ...) -> VisaRecord:
        """Create new visa record with timeline event."""

    async def update_visa_status(self, visa_id: int, new_status: str) -> Optional[VisaRecord]:
        """Update visa status (e.g., expiring_soon, expired)."""
```

**VisaSummary Response:**

```json
{
  "has_active_visa": true,
  "visa_type": "kitas_work",
  "expiry_date": "2026-12-31",
  "days_until_expiry": 333,
  "status": "active" // none | active | expiring_soon | expired
}
```

**Status Logic:**

- `none`: No active visa
- `active`: Visa valid, expiry > 30 days
- `expiring_soon`: Visa expiry ≤ 30 days
- `expired`: Visa expiry ≤ 0 days

---

## API Endpoints

### Portal Taxes API

**Base URL:** `/api/portal/taxes`

| Method | Endpoint   | Description                                      |
| ------ | ---------- | ------------------------------------------------ |
| GET    | `/`        | Get all tax obligations for authenticated client |
| GET    | `/summary` | Get tax summary for dashboard card               |

**Authentication:** JWT token with `role = 'client'`

**Example Response:**

```json
{
  "summary": {
    "total_due": 15000000.0,
    "next_deadline": "2026-02-15",
    "days_until_deadline": 13,
    "pending_count": 3,
    "overdue_count": 0,
    "status": "attention"
  },
  "obligations": [
    {
      "id": 1,
      "tax_type": "pph_21",
      "name": "PPh 21 - January 2026",
      "due_date": "2026-02-15",
      "status": "pending",
      "amount_due": 5000000.0
    }
  ]
}
```

### Portal Visa API

**Base URL:** `/api/portal/visa`

| Method | Endpoint   | Description                              |
| ------ | ---------- | ---------------------------------------- |
| GET    | `/`        | Get visa status for authenticated client |
| GET    | `/summary` | Get visa summary for dashboard card      |

**Example Response:**

```json
{
  "summary": {
    "has_active_visa": true,
    "visa_type": "kitas_work",
    "expiry_date": "2026-12-31",
    "days_until_expiry": 333,
    "status": "active"
  },
  "current_visa": {
    "id": 1,
    "visa_type": "kitas_work",
    "status": "active",
    "expiry_date": "2026-12-31",
    "sponsor_name": "PT Example Indonesia"
  },
  "history": []
}
```

---

## Background Jobs

### DeadlineChecker

**Location:** `backend/jobs/deadline_checker.py`

Runs daily to create reminder timeline events.

**Tax Reminders:**
| Days Before | Urgency | Color |
|-------------|---------|-------|
| 30 days | info | info |
| 14 days | warning | warning |
| 7 days | critical | error |
| 1 day | critical | error |

**Visa Reminders:**
| Days Before | Urgency | Action |
|-------------|---------|--------|
| 90 days | info | Renewal notice |
| 60 days | warning | Renewal reminder |
| 30 days | critical | Status → `expiring_soon` |

**Running the Job:**

```bash
# CLI
python -m backend.jobs.deadline_checker

# Or via cron/APScheduler
*/0 8 * * * python -m backend.jobs.deadline_checker
```

**Prometheus Metrics:**

- `deadline_checker_total` - Total job runs
- `deadline_reminders_created{type,urgency}` - Reminders created
- `deadline_checker_last_run_timestamp` - Last successful run

---

## Authentication

### get_current_portal_client Dependency

**Location:** `backend/app/dependencies.py`

Shared dependency for all Portal endpoints.

```python
async def get_current_portal_client(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """
    Get current authenticated client from JWT token for Portal endpoints.

    Returns:
        dict: Client info with id, email, full_name

    Raises:
        HTTPException 401: No valid JWT token
        HTTPException 403: User role is not 'client'
        HTTPException 404: Client profile not found
    """
```

**Usage:**

```python
from backend.app.dependencies import get_current_portal_client

@router.get("/my-data")
async def get_my_data(
    current_client: dict = Depends(get_current_portal_client)
):
    client_id = current_client["id"]
    # ... fetch client-specific data
```

---

## Pydantic Schemas

**Location:** `backend/schemas/portal.py`

```python
class TaxObligation(BaseModel):
    id: int
    uuid: str
    client_id: int
    tax_type: str
    name: str
    frequency: str
    period_start: date
    period_end: date
    due_date: date
    status: str
    amount_due: Optional[float]
    amount_paid: Optional[float]
    created_at: datetime

class TaxSummary(BaseModel):
    total_due: float = 0
    next_deadline: Optional[date] = None
    days_until_deadline: Optional[int] = None
    pending_count: int = 0
    overdue_count: int = 0
    status: str = "ok"  # ok, attention, critical

class VisaRecord(BaseModel):
    id: int
    uuid: str
    client_id: int
    visa_type: str
    status: str
    issue_date: Optional[date]
    expiry_date: Optional[date]
    visa_number: Optional[str]
    sponsor_name: Optional[str]
    sponsor_type: Optional[str]
    created_at: datetime

class VisaSummary(BaseModel):
    has_active_visa: bool = False
    visa_type: Optional[str] = None
    expiry_date: Optional[date] = None
    days_until_expiry: Optional[int] = None
    status: str = "none"  # none, active, expiring_soon, expired

class TimelineEvent(BaseModel):
    id: int
    event_type: str
    title: str
    description: Optional[str]
    event_date: datetime
    icon: Optional[str]
    color: str = "info"
    action_url: Optional[str]
    action_label: Optional[str]
```

---

## Testing

### Test Files

| File                       | Tests | Coverage            |
| -------------------------- | ----- | ------------------- |
| `test_tax_service.py`      | 15    | TaxService methods  |
| `test_visa_service.py`     | 17    | VisaService methods |
| `test_deadline_checker.py` | 11    | Background job      |

**Total:** 43 tests, all passing

### Running Tests

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/portal/ backend/tests/unit/jobs/ -v
```

### Mock Pattern

```python
class AsyncContextManagerMock:
    """Helper for mocking async with db_pool.acquire()."""

    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.fixture
def mock_db_pool(mock_conn):
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContextManagerMock(mock_conn))
    return pool
```

---

## Prometheus Metrics

### Portal Taxes

```python
tax_requests = Counter(
    "portal_tax_requests_total",
    "Tax endpoint requests",
    ["endpoint", "status"]
)
tax_latency = Histogram(
    "portal_tax_latency_seconds",
    "Tax endpoint latency"
)
```

### Portal Visa

```python
visa_requests = Counter(
    "portal_visa_requests_total",
    "Visa endpoint requests",
    ["endpoint", "status"]
)
visa_latency = Histogram(
    "portal_visa_latency_seconds",
    "Visa endpoint latency"
)
```

### Deadline Checker

```python
deadlines_checked = Counter(
    "deadline_checker_total",
    "Total deadlines checked"
)
reminders_created = Counter(
    "deadline_reminders_created",
    "Reminder events created",
    ["type", "urgency"]
)
job_last_run = Gauge(
    "deadline_checker_last_run_timestamp",
    "Last successful run"
)
```

---

## Files Reference

| File                                          | Purpose                     |
| --------------------------------------------- | --------------------------- |
| `db/migrations_v2/002_portal_sync_tables.sql` | Database schema             |
| `services/portal/tax_service.py`              | Tax business logic          |
| `services/portal/visa_service.py`             | Visa business logic         |
| `app/routers/portal_taxes.py`                 | Tax API endpoints           |
| `app/routers/portal_visa.py`                  | Visa API endpoints          |
| `app/dependencies.py`                         | `get_current_portal_client` |
| `schemas/portal.py`                           | Pydantic models             |
| `jobs/deadline_checker.py`                    | Background job              |
| `tests/unit/services/portal/`                 | Unit tests                  |
| `tests/unit/jobs/`                            | Job tests                   |

---

## Deployment

### Apply Migration

```bash
psql $DATABASE_URL -f backend/db/migrations_v2/002_portal_sync_tables.sql
```

### Verify Endpoints

```bash
# Health check
curl https://nuzantara-rag.fly.dev/health

# Metrics
curl https://nuzantara-rag.fly.dev/metrics | grep portal_
```

### Schedule Deadline Checker

Add to crontab or APScheduler:

```bash
# Run daily at 8 AM UTC
0 8 * * * cd /app && python -m backend.jobs.deadline_checker
```

---

## Changelog

### v1.0.0 (2026-02-02)

- Initial implementation
- TaxService with CRUD + timeline events
- VisaService with CRUD + timeline events
- DeadlineChecker background job
- 43 unit tests
- DRY refactor: `get_current_portal_client` shared dependency
- Bug fix: visa expiry status check order

---

**Maintained by:** Nuzantara Engineering Team
**Contact:** tech@balizero.com
