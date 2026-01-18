"""
ZANTARA CRM - Clients Management Router
Endpoints for managing client data (anagrafica clienti)

Refactored: Migrated to asyncpg with connection pooling (2025-12-07)
"""

import time
from datetime import datetime
from typing import Any

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, EmailStr, field_validator

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.services.crm.audit_logger import audit_change, audit_logger
from backend.app.services.crm.metrics import crm_metrics, metrics_collector, track_client_creation
from backend.app.utils.crm_utils import extract_json_from_llm_response, is_crm_admin
from backend.app.utils.error_handlers import handle_database_error
from backend.app.utils.json_utils import to_jsonb
from backend.app.utils.logging_utils import get_logger, log_database_operation, log_success
from backend.core.cache import cached

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

    @field_validator("passport_expiry", "date_of_birth", mode="before")
    @classmethod
    def convert_date_to_string(cls, v):
        """Convert date objects to ISO format strings"""
        if v is None:
            return None
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v) if v else None


# ================================================
# ENDPOINTS
# ================================================


@router.post("/", response_model=ClientResponse)
@track_client_creation()
@audit_change(entity_type="client", change_type="create")
async def create_client(
    client: ClientCreate,
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
    time.time()
    try:
        user_email = current_user.get("email", "").lower()
        # Add timeout for connection acquisition to prevent hanging
        import asyncio

        try:
            async with asyncio.timeout(10.0):
                async with db_pool.acquire() as conn:
                    # Sanitize date fields - convert strings to date objects for asyncpg
                    passport_expiry = None
                    if client.passport_expiry:
                        try:
                            passport_expiry = datetime.strptime(
                                client.passport_expiry, "%Y-%m-%d"
                            ).date()
                        except ValueError:
                            passport_expiry = None

                    date_of_birth = None
                    if client.date_of_birth:
                        try:
                            date_of_birth = datetime.strptime(
                                client.date_of_birth, "%Y-%m-%d"
                            ).date()
                        except ValueError:
                            date_of_birth = None

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
                    log_success(
                        logger, f"Created client: {client.full_name}", client_id=new_client["id"]
                    )
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
            ) from None

    except asyncpg.UniqueViolationError as e:
        logger.warning(f"Integrity error creating client: {e}")
        raise HTTPException(
            status_code=400, detail="Client with this email or phone already exists"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e) from e


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
        current_user_email.lower().split("@")[0] if current_user_email else ""

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
        raise handle_database_error(e) from e


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
        current_user.get("email", "").lower()
        is_crm_admin(current_user)

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
        raise handle_database_error(e) from e


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
        raise handle_database_error(e) from e


