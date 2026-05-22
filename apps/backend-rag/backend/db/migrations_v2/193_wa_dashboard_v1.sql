-- migration 193: WA Team Inbox Dashboard v1
-- Companion spec: research/operations/specs/2026-05-23-wa-team-inbox-webapp.md (v3)
-- Companion decisions: research/operations/specs/2026-05-23-wa-team-inbox-webapp-decisions.md
-- Compliance basis: NB-6 UU PDP 27/2022 sintesi A.1-A.9 of decisions doc
--
-- Adds 5 tables + FTS GIN + 3 pg_notify channels for the local-only Bali Zero
-- team WhatsApp inbox webapp (apps/wa-dashboard/).
--
-- IMPORTANT: this migration is ADDITIVE only. No destructive operations
-- on existing tables. The trigger trg_wa_message_notify on existing
-- whatsapp_message_context is installed via CREATE OR REPLACE FUNCTION
-- plus an idempotency DO block (no DROP). Rollback procedure documented
-- in companion file 193_wa_dashboard_v1.rollback.sql (separate file kept
-- out of the additive migration runner).

-- ============================================================
-- 1. RBAC mapping table (devils-advocate v3 fix #6)
-- Maps user_email -> which team_member_phone(s) they can send from
-- ============================================================
CREATE TABLE IF NOT EXISTS team_member_phone_authorizations (
  user_email VARCHAR(255) NOT NULL,
  team_member_phone VARCHAR(20) NOT NULL,
  granted_by VARCHAR(255) NOT NULL,
  granted_at TIMESTAMPTZ DEFAULT NOW(),
  revoked_at TIMESTAMPTZ,
  PRIMARY KEY (user_email, team_member_phone)
);

CREATE INDEX IF NOT EXISTS idx_tmpa_lookup
  ON team_member_phone_authorizations(user_email)
  WHERE revoked_at IS NULL;

COMMENT ON TABLE team_member_phone_authorizations IS
  'RBAC for /api/v1/wa-dashboard/send: which user_email can send from which team_member_phone. Seed defaults to 1:1 user-to-own-phone; cross-account grants opt-in admin only.';

-- ============================================================
-- 2. Outbound queue (anti-ban jittered cooldown)
-- ============================================================
CREATE TABLE IF NOT EXISTS wa_dashboard_outbound_queue (
  queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  team_member_phone VARCHAR(20) NOT NULL,
  counterpart_phone VARCHAR(20) NOT NULL,
  body TEXT,
  media_path TEXT,
  scheduled_for TIMESTAMPTZ NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','dispatching','dispatched','failed','cancelled')),
  dispatched_baileys_message_id TEXT,
  dispatched_at TIMESTAMPTZ,
  error_message TEXT,
  retry_count SMALLINT NOT NULL DEFAULT 0,
  created_by VARCHAR(255) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wdoq_team_scheduled
  ON wa_dashboard_outbound_queue(team_member_phone, scheduled_for)
  WHERE status IN ('pending','dispatching');

CREATE INDEX IF NOT EXISTS idx_wdoq_created_by
  ON wa_dashboard_outbound_queue(created_by, created_at DESC);

COMMENT ON COLUMN wa_dashboard_outbound_queue.scheduled_for IS
  'Anti-ban cooldown anchor: NOW() + uniform(10, 30)s computed under pg_advisory_xact_lock(hash(team_member_phone)) to prevent jitter race.';

COMMENT ON COLUMN wa_dashboard_outbound_queue.status IS
  'pending -> dispatching (worker claimed via SELECT FOR UPDATE SKIP LOCKED) -> dispatched | failed. dispatching > 60s old without progress = crash-mid-send -> mark failed for manual review.';

-- ============================================================
-- 3. Idempotency cache for POST /send (24h TTL)
-- ============================================================
CREATE TABLE IF NOT EXISTS wa_outbound_idempotency (
  idempotency_key VARCHAR(64) NOT NULL,
  user_email VARCHAR(255) NOT NULL,
  response_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '24 hours',
  PRIMARY KEY (idempotency_key, user_email)
);

CREATE INDEX IF NOT EXISTS idx_woi_expires
  ON wa_outbound_idempotency(expires_at);

COMMENT ON TABLE wa_outbound_idempotency IS
  'Cron hourly cleanup prunes entries with expires_at past. devils-advocate v3 fix 9 unbounded growth.';

-- ============================================================
-- 4. Threads - UI-side state for unified inbox
-- ============================================================
CREATE TABLE IF NOT EXISTS wa_dashboard_threads (
  thread_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  counterpart_phone VARCHAR(20) NOT NULL,
  chat_type VARCHAR(10) NOT NULL CHECK (chat_type IN ('dm','group')),
  group_jid TEXT,
  team_member_phone VARCHAR(20),
  assigned_to VARCHAR(255),
  status VARCHAR(20) NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','assigned','waiting','escalated','handled','closed')),
  client_id BIGINT,
  practice_id BIGINT,
  last_message_at TIMESTAMPTZ NOT NULL,
  unread_count INT NOT NULL DEFAULT 0,
  tags TEXT[] DEFAULT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  -- v3 fix #10: prevent empty-string-vs-NULL collision in COALESCE unique index
  CONSTRAINT wdt_team_phone_not_empty
    CHECK (team_member_phone IS NULL OR team_member_phone <> ''),
  CONSTRAINT wdt_group_jid_not_empty
    CHECK (group_jid IS NULL OR group_jid <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wdt_unique_thread
  ON wa_dashboard_threads (
    counterpart_phone,
    COALESCE(team_member_phone, ''),
    COALESCE(group_jid, '')
  );

CREATE INDEX IF NOT EXISTS idx_wdt_assigned_status
  ON wa_dashboard_threads(assigned_to, status)
  WHERE status NOT IN ('handled','closed');

CREATE INDEX IF NOT EXISTS idx_wdt_last_message
  ON wa_dashboard_threads(last_message_at DESC);

COMMENT ON TABLE wa_dashboard_threads IS
  'UI-side state: one row per (counterpart_phone, team_member_phone, group_jid) tuple. team_member_phone NULL = cross-account merged view (admin-toggled).';

-- ============================================================
-- 5. Operator audit log (UU PDP Pasal 39 compliance)
-- ============================================================
CREATE TABLE IF NOT EXISTS whatsapp_operator_actions (
  id BIGSERIAL PRIMARY KEY,
  user_email VARCHAR(255) NOT NULL,
  action_type VARCHAR(50) NOT NULL CHECK (action_type IN (
    'send','tag','assign','reassign','escalate','resolve_attention',
    'add_note','close_thread','reopen_thread','claim_thread','view_thread','search'
  )),
  target_message_id BIGINT REFERENCES whatsapp_message_context(id),
  target_thread_id UUID REFERENCES wa_dashboard_threads(thread_id),
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_woa_user_created
  ON whatsapp_operator_actions(user_email, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_woa_target_msg
  ON whatsapp_operator_actions(target_message_id)
  WHERE target_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_woa_target_thread
  ON whatsapp_operator_actions(target_thread_id)
  WHERE target_thread_id IS NOT NULL;

COMMENT ON TABLE whatsapp_operator_actions IS
  'UU PDP Pasal 39 audit log: every operator interaction with WA data. Retention 5+ years. Cite in ROPA (Records of Processing Activities).';

-- ============================================================
-- 6. FTS index on body (multilingual safe via simple config)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_wmc_body_fts
  ON whatsapp_message_context
  USING GIN (to_tsvector('simple', COALESCE(body, message_text, '')));

COMMENT ON INDEX idx_wmc_body_fts IS
  'Full-text search for /api/v1/wa-dashboard/search. simple config = no language stemming (multilingual safe IT/EN/ID).';

-- ============================================================
-- 7. pg_notify trigger function on whatsapp_message_context INSERT
-- Pointer-only payload (well under 8KB PG NOTIFY hard limit)
-- ============================================================
CREATE OR REPLACE FUNCTION notify_wa_message_inserted() RETURNS TRIGGER AS $$
BEGIN
  PERFORM pg_notify('wa_message_inserted', json_build_object(
    'id', NEW.id,
    'direction', NEW.direction,
    'team_member_phone', NEW.team_member_phone,
    'counterpart_phone', NEW.counterpart_phone,
    'chat_type', NEW.chat_type,
    'group_jid', NEW.group_jid,
    'attention_priority', NEW.attention_priority
  )::text);
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

-- Install trigger binding idempotently without using DROP TRIGGER
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'trg_wa_message_notify'
      AND tgrelid = 'whatsapp_message_context'::regclass
  ) THEN
    CREATE TRIGGER trg_wa_message_notify
      AFTER INSERT ON whatsapp_message_context
      FOR EACH ROW EXECUTE FUNCTION notify_wa_message_inserted();
  END IF;
END $$;

COMMENT ON FUNCTION notify_wa_message_inserted() IS
  'Pointer-only payload (id + tuple keys). SSE worker SELECTs full row by ID. Avoids 8KB NOTIFY limit. wa_outbound_queued + wa_outbound_dispatched channels emitted explicitly by send endpoint / bridge worker (NOT via row trigger).';

-- === ROLLBACK ===
-- Reverses migration 193 (wa_dashboard_v1).
-- Order: trigger → function → FTS index on existing table → new indexes → new tables.
-- All operations use IF EXISTS for idempotency.
-- Note: whatsapp_message_context table predates this migration (wa-mirror service).
-- Only the trigger + FTS index added by 193 are dropped from it; the table stays.

DROP TRIGGER IF EXISTS trg_wa_message_notify ON whatsapp_message_context;
DROP FUNCTION IF EXISTS notify_wa_message_inserted();

DROP INDEX IF EXISTS idx_wmc_body_fts;
DROP INDEX IF EXISTS idx_woa_target_thread;
DROP INDEX IF EXISTS idx_woa_target_msg;
DROP INDEX IF EXISTS idx_woa_user_created;
DROP INDEX IF EXISTS idx_wdt_last_message;
DROP INDEX IF EXISTS idx_wdt_assigned_status;
DROP INDEX IF EXISTS idx_woi_expires;
DROP INDEX IF EXISTS idx_wdoq_created_by;
DROP INDEX IF EXISTS idx_wdoq_team_scheduled;
DROP INDEX IF EXISTS idx_tmpa_lookup;

DROP TABLE IF EXISTS whatsapp_operator_actions;
DROP TABLE IF EXISTS wa_dashboard_threads;
DROP TABLE IF EXISTS wa_outbound_idempotency;
DROP TABLE IF EXISTS wa_dashboard_outbound_queue;
DROP TABLE IF EXISTS team_member_phone_authorizations;
