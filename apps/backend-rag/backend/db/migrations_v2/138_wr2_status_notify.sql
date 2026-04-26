-- Migration 138: WR2 status-change NOTIFY trigger
--
-- Purpose: emit a Postgres NOTIFY on the channel `wr2_status_change` every
-- time a row in `war_room_drafts` is INSERTed or its `status` column
-- changes via UPDATE. Consumed by `scripts/wr2_supervisor.py` (a long-
-- running launchd daemon) to chain the WR2 carousel pipeline stages
-- event-driven instead of cron-scheduled.
--
-- Channel:   wr2_status_change   (28 chars; well under the 63-char limit)
-- Payload:   ~120 bytes JSON     (well under the 8 KB pg_notify cap)
--   { "draft_id":   "<uuid>",
--     "old_status": "<str> | null",
--     "new_status": "<str>",
--     "changed_at": <epoch float> }
--
-- Idempotent: trigger uses `IS DISTINCT FROM` to ignore no-op updates.
-- Reviewed by Codex GPT-5.5, Gemini 3.1 Pro, DeepSeek Reasoner (2026-04-26).

CREATE OR REPLACE FUNCTION wr2_status_change_notify() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- INSERT always fires; UPDATE only when status really changed
    -- (IS DISTINCT FROM handles NULL on either side correctly).
    IF (TG_OP = 'INSERT') OR (NEW.status IS DISTINCT FROM OLD.status) THEN
        PERFORM pg_notify(
            'wr2_status_change',
            json_build_object(
                'draft_id',   NEW.id::text,
                'old_status', CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.status END,
                'new_status', NEW.status,
                'changed_at', extract(epoch FROM NOW())
            )::text
        );
    END IF;
    RETURN NEW;
END;
$$;

-- Drop the trigger if it exists (idempotent re-run of this migration).
DROP TRIGGER IF EXISTS wr2_status_change_trg ON war_room_drafts;

-- Fires on every INSERT, plus only those UPDATEs that touch `status`.
-- This narrowing avoids spurious fires from other column updates.
CREATE TRIGGER wr2_status_change_trg
    AFTER INSERT OR UPDATE OF status ON war_room_drafts
    FOR EACH ROW
    EXECUTE FUNCTION wr2_status_change_notify();

COMMENT ON FUNCTION wr2_status_change_notify() IS
    'Emits NOTIFY wr2_status_change with JSON payload {draft_id, old_status, new_status, changed_at}. Consumed by wr2_supervisor.py to event-drive the WR2 carousel pipeline. See docs/wr2/SUPERVISOR.md.';

-- === ROLLBACK ===
-- Reverts the trigger and the function. Safe to run on any DB state because
-- both DROP statements use IF EXISTS — no error if the migration was never
-- applied. Rolling back simply removes the NOTIFY emission; consumers
-- (wr2_supervisor.py) would receive no events but tolerate that gracefully
-- (they fall back to cron-style polling on their next loop).
DROP TRIGGER IF EXISTS wr2_status_change_trg ON war_room_drafts;
DROP FUNCTION IF EXISTS wr2_status_change_notify();
