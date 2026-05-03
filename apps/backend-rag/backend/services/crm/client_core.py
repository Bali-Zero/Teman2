"""
CRM Client Core — consolidated module.

Merges:
  - validators.py          (ClientValidator, PracticeValidator, InteractionValidator,
                             sanitize_input, validate_uuid, normalize_phone_e164,
                             extract_entities_from_text)
  - audit_trail.py         (AuditAction, CRMAuditor, CREATE_AUDIT_TABLE_SQL, init_audit_table)
  - enhanced_crm_service.py (EnhancedCRMService, get_enhanced_crm_service)
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from enum import Enum
from typing import Any

import asyncpg
from pydantic import BaseModel, EmailStr, Field, ValidationError as PydanticValidationError, field_validator

from backend.app.core.exceptions import (
    DatabaseError,
    ResourceNotFoundError,
    ValidationError,
)
from backend.app.utils.error_sanitizer import sanitize_error_message
from backend.services.common.cache import cache_invalidating
from backend.services.crm.cache_query import (
    CRMQueryOptimizer,
    crm_cache,
    health_check_crm_tables,
    invalidate_client_cache,
    query_cache,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Validators (from validators.py)
# ─────────────────────────────────────────────────────────────────────────────

class ClientValidator(BaseModel):
    """Validatore per dati cliente."""

    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    whatsapp: str | None = Field(None, max_length=50)
    nationality: str | None = Field(None, max_length=100)
    passport_number: str | None = Field(None, max_length=100)
    # Fields that were silently dropped by Pydantic extra="ignore" default
    status: str = "active"
    client_type: str = "individual"
    assigned_to: str | None = None
    created_by: str | None = None
    avatar_url: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    lead_source: str | None = None
    service_interest: list[str] = Field(default_factory=list)
    tax_id: str | None = None
    passport_expiry: str | None = None
    date_of_birth: str | None = None
    company_name: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Valida e pulisce il nome."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return re.sub(r"\s+", " ", v)

    @field_validator("phone", "whatsapp")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Valida formato telefono."""
        if not v:
            return None
        cleaned = re.sub(r"[^\d+]", "", v)
        if len(cleaned) < 8:
            raise ValueError("Phone number too short")
        return cleaned

    @field_validator("passport_number")
    @classmethod
    def validate_passport(cls, v: str | None) -> str | None:
        """Valida formato passport."""
        if not v:
            return None
        if not re.match(r"^[A-Z0-9]+$", v.upper()):
            raise ValueError("Invalid passport format")
        return v.upper()


class PracticeValidator(BaseModel):
    """Validatore per pratiche."""

    client_id: int = Field(..., gt=0)
    practice_type_id: int = Field(..., gt=0)
    status: str = Field(default="inquiry")
    priority: str = Field(default="normal")
    quoted_price: float | None = Field(None, ge=0)
    actual_price: float | None = Field(None, ge=0)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status."""
        allowed = {
            "inquiry",
            "waiting_documents",
            "sending_invoice",
            "on_process",
            "completed",
        }
        if v not in allowed:
            raise ValueError(f"Status must be one of: {allowed}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """Validate priority."""
        allowed = {"low", "normal", "high", "urgent"}
        if v not in allowed:
            raise ValueError(f"Priority must be one of: {allowed}")
        return v


class InteractionValidator(BaseModel):
    """Validatore per interazioni."""

    client_id: int | None = Field(None, gt=0)
    practice_id: int | None = Field(None, gt=0)
    interaction_type: str
    channel: str | None = None
    subject: str | None = Field(None, max_length=500)
    summary: str | None = None
    sentiment: str | None = Field(None, max_length=20)

    @field_validator("interaction_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate type."""
        allowed = {"chat", "email", "whatsapp", "call", "meeting", "note"}
        if v not in allowed:
            raise ValueError(f"Type must be one of: {allowed}")
        return v

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, v: str | None) -> str | None:
        """Validate sentiment."""
        if not v:
            return None
        allowed = {"positive", "neutral", "negative", "urgent"}
        if v not in allowed:
            raise ValueError(f"Sentiment must be one of: {allowed}")
        return v


