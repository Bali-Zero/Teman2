# 🎯 NUZANTARA Phase 2: Tax & Visa Portal Endpoints + Deadline Checker

## 📍 Working Directory

```
/Users/antonellosiano/Projects/nuzantara/apps/backend-rag/backend
```

## 🎯 Obiettivo

Implementare endpoints Portal per gestione tax obligations e visa records, più job automatico per reminder scadenze.

---

## ✅ GOLDEN RULES (OBBLIGATORIE)

1. **Virtualenv**: Tutti i test in virtualenv (`source .venv/bin/activate`)
2. **Absolute Imports**: `from backend.services...`, `from backend.app.routers...`
3. **Async First**: Tutte le funzioni DB/IO devono essere `async def`
4. **Type Hints**: TUTTE le funzioni devono avere type hints completi
5. **No Hardcoding**: Config da `os.getenv()` o `settings.py`
6. **Logging**: `logger.info/warning/error` su tutte le operazioni
7. **Metrics**: Prometheus Counter/Histogram per operazioni chiave

---

## 📁 FILES DA CREARE

### 1️⃣ `backend/schemas/portal.py`

```python
"""Portal API schemas - Pydantic models for request/response validation."""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class TaxObligation(BaseModel):
    """Tax obligation record."""
    id: int
    uuid: str
    client_id: int
    tax_type: str  # pph_21, pph_23, pph_4_2, ppn, spt_annual, npwp
    name: str
    frequency: str  # monthly, quarterly, annual, one_time
    period_start: date
    period_end: date
    due_date: date
    status: str  # upcoming, pending, filed, paid, overdue
    amount_due: Optional[float] = None
    amount_paid: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TaxSummary(BaseModel):
    """Tax summary for dashboard card."""
    total_due: float = 0
    next_deadline: Optional[date] = None
    days_until_deadline: Optional[int] = None
    pending_count: int = 0
    overdue_count: int = 0
    status: str = "ok"  # ok, attention, critical


class VisaRecord(BaseModel):
    """Visa record."""
    id: int
    uuid: str
    client_id: int
    visa_type: str  # tourist, business, social, kitas_work, kitas_investor, etc.
    status: str  # none, applied, processing, active, expiring_soon, expired, cancelled
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    visa_number: Optional[str] = None
    sponsor_name: Optional[str] = None
    sponsor_type: Optional[str] = None  # company, individual
    created_at: datetime

    class Config:
        from_attributes = True


class VisaSummary(BaseModel):
    """Visa summary for dashboard card."""
    has_active_visa: bool = False
    visa_type: Optional[str] = None
    expiry_date: Optional[date] = None
    days_until_expiry: Optional[int] = None
    status: str = "none"  # none, active, expiring_soon, expired


class TimelineEvent(BaseModel):
    """Timeline event for Portal dashboard."""
    id: int
    event_type: str  # deadline, milestone, document_request, status_change, reminder, etc.
    title: str
    description: Optional[str] = None
    event_date: datetime
    icon: Optional[str] = None
    color: str = "info"  # info, warning, success, error
    action_url: Optional[str] = None
    action_label: Optional[str] = None

    class Config:
        from_attributes = True
```

---

### 2️⃣ `backend/services/portal/tax_service.py`

