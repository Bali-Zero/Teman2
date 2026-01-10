"""
CRM Audit Logging System
Tracks all state changes with user attribution and timestamps
"""

import functools
import json
import logging
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import asyncpg
from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)


class CRMAuditLogger:
    """Centralized audit logging for CRM operations"""

    def __init__(self):
        self.pool = None

    def initialize(self, pool: asyncpg.Pool):
        """Initialize with a database pool"""
        self.pool = pool
        logger.info("✅ CRMAuditLogger initialized with database pool")

    async def _get_pool(self):
        """Get database pool connection"""
        if not self.pool:
            # Try to get it from backend.app.state if we can't find it
            # But in a service, it should be initialized
            raise RuntimeError("CRMAuditLogger not initialized with pool. Call .initialize(pool) first.")
        return self.pool

    async def log_state_change(
        self,
        entity_type: str,
        entity_id: int,
        old_state: dict[str, Any],
        new_state: dict[str, Any],
        user_email: str,
        change_type: str = "status_change",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Log a state change for audit purposes

        Args:
            entity_type: Type of entity (client, case, interaction)
            entity_id: ID of the entity
            old_state: Previous state values
            new_state: New state values
            user_email: User making the change
            change_type: Type of change (status_change, update, create, delete)
            metadata: Additional context data
        """
        try:
            pool = await self._get_pool()

            # Detect what changed
            changes = self._detect_changes(old_state, new_state)

            if not changes:
                logger.warning(f"No changes detected for {entity_type} {entity_id}")
                return True

            async with pool.acquire() as conn:
                # Insert audit record
                await conn.execute(
                    """
                    INSERT INTO crm_audit_log (
                        entity_type, entity_id, change_type, user_email,
                        old_state, new_state, changes, metadata, timestamp
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    entity_type,
                    entity_id,
                    change_type,
                    user_email,
                    json.dumps(old_state, default=str),
                    json.dumps(new_state, default=str),
                    json.dumps(changes, default=str),
                    json.dumps(metadata or {}, default=str),
                    datetime.now(),
                )

            # Log structured message
            logger.info(
                f"🔍 [CRM AUDIT] {entity_type.title()} {entity_id} {change_type} by {user_email}",
                extra={
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "change_type": change_type,
                    "user_email": user_email,
                    "changes": changes,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            return True

        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}", exc_info=True)
            return False

    def _detect_changes(
        self, old_state: dict[str, Any], new_state: dict[str, Any]
    ) -> dict[str, Any]:
        """Detect what changed between old and new state"""
        changes = {}

        # Check all fields in new state
        for key, new_value in new_state.items():
            old_value = old_state.get(key)

            if old_value != new_value:
                changes[key] = {
                    "old": str(old_value) if old_value is not None else None,
                    "new": str(new_value) if new_value is not None else None,
                    "changed_at": datetime.now().isoformat(),
                }

        # Check for removed fields
        for key in old_state:
            if key not in new_state:
                changes[key] = {
                    "old": str(old_state[key]) if old_state[key] is not None else None,
                    "new": None,
                    "removed": True,
                    "changed_at": datetime.now().isoformat(),
                }

        return changes

    async def log_client_status_change(
        self,
        client_id: int,
        old_status: str,
        new_status: str,
        user_email: str,
        additional_data: dict[str, Any] | None = None,
    ) -> bool:
        """
        Log client status change specifically
        """
        old_state = {"status": old_status}
        new_state = {"status": new_status}

        if additional_data:
            old_state.update(additional_data.get("old", {}))
            new_state.update(additional_data.get("new", {}))

        metadata = {
            "change_reason": additional_data.get("reason") if additional_data else None,
            "previous_status": old_status,
            "new_status": new_status,
            "client_id": client_id,
        }

        return await self.log_state_change(
            entity_type="client",
            entity_id=client_id,
            old_state=old_state,
            new_state=new_state,
            user_email=user_email,
            change_type="status_change",
            metadata=metadata,
        )

    async def log_case_progression(
        self,
        case_id: int,
        old_stage: str,
        new_stage: str,
        user_email: str,
        notes: str | None = None,
    ) -> bool:
        """
        Log case progression through stages
        """
        old_state = {"stage": old_stage}
        new_state = {"stage": new_stage}

        metadata = {
            "case_id": case_id,
            "previous_stage": old_stage,
            "new_stage": new_stage,
            "notes": notes,
        }

        return await self.log_state_change(
            entity_type="case",
            entity_id=case_id,
            old_state=old_state,
            new_state=new_state,
            user_email=user_email,
            change_type="stage_progression",
            metadata=metadata,
        )

    async def get_audit_trail(
        self,
        entity_type: str | None = None,
        entity_id: int | None = None,
        user_email: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Retrieve audit trail with filters
        """
        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                query_parts = [
                    """
                    SELECT entity_type, entity_id, change_type, user_email,
                           old_state, new_state, changes, metadata, timestamp
                    FROM crm_audit_log
                    WHERE 1=1
                    """
                ]
                params = []
                param_index = 1

                if entity_type:
                    query_parts.append(f" AND entity_type = ${param_index}")
                    params.append(entity_type)
                    param_index += 1

                if entity_id:
                    query_parts.append(f" AND entity_id = ${param_index}")
                    params.append(entity_id)
                    param_index += 1

                if user_email:
                    query_parts.append(f" AND user_email = ${param_index}")
                    params.append(user_email)
                    param_index += 1

                if start_date:
                    query_parts.append(f" AND timestamp >= ${param_index}")
                    params.append(start_date)
                    param_index += 1

                if end_date:
                    query_parts.append(f" AND timestamp <= ${param_index}")
                    params.append(end_date)
                    param_index += 1

                query_parts.append(f" ORDER BY timestamp DESC LIMIT ${param_index}")
                params.append(limit)

                query = " ".join(query_parts)
                rows = await conn.fetch(query, *params)

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to retrieve audit trail: {e}", exc_info=True)
            return []


# Global audit logger instance
audit_logger = CRMAuditLogger()


# Decorator for automatic audit logging
def audit_change(entity_type: str, change_type: str = "update"):
    """
    Decorator to automatically log changes to CRM entities
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user and entity info from kwargs
            # Priority: user_email kwarg > current_user dict > request.state.user
            user_email = kwargs.get("user_email")
            if not user_email:
                current_user = kwargs.get("current_user", {})
                if isinstance(current_user, dict):
                    user_email = current_user.get("email")
            if not user_email:
                request = kwargs.get("request")
                if request and hasattr(request, "state"):
                    user_email = getattr(request.state, "user", {}).get("email")
            entity_id = kwargs.get("client_id") or kwargs.get("case_id") or kwargs.get("id")

            # Get old state before change
            old_state = {}
            if entity_id and entity_type == "client":
                # Fetch current client state
                try:
                    # Get pool from kwargs or global instance
                    pool = kwargs.get("db_pool") or audit_logger.pool
                    if pool:
                        async with pool.acquire() as conn:
                            row = await conn.fetchrow("SELECT * FROM clients WHERE id = $1", entity_id)
                            if row and hasattr(row, "items"):
                                old_state = dict(row)
                            elif row and not isinstance(row, MagicMock):
                                # If it's a real record but doesn't have items() (unlikely for asyncpg)
                                old_state = dict(row)
                    else:
                        logger.warning("⚠️ No database pool available for audit logging")
                except Exception as e:
                    logger.error(f"Failed to fetch client state: {e}", exc_info=True)

            # Execute the function
            result = await func(*args, **kwargs)

            # Log the change
            if entity_id and user_email and old_state:
                new_state = {}
                if isinstance(result, dict):
                    new_state = result
                elif hasattr(result, "model_dump"):
                    new_state = result.model_dump()
                elif hasattr(result, "dict"):
                    new_state = result.dict()
                await audit_logger.log_state_change(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    old_state=old_state,
                    new_state=new_state,
                    user_email=user_email,
                    change_type=change_type,
                )

            return result

        return wrapper

    return decorator


# Migration script to create audit log table
async def create_audit_log_table(pool: asyncpg.Pool | None = None):
    """Create the CRM audit log table"""
    if not pool:
        pool = audit_logger.pool
    
    if not pool:
        logger.error("❌ Cannot create audit log table: no database pool available")
        return

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS crm_audit_log (
                id SERIAL PRIMARY KEY,
                entity_type VARCHAR(50) NOT NULL,
                entity_id INTEGER NOT NULL,
                change_type VARCHAR(50) NOT NULL,
                user_email VARCHAR(255) NOT NULL,
                old_state JSONB,
                new_state JSONB,
                changes JSONB,
                metadata JSONB,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_crm_audit_entity ON crm_audit_log(entity_type, entity_id);
            CREATE INDEX IF NOT EXISTS idx_crm_audit_user ON crm_audit_log(user_email);
            CREATE INDEX IF NOT EXISTS idx_crm_audit_timestamp ON crm_audit_log(timestamp);
            CREATE INDEX IF NOT EXISTS idx_crm_audit_changes ON crm_audit_log USING GIN(changes);
        """)

    logger.info("CRM audit log table created successfully")