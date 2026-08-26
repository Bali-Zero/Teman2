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
    -- NULLABLE, deliberately, and this was a real defect caught by an
    -- adversarial review before merge: it was `NOT NULL`, and since PROD's
    -- practices.status is nullable, `UPDATE practices SET status = NULL`
    -- entered the trigger, violated that constraint, and ABORTED THE CALLER'S
    -- UPDATE -- measured, the row stayed at its old value. The history table
    -- vetoed the transition it exists to observe, which is precisely what the
    -- comment on current_setting below forbids. A history row must be able to
    -- express whatever the source column can hold.
    new_status  VARCHAR(64),
    -- clock_timestamp(), NOT now(): now() returns TRANSACTION START time, so
    -- two concurrent transitions on the same practice can be recorded in the
    -- reverse of the order they committed, and the reader's ORDER BY
    -- changed_at ASC would then show the timeline out of sequence -- and pick
    -- the wrong row as current, since it treats the last row as current.
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    changed_by  TEXT
);

-- CONVERGENCE, not decoration. `CREATE TABLE IF NOT EXISTS` silently ACCEPTS a
-- pre-existing table whose shape differs -- so on any database that already
-- holds an earlier draft of this table, the CREATE above is a no-op and the
-- column keeps its old constraint. That is not hypothetical: it happened during
-- this migration's own development, where a database carrying the draft's
-- `new_status NOT NULL` kept aborting the caller's UPDATE even after the CREATE
-- was fixed, because the CREATE never ran. These ALTERs make the file converge
-- to the intended shape whatever the database started from, which is also what
-- makes it honestly idempotent rather than idempotent-only-for-creation.
ALTER TABLE practice_status_log ALTER COLUMN new_status DROP NOT NULL;
ALTER TABLE practice_status_log ALTER COLUMN changed_at SET DEFAULT clock_timestamp();

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
-- These statements are EXECUTABLE on purpose. An earlier draft had all three
-- commented out: the runner then executed a comments-only string, reported the
-- rollback as successful, and dropped the version row while table, function and
-- trigger stayed installed. Caught by an adversarial review, not by the suite,
-- whose `assert rollback is not None` passed on that string too.
DROP TRIGGER IF EXISTS trg_practice_status_log ON practices;
DROP FUNCTION IF EXISTS log_practice_status_change();
DROP TABLE IF EXISTS practice_status_log;