```python
"""Tax obligations service for Portal."""
from typing import Optional
from datetime import date
import structlog
from asyncpg import Pool

from backend.schemas.portal import TaxObligation, TaxSummary

logger = structlog.get_logger(__name__)


class TaxService:
    """Service for managing client tax obligations."""

    def __init__(self, db_pool: Pool):
        self.db_pool = db_pool

    async def get_client_taxes(
        self,
        client_id: int,
        include_completed: bool = False
    ) -> list[TaxObligation]:
        """
        Get all tax obligations for a client.

        Args:
            client_id: The client's database ID
            include_completed: Whether to include paid/filed obligations

        Returns:
            List of TaxObligation objects
        """
        query = """
            SELECT * FROM tax_obligations
            WHERE client_id = $1
        """
        if not include_completed:
            query += " AND status NOT IN ('paid', 'filed')"
        query += " ORDER BY due_date ASC"

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, client_id)
            logger.info("Fetched tax obligations", client_id=client_id, count=len(rows))
            return [TaxObligation(**dict(row)) for row in rows]

    async def get_tax_summary(self, client_id: int) -> TaxSummary:
        """
        Get aggregated tax summary for dashboard card.

        Returns:
            TaxSummary with total_due, next_deadline, etc.
        """
        query = """
            SELECT
                COALESCE(SUM(CASE WHEN status IN ('upcoming', 'pending', 'overdue')
                    THEN amount_due ELSE 0 END), 0) as total_due,
                MIN(CASE WHEN status IN ('upcoming', 'pending')
                    THEN due_date END) as next_deadline,
                COUNT(CASE WHEN status IN ('upcoming', 'pending')
                    THEN 1 END) as pending_count,
                COUNT(CASE WHEN status = 'overdue'
                    THEN 1 END) as overdue_count
            FROM tax_obligations
            WHERE client_id = $1
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, client_id)

            days_until = None
            status = "ok"
            if row['next_deadline']:
                days_until = (row['next_deadline'] - date.today()).days
                if days_until <= 7:
                    status = "critical"
                elif days_until <= 14:
                    status = "attention"

            if row['overdue_count'] > 0:
                status = "critical"

            logger.info("Generated tax summary", client_id=client_id, status=status)

            return TaxSummary(
                total_due=float(row['total_due'] or 0),
                next_deadline=row['next_deadline'],
                days_until_deadline=days_until,
                pending_count=row['pending_count'],
                overdue_count=row['overdue_count'],
                status=status
            )

    async def create_obligation(
        self,
        client_id: int,
        tax_type: str,
        name: str,
        frequency: str,
        period_start: date,
        period_end: date,
        due_date: date,
        amount_due: Optional[float] = None
    ) -> TaxObligation:
        """Create a new tax obligation with timeline event."""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                # Insert obligation
                row = await conn.fetchrow("""
                    INSERT INTO tax_obligations
                    (client_id, tax_type, name, frequency, period_start,
                     period_end, due_date, amount_due, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'upcoming')
                    RETURNING *
                """, client_id, tax_type, name, frequency,
                period_start, period_end, due_date, amount_due)

                # Create timeline event
                await conn.execute("""
                    INSERT INTO timeline_events
                    (client_id, event_type, title, description, event_date, color, client_visible)
                    VALUES ($1, 'deadline', $2, $3, $4, 'warning', true)
                """, client_id, f"Tax Deadline: {name}",
                f"Due: {due_date}", due_date)

                logger.info("Created tax obligation",
                           client_id=client_id, tax_type=tax_type, due_date=str(due_date))
                return TaxObligation(**dict(row))

    async def update_status(
        self,
        obligation_id: int,
        new_status: str,
        amount_paid: Optional[float] = None
    ) -> Optional[TaxObligation]:
        """Update obligation status and create timeline event."""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("""
                    UPDATE tax_obligations
                    SET status = $2, amount_paid = COALESCE($3, amount_paid),
                        updated_at = NOW()
                    WHERE id = $1
                    RETURNING *
                """, obligation_id, new_status, amount_paid)

                if row and new_status == 'paid':
                    await conn.execute("""
                        INSERT INTO timeline_events
                        (client_id, event_type, title, event_date, color, client_visible)
                        VALUES ($1, 'completion', $2, NOW(), 'success', true)
                    """, row['client_id'], f"Tax Paid: {row['name']}")

                logger.info("Updated tax obligation",
                           id=obligation_id, new_status=new_status)
                return TaxObligation(**dict(row)) if row else None
```

---

### 3️⃣ `backend/services/portal/visa_service.py`

