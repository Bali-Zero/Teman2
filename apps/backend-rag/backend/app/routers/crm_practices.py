"""
ZANTARA CRM - Practices Management Router
Endpoints for managing practices (KITAS, PT PMA, Visas, etc.)

Refactored: Migrated to asyncpg with connection pooling (2025-12-07)
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import asyncpg
from core.cache import cached
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, field_validator

from app.dependencies import get_database_pool
from app.utils.error_handlers import handle_database_error
from app.utils.logging_utils import get_logger, log_database_operation, log_success

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm/practices", tags=["crm-practices"])

# Constants
MAX_LIMIT = 200
DEFAULT_LIMIT = 50
CACHE_TTL_STATS_SECONDS = 300  # 5 minutes
DEFAULT_EXPIRY_LOOKAHEAD_DAYS = 90
MAX_EXPIRY_LOOKAHEAD_DAYS = 365
PRIORITY_VALUES = {"low", "normal", "high", "urgent"}
STATUS_VALUES = {
    "inquiry",
    "quotation_sent",
    "payment_pending",
    "in_progress",
    "waiting_documents",
    "submitted_to_gov",
    "approved",
    "completed",
    "cancelled",
}


# ================================================
# PYDANTIC MODELS
# ================================================


class PracticeCreate(BaseModel):
    client_id: int
    practice_type_code: str  # Practice type code retrieved from database
    status: str = "inquiry"
    priority: str = "normal"  # 'low', 'normal', 'high', 'urgent'
    quoted_price: Decimal | None = None
    assigned_to: str | None = None  # team member email
    notes: str | None = None
    internal_notes: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of allowed values"""
        if v not in STATUS_VALUES:
            raise ValueError(f"status must be one of {STATUS_VALUES}, got '{v}'")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """Validate priority is one of allowed values"""
        if v not in PRIORITY_VALUES:
            raise ValueError(f"priority must be one of {PRIORITY_VALUES}, got '{v}'")
        return v

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, v: int) -> int:
        """Validate client_id is positive"""
        if v <= 0:
            raise ValueError("client_id must be positive")
        return v

    @field_validator("quoted_price")
    @classmethod
    def validate_quoted_price(cls, v: Decimal | None) -> Decimal | None:
        """Validate quoted_price is non-negative"""
        if v is not None and v < 0:
            raise ValueError("quoted_price must be non-negative")
        return v


class PracticeUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    quoted_price: Decimal | None = None
    actual_price: Decimal | None = None
    payment_status: str | None = None
    paid_amount: Decimal | None = None
    assigned_to: str | None = None
    start_date: datetime | None = None
    completion_date: datetime | None = None
    expiry_date: date | None = None
    notes: str | None = None
    internal_notes: str | None = None
    documents: list[dict] | None = None
    missing_documents: list[str] | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """Validate status is one of allowed values"""
        if v is not None and v not in STATUS_VALUES:
            raise ValueError(f"status must be one of {STATUS_VALUES}, got '{v}'")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        """Validate priority is one of allowed values"""
        if v is not None and v not in PRIORITY_VALUES:
            raise ValueError(f"priority must be one of {PRIORITY_VALUES}, got '{v}'")
        return v

    @field_validator("quoted_price", "actual_price", "paid_amount")
    @classmethod
    def validate_price_fields(cls, v: Decimal | None) -> Decimal | None:
        """Validate price fields are non-negative"""
        if v is not None and v < 0:
            raise ValueError("Price fields must be non-negative")
        return v


class PracticeResponse(BaseModel):
    id: int
    uuid: str
    client_id: int
    practice_type_id: int
    status: str
    priority: str
    quoted_price: Decimal | None
    actual_price: Decimal | None
    payment_status: str
    assigned_to: str | None
    start_date: datetime | None
    completion_date: datetime | None
    expiry_date: date | None
    created_at: datetime


# ================================================
# ENDPOINTS
# ================================================