@router.patch("/{client_id}", response_model=ClientResponse)
@audit_change(entity_type="client", change_type="update")
async def update_client(
    updates: ClientUpdate = Body(...),
    client_id: int = Path(..., gt=0, description="Client ID"),
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
    time.time()
    try:
        user_is_admin = is_crm_admin(current_user)
        user_email = current_user.get("email", "").lower()

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

                # Convert date fields: empty string → None, valid string → date object
                if field in date_fields:
                    if value == "" or value is None:
                        value = None
                    elif isinstance(value, str):
                        try:
                            value = datetime.strptime(value, "%Y-%m-%d").date()
                        except ValueError:
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
        raise handle_database_error(e) from e


@router.delete("/{client_id}")
@audit_change(entity_type="client", change_type="delete")
async def delete_client(
    client_id: int = Path(..., gt=0, description="Client ID"),
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
    time.time()
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
        raise handle_database_error(e) from e


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
        raise handle_database_error(e) from e


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
        raise handle_database_error(e) from e


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
        raise handle_database_error(e) from e


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
        raise handle_database_error(e) from e


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
        raise handle_database_error(e) from e


# ================================================
# PASSPORT OCR EXTRACTION
# ================================================


class PassportExtractRequest(BaseModel):
    """Request model for passport data extraction"""

    client_id: int
    image_url: str


class PassportExtractResponse(BaseModel):
    """Response model for extracted passport data"""

    success: bool
    passport_number: str | None = None
    passport_expiry: str | None = None
    message: str | None = None


@router.post("/extract-passport", response_model=PassportExtractResponse)
async def extract_passport_data(
    request: PassportExtractRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Extract passport number and expiry date from passport image using Gemini Vision.
    Updates the client record with extracted data.
    """
    import base64

    import httpx

    try:
        from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient

        if not GENAI_AVAILABLE:
            return PassportExtractResponse(success=False, message="Vision service not available")

        # Initialize Gemini client
        genai_client = GenAIClient()
        if not genai_client.is_available:
            return PassportExtractResponse(success=False, message="Gemini Vision not configured")

        # Download image from Google Drive
        image_url = request.image_url
        if "/view" in image_url:
            # Convert view URL to direct download URL
            import re

            match = re.search(r"/d/([^/]+)", image_url)
            if match:
                file_id = match.group(1)
                image_url = f"https://drive.google.com/uc?export=download&id={file_id}"

        logger.info(f"Downloading passport image from: {image_url[:50]}...")

        async with httpx.AsyncClient(follow_redirects=True) as http_client:
            response = await http_client.get(image_url, timeout=30.0)
            if response.status_code != 200:
                return PassportExtractResponse(
                    success=False, message=f"Failed to download image: HTTP {response.status_code}"
                )
            image_data = response.content

        # Convert to base64
        image_base64 = base64.b64encode(image_data).decode()

        # Determine MIME type
        mime_type = "image/jpeg"
        if image_data[:4] == b"\x89PNG":
            mime_type = "image/png"
        elif image_data[:4] == b"%PDF":
            mime_type = "application/pdf"

        # Build multimodal content for Gemini Vision
        ocr_prompt = """Analyze this passport image and extract the following information.
Return ONLY a JSON object with these fields:
{
  "passport_number": "the passport number or null if not found",
  "expiry_date": "expiry date in YYYY-MM-DD format or null if not found"
}

Look for:
- The passport number (usually alphanumeric, 8-9 characters)
- The expiry date or date of expiration field

IMPORTANT: Return ONLY the JSON object, no additional text."""

        contents = [
            {"text": ocr_prompt},
            {"inline_data": {"mime_type": mime_type, "data": image_base64}},
        ]

        result = await genai_client.generate_content(
            contents=contents,
            model="gemini-3-flash-preview",
            max_output_tokens=500,
        )

        response_text = result.get("text", "")
        logger.info(f"Gemini OCR response: {response_text[:200]}...")

        # Parse JSON response
        import json
        import re as regex

        # Extract JSON from response (handle markdown code blocks)
        json_match = regex.search(r"\{[^}]+\}", response_text, regex.DOTALL)
        if not json_match:
            return PassportExtractResponse(success=False, message="Could not parse OCR response")

        extracted_data = json.loads(json_match.group())
        passport_number = extracted_data.get("passport_number")
        expiry_date = extracted_data.get("expiry_date")

        if not passport_number and not expiry_date:
            return PassportExtractResponse(success=False, message="No passport data found in image")

        # Update client record
        async with db_pool.acquire() as conn:
            update_fields = []
            update_values = []
            param_num = 1

            if passport_number:
                update_fields.append(f"passport_number = ${param_num}")
                update_values.append(passport_number)
                param_num += 1

            if expiry_date:
                update_fields.append(f"passport_expiry = ${param_num}")
                update_values.append(expiry_date)
                param_num += 1

            if update_fields:
                update_values.append(request.client_id)
                await conn.execute(
                    f"UPDATE clients SET {', '.join(update_fields)}, updated_at = NOW() WHERE id = ${param_num}",
                    *update_values,
                )
                logger.info(f"Updated client {request.client_id} with extracted passport data")

        return PassportExtractResponse(
            success=True,
            passport_number=passport_number,
            passport_expiry=expiry_date,
            message="Passport data extracted successfully",
        )

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse OCR JSON: {e}")
        return PassportExtractResponse(success=False, message="Failed to parse extracted data")
    except Exception as e:
        logger.error(f"Passport OCR extraction failed: {e}")
        return PassportExtractResponse(success=False, message=str(e))


# ================================================
# ENHANCED PASSPORT OCR (Full Extraction)
# ================================================


class PassportEnhancedRequest(BaseModel):
    """Request model for enhanced passport OCR"""

    client_id: int
    file_id: str  # Google Drive file ID


class PassportEnhancedResponse(BaseModel):
    """Response model for enhanced passport OCR"""

    success: bool
    passport_number: str | None = None
    expiry_date: str | None = None
    full_name: str | None = None
    gender: str | None = None
    date_of_birth: str | None = None
    birthplace: str | None = None
    nationality: str | None = None
    mrz_line1: str | None = None
    mrz_line2: str | None = None
    confidence: float = 0.0
    name_match: bool | None = None
    message: str | None = None


@router.post("/extract-passport-enhanced", response_model=PassportEnhancedResponse)
async def extract_passport_enhanced(
    request: PassportEnhancedRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Enhanced passport OCR using Gemini Vision.
    Extracts all visible data from passport and updates client record.

    Returns:
        - passport_number
        - expiry_date (linked to alert)
        - full_name (with fuzzy match verification)
        - gender (M/F)
        - date_of_birth
        - birthplace (for enrichment)
        - nationality
        - MRZ lines (if visible)
        - confidence score
    """
    import base64
    import json
    from difflib import SequenceMatcher

    from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient
    from backend.services.integrations.google_drive_service import GoogleDriveService

    try:
        if not GENAI_AVAILABLE:
            return PassportEnhancedResponse(success=False, message="Vision service not available")

        genai_client = GenAIClient()
        if not genai_client.is_available:
            return PassportEnhancedResponse(success=False, message="Gemini Vision not configured")

        # Get current client data for name verification
        async with db_pool.acquire() as conn:
            client = await conn.fetchrow(
                "SELECT full_name FROM clients WHERE id = $1", request.client_id
            )
            if not client:
                return PassportEnhancedResponse(
                    success=False, message=f"Client {request.client_id} not found"
                )
            existing_name = client["full_name"]

        # Download image via Google Drive API (SYSTEM OAuth token)
        drive_service = GoogleDriveService(db_pool)
        access_token = await drive_service.get_valid_token(GoogleDriveService.SYSTEM_USER_ID)

        if not access_token:
            return PassportEnhancedResponse(
                success=False, message="Google Drive not connected. Please connect via Settings."
            )

        import httpx

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # Get file metadata
            meta_response = await http_client.get(
                f"https://www.googleapis.com/drive/v3/files/{request.file_id}",
                params={"fields": "mimeType,name"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if meta_response.status_code != 200:
                return PassportEnhancedResponse(
                    success=False,
                    message=f"Failed to get file metadata: {meta_response.status_code}",
                )
            metadata = meta_response.json()
            mime_type = metadata.get("mimeType", "image/jpeg")

            # Download file
            download_response = await http_client.get(
                f"https://www.googleapis.com/drive/v3/files/{request.file_id}",
                params={"alt": "media"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if download_response.status_code != 200:
                return PassportEnhancedResponse(
                    success=False,
                    message=f"Failed to download file: {download_response.status_code}",
                )
            image_data = download_response.content

        # Build enhanced OCR prompt - simplified to avoid token truncation
        ocr_prompt = """Extract passport data. Return ONLY this JSON:

{
  "passport_number": "XX123456",
  "expiry_date": "YYYY-MM-DD",
  "full_name": "SURNAME GIVEN_NAMES",
  "surname": "SURNAME",
  "given_names": "GIVEN NAMES",
  "gender": "M or F",
  "date_of_birth": "YYYY-MM-DD",
  "birthplace": "city, country",
  "nationality": "country code",
  "confidence": 0.95
}

Use null for unclear fields. Return ONLY JSON."""

        # Call Gemini Vision
        contents = [
            ocr_prompt,
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(image_data).decode(),
                }
            },
        ]

        result = await genai_client.generate_content(
            contents=contents,
            model="gemini-3-flash-preview",
            max_output_tokens=4000,  # Increased further to prevent JSON truncation
        )

        response_text = result.get("text", "")
        logger.info(f"Enhanced OCR response: {response_text[:300]}...")

        # Parse JSON response (handles code fences and chain-of-thought)
        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error(f"OCR JSON parsing failed. Raw response: {response_text[:500]}")
            return PassportEnhancedResponse(success=False, message="Could not parse OCR response")

        # Verify name match
        name_match = None
        extracted_name = extracted.get("full_name")
        if extracted_name and existing_name:
            # Fuzzy match with 80% threshold
            ratio = SequenceMatcher(
                None,
                existing_name.upper().replace(",", " ").split(),
                extracted_name.upper().replace(",", " ").split(),
            ).ratio()
            name_match = ratio >= 0.8

        # Prepare OCR data for storage
        ocr_data = {
            "extracted_at": datetime.utcnow().isoformat(),
            "raw_response": extracted,
            "file_id": request.file_id,
            "confidence": extracted.get("confidence", 0.0),
            "name_match_ratio": ratio if name_match is not None else None,
        }

        # Update client record with extracted data
        async with db_pool.acquire() as conn:
            update_parts = ["passport_ocr_data = $1"]
            # Use to_jsonb for asyncpg JSONB compatibility (handles Decimal, datetime, UUID)
            params = [to_jsonb(ocr_data)]
            param_idx = 2

            if extracted.get("passport_number"):
                update_parts.append(f"passport_number = ${param_idx}")
                params.append(extracted["passport_number"])
                param_idx += 1

            if extracted.get("expiry_date"):
                try:
                    expiry_date = datetime.strptime(extracted["expiry_date"], "%Y-%m-%d").date()
                    update_parts.append(f"passport_expiry = ${param_idx}")
                    params.append(expiry_date)
                    param_idx += 1
                except ValueError:
                    logger.warning(f"Invalid expiry_date format: {extracted['expiry_date']}")

            if extracted.get("gender"):
                update_parts.append(f"gender = ${param_idx}")
                params.append(extracted["gender"][0].upper())  # M or F
                param_idx += 1

            if extracted.get("date_of_birth"):
                try:
                    dob = datetime.strptime(extracted["date_of_birth"], "%Y-%m-%d").date()
                    update_parts.append(f"date_of_birth = ${param_idx}")
                    params.append(dob)
                    param_idx += 1
                except ValueError:
                    logger.warning(f"Invalid date_of_birth format: {extracted['date_of_birth']}")

            if extracted.get("birthplace"):
                update_parts.append(f"birthplace = ${param_idx}")
                params.append(extracted["birthplace"])
                param_idx += 1

            if extracted.get("nationality"):
                update_parts.append(f"nationality = ${param_idx}")
                params.append(extracted["nationality"])
                param_idx += 1

            params.append(request.client_id)
            update_sql = f"""
                UPDATE clients SET {", ".join(update_parts)}, updated_at = NOW()
                WHERE id = ${param_idx}
            """
            await conn.execute(update_sql, *params)
            logger.info(f"Updated client {request.client_id} with enhanced OCR data")

        return PassportEnhancedResponse(
            success=True,
            passport_number=extracted.get("passport_number"),
            expiry_date=extracted.get("expiry_date"),
            full_name=extracted.get("full_name"),
            gender=extracted.get("gender"),
            date_of_birth=extracted.get("date_of_birth"),
            birthplace=extracted.get("birthplace"),
            nationality=extracted.get("nationality"),
            mrz_line1=extracted.get("mrz_line1"),
            mrz_line2=extracted.get("mrz_line2"),
            confidence=extracted.get("confidence", 0.0),
            name_match=name_match,
            message="Passport data extracted and saved successfully",
        )

    except json.JSONDecodeError as e:
        logger.warning(f"Enhanced OCR JSON parse error: {e}")
        return PassportEnhancedResponse(success=False, message="Failed to parse OCR response")
    except Exception as e:
        logger.error(f"Enhanced passport OCR failed: {e}")
        return PassportEnhancedResponse(success=False, message=str(e))