```python
"""Visa records service for Portal."""
from typing import Optional
from datetime import date
import structlog
from asyncpg import Pool

from backend.schemas.portal import VisaRecord, VisaSummary

logger = structlog.get_logger(__name__)


class VisaService:
    """Service for managing client visa records."""

    def __init__(self, db_pool: Pool):
        self.db_pool = db_pool

    async def get_active_visa(self, client_id: int) -> Optional[VisaRecord]:
        """Get the currently active visa for a client."""
        query = """
            SELECT * FROM visa_records
            WHERE client_id = $1 AND status IN ('active', 'expiring_soon')
            ORDER BY expiry_date DESC
            LIMIT 1
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, client_id)
            if row:
                logger.info("Found active visa",
                           client_id=client_id, visa_type=row['visa_type'])
                return VisaRecord(**dict(row))
            return None

    async def get_visa_history(self, client_id: int) -> list[VisaRecord]:
        """Get all visa records for a client."""
        query = """
            SELECT * FROM visa_records
            WHERE client_id = $1
            ORDER BY created_at DESC
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, client_id)
            logger.info("Fetched visa history", client_id=client_id, count=len(rows))
            return [VisaRecord(**dict(row)) for row in rows]

    async def get_visa_summary(self, client_id: int) -> VisaSummary:
        """Get visa summary for dashboard card."""
        active_visa = await self.get_active_visa(client_id)

        if not active_visa:
            return VisaSummary(has_active_visa=False, status="none")

        days_until = None
        status = "active"

        if active_visa.expiry_date:
            days_until = (active_visa.expiry_date - date.today()).days
            if days_until <= 30:
                status = "expiring_soon"
            elif days_until <= 0:
                status = "expired"

        logger.info("Generated visa summary",
                   client_id=client_id, status=status, days_until=days_until)

        return VisaSummary(
            has_active_visa=True,
            visa_type=active_visa.visa_type,
            expiry_date=active_visa.expiry_date,
            days_until_expiry=days_until,
            status=status
        )

    async def create_visa_record(
        self,
        client_id: int,
        visa_type: str,
        status: str = "active",
        issue_date: Optional[date] = None,
        expiry_date: Optional[date] = None,
        visa_number: Optional[str] = None,
        sponsor_name: Optional[str] = None,
        sponsor_type: Optional[str] = None,
        practice_id: Optional[int] = None
    ) -> VisaRecord:
        """Create new visa record with timeline event."""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("""
                    INSERT INTO visa_records
                    (client_id, visa_type, status, issue_date, expiry_date,
                     visa_number, sponsor_name, sponsor_type, practice_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING *
                """, client_id, visa_type, status, issue_date, expiry_date,
                visa_number, sponsor_name, sponsor_type, practice_id)

                # Create timeline event
                await conn.execute("""
                    INSERT INTO timeline_events
                    (client_id, event_type, title, description, event_date, color, client_visible)
                    VALUES ($1, 'milestone', $2, $3, NOW(), 'success', true)
                """, client_id, f"Visa Issued: {visa_type}",
                f"Valid until: {expiry_date}" if expiry_date else None)

                logger.info("Created visa record",
                           client_id=client_id, visa_type=visa_type)
                return VisaRecord(**dict(row))

    async def update_visa_status(
        self,
        visa_id: int,
        new_status: str
    ) -> Optional[VisaRecord]:
        """Update visa status (e.g., expiring_soon, expired)."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE visa_records
                SET status = $2, updated_at = NOW()
                WHERE id = $1
                RETURNING *
            """, visa_id, new_status)

            if row:
                logger.info("Updated visa status", visa_id=visa_id, new_status=new_status)
                return VisaRecord(**dict(row))
            return None
```

---

### 4️⃣ `backend/app/routers/portal_taxes.py`

```python
"""Portal Tax API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from prometheus_client import Counter, Histogram
import time

from backend.services.portal.tax_service import TaxService
from backend.app.deps import get_current_portal_client, get_db_pool
from backend.schemas.portal import TaxSummary, TaxObligation

router = APIRouter(prefix="/api/portal/taxes", tags=["Portal - Taxes"])

# Metrics
tax_requests = Counter('portal_tax_requests_total', 'Tax endpoint requests',
                       ['endpoint', 'status'])
tax_latency = Histogram('portal_tax_latency_seconds', 'Tax endpoint latency')


@router.get("/", response_model=dict)
async def get_taxes(
    include_completed: bool = False,
    current_client = Depends(get_current_portal_client),
    db_pool = Depends(get_db_pool)
):
    """
    Get all tax obligations for the authenticated client.

    Returns:
        - summary: TaxSummary (total_due, next_deadline, status)
        - obligations: List[TaxObligation]
    """
    start = time.time()
    try:
        service = TaxService(db_pool)
        obligations = await service.get_client_taxes(current_client.id, include_completed)
        summary = await service.get_tax_summary(current_client.id)

        tax_requests.labels(endpoint="get_taxes", status="success").inc()
        tax_latency.observe(time.time() - start)

        return {
            "summary": summary.model_dump(),
            "obligations": [o.model_dump() for o in obligations]
        }
    except Exception as e:
        tax_requests.labels(endpoint="get_taxes", status="error").inc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=TaxSummary)
async def get_tax_summary(
    current_client = Depends(get_current_portal_client),
    db_pool = Depends(get_db_pool)
):
    """Get tax summary for dashboard card."""
    service = TaxService(db_pool)
    return await service.get_tax_summary(current_client.id)
```

---

### 5️⃣ `backend/app/routers/portal_visa.py`

