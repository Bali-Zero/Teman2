"""
Security audit trail service (S03 Sprint 2).

Logs security-sensitive events to security_audit_log table.
Best-effort: DB errors are logged but never propagate.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SecurityAuditService:
    """
    Log security events to PostgreSQL.

    Actions: login, logout, token_refresh, token_revoke,
    rbac_violation, api_key_usage, data_export, permission_change.
    """

    async def log_event(
        self,
        conn: Any,
        action: str,
        user_email: str | None = None,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        success: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a security event. Best-effort — never raises.
        """
        try:
            # The application pool registers a jsonb codec with
            # ``encoder=json.dumps``. Bind the Python mapping directly so the
            # codec serializes it exactly once; pre-serializing here stores a
            # JSON string scalar instead of a queryable JSON object.
            details_payload = details if details else None

            await conn.execute(
                """
                INSERT INTO security_audit_log
                    (user_id, user_email, action, resource_type, resource_id,
                     ip_address, user_agent, success, details)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                """,
                user_id,
                user_email,
                action,
                resource_type,
                resource_id,
                ip_address,
                user_agent,
                success,
                details_payload,
            )
        except Exception as e:
            logger.error("S03-S2: Security audit log failed: %s (action=%s)", e, action)
