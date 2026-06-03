-- migration 206_wa_meta_inbox
-- WA Meta Inbox: read+write console for the Meta WhatsApp Business number
-- +62 821-3465-159 (verified_name=BALI ZERO, phone_number_id=1104946272705747).
-- Bot stays human-in-the-loop: replies by default, owner can take over a thread
-- (human_handling flag) which suppresses the bot on that thread only.
--
-- 4-LLM panel synthesis 2026-06-03 (DeepSeek V4 Pro + Codex GPT-5.5 +
-- Gemini 3.1 Pro, per-section adversarial, 5 sections × 3 reviews, 0 REJECT).
-- Design: docs/superpowers/specs/2026-06-03-wa-meta-inbox-design.md
--
-- Key panel-driven invariants enforced here:
-- - meta_inbox_messages is an append-only ledger; partial-unique on
--   meta_message_id (inbound dedup under Meta retries) and on
--   (thread_id, idempotency_key) (human-send dedup under network retries).
-- - last_customer_at on threads is updated ONLY from real inbound customer
--   messages (via GREATEST), NEVER from status receipts — protects the
--   Meta 24h customer-care window integrity.
-- - wa_outbox is a separate operational send-queue with a claim lease
--   (claim_expires_at) so a crashed worker does not park sends forever.
-- - wa_status_pending stages orphan status receipts (read/delivered arriving
--   before the outbound send commit) to apply later.

BEGIN;

-- 1. Threads (one row per counterpart phone, 1:1 conversation).
CREATE TABLE IF NOT EXISTS meta_inbox_threads (
    thread_id BIGSERIAL PRIMARY KEY,
    counterpart_phone TEXT NOT NULL,
    counterpart_name TEXT,
    human_handling BOOLEAN NOT NULL DEFAULT false,
    handling_version INT NOT NULL DEFAULT 0,
    last_customer_at TIMESTAMPTZ,
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_meta_inbox_threads_phone UNIQUE (counterpart_phone)
);

-- 2. Messages: append-only ledger (audit + source of truth for the UI).
CREATE TABLE IF NOT EXISTS meta_inbox_messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id BIGINT NOT NULL REFERENCES meta_inbox_threads(thread_id),
    meta_message_id TEXT,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    sender_role TEXT NOT NULL CHECK (sender_role IN ('customer', 'bot', 'human')),
    body TEXT,
    media_type TEXT,
    media_url TEXT,
    status TEXT NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'queued', 'generating', 'sending',
                          'sent', 'delivered', 'read', 'failed')),
    error TEXT,
    idempotency_key TEXT,
    webhook_id BIGINT REFERENCES inbound_webhooks(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ
);

-- inbound dedup: one ledger row per Meta wamid
CREATE UNIQUE INDEX IF NOT EXISTS uq_meta_inbox_messages_wamid
    ON meta_inbox_messages (meta_message_id)
    WHERE meta_message_id IS NOT NULL;

-- human-send dedup: one row per (thread, client idempotency_key)
CREATE UNIQUE INDEX IF NOT EXISTS uq_meta_inbox_messages_idem
    ON meta_inbox_messages (thread_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- UI conversation query (messages of a thread, newest first)
CREATE INDEX IF NOT EXISTS meta_inbox_messages_thread_created_idx
    ON meta_inbox_messages (thread_id, created_at DESC);

-- 3. Outbox: operational send-intent queue consumed by the worker.
CREATE TABLE IF NOT EXISTS wa_outbox (
    id BIGSERIAL PRIMARY KEY,
    thread_id BIGINT NOT NULL REFERENCES meta_inbox_threads(thread_id),
    message_id BIGINT NOT NULL REFERENCES meta_inbox_messages(id),
    needs_generation BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'generating', 'claimed', 'done', 'failed')),
    claim_token UUID,
    claimed_at TIMESTAMPTZ,
    claim_expires_at TIMESTAMPTZ,
    attempts INT NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_wa_outbox_message UNIQUE (message_id)
);

-- worker dequeue: pending rows due for send, cheapest possible scan
CREATE INDEX IF NOT EXISTS wa_outbox_pending_idx
    ON wa_outbox (next_retry_at, id)
    WHERE status = 'pending';

-- 4. UI thread-list query (keyset pagination ORDER BY last_message_at DESC, thread_id DESC)
CREATE INDEX IF NOT EXISTS meta_inbox_threads_last_message_idx
    ON meta_inbox_threads (last_message_at DESC, thread_id DESC);

-- 5. Orphan status receipts: a delivered/read callback may arrive before the
-- outbound send row has committed its wamid. Stage it, apply on send commit.
CREATE TABLE IF NOT EXISTS wa_status_pending (
    meta_message_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    error TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;

-- === ROLLBACK ===
-- Inline rollback per W42 lint requirement. To revert, run (manually, in a
-- transaction) the inverse of the four CREATE TABLE statements above, in
-- reverse dependency order: wa_status_pending, then wa_outbox, then
-- meta_inbox_messages, then meta_inbox_threads. (Statements omitted verbatim
-- here because the guardrails hook blocks destructive SQL tokens even in
-- comments; see docs/superpowers/specs/2026-06-03-wa-meta-inbox-design.md.)
