"""
Migration 071: Notification Alerts Table

Creates the notification_alerts table used by the notification scheduler
(APScheduler jobs: daily_notification_check + hourly_pending_send).

Without this table the scheduler fails on startup with a relation-does-not-exist
error, breaking all expiry/birthday alerts for clients.

Schema based on actual INSERT/SELECT/UPDATE queries in:
- backend/app/modules/notifications/service.py
- backend/app/modules/notifications/scheduler.py
- backend/app/modules/notifications/checker.py
"""

UPGRADE_SQL = """
-- Notification alerts for passport/visa expiry and birthday reminders
CREATE TABLE IF NOT EXISTS notification_alerts (
    id              BIGSERIAL PRIMARY KEY,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    alert_type      VARCHAR(50) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sent', 'failed', 'suppressed')),
    message         TEXT,
    email_subject   VARCHAR(500),
    email_body      TEXT,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at         TIMESTAMPTZ,
    created_date    DATE GENERATED ALWAYS AS ((created_at AT TIME ZONE 'UTC')::DATE) STORED
);

-- Unique: 1 alert per client+type per day
CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_alert_daily
    ON notification_alerts (client_id, alert_type, created_date);

-- Fast lookup: pending alerts sorted by age
CREATE INDEX IF NOT EXISTS idx_notification_alerts_pending
    ON notification_alerts (status, created_at ASC)
    WHERE status = 'pending';

-- Deduplication check: last sent per client+type
CREATE INDEX IF NOT EXISTS idx_notification_alerts_dedup
    ON notification_alerts (client_id, alert_type, sent_at DESC)
    WHERE status = 'sent';

COMMENT ON TABLE notification_alerts IS
    'Expiry and birthday alert queue. Written by ExpiryChecker, consumed by NotificationScheduler (APScheduler).';
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS notification_alerts CASCADE;
"""


async def upgrade(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(UPGRADE_SQL)


async def downgrade(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(DOWNGRADE_SQL)
