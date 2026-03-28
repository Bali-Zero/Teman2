"""Visa records service for Portal."""

from datetime import date, datetime, timezone

import structlog
from asyncpg import Pool

from backend.schemas.portal import VisaRecord, VisaSummary

logger = structlog.get_logger(__name__)


class VisaService:
    """Service for managing client visa records."""

    def __init__(self, db_pool: Pool) -> None:
        self.db_pool = db_pool

    async def get_active_visa(self, client_id: int) -> VisaRecord | None:
        """Get the currently active visa for a client."""
        query = """
            SELECT * FROM visa_records
            WHERE client_id = $1 AND status IN ('active', 'expiring_soon')
            ORDER BY expiry_date DESC
            LIMIT 1
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, client_id)
            if row:
                logger.info("Found active visa", client_id=client_id, visa_type=row["visa_type"])
                return VisaRecord(**dict(row))
            return None

    async def get_visa_history(self, client_id: int) -> list[VisaRecord]:
        """Get all visa records for a client."""
        query = """
            SELECT * FROM visa_records
            WHERE client_id = $1
            ORDER BY created_at DESC
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, client_id)
            logger.info("Fetched visa history", client_id=client_id, count=len(rows))
            return [VisaRecord(**dict(row)) for row in rows]

    async def get_visa_summary(self, client_id: int) -> VisaSummary:
        """Get visa summary for dashboard card."""
        active_visa = await self.get_active_visa(client_id)

        if not active_visa:
            return VisaSummary(has_active_visa=False, status="none")

        days_until = None
        status = "active"

        if active_visa.expiry_date:
            days_until = (active_visa.expiry_date - datetime.now(tz=timezone.utc).date()).days
            if days_until <= 0:
                status = "expired"
            elif days_until <= 30:
                status = "expiring_soon"

        logger.info(
            "Generated visa summary", client_id=client_id, status=status, days_until=days_until,
        )

        return VisaSummary(
            has_active_visa=True,
            visa_type=active_visa.visa_type,
            expiry_date=active_visa.expiry_date,
            days_until_expiry=days_until,
            status=status,
        )

    async def create_visa_record(
        self,
        client_id: int,
        visa_type: str,
        status: str = "active",
        issue_date: date | None = None,
        expiry_date: date | None = None,
        visa_number: str | None = None,
        sponsor_name: str | None = None,
        sponsor_type: str | None = None,
        practice_id: int | None = None,
    ) -> VisaRecord:
        """Create new visa record with timeline event."""
        async with self.db_pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                    INSERT INTO visa_records
                    (client_id, visa_type, status, issue_date, expiry_date,
                     visa_number, sponsor_name, sponsor_type, practice_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING *
                """,
                client_id,
                visa_type,
                status,
                issue_date,
                expiry_date,
                visa_number,
                sponsor_name,
                sponsor_type,
                practice_id,
            )

            # Create timeline event
            await conn.execute(
                """
                    INSERT INTO timeline_events
                    (client_id, event_type, title, description, event_date, color, client_visible)
                    VALUES ($1, 'milestone', $2, $3, NOW(), 'success', true)
                """,
                client_id,
                f"Visa Issued: {visa_type}",
                f"Valid until: {expiry_date}" if expiry_date else None,
            )

            logger.info("Created visa record", client_id=client_id, visa_type=visa_type)
            return VisaRecord(**dict(row))

    async def update_visa_status(self, visa_id: int, new_status: str) -> VisaRecord | None:
        """Update visa status (e.g., expiring_soon, expired)."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE visa_records
                SET status = $2, updated_at = NOW()
                WHERE id = $1
                RETURNING *
            """,
                visa_id,
                new_status,
            )

            if row:
                logger.info("Updated visa status", visa_id=visa_id, new_status=new_status)
                return VisaRecord(**dict(row))
            return None
