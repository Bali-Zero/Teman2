-- ============================================================
-- 289_practice_status_log.sql
-- Create the table the portal tracker has been reading since March.
--
-- `practice_status_log` is referenced by four live surfaces —
-- backend/app/routers/portal_process_timeline.py, its test, and the frontend's
-- portal.types.ts + schemas/process.ts — and NO migration in this repo ever
-- created it. Measured on prod 2026-08-27: `relation "practice_status_log"
-- does not exist`.
--
-- The consequence was invisible rather than loud. The reader wraps its query in
-- a bare `except Exception: pass` commented "Table may not exist yet", so every
-- tracker request silently fell through to a single-step timeline and answered
-- 200. The parcel-style progression the portal promises could not render, and
-- nothing anywhere went red.
--
-- WHY A TRIGGER AND NOT APPLICATION CODE
-- The reader selects old_status/new_status/changed_at — an OLD/NEW shape, i.e.
-- trigger-shaped by design. It is also the only shape that cannot be bypassed:
-- `practices.status` is written from many services, and a history table fed by
-- N call sites is a history table that is wrong the first time someone adds
-- the N+1th. The DB observes every UPDATE regardless of which service issued
-- it. Migration 075 already installs `trg_practice_changed` on this same
-- column for pg_notify, so the pattern is established here, not invented.
--
-- changed_by is nullable and read from a session GUC. It is deliberately NOT
-- required: the trigger cannot know an application actor, and inventing one
-- would be worse than recording none. The tracker reader never selects this
-- column on purpose (it holds internal staff emails — see the identity-leak
-- guard in portal_process_timeline.py), so it exists for internal audit only.
-- ============================================================

CREATE TABLE IF NOT EXISTS practice_status_log (
    id          BIGSERIAL PRIMARY KEY,
    practice_id INTEGER     NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
    old_status  VARCHAR(64),
    new_status  VARCHAR(64) NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by  TEXT
);

-- The reader's only access path: WHERE practice_id = $1 ORDER BY changed_at ASC.
CREATE INDEX IF NOT EXISTS idx_practice_status_log_practice_at
    ON practice_status_log (practice_id, changed_at);

COMMENT ON TABLE practice_status_log IS
    'Append-only status history for practices, written by trg_practice_status_log. Feeds the client portal process timeline. changed_by holds an internal actor and is never exposed to a client.';

COMMENT ON COLUMN practice_status_log.old_status IS
    'NULL for the first recorded transition of a practice that predates this table.';

COMMENT ON COLUMN practice_status_log.changed_by IS
    'Internal actor, read from the app.actor session GUC when the caller sets one; NULL otherwise. Never selected by the client-facing timeline query.';

CREATE OR REPLACE FUNCTION log_practice_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- IS DISTINCT FROM, not <>: a NULL on either side must still count as a
    -- change, and `NULL <> 'x'` is NULL, which would silently skip the row.
    -- This is reachable, not theoretical: measured 2026-08-27, PROD's
    -- practices.status is NULLABLE (default 'inquiry'), so a row written with
    -- an explicit NULL takes exactly that path on its first transition. Note
    -- the migrated TEST database has the column NOT NULL — the two schemas
    -- diverge here, which is why the accompanying test branches on the live
    -- constraint instead of assuming either shape.
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO practice_status_log (practice_id, old_status, new_status, changed_by)
        VALUES (
            NEW.id,
            OLD.status,
            NEW.status,
            -- `true` = missing_ok: without it, an UPDATE from any session that
            -- has not set the GUC raises and the practice update itself fails.
            -- History must never be able to block the transition it records.
            NULLIF(current_setting('app.actor', true), '')
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_practice_status_log ON practices;
CREATE TRIGGER trg_practice_status_log
    AFTER UPDATE OF status ON practices
    FOR EACH ROW
    EXECUTE FUNCTION log_practice_status_change();

-- === ROLLBACK ===
-- DROP TRIGGER IF EXISTS trg_practice_status_log ON practices;
-- DROP FUNCTION IF EXISTS log_practice_status_change();
-- DROP TABLE IF EXISTS practice_status_log;
