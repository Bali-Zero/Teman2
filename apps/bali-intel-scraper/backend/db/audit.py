"""
Audit logging for data modifications.

Tracks all changes to sensitive data.
"""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from backend.db.connection import db
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="audit")


class AuditAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    EXPORT = "export"


class AuditLogger:
    """Log data changes for audit purposes."""

    async def log(
        self,
        action: AuditAction,
        table_name: str,
        record_id: str,
        user_id: str | None = None,
        old_data: dict | None = None,
        new_data: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log an audit event."""
        try:
            await db.execute(
                """
                INSERT INTO audit_log (
                    id, action, table_name, record_id, user_id,
                    old_data, new_data, ip_address, user_agent, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                str(uuid4()),
                action.value,
                table_name,
                record_id,
                user_id,
                old_data,
                new_data,
                ip_address,
                user_agent,
                datetime.now(),
            )

            logger.debug(
                f"Audit log: {action.value} on {table_name}",
                metadata={"table": table_name, "action": action.value},
            )

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}", action=LogAction.ERROR)

    async def get_history(
        self, table_name: str, record_id: str, limit: int = 100
    ) -> list:
        """Get audit history for a record."""
        return await db.fetch(
            """
            SELECT * FROM audit_log
            WHERE table_name = $1 AND record_id = $2
            ORDER BY created_at DESC
            LIMIT $3
            """,
            table_name,
            record_id,
            limit,
        )

    async def search(
        self,
        user_id: str | None = None,
        action: AuditAction | None = None,
        table_name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list:
        """Search audit logs."""
        conditions = ["1=1"]
        params = []

        if user_id:
            conditions.append(f"user_id = ${len(params) + 1}")
            params.append(user_id)

        if action:
            conditions.append(f"action = ${len(params) + 1}")
            params.append(action.value)

        if table_name:
            conditions.append(f"table_name = ${len(params) + 1}")
            params.append(table_name)

        if start_date:
            conditions.append(f"created_at >= ${len(params) + 1}")
            params.append(start_date)

        if end_date:
            conditions.append(f"created_at <= ${len(params) + 1}")
            params.append(end_date)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT * FROM audit_log
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${len(params) + 1}
        """
        params.append(limit)

        return await db.fetch(query, *params)


audit_logger = AuditLogger()


async def log_audit(
    action: AuditAction, table_name: str, record_id: str, **kwargs
) -> None:
    """Quick audit logging function."""
    await audit_logger.log(action, table_name, record_id, **kwargs)


__all__ = [
    "AuditAction",
    "AuditLogger",
    "audit_logger",
    "log_audit",
]
