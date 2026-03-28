"""
Enhanced CRM Service

Servizio CRM unificato con tutte le ottimizzazioni:
- Validazione robusta
- Caching intelligente
- Query ottimizzate
- Audit trail completo
- Error handling avanzato
"""

import logging
from typing import Any

import asyncpg

from backend.app.core.exceptions import (
    DatabaseError,
    ResourceNotFoundError,
    ValidationError,
)
from backend.app.utils.error_sanitizer import sanitize_error_message
from backend.services.crm.audit_trail import AuditAction, CRMAuditor, init_audit_table
from backend.services.crm.cache_manager import crm_cache, invalidate_client_cache, query_cache
from backend.services.crm.query_optimizer import CRMQueryOptimizer, health_check_crm_tables
from backend.services.crm.validators import ClientValidator, PracticeValidator, normalize_phone_e164

logger = logging.getLogger(__name__)


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
            # Inizializza tabella audit
            await init_audit_table(self.db_pool)

            # Precarica practice types in cache
            async with self.db_pool.acquire() as conn:
                types = await conn.fetch(
                    "SELECT id, code, name FROM practice_types WHERE active = true",
                )
                await query_cache.set_practice_types([dict(t) for t in types])

            self._initialized = True
            logger.info("✅ EnhancedCRMService initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize CRM service: {sanitize_error_message(e)}")
            raise

    # ==================== CLIENT OPERATIONS ====================

    async def create_client(
        self,
        client_data: dict[str, Any],
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Crea nuovo cliente con validazione e audit.

        Args:
            client_data: Dati cliente
            user_id: ID utente che crea
            metadata: Metadati request

        Returns:
            Cliente creato con ID
        """
        try:
            # Validazione
            validated = ClientValidator(**client_data)

            # Verifica duplicati
            existing = await self._find_duplicate_client(validated.model_dump())
            if existing:
                raise ValidationError(
                    "Client already exists with email or phone", {"existing_id": existing},
                )

            # Insert
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

            # Audit
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
        except Exception as e:
            logger.error(f"Failed to create client: {sanitize_error_message(e)}")
            raise DatabaseError("Failed to create client", operation="insert")

    async def update_client(
        self,
        client_id: int,
        updates: dict[str, Any],
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Aggiorna cliente con validazione delta e audit.
        """
        try:
            # Recupera dati esistenti
            async with self.db_pool.acquire() as conn:
                old_data = await conn.fetchrow("SELECT * FROM clients WHERE id = $1", client_id)

                if not old_data:
                    raise ResourceNotFoundError("Client", str(client_id))

                old_dict = dict(old_data)

            # Validazione nuovi dati
            if "full_name" in updates:
                ClientValidator(**{**old_dict, **updates})

            # Costruisci update — solo colonne nella whitelist
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
                return old_dict  # No changes

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

            # Invalidate cache
            invalidate_client_cache(client_id)

            # Audit
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
        except Exception as e:
            logger.error(f"Failed to update client: {sanitize_error_message(e)}")
            raise DatabaseError("Failed to update client", operation="update")

    async def get_client(
        self, client_id: int, include_practices: bool = False,
    ) -> dict[str, Any] | None:
        """
        Recupera cliente con caching.
        """
        cache_key = f"client:{client_id}:practices:{include_practices}"

        # Prova cache
        cached = await crm_cache.get(cache_key)
        if cached:
            return cached

        try:
            if include_practices:
                # Usa query optimizer
                results = await self.optimizer.get_clients_with_practices([client_id])
                result = results[0] if results else None
            else:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT * FROM clients WHERE id = $1", client_id)
                    result = dict(row) if row else None

            if result:
                # Salva in cache
                await crm_cache.set(cache_key, result, ttl=300)

            return result

        except Exception as e:
            logger.error(f"Failed to get client: {sanitize_error_message(e)}")
            raise DatabaseError("Failed to retrieve client", operation="select")

    async def search_clients(
        self, query: str, limit: int = 20, offset: int = 0,
    ) -> tuple[list[dict], int]:
        """
        Ricerca clienti ottimizzata.
        """
        return await self.optimizer.search_clients_optimized(query, limit, offset)

    # ==================== PRACTICE OPERATIONS ====================

    async def create_practice(
        self,
        practice_data: dict[str, Any],
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Crea pratica con validazione.
        """
        try:
            # Validazione
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

            # Audit
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

        except Exception as e:
            logger.error(f"Failed to create practice: {sanitize_error_message(e)}")
            raise DatabaseError("Failed to create practice", operation="insert")

    async def update_practice_status(
        self,
        practice_id: int,
        new_status: str,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Aggiorna stato pratica con audit trail.
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Get current status
                old = await conn.fetchrow(
                    "SELECT status, client_id FROM practices WHERE id = $1", practice_id,
                )

                if not old:
                    raise ResourceNotFoundError("Practice", str(practice_id))

                old_status = old["status"]

                # Update
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

            # Audit
            await self.auditor.log_practice_status_change(
                practice_id=practice_id,
                user_id=user_id,
                old_status=old_status,
                new_status=new_status,
                metadata=metadata,
            )

            logger.info(f"Practice {practice_id} status: {old_status} -> {new_status}")
            return result

        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to update practice status: {sanitize_error_message(e)}")
            raise DatabaseError("Failed to update practice status", operation="update")

    # ==================== BATCH OPERATIONS ====================

    async def batch_create_clients(
        self, clients: list[dict[str, Any]], user_id: str | None = None,
    ) -> list[int]:
        """
        Creazione batch clienti.
        """
        try:
            # Valida tutti
            for c in clients:
                ClientValidator(**c)

            # Batch insert
            ids = await self.optimizer.batch_insert_clients(clients)

            logger.info(f"Batch created {len(ids)} clients")
            return ids

        except Exception as e:
            logger.error(f"Batch create failed: {sanitize_error_message(e)}")
            raise DatabaseError("Batch creation failed", operation="batch_insert")

    # ==================== UTILITY METHODS ====================

    async def _find_duplicate_client(self, data: dict[str, Any]) -> int | None:
        """Verifica se esiste già cliente con stesso email/phone."""
        async with self.db_pool.acquire() as conn:
            # Check by email
            if data.get("email"):
                existing = await conn.fetchval(
                    "SELECT id FROM clients WHERE email = $1 AND status != 'deleted'",
                    data["email"].lower(),
                )
                if existing:
                    return existing

            # Check by phone
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
