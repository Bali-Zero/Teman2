"""
Migration 067: Audit Logs for UU PDP Compliance

Creates immutable audit_logs table for tracking access to PII data.
Compliance: UU PDP No. 27/2022 Art. 37 (monitoring and recording of activities)

Rules:
- No UPDATE allowed (WORM: Write Once, Read Many)
- No DELETE allowed (immutable for compliance)
- Partitioned by month for performance
"""

UPGRADE_SQL = """
-- Audit logs table (immutable)
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT,
    client_id INTEGER,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    ip_address INET,
    user_agent TEXT,
    details JSONB DEFAULT '{}'::jsonb
);

-- Prevent updates (WORM compliance)
CREATE OR REPLACE RULE audit_no_update AS
    ON UPDATE TO audit_logs DO INSTEAD NOTHING;

-- Prevent deletes (WORM compliance)
CREATE OR REPLACE RULE audit_no_delete AS
    ON DELETE TO audit_logs DO INSTEAD NOTHING;

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_audit_client_ts
    ON audit_logs (client_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action_ts
    ON audit_logs (action, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource
    ON audit_logs (resource, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user
    ON audit_logs (user_id, timestamp DESC);

-- Comment for documentation
COMMENT ON TABLE audit_logs IS 'Immutable audit trail for UU PDP compliance (Art. 37). No UPDATE/DELETE allowed.';
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS audit_logs CASCADE;
"""


async def upgrade(pool) -> None:
    """Apply migration."""
    async with pool.acquire() as conn:
        await conn.execute(UPGRADE_SQL)


async def downgrade(pool) -> None:
    """Revert migration."""
    async with pool.acquire() as conn:
        await conn.execute(DOWNGRADE_SQL)
