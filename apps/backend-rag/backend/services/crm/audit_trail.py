"""
CRM Audit Trail

Sistema completo di audit logging per tracciabilità operazioni CRM.
"""

import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any

import asyncpg

from backend.app.utils.error_sanitizer import sanitize_error_message

logger = logging.getLogger(__name__)


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
            # Calcola delta per update
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

            # Buffer per batch insert
            self._buffer.append(entry)

            if len(self._buffer) >= self._buffer_size:
                await self._flush_buffer()

        except Exception as e:
            logger.error(f"Failed to log audit entry: {sanitize_error_message(e)}")

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
            params = []

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

            # Count
            count_sql = f"SELECT COUNT(*) FROM crm_audit_log WHERE {where_clause}"
            total = await conn.fetchval(count_sql, *params)

            # Data
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
                # Batch insert
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

        except Exception as e:
            logger.error(f"Failed to flush audit buffer: {sanitize_error_message(e)}")

    def _calculate_changes(
        self, old_values: dict[str, Any], new_values: dict[str, Any]
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
