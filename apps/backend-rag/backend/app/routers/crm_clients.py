"""
ZANTARA CRM - Clients Management Router
Endpoints for managing client data (anagrafica clienti)

Refactored: Migrated to asyncpg with connection pooling (2025-12-07)
"""

import base64
import binascii
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, EmailStr, field_validator

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.deps.crm_access import get_crm_user_filter
from backend.app.deps.crm_service_write import verify_crm_write_key
from backend.app.services.crm.audit_logger import audit_change, audit_logger
from backend.app.services.crm.metrics import metrics_collector, track_client_creation
from backend.app.utils.crm_utils import (
    AvatarUrl,
    is_crm_admin,
    verify_client_access,
)
from backend.app.utils.error_handlers import handle_database_error
from backend.app.utils.logging_utils import get_logger, log_success
from backend.core.cache import cached, invalidate_cache
from backend.db.phone_lock import lock_phone_cores, phone_core
from backend.db.repositories.client_repository import ClientRepository
from backend.services.common.background import spawn
from backend.services.crm.client_service import ClientService

logger = get_logger(__name__)


def _normalize_phone_digits(raw: str | None) -> str | None:
    """Reduce a phone to a comparable digit tail for dedup.

    Delegates to the SINGLE canonical projection ``backend.db.phone_lock
    .phone_core`` (digits, one leading ``62``/``0`` prefix stripped, ≥6) —
    shared with the intake-delivery gate and every phone writer, so "the same
    phone" has exactly one definition (Codex 2026-07-19 round 10).
    """
    return phone_core(raw)


def _row_str(row: object, key: str) -> str | None:
    """Subscript a DB row (asyncpg Record / dict) for a string column,
    tolerating missing keys and non-string test doubles."""
    if row is None:
        return None
    try:
        value = row[key]  # type: ignore[index]
    except (KeyError, TypeError):
        return None
    return value if isinstance(value, str) else None


# Core-equivalence matcher for upsert-by-phone: matches every stored row whose
# phone_normalized collapses to the same canonical core as the payload — 0812…
# and 62812… are ONE identity (Codex 2026-07-19 round 10, F15: exact-string
# matching let intake delivery mint duplicate cards for prefix variants). $1 is
# the payload's core. SQL CASE mirrors backend.db.phone_lock.phone_core.
UPSERT_MATCH_SQL = """
SELECT id, full_name, notes, deleted_at, strategic_recap_source, updated_at
FROM clients
WHERE CASE WHEN regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g') LIKE '62%'
           THEN substr(regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g'), 3)
           WHEN regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g') LIKE '0%'
           THEN substr(regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g'), 2)
           ELSE regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g') END = $1
ORDER BY (deleted_at IS NULL) DESC, updated_at DESC NULLS LAST
FOR UPDATE
"""

router = APIRouter(prefix="/api/crm/clients", tags=["crm-clients"])


def get_client_service(db_pool: asyncpg.Pool = Depends(get_database_pool)) -> ClientService:
    repository = ClientRepository(db_pool)
    return ClientService(repository)


async def get_current_user_or_internal(request: Request) -> dict | None:
    """Auth dependency: accept either JWT user OR `X-Internal-Key` service token.

    Returns the user dict for JWT path (RBAC enforced by caller via
    `verify_client_access`). Returns `None` when authenticated via internal key —
    callers MUST treat None as "skip RBAC" and apply per-endpoint trust model
    (the internal key is used by wa-mirror auto-promote and is rotation-managed
    via Fly secret `WA_MIRROR_INTERNAL_KEY`).

    Raises 401 if neither auth path succeeds.
    """
    from backend.app.core.config import settings as _settings

    internal_key = (request.headers.get("X-Internal-Key") or "").strip()
    configured = (getattr(_settings, "wa_mirror_internal_key", None) or "").strip()
    if internal_key and configured and internal_key == configured:
        return None  # Trusted service call — no user identity

    # Fall back to normal JWT validation. `get_current_user` is sync, takes (request, credentials).
    # Credentials come from FastAPI's HTTPBearer security; we replicate that here.
    try:
        from fastapi.security import HTTPAuthorizationCredentials

        auth_header = request.headers.get("Authorization") or ""
        credentials: HTTPAuthorizationCredentials | None = None
        if auth_header.lower().startswith("bearer "):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=auth_header.split(" ", 1)[1].strip(),
            )
        return get_current_user(request, credentials)  # type: ignore[arg-type]
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("get_current_user_or_internal: auth failed: %s", e)
        raise HTTPException(status_code=401, detail="authentication required") from e


# ================================================
# HELPERS — Drive folder observability
# ================================================


def _report_drive_folder_failure(
    client_id: int,
    client_name: str | None,
    client_type: str | None,
    error: BaseException,
) -> None:
    """Surface Drive folder creation failures to Sentry without leaking PII.

    Sentry already redacts UU PDP fields via `_before_send` (sentry_config.py).
    Tags are scalar metadata, no PII.
    """
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("subsystem", "drive_folder_create")
            scope.set_tag("client_type", client_type or "unknown")
            scope.set_extra("client_id", client_id)
            sentry_sdk.capture_exception(error)
    except Exception:
        pass


async def _create_drive_folder_with_observability(
    drive_service,
    *,
    client_id: int,
    client_name: str,
    client_type: str,
    db_pool,
) -> None:
    """BackgroundTask wrapper that surfaces Drive create failures instead of swallowing.

    Without this, an exception in `create_client_folder` (e.g. 404 on a phantom
    parent folder ID) is silently logged and never reaches Sentry — clients end
    up without a Drive folder and no alert fires. See cicatrix-scars.md
    (2026-05-21: GDRIVE_COMPANIES_FOLDER_ID phantom).
    """
    try:
        result = await drive_service.ensure_client_folder(
            client_id=client_id,
            client_name=client_name,
            client_type=client_type,
            db_pool=db_pool,
        )
        if not result.get("success"):
            err = RuntimeError(
                f"ensure_client_folder returned success=False: {result.get('error')}"
            )
            logger.error(
                "Drive folder creation failed for client %s (%s): %s",
                client_id,
                client_type,
                result.get("error"),
            )
            _report_drive_folder_failure(client_id, client_name, client_type, err)
    except Exception as e:
        logger.error(
            "Drive folder creation exception for client %s (%s): %s",
            client_id,
            client_type,
            e,
        )
        _report_drive_folder_failure(client_id, client_name, client_type, e)


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
    avatar_url: AvatarUrl = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] = []
    lead_source: str | None = None  # 'website', 'referral', 'event', 'social_media', etc
    service_interest: list[str] = []  # Services client is interested in
    custom_fields: dict = {}
    # When a client with the same normalized phone already exists, create_client
    # returns 409 with the existing match instead of silently spawning a duplicate
    # (the Trevor-class bug: a team member adds a WhatsApp contact already owned by
    # someone else). Set True to override for a legitimate shared-phone person
    # (51 live shared-phone groups exist — spouses / reused numbers).
    allow_duplicate_phone: bool = False

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


