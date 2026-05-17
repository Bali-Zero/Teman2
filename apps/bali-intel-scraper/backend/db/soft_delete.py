"""
Soft delete implementation.

Allows records to be marked as deleted without removing them.
"""

from datetime import datetime

from backend.db.connection import db
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="soft_delete")


class SoftDeleteMixin:
    """Mixin for models that support soft delete."""

    _table_name: str = ""

    async def soft_delete(
        self, record_id: str, deleted_by: str | None = None
    ) -> bool:
        """Soft delete a record."""
        try:
            result = await db.execute(
                f"""
                UPDATE {self._table_name}
                SET 
                    deleted_at = $1,
                    deleted_by = $2,
                    is_deleted = true
                WHERE id = $3 AND is_deleted = false
                """,
                datetime.now(),
                deleted_by,
                record_id,
            )

            logger.info(
                f"Soft deleted {self._table_name} record {record_id}",
                action=LogAction.DELETE,
            )

            return "UPDATE 1" in result

        except Exception as e:
            logger.error(f"Soft delete failed: {e}", action=LogAction.ERROR)
            return False

    async def restore(self, record_id: str) -> bool:
        """Restore a soft-deleted record."""
        try:
            result = await db.execute(
                f"""
                UPDATE {self._table_name}
                SET 
                    deleted_at = NULL,
                    deleted_by = NULL,
                    is_deleted = false
                WHERE id = $1 AND is_deleted = true
                """,
                record_id,
            )

            logger.info(
                f"Restored {self._table_name} record {record_id}",
                action=LogAction.UPDATE,
            )

            return "UPDATE 1" in result

        except Exception as e:
            logger.error(f"Restore failed: {e}", action=LogAction.ERROR)
            return False

    async def get_deleted(self, limit: int = 100) -> list:
        """Get soft-deleted records."""
        return await db.fetch(
            f"""
            SELECT * FROM {self._table_name}
            WHERE is_deleted = true
            ORDER BY deleted_at DESC
            LIMIT $1
            """,
            limit,
        )

    async def purge_deleted(self, days_old: int = 30) -> int:
        """Permanently delete old soft-deleted records."""
        cutoff = datetime.now() - __import__("datetime").timedelta(days=days_old)

        try:
            result = await db.execute(
                f"""
                DELETE FROM {self._table_name}
                WHERE is_deleted = true AND deleted_at < $1
                """,
                cutoff,
            )

            # Parse result (e.g., "DELETE 5")
            count = int(result.split()[1]) if "DELETE" in result else 0

            logger.info(f"Purged {count} deleted records", action=LogAction.DELETE)

            return count

        except Exception as e:
            logger.error(f"Purge failed: {e}", action=LogAction.ERROR)
            return 0


class SoftDeleteManager:
    """Manage soft delete for any table."""

    async def soft_delete(
        self, table_name: str, record_id: str, deleted_by: str | None = None
    ) -> bool:
        """Soft delete a record from any table."""
        try:
            result = await db.execute(
                f"""
                UPDATE {table_name}
                SET deleted_at = $1, deleted_by = $2, is_deleted = true
                WHERE id = $3 AND (is_deleted = false OR is_deleted IS NULL)
                """,
                datetime.now(),
                deleted_by,
                record_id,
            )
            return "UPDATE 1" in result
        except Exception as e:
            logger.error(f"Soft delete failed: {e}")
            return False

    async def restore(self, table_name: str, record_id: str) -> bool:
        """Restore a soft-deleted record."""
        try:
            result = await db.execute(
                f"""
                UPDATE {table_name}
                SET deleted_at = NULL, deleted_by = NULL, is_deleted = false
                WHERE id = $1 AND is_deleted = true
                """,
                record_id,
            )
            return "UPDATE 1" in result
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    async def list_active(
        self, table_name: str, limit: int = 100, offset: int = 0
    ) -> list:
        """List active (non-deleted) records."""
        return await db.fetch(
            f"""
            SELECT * FROM {table_name}
            WHERE is_deleted = false OR is_deleted IS NULL
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )

    async def list_deleted(self, table_name: str, limit: int = 100) -> list:
        """List soft-deleted records."""
        return await db.fetch(
            f"""
            SELECT * FROM {table_name}
            WHERE is_deleted = true
            ORDER BY deleted_at DESC
            LIMIT $1
            """,
            limit,
        )


soft_delete_manager = SoftDeleteManager()


__all__ = [
    "SoftDeleteMixin",
    "SoftDeleteManager",
    "soft_delete_manager",
]
