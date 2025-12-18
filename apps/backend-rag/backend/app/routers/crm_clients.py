"""
ZANTARA CRM - Clients Management Router
Endpoints for managing client data (anagrafica clienti)

Refactored: Migrated to asyncpg with connection pooling (2025-12-07)
"""

from datetime import datetime
from typing import Any

import asyncpg
from core.cache import cached
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, EmailStr, field_validator

from app.dependencies import get_database_pool
from app.utils.error_handlers import handle_database_error
from app.utils.logging_utils import get_logger, log_database_operation, log_success

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm/clients", tags=["crm-clients"])

# Constants
MAX_LIMIT = 200
DEFAULT_LIMIT = 50
STATUS_VALUES = {"active", "inactive", "prospect"}
CACHE_TTL_STATS_SECONDS = 300  # 5 minutes
STATS_DAYS_RECENT = 30  # Days for "recent" stats queries


# ================================================
# PYDANTIC MODELS
# ================================================


class ClientCreate(BaseModel):
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    whatsapp: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    client_type: str = "individual"  # 'individual' or 'company'
    assigned_to: str | None = None  # team member email
    address: str | None = None
    notes: str | None = None
    tags: list[str] = []
    custom_fields: dict = {}

    @field_validator("client_type")
    @classmethod
    def validate_client_type(cls, v: str) -> str:
        """Validate client_type is one of allowed values"""
        allowed_types = {"individual", "company"}
        if v not in allowed_types:
            raise ValueError(f"client_type must be one of {allowed_types}, got '{v}'")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """Validate full_name is not empty"""
        if not v or not v.strip():
            raise ValueError("full_name cannot be empty")
        if len(v) > 200:
            raise ValueError("full_name must be less than 200 characters")
        return v.strip()


class ClientUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    whatsapp: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    status: str | None = None  # 'active', 'inactive', 'prospect'
    client_type: str | None = None
    assigned_to: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    custom_fields: dict | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """Validate status is one of allowed values"""
        if v is not None and v not in STATUS_VALUES:
            raise ValueError(f"status must be one of {STATUS_VALUES}, got '{v}'")
        return v

    @field_validator("client_type")
    @classmethod
    def validate_client_type(cls, v: str | None) -> str | None:
        """Validate client_type is one of allowed values"""
        allowed_types = {"individual", "company"}
        if v is not None and v not in allowed_types:
            raise ValueError(f"client_type must be one of {allowed_types}, got '{v}'")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str | None) -> str | None:
        """Validate full_name if provided"""
        if v is not None:
            if not v.strip():
                raise ValueError("full_name cannot be empty")
            if len(v) > 200:
                raise ValueError("full_name must be less than 200 characters")
            return v.strip()
        return v


class ClientResponse(BaseModel):
    id: int
    uuid: str
    full_name: str
    email: str | None
    phone: str | None
    whatsapp: str | None
    nationality: str | None
    status: str
    client_type: str
    assigned_to: str | None
    first_contact_date: datetime | None
    last_interaction_date: datetime | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


# ================================================
# ENDPOINTS
# ================================================