TAX_CONSULTANT_VALUES: set[str] = {
    "veronika.tax@balizero.com",
    "kadek.tax@balizero.com",
    "dewaayu.tax@balizero.com",
    "angel.tax@balizero.com",
    "faisha.tax@balizero.com",
}


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
    tax_consultant: str | None = None  # one of TAX_CONSULTANT_VALUES or null
    avatar_url: AvatarUrl = None
    address: str | None = None
    notes: str | None = None
    strategic_recap: str | None = None
    tags: list[str] | None = None
    lead_source: str | None = None
    service_interest: list[str] | None = None
    custom_fields: dict | None = None
    gender: str | None = None
    birthplace: str | None = None
    tax_id: str | None = None
    npwp: str | None = None
    nib: str | None = None
    current_visa_type: str | None = None
    current_visa_sponsor: str | None = None

    # avatar_url is guarded by the shared `AvatarUrl` type (crm_utils) — the
    # validator travels with the type, so every model that stores an avatar gets
    # it. This model's inline copy was the ONLY guarded write-path while
    # ClientCreate / ClientProfileUpdate / ClientValidator silently were not.

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

    @field_validator("tax_consultant")
    @classmethod
    def validate_tax_consultant(cls, v: str | None) -> str | None:
        """Validate tax_consultant is one of the 5 Bali Zero tax team emails, or None."""
        if v is None or v == "":
            return None
        if v not in TAX_CONSULTANT_VALUES:
            raise ValueError(
                f"tax_consultant must be one of {sorted(TAX_CONSULTANT_VALUES)} or null, got '{v}'",
            )
        return v

    @field_validator("email", "passport_expiry", "date_of_birth", mode="before")
    @classmethod
    def validate_optional_fields(cls, v: Any) -> Any:
        """Convert empty strings to None for optional fields"""
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("gender", mode="before")
    @classmethod
    def normalize_gender(cls, v: str | None) -> str | None:
        """Normalize gender values: M→male, F→female, O→other."""
        if not v:
            return None
        normalized = v.strip().lower()
        mapping = {"m": "male", "f": "female", "o": "other"}
        return mapping.get(normalized, normalized)

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
    tax_consultant: str | None = None
    avatar_url: str | None = None
    # has_avatar: list views omit the (potentially base64 data-URI) avatar_url
    # to keep the page lean; the card lazy-loads the image from
    # GET /api/crm/clients/{id}/avatar when this is true.
    has_avatar: bool = False
    address: str | None = None
    notes: str | None = None
    strategic_recap: str | None = None
    strategic_recap_updated_at: datetime | None = None
    strategic_recap_source: str | None = None
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
    current_visa_type: str | None = None
    current_visa_sponsor: str | None = None
    ai_summary_status: str | None = None
    ai_summary_generated_at: datetime | None = None
    ai_profile_tier: str | None = None
    ai_profile_archetype: str | None = None
    ai_red_flags_count: int = 0
    ai_extraction_confidence: float | None = None
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

    @field_validator("custom_fields", mode="before")
    @classmethod
    def ensure_custom_fields_dict(cls, v: Any) -> Any:
        """Coerce custom_fields to a dict regardless of the stored jsonb shape.

        custom_fields is jsonb and the schema expects an object, but a handful of
        legacy rows hold a non-object value (e.g. a json array — id 10816 had
        ``custom_fields`` stored as ``[]``). Without this coercion Pydantic raises
        ``Input should be a valid dictionary`` on that row, and since the list
        endpoint validates the whole page in one comprehension a single bad row
        500s the entire request (reproduced: sahira@ page 2, limit>=75). Any
        non-dict — array, scalar, null — degrades to ``{}`` so one dirty row can
        never poison a list page.
        """
        if isinstance(v, dict):
            return v
        return {}

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

        # Phone dedup gate (not a DB column — strip before insert).
        allow_dup_phone = bool(client_data.pop("allow_duplicate_phone", False))

        # Phone-keyed dedup: a team member adding a WhatsApp contact that another
        # owner already has (same number) used to spawn a silent duplicate
        # (the Trevor-class bug). Block with 409 + the existing match so the UI
        # can offer "open existing" instead. `allow_duplicate_phone=True` overrides
        # for legitimate shared-phone people (spouses / reused numbers — 51 live
        # groups). The auto-promote path already dedups via upsert_client_by_phone;
        # this closes the manual-create hole.
        phone_norm = _normalize_phone_digits(client.phone or client.whatsapp)
        if phone_norm and not allow_dup_phone:
            # Match on digits-only on BOTH sides: the table stores phone in two
            # inconsistent shapes (E.164 `+62…` in `phone`, bare digits in
            # `phone_normalized`), and that drift is part of why duplicates slip
            # through. Compare normalized-to-digits to catch either shape.
            async with db_pool.acquire() as conn:
                # Mirror `_normalize_phone_digits` IN SQL: strip non-digits, then
                # drop a leading `62` or `0` so both sides collapse to the same
                # tail. Keeping these two normalizers identical is load-bearing —
                # if they drift, the gate silently never matches (false safety).
                dup = await conn.fetchrow(
                    """
                    WITH norm AS (
                        SELECT id, full_name, assigned_to, updated_at,
                               REGEXP_REPLACE(COALESCE(phone_normalized, phone, ''),
                                              '\\D', '', 'g') AS digits
                        FROM clients
                        WHERE deleted_at IS NULL
                    )
                    SELECT id, full_name, assigned_to
                    FROM norm
                    WHERE CASE
                            WHEN digits LIKE '62%' THEN SUBSTRING(digits FROM 3)
                            WHEN digits LIKE '0%'  THEN SUBSTRING(digits FROM 2)
                            ELSE digits
                          END = $1
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    phone_norm,
                )
            if dup:
                # Do NOT log the raw phone (UU PDP / Law 2: no PII in clear text —
                # CodeQL clear-text-logging gate). The existing client id is a
                # non-PII internal reference and is enough to trace the dedup hit.
                logger.info(
                    "create_client phone dedup hit: existing client id=%s",
                    dup["id"],
                )
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "duplicate_phone",
                        "message": (
                            "A client with this phone already exists. Open the "
                            "existing record, or resend with allow_duplicate_phone "
                            "to add a separate person on a shared number."
                        ),
                        "existing_client_id": dup["id"],
                        "existing_full_name": dup["full_name"],
                        "existing_assigned_to": dup["assigned_to"],
                    },
                )

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
                            "Company dedup: found existing company %s by NIB %s",
                            existing_company_id,
                            nib,
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
                _create_drive_folder_with_observability,
                drive_service,
                client_id=new_client["id"],
                client_name=client.full_name,
                client_type=client.client_type,
                db_pool=db_pool,
            )
        except Exception as e:
            logger.error("Drive folder creation scheduling failed: %s", e)
            _report_drive_folder_failure(new_client["id"], client.full_name, client.client_type, e)

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
            logger.error("Welcome communication setup failed: %s", e)

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
            logger.error("Portal profile creation setup failed: %s", e)

        return ClientResponse(**new_client)

    except ResourceConflictError as e:
        logger.warning("Integrity error creating client: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        # Intentional HTTP errors (409 duplicate-phone gate, 401 missing email)
        # must pass through — the generic handler below would mask them as 500.
        raise
    except Exception as e:
        raise handle_database_error(e) from e


@router.get("/", response_model=list[ClientResponse])
async def list_clients(
    status: str | None = Query(
        None,
        description="Filter by status: active, inactive, prospect, lead",
        pattern="^(active|inactive|prospect|lead)$",
    ),
    assigned_to: str | None = Query(None, description="Filter by assigned team member email"),
    search: str | None = Query(None, description="Search by name, email, or phone"),
    nationality: str | None = Query(None, description="Filter by nationality"),
    unnamed: bool = Query(
        False,
        description=(
            "When true, return ONLY phone-keyed leads whose full_name is still a "
            "placeholder (`Lead +<digits>`, `wa:<digits>`, bare digits, or empty) — "
            "the WA-mirror auto-created leads an operator must still name. "
            "Combine with assigned_to (or rely on RBAC) to scope to one operator."
        ),
    ),
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

    RBAC:
    - Admin/board users: See ALL clients
    - Team members: Only clients assigned to them

    FILTERS:
    - **status**: Filter by client status
    - **assigned_to**: Filter by assigned team member (optional, admin only)
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

        # RBAC: non-admin users only see their own clients
        rbac_filter = get_crm_user_filter(current_user)

        logger.info(
            "📋 [CRM Clients] User %s requesting clients list (assigned_to_filter=%s, rbac_filter=%s)",
            current_user_email,
            assigned_to,
            rbac_filter,
        )

        async with db_pool.acquire() as conn:
            # Build query dynamically with explicit columns + sentiment/summary from interactions
            query_parts = [
                """
                SELECT
                    c.id, c.uuid, c.full_name, c.email, c.phone, c.whatsapp, c.nationality, c.status,
                    c.client_type, c.assigned_to,
                    -- Base64 data-URI avatars (avg 20KB, max 518KB) bloat the list
                    -- page to ~10MB. Inline only http(s) URLs; the card lazy-loads
                    -- data-URI images from /{id}/avatar via the has_avatar flag.
                    CASE WHEN c.avatar_url LIKE 'data:%' THEN NULL ELSE c.avatar_url END AS avatar_url,
                    (c.avatar_url IS NOT NULL AND length(c.avatar_url) > 0) AS has_avatar,
                    c.first_contact_date, c.last_interaction_date,
                    c.passport_number, c.passport_expiry, c.date_of_birth, c.gender, c.birthplace, c.company_name,
                    c.custom_fields, c.address, c.notes, c.npwp, c.nib,
                    c.tags, c.created_at, c.updated_at,
                    i.sentiment as last_sentiment,
                    i.summary as last_interaction_summary,
                    CASE
                        WHEN c.ai_summary IS NOT NULL THEN 'available'
                        WHEN gq.status IS NOT NULL THEN 'pending'
                        ELSE 'not_generated'
                    END AS ai_summary_status,
                    c.ai_summary_generated_at,
                    NULLIF(c.ai_summary->'profile'->>'tier', '') AS ai_profile_tier,
                    NULLIF(c.ai_summary->'profile'->>'archetype', '') AS ai_profile_archetype,
                    COALESCE(
                        jsonb_array_length(
                            CASE
                                WHEN jsonb_typeof(c.ai_summary->'compliance'->'red_flags') = 'array'
                                THEN c.ai_summary->'compliance'->'red_flags'
                                ELSE '[]'::jsonb
                            END
                        ),
                        0
                    ) AS ai_red_flags_count,
                    CASE
                        WHEN jsonb_typeof(c.ai_summary->'extraction_confidence') = 'number'
                        THEN (c.ai_summary->>'extraction_confidence')::double precision
                        ELSE NULL
                    END AS ai_extraction_confidence
                FROM clients c
                LEFT JOIN LATERAL (
                    SELECT sentiment, summary
                    FROM interactions
                    WHERE client_id = c.id
                    ORDER BY interaction_date DESC
                    LIMIT 1
                ) i ON true
                LEFT JOIN LATERAL (
                    SELECT status
                    FROM crm_guardian_summary_queue
                    WHERE client_id = c.id
                      AND status IN ('pending', 'running')
                    ORDER BY enqueued_at DESC
                    LIMIT 1
                ) gq ON true
                WHERE c.deleted_at IS NULL
                """,
            ]
            params: list[Any] = []
            param_index = 1

            # RBAC: enforce assigned_to filter for non-admin users. A non-admin
            # sees ONLY their own assigned clients (admins get rbac_filter=None =
            # full view). Decision 2026-06-19: NOT "own + unassigned" — 93% of the
            # book is unassigned, so an OR-NULL clause would leak ~10.7k clients to
            # every team member. Unassigned clients stay admin-only until triaged.
            if rbac_filter is not None:
                query_parts.append(f" AND c.assigned_to = ${param_index}")
                params.append(rbac_filter)
                param_index += 1

            if status:
                query_parts.append(f" AND c.status = ${param_index}")
                params.append(status)
                param_index += 1

            # Unnamed phone-keyed leads: full_name is still a placeholder the
            # WA-mirror sweeper assigned (`Lead +628…`, `wa:+…`, bare digits) or
            # empty. Mirrors JUNK_NAME_PATTERNS in apps/wa-dashboard-m1/server.cjs
            # so both surfaces agree on "this contact still needs a human name".
            # No bound params (constant predicate) → param_index unchanged.
            if unnamed:
                query_parts.append(
                    " AND ("
                    "c.full_name IS NULL"
                    " OR btrim(c.full_name) = ''"
                    " OR c.full_name ~* '^lead\\s*\\+?[0-9]+$'"
                    " OR c.full_name ~* '^wa:\\s*\\+?[0-9]+$'"
                    " OR c.full_name ~ '^\\+?[0-9]{8,}$'"
                    ")",
                )

            # Optional filter by assigned_to (admin users can filter by any team member)
            if assigned_to:
                query_parts.append(f" AND c.assigned_to = ${param_index}")
                params.append(assigned_to)
                param_index += 1

            # NOTE: can_view_all_clients() returns True for all authenticated
            # users — everyone sees the full client list. The RBAC filter from
            # get_crm_user_filter() above already handles this correctly.

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
                        f" AND c.passport_expiry <= CURRENT_DATE + make_interval(days => ${param_index})",
                    )
                    params.append(passport_expiring_days)
                    param_index += 1

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
                   c.client_type, c.assigned_to, c.tax_consultant, c.avatar_url, c.first_contact_date, c.last_interaction_date,
                   c.tags, c.custom_fields, c.address, c.notes,
                   c.strategic_recap, c.strategic_recap_updated_at, c.strategic_recap_source,
                   c.passport_number, c.passport_expiry,
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


@router.get("/{client_id}/avatar")
async def get_client_avatar(
    client_id: int = Path(..., gt=0),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> Response:
    """Serve a client's avatar image.

    The list endpoint (`GET /`) omits base64 data-URI avatars to keep the page
    lean (they average ~20KB, up to 518KB, and would bloat a 200-row page to
    ~10MB). Cards lazy-load the image here when `has_avatar` is true.

    - Stored as a `data:` URI  -> decoded and streamed as image bytes.
    - Stored as an http(s) URL  -> 302 redirect to that URL.

    Access Control: admin sees any client; a team member only their assigned
    ones (same rule as `GET /{client_id}`).
    """
    try:
        async with db_pool.acquire() as conn:
            await verify_client_access(client_id, current_user, conn, allow_assigned=True)
            avatar_url = await conn.fetchval(
                "SELECT avatar_url FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )

        if not avatar_url:
            raise HTTPException(status_code=404, detail="No avatar for this client")

        if avatar_url.startswith("http://") or avatar_url.startswith("https://"):
            return RedirectResponse(url=avatar_url, status_code=302)

        if avatar_url.startswith("data:"):
            # data:[<mediatype>][;base64],<data>
            try:
                header, b64 = avatar_url.split(",", 1)
                media_type = "image/jpeg"
                if header.startswith("data:") and ";" in header:
                    media_type = header[len("data:"):].split(";", 1)[0] or media_type
                image_bytes = base64.b64decode(b64)
            except (ValueError, binascii.Error) as e:
                raise HTTPException(status_code=422, detail="Malformed avatar data") from e
            return Response(
                content=image_bytes,
                media_type=media_type,
                headers={"Cache-Control": "private, max-age=86400"},
            )

        # Unknown scheme -> treat as not found rather than leaking the raw value.
        raise HTTPException(status_code=404, detail="No servable avatar for this client")

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e) from e


_AVATAR_MAX_BYTES = 5 * 1024 * 1024  # 5MB — generous for a 400px crop, rejects abuse
_AVATAR_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


@router.post("/{client_id}/avatar", response_model=dict)
async def upload_client_avatar(
    client_id: int = Path(..., gt=0),
    file: UploadFile = File(...),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload a client avatar to Tigris S3 and store the public URL.

    Replaces the legacy path where the frontend inlined a base64 data: URI into
    avatar_url (which bloated the clients list to ~10MB). The image bytes are
    stored object-side and avatar_url becomes a plain public https URL.

    Access Control: admin any client; team member only their assigned ones.
    """
    import hashlib as _hl

    from backend.services.canva_renderer_v2 import _tigris

    content_type = (file.content_type or "").lower()
    ext = _AVATAR_CONTENT_TYPES.get(content_type)
    if ext is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported avatar type '{content_type}'. Use JPEG, PNG or WebP.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > _AVATAR_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Avatar too large ({len(data)} bytes); max {_AVATAR_MAX_BYTES}.",
        )

    async with db_pool.acquire() as conn:
        await verify_client_access(client_id, current_user, conn, allow_assigned=True)

    # Content-addressed key so re-uploads get a fresh URL (no stale CDN bytes).
    sha8 = _hl.sha256(data).hexdigest()[:8]
    key = f"client-avatar/{client_id}/{sha8}.{ext}"
    try:
        s3 = _tigris.get_s3_client()
        s3.put_object(
            Bucket=_tigris.BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
            ACL="public-read",
        )
    except Exception as e:
        logger.error("Avatar upload to Tigris failed for client %s: %s", client_id, e)
        raise HTTPException(status_code=502, detail="Avatar storage failed") from e

    public_url = f"https://{_tigris.PUBLIC_HOST}/{key}"

    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET avatar_url = $1, updated_at = NOW() WHERE id = $2",
            public_url,
            client_id,
        )
    await invalidate_cache("zantara:crm_clients_stats:*")

    logger.info("Avatar uploaded for client %s -> %s", client_id, key)
    return {"success": True, "avatar_url": public_url}


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
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT c.id, c.uuid, c.full_name, c.email, c.phone, c.whatsapp, c.nationality, c.status,
                   c.client_type, c.assigned_to, c.tax_consultant, c.avatar_url, c.first_contact_date, c.last_interaction_date,
                   c.tags, c.custom_fields, c.address, c.notes,
                   c.strategic_recap, c.strategic_recap_updated_at, c.strategic_recap_source,
                   c.passport_number, c.passport_expiry,
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

            # RBAC: verify user has access to this specific client
            await verify_client_access(row["id"], current_user, conn, allow_assigned=True)

            return ClientResponse(**dict(row))

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e) from e


