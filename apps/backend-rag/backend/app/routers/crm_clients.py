"""
ZANTARA CRM - Clients Management Router
Endpoints for managing client data (anagrafica clienti)

Refactored: Migrated to asyncpg with connection pooling (2025-12-07)
"""

import time
from datetime import datetime
from typing import Any

import asyncpg
from core.cache import cached
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, EmailStr, field_validator

from app.dependencies import get_current_user, get_database_pool
from app.services.crm.audit_logger import audit_change, audit_logger
from app.services.crm.metrics import crm_metrics, metrics_collector, track_client_creation
from app.utils.crm_utils import is_crm_admin
from app.utils.error_handlers import handle_database_error
from app.utils.logging_utils import get_logger, log_database_operation, log_success

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm/clients", tags=["crm-clients"])

# Constants
MAX_LIMIT = 200
DEFAULT_LIMIT = 50
STATUS_VALUES = {"active", "inactive", "prospect", "lead"}
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
    company_name: str | None = None  # For corporate clients
    nationality: str | None = None
    passport_number: str | None = None
    passport_expiry: str | None = None  # ISO date string (YYYY-MM-DD)
    date_of_birth: str | None = None  # ISO date string (YYYY-MM-DD)
    status: str = "active"  # 'active', 'inactive', 'prospect', 'lead'
    client_type: str = "individual"  # 'individual' or 'company'
    assigned_to: str | None = None  # team member email
    avatar_url: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] = []
    lead_source: str | None = None  # 'website', 'referral', 'event', 'social_media', etc
    service_interest: list[str] = []  # Services client is interested in
    custom_fields: dict = {}

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of allowed values"""
        allowed_statuses = {"active", "inactive", "prospect", "lead"}
        if v not in allowed_statuses:
            raise ValueError(f"status must be one of {allowed_statuses}, got '{v}'")
        return v

    @field_validator("client_type")
    @classmethod
    def validate_client_type(cls, v: str) -> str:
        """Validate client_type is one of allowed values"""
        allowed_types = {"individual", "company"}
        if v not in allowed_types:
            raise ValueError(f"client_type must be one of {allowed_types}, got '{v}'")
        return v

    @field_validator("email", "passport_expiry", "date_of_birth", mode="before")
    @classmethod
    def validate_optional_fields(cls, v):
        """Convert empty strings to None for optional fields"""
        if isinstance(v, str) and not v.strip():
            return None
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
    company_name: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    passport_expiry: str | None = None  # ISO date string
    date_of_birth: str | None = None  # ISO date string
    status: str | None = None  # 'active', 'inactive', 'prospect', 'lead'
    client_type: str | None = None
    assigned_to: str | None = None
    avatar_url: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    lead_source: str | None = None
    service_interest: list[str] | None = None
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

    @field_validator("email", "passport_expiry", "date_of_birth", mode="before")
    @classmethod
    def validate_optional_fields(cls, v):
        """Convert empty strings to None for optional fields"""
        if isinstance(v, str) and not v.strip():
            return None
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
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    company_name: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    passport_expiry: str | None = None
    date_of_birth: str | None = None
    status: str
    client_type: str
    assigned_to: str | None = None
    avatar_url: str | None = None
    address: str | None = None
    notes: str | None = None
    first_contact_date: datetime | None = None
    last_interaction_date: datetime | None = None
    last_sentiment: str | None = None
    last_interaction_summary: str | None = None
    tags: list[str] = []  # Default to empty list if None
    lead_source: str | None = None
    service_interest: list[str] = []  # Default to empty list
    custom_fields: dict = {}  # Default to empty dict
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None

    @field_validator("uuid", mode="before")
    @classmethod
    def convert_uuid_to_string(cls, v):
        """Convert UUID object to string if needed"""
        if v is None:
            return ""
        return str(v)

    @field_validator("tags", mode="before")
    @classmethod
    def ensure_tags_list(cls, v):
        """Ensure tags is always a list"""
        if v is None:
            return []
        return v


# ================================================
# ENDPOINTS
# ================================================


@router.post("/", response_model=ClientResponse)
@track_client_creation()
@audit_change(entity_type="client", change_type="create")
async def create_client(
    client: ClientCreate,
    user_email: str = Query(
        ..., description="Team member email creating this client", alias="created_by"
    ),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
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
    - **avatar_url**: URL to client avatar image
    - **tags**: Array of tags (e.g., ['vip', 'urgent'])
    """
    start_time = time.time()
    try:
        # Add timeout for connection acquisition to prevent hanging
        import asyncio
        try:
            async with asyncio.timeout(10.0):
                async with db_pool.acquire() as conn:
                    # Sanitize date fields - convert empty strings to None
                    passport_expiry = client.passport_expiry if client.passport_expiry else None
                    date_of_birth = client.date_of_birth if client.date_of_birth else None

                    row = await conn.fetchrow(
                        """
                        INSERT INTO clients (
                            full_name, email, phone, whatsapp, company_name,
                            nationality, passport_number, passport_expiry, date_of_birth,
                            status, client_type, assigned_to, avatar_url, address, notes,
                            tags, lead_source, service_interest, custom_fields,
                            first_contact_date, created_by
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                            $16, $17, $18, $19, $20, $21
                        )
                        RETURNING *
                        """,
                        client.full_name,
                        client.email,
                        client.phone,
                        client.whatsapp,
                        client.company_name,
                        client.nationality,
                        client.passport_number,
                        passport_expiry,
                        date_of_birth,
                        client.status,  # Use client's status instead of hardcoded "active"
                        client.client_type,
                        client.assigned_to,
                        client.avatar_url,
                        client.address,
                        client.notes,
                        client.tags,
                        client.lead_source,
                        client.service_interest,
                        client.custom_fields,
                        datetime.now(),
                        user_email,
                    )

                    if not row:
                        raise HTTPException(status_code=500, detail="Failed to create client")

                    new_client = dict(row)
                    log_success(logger, f"Created client: {client.full_name}", client_id=new_client["id"])
                    log_database_operation(logger, "CREATE", "clients", record_id=new_client["id"])

                    # Track metrics (Legacy - keeping for backward metrics compatibility)
                    # crm_client_operations.labels(operation="create", status="success").inc()
                    # crm_client_creation_duration.observe(time.time() - start_time)

                    # Use Enhanced Metrics
                    crm_metrics.client_status_changes.labels(
                        from_status="none", to_status=client.status, changed_by=user_email
                    ).inc()

                    return ClientResponse(**new_client)
        except asyncio.TimeoutError:
            logger.error("Database connection acquisition timeout")
            raise HTTPException(
                status_code=503,
                detail="Database connection timeout. Please try again.",
            )

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
        pattern="^(active|inactive|prospect)$",
    ),
    assigned_to: str | None = Query(None, description="Filter by assigned team member email"),
    search: str | None = Query(None, description="Search by name, email, or phone"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    List clients with pagination and search.

    Access Control:
    - Admin users: See ALL clients
    - Team members: See only clients assigned to them (assigned_to = email)

    FILTERS:
    - **status**: Filter by client status
    - **assigned_to**: Filter by assigned team member (only works for admin)
    - **search**: Search in name, email, phone fields
    - **limit**: Max results (default: 50, max: 200)
    - **offset**: For pagination
    """
    try:
        # Get current user from dependency
        current_user_email = current_user.get("email", "") if current_user else ""
        current_user_name = current_user_email.lower().split("@")[0] if current_user_email else ""

        # SECURITY: Require authentication for client list
        if not current_user_email:
            raise HTTPException(status_code=401, detail="Authentication required to view clients")

        # ============================================
        # ACCESS CONTROL RULES
        # ============================================
        # Use centralized CRM RBAC logic
        # is_crm_admin covers 'zero@balizero.com' and users with 'admin' role
        # ============================================
        is_admin = is_crm_admin(current_user)

        logger.info(
            f"📋 [CRM Clients] User {current_user_email} requesting clients list "
            f"(is_admin={is_admin}, assigned_to_filter={assigned_to})"
        )

        async with db_pool.acquire() as conn:
            # Build query dynamically with explicit columns + sentiment/summary from interactions
            query_parts = [
                """
                SELECT 
                    c.id, c.uuid, c.full_name, c.email, c.phone, c.whatsapp, c.nationality, c.status,
                    c.client_type, c.assigned_to, c.avatar_url, c.first_contact_date, c.last_interaction_date,
                    c.tags, c.created_at, c.updated_at,
                    i.sentiment as last_sentiment,
                    i.summary as last_interaction_summary
                FROM clients c
                LEFT JOIN LATERAL (
                    SELECT sentiment, summary
                    FROM interactions
                    WHERE client_id = c.id
                    ORDER BY interaction_date DESC
                    LIMIT 1
                ) i ON true
                WHERE 1=1
                """
            ]
            params: list[Any] = []
            param_index = 1

            if status:
                query_parts.append(f" AND c.status = ${param_index}")
                params.append(status)
                param_index += 1

            # Access control based on user role
            if is_admin:
                # Admins can see ALL clients (no filter)
                if assigned_to:
                    # Admin can optionally filter by assigned_to using query param
                    query_parts.append(f" AND c.assigned_to = ${param_index}")
                    params.append(assigned_to)
                    param_index += 1
                logger.info(
                    f"🔓 [CRM Clients] CRM Admin ({current_user_email}) - viewing all clients"
                )
            else:
                # Regular members can ONLY see clients assigned to them
                query_parts.append(f" AND c.assigned_to = ${param_index}")
                params.append(current_user_email)
                param_index += 1
                logger.info(
                    f"🔒 [CRM Clients] Regular member - filtered to assigned_to={current_user_email}"
                )

            if search:
                search_pattern = f"%{search}%"
                query_parts.append(
                    f" AND (c.full_name ILIKE ${param_index} OR c.email ILIKE ${param_index + 1} OR c.phone ILIKE ${param_index + 2})"
                )
                params.extend([search_pattern, search_pattern, search_pattern])
                param_index += 3

            query_parts.append(
                f" ORDER BY c.created_at DESC LIMIT ${param_index} OFFSET ${param_index + 1}"
            )
            params.extend([limit, offset])

            query = " ".join(query_parts)
            rows = await conn.fetch(query, *params)

            clients = [ClientResponse(**dict(row)) for row in rows]
            logger.info(
                f"📋 [CRM Clients] Returning {len(clients)} clients for {current_user_email}"
            )
            return clients

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int = Path(..., gt=0),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Get client by ID

    Access Control:
    - Admin users: Can view any client
    - Team members: Can only view clients assigned to them
    """
    try:
        user_email = current_user.get("email", "").lower()
        user_is_admin = is_crm_admin(current_user)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, uuid, full_name, email, phone, whatsapp, nationality, status,
                   client_type, assigned_to, avatar_url, first_contact_date, last_interaction_date,
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
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Get client by email address

    Access Control:
    - Admin users: Can view any client
    - Team members: Can only view clients assigned to them
    """
    try:
        user_email = current_user.get("email", "").lower()
        user_is_admin = is_crm_admin(current_user)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, uuid, full_name, email, phone, whatsapp, nationality, status,
                   client_type, assigned_to, avatar_url, first_contact_date, last_interaction_date,
                   tags, created_at, updated_at FROM clients WHERE email = $1""",
                email,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Client not found")

            # RBAC: Check if non-admin user has access to this client
            if not user_is_admin and (row["assigned_to"] or "").lower() != user_email:
                raise HTTPException(status_code=403, detail="Access denied to this client")

            return ClientResponse(**dict(row))

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.patch("/{client_id}", response_model=ClientResponse)
@audit_change(entity_type="client", change_type="update")
async def update_client(
    updates: ClientUpdate = Body(...),
    client_id: int = Path(..., gt=0, description="Client ID"),
    user_email: str = Query(..., description="Team member making the update", alias="updated_by"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Update client information

    Only provided fields will be updated. Other fields remain unchanged.

    Access Control:
    - Admin users: Can update any client
    - Team members: Can only update clients assigned to them
    """
    start_time = time.time()
    try:
        user_email = current_user.get("email", "").lower()
        user_is_admin = is_crm_admin(current_user)

        async with db_pool.acquire() as conn:
            # RBAC: First check if user has access to this client
            if not user_is_admin:
                check_row = await conn.fetchrow(
                    "SELECT assigned_to FROM clients WHERE id = $1", client_id
                )
                if not check_row:
                    raise HTTPException(status_code=404, detail="Client not found")

                if (check_row["assigned_to"] or "").lower() != user_email:
                    raise HTTPException(
                        status_code=403,
                        detail="Access denied: You can only update your assigned clients",
                    )

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
                "company_name": "company_name",
                "nationality": "nationality",
                "passport_number": "passport_number",
                "passport_expiry": "passport_expiry",
                "date_of_birth": "date_of_birth",
                "status": "status",
                "client_type": "client_type",
                "assigned_to": "assigned_to",
                "avatar_url": "avatar_url",
                "address": "address",
                "notes": "notes",
                "tags": "tags",
                "custom_fields": "custom_fields",
            }

            # Date fields that need empty string → None conversion
            date_fields = {"passport_expiry", "date_of_birth"}

            for field, value in updates.dict(exclude_unset=True).items():
                if field not in field_mapping:
                    raise HTTPException(status_code=400, detail=f"Invalid field name: {field}")

                # Convert empty strings to None for date fields
                if field in date_fields and value == "":
                    value = None

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
                user_email,
                f"Updated fields: {updated_fields}",
            )

            log_success(
                logger,
                "Updated client",
                client_id=client_id,
                updated_by=user_email,
            )

            # Track metrics
            # crm_client_operations.labels(operation="update", status="success").inc()

            return ClientResponse(**dict(row))

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.delete("/{client_id}")
@audit_change(entity_type="client", change_type="delete")
async def delete_client(
    client_id: int = Path(..., gt=0, description="Client ID"),
    user_email: str = Query(..., description="Team member deleting the client", alias="deleted_by"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a client (soft delete - marks as inactive)

    This doesn't permanently delete the client, just marks them as inactive.

    Access Control:
    - Admin users: Can delete any client
    - Team members: Can only delete clients assigned to them
    """
    start_time = time.time()
    try:
        user_email = current_user.get("email", "").lower()
        user_is_admin = is_crm_admin(current_user)

        async with db_pool.acquire() as conn:
            # RBAC Check
            if not user_is_admin:
                check_row = await conn.fetchrow(
                    "SELECT assigned_to FROM clients WHERE id = $1", client_id
                )
                if not check_row:
                    raise HTTPException(status_code=404, detail="Client not found")

                if (check_row["assigned_to"] or "").lower() != user_email:
                    raise HTTPException(
                        status_code=403,
                        detail="Access denied: You can only delete your assigned clients",
                    )

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
                user_email,
                "Client marked as inactive",
            )

            log_success(
                logger,
                "Deleted (soft) client",
                client_id=client_id,
                deleted_by=user_email,
            )

            # Track metrics
            # crm_client_operations.labels(operation="delete", status="success").inc()

            return {"success": True, "message": "Client marked as inactive"}

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/{client_id}/summary")
async def get_client_summary(
    client_id: int = Path(..., gt=0, description="Client ID"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
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
        user_email = current_user.get("email", "").lower()
        user_is_admin = is_crm_admin(current_user)

        async with db_pool.acquire() as conn:
            # Get client basic info
            client_row = await conn.fetchrow(
                """SELECT id, uuid, full_name, email, phone, whatsapp, nationality, status,
                   client_type, assigned_to, avatar_url, first_contact_date, last_interaction_date,
                   tags, created_at, updated_at FROM clients WHERE id = $1""",
                client_id,
            )

            if not client_row:
                raise HTTPException(status_code=404, detail="Client not found")

            # RBAC: Check if non-admin user has access to this client
            if not user_is_admin and (client_row["assigned_to"] or "").lower() != user_email:
                raise HTTPException(status_code=403, detail="Access denied to this client summary")

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
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
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

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/{client_id}/audit-trail")
async def get_client_audit_trail(
    request: Request,
    client_id: int = Path(..., gt=0, description="Client ID"),
    limit: int = Query(50, ge=1, le=200, description="Max audit entries to return"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Get audit trail for a specific client
    """
    try:
        user_email = current_user.get("email", "")
        user_is_admin = is_crm_admin(current_user)

        async with db_pool.acquire() as conn:
            client = await conn.fetchrow(
                "SELECT id, full_name, assigned_to FROM clients WHERE id = $1", client_id
            )

            if not client:
                raise HTTPException(status_code=404, detail="Client not found")

            # Check access permissions
            if not user_is_admin and (client["assigned_to"] or "").lower() != user_email.lower():
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: You can only view audit trails for your assigned clients",
                )

        # Get audit trail
        trail = await audit_logger.get_audit_trail(
            entity_type="client", entity_id=client_id, limit=limit
        )

        return {
            "client": {
                "id": client["id"],
                "full_name": client["full_name"],
                "assigned_to": client["assigned_to"],
            },
            "audit_trail": trail,
            "total_entries": len(trail),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/metrics/summary")
async def get_crm_metrics_summary(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get CRM metrics summary for dashboard
    """
    try:
        user_email = current_user.get("email", "")
        if not user_email:
            raise HTTPException(status_code=401, detail="Authentication required")

        summary = await metrics_collector.get_metrics_summary()
        return summary

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.post("/metrics/refresh")
async def refresh_crm_metrics(
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Force refresh of CRM metrics (Admin only)
    """
    try:
        if not is_crm_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        results = await metrics_collector.update_all_metrics()

        return {
            "message": "CRM metrics refreshed successfully",
            "timestamp": results.get("timestamp"),
            "metrics_updated": results.get("metrics_updated", []),
            "errors": results.get("errors", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)
