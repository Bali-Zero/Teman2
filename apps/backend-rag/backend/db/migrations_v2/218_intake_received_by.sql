-- Migration 218: intake_queue.received_by — who RECEIVED the document.
--
-- Anello 1b (INTAKE login-gate, spec f21671486). The intake queue today scopes
-- nothing by the team member who received a document — only client_id_hint
-- (which client it's about). For the login-gate's by-receiver rule ("the docs
-- that arrived to YOU, you handle") and the anti-Surya control, we record the
-- receiving team member's email on the queue row at enqueue time.
--
-- For the LIVE WhatsApp path (Anello 1), received_by is resolved from the
-- official line that received the message (whatsapp_message_context.
-- team_member_email / the phone_number_id → owner mapping). For drive/zoho/
-- whatsapp-export sources it stays NULL (no receiver concept) — those remain
-- assigned_to-scoped as before. NULL-able by design; the gate treats NULL as
-- "not receiver-owned" and falls back to assigned_to scoping.
--
-- Pure additive column + a partial index for the gate's per-receiver count
-- probe. No backfill (existing rows have no receiver — correct).

ALTER TABLE intake_queue
    ADD COLUMN IF NOT EXISTS received_by TEXT;

-- Hot path for the login-gate probe: "documents received by me, still pending".
-- Partial: only rows that HAVE a receiver and are still in a review state.
CREATE INDEX IF NOT EXISTS idx_iq_received_by_pending
    ON intake_queue (received_by, status)
    WHERE received_by IS NOT NULL
      AND status IN ('review_pending', 'review_claimed');

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_iq_received_by_pending;
ALTER TABLE intake_queue DROP COLUMN IF EXISTS received_by;
