"""Migration 076: PostgreSQL triggers for event bus channels.

Adds pg_notify triggers for:
  - client_changed: fires on INSERT/UPDATE to clients table
  - compliance_alert: fires on INSERT to compliance_alerts table (if exists)

These complement the existing practice_changed trigger (migration_075)
and feed into the EventBus listener.
"""

import logging

import asyncpg

logger = logging.getLogger(__name__)

MIGRATION_ID = "076"
DESCRIPTION = (
    "Add pg_notify triggers for event bus: client_changed on clients table "
    "(INSERT/UPDATE), compliance_alert on compliance_alerts (INSERT)."
)


async def up(conn: asyncpg.Connection) -> None:
    # ── client_changed trigger ─────────────────────────────────────────
    await conn.execute("""
        CREATE OR REPLACE FUNCTION notify_client_change()
        RETURNS TRIGGER AS $$
        DECLARE
            payload TEXT;
        BEGIN
            payload := json_build_object(
                'client_id',     NEW.id,
                'email',         NEW.email,
                'full_name',     NEW.full_name,
                'status',        NEW.status,
                'assigned_to',   NEW.assigned_to,
                'operation',     TG_OP,
                'ts',            EXTRACT(EPOCH FROM NOW())
            )::text;

            PERFORM pg_notify('client_changed', payload);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_client_changed ON clients;
        CREATE TRIGGER trg_client_changed
        AFTER INSERT OR UPDATE ON clients
        FOR EACH ROW
        EXECUTE FUNCTION notify_client_change();
    """)

    # ── compliance_alert trigger (conditional — table may not exist) ───
    table_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'compliance_alerts'
        )
    """)

    if table_exists:
        await conn.execute("""
            CREATE OR REPLACE FUNCTION notify_compliance_alert()
            RETURNS TRIGGER AS $$
            DECLARE
                payload TEXT;
            BEGIN
                payload := json_build_object(
                    'alert_id',    NEW.id,
                    'client_id',   NEW.client_id,
                    'alert_type',  NEW.alert_type,
                    'severity',    NEW.severity,
                    'message',     LEFT(NEW.message, 500),
                    'ts',          EXTRACT(EPOCH FROM NOW())
                )::text;

                PERFORM pg_notify('compliance_alert', payload);
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)

        await conn.execute("""
            DROP TRIGGER IF EXISTS trg_compliance_alert ON compliance_alerts;
            CREATE TRIGGER trg_compliance_alert
            AFTER INSERT ON compliance_alerts
            FOR EACH ROW
            EXECUTE FUNCTION notify_compliance_alert();
        """)
        logger.info("Migration 076: compliance_alert trigger created")
    else:
        logger.info("Migration 076: compliance_alerts table not found, skipping trigger")

    logger.info("Migration 076 applied: event bus pg_notify triggers")


async def down(conn: asyncpg.Connection) -> None:
    await conn.execute("DROP TRIGGER IF EXISTS trg_client_changed ON clients;")
    await conn.execute("DROP FUNCTION IF EXISTS notify_client_change();")
    await conn.execute("DROP TRIGGER IF EXISTS trg_compliance_alert ON compliance_alerts;")
    await conn.execute("DROP FUNCTION IF EXISTS notify_compliance_alert();")
    logger.info("Migration 076 rolled back")