def sanitize_input(value: str | None, max_length: int = 255) -> str | None:
    """Sanitizza input stringa."""
    if not value:
        return None
    value = value.strip()
    if len(value) > max_length:
        value = value[:max_length]
    return re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", value)


def validate_uuid(uuid: str) -> bool:
    """Valida formato UUID."""
    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    return bool(re.match(pattern, uuid.lower()))


def normalize_phone_e164(phone: str) -> str | None:
    """
    Normalizza numero telefono a formato E.164.

    Args:
        phone: Numero telefono in qualsiasi formato

    Returns:
        Numero normalizzato o None se invalido
    """
    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)

    if len(digits) < 8:
        return None

    # Handle Indonesian numbers
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits

    return "+" + digits


def extract_entities_from_text(text: str) -> dict[str, Any]:
    """
    Estrae entità rilevanti da testo conversazione.

    Returns:
        Dict con email, phone, passport trovati
    """
    entities: dict[str, Any] = {"emails": [], "phones": [], "passports": [], "dates": []}

    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    entities["emails"] = re.findall(email_pattern, text)

    phone_pattern = (
        r"(?:\+62|62|0)[\s-]?8[\s-]?[0-9]{1}[\s-]?[0-9]{3}[\s-]?[0-9]{2}[\s-]?[0-9]{2,3}"
    )
    phones = re.findall(phone_pattern, text)
    entities["phones"] = [normalize_phone_e164(p) for p in phones if normalize_phone_e164(p)]

    passport_pattern = r"\b[A-Z]{1,2}[0-9]{6,9}\b"
    entities["passports"] = re.findall(passport_pattern, text.upper())

    return entities


# ─────────────────────────────────────────────────────────────────────────────
# Audit Trail (from audit_trail.py)
# ─────────────────────────────────────────────────────────────────────────────

class AuditAction(str, Enum):
    """Tipi di azioni auditabili."""

    CLIENT_CREATED = "client_created"
    CLIENT_UPDATED = "client_updated"
    CLIENT_DELETED = "client_deleted"
    PRACTICE_CREATED = "practice_created"
    PRACTICE_UPDATED = "practice_updated"
    PRACTICE_DELETED = "practice_deleted"
    PRACTICE_STATUS_CHANGED = "practice_status_changed"
    INTERACTION_CREATED = "interaction_created"
    INTERACTION_UPDATED = "interaction_updated"
    ASSIGNMENT_CHANGED = "assignment_changed"
    DATA_EXPORTED = "data_exported"
    BULK_OPERATION = "bulk_operation"


