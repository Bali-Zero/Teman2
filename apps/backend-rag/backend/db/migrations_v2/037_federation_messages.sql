-- Migration 037: Federation message bus for inter-node communication
-- Nodes: pro, air, krisna, damar (and future members)

CREATE TABLE IF NOT EXISTS federation_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_node   VARCHAR(50) NOT NULL,
    to_node     VARCHAR(50) NOT NULL,  -- 'all' for broadcast
    subject     VARCHAR(255),
    body        TEXT NOT NULL,
    message_type VARCHAR(50) DEFAULT 'message',  -- 'message', 'task', 'escalation', 'ack'
    priority    VARCHAR(20) DEFAULT 'normal',     -- 'low', 'normal', 'high', 'urgent'
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fed_msg_to_node   ON federation_messages(to_node, read_at);
CREATE INDEX IF NOT EXISTS idx_fed_msg_from_node ON federation_messages(from_node, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fed_msg_unread    ON federation_messages(to_node, created_at DESC) WHERE read_at IS NULL;
