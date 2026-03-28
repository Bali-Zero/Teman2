"""
Auto-Practice Creation Job
Runs daily to automatically create visa renewal practices at T-60 days.

Business Logic:
- Scans active visas expiring in 60 days
- Creates renewal practice if:
  * No existing renewal practice for this visa
  * Visa status is 'active' or 'expiring_soon'
  * Client is still active
- Links practice to client and creates timeline event
- Assigns to client's assigned_to agent (or default)
- Sets priority based on urgency (high if <30 days, normal otherwise)

Features:
- Duplicate prevention (checks existing practices)
- Automatic assignment to client's agent
- Timeline event creation for client visibility
- Prometheus metrics for monitoring
- Structured logging
"""

import asyncio
from datetime import date, datetime, timedelta, timezone

import structlog
from prometheus_client import Counter, Gauge

logger = structlog.get_logger(__name__)

# Metrics
practices_checked = Counter(
    "auto_practice_creator_visas_checked", "Total visas checked for renewal",
)
practices_created = Counter(
    "auto_practice_creator_practices_created", "Renewal practices created", ["visa_type"],
)
practices_skipped = Counter(
    "auto_practice_creator_practices_skipped",
    "Practices skipped (already exists)",
    ["reason"],
)
job_last_run = Gauge("auto_practice_creator_last_run_timestamp", "Last successful run")

# Business rules
RENEWAL_TRIGGER_DAYS = 60  # Create practice 60 days before expiry
URGENT_THRESHOLD_DAYS = 30  # Set high priority if <30 days
DEFAULT_ASSIGNEE = "admin@balizero.com"  # Fallback if no agent assigned


async def get_practice_type_id(db_pool, visa_type: str) -> int | None:
    """
    Get practice_type_id for visa renewal based on visa type.

    Mapping:
    - kitas_work -> KITAS_RENEWAL
    - kitas_spouse -> KITAS_SPOUSE_RENEWAL
    - kitap -> KITAP_RENEWAL
    - tourist_visa -> TOURIST_VISA_EXTENSION
    - business_visa -> BUSINESS_VISA_RENEWAL
    - social_visa -> SOCIAL_VISA_EXTENSION
    - other -> VISA_RENEWAL_GENERAL

    Args:
        db_pool: Database connection pool
        visa_type: Visa type from visa_records table

    Returns:
        practice_type_id if found, None otherwise
    """
    # Map visa types to practice type codes
    visa_to_practice_map = {
        "kitas_work": "KITAS_RENEWAL",
        "kitas_spouse": "KITAS_SPOUSE_RENEWAL",
        "kitap": "KITAP_RENEWAL",
        "tourist_visa": "TOURIST_VISA_EXTENSION",
        "business_visa": "BUSINESS_VISA_RENEWAL",
        "social_visa": "SOCIAL_VISA_EXTENSION",
        "other": "VISA_RENEWAL_GENERAL",
    }

    practice_type_code = visa_to_practice_map.get(visa_type, "VISA_RENEWAL_GENERAL")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM practice_types WHERE code = $1 AND active = true", practice_type_code,
        )

        if not row:
            logger.warning(
                "Practice type not found",
                visa_type=visa_type,
                practice_type_code=practice_type_code,
            )
            return None

        return row["id"]