@router.post("/{client_id}/ensure-drive-folder")
async def ensure_drive_folder(
    request: Request,
    client_id: int = Path(..., gt=0, description="Client ID"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict | None = Depends(get_current_user_or_internal),
) -> dict:
    """Idempotently ensure a Google Drive folder structure exists for a client.

    Auth: either a normal user JWT (RBAC enforced — admin or assigned user) OR
    a valid `X-Internal-Key` header matching `settings.wa_mirror_internal_key`.
    Used by:
      - `wa-mirror-auto-promote-leads.py` after inserting a new lead client directly in DB
        (those clients bypass `POST /api/crm/clients/` so the BackgroundTask Drive creation
         never fires).
      - Manual repair tooling / scripts.

    Behavior:
      - If `clients.google_drive_folder_id` is already set → returns `{"created": False, ...}`.
      - Otherwise → calls `ServiceAccountDriveService.ensure_client_folder` (awaited, NOT a
        BackgroundTask) so caller knows the outcome. The ensure path holds a per-client
        pg advisory lock and re-checks the column, so a concurrent creator never produces
        a twin folder.
    """
    async with db_pool.acquire() as conn:
        # RBAC: skip if authenticated via internal key (service-to-service call)
        if current_user is not None:
            await verify_client_access(client_id, current_user, conn, allow_assigned=True)
        row = await conn.fetchrow(
            "SELECT id, full_name, client_type, google_drive_folder_id "
            "FROM clients WHERE id = $1 AND deleted_at IS NULL",
            client_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail=f"client {client_id} not found")

    if row["google_drive_folder_id"]:
        return {
            "created": False,
            "reason": "already_exists",
            "client_id": client_id,
            "folder_id": row["google_drive_folder_id"],
        }

    from backend.services.integrations.service_account_drive_service import (
        ServiceAccountDriveService,
    )

    drive_service = ServiceAccountDriveService()
    try:
        result = await drive_service.ensure_client_folder(
            client_id=client_id,
            client_name=row["full_name"] or f"client_{client_id}",
            client_type=row["client_type"] or "individual",
            db_pool=db_pool,
        )
    except Exception as e:
        _report_drive_folder_failure(client_id, row["full_name"], row["client_type"], e)
        raise HTTPException(status_code=502, detail=f"Drive folder creation failed: {e}") from e

    if not result.get("success"):
        err = RuntimeError(result.get("error") or "ensure_client_folder returned success=False")
        _report_drive_folder_failure(client_id, row["full_name"], row["client_type"], err)
        raise HTTPException(status_code=502, detail=str(err))

    # F32: ensure-drive-folder was the only mutating endpoint here without invalidation
    await invalidate_cache("zantara:crm_clients_stats:*")
    return {
        "created": result.get("created", True),
        "client_id": client_id,
        "folder_id": result.get("root_folder_id"),
        "folder_url": result.get("root_folder_url"),
        "subfolder_count": len(result.get("subfolders", {})),
    }


# ================================================
# SERVICE-TO-SERVICE: phone-keyed lead upsert (wa-mirror)
# ================================================


def _name_is_junk(name: str | None) -> bool:
    """A name is placeholder/junk when empty, a 'Lead +<digits>' stub, 'unknown',
    or a bare phone number — i.e. not a real human/company name."""
    n = (name or "").strip().lower()
    if not n:
        return True
    if n == "unknown" or n.startswith("lead +") or n.startswith("lead+"):
        return True
    return n.replace("+", "").replace(" ", "").replace("-", "").isdigit()


def _name_is_better(new: str | None, current: str | None) -> bool:
    """`new` improves on `current` only when `new` is a real name AND `current` is
    empty/junk. Never downgrades an existing real name."""
    if not new or _name_is_junk(new):
        return False
    return _name_is_junk(current)


class ClientUpsertByPhone(BaseModel):
    """Sanitized payload for service-side lead promotion. Raw WhatsApp content NEVER
    crosses this boundary — only derived fields (name, note recap, strategic summary)."""

    phone_normalized: str  # digits only, no leading '+'
    full_name: str | None = None  # required to CREATE a new lead
    lead_source: str = "whatsapp_auto"
    assigned_to: str | None = None
    notes_append: str | None = None  # appended to clients.notes (never raw log text)
    strategic_recap: str | None = None  # 2-3 sentence Ollama-local summary, optional
    create_if_missing: bool = True  # auto-promote=True; recap-updater=False (update-only)
    restore_if_archived: bool = True
    improve_name: bool = True
    notes_append_min_age_hours: int = 24  # on enrich, append notes at most once per window
    # Identity-RESOLUTION callers (intake delivery bridge) set this: a shared
    # phone (matched_count > 1) must fail BEFORE any restore/rename/update —
    # the "best match" pick is arbitrary and mutating it writes the caller's
    # name onto a stranger (Codex 2026-07-19 round 6, F10). Default False keeps
    # the wa-mirror lead-promotion semantics unchanged.
    reject_ambiguous: bool = False

    @field_validator("phone_normalized")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.isdigit() or not (6 <= len(v) <= 20):
            raise ValueError("phone_normalized must be 6-20 digits with no '+'")
        return v


@router.post("/upsert-by-phone")
async def upsert_client_by_phone(
    payload: ClientUpsertByPhone,
    request: Request,
    actor: str = Depends(verify_crm_write_key),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Idempotent phone-keyed client upsert for wa-mirror lead promotion + strategic recap.

    Atomic per phone: a transaction-scoped advisory lock serializes concurrent upserts for
    the same phone (no unique constraint needed — production data has 51 live shared-phone
    groups), then `SELECT ... FOR UPDATE WHERE phone_normalized = $1` picks the best match
    (live first, then most-recent) and ENRICHes it, or INSERTs a fresh lead. Shared-phone
    groups (spouses / reused numbers) are reported via `matched_count` for audit.
    `strategic_recap` is applied only when the existing `strategic_recap_source` is not
    'manual' (human edit wins).

    Auth: scoped `X-CRM-Write-Key` + `WA_MIRROR_CRM_WRITE_ENABLED` flag.
    """
    phone = payload.phone_normalized
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # Serialize concurrent upserts for THIS phone (insert-race proof without a
            # unique index, which is infeasible: 51 live shared-phone groups exist).
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", phone)
            _core = _normalize_phone_digits(phone)
            if _core:
                # Canonical phone-core lock: converges with the intake-delivery
                # resolution window and the PATCH phone writer even when the
                # stored formats/prefixes differ (0812… vs 62812…) — round-9
                # F12/F13. Acquisition order is lexicographic (the digits key
                # above always sorts before 'phonecore:…'), giving every
                # participant the same total order: deadlock-safe.
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1))", f"phonecore:{_core}"
                )

            if _core:
                rows = await conn.fetch(UPSERT_MATCH_SQL, _core)
            else:
                # Payload too short to yield a core — legacy exact match.
                rows = await conn.fetch(
                    """
                    SELECT id, full_name, notes, deleted_at, strategic_recap_source, updated_at
                    FROM clients
                    WHERE phone_normalized = $1
                    ORDER BY (deleted_at IS NULL) DESC, updated_at DESC NULLS LAST
                    FOR UPDATE
                    """,
                    phone,
                )
            matched_count = len(rows)

            if payload.reject_ambiguous and matched_count > 1:
                # Fail BEFORE any restore/rename/update (F10): with a shared
                # phone the rows[0] pick is arbitrary — nothing may be mutated.
                return {
                    "client_id": None,
                    "was_created": False,
                    "action": "rejected_ambiguous",
                    "matched_count": matched_count,
                    "recap_applied": False,
                    "was_archived": False,
                }

            if rows:
                row = rows[0]
                cid: int = row["id"]
                was_archived = row["deleted_at"] is not None
                if was_archived and not payload.restore_if_archived:
                    # Archived rows are READ-ONLY when restore is disabled: an
                    # identity-resolution caller must never rename/annotate an
                    # archived card ahead of its own rejection — the local
                    # identity it sends may not be this card's person (Codex
                    # 2026-07-19 round 9, F14). No restore, no name/notes/recap.
                    return {
                        "client_id": cid,
                        "was_created": False,
                        "action": "skipped_archived",
                        "matched_count": matched_count,
                        "recap_applied": False,
                        "was_archived": True,
                    }
                set_parts: list[str] = []
                params: list[Any] = []
                pi = 1

                if was_archived and payload.restore_if_archived:
                    set_parts.append("deleted_at = NULL")
                    set_parts.append("deleted_by = NULL")
                if payload.improve_name and _name_is_better(payload.full_name, row["full_name"]):
                    set_parts.append(f"full_name = ${pi}")
                    params.append(payload.full_name.strip())  # type: ignore[union-attr]
                    pi += 1
                # Append notes at most once per `notes_append_min_age_hours` window
                # (the cron fires every ~5min; without this gate enrich would bloat
                # notes on every run). Gate on the authoritative Fly `updated_at`.
                _ua = row["updated_at"]
                if _ua is not None and _ua.tzinfo is None:
                    _ua = _ua.replace(tzinfo=timezone.utc)
                _notes_stale = _ua is None or (
                    datetime.now(timezone.utc) - _ua
                    >= timedelta(hours=payload.notes_append_min_age_hours)
                )
                if payload.notes_append and _notes_stale:
                    sep = "\n\n" if (row["notes"] or "").strip() else ""
                    set_parts.append(f"notes = COALESCE(NULLIF(notes, ''), '') || ${pi}")
                    params.append(sep + payload.notes_append)
                    pi += 1

                recap_applied = False
                if payload.strategic_recap and (row["strategic_recap_source"] or "") != "manual":
                    set_parts.append(f"strategic_recap = ${pi}")
                    params.append(payload.strategic_recap)
                    pi += 1
                    # 'ollama_local' is the only constraint-valid automated source
                    # (clients_strategic_recap_source_check, mig 189). 'manual' is human.
                    set_parts.append("strategic_recap_source = 'ollama_local'")
                    set_parts.append("strategic_recap_updated_at = NOW()")
                    recap_applied = True

                if set_parts:
                    set_parts.append("updated_at = NOW()")
                    set_parts.append(f"updated_by = ${pi}")
                    params.append(actor)
                    pi += 1
                    params.append(cid)
                    # set_parts are hardcoded column assignments; only $N placeholders
                    # are interpolated (param indices) — values stay parameterized.
                    await conn.execute(
                        f"UPDATE clients SET {', '.join(set_parts)} WHERE id = ${pi}",
                        *params,
                    )
                    action = "enriched"
                else:
                    action = "skipped_no_change"

                result: dict[str, Any] = {
                    "client_id": cid,
                    "was_created": False,
                    "action": action,
                    "matched_count": matched_count,
                    "recap_applied": recap_applied,
                    # The matched row was soft-deleted at match time. Identity
                    # RESOLUTION callers (intake delivery) treat this as
                    # unresolvable: an archived row cannot prove a live
                    # identity (Codex 2026-07-19 round 8, F11 archive gap).
                    "was_archived": was_archived,
                }
            else:
                if not payload.create_if_missing:
                    return {
                        "client_id": None,
                        "was_created": False,
                        "action": "skipped_not_found",
                        "matched_count": 0,
                        "recap_applied": False,
                        "was_archived": False,
                    }
                if not payload.full_name or not payload.full_name.strip():
                    raise HTTPException(
                        status_code=422, detail="full_name required to create a new lead"
                    )
                new_id = await conn.fetchval(
                    """
                    INSERT INTO clients (
                      full_name, phone, whatsapp, phone_normalized,
                      status, client_type, lead_source, assigned_to,
                      created_by, updated_by, notes,
                      strategic_recap, strategic_recap_source, strategic_recap_updated_at
                    ) VALUES (
                      $1, '+' || $2, '+' || $2, $2,
                      'lead', 'individual', $3, $4,
                      $5, $5, $6,
                      $7::text,
                      CASE WHEN $7::text IS NULL THEN NULL ELSE 'ollama_local' END,
                      CASE WHEN $7::text IS NULL THEN NULL ELSE NOW() END
                    )
                    RETURNING id
                    """,
                    payload.full_name.strip(),
                    phone,
                    payload.lead_source,
                    payload.assigned_to,
                    actor,
                    payload.notes_append,
                    payload.strategic_recap,
                )
                result = {
                    "client_id": new_id,
                    "was_created": True,
                    "action": "inserted",
                    "matched_count": 0,
                    "recap_applied": bool(payload.strategic_recap),
                    "was_archived": False,
                }

    # Cache invalidation OUTSIDE the transaction (HTTP-layer cache; best-effort).
    try:
        await invalidate_cache("zantara:crm_clients_stats:*")
    except Exception as exc:  # pragma: no cover - cache best-effort
        logger.warning("upsert-by-phone: cache invalidation failed: %s", exc)

    if result.get("matched_count", 0) > 1:
        # Do NOT log the phone (PII / UU PDP + log-injection: it's user-supplied).
        # client_id + matched_count are non-PII DB integers and fully identify the row.
        logger.warning(
            "upsert-by-phone: %s clients share a phone (acted on id=%s) — "
            "review for possible duplicate-client merge",
            result["matched_count"],
            result["client_id"],
        )
    return result


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
            await verify_client_access(
                client_id, current_user, conn, allow_assigned=True, write=True
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
                "tax_consultant": "tax_consultant",
                "avatar_url": "avatar_url",
                "address": "address",
                "notes": "notes",
                "strategic_recap": "strategic_recap",
                "tags": "tags",
                "custom_fields": "custom_fields",
                "lead_source": "lead_source",
                "service_interest": "service_interest",
                "gender": "gender",
                "birthplace": "birthplace",
                "tax_id": "tax_id",
                "npwp": "npwp",
                "nib": "nib",
                "current_visa_type": "current_visa_type",
                "current_visa_sponsor": "current_visa_sponsor",
            }

            # Date fields that need empty string → None conversion
            date_fields = {"passport_expiry", "date_of_birth"}

            # Fields that are allowed to be explicitly set to NULL (clearing a value).
            # Without this, the loop below would silently drop None values.
            nullable_fields = {"tax_consultant"}

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

                # NPWP is a strong-id key (the intake m248 matcher corroborates
                # doc→client on it): store canonical ASCII digits only, and refuse
                # incomplete values outright — a fragment on the card poisons
                # strong-id matching downstream. Empty string → skip (no write;
                # previously it stored "" on the column).
                if field == "npwp" and value is not None:
                    digits = re.sub(r"[^0-9]", "", str(value))
                    if not str(value).strip():
                        value = None
                    elif len(digits) not in (15, 16):
                        raise HTTPException(
                            status_code=422,
                            detail="npwp must contain exactly 15 or 16 digits",
                        )
                    else:
                        value = digits

                # Allow explicit NULL assignment for nullable fields
                if value is not None or field in nullable_fields:
                    column_name = field_mapping[field]
                    update_fields.append(f"{column_name} = ${param_index}")
                    params.append(value)
                    param_index += 1

            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")

            # If strategic_recap was edited by a human AND the value actually changed,
            # bump source -> 'manual' + timestamp. Guard against full-payload saves: the
            # frontend resubmits the whole client (incl. unchanged strategic_recap), which
            # would otherwise silently flip every recap to 'manual' and permanently lock
            # out the automated wa-mirror recap updater (panel finding 2026-06-06).
            if "strategic_recap" in updates.dict(exclude_unset=True):
                _current_recap = await conn.fetchval(
                    "SELECT strategic_recap FROM clients WHERE id = $1", client_id
                )
                if (updates.strategic_recap or None) != (_current_recap or None):
                    update_fields.append("strategic_recap_updated_at = NOW()")
                    update_fields.append("strategic_recap_source = 'manual'")

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

            if updates.phone is not None:
                # Phone is an identity-resolution key: intake delivery resolves
                # the Fly identity by it while holding 'phonecore:' advisory
                # locks. Changing a phone must be COOPERATIVE with that window
                # (Codex 2026-07-19 rounds 9-10, F12): lock the canonical cores
                # of the NEW value plus everything the row currently holds,
                # with a re-read-under-lock CONVERGENCE loop — the pre-lock
                # read can be stale (a racing PATCH may land between our read
                # and our locks), so keep re-reading and additively locking
                # until the row's cores are fully covered by locks we hold.
                async with conn.transaction():
                    _locked: set[str] = set()
                    for _ in range(3):
                        _cur = await conn.fetchrow(
                            "SELECT phone, phone_normalized FROM clients WHERE id = $1",
                            client_id,
                        )
                        _want = {
                            c
                            for c in (
                                phone_core(updates.phone),
                                phone_core(_row_str(_cur, "phone")),
                                phone_core(_row_str(_cur, "phone_normalized")),
                            )
                            if c is not None
                        }
                        if _want <= _locked:
                            break
                        _locked |= await lock_phone_cores(
                            conn,
                            updates.phone,
                            _row_str(_cur, "phone"),
                            _row_str(_cur, "phone_normalized"),
                        )
                    row = await conn.fetchrow(query, *params)  # nosemgrep
            else:
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
                spawn(
                    notif_service.notify_profile_updated(
                        client_id=client_id,
                        updated_fields=updated_field_names,
                        sent_by=user_email,
                    ),
                )
            except Exception as e:
                logger.error("Portal notification for profile update failed: %s", e)

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
            await verify_client_access(
                client_id, current_user, conn, allow_assigned=True, write=True
            )

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
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get overall client statistics

    Returns counts by status, top assigned team members, etc.

    Access Control:
    - Admin: sees global stats across all clients
    - Team member: sees only stats for clients assigned to them

    Performance: Cached for 5 minutes to reduce database load.

    Cache safety: the @cached decorator hashes the call kwargs, which include
    the authenticated user (a JSON-serializable dict) — so every user gets a
    distinct cache entry and cannot be served another user's aggregate.
    Mirrors get_practices_stats in crm_practices.py.
    """
    try:
        # RBAC: admins see the whole book; non-admin team members are scoped to
        # their own assigned clients. For scoped (non-admin) requests $1 is the
        # user email in every query below (the only pre-existing param,
        # STATS_DAYS_RECENT, shifts to $2 in the new_last_30_days query).
        user_email = (
            current_user.get("email", "").lower()
            if isinstance(current_user, dict)
            else ""
        )
        scoped = bool(user_email) and not is_crm_admin(current_user)

        async with db_pool.acquire() as conn:
            # Total clients by status (exclude soft-deleted)
            by_status_rows = await conn.fetch(
                f"""
                SELECT status, COUNT(*) as count
                FROM clients
                WHERE deleted_at IS NULL{" AND assigned_to = $1" if scoped else ""}
                GROUP BY status
                """,
                *([user_email] if scoped else []),
            )

            # Clients by assigned team member (exclude soft-deleted)
            by_team_member_rows = await conn.fetch(
                f"""
                SELECT assigned_to, COUNT(*) as count
                FROM clients
                WHERE assigned_to IS NOT NULL AND deleted_at IS NULL{
                    " AND assigned_to = $1" if scoped else ""
                }
                GROUP BY assigned_to
                ORDER BY count DESC
                """,
                *([user_email] if scoped else []),
            )

            # New clients last N days
            if scoped:
                new_last_30_days_row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as count
                    FROM clients
                    WHERE assigned_to = $1
                        AND created_at >= NOW() - INTERVAL '1 day' * $2
                    """,
                    user_email,
                    STATS_DAYS_RECENT,
                )
            else:
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
                f"""
                SELECT pt.name as practice_type, COUNT(p.id) as count
                FROM practices p
                JOIN practice_types pt ON p.practice_type_id = pt.id
                {"WHERE p.assigned_to = $1" if scoped else ""}
                GROUP BY pt.name
                ORDER BY count DESC
                """,
                *([user_email] if scoped else []),
            )

            # Passport health counts
            passport_health_row = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE passport_expiry < CURRENT_DATE) as expired,
                    COUNT(*) FILTER (WHERE passport_expiry >= CURRENT_DATE AND passport_expiry <= CURRENT_DATE + INTERVAL '90 days') as expiring_soon,
                    COUNT(*) FILTER (WHERE last_interaction_date < NOW() - INTERVAL '30 days' OR last_interaction_date IS NULL) as silent_30d
                FROM clients
                WHERE deleted_at IS NULL AND status != 'inactive'
                    AND passport_expiry IS NOT NULL{" AND assigned_to = $1" if scoped else ""}
                """,
                *([user_email] if scoped else []),
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
                "passport_expiring_soon": passport_health_row["expiring_soon"]
                if passport_health_row
                else 0,
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
                "SELECT id, full_name, assigned_to FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )

            if not client:
                raise HTTPException(status_code=404, detail="Client not found")

        # Get audit trail
        trail = await audit_logger.get_audit_trail(
            entity_type="client",
            entity_id=client_id,
            limit=limit,
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
# AI SUMMARY (Phase 1 cross-folder L1 — CRM-Guardian)
# ================================================


class AiSummaryResponse(BaseModel):
    """Response model for GET /api/crm/clients/{id}/ai-summary.

    Wraps the JSONB blob from clients.ai_summary with freshness metadata.
    The summary itself follows L1ClientSummary v2.0 schema (see
    apps/backend-rag/backend/services/crm_guardian/schemas.py).
    """

    client_id: int
    summary: dict[str, Any] | None
    generated_at: datetime | None
    schema_version: str | None
    fingerprint: str | None
    status: str  # 'available' | 'not_generated' | 'pending'


class WaCaseIntelligenceCard(BaseModel):
    """One Zantara Captain card linked to a client's WhatsApp conversation."""

    id: int
    conversation_key: str
    member_phone: str | None = None
    counterpart_key: str | None = None
    display_name: str | None = None
    chat_kind: str
    case_status: str
    case_type: str | None = None
    source_model: str
    reasoning_effort: str | None = None
    analysis_hash: str
    analysis_id: str | None = None
    message_count: int
    unread_count: int
    last_message_at: datetime | None = None
    priority_score: int
    flags: list[dict[str, Any]]
    recap: str | None = None
    next_action: str | None = None
    ideal_reply: str | None = None
    evidence: str | None = None
    crm_packet: str | None = None
    raw_sections: dict[str, Any]
    analysis_output_path: str | None = None
    generated_at: datetime | None = None
    imported_at: datetime
    updated_at: datetime


class WaCaseIntelligenceResponse(BaseModel):
    client_id: int
    status: str  # 'available' | 'not_generated'
    case_count: int
    cases: list[WaCaseIntelligenceCard]


def _coerce_json_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _coerce_json_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


@router.get(
    "/{client_id}/ai-summary",
    operation_id="get_crm_client_ai_summary",
    response_model=AiSummaryResponse,
)
async def get_client_ai_summary(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> AiSummaryResponse:
    """Fetch the L1 AI summary for a client (cross-folder Phase 1).

    The summary is produced by the CRM-Guardian gemini CLI worker
    (scripts/crm_guardian_gemini_cli_worker.py) reading Drive folder of
    the client + all linked active companies (client_company_links).

    Access control:
      - Admin (`is_crm_admin`): can read any client's summary
      - Team member: can read only clients matching their RBAC filter
        (own assigned_to or null assigned_to)
      - Non-team: 403

    Returns 404 if client doesn't exist (or RBAC denies visibility);
    200 with `status='not_generated'` and null fields if the worker hasn't
    yet processed this client; 200 with `status='available'` and the JSONB
    payload otherwise; 200 with `status='pending'` if a queue row is
    waiting/running.
    """
    start_time = time.time()

    # RBAC: enforce per-user filter unless admin
    assigned_filter: str | None = None
    if not is_crm_admin(current_user):
        assigned_filter = get_crm_user_filter(current_user)

    try:
        async with db_pool.acquire() as conn:
            # Verify access (raises 404 if RBAC blocks or client missing)
            if assigned_filter is not None:
                row = await conn.fetchrow(
                    """
                    SELECT id, ai_summary, ai_summary_generated_at,
                           ai_summary_schema_version, ai_summary_file_hash
                    FROM clients
                    WHERE id = $1
                      AND (assigned_to = $2 OR assigned_to IS NULL)
                    """,
                    client_id,
                    assigned_filter,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT id, ai_summary, ai_summary_generated_at,
                           ai_summary_schema_version, ai_summary_file_hash
                    FROM clients WHERE id = $1
                    """,
                    client_id,
                )
            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Client {client_id} not found or not accessible",
                )

            # Resolve summary status
            if row["ai_summary"] is not None:
                # asyncpg returns JSONB as a Python dict already, but the
                # column may have been written as a raw json text on older
                # rows — guard against str.
                summary_payload = row["ai_summary"]
                if isinstance(summary_payload, str):
                    import json as _json

                    summary_payload = _json.loads(summary_payload)

                # CodeQL log-injection: cast to int defangs any non-numeric
                # injection vector even though FastAPI already validates the
                # path param as int (defense in depth).
                safe_client_id = int(client_id)
                safe_schema = (
                    str(row["ai_summary_schema_version"] or "")
                    .replace(
                        "\n",
                        " ",
                    )
                    .replace("\r", " ")[:64]
                )
                safe_fp = (row["ai_summary_file_hash"] or "")[:12]
                logger.info(
                    "ai_summary served client_id=%d schema=%s fp=%s elapsed_ms=%d",
                    safe_client_id,
                    safe_schema,
                    safe_fp,
                    int((time.time() - start_time) * 1000),
                )
                return AiSummaryResponse(
                    client_id=client_id,
                    summary=summary_payload,
                    generated_at=row["ai_summary_generated_at"],
                    schema_version=row["ai_summary_schema_version"],
                    fingerprint=row["ai_summary_file_hash"],
                    status="available",
                )

            # No summary yet — check if queued
            queue_row = await conn.fetchrow(
                """
                SELECT status FROM crm_guardian_summary_queue
                WHERE client_id = $1 AND status IN ('pending', 'running')
                LIMIT 1
                """,
                client_id,
            )
            queue_status = queue_row["status"] if queue_row else None

            return AiSummaryResponse(
                client_id=client_id,
                summary=None,
                generated_at=None,
                schema_version=None,
                fingerprint=None,
                status="pending" if queue_status else "not_generated",
            )

    except HTTPException:
        raise
    except Exception as e:
        # CodeQL log-injection: cast to int defangs any non-numeric path.
        logger.exception(
            "ai_summary fetch failed for client %d",
            int(client_id),
        )
        raise handle_database_error(e) from e


@router.get(
    "/{client_id}/wa-case-intelligence",
    operation_id="get_crm_client_wa_case_intelligence",
    response_model=WaCaseIntelligenceResponse,
)
async def get_client_wa_case_intelligence(
    client_id: int,
    limit: int = Query(12, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> WaCaseIntelligenceResponse:
    """Fetch Zantara Captain case cards derived from WhatsApp analysis.

    This endpoint is read-only. It intentionally returns case-level intelligence
    separately from clients.strategic_recap so the CRM can show per-conversation
    reasoning, evidence, ideal reply, and next action without flattening multiple
    cases into a single paragraph.
    """
    try:
        async with db_pool.acquire() as conn:
            await verify_client_access(client_id, current_user, conn, allow_assigned=True)
            rows = await conn.fetch(
                """
                SELECT id, conversation_key, member_phone, counterpart_key, display_name,
                       chat_kind, case_status, case_type, source_model, reasoning_effort,
                       analysis_hash, analysis_id, message_count, unread_count,
                       last_message_at, priority_score, flags, recap, next_action,
                       ideal_reply, evidence, crm_packet, raw_sections,
                       analysis_output_path, generated_at, imported_at, updated_at
                FROM crm_wa_case_intelligence
                WHERE client_id = $1
                ORDER BY priority_score DESC, last_message_at DESC NULLS LAST, updated_at DESC
                LIMIT $2
                """,
                client_id,
                limit,
            )

            cases: list[WaCaseIntelligenceCard] = []
            for row in rows:
                payload = dict(row)
                payload["flags"] = _coerce_json_list(payload.get("flags"))
                payload["raw_sections"] = _coerce_json_dict(payload.get("raw_sections"))
                cases.append(WaCaseIntelligenceCard(**payload))

            return WaCaseIntelligenceResponse(
                client_id=client_id,
                status="available" if cases else "not_generated",
                case_count=len(cases),
                cases=cases,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "wa_case_intelligence fetch failed for client %d",
            int(client_id),
        )
        raise handle_database_error(e) from e


# ================================================

# OCR, METRICS, DOCUMENT ENDPOINTS → crm_clients_documents.py
