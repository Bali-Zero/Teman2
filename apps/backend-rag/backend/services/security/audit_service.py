"""
Security audit trail service (S03 Sprint 2).

Logs security-sensitive events to security_audit_log table.
Best-effort: DB errors are logged but never propagate.
"""

import json
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
            details_json = json.dumps(details) if details else None

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
                details_json,
            )
        except Exception as e:
            logger.error(f"S03-S2: Security audit log failed: {e} (action={action})")
