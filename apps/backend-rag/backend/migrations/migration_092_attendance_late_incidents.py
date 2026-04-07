"""
Migration 092: Attendance late-incident state machine.

⚠️ NOT WIRED INTO THE LOADER. This file is kept only as historical reference,
matching the 91+ migration_*.py files in this directory. The actual migration
applied by ``python -m backend.db.migrate apply-all`` is the SQL version at:

    backend/db/migrations_v2/092_attendance_late_incidents.sql

The v2 loader (backend/db/migration_manager.py) only picks up *.sql files in
backend/db/migrations_v2/. The legacy migration_*.py files in backend/migrations/
are NOT discovered by any automated loader and must be applied manually if used.

Tracks every clock_in that arrives at or after 09:40 Bali time as a discrete
incident with a state machine:

    AWAITING_REPLY -> REMINDER_SENT -> ESCALATED
                  \-> RESOLVED       (reply received before reminder)
                   \-> RESOLVED_LATE (reply received after reminder)

A signed reply_token allows the team member to submit a reason via the HR
portal without authentication (the token IS the auth).

Index on (state, first_email_sent_at) lets the every-15-minutes escalation
cron scan only the rows that may need promotion.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "092_attendance_late_incidents"
DESCRIPTION = "HR: Create attendance_late_incidents table for late check-in escalation"


async def check_if_applied(conn) -> bool:
    result = await conn.fetchval(
        "SELECT EXISTS("
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'attendance_late_incidents'"
        ")",
    )
    return result


async def apply(conn) -> None:
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    # The pgcrypto extension provides gen_random_uuid(); it is already enabled
    # on nuzantara-postgres but the IF NOT EXISTS makes the migration safe in
    # any environment (e.g. local dev).
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance_late_incidents (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email                       VARCHAR(255) NOT NULL,
            full_name                   VARCHAR(255),
            late_date                   DATE NOT NULL,
            checkin_time                TIMESTAMPTZ NOT NULL,
            state                       VARCHAR(20) NOT NULL DEFAULT 'AWAITING_REPLY'
                                        CHECK (state IN (
                                            'AWAITING_REPLY',
                                            'REMINDER_SENT',
                                            'ESCALATED',
                                            'RESOLVED',
                                            'RESOLVED_LATE'
                                        )),
            first_email_sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            reminder_sent_at            TIMESTAMPTZ,
            ultimatum_sent_at           TIMESTAMPTZ,
            reply_received_at           TIMESTAMPTZ,
            reply_content               TEXT,
            reply_token                 VARCHAR(64) NOT NULL UNIQUE,
            responsible_manager_email   VARCHAR(255),
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_email_late_date UNIQUE (email, late_date)
        )
    """)

    # Hot path for the escalation cron: filter by state, order by send time.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_late_incidents_state_sent
        ON attendance_late_incidents (state, first_email_sent_at)
        WHERE state IN ('AWAITING_REPLY', 'REMINDER_SENT')
    """)

    # Lookup by token (reply form) — token is unique already, but a dedicated
    # index keeps the query plan tight.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_late_incidents_token
        ON attendance_late_incidents (reply_token)
    """)

    # Daily digest scan: recent activity by date.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_late_incidents_date
        ON attendance_late_incidents (late_date DESC)
    """)

    # Trigger to keep updated_at fresh on any UPDATE.
    await conn.execute("""
        CREATE OR REPLACE FUNCTION trg_attendance_late_incidents_touch()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    await conn.execute("""
        DROP TRIGGER IF EXISTS attendance_late_incidents_touch
        ON attendance_late_incidents
    """)
    await conn.execute("""
        CREATE TRIGGER attendance_late_incidents_touch
        BEFORE UPDATE ON attendance_late_incidents
        FOR EACH ROW EXECUTE FUNCTION trg_attendance_late_incidents_touch()
    """)

    await conn.execute("""
        INSERT INTO migration_history (migration_id, description, applied_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (migration_id) DO NOTHING
    """, MIGRATION_ID, DESCRIPTION)

    logger.info(f"✅ Migration {MIGRATION_ID} applied successfully")


async def rollback(conn) -> None:
    logger.info(f"Rolling back migration {MIGRATION_ID}")
    await conn.execute(
        "DROP TRIGGER IF EXISTS attendance_late_incidents_touch "
        "ON attendance_late_incidents",
    )
    await conn.execute("DROP FUNCTION IF EXISTS trg_attendance_late_incidents_touch()")
    await conn.execute("DROP TABLE IF EXISTS attendance_late_incidents CASCADE")
    await conn.execute(
        "DELETE FROM migration_history WHERE migration_id = $1", MIGRATION_ID,
    )
    logger.info(f"✅ Migration {MIGRATION_ID} rolled back")
