-- scripts/sql/pro_local/team_promises.sql
--
-- T3 promise gate — Pro-local DDL, NOT a migrations_v2 file (Fly's `migrate
-- apply-all` would ACCESS-EXCLUSIVE-lock a table it never touches). Applied
-- by `wa_team_promises.py --init-schema` inside ONE transaction (no
-- BEGIN/COMMIT here). CREATE TABLE IF NOT EXISTS no-ops on a pre-existing
-- table (e.g. a mig-200-shaped team_promises missing `thread_key` etc), so
-- every non-core column is its own ALTER ... ADD COLUMN IF NOT EXISTS,
-- which DOES apply — caller verifies presence+type via pg_catalog in the
-- same transaction, same reason it also verifies both unique indexes.

CREATE TABLE IF NOT EXISTS team_promises (
    promise_id              BIGSERIAL PRIMARY KEY,
    message_id               BIGINT NOT NULL,
    conversation_id          BIGINT,
    client_id                 BIGINT,
    promise_text              TEXT NOT NULL,
    promise_type              TEXT,
    due_at                    TIMESTAMPTZ,
    resolved                  BOOLEAN NOT NULL DEFAULT false,
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

-- Candidates stage (PR-2/PR-3): the scanner only PROPOSES a clause, no
-- dedup here (that's the judged_true -> team_promises ON CONFLICT insert).
-- Same core/ALTER split, in case a prior partial run left this half-built.
CREATE TABLE IF NOT EXISTS team_promise_candidates (
    id                BIGSERIAL PRIMARY KEY,
    message_id         BIGINT NOT NULL,
    clause_idx         INTEGER NOT NULL,
    clause_hash        TEXT NOT NULL,
    promise_type       TEXT NOT NULL
);

ALTER TABLE team_promise_candidates ADD COLUMN IF NOT EXISTS cue TEXT;
ALTER TABLE team_promise_candidates ADD COLUMN IF NOT EXISTS due_at_hint TEXT;
ALTER TABLE team_promise_candidates ADD COLUMN IF NOT EXISTS status TEXT NOT NULL
    DEFAULT 'unjudged' CHECK (status IN ('unjudged', 'judged_true', 'judged_false', 'quarantined'));
ALTER TABLE team_promise_candidates ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE team_promise_candidates ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ;
ALTER TABLE team_promise_candidates ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE UNIQUE INDEX IF NOT EXISTS uix_team_promise_candidates_msg_clause
    ON team_promise_candidates (message_id, clause_idx);
