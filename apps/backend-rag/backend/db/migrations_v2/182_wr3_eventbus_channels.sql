-- 182_wr3_eventbus_channels.sql
--
-- WR3 Video Production Room eventbus channels.
--
-- Adds 6 PG NOTIFY channels for the WR3 episode state machine, plus a
-- single helper function publish_wr3_event(channel, payload) that fires
-- the NOTIFY AND writes the event to events_outbox in the SAME tx — same
-- contract as migration 146 trigger functions, but invoked imperatively
-- from the Python supervisor instead of from row-level triggers.
--
-- The 6 channels (declared in PG_CHANNEL_MAP at the Python layer):
--   * wr3_episode_brief_requested   — orchestrator fires when a new
--                                     topic enters the room.
--   * wr3_episode_pre_render_ready  — brief sanitized + script frozen,
--                                     ready for parallel shot-director
--                                     + audio-asset-producer.
--   * wr3_episode_gate_passed       — pre_render_gatekeeper PASS, Veo
--                                     spend authorized.
--   * wr3_episode_assembly_ready    — clips + audio both ready.
--   * wr3_episode_critic_verdict    — payload includes verdict =
--                                     PASS | FAIL, per-lane failure mask.
--   * wr3_episode_staged            — Drive staged, awaiting Antonello
--                                     manual publish to IG/TT/YT.
--
-- Atomicity contract: identical to migration 146 — the outbox INSERT and
-- the pg_notify share the user transaction. If the supervisor's tx rolls
-- back, both vanish. If the supervisor commits but the listener is
-- disconnected, the outbox row stays unconsumed and replays on reconnect
-- via EventBus._replay_outbox_on_reconnect.
--
-- Phase 3 driver (cicatrix scar EventBus): WR3 supervisor will implement
-- EXPLICIT per-handler acknowledge_outbox(). Migration 144's
-- replay_unconsumed() auto-acks on dispatch return, which is unsafe for
-- a video pipeline where ffmpeg can crash mid-render. The WR3 supervisor
-- consumer (scripts/wr3_supervisor.py) wraps each dispatch in try/except
-- and only acks on PASS — handler crash leaves the outbox row pending so
-- the event replays on next reconnect.
--
-- Idempotency: CREATE OR REPLACE FUNCTION is safe to re-run. No new
-- tables, indexes, or constraints — events_outbox (migration 144)
-- already exists. The 6 channel names are just strings; PG NOTIFY does
-- not require channel declaration.
--
-- Squawk lint: no destructive operations in the forward path. The
-- ROLLBACK section drops the function (and is the only DDL with risk).

-- ── Helper function ──────────────────────────────────────────────────
-- publish_wr3_event(channel TEXT, payload JSONB) RETURNS BIGINT
--
-- Inserts the payload into events_outbox AND fires pg_notify on the
-- given channel with _outbox_id injected. Returns the outbox row id.
--
-- The Python supervisor calls this inside its own transaction so that
-- a supervisor crash before COMMIT vanishes both the notify and the
-- outbox row (correct MVCC behavior).

CREATE OR REPLACE FUNCTION publish_wr3_event(
    p_channel TEXT,
    p_payload JSONB
)
RETURNS BIGINT AS $$
DECLARE
    v_outbox_id  BIGINT;
    v_full       JSONB;
BEGIN
    -- Validate channel name to prevent injection or typo channels.
    IF p_channel NOT IN (
        'wr3_episode_brief_requested',
        'wr3_episode_pre_render_ready',
        'wr3_episode_gate_passed',
        'wr3_episode_assembly_ready',
        'wr3_episode_critic_verdict',
        'wr3_episode_staged'
    ) THEN
        RAISE EXCEPTION 'publish_wr3_event: invalid channel %', p_channel
            USING HINT = 'Allowed: wr3_episode_brief_requested, _pre_render_ready, _gate_passed, _assembly_ready, _critic_verdict, _staged';
    END IF;

    INSERT INTO events_outbox (channel, payload, created_at)
    VALUES (p_channel, p_payload::text, NOW())
    RETURNING id INTO v_outbox_id;

    v_full := p_payload || jsonb_build_object('_outbox_id', v_outbox_id);

    PERFORM pg_notify(p_channel, v_full::text);

    RETURN v_outbox_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION publish_wr3_event(TEXT, JSONB) IS
    'WR3 supervisor entry point: writes to events_outbox + pg_notify in
     same tx. Channel name is validated against a closed set to prevent
     typos. _outbox_id is injected into the NOTIFY payload so consumers
     can EXPLICITLY ack (not auto-ack — see scripts/wr3_supervisor.py).
     Closes EventBus Phase 3 pending per cicatrix scar.';

-- ── Smoke check (intentional comment, not executed) ──────────────────
-- A development-time sanity check (do not run in migration):
--   BEGIN;
--   SELECT publish_wr3_event(
--       'wr3_episode_brief_requested',
--       jsonb_build_object('episode_id', 'test-1', 'topic', 'smoke')
--   );
--   ROLLBACK;
-- The ROLLBACK guarantees the smoke leaves no row in events_outbox.

-- === ROLLBACK ===
-- squawk-ignore: ban-drop-function — single function, no dependents,
-- only invoked from the WR3 supervisor which is a new code path.
DROP FUNCTION IF EXISTS publish_wr3_event(TEXT, JSONB);
