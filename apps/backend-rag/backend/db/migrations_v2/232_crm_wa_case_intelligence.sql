-- migration 232: CRM WhatsApp case intelligence
--
-- Stores one Zantara Captain card per WhatsApp conversation/case linked to a
-- CRM client. This is intentionally separate from clients.strategic_recap:
-- the recap is the high-level client story, while this table preserves the
-- case-level reasoning, ideal reply, evidence, and operational flags.

CREATE TABLE IF NOT EXISTS crm_wa_case_intelligence (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  conversation_key TEXT NOT NULL,
  member_phone TEXT,
  counterpart_key TEXT,
  display_name TEXT,
  chat_kind TEXT NOT NULL DEFAULT 'direct'
    CHECK (chat_kind IN ('direct', 'group', 'unknown')),
  case_status TEXT NOT NULL DEFAULT 'open'
    CHECK (case_status IN ('open', 'waiting', 'blocked', 'done', 'archived')),
  case_type TEXT,
  source_model TEXT NOT NULL DEFAULT 'gpt-5.5',
  reasoning_effort TEXT DEFAULT 'xhigh',
  analysis_hash TEXT NOT NULL,
  analysis_id TEXT,
  message_count INTEGER NOT NULL DEFAULT 0,
  unread_count INTEGER NOT NULL DEFAULT 0,
  last_message_at TIMESTAMPTZ,
  priority_score INTEGER NOT NULL DEFAULT 0,
  flags JSONB NOT NULL DEFAULT '[]'::jsonb,
  recap TEXT,
  next_action TEXT,
  ideal_reply TEXT,
  evidence TEXT,
  crm_packet TEXT,
  raw_sections JSONB NOT NULL DEFAULT '{}'::jsonb,
  analysis_output_path TEXT,
  generated_at TIMESTAMPTZ,
  imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT crm_wa_case_intelligence_unique_conversation
    UNIQUE (client_id, conversation_key)
);

CREATE INDEX IF NOT EXISTS idx_cwci_client_last_message
  ON crm_wa_case_intelligence(client_id, last_message_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_cwci_client_priority
  ON crm_wa_case_intelligence(client_id, priority_score DESC, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_cwci_flags
  ON crm_wa_case_intelligence USING GIN (flags);

COMMENT ON TABLE crm_wa_case_intelligence IS
  'Zantara Captain case cards derived from WhatsApp conversations. One row per CRM client + conversation key; stores reasoning surfaces, not raw chat logs.';

COMMENT ON COLUMN crm_wa_case_intelligence.conversation_key IS
  'Stable key from wa-dashboard analysis: chat_kind|team_member_phone|counterpart.';

COMMENT ON COLUMN crm_wa_case_intelligence.crm_packet IS
  'Human-readable CRM note candidate. Technical/debug packets must stay in raw_sections only.';

-- === ROLLBACK ===
-- DROP TABLE IF EXISTS crm_wa_case_intelligence;