```python
"""Portal Visa API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from prometheus_client import Counter, Histogram
import time

from backend.services.portal.visa_service import VisaService
from backend.app.deps import get_current_portal_client, get_db_pool
from backend.schemas.portal import VisaSummary, VisaRecord

router = APIRouter(prefix="/api/portal/visa", tags=["Portal - Visa"])

# Metrics
visa_requests = Counter('portal_visa_requests_total', 'Visa endpoint requests',
                       ['endpoint', 'status'])
visa_latency = Histogram('portal_visa_latency_seconds', 'Visa endpoint latency')


@router.get("/", response_model=dict)
async def get_visa_status(
    current_client = Depends(get_current_portal_client),
    db_pool = Depends(get_db_pool)
):
    """
    Get immigration status for authenticated client.

    Returns:
        - summary: VisaSummary
        - current_visa: VisaRecord or null
        - history: List[VisaRecord]
    """
    start = time.time()
    try:
        service = VisaService(db_pool)
        current_visa = await service.get_active_visa(current_client.id)
        history = await service.get_visa_history(current_client.id)
        summary = await service.get_visa_summary(current_client.id)

        visa_requests.labels(endpoint="get_visa", status="success").inc()
        visa_latency.observe(time.time() - start)

        return {
            "summary": summary.model_dump(),
            "current_visa": current_visa.model_dump() if current_visa else None,
            "history": [v.model_dump() for v in history]
        }
    except Exception as e:
        visa_requests.labels(endpoint="get_visa", status="error").inc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=VisaSummary)
async def get_visa_summary(
    current_client = Depends(get_current_portal_client),
    db_pool = Depends(get_db_pool)
):
    """Get visa summary for dashboard card."""
    service = VisaService(db_pool)
    return await service.get_visa_summary(current_client.id)
```

---

### 6️⃣ `backend/jobs/deadline_checker.py`

