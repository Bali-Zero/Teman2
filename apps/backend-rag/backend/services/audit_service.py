"""
ZANTARA Audit Service
Handles security logging and system audit trails for compliance and debugging.
Replaces Node.js audit-trail.ts
"""

import logging
from typing import Any

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for logging security and system events to the database.
    """

    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or settings.database_url
        self.pool: asyncpg.Pool | None = None
        self.enabled = bool(self.database_url)

    async def connect(self):
        """Initialize PostgreSQL connection pool"""
        if not self.enabled:
            logger.warning("⚠️ AuditService disabled: No DATABASE_URL")
            return

        try:
            self.pool = await asyncpg.create_pool(
                self.database_url, min_size=1, max_size=5, command_timeout=10
            )
            logger.info("✅ AuditService connected to database")
        except Exception as e:
            logger.error(f"❌ AuditService connection failed: {e}")
            self.enabled = False

    async def close(self):
        """Close PostgreSQL connection pool"""
        if self.pool:
            await self.pool.close()

    async def log_auth_event(
        self,
        email: str,
        action: str,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        user_id: str | None = None,
        failure_reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Log an authentication event (login, logout, failed attempt).

        Args:
            email: User email
            action: Event action ('login', 'logout', 'failed_login', etc.)
            success: Whether the action was successful
            ip_address: Client IP address
            user_agent: Client User Agent string
            user_id: User ID (if known/authenticated)
            failure_reason: Reason for failure (if applicable)
            metadata: Additional context
        """
        if not self.enabled or not self.pool:
            logger.warning(f"⚠️ Audit log skipped (DB unavailable): {action} for {email}")
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO auth_audit_log
                    (user_id, email, action, ip_address, user_agent, success, failure_reason, metadata, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    """,
                    user_id,
                    email,
                    action,
                    ip_address,
                    user_agent,
                    success,
                    failure_reason,
                    metadata or {},
                )
                logger.debug(f"📝 Auth audit logged: {action} for {email} (Success: {success})")

        except Exception as e:
            logger.error(f"❌ Failed to log auth event: {e}")

    async def log_system_event(
        self,
        event_type: str,
        action: str,
        user_id: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        """
        Log a general system event for audit trail.

        Args:
            event_type: Category ('data_access', 'security_alert', etc.)
            action: Specific action ('read', 'write', 'delete')
            user_id: Who performed the action
            resource_id: What was accessed/modified
            details: JSON details about the event
            ip_address: Client IP
            user_agent: Client User Agent
        """
        if not self.enabled or not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO audit_events
                    (event_type, user_id, resource_id, action, details, ip_address, user_agent, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    """,
                    event_type,
                    user_id,
                    resource_id,
                    action,
                    details or {},
                    ip_address,
                    user_agent,
                )
                logger.debug(f"📝 System audit logged: {event_type} - {action}")

        except Exception as e:
            logger.error(f"❌ Failed to log system event: {e}")


# Global instance
_audit_service: AuditService | None = None


def get_audit_service() -> AuditService:
    """Get or initialize global audit service"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
