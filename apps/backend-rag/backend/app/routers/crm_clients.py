"""
ZANTARA CRM - Clients Management Router
Endpoints for managing client data (anagrafica clienti)

Refactored: Migrated to asyncpg with connection pooling (2025-12-07)
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, EmailStr, field_validator

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.services.crm.audit_logger import audit_change, audit_logger
from backend.app.services.crm.metrics import metrics_collector, track_client_creation
from backend.app.utils.crm_utils import (
    is_crm_admin,
    verify_client_access,
)
from backend.app.utils.error_handlers import handle_database_error
from backend.app.utils.logging_utils import get_logger, log_success
from backend.core.cache import cached, invalidate_cache
from backend.db.repositories.client_repository import ClientRepository
from backend.services.crm.client_service import ClientService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm/clients", tags=["crm-clients"])


def get_client_service(db_pool: asyncpg.Pool = Depends(get_database_pool)) -> ClientService:
    repository = ClientRepository(db_pool)
    return ClientService(repository)


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
    def validate_optional_fields(cls, v: Any) -> Any:
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

    @field_validator("date_of_birth")
    @classmethod
    def validate_not_minor(cls, v: str | None) -> str | None:
        """Block standalone profiles for clients under 18 years old."""
        if not v:
            return v
        try:
            dob = datetime.strptime(v, "%Y-%m-%d").date()
            today = datetime.now(tz=timezone.utc).date()
            age = (today - dob).days // 365
            if age < 18:
                raise ValueError(
                    f"MINORE ({age} anni): i clienti under 18 non possono avere profilo singolo. "
                    "Collegare al profilo del genitore tramite family members.",
                )
        except ValueError as e:
            if "MINORE" in str(e):
                raise
            # Invalid date format — handled elsewhere
        return v


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
    def validate_optional_fields(cls, v: Any) -> Any:
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

    @field_validator("date_of_birth")
    @classmethod
    def validate_not_minor(cls, v: str | None) -> str | None:
        """Block setting date_of_birth that makes client under 18."""
        if not v:
            return v
        try:
            dob = datetime.strptime(v, "%Y-%m-%d").date()
            today = datetime.now(tz=timezone.utc).date()
            age = (today - dob).days // 365
            if age < 18:
                raise ValueError(
                    f"MINORE ({age} anni): i clienti under 18 non possono avere profilo singolo. "
                    "Collegare al profilo del genitore tramite family members.",
                )
        except ValueError as e:
            if "MINORE" in str(e):
                raise
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
    gender: str | None = None
    birthplace: str | None = None
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
    tax_id: str | None = None
    npwp: str | None = None
    nib: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None

    @field_validator("uuid", mode="before")
    @classmethod
    def convert_uuid_to_string(cls, v: Any) -> Any:
        """Convert UUID object to string if needed"""
        if v is None:
            return ""
        return str(v)

    @field_validator("tags", mode="before")
    @classmethod
    def ensure_tags_list(cls, v: Any) -> Any:
        """Ensure tags is always a list"""
        if v is None:
            return []
        return v

    @field_validator("passport_expiry", "date_of_birth", mode="before")
    @classmethod
    def convert_date_to_string(cls, v: Any) -> Any:
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
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    client_service: ClientService = Depends(get_client_service),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ClientResponse:
    """
    Create a new client with transactional safety and domain error mapping.
    """
    from backend.app.core.exceptions import ResourceConflictError

    try:
        # Estrae i dati validati da FastAPI/Pydantic
        client_data = client.model_dump(exclude_unset=True)

        # Popola created_by con l'utente autenticato
        creator_email = (current_user.get("email") or "").strip().lower() if current_user else None
        if not creator_email:
            logger.error(
                f"create_client: missing email in current_user context. "
                f"Keys: {list(current_user.keys()) if current_user else 'None'}, "
                f"sub: {current_user.get('sub') if current_user else 'N/A'}"
            )
            raise HTTPException(
                status_code=401,
                detail="Authentication error: user email not found in token. Please re-login.",
            )
        client_data["created_by"] = creator_email
        # Auto-assign to creator if not explicitly assigned
        if not client_data.get("assigned_to"):
            client_data["assigned_to"] = creator_email

        # Costruisce i dati opzionali per l'azienda se presenti nel payload
        # NIB-only dedup: match existing company by NIB (unique identifier)
        # NEVER match by name — One Sponsor Policy (SE 3/836/2026) requires legal entity distinction
        company_data = None
        existing_company_id = None
        if client.company_name:
            nib = client_data.pop("nib", None)
            if nib:
                async with db_pool.acquire() as conn:
                    existing_company_id = await conn.fetchval(
                        "SELECT id FROM companies WHERE nib = $1 AND status = 'active' LIMIT 1",
                        nib.strip(),
                    )
                    if existing_company_id:
                        logger.info(
                            f"Company dedup: found existing company {existing_company_id} by NIB {nib}"
                        )

            if not existing_company_id:
                company_data = {
                    "company_name": client.company_name,
                    "status": "active",
                    "kbli_code": client_data.pop("kbli_code", None),
                }
                if nib:
                    company_data["nib"] = nib

        # Chiama il Business Logic Layer (gestisce transazioni e Domain Errors)
        created_record = await client_service.create_client(
            client_data=client_data,
            company_data=company_data,
            existing_company_id=existing_company_id,
        )

        new_client = dict(created_record)

        # Logica accessoria: Google Drive
        try:
            from backend.services.integrations.service_account_drive_service import (
                ServiceAccountDriveService,
            )

            drive_service = ServiceAccountDriveService()
            background_tasks.add_task(
                drive_service.create_client_folder,
                client_id=new_client["id"],
                client_name=client.full_name,
                client_type=client.client_type,
                db_pool=db_pool,
            )
        except Exception as e:
            logger.error(f"Drive folder creation failed: {e}")

        # Invalidazione extra cache HTTP (il service invalida la memory cache)
        await invalidate_cache("zantara:crm_clients_stats:*")

        # Welcome communications (Trigger 1a + 1b)
        try:
            from backend.services.crm.welcome.welcome_email_service import (
                schedule_client_welcome_email,
            )
            from backend.services.crm.welcome.welcome_whatsapp_service import send_client_welcome

            background_tasks.add_task(send_client_welcome, new_client["id"], db_pool)
            background_tasks.add_task(schedule_client_welcome_email, new_client["id"], db_pool)
        except Exception as e:
            logger.error(f"Welcome communication setup failed: {e}")

        # Auto-create portal profile (team_members with role='client')
        try:
            from backend.services.portal.portal_profile_service import PortalProfileService

            portal_profile_service = PortalProfileService(db_pool)
            background_tasks.add_task(
                portal_profile_service.ensure_portal_profile,
                client_id=new_client["id"],
                email=new_client.get("email"),
                full_name=new_client.get("full_name", ""),
            )
        except Exception as e:
            logger.error(f"Portal profile creation setup failed: {e}")

        return ClientResponse(**new_client)

    except ResourceConflictError as e:
        logger.warning(f"Integrity error creating client: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
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
    nationality: str | None = Query(None, description="Filter by nationality"),
    passport_expiring_days: int | None = Query(
        None,
        ge=0,
        le=730,
        description="Filter clients with passport expiring within N days (0=already expired)",
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> Any:
    """
    List clients with pagination and search.

    All authenticated users can see ALL clients.

    FILTERS:
    - **status**: Filter by client status
    - **assigned_to**: Filter by assigned team member (optional)
    - **search**: Search in name, email, phone fields
    - **nationality**: Filter by nationality
    - **limit**: Max results (default: 50, max: 200)
    - **offset**: For pagination
    """
    try:
        # Get current user from dependency
        current_user_email = current_user.get("email", "") if current_user else ""

        # SECURITY: Require authentication for client list
        if not current_user_email:
            raise HTTPException(status_code=401, detail="Authentication required to view clients")

        logger.info(
            f"📋 [CRM Clients] User {current_user_email} requesting clients list "
            f"(assigned_to_filter={assigned_to})",
        )

        async with db_pool.acquire() as conn:
            # Build query dynamically with explicit columns + sentiment/summary from interactions
            query_parts = [
                """
                SELECT
                    c.id, c.uuid, c.full_name, c.email, c.phone, c.whatsapp, c.nationality, c.status,
                    c.client_type, c.assigned_to, c.avatar_url, c.first_contact_date, c.last_interaction_date,
                    c.passport_number, c.passport_expiry, c.date_of_birth, c.gender, c.birthplace, c.company_name,
                    c.custom_fields, c.address, c.notes, c.npwp, c.nib,
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
                WHERE c.deleted_at IS NULL
                """,
            ]
            params: list[Any] = []
            param_index = 1

            if status:
                query_parts.append(f" AND c.status = ${param_index}")
                params.append(status)
                param_index += 1

            # Optional filter by assigned_to (all users can see all clients)
            if assigned_to:
                query_parts.append(f" AND c.assigned_to = ${param_index}")
                params.append(assigned_to)
                param_index += 1

            if search:
                search_pattern = f"%{search}%"
                query_parts.append(
                    f" AND (c.full_name ILIKE ${param_index} OR c.email ILIKE ${param_index + 1} OR c.phone ILIKE ${param_index + 2})",
                )
                params.extend([search_pattern, search_pattern, search_pattern])
                param_index += 3

            if nationality:
                query_parts.append(f" AND c.nationality ILIKE ${param_index}")
                params.append(f"%{nationality}%")
                param_index += 1

            if passport_expiring_days is not None:
                if passport_expiring_days == 0:
                    # Already expired
                    query_parts.append(
                        " AND c.passport_expiry IS NOT NULL AND c.passport_expiry < CURRENT_DATE",
                    )
                else:
                    query_parts.append(
                        f" AND c.passport_expiry IS NOT NULL"
                        f" AND c.passport_expiry <= CURRENT_DATE + INTERVAL '{passport_expiring_days} days'",
                    )

            query_parts.append(
                f" ORDER BY c.created_at DESC LIMIT ${param_index} OFFSET ${param_index + 1}",
            )
            params.extend([limit, offset])

            query = " ".join(query_parts)
            rows = await conn.fetch(query, *params)

            clients = [ClientResponse(**dict(row)) for row in rows]
            logger.info(
                f"📋 [CRM Clients] Returning {len(clients)} clients for {current_user_email}",
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
) -> ClientResponse:
    """
    Get client by ID

    Access Control:
    - Admin users: Can view any client
    - Team members: Can only view clients assigned to them
    """
    try:
        async with db_pool.acquire() as conn:
            # RBAC: verify user has access to this specific client
            await verify_client_access(client_id, current_user, conn, allow_assigned=True)

            row = await conn.fetchrow(
                """SELECT c.id, c.uuid, c.full_name, c.email, c.phone, c.whatsapp, c.nationality, c.status,
                   c.client_type, c.assigned_to, c.avatar_url, c.first_contact_date, c.last_interaction_date,
                   c.tags, c.custom_fields, c.address, c.notes, c.passport_number, c.passport_expiry,
                   c.date_of_birth, c.gender, c.birthplace, c.lead_source, c.service_interest, c.tax_id,
                   c.npwp, c.nib,
                   c.created_at, c.updated_at, c.created_by,
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
                   WHERE c.id = $1""",
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
) -> ClientResponse:
    """
    Get client by email address

    Access Control:
    - Admin users: Can view any client
    - Team members: Can only view clients assigned to them
    """
    try:
        user_email = current_user.get("email", "").lower()

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT c.id, c.uuid, c.full_name, c.email, c.phone, c.whatsapp, c.nationality, c.status,
                   c.client_type, c.assigned_to, c.avatar_url, c.first_contact_date, c.last_interaction_date,
                   c.tags, c.custom_fields, c.address, c.notes, c.passport_number, c.passport_expiry,
                   c.date_of_birth, c.gender, c.birthplace, c.lead_source, c.service_interest, c.tax_id,
                   c.npwp, c.nib,
                   c.created_at, c.updated_at, c.created_by,
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
                   WHERE c.email = $1""",
                email,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Client not found")

            # RBAC: non-admin users can only view clients assigned to them
            if not is_crm_admin(current_user):
                assigned_to = row["assigned_to"]
                if not assigned_to or assigned_to.lower() != user_email:
                    logger.warning(
                        f"RBAC: User {user_email} denied access to client by email "
                        f"(assigned_to: {assigned_to})",
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have permission to access this client.",
                    )

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
) -> ClientResponse:
    """
    Update client information

    Only provided fields will be updated. Other fields remain unchanged.

    Access: Admin can update any client. Non-admin users can only update clients assigned to them.
    """
    user_email = current_user.get("email", "").lower()
    time.time()
    try:
        async with db_pool.acquire() as conn:
            # RBAC: Verify user has access to this client
            await verify_client_access(client_id, current_user, conn, allow_assigned=True)
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
                "lead_source": "lead_source",
                "service_interest": "service_interest",
                "gender": "gender",
                "birthplace": "birthplace",
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

            # Notify client via portal about significant profile changes
            try:
                updated_field_names = list(updates.dict(exclude_unset=True).keys())
                from backend.services.portal.portal_notification_service import (
                    PortalNotificationService,
                )

                notif_service = PortalNotificationService(db_pool)
                asyncio.create_task(
                    notif_service.notify_profile_updated(
                        client_id=client_id,
                        updated_fields=updated_field_names,
                        sent_by=user_email,
                    ),
                )
            except Exception as e:
                logger.error(f"Portal notification for profile update failed: {e}")

            log_success(
                logger,
                "Updated client",
                client_id=client_id,
                updated_by=user_email,
            )

            # Track metrics
            # crm_client_operations.labels(operation="update", status="success").inc()

            await invalidate_cache("zantara:crm_clients_stats:*")
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
) -> dict[str, Any]:
    """
    Delete a client (soft delete - marks as inactive)

    This doesn't permanently delete the client, just marks them as inactive.

    Access: Admin can delete any client. Non-admin users can only delete clients assigned to them.
    """
    time.time()
    try:
        user_email = current_user.get("email", "").lower()

        async with db_pool.acquire() as conn:
            # RBAC: Verify user has access to this client
            await verify_client_access(client_id, current_user, conn, allow_assigned=True)

            # Soft delete (mark as inactive + set deleted_at so list queries exclude it)
            row = await conn.fetchrow(
                """
                UPDATE clients
                SET status = 'inactive', updated_at = NOW(), deleted_at = NOW()
                WHERE id = $1 AND deleted_at IS NULL
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

            await invalidate_cache("zantara:crm_clients_stats:*")
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
) -> dict[str, Any]:
    """
    Get comprehensive client summary including:
    - Basic client info
    - All practices (active + completed)
    - Recent interactions
    - Documents
    - Upcoming renewals

    Access Control:
    - Admin users: Can view any client summary
    - Team members: Can only view summary of clients assigned to them
    """
    try:
        async with db_pool.acquire() as conn:
            # RBAC: verify user has access to this specific client
            await verify_client_access(client_id, current_user, conn, allow_assigned=True)
            # Get client basic info
            client_row = await conn.fetchrow(
                """SELECT id, uuid, full_name, email, phone, whatsapp, nationality, status,
                   client_type, assigned_to, avatar_url, first_contact_date, last_interaction_date,
                   tags, created_at, updated_at FROM clients WHERE id = $1 AND deleted_at IS NULL""",
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
                            in ["inquiry", "waiting_documents", "sending_invoice", "on_process"]
                        ],
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
    _request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    _current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get overall client statistics

    Returns counts by status, top assigned team members, etc.

    Performance: Cached for 5 minutes to reduce database load.
    """
    try:
        async with db_pool.acquire() as conn:
            # Total clients by status (exclude soft-deleted)
            by_status_rows = await conn.fetch(
                """
                SELECT status, COUNT(*) as count
                FROM clients
                WHERE deleted_at IS NULL
                GROUP BY status
                """,
            )

            # Clients by assigned team member (exclude soft-deleted)
            by_team_member_rows = await conn.fetch(
                """
                SELECT assigned_to, COUNT(*) as count
                FROM clients
                WHERE assigned_to IS NOT NULL AND deleted_at IS NULL
                GROUP BY assigned_to
                ORDER BY count DESC
                """,
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

            # Practices by type — single GROUP BY query (avoids N+1 per-type loop)
            by_practice_type_rows = await conn.fetch(
                """
                SELECT pt.name as practice_type, COUNT(p.id) as count
                FROM practices p
                JOIN practice_types pt ON p.practice_type_id = pt.id
                GROUP BY pt.name
                ORDER BY count DESC
                """,
            )

            # Passport health counts
            passport_health_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE passport_expiry < CURRENT_DATE) as expired,
                    COUNT(*) FILTER (WHERE passport_expiry >= CURRENT_DATE AND passport_expiry <= CURRENT_DATE + INTERVAL '90 days') as expiring_soon,
                    COUNT(*) FILTER (WHERE last_interaction_date < NOW() - INTERVAL '30 days' OR last_interaction_date IS NULL) as silent_30d
                FROM clients
                WHERE deleted_at IS NULL AND status != 'inactive'
                    AND passport_expiry IS NOT NULL
                """,
            )

            by_status = {row["status"]: row["count"] for row in by_status_rows}
            by_team_member = [dict(row) for row in by_team_member_rows]
            new_last_30_days = new_last_30_days_row["count"] if new_last_30_days_row else 0
            by_practice_type = {row["practice_type"]: row["count"] for row in by_practice_type_rows}

            return {
                "total": sum(by_status.values()),
                "by_status": by_status,
                "by_team_member": by_team_member,
                "new_last_30_days": new_last_30_days,
                "by_practice_type": by_practice_type,
                "passport_expired": passport_health_row["expired"] if passport_health_row else 0,
                "passport_expiring_soon": passport_health_row["expiring_soon"] if passport_health_row else 0,
                "silent_30d": passport_health_row["silent_30d"] if passport_health_row else 0,
            }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e) from e


@router.get("/{client_id}/audit-trail")
async def get_client_audit_trail(
    _request: Request,
    client_id: int = Path(..., gt=0, description="Client ID"),
    limit: int = Query(50, ge=1, le=200, description="Max audit entries to return"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get audit trail for a specific client.

    Access Control:
    - Admin users: Can view audit trail for any client
    - Team members: Can only view audit trail of clients assigned to them
    """
    try:
        async with db_pool.acquire() as conn:
            # RBAC: verify user has access to this specific client
            await verify_client_access(client_id, current_user, conn, allow_assigned=True)

            client = await conn.fetchrow(
                "SELECT id, full_name, assigned_to FROM clients WHERE id = $1 AND deleted_at IS NULL", client_id,
            )

            if not client:
                raise HTTPException(status_code=404, detail="Client not found")

        # Get audit trail
        trail = await audit_logger.get_audit_trail(
            entity_type="client", entity_id=client_id, limit=limit,
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


@router.get("/metrics/summary", operation_id="get_crm_client_metrics_summary")
async def get_crm_metrics_summary(
    current_user: dict = Depends(get_current_user),
    _db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """
    Get CRM metrics summary for dashboard
    """
    try:
        user_email = current_user.get("email", "")
        if not user_email:
            raise HTTPException(status_code=401, detail="Authentication required")

        return await metrics_collector.get_metrics_summary()

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e) from e


@router.post("/metrics/refresh", operation_id="refresh_crm_client_metrics")
async def refresh_crm_metrics(
    current_user: dict = Depends(get_current_user),
    _db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
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

# OCR, METRICS, DOCUMENT ENDPOINTS → crm_clients_documents.py