```python
"""
Deadline checker background job.
Runs daily to create reminder timeline events for upcoming deadlines.
"""
import asyncio
from datetime import date, timedelta
import structlog
from prometheus_client import Counter, Gauge

logger = structlog.get_logger(__name__)

# Metrics
deadlines_checked = Counter('deadline_checker_total', 'Total deadlines checked')
reminders_created = Counter('deadline_reminders_created',
                           'Reminder events created', ['type', 'urgency'])
job_last_run = Gauge('deadline_checker_last_run_timestamp', 'Last successful run')

# Reminder schedule
TAX_REMINDER_DAYS = [30, 14, 7, 1]
VISA_REMINDER_DAYS = [90, 60, 30]


async def check_tax_deadlines(db_pool) -> int:
    """
    Check all upcoming tax deadlines and create reminders.

    Reminder schedule:
    - 30 days before: info reminder
    - 14 days before: warning reminder
    - 7 days before: urgent reminder
    - 1 day before: critical reminder

    Returns:
        Number of reminders created
    """
    reminders_count = 0
    today = date.today()

    async with db_pool.acquire() as conn:
        for days in TAX_REMINDER_DAYS:
            target_date = today + timedelta(days=days)
            urgency = "critical" if days <= 7 else ("warning" if days <= 14 else "info")
            color = "error" if days <= 7 else ("warning" if days <= 14 else "info")

            # Find obligations due on target_date without existing reminder
            obligations = await conn.fetch("""
                SELECT t.* FROM tax_obligations t
                WHERE t.due_date = $1
                AND t.status IN ('upcoming', 'pending')
                AND NOT EXISTS (
                    SELECT 1 FROM timeline_events e
                    WHERE e.client_id = t.client_id
                    AND e.event_type = 'reminder'
                    AND e.title LIKE '%' || t.name || '%'
                    AND DATE(e.event_date) = $2
                )
            """, target_date, today)

            for ob in obligations:
                await conn.execute("""
                    INSERT INTO timeline_events
                    (client_id, event_type, title, description, event_date, color, client_visible)
                    VALUES ($1, 'reminder', $2, $3, NOW(), $4, true)
                """,
                    ob['client_id'],
                    f"Tax Reminder: {ob['name']}",
                    f"Due in {days} days ({target_date})",
                    color
                )
                reminders_count += 1
                reminders_created.labels(type="tax", urgency=urgency).inc()
                logger.info("Created tax reminder",
                           client_id=ob['client_id'], tax=ob['name'], days=days)

    return reminders_count


async def check_visa_expiry(db_pool) -> int:
    """
    Check all visa records for upcoming expiry.

    Actions:
    - 90 days before: send renewal notice
    - 60 days before: create renewal practice (if not exists)
    - 30 days before: update status to 'expiring_soon'

    Returns:
        Number of actions taken
    """
    actions_count = 0
    today = date.today()

    async with db_pool.acquire() as conn:
        # Update status to expiring_soon (30 days)
        result = await conn.execute("""
            UPDATE visa_records
            SET status = 'expiring_soon', updated_at = NOW()
            WHERE status = 'active'
            AND expiry_date <= $1
            AND expiry_date > $2
        """, today + timedelta(days=30), today)

        updated = int(result.split()[-1]) if result else 0
        if updated > 0:
            logger.info("Updated visas to expiring_soon", count=updated)
            actions_count += updated

        # Update status to expired
        result = await conn.execute("""
            UPDATE visa_records
            SET status = 'expired', updated_at = NOW()
            WHERE status IN ('active', 'expiring_soon')
            AND expiry_date < $1
        """, today)

        expired = int(result.split()[-1]) if result else 0
        if expired > 0:
            logger.info("Updated visas to expired", count=expired)
            actions_count += expired

        # Create reminders for expiring visas
        for days in VISA_REMINDER_DAYS:
            target_date = today + timedelta(days=days)
            urgency = "critical" if days <= 30 else ("warning" if days <= 60 else "info")

            visas = await conn.fetch("""
                SELECT v.* FROM visa_records v
                WHERE v.expiry_date = $1
                AND v.status IN ('active', 'expiring_soon')
                AND NOT EXISTS (
                    SELECT 1 FROM timeline_events e
                    WHERE e.client_id = v.client_id
                    AND e.event_type = 'reminder'
                    AND e.title LIKE '%Visa%'
                    AND DATE(e.event_date) = $2
                )
            """, target_date, today)

            for visa in visas:
                await conn.execute("""
                    INSERT INTO timeline_events
                    (client_id, event_type, title, description, event_date, color, client_visible)
                    VALUES ($1, 'reminder', $2, $3, NOW(), $4, true)
                """,
                    visa['client_id'],
                    f"Visa Expiry Reminder: {visa['visa_type']}",
                    f"Expires in {days} days ({target_date})",
                    "warning" if days > 30 else "error"
                )
                actions_count += 1
                reminders_created.labels(type="visa", urgency=urgency).inc()
                logger.info("Created visa reminder",
                           client_id=visa['client_id'], visa_type=visa['visa_type'], days=days)

    return actions_count


async def run_deadline_checker():
    """
    Main entry point for deadline checker job.
    Should be scheduled via cron or APScheduler.
    """
    logger.info("Starting deadline checker job")

    try:
        from backend.db.connection import get_db_pool
        db_pool = await get_db_pool()

        tax_reminders = await check_tax_deadlines(db_pool)
        visa_actions = await check_visa_expiry(db_pool)

        deadlines_checked.inc()
        job_last_run.set_to_current_time()

        logger.info(
            "Deadline checker completed",
            tax_reminders=tax_reminders,
            visa_actions=visa_actions
        )

        return {"tax_reminders": tax_reminders, "visa_actions": visa_actions}

    except Exception as e:
        logger.error("Deadline checker failed", error=str(e), exc_info=True)
        raise


# CLI entry point
if __name__ == "__main__":
    asyncio.run(run_deadline_checker())
```

---

## 📝 FILES DA MODIFICARE

### `backend/app/main.py` (o `main_cloud.py`)

**Aggiungi questi import:**

```python
from backend.app.routers import portal_taxes, portal_visa
```

**Registra i routers (cerca la sezione con `app.include_router`):**

```python
# Portal endpoints
app.include_router(portal_taxes.router)
app.include_router(portal_visa.router)
```

---

## ✅ CHECKLIST IMPLEMENTAZIONE

- [ ] Creato `backend/schemas/portal.py`
- [ ] Creato `backend/services/portal/tax_service.py`
- [ ] Creato `backend/services/portal/visa_service.py`
- [ ] Creato `backend/app/routers/portal_taxes.py`
- [ ] Creato `backend/app/routers/portal_visa.py`
- [ ] Creato `backend/jobs/deadline_checker.py`
- [ ] Aggiornato `backend/app/main.py` con nuovi routers
- [ ] Tutte le funzioni hanno type hints completi
- [ ] Tutte le funzioni hanno docstrings
- [ ] Logging strutturato su tutte le operazioni
- [ ] Prometheus metrics definiti
- [ ] Error handling con try/except
- [ ] Absolute imports (`from backend.services...`)
- [ ] Async/await per tutte le operazioni DB