class CRMAuditor:
    """Sistema audit per CRM."""

    def __init__(self, db_pool: asyncpg.Pool, buffer_size: int = 100) -> None:
        self.db_pool = db_pool
        self._buffer: list[dict] = []
        self._buffer_size = buffer_size
        self._flush_task: asyncio.Task | None = None

    def start_periodic_flush(self, interval_seconds: int = 60) -> None:
        """Start background task to periodically flush the audit buffer."""

        async def _periodic_flush() -> None:
            while True:
                await asyncio.sleep(interval_seconds)
                if self._buffer:
                    await self._flush_buffer()

        self._flush_task = asyncio.create_task(_periodic_flush())

    def stop_periodic_flush(self) -> None:
        """Stop the periodic flush background task."""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()

    async def log(
        self,
        action: AuditAction,
        entity_type: str,
        entity_id: int | str,
        user_id: str | None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Registra un evento audit.

        Args:
            action: Tipo azione
            entity_type: Tipo entità (client, practice, etc.)
            entity_id: ID entità
            user_id: ID utente che ha eseguito l'azione
            old_values: Valori precedenti (per update)
            new_values: Nuovi valori
            metadata: Metadati addizionali
        """
        try:
            changes = None
            if old_values and new_values:
                changes = self._calculate_changes(old_values, new_values)

            entry = {
                "action": action.value,
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "user_id": user_id or "system",
                "changes": changes,
                "old_values": self._sanitize_values(old_values),
                "new_values": self._sanitize_values(new_values),
                "metadata": metadata or {},
                "ip_address": metadata.get("ip_address") if metadata else None,
                "user_agent": metadata.get("user_agent") if metadata else None,
            }

            self._buffer.append(entry)

            if len(self._buffer) >= self._buffer_size:
                await self._flush_buffer()

        except (asyncpg.PostgresError, OSError) as e:
            logger.warning(f"Failed to log audit entry (DB): {sanitize_error_message(e)}")
        except Exception as e:
            logger.exception(f"Failed to log audit entry: {sanitize_error_message(e)}")

    async def log_client_created(
        self,
        client_id: int,
        user_id: str | None,
        client_data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log creazione cliente."""
        await self.log(
            action=AuditAction.CLIENT_CREATED,
            entity_type="client",
            entity_id=client_id,
            user_id=user_id,
            new_values=client_data,
            metadata=metadata,
        )

    async def log_client_updated(
        self,
        client_id: int,
        user_id: str | None,
        old_data: dict[str, Any],
        new_data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log aggiornamento cliente."""
        await self.log(
            action=AuditAction.CLIENT_UPDATED,
            entity_type="client",
            entity_id=client_id,
            user_id=user_id,
            old_values=old_data,
            new_values=new_data,
            metadata=metadata,
        )

    async def log_practice_status_change(
        self,
        practice_id: int,
        user_id: str | None,
        old_status: str,
        new_status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log cambio stato pratica."""
        await self.log(
            action=AuditAction.PRACTICE_STATUS_CHANGED,
            entity_type="practice",
            entity_id=practice_id,
            user_id=user_id,
            old_values={"status": old_status},
            new_values={"status": new_status},
            metadata=metadata,
        )

    async def log_assignment_change(
        self,
        entity_type: str,
        entity_id: int,
        user_id: str | None,
        old_assignee: str | None,
        new_assignee: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log cambio assegnazione."""
        await self.log(
            action=AuditAction.ASSIGNMENT_CHANGED,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            old_values={"assigned_to": old_assignee},
            new_values={"assigned_to": new_assignee},
            metadata=metadata,
        )

    async def get_audit_trail(
        self,
        entity_type: str | None = None,
        entity_id: int | str | None = None,
        user_id: str | None = None,
        action: AuditAction | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """
        Recupera audit trail con filtri.

        Returns:
            Tuple (records, total_count)
        """
        async with self.db_pool.acquire() as conn:
            conditions = ["1=1"]
            params: list[Any] = []

            if entity_type:
                conditions.append(f"entity_type = ${len(params) + 1}")
                params.append(entity_type)

            if entity_id:
                conditions.append(f"entity_id = ${len(params) + 1}")
                params.append(str(entity_id))

            if user_id:
                conditions.append(f"user_id = ${len(params) + 1}")
                params.append(user_id)

            if action:
                conditions.append(f"action = ${len(params) + 1}")
                params.append(action.value)

            if start_date:
                conditions.append(f"created_at >= ${len(params) + 1}")
                params.append(start_date)

            if end_date:
                conditions.append(f"created_at <= ${len(params) + 1}")
                params.append(end_date)

            where_clause = " AND ".join(conditions)

            count_sql = f"SELECT COUNT(*) FROM crm_audit_log WHERE {where_clause}"
            total = await conn.fetchval(count_sql, *params)

            data_sql = f"""
                SELECT * FROM crm_audit_log
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
            """
            params.extend([limit, offset])

            rows = await conn.fetch(data_sql, *params)
            return [dict(row) for row in rows], total

    async def _flush_buffer(self) -> None:
        """Scrive buffer su database."""
        if not self._buffer:
            return

        try:
            async with self.db_pool.acquire() as conn:
                query = """
                    INSERT INTO crm_audit_log (
                        action, entity_type, entity_id, user_id,
                        changes, old_values, new_values, metadata,
                        ip_address, user_agent, created_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW()
                    )
                """

                for entry in self._buffer:
                    await conn.execute(
                        query,
                        entry["action"],
                        entry["entity_type"],
                        entry["entity_id"],
                        entry["user_id"],
                        json.dumps(entry["changes"]) if entry["changes"] else None,
                        json.dumps(entry["old_values"]) if entry["old_values"] else None,
                        json.dumps(entry["new_values"]) if entry["new_values"] else None,
                        json.dumps(entry["metadata"]),
                        entry.get("ip_address"),
                        entry.get("user_agent"),
                    )

            logger.debug(f"Flushed {len(self._buffer)} audit entries")
            self._buffer.clear()

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to flush audit buffer (serialization): {sanitize_error_message(e)}")
        except (asyncpg.PostgresError, OSError) as e:
            logger.warning(f"Failed to flush audit buffer (DB): {sanitize_error_message(e)}")
        except Exception as e:
            logger.exception(f"Failed to flush audit buffer: {sanitize_error_message(e)}")

    def _calculate_changes(
        self, old_values: dict[str, Any], new_values: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Calcola differenze tra old e new values."""
        changes = {}
        all_keys = set(old_values.keys()) | set(new_values.keys())

        for key in all_keys:
            old_val = old_values.get(key)
            new_val = new_values.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}

        return changes

    def _sanitize_values(self, values: dict[str, Any] | None) -> dict[str, Any] | None:
        """Rimuove dati sensibili dai valori."""
        if not values:
            return None

        sensitive_fields = {"password", "token", "api_key", "secret"}
        sanitized = {}

        for key, value in values.items():
            if any(s in key.lower() for s in sensitive_fields):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value

        return sanitized

    async def close(self) -> None:
        """Flush rimanente e chiudi."""
        self.stop_periodic_flush()
        if self._buffer:
            await self._flush_buffer()


# SQL per creare tabella audit (da eseguire una sola volta)
CREATE_AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS crm_audit_log (
    id SERIAL PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    changes JSONB,
    old_values JSONB,
    new_values JSONB,
    metadata JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indici per query frequenti
    CONSTRAINT idx_crm_audit_entity
        UNIQUE (entity_type, entity_id, created_at)
);

-- Indici
CREATE INDEX IF NOT EXISTS idx_audit_action ON crm_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_user ON crm_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON crm_audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_entity_lookup ON crm_audit_log(entity_type, entity_id);
"""


async def init_audit_table(db_pool: asyncpg.Pool) -> None:
    """Inizializza tabella audit se non esiste."""
    async with db_pool.acquire() as conn:
        await conn.execute(CREATE_AUDIT_TABLE_SQL)
        logger.info("CRM audit table initialized")


# ─────────────────────────────────────────────────────────────────────────────
# EnhancedCRMService (from enhanced_crm_service.py)
# ─────────────────────────────────────────────────────────────────────────────

class EnhancedCRMService:
    """
    Servizio CRM ottimizzato e production-ready.

    Features:
    - Validazione automatica input
    - Caching livello query
    - Audit trail completo
    - Batch operations
    - Error handling robusto
    """

    # Allowed columns for dynamic UPDATE to prevent SQL injection
    ALLOWED_CLIENT_COLUMNS = frozenset(
        {
            "full_name",
            "email",
            "phone",
            "whatsapp",
            "nationality",
            "passport_number",
            "status",
            "client_type",
            "assigned_to",
            "custom_fields",
            "tags",
            "notes",
        },
    )

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.optimizer = CRMQueryOptimizer(db_pool)
        self.auditor = CRMAuditor(db_pool)
        self._initialized = False

    async def initialize(self) -> None:
        """Inizializza servizio (tabelle, cache, etc.)."""
        if self._initialized:
            return

        try:
            await init_audit_table(self.db_pool)

            async with self.db_pool.acquire() as conn:
                types = await conn.fetch(
                    "SELECT id, code, name FROM practice_types WHERE active = true",
                )
                await query_cache.set_practice_types([dict(t) for t in types])

            self._initialized = True
            logger.info("✅ EnhancedCRMService initialized successfully")

        except (asyncpg.PostgresError, OSError) as e:
            logger.warning(f"Failed to initialize CRM service (DB): {sanitize_error_message(e)}")
            raise
        except Exception as e:
            logger.exception(f"Failed to initialize CRM service: {sanitize_error_message(e)}")
            raise

    # ==================== CLIENT OPERATIONS ====================

    @cache_invalidating([
        "zantara:crm_clients_stats:*",
        "zantara:crm_clients:*",
    ])
    async def create_client(
        self,
        client_data: dict[str, Any],
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Crea nuovo cliente con validazione e audit."""
        try:
            validated = ClientValidator(**client_data)

            existing = await self._find_duplicate_client(validated.model_dump())
            if existing:
                raise ValidationError(
                    "Client already exists with email or phone", {"existing_id": existing},
                )

            async with self.db_pool.acquire() as conn:
                query = """
                    INSERT INTO clients (
                        full_name, email, phone, whatsapp, nationality,
                        passport_number, status, client_type, assigned_to,
                        custom_fields, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())
                    RETURNING *
                """

                row = await conn.fetchrow(
                    query,
                    validated.full_name,
                    validated.email,
                    validated.phone,
                    validated.whatsapp,
                    validated.nationality,
                    validated.passport_number,
                    client_data.get("status", "active"),
                    client_data.get("client_type", "individual"),
                    client_data.get("assigned_to"),
                    client_data.get("custom_fields", {}),
                )

                result = dict(row)

            await self.auditor.log_client_created(
                client_id=result["id"],
                user_id=user_id,
                client_data=validated.model_dump(exclude_none=True),
                metadata=metadata,
            )

            logger.info(f"Created client {result['id']}: {validated.full_name}")
            return result

        except ValidationError:
            raise
        except PydanticValidationError as e:
            logger.warning(f"Failed to create client (validation): {sanitize_error_message(e)}")
            raise DatabaseError("Failed to create client", operation="insert")
        except (asyncpg.PostgresError, OSError) as e:
            logger.warning(f"Failed to create client (DB): {sanitize_error_message(e)}")
            raise DatabaseError("Failed to create client", operation="insert")
        except Exception as e:
            logger.exception(f"Failed to create client: {sanitize_error_message(e)}")
            raise DatabaseError("Failed to create client", operation="insert")

    @cache_invalidating([
        lambda self, client_id, *a, **k: f"zantara:crm_client:{client_id}:*",
        "zantara:crm_clients_stats:*",
        "zantara:crm_clients:*",
    ])
    async def update_client(
        self,
        client_id: int,
        updates: dict[str, Any],
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Aggiorna cliente con validazione delta e audit."""
        try:
            async with self.db_pool.acquire() as conn:
                old_data = await conn.fetchrow(
                    "SELECT * FROM clients WHERE id = $1 AND deleted_at IS NULL", client_id,
                )

                if not old_data:
                    raise ResourceNotFoundError("Client", str(client_id))

                old_dict = dict(old_data)

            if "full_name" in updates:
                ClientValidator(**{**old_dict, **updates})

            fields = []
            values = []
            for key, value in updates.items():
                if key not in self.ALLOWED_CLIENT_COLUMNS:
                    raise ValidationError(
                        f"Column '{key}' not allowed for client update",
                        {"allowed": sorted(self.ALLOWED_CLIENT_COLUMNS)},
                    )
                if key in old_dict and old_dict[key] != value:
                    fields.append(f"{key} = ${len(values) + 1}")
                    values.append(value)

            if not fields:
                return old_dict

            values.append(client_id)

            async with self.db_pool.acquire() as conn:
                query = f"""
                    UPDATE clients
                    SET {", ".join(fields)}, updated_at = NOW()
                    WHERE id = ${len(values)}
                    RETURNING *
                """

                row = await conn.fetchrow(query, *values)
                result = dict(row)

            invalidate_client_cache(client_id)

            await self.auditor.log_client_updated(
                client_id=client_id,
                user_id=user_id,
                old_data=old_dict,
                new_data=result,
                metadata=metadata,
            )

            logger.info(f"Updated client {client_id}")
            return result

        except ResourceNotFoundError:
            raise
        except (ValidationError, PydanticValidationError) as e:
            logger.warning(f"Failed to update client (validation): {sanitize_error_message(e)}")
            raise DatabaseError("Failed to update client", operation="update")
        except (asyncpg.PostgresError, OSError) as e:
            logger.warning(f"Failed to update client (DB): {sanitize_error_message(e)}")
            raise DatabaseError("Failed to update client", operation="update")
        except Exception as e:
            logger.exception(f"Failed to update client: {sanitize_error_message(e)}")
            raise DatabaseError("Failed to update client", operation="update")

    async def get_client(
        self, client_id: int, include_practices: bool = False,
    ) -> dict[str, Any] | None:
        """Recupera cliente con caching."""
        cache_key = f"client:{client_id}:practices:{include_practices}"

        cached = await crm_cache.get(cache_key)
        if cached:
            return cached

        try:
            if include_practices:
                results = await self.optimizer.get_clients_with_practices([client_id])
                result = results[0] if results else None
            else:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM clients WHERE id = $1 AND deleted_at IS NULL", client_id,
                    )
                    result = dict(row) if row else None

            if result:
                await crm_cache.set(cache_key, result, ttl=300)

            return result

        except (asyncpg.PostgresError, OSError) as e:
            logger.warning(f"Failed to get client (DB): {sanitize_error_message(e)}")
            raise DatabaseError("Failed to retrieve client", operation="select")
        except Exception as e:
            logger.exception(f"Failed to get client: {sanitize_error_message(e)}")
            raise DatabaseError("Failed to retrieve client", operation="select")

    async def search_clients(
        self, query: str, limit: int = 20, offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Ricerca clienti ottimizzata."""
        return await self.optimizer.search_clients_optimized(query, limit, offset)

    # ==================== PRACTICE OPERATIONS ====================

    @cache_invalidating([
        "zantara:crm_practices:*",
    ])
    async def create_practice(
        self,
        practice_data: dict[str, Any],
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Crea pratica con validazione."""
        try:
            validated = PracticeValidator(**practice_data)

            async with self.db_pool.acquire() as conn:
                query = """
                    INSERT INTO practices (
                        client_id, practice_type_id, status, priority,
                        inquiry_date, quoted_price, actual_price, currency,
                        assigned_to, notes, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, NOW(), $5, $6, $7, $8, $9, NOW(), NOW())
                    RETURNING *
                """

                row = await conn.fetchrow(
                    query,
                    validated.client_id,
                    validated.practice_type_id,
                    validated.status,
                    validated.priority,
                    validated.quoted_price,
                    validated.actual_price,
                    practice_data.get("currency", "IDR"),
                    practice_data.get("assigned_to"),
                    practice_data.get("notes"),
                )

                result = dict(row)

            await self.auditor.log(
                action=AuditAction.PRACTICE_CREATED,
                entity_type="practice",
                entity_id=result["id"],
                user_id=user_id,
                new_values=validated.model_dump(exclude_none=True),
                metadata=metadata,
            )

            logger.info(f"Created practice {result['id']} for client {validated.client_id}")
            return result

        except PydanticValidationError as e:
            logger.warning(f"Failed to create practice (validation): {sanitize_error_message(e)}")
            raise DatabaseError("Failed to create practice", operation="insert")
        except (asyncpg.PostgresError, OSError) as e:
            logger.warning(f"Failed to create practice (DB): {sanitize_error_message(e)}")
            raise DatabaseError("Failed to create practice", operation="insert")
        except Exception as e:
            logger.exception(f"Failed to create practice: {sanitize_error_message(e)}")
            raise DatabaseError("Failed to create practice", operation="insert")

    @cache_invalidating([
        lambda self, practice_id, *a, **k: f"zantara:crm_practice:{practice_id}:*",
        "zantara:crm_practices:*",
    ])
    async def update_practice_status(
        self,
        practice_id: int,
        new_status: str,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Aggiorna stato pratica con audit trail."""
        try:
            async with self.db_pool.acquire() as conn:
                old = await conn.fetchrow(
                    "SELECT status, client_id FROM practices WHERE id = $1", practice_id,
                )

                if not old:
                    raise ResourceNotFoundError("Practice", str(practice_id))

                old_status = old["status"]

                row = await conn.fetchrow(
                    """
                    UPDATE practices
                    SET status = $1, updated_at = NOW()
                    WHERE id = $2
                    RETURNING *
                    """,
                    new_status,
                    practice_id,
                )

                result = dict(row)

            await self.auditor.log_practice_status_change(
                practice_id=practice_id,
                user_id=user_id,
                old_status=old_status,
                new_status=new_status,
                metadata=metadata,
            )

            logger.info(f"Practice {practice_id} status: {old_status} -> {new_status}")

            # HR Bonus hook: auto-create bonus entry when practice completed
            if new_status == "completed" and old_status != "completed":
                await self._create_hr_bonus_entry(practice_id, result)

            return result

        except ResourceNotFoundError:
            raise
        except (asyncpg.PostgresError, OSError) as e:
            logger.warning(f"Failed to update practice status (DB): {sanitize_error_message(e)}")
            raise DatabaseError("Failed to update practice status", operation="update")
        except Exception as e:
            logger.exception(f"Failed to update practice status: {sanitize_error_message(e)}")
            raise DatabaseError("Failed to update practice status", operation="update")

    # ==================== BATCH OPERATIONS ====================

    @cache_invalidating([
        "zantara:crm_clients_stats:*",
        "zantara:crm_clients:*",
    ])
    async def batch_create_clients(
        self, clients: list[dict[str, Any]], user_id: str | None = None,
    ) -> list[int]:
        """Creazione batch clienti."""
        try:
            for c in clients:
                ClientValidator(**c)

            ids = await self.optimizer.batch_insert_clients(clients)

            logger.info(f"Batch created {len(ids)} clients")
            return ids

        except PydanticValidationError as e:
            logger.warning(f"Batch create failed (validation): {sanitize_error_message(e)}")
            raise DatabaseError("Batch creation failed", operation="batch_insert")
        except (asyncpg.PostgresError, OSError) as e:
            logger.warning(f"Batch create failed (DB): {sanitize_error_message(e)}")
            raise DatabaseError("Batch creation failed", operation="batch_insert")
        except Exception as e:
            logger.exception(f"Batch create failed: {sanitize_error_message(e)}")
            raise DatabaseError("Batch creation failed", operation="batch_insert")

    # ==================== HR BONUS HOOK ====================

    async def _create_hr_bonus_entry(
        self, practice_id: int, practice_data: dict[str, Any],
    ) -> None:
        """
        Auto-create a bonus ledger entry when a practice is completed.
        Non-blocking: logs warning on failure, never crashes the status update.
        """
        try:
            assigned_to = practice_data.get("assigned_to")
            if not assigned_to:
                return

            async with self.db_pool.acquire() as conn:
                table_exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'hr_bonus_rates')",
                )
                if not table_exists:
                    return

                pt = await conn.fetchrow(
                    """
                    SELECT pt.code FROM practice_types pt
                    JOIN practices p ON p.practice_type_id = pt.id
                    WHERE p.id = $1
                """,
                    practice_id,
                )
                if not pt:
                    logger.debug(f"HR bonus skip: practice {practice_id} has no practice_type")
                    return

                practice_type_code = pt["code"]

                rate = await conn.fetchrow(
                    """
                    SELECT id, amount_idr FROM hr_bonus_rates
                    WHERE practice_type_code = $1
                      AND is_active = TRUE
                      AND effective_from <= CURRENT_DATE
                      AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
                """,
                    practice_type_code,
                )
                if not rate:
                    logger.debug(
                        f"HR bonus skip: no active rate for practice_type={practice_type_code}",
                    )
                    return

                emp = await conn.fetchrow(
                    """
                    SELECT e.id FROM hr_employees e
                    JOIN team_members tm ON tm.id = e.team_member_id
                    WHERE tm.email = $1 AND e.is_active = TRUE
                """,
                    assigned_to,
                )
                if not emp:
                    logger.debug(
                        f"HR bonus skip: no HR employee for email={assigned_to}",
                    )
                    return

                existing = await conn.fetchval(
                    """
                    SELECT id FROM hr_bonus_ledger
                    WHERE practice_id = $1 AND employee_id = $2
                """,
                    practice_id,
                    emp["id"],
                )
                if existing:
                    logger.debug(f"HR bonus skip: duplicate for practice={practice_id}")
                    return

                await conn.execute(
                    """
                    INSERT INTO hr_bonus_ledger (
                        practice_id, employee_id, bonus_rate_id,
                        practice_type_code, amount_idr, status
                    ) VALUES ($1, $2, $3, $4, $5, 'pending')
                """,
                    practice_id,
                    emp["id"],
                    rate["id"],
                    practice_type_code,
                    rate["amount_idr"],
                )

                logger.info(
                    f"HR bonus created: practice={practice_id}, "
                    f"employee={assigned_to}, amount={rate['amount_idr']} IDR",
                )

        except (asyncpg.PostgresError, OSError) as e:
            logger.warning(f"HR bonus hook failed for practice {practice_id} (DB): {e}")
        except (KeyError, TypeError) as e:
            logger.warning(f"HR bonus hook failed for practice {practice_id} (data): {e}")
        except Exception as e:
            logger.exception(f"HR bonus hook failed for practice {practice_id}: {e}")

    # ==================== UTILITY METHODS ====================

    async def _find_duplicate_client(self, data: dict[str, Any]) -> int | None:
        """Verifica se esiste già cliente con stesso email/phone."""
        async with self.db_pool.acquire() as conn:
            if data.get("email"):
                existing = await conn.fetchval(
                    "SELECT id FROM clients WHERE email = $1 AND status != 'deleted'",
                    data["email"].lower(),
                )
                if existing:
                    return existing

            if data.get("phone"):
                normalized = normalize_phone_e164(data["phone"])
                if normalized:
                    existing = await conn.fetchval(
                        "SELECT id FROM clients WHERE phone = $1 AND status != 'deleted'",
                        normalized,
                    )
                    if existing:
                        return existing

        return None

    async def get_statistics(self, assigned_to: str | None = None) -> dict[str, Any]:
        """Statistiche CRM aggregate."""
        return await self.optimizer.get_practice_statistics(assigned_to)

    async def get_overdue_practices(self, days: int = 7) -> list[dict[str, Any]]:
        """Pratiche scadute o in scadenza."""
        return await self.optimizer.get_overdue_practices(days)

    async def health_check(self) -> dict[str, Any]:
        """Verifica integrità dati CRM."""
        return await health_check_crm_tables(self.db_pool)

    async def close(self) -> None:
        """Cleanup risorse."""
        await self.auditor.close()
        await crm_cache.clear()


# Singleton
_enhanced_crm_service: EnhancedCRMService | None = None


async def get_enhanced_crm_service(db_pool: asyncpg.Pool) -> EnhancedCRMService:
    """Factory per singleton service."""
    global _enhanced_crm_service

    if _enhanced_crm_service is None:
        _enhanced_crm_service = EnhancedCRMService(db_pool)
        await _enhanced_crm_service.initialize()

    return _enhanced_crm_service
