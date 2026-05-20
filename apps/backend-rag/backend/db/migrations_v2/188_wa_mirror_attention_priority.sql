-- migration 188: WA mirror attention priority columns
-- Adds attention_priority + attention_reason + attention_computed_at to whatsapp_message_context.
-- Used by wa-mirror-attention-classifier.py (cron 5min) for Phase 1 "Owner Attention Queue".
-- Source: research/operations/2026-05-20-wa-chat-flow-synthesis.md

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name='whatsapp_message_context' AND column_name='attention_priority') THEN
    ALTER TABLE whatsapp_message_context
      ADD COLUMN attention_priority TEXT
        CHECK (attention_priority IN ('HIGH','MEDIUM','LOW') OR attention_priority IS NULL),
      ADD COLUMN attention_reason TEXT[] DEFAULT NULL,
      ADD COLUMN attention_computed_at TIMESTAMPTZ DEFAULT NULL,
      ADD COLUMN attention_resolved_at TIMESTAMPTZ DEFAULT NULL;
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_wmc_attention_priority_unresolved
  ON whatsapp_message_context (attention_priority, created_at DESC)
  WHERE attention_priority = 'HIGH' AND attention_resolved_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_wmc_attention_computed_at
  ON whatsapp_message_context (attention_computed_at)
  WHERE attention_computed_at IS NOT NULL;

COMMENT ON COLUMN whatsapp_message_context.attention_priority IS
  'HIGH (immediate Telegram + dashboard), MEDIUM (digest), LOW (silent). NULL = unclassified.';
COMMENT ON COLUMN whatsapp_message_context.attention_reason IS
  'Reason codes array: refund, complaint, deadline, payment_dispute, lawyer, audit, new_lead, unanswered_thread, urgent_keyword, media_on_active_practice, etc.';
COMMENT ON COLUMN whatsapp_message_context.attention_resolved_at IS
  'Set by classifier when team responds outbound within 2h (HIGH→MEDIUM decay) or admin manual resolve.';

-- === ROLLBACK ===

DROP INDEX IF EXISTS idx_wmc_attention_priority_unresolved;
DROP INDEX IF EXISTS idx_wmc_attention_computed_at;
ALTER TABLE whatsapp_message_context
  DROP COLUMN IF EXISTS attention_priority,
  DROP COLUMN IF EXISTS attention_reason,
  DROP COLUMN IF EXISTS attention_computed_at,
  DROP COLUMN IF EXISTS attention_resolved_at;
