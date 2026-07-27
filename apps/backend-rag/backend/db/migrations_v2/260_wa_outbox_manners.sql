-- Migration 260: WA outbox "manners" — durable idempotency for the
-- concierge ack (C3) and the terminal-failure apology (C4).
--
-- Both are best-effort auto-messages the worker sends on top of the normal
-- bot reply / human send already tracked by wa_outbox. Without a durable
-- flag, a retry (bot_generate_fn failed once, the SAME row is reprocessed)
-- or a worker crash-and-reclaim could fire either message a second time —
-- an in-memory flag would not survive the crash, and this table already
-- uses claim_token-fenced UPDATEs for every other state transition, so a
-- nullable "sent_at" column on the SAME row follows the existing pattern:
-- NULL = not sent yet, set-once = claimed (fenced by
-- "WHERE ... IS NULL RETURNING id", never reset).

ALTER TABLE wa_outbox
    ADD COLUMN IF NOT EXISTS ack_sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS apology_sent_at TIMESTAMPTZ;

-- === ROLLBACK ===
ALTER TABLE wa_outbox DROP COLUMN IF EXISTS ack_sent_at;
ALTER TABLE wa_outbox DROP COLUMN IF EXISTS apology_sent_at;
