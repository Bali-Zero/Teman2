"""Migration 075: PostgreSQL triggers for practice status + payment notifications."""
import logging

import asyncpg

logger = logging.getLogger(__name__)

MIGRATION_ID = "075"
DESCRIPTION = (
    "Add pg_notify triggers on practices table for status changes and payment_status "
    "transitions. Powers real-time email dispatch (M5 + M4)."
)


async def up(conn: asyncpg.Connection) -> None:
    # ── Trigger function: fires on ANY UPDATE to practices ──────────────────
    await conn.execute("""
        CREATE OR REPLACE FUNCTION notify_practice_change()
        RETURNS TRIGGER AS $$
        DECLARE
            payload TEXT;
        BEGIN
            -- Only act on relevant field changes
            IF (OLD.status IS DISTINCT FROM NEW.status)
               OR (OLD.payment_status IS DISTINCT FROM NEW.payment_status)
            THEN
                payload := json_build_object(
                    'practice_id',     NEW.id,
                    'client_id',       NEW.client_id,
                    'old_status',      OLD.status,
                    'new_status',      NEW.status,
                    'old_payment',     OLD.payment_status,
                    'new_payment',     NEW.payment_status,
                    'assigned_to',     NEW.assigned_to,
                    'ts',              EXTRACT(EPOCH FROM NOW())
                )::text;

                PERFORM pg_notify('practice_changed', payload);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ── Attach trigger to practices table ───────────────────────────────────
    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_practice_changed ON practices;
        CREATE TRIGGER trg_practice_changed
        AFTER UPDATE ON practices
        FOR EACH ROW
        EXECUTE FUNCTION notify_practice_change();
    """)

    logger.info("Migration 075 applied: practice_changed pg_notify trigger")


async def down(conn: asyncpg.Connection) -> None:
    await conn.execute("DROP TRIGGER IF EXISTS trg_practice_changed ON practices;")
    await conn.execute("DROP FUNCTION IF EXISTS notify_practice_change();")
    logger.info("Migration 075 rolled back")
