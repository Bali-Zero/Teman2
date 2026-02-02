"""
Deadline checker background job.
Runs daily to create reminder timeline events for upcoming deadlines.
"""
import asyncio
from datetime import date, timedelta

import structlog
from prometheus_client import Counter, Gauge

logger = structlog.get_logger(__name__)

# Metrics
deadlines_checked = Counter("deadline_checker_total", "Total deadlines checked")
reminders_created = Counter(
    "deadline_reminders_created", "Reminder events created", ["type", "urgency"]
)
job_last_run = Gauge("deadline_checker_last_run_timestamp", "Last successful run")

# Reminder schedule
TAX_REMINDER_DAYS = [30, 14, 7, 1]
VISA_REMINDER_DAYS = [90, 60, 30]


async def check_tax_deadlines(db_pool) -> int:
    """
    Check all upcoming tax deadlines and create reminders.

    Reminder schedule:
    - 30 days before: info reminder
    - 14 days before: warning reminder
    - 7 days before: urgent reminder
    - 1 day before: critical reminder

    Returns:
        Number of reminders created
    """
    reminders_count = 0
    today = date.today()

    async with db_pool.acquire() as conn:
        for days in TAX_REMINDER_DAYS:
            target_date = today + timedelta(days=days)
            urgency = "critical" if days <= 7 else ("warning" if days <= 14 else "info")
            color = "error" if days <= 7 else ("warning" if days <= 14 else "info")

            # Find obligations due on target_date without existing reminder
            obligations = await conn.fetch(
                """
                SELECT t.* FROM tax_obligations t
                WHERE t.due_date = $1
                AND t.status IN ('upcoming', 'pending')
                AND NOT EXISTS (
                    SELECT 1 FROM timeline_events e
                    WHERE e.client_id = t.client_id
                    AND e.event_type = 'reminder'
                    AND e.title LIKE '%' || t.name || '%'
                    AND DATE(e.event_date) = $2
                )
            """,
                target_date,
                today,
            )

            for ob in obligations:
                await conn.execute(
                    """
                    INSERT INTO timeline_events
                    (client_id, event_type, title, description, event_date, color, client_visible)
                    VALUES ($1, 'reminder', $2, $3, NOW(), $4, true)
                """,
                    ob["client_id"],
                    f"Tax Reminder: {ob['name']}",
                    f"Due in {days} days ({target_date})",
                    color,
                )
                reminders_count += 1
                reminders_created.labels(type="tax", urgency=urgency).inc()
                logger.info(
                    "Created tax reminder", client_id=ob["client_id"], tax=ob["name"], days=days
                )

    return reminders_count


async def check_visa_expiry(db_pool) -> int:
    """
    Check all visa records for upcoming expiry.

    Actions:
    - 90 days before: send renewal notice
    - 60 days before: create renewal practice (if not exists)
    - 30 days before: update status to 'expiring_soon'

    Returns:
        Number of actions taken
    """
    actions_count = 0
    today = date.today()

    async with db_pool.acquire() as conn:
        # Update status to expiring_soon (30 days)
        result = await conn.execute(
            """
            UPDATE visa_records
            SET status = 'expiring_soon', updated_at = NOW()
            WHERE status = 'active'
            AND expiry_date <= $1
            AND expiry_date > $2
        """,
            today + timedelta(days=30),
            today,
        )

        updated = int(result.split()[-1]) if result else 0
        if updated > 0:
            logger.info("Updated visas to expiring_soon", count=updated)
            actions_count += updated

        # Update status to expired
        result = await conn.execute(
            """
            UPDATE visa_records
            SET status = 'expired', updated_at = NOW()
            WHERE status IN ('active', 'expiring_soon')
            AND expiry_date < $1
        """,
            today,
        )

        expired = int(result.split()[-1]) if result else 0
        if expired > 0:
            logger.info("Updated visas to expired", count=expired)
            actions_count += expired

        # Create reminders for expiring visas
        for days in VISA_REMINDER_DAYS:
            target_date = today + timedelta(days=days)
            urgency = "critical" if days <= 30 else ("warning" if days <= 60 else "info")

            visas = await conn.fetch(
                """
                SELECT v.* FROM visa_records v
                WHERE v.expiry_date = $1
                AND v.status IN ('active', 'expiring_soon')
                AND NOT EXISTS (
                    SELECT 1 FROM timeline_events e
                    WHERE e.client_id = v.client_id
                    AND e.event_type = 'reminder'
                    AND e.title LIKE '%Visa%'
                    AND DATE(e.event_date) = $2
                )
            """,
                target_date,
                today,
            )

            for visa in visas:
                await conn.execute(
                    """
                    INSERT INTO timeline_events
                    (client_id, event_type, title, description, event_date, color, client_visible)
                    VALUES ($1, 'reminder', $2, $3, NOW(), $4, true)
                """,
                    visa["client_id"],
                    f"Visa Expiry Reminder: {visa['visa_type']}",
                    f"Expires in {days} days ({target_date})",
                    "warning" if days > 30 else "error",
                )
                actions_count += 1
                reminders_created.labels(type="visa", urgency=urgency).inc()
                logger.info(
                    "Created visa reminder",
                    client_id=visa["client_id"],
                    visa_type=visa["visa_type"],
                    days=days,
                )

    return actions_count


async def run_deadline_checker():
    """
    Main entry point for deadline checker job.
    Should be scheduled via cron or APScheduler.
    """
    logger.info("Starting deadline checker job")

    try:
        from backend.app.core.database import get_db_pool

        db_pool = await get_db_pool()

        tax_reminders = await check_tax_deadlines(db_pool)
        visa_actions = await check_visa_expiry(db_pool)

        deadlines_checked.inc()
        job_last_run.set_to_current_time()

        logger.info(
            "Deadline checker completed", tax_reminders=tax_reminders, visa_actions=visa_actions
        )

        return {"tax_reminders": tax_reminders, "visa_actions": visa_actions}

    except Exception as e:
        logger.error("Deadline checker failed", error=str(e), exc_info=True)
        raise


# CLI entry point
if __name__ == "__main__":
    asyncio.run(run_deadline_checker())
