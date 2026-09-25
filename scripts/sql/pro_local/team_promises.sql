-- scripts/sql/pro_local/team_promises.sql
--
-- T3 promise gate — Pro-local DDL (PR-1 of the #7316 re-spec), NOT a
-- migrations_v2 file (Fly's `migrate apply-all` would ACCESS-EXCLUSIVE-lock
-- a table this diff never touches on Fly). Applied by `wa_team_promises.py
-- --init-schema` inside ONE transaction (no BEGIN/COMMIT here). Every
-- statement is IF NOT EXISTS — but that silently no-ops on a same-named
-- index with a DIFFERENT definition, so the caller verifies both unique
-- indexes against pg_catalog by OID in the same transaction, rollback on mismatch.

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
    thread_key                 TEXT,
    team_member_email          TEXT,
    extractor_version           TEXT,
    resolution_kind             TEXT,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_team_promises_msg_type
    ON team_promises (message_id, promise_type);

-- Candidates stage (PR-2/PR-3): the regex scanner only PROPOSES a clause,
-- no dedup here — a judged_true clause is inserted into team_promises
-- (ON CONFLICT (message_id, promise_type) DO NOTHING), dedup happens there.
CREATE TABLE IF NOT EXISTS team_promise_candidates (
    id                BIGSERIAL PRIMARY KEY,
    message_id         BIGINT NOT NULL,
    clause_idx         INTEGER NOT NULL,
    clause_hash        TEXT NOT NULL,
    promise_type       TEXT NOT NULL,
    cue                TEXT,
    due_at_hint        TEXT,
    status              TEXT NOT NULL DEFAULT 'unjudged'
        CHECK (status IN ('unjudged', 'judged_true', 'judged_false', 'quarantined')),
    attempts            INTEGER NOT NULL DEFAULT 0,
    last_attempt_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uix_team_promise_candidates_msg_clause
    ON team_promise_candidates (message_id, clause_idx);
