-- scripts/sql/pro_local/team_promises.sql
--
-- T3 promise gate — Pro-local DDL, NOT a migrations_v2 file (round-1
-- amendment after codex BLOCK on PR #7316). Reasons this table is owned by
-- the Pro organ instead of the shared migration ledger:
--   - `apps/backend-rag/backend/db/migrate.py` has no apply-by-number mode
--     (only `apply-all`), and on Pro that would also try every migration
--     pending after 246 (Pro's ledger stops there) — not what a single new
--     Pro-only table needs.
--   - Merging `apps/backend-rag/**` deploys Fly and the release runs
--     `migrate apply-all`; the ALTER TABLE ADD COLUMN statements a
--     migrations_v2 file would need take an ACCESS EXCLUSIVE lock even
--     when the column already exists (Postgres docs, ALTER TABLE) — for a
--     table this diff never puts data into on Fly, that lock is pure risk
--     for zero benefit, on the runner's 2s SSH timeout no less.
--   - Precedent for this exact pattern already ships in this repo:
--     `scripts/replay_outbox_throttled.py`'s `DLQ_DDL` — a script-owned,
--     `IF NOT EXISTS`-guarded DDL string applied by the script itself via
--     `conn.execute(DDL)`, outside the migrations_v2 ledger entirely.
--
-- Applied by `scripts/wa_team_promises.py --init-schema`, wrapped in ONE
-- transaction by the caller (this file carries no BEGIN/COMMIT of its
-- own). Every statement IF NOT EXISTS so re-running is a no-op. After
-- apply, the caller verifies `uix_team_promises_msg_type` against
-- pg_catalog (table, columns, indisunique, indisvalid, no predicate) —
-- CREATE UNIQUE INDEX IF NOT EXISTS silently no-ops on a same-named index
-- with a DIFFERENT definition, and `ON CONFLICT (message_id,
-- promise_type)` would then fail at insert time with no warning here.

CREATE TABLE IF NOT EXISTS team_promises (
    promise_id                BIGSERIAL PRIMARY KEY,
    message_id                BIGINT NOT NULL,
    conversation_id           BIGINT,
    client_id                 BIGINT,
    promise_text               TEXT NOT NULL,
    promise_type               TEXT,
    due_at                     TIMESTAMPTZ,
    resolved                   BOOLEAN NOT NULL DEFAULT false,
    resolved_at                TIMESTAMPTZ,
    resolved_by_message_id     BIGINT,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE team_promises ADD COLUMN IF NOT EXISTS thread_key TEXT;
ALTER TABLE team_promises ADD COLUMN IF NOT EXISTS team_member_email TEXT;
ALTER TABLE team_promises ADD COLUMN IF NOT EXISTS extractor_version TEXT;
ALTER TABLE team_promises ADD COLUMN IF NOT EXISTS resolution_kind TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uix_team_promises_msg_type
    ON team_promises (message_id, promise_type);

CREATE INDEX IF NOT EXISTS idx_team_promises_unresolved
    ON team_promises (resolved, due_at)
    WHERE resolved = false;

CREATE INDEX IF NOT EXISTS idx_team_promises_thread_key
    ON team_promises (thread_key)
    WHERE thread_key IS NOT NULL;