async def check_existing_renewal_practice(db_pool, client_id: int, visa_record_id: int) -> bool:
    """
    Check if renewal practice already exists for this visa.

    Args:
        db_pool: Database connection pool
        client_id: Client ID
        visa_record_id: Visa record ID

    Returns:
        True if practice exists, False otherwise
    """
    async with db_pool.acquire() as conn:
        # Check if practice exists in custom_fields with visa_record_id reference
        # or in the last 120 days for this client with renewal practice types
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) as count
            FROM practices p
            JOIN practice_types pt ON p.practice_type_id = pt.id
            WHERE p.client_id = $1
              AND pt.code LIKE '%RENEWAL%'
              AND p.status NOT IN ('cancelled', 'completed')
              AND p.created_at >= NOW() - INTERVAL '120 days'
              AND (
                  p.custom_fields->>'source_visa_record_id' = $2::text
                  OR p.created_at >= NOW() - INTERVAL '60 days'
              )
        """,
            client_id,
            str(visa_record_id),
        )

        return row["count"] > 0


async def create_renewal_practice(
    db_pool,
    client_id: int,
    client_name: str,
    visa_record_id: int,
    visa_type: str,
    visa_number: str,
    expiry_date: date,
    assigned_to: str | None,
) -> int | None:
    """
    Create a renewal practice for a visa.

    Args:
        db_pool: Database connection pool
        client_id: Client ID
        client_name: Client full name
        visa_record_id: Visa record ID
        visa_type: Visa type
        visa_number: Visa number
        expiry_date: Visa expiry date
        assigned_to: Agent email (or None for default)

    Returns:
        Practice ID if created, None otherwise
    """
    # Get practice type
    practice_type_id = await get_practice_type_id(db_pool, visa_type)
    if not practice_type_id:
        logger.error("Cannot create practice: practice type not found", visa_type=visa_type)
        return None

    # Calculate priority
    days_until_expiry = (expiry_date - datetime.now(tz=timezone.utc).date()).days
    priority = "high" if days_until_expiry < URGENT_THRESHOLD_DAYS else "normal"

    # Determine assignee
    assignee = assigned_to or DEFAULT_ASSIGNEE

    # Create practice
    async with db_pool.acquire() as conn:
        try:
            # Insert practice
            practice_row = await conn.fetchrow(
                """
                INSERT INTO practices (
                    client_id,
                    practice_type_id,
                    status,
                    priority,
                    assigned_to,
                    inquiry_date,
                    expiry_date,
                    notes,
                    internal_notes,
                    custom_fields,
                    created_by
                )
                VALUES ($1, $2, $3, $4, $5, NOW(), $6, $7, $8, $9::jsonb, $10)
                RETURNING id, uuid
            """,
                client_id,
                practice_type_id,
                "inquiry",  # Initial status
                priority,
                assignee,
                expiry_date,
                f"Visa renewal for {visa_type} expiring on {expiry_date}",
                f"Auto-created by system at T-{days_until_expiry} days. Source visa: {visa_number}",
                f'{{"source_visa_record_id": {visa_record_id}, "auto_created": true, "created_at_days_before_expiry": {days_until_expiry}}}',
                "system_auto_practice_creator",
            )

            practice_id = practice_row["id"]
            practice_uuid = practice_row["uuid"]

            # Create timeline event for client
            await conn.execute(
                """
                INSERT INTO timeline_events (
                    client_id,
                    practice_id,
                    event_type,
                    title,
                    description,
                    event_date,
                    color,
                    client_visible
                )
                VALUES ($1, $2, 'practice_created', $3, $4, NOW(), 'info', true)
            """,
                client_id,
                practice_id,
                f"Visa Renewal Practice Created: {visa_type}",
                f"We've initiated your visa renewal process for {visa_type} (expires {expiry_date}). Our team will contact you shortly with next steps.",
            )

            practices_created.labels(visa_type=visa_type).inc()
            logger.info(
                "Renewal practice created",
                client_id=client_id,
                client_name=client_name,
                practice_id=practice_id,
                practice_uuid=practice_uuid,
                visa_type=visa_type,
                visa_number=visa_number,
                expiry_date=str(expiry_date),
                days_until_expiry=days_until_expiry,
                priority=priority,
                assigned_to=assignee,
            )

            return practice_id

        except Exception as e:
            logger.error(
                "Failed to create renewal practice",
                client_id=client_id,
                visa_type=visa_type,
                error=str(e),
                exc_info=True,
            )
            return None


async def run_auto_practice_creator(db_pool) -> dict:
    """
    Main job execution: Check visas expiring in 60 days and create renewal practices.

    Returns:
        dict with job statistics
    """
    logger.info("Starting auto-practice-creator job")

    target_date = datetime.now(tz=timezone.utc).date() + timedelta(days=RENEWAL_TRIGGER_DAYS)

    stats = {
        "visas_checked": 0,
        "practices_created": 0,
        "practices_skipped": 0,
        "errors": 0,
    }

    try:
        # Find visas expiring in exactly 60 days
        async with db_pool.acquire() as conn:
            visas = await conn.fetch(
                """
                SELECT
                    vr.id as visa_record_id,
                    vr.client_id,
                    vr.visa_type,
                    vr.visa_number,
                    vr.expiry_date,
                    vr.status,
                    c.full_name as client_name,
                    c.email as client_email,
                    c.assigned_to,
                    c.status as client_status
                FROM visa_records vr
                JOIN clients c ON vr.client_id = c.id
                WHERE vr.expiry_date = $1
                  AND vr.status IN ('active', 'expiring_soon')
                  AND c.status = 'active'
                ORDER BY c.full_name
            """,
                target_date,
            )

            logger.info(f"Found {len(visas)} visas expiring in {RENEWAL_TRIGGER_DAYS} days")

            for visa in visas:
                stats["visas_checked"] += 1
                practices_checked.inc()

                # Check if practice already exists
                exists = await check_existing_renewal_practice(
                    db_pool, visa["client_id"], visa["visa_record_id"],
                )

                if exists:
                    practices_skipped.labels(reason="already_exists").inc()
                    stats["practices_skipped"] += 1
                    logger.info(
                        "Skipping: renewal practice already exists",
                        client_id=visa["client_id"],
                        client_name=visa["client_name"],
                        visa_type=visa["visa_type"],
                        visa_number=visa["visa_number"],
                    )
                    continue

                # Create renewal practice
                practice_id = await create_renewal_practice(
                    db_pool=db_pool,
                    client_id=visa["client_id"],
                    client_name=visa["client_name"],
                    visa_record_id=visa["visa_record_id"],
                    visa_type=visa["visa_type"],
                    visa_number=visa["visa_number"] or "N/A",
                    expiry_date=visa["expiry_date"],
                    assigned_to=visa["assigned_to"],
                )

                if practice_id:
                    stats["practices_created"] += 1
                else:
                    stats["errors"] += 1

        # Update last run metric
        job_last_run.set(datetime.now(timezone.utc).timestamp())

        logger.info(
            "Auto-practice-creator job completed",
            visas_checked=stats["visas_checked"],
            practices_created=stats["practices_created"],
            practices_skipped=stats["practices_skipped"],
            errors=stats["errors"],
        )

        return stats

    except Exception as e:
        logger.error("Auto-practice-creator job failed", error=str(e), exc_info=True)
        raise


async def main():
    """Entry point for direct execution (cron job)"""
    import asyncpg

    from backend.app.core.config import settings

    db_pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=3)

    try:
        stats = await run_auto_practice_creator(db_pool)
        return stats
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