@router.post("/", response_model=PracticeResponse)
async def create_practice(
    practice: PracticeCreate,
    created_by: str = Query(..., description="Team member creating this practice"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Create a new practice for a client

    - **client_id**: ID of the client
    - **practice_type_code**: Practice type code (retrieved from database)
    - **status**: Initial status (default: 'inquiry')
    - **quoted_price**: Price quoted to client
    - **assigned_to**: Team member email to handle this
    """
    try:
        async with db_pool.acquire() as conn:
            # Get practice_type_id from code
            practice_type_row = await conn.fetchrow(
                "SELECT id, base_price FROM practice_types WHERE code = $1",
                practice.practice_type_code,
            )

            if not practice_type_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Practice type '{practice.practice_type_code}' not found",
                )

            # Use base_price if no quoted price provided
            quoted_price = practice.quoted_price or practice_type_row["base_price"]

            # Insert practice
            practice_row = await conn.fetchrow(
                """
                INSERT INTO practices (
                    client_id, practice_type_id, status, priority,
                    quoted_price, assigned_to, notes, internal_notes,
                    inquiry_date, created_by
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
                )
                RETURNING *
                """,
                practice.client_id,
                practice_type_row["id"],
                practice.status,
                practice.priority,
                quoted_price,
                practice.assigned_to,
                practice.notes,
                practice.internal_notes,
                datetime.now(),
                created_by,
            )

            if not practice_row:
                raise HTTPException(status_code=500, detail="Failed to create practice")

            new_practice = dict(practice_row)

            # Update client's last_interaction_date
            await conn.execute(
                """
                UPDATE clients
                SET last_interaction_date = NOW()
                WHERE id = $1
                """,
                practice.client_id,
            )

            # Log activity
            await conn.execute(
                """
                INSERT INTO activity_log (entity_type, entity_id, action, performed_by, description)
                VALUES ($1, $2, $3, $4, $5)
                """,
                "practice",
                new_practice["id"],
                "created",
                created_by,
                f"New {practice.practice_type_code} practice created",
            )

            log_success(
                logger,
                f"Created practice: {practice.practice_type_code}",
                practice_id=new_practice["id"],
                client_id=practice.client_id,
            )
            log_database_operation(logger, "CREATE", "practices", record_id=new_practice["id"])

            return PracticeResponse(**new_practice)

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/", response_model=list[dict])
async def list_practices(
    client_id: int | None = Query(None, description="Filter by client ID"),
    status: str | None = Query(None, description="Filter by status"),
    assigned_to: str | None = Query(None, description="Filter by assigned team member"),
    practice_type: str | None = Query(None, description="Filter by practice type code"),
    priority: str | None = Query(None, description="Filter by priority"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    List practices with optional filtering

    Returns practices with client and practice type information joined
    """
    try:
        async with db_pool.acquire() as conn:
            # Build query dynamically
            query_parts = [
                """
                SELECT
                    p.*,
                    c.full_name as client_name,
                    c.email as client_email,
                    c.phone as client_phone,
                    pt.name as practice_type_name,
                    pt.code as practice_type_code,
                    pt.category as practice_category
                FROM practices p
                JOIN clients c ON p.client_id = c.id
                JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE 1=1
                """
            ]
            params: list[Any] = []
            param_index = 1

            if client_id:
                query_parts.append(f" AND p.client_id = ${param_index}")
                params.append(client_id)
                param_index += 1

            if status:
                query_parts.append(f" AND p.status = ${param_index}")
                params.append(status)
                param_index += 1

            if assigned_to:
                query_parts.append(f" AND p.assigned_to = ${param_index}")
                params.append(assigned_to)
                param_index += 1

            if practice_type:
                query_parts.append(f" AND pt.code = ${param_index}")
                params.append(practice_type)
                param_index += 1

            if priority:
                query_parts.append(f" AND p.priority = ${param_index}")
                params.append(priority)
                param_index += 1

            query_parts.append(
                f" ORDER BY p.created_at DESC LIMIT ${param_index} OFFSET ${param_index + 1}"
            )
            params.extend([limit, offset])

            query = " ".join(query_parts)
            rows = await conn.fetch(query, *params)

            return [dict(row) for row in rows]

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/active")
async def get_active_practices(
    assigned_to: str | None = Query(None),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get all active practices (in progress, not completed/cancelled)

    Optionally filter by assigned team member
    """
    try:
        async with db_pool.acquire() as conn:
            query_parts = ["SELECT * FROM active_practices_view WHERE 1=1"]
            params: list[Any] = []
            param_index = 1

            if assigned_to:
                query_parts.append(f" AND assigned_to = ${param_index}")
                params.append(assigned_to)

            query_parts.append(" ORDER BY priority DESC, start_date ASC")
            query = " ".join(query_parts)

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    except Exception as e:
        raise handle_database_error(e)


@router.get("/renewals/upcoming")
async def get_upcoming_renewals(
    days: int = Query(
        DEFAULT_EXPIRY_LOOKAHEAD_DAYS,
        ge=1,
        le=MAX_EXPIRY_LOOKAHEAD_DAYS,
        description="Days to look ahead",
    ),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get practices with upcoming renewal dates

    Default: next 90 days
    """
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM upcoming_renewals_view")
            return [dict(row) for row in rows]

    except Exception as e:
        raise handle_database_error(e)


@router.get("/{practice_id}")
async def get_practice(
    practice_id: int = Path(..., gt=0, description="Practice ID"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get practice details by ID with full client and type info"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    p.*,
                    c.full_name as client_name,
                    c.email as client_email,
                    c.phone as client_phone,
                    pt.name as practice_type_name,
                    pt.code as practice_type_code,
                    pt.category as practice_category,
                    pt.required_documents as required_documents
                FROM practices p
                JOIN clients c ON p.client_id = c.id
                JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE p.id = $1
                """,
                practice_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Practice not found")

            return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.patch("/{practice_id}")
async def update_practice(
    practice_id: int = Path(..., gt=0, description="Practice ID"),
    updates: PracticeUpdate = ...,
    updated_by: str = Query(..., description="Team member making the update"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Update practice information

    Common status values:
    - inquiry
    - quotation_sent
    - payment_pending
    - in_progress
    - waiting_documents
    - submitted_to_gov
    - approved
    - completed
    - cancelled
    """
    try:
        async with db_pool.acquire() as conn:
            # Build update query dynamically
            update_fields: list[str] = []
            params: list[Any] = []
            param_index = 1

            # Map of allowed fields to database columns
            field_mapping = {
                "status": "status",
                "priority": "priority",
                "quoted_price": "quoted_price",
                "actual_price": "actual_price",
                "payment_status": "payment_status",
                "paid_amount": "paid_amount",
                "assigned_to": "assigned_to",
                "start_date": "start_date",
                "completion_date": "completion_date",
                "expiry_date": "expiry_date",
                "notes": "notes",
                "internal_notes": "internal_notes",
                "documents": "documents",
                "missing_documents": "missing_documents",
            }

            for field, value in updates.dict(exclude_unset=True).items():
                if field not in field_mapping:
                    raise HTTPException(status_code=400, detail=f"Invalid field name: {field}")

                if value is not None:
                    column_name = field_mapping[field]
                    update_fields.append(f"{column_name} = ${param_index}")
                    params.append(value)
                    param_index += 1

            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")

            # Add updated_at
            update_fields.append("updated_at = NOW()")
            update_fields_str = ", ".join(update_fields)

            # Column names are from a whitelist (field_mapping), values are parameterized
            # nosemgrep: sqlalchemy-execute-raw-query
            query = f"""
                UPDATE practices
                SET {update_fields_str}
                WHERE id = ${param_index}
                RETURNING *
            """
            params.append(practice_id)

            row = await conn.fetchrow(query, *params)  # nosemgrep

            if not row:
                raise HTTPException(status_code=404, detail="Practice not found")

            updated_practice = dict(row)

            # Log activity
            changed_fields = list(updates.dict(exclude_unset=True).keys())
            await conn.execute(
                """
                INSERT INTO activity_log (entity_type, entity_id, action, performed_by, description, changes)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                "practice",
                practice_id,
                "updated",
                updated_by,
                f"Updated: {', '.join(changed_fields)}",
                updates.dict(exclude_unset=True),
            )

            # If status changed to 'completed' and there's an expiry date, create renewal alert
            if updates.status == "completed" and updates.expiry_date:
                alert_date = updates.expiry_date - timedelta(days=60)  # 60 days before expiry

                await conn.execute(
                    """
                    INSERT INTO renewal_alerts (
                        practice_id, client_id, alert_type, description,
                        target_date, alert_date, notify_team_member
                    )
                    SELECT
                        $1, client_id, 'renewal_due',
                        'Practice renewal due soon',
                        $2, $3, assigned_to
                    FROM practices
                    WHERE id = $4
                    """,
                    practice_id,
                    updates.expiry_date,
                    alert_date,
                    practice_id,
                )

            log_success(
                logger,
                "Updated practice",
                practice_id=practice_id,
                updated_by=updated_by,
            )
            return updated_practice

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.post("/{practice_id}/documents/add")
async def add_document_to_practice(
    practice_id: int = Path(..., gt=0, description="Practice ID"),
    document_name: str = Query(...),
    drive_file_id: str = Query(...),
    uploaded_by: str = Query(...),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Add a document to a practice

    - **document_name**: Name/type of document (e.g., "Passport Copy")
    - **drive_file_id**: Google Drive file ID
    - **uploaded_by**: Email of person uploading
    """
    try:
        async with db_pool.acquire() as conn:
            # Get current documents
            row = await conn.fetchrow("SELECT documents FROM practices WHERE id = $1", practice_id)

            if not row:
                raise HTTPException(status_code=404, detail="Practice not found")

            documents = row["documents"] or []

            # Add new document
            new_doc = {
                "name": document_name,
                "drive_file_id": drive_file_id,
                "uploaded_at": datetime.now().isoformat(),
                "uploaded_by": uploaded_by,
                "status": "received",
            }

            documents.append(new_doc)

            # Update practice
            await conn.execute(
                """
                UPDATE practices
                SET documents = $1, updated_at = NOW()
                WHERE id = $2
                """,
                documents,
                practice_id,
            )

            log_success(
                logger,
                "Added document to practice",
                practice_id=practice_id,
                document_name=document_name,
            )

            return {"success": True, "document": new_doc, "total_documents": len(documents)}

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/stats/overview")
@cached(ttl=CACHE_TTL_STATS_SECONDS, prefix="crm_practices_stats")
async def get_practices_stats(
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get overall practice statistics

    - Counts by status
    - Counts by practice type
    - Revenue metrics

    Performance: Cached for 5 minutes to reduce database load.
    """
    try:
        async with db_pool.acquire() as conn:
            # By status
            by_status_rows = await conn.fetch(
                """
                SELECT status, COUNT(*) as count
                FROM practices
                GROUP BY status
                """
            )

            # By practice type
            by_type_rows = await conn.fetch(
                """
                SELECT pt.code, pt.name, COUNT(p.id) as count
                FROM practices p
                JOIN practice_types pt ON p.practice_type_id = pt.id
                GROUP BY pt.code, pt.name
                ORDER BY count DESC
                """
            )

            # Revenue stats
            revenue_row = await conn.fetchrow(
                """
                SELECT
                    SUM(actual_price) as total_revenue,
                    SUM(CASE WHEN payment_status = 'paid' THEN actual_price ELSE 0 END) as paid_revenue,
                    SUM(CASE WHEN payment_status IN ('unpaid', 'partial') THEN actual_price - COALESCE(paid_amount, 0) ELSE 0 END) as outstanding_revenue
                FROM practices
                WHERE actual_price IS NOT NULL
                """
            )

            # Active practices count
            active_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM practices
                WHERE status IN ('inquiry', 'in_progress', 'waiting_documents', 'submitted_to_gov')
                """
            )

            by_status = {row["status"]: row["count"] for row in by_status_rows}
            by_type = [dict(row) for row in by_type_rows]
            revenue = dict(revenue_row) if revenue_row else {}
            active_count = active_row["count"] if active_row else 0

            return {
                "total_practices": sum(by_status.values()),
                "active_practices": active_count,
                "by_status": by_status,
                "by_type": by_type,
                "revenue": revenue,
            }

    except Exception as e:
        raise handle_database_error(e)
