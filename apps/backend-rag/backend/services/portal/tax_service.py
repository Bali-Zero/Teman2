"""Tax obligations service for Portal."""

from datetime import date, datetime, timezone

import structlog
from asyncpg import Pool

from backend.schemas.portal import TaxObligation, TaxSummary

logger = structlog.get_logger(__name__)


class TaxService:
    """Service for managing client tax obligations."""

    def __init__(self, db_pool: Pool) -> None:
        self.db_pool = db_pool

    async def get_client_taxes(
        self, client_id: int, include_completed: bool = False
    ) -> list[TaxObligation]:
        """
        Get all tax obligations for a client.

        Args:
            client_id: The client's database ID
            include_completed: Whether to include paid/filed obligations

        Returns:
            List of TaxObligation objects
        """
        query = """
            SELECT * FROM tax_obligations
            WHERE client_id = $1
        """
        if not include_completed:
            query += " AND status NOT IN ('paid', 'filed')"
        query += " ORDER BY due_date ASC"

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, client_id)
            logger.info("Fetched tax obligations", client_id=client_id, count=len(rows))
            return [TaxObligation(**dict(row)) for row in rows]

    async def get_tax_summary(self, client_id: int) -> TaxSummary:
        """
        Get aggregated tax summary for dashboard card.

        Returns:
            TaxSummary with total_due, next_deadline, etc.
        """
        query = """
            SELECT
                COALESCE(SUM(CASE WHEN status IN ('upcoming', 'pending', 'overdue')
                    THEN amount_due ELSE 0 END), 0) as total_due,
                MIN(CASE WHEN status IN ('upcoming', 'pending')
                    THEN due_date END) as next_deadline,
                COUNT(CASE WHEN status IN ('upcoming', 'pending')
                    THEN 1 END) as pending_count,
                COUNT(CASE WHEN status = 'overdue'
                    THEN 1 END) as overdue_count
            FROM tax_obligations
            WHERE client_id = $1
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, client_id)

            days_until = None
            status = "ok"
            if row["next_deadline"]:
                days_until = (row["next_deadline"] - datetime.now(tz=timezone.utc).date()).days
                if days_until <= 7:
                    status = "critical"
                elif days_until <= 14:
                    status = "attention"

            if row["overdue_count"] > 0:
                status = "critical"

            logger.info("Generated tax summary", client_id=client_id, status=status)

            return TaxSummary(
                total_due=float(row["total_due"] or 0),
                next_deadline=row["next_deadline"],
                days_until_deadline=days_until,
                pending_count=row["pending_count"],
                overdue_count=row["overdue_count"],
                status=status,
            )

    async def create_obligation(
        self,
        client_id: int,
        tax_type: str,
        name: str,
        frequency: str,
        period_start: date,
        period_end: date,
        due_date: date,
        amount_due: float | None = None,
    ) -> TaxObligation:
        """Create a new tax obligation with timeline event."""
        async with self.db_pool.acquire() as conn, conn.transaction():
            # Insert obligation
            row = await conn.fetchrow(
                """
                    INSERT INTO tax_obligations
                    (client_id, tax_type, name, frequency, period_start,
                     period_end, due_date, amount_due, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'upcoming')
                    RETURNING *
                """,
                client_id,
                tax_type,
                name,
                frequency,
                period_start,
                period_end,
                due_date,
                amount_due,
            )

            # Create timeline event
            await conn.execute(
                """
                    INSERT INTO timeline_events
                    (client_id, event_type, title, description, event_date, color, client_visible)
                    VALUES ($1, 'deadline', $2, $3, $4, 'warning', true)
                """,
                client_id,
                f"Tax Deadline: {name}",
                f"Due: {due_date}",
                due_date,
            )

            logger.info(
                "Created tax obligation",
                client_id=client_id,
                tax_type=tax_type,
                due_date=str(due_date),
            )
            return TaxObligation(**dict(row))

    async def update_status(
        self, obligation_id: int, new_status: str, amount_paid: float | None = None
    ) -> TaxObligation | None:
        """Update obligation status and create timeline event."""
        async with self.db_pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                    UPDATE tax_obligations
                    SET status = $2, amount_paid = COALESCE($3, amount_paid),
                        updated_at = NOW()
                    WHERE id = $1
                    RETURNING *
                """,
                obligation_id,
                new_status,
                amount_paid,
            )

            if row and new_status == "paid":
                await conn.execute(
                    """
                        INSERT INTO timeline_events
                        (client_id, event_type, title, event_date, color, client_visible)
                        VALUES ($1, 'completion', $2, NOW(), 'success', true)
                    """,
                    row["client_id"],
                    f"Tax Paid: {row['name']}",
                )

            logger.info("Updated tax obligation", id=obligation_id, new_status=new_status)
            return TaxObligation(**dict(row)) if row else None
