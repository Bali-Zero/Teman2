-- migration 178_dream_room_state
-- TODO(#77) closure: persist Dream Room state in Postgres JSONB instead of
-- an in-memory MOCK_DB dict that resets on every Fly machine restart.
--
-- Single-row-per-user UPSERT pattern. No multi-tenant scoping yet
-- (user_id is whatever string the client sends — same security level
-- as the pre-existing in-memory MOCK_DB; tightening is out of scope).

CREATE TABLE IF NOT EXISTS dream_room_state (
    user_id    VARCHAR(255) PRIMARY KEY,
    state      JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE dream_room_state IS
    'Dream Thinking Room per-user state snapshot. Single row per user_id,
     upserted on every POST /api/dream/state. Closes TODO(#77).';
COMMENT ON COLUMN dream_room_state.user_id IS
    'Opaque user identifier sent by the client. NOT authenticated at this
     layer — tightening is tracked separately.';
COMMENT ON COLUMN dream_room_state.state IS
    'JSON blob of the Dream Room canvas (articles, inspirations, layout).
     Pass as a Python dict; the asyncpg pool has a jsonb codec
     (init_db_connection) so json.dumps would double-encode.';

-- === ROLLBACK ===
DROP TABLE IF EXISTS dream_room_state;
