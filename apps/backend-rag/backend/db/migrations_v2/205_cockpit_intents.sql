-- 205_cockpit_intents.sql
-- Intent queue: cockpit writes here, existing services consume
-- Decouples UI from production state machines (war_room_drafts, intel_items)
-- === FORWARD ===
CREATE TABLE IF NOT EXISTS cockpit_intents (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    intent_type TEXT NOT NULL,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'consumed', 'rejected', 'expired')),
    consumer TEXT,
    consumed_at TIMESTAMPTZ,
    error_message TEXT,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE INDEX IF NOT EXISTS idx_cockpit_intents_pending ON cockpit_intents (intent_type, created_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_cockpit_intents_expires ON cockpit_intents (expires_at) WHERE status = 'pending';

COMMENT ON TABLE cockpit_intents IS 'Intent queue from Zantara Cockpit. Consumers: intel-lake-router-cron.sh (intel.skip/rerun), wr2_supervisor.py (wr2.approve/reject), manual review (cron.kill, library.*).';

-- === ROLLBACK ===
-- DROP INDEX IF EXISTS idx_cockpit_intents_expires;
-- DROP INDEX IF EXISTS idx_cockpit_intents_pending;
-- DROP TABLE IF EXISTS cockpit_intents;
