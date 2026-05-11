-- 164_wr2_status_change_outbox.sql
--
-- "Everyone hears everything" #2: close the WR2 durability gap.
--
-- Migration 138 created the wr2_status_change_notify() trigger function
-- which fires pg_notify('wr2_status_change', ...) when war_room_drafts
-- rows insert or change status. Consumer: scripts/wr2_supervisor.py
-- (long-running launchd daemon, not registered in PG_CHANNEL_MAP).
--
-- Phase-2 EventBus refactor (migration 146) deliberately skipped this
-- channel because its consumer is dedicated, not the in-process EventBus
-- replay-on-reconnect path. Result: when wr2_supervisor.py is offline,
-- pg_notify packets are dropped on the floor — no durability.
--
-- This migration mirrors the 146 pattern: payload is built first, INSERT
-- INTO events_outbox PRESERVES the event durably, THEN pg_notify fires
-- with _outbox_id injected so the consumer can ack idempotently.
--
-- wr2_supervisor.py is expected to read events_outbox WHERE
-- channel='wr2_status_change' AND consumed_at IS NULL on startup
-- (replay path) and to call outbox.acknowledge(_outbox_id) after each
-- successful dispatch. That work is in apps/war-room — NOT this
-- migration. The migration only opens the door; the supervisor walks
-- through it.
--
-- Atomicity: the INSERT INTO events_outbox + pg_notify run inside the
-- user transaction that produced the war_room_drafts INSERT/UPDATE.
-- Same contract as 146.
--
-- Idempotency: CREATE OR REPLACE FUNCTION + DROP TRIGGER IF EXISTS +
-- CREATE TRIGGER. Safe to re-apply.

CREATE OR REPLACE FUNCTION wr2_status_change_notify() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    payload    JSONB;
    outbox_id  BIGINT;
BEGIN
    -- INSERT always fires; UPDATE only when status really changed
    -- (IS DISTINCT FROM handles NULL on either side correctly).
    IF (TG_OP = 'INSERT') OR (NEW.status IS DISTINCT FROM OLD.status) THEN
        payload := jsonb_build_object(
            'draft_id',   NEW.id::text,
            'old_status', CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.status END,
            'new_status', NEW.status,
            'changed_at', extract(epoch FROM NOW())
        );

        INSERT INTO events_outbox (channel, payload)
        VALUES ('wr2_status_change', payload)
        RETURNING id INTO outbox_id;

        PERFORM pg_notify(
            'wr2_status_change',
            (payload || jsonb_build_object('_outbox_id', outbox_id))::text
        );
    END IF;
    RETURN NEW;
END;
$$;

-- Trigger itself unchanged from migration 138 — only the function body is
-- refactored. We don't drop+recreate the trigger to avoid any window where
-- it's missing within this transaction. The trigger keeps pointing at the
-- same function name (CREATE OR REPLACE replaced the body in place).

COMMENT ON FUNCTION wr2_status_change_notify() IS
    'Emits NOTIFY wr2_status_change with JSON payload {draft_id, old_status, new_status, changed_at, _outbox_id}. Writes to events_outbox FIRST for durability across listener disconnect windows. Consumed by wr2_supervisor.py — replay path reads events_outbox WHERE channel=wr2_status_change AND consumed_at IS NULL. See migration 164 + apps/war-room/scripts/wr2_supervisor.py.';

-- === ROLLBACK ===
-- Reverts the function body to the migration 138 form (pg_notify only,
-- no events_outbox row). Trigger and outbox table are NOT dropped — the
-- table is shared infrastructure (migration 144), and the trigger keeps
-- pointing at the same function name. Rolling back simply removes the
-- durability layer; consumers fall back to ephemeral pg_notify only.
CREATE OR REPLACE FUNCTION wr2_status_change_notify() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
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