---

## 🧪 VALIDATION COMMANDS

```bash
# 1. Activate virtualenv
cd /Users/antonellosiano/Projects/nuzantara/apps/backend-rag
source .venv/bin/activate

# 2. Syntax check (compile all new files)
python -m py_compile backend/schemas/portal.py
python -m py_compile backend/services/portal/tax_service.py
python -m py_compile backend/services/portal/visa_service.py
python -m py_compile backend/app/routers/portal_taxes.py
python -m py_compile backend/app/routers/portal_visa.py
python -m py_compile backend/jobs/deadline_checker.py

# 3. Run deadline checker manually (test job logic)
PYTHONPATH=. python -m backend.jobs.deadline_checker

# 4. Start server (test endpoints)
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 5. Test endpoints (in another terminal)
# GET /api/portal/taxes
# GET /api/portal/taxes/summary
# GET /api/portal/visa
# GET /api/portal/visa/summary
```

---

## 🎯 ACCEPTANCE CRITERIA

✅ **Endpoint `/api/portal/taxes`**

- Returns tax obligations for authenticated client
- Includes summary with `next_deadline`
- Filtered by `client_id` from JWT

✅ **Endpoint `/api/portal/visa`**

- Returns visa status for authenticated client
- Includes `current_visa` and `history`
- Shows related immigration practices

✅ **Deadline Checker Job**

- Creates `timeline_events` for upcoming deadlines
- Tax: 30/14/7/1 day reminders
- Visa: 90/60/30 day actions
- No duplicate reminders

✅ **Production-Ready Standard**

- All functions have type hints
- Structured logging on all operations
- Prometheus metrics for monitoring
- Error handling with graceful degradation

---

## ⚠️ CONSTRAINTS

- ❌ NEVER hardcode database credentials
- ❌ NEVER skip type hints
- ❌ NEVER create functions without docstrings
- ✅ ALWAYS use async for DB operations
- ✅ ALWAYS create timeline_events for status changes
- ✅ ALWAYS filter portal data by client_id from auth
- ✅ ALWAYS use absolute imports

---

## 📊 DATABASE SCHEMA REFERENCE

**Tables già esistenti (Migration 002):**

```sql
-- timeline_events: eventi visibili nel Portal
CREATE TABLE timeline_events (
    id SERIAL PRIMARY KEY,
    client_id INT NOT NULL,
    event_type VARCHAR(50),  -- deadline, milestone, reminder, etc.
    title VARCHAR(200),
    description TEXT,
    event_date TIMESTAMP,
    color VARCHAR(20),
    client_visible BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- tax_obligations: obblighi fiscali
CREATE TABLE tax_obligations (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT gen_random_uuid(),
    client_id INT NOT NULL,
    tax_type VARCHAR(50),
    name VARCHAR(200),
    frequency VARCHAR(20),
    period_start DATE,
    period_end DATE,
    due_date DATE,
    status VARCHAR(20),
    amount_due NUMERIC(12,2),
    amount_paid NUMERIC(12,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- visa_records: status immigrazione
CREATE TABLE visa_records (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT gen_random_uuid(),
    client_id INT NOT NULL,
    visa_type VARCHAR(50),
    status VARCHAR(20),
    issue_date DATE,
    expiry_date DATE,
    visa_number VARCHAR(100),
    sponsor_name VARCHAR(200),
    sponsor_type VARCHAR(50),
    practice_id INT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🚀 DEPLOYMENT NOTES

**Cron Job Schedule (da configurare dopo test):**

```bash
# Run deadline checker daily at 6 AM
0 6 * * * cd /path/to/backend && /path/to/.venv/bin/python -m backend.jobs.deadline_checker
```

**Environment Variables Required:**

```bash
DATABASE_URL=postgresql://user:pass@host:port/dbname
LOG_LEVEL=INFO
```

---

## 📚 ADDITIONAL CONTEXT

- **Portal Authentication**: Usa `get_current_portal_client` dependency
- **Portal Service Pattern**: Vedi `backend/services/portal/portal_service.py`
- **CRM Integration**: Vedi `backend/app/routers/crm_practices.py` per pattern timeline_events
- **Database Connection**: Pool asincrono via `get_db_pool()`

---

**Ready for Windsurf!** 🚀