@router.post("/", response_model=ClientResponse)
async def create_client(
    client: ClientCreate,
    created_by: str = Query(..., description="Team member email creating this client"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Create a new client

    - **full_name**: Client's full name (required)
    - **email**: Email address (optional but recommended)
    - **phone**: Phone number
    - **whatsapp**: WhatsApp number (can be same as phone)
    - **nationality**: Client's nationality
    - **passport_number**: Passport number
    - **assigned_to**: Team member email to assign client to
    - **tags**: Array of tags (e.g., ['vip', 'urgent'])
    """
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO clients (
                    full_name, email, phone, whatsapp, nationality, passport_number,
                    client_type, assigned_to, address, notes, tags, custom_fields,
                    first_contact_date, created_by, status
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
                )
                RETURNING *
                """,
                client.full_name,
                client.email,
                client.phone,
                client.whatsapp,
                client.nationality,
                client.passport_number,
                client.client_type,
                client.assigned_to,
                client.address,
                client.notes,
                client.tags,
                client.custom_fields,
                datetime.now(),
                created_by,
                "active",
            )

            if not row:
                raise HTTPException(status_code=500, detail="Failed to create client")

            new_client = dict(row)
            log_success(logger, f"Created client: {client.full_name}", client_id=new_client["id"])
            log_database_operation(logger, "CREATE", "clients", record_id=new_client["id"])
            return ClientResponse(**new_client)

    except asyncpg.UniqueViolationError as e:
        logger.warning(f"Integrity error creating client: {e}")
        raise HTTPException(
            status_code=400, detail="Client with this email or phone already exists"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/", response_model=list[ClientResponse])
async def list_clients(
    status: str | None = Query(
        None,
        description="Filter by status: active, inactive, prospect",
        regex="^(active|inactive|prospect)$",
    ),
    assigned_to: str | None = Query(None, description="Filter by assigned team member email"),
    search: str | None = Query(None, description="Search by name, email, or phone"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    List all clients with optional filtering

    - **status**: Filter by client status
    - **assigned_to**: Filter by assigned team member
    - **search**: Search in name, email, phone fields
    - **limit**: Max results (default: 50, max: 200)
    - **offset**: For pagination
    """
    try:
        async with db_pool.acquire() as conn:
            # Build query dynamically with explicit columns
            query_parts = [
                """SELECT id, uuid, full_name, email, phone, whatsapp, nationality, status,
                   client_type, assigned_to, first_contact_date, last_interaction_date,
                   tags, created_at, updated_at FROM clients WHERE 1=1"""
            ]
            params: list[Any] = []
            param_index = 1

            if status:
                query_parts.append(f" AND status = ${param_index}")
                params.append(status)
                param_index += 1

            if assigned_to:
                query_parts.append(f" AND assigned_to = ${param_index}")
                params.append(assigned_to)
                param_index += 1

            if search:
                search_pattern = f"%{search}%"
                query_parts.append(
                    f" AND (full_name ILIKE ${param_index} OR email ILIKE ${param_index + 1} OR phone ILIKE ${param_index + 2})"
                )
                params.extend([search_pattern, search_pattern, search_pattern])
                param_index += 3

            query_parts.append(
                f" ORDER BY created_at DESC LIMIT ${param_index} OFFSET ${param_index + 1}"
            )
            params.extend([limit, offset])

            query = " ".join(query_parts)
            rows = await conn.fetch(query, *params)

            return [ClientResponse(**dict(row)) for row in rows]

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int = Path(..., gt=0, description="Client ID"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get client by ID"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, uuid, full_name, email, phone, whatsapp, nationality, status,
                   client_type, assigned_to, first_contact_date, last_interaction_date,
                   tags, created_at, updated_at FROM clients WHERE id = $1""",
                client_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Client not found")

            return ClientResponse(**dict(row))

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/by-email/{email}", response_model=ClientResponse)
async def get_client_by_email(
    email: EmailStr = Path(..., description="Client email address"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get client by email address"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, uuid, full_name, email, phone, whatsapp, nationality, status,
                   client_type, assigned_to, first_contact_date, last_interaction_date,
                   tags, created_at, updated_at FROM clients WHERE email = $1""",
                email,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Client not found")

            return ClientResponse(**dict(row))

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int = Path(..., gt=0, description="Client ID"),
    updates: ClientUpdate = ...,
    updated_by: str = Query(..., description="Team member making the update"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Update client information

    Only provided fields will be updated. Other fields remain unchanged.
    """
    try:
        async with db_pool.acquire() as conn:
            # Build update query dynamically
            update_fields: list[str] = []
            params: list[Any] = []
            param_index = 1

            # Map of allowed fields to database columns
            field_mapping = {
                "full_name": "full_name",
                "email": "email",
                "phone": "phone",
                "whatsapp": "whatsapp",
                "nationality": "nationality",
                "passport_number": "passport_number",
                "status": "status",
                "client_type": "client_type",
                "assigned_to": "assigned_to",
                "address": "address",
                "notes": "notes",
                "tags": "tags",
                "custom_fields": "custom_fields",
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
                UPDATE clients
                SET {update_fields_str}
                WHERE id = ${param_index}
                RETURNING *
            """
            params.append(client_id)

            row = await conn.fetchrow(query, *params)  # nosemgrep

            if not row:
                raise HTTPException(status_code=404, detail="Client not found")

            # Log activity
            updated_fields = ", ".join(updates.dict(exclude_unset=True).keys())
            await conn.execute(
                """
                INSERT INTO activity_log (entity_type, entity_id, action, performed_by, description)
                VALUES ($1, $2, $3, $4, $5)
                """,
                "client",
                client_id,
                "updated",
                updated_by,
                f"Updated fields: {updated_fields}",
            )

            log_success(
                logger,
                "Updated client",
                client_id=client_id,
                updated_by=updated_by,
            )
            return ClientResponse(**dict(row))

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.delete("/{client_id}")
async def delete_client(
    client_id: int = Path(..., gt=0, description="Client ID"),
    deleted_by: str = Query(..., description="Team member deleting the client"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Delete a client (soft delete - marks as inactive)

    This doesn't permanently delete the client, just marks them as inactive.
    Use with caution as this will also affect related practices and interactions.
    """
    try:
        async with db_pool.acquire() as conn:
            # Soft delete (mark as inactive)
            row = await conn.fetchrow(
                """
                UPDATE clients
                SET status = 'inactive', updated_at = NOW()
                WHERE id = $1
                RETURNING id
                """,
                client_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Client not found")

            # Log activity
            await conn.execute(
                """
                INSERT INTO activity_log (entity_type, entity_id, action, performed_by, description)
                VALUES ($1, $2, $3, $4, $5)
                """,
                "client",
                client_id,
                "deleted",
                deleted_by,
                "Client marked as inactive",
            )

            log_success(
                logger,
                "Deleted (soft) client",
                client_id=client_id,
                deleted_by=deleted_by,
            )
            return {"success": True, "message": "Client marked as inactive"}

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/{client_id}/summary")
async def get_client_summary(
    client_id: int = Path(..., gt=0, description="Client ID"),
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get comprehensive client summary including:
    - Basic client info
    - All practices (active + completed)
    - Recent interactions
    - Documents
    - Upcoming renewals
    """
    try:
        async with db_pool.acquire() as conn:
            # Get client basic info
            client_row = await conn.fetchrow(
                """SELECT id, uuid, full_name, email, phone, whatsapp, nationality, status,
                   client_type, assigned_to, first_contact_date, last_interaction_date,
                   tags, created_at, updated_at FROM clients WHERE id = $1""",
                client_id,
            )

            if not client_row:
                raise HTTPException(status_code=404, detail="Client not found")

            # Get practices
            practices_rows = await conn.fetch(
                """
                SELECT p.*, pt.name as practice_type_name, pt.category
                FROM practices p
                JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE p.client_id = $1
                ORDER BY p.created_at DESC
                """,
                client_id,
            )

            # Get recent interactions
            interactions_rows = await conn.fetch(
                """
                SELECT id, client_id, practice_id, conversation_id, interaction_type, channel,
                       subject, summary, full_content, sentiment, team_member, direction,
                       duration_minutes, extracted_entities, action_items, interaction_date, created_at
                FROM interactions
                WHERE client_id = $1
                ORDER BY interaction_date DESC
                LIMIT 10
                """,
                client_id,
            )

            # Get upcoming renewals
            renewals_rows = await conn.fetch(
                """
                SELECT *
                FROM renewal_alerts
                WHERE client_id = $1 AND status = 'pending'
                ORDER BY alert_date ASC
                """,
                client_id,
            )

            practices = [dict(row) for row in practices_rows]
            interactions = [dict(row) for row in interactions_rows]
            renewals = [dict(row) for row in renewals_rows]

            return {
                "client": dict(client_row),
                "practices": {
                    "total": len(practices),
                    "active": len(
                        [
                            p
                            for p in practices
                            if p["status"]
                            in ["inquiry", "in_progress", "waiting_documents", "submitted_to_gov"]
                        ]
                    ),
                    "completed": len([p for p in practices if p["status"] == "completed"]),
                    "list": practices,
                },
                "interactions": {"total": len(interactions), "recent": interactions},
                "renewals": {"upcoming": renewals},
            }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/stats/overview")
@cached(ttl=CACHE_TTL_STATS_SECONDS, prefix="crm_clients_stats")
async def get_clients_stats(
    request: Request = ...,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get overall client statistics

    Returns counts by status, top assigned team members, etc.

    Performance: Cached for 5 minutes to reduce database load.
    """
    try:
        async with db_pool.acquire() as conn:
            # Total clients by status
            by_status_rows = await conn.fetch(
                """
                SELECT status, COUNT(*) as count
                FROM clients
                GROUP BY status
                """
            )

            # Clients by assigned team member
            by_team_member_rows = await conn.fetch(
                """
                SELECT assigned_to, COUNT(*) as count
                FROM clients
                WHERE assigned_to IS NOT NULL
                GROUP BY assigned_to
                ORDER BY count DESC
                """
            )

            # New clients last N days
            new_last_30_days_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM clients
                WHERE created_at >= NOW() - INTERVAL '1 day' * $1
                """,
                STATS_DAYS_RECENT,
            )

            by_status = {row["status"]: row["count"] for row in by_status_rows}
            by_team_member = [dict(row) for row in by_team_member_rows]
            new_last_30_days = new_last_30_days_row["count"] if new_last_30_days_row else 0

            return {
                "total": sum(by_status.values()),
                "by_status": by_status,
                "by_team_member": by_team_member,
                "new_last_30_days": new_last_30_days,
            }

    except Exception as e:
        raise handle_database_error(e)
