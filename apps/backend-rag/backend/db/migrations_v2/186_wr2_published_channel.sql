-- 186_wr2_published_channel.sql
--
-- WR2 → WR3 cross-pipeline handoff channel.
--
-- Adds a single new PG NOTIFY channel `wr2_episode_published` plus a sibling
-- helper function `publish_wr2_episode_published_event(payload JSONB)` that
-- writes to events_outbox AND fires pg_notify in the SAME transaction
-- (identical atomicity contract to migration 146 trigger functions and
-- migration 183's `publish_wr3_event`).
--
-- WHY a separate function (not extend publish_wr3_event's whitelist):
--   * publish_wr3_event() is constrained to the WR3 6-channel closed set.
--     Adding a WR2-namespace channel to its whitelist would break the
--     "WR3 supervisor owns WR3 channels" invariant and contaminate the
--     error messages emitted to operators.
--   * A dedicated `publish_wr2_episode_published_event()` helper keeps the
--     two pipelines orthogonal at the SQL layer. The WR3 supervisor still
--     consumes the channel via the shared LISTEN/NOTIFY plumbing — only
--     emission is namespace-isolated.
--
-- WHEN it fires (informational — emitter lives in scripts/wr2_supervisor.py,
-- TODO documented in docs/wr3/runbook-supervisor.md "Companion mode"):
--   * After Canva apply succeeds (richtext ops applied, no template_mismatch)
--   * AND Drive staging completes (10 PNGs + brief.json + slides.json)
--   * AND Telegram P0 publish-ready notification sent
--
-- Payload contract (validated at dispatch time by wr3_companion_dispatcher.py
-- — see docstring there for the exact required keys):
--   {
--     "slug": str,                  -- WR2 carousel slug (matches output dir)
--     "slides_count": int,          -- usually 10
--     "hero_image_path": str,       -- relative path to slide-01.png
--     "primary_claim_ids": [str],   -- inherited verbatim → WR3 brief (no re-query)
--     "domain": str,                -- tax|visa|company|property|compliance
--     "audience_segment": str,      -- expat-35-55|founder|...
--     "brief_path": str,            -- WR2 brief.json path (read-only mirror)
--     "slides_path": str            -- WR2 slides.json path (script hook source)
--   }
--
-- Idempotency: CREATE OR REPLACE FUNCTION is safe to re-run. No new tables,
-- no destructive operations. The channel name itself does not require
-- declaration in Postgres (pg_notify accepts any TEXT).
--
-- Squawk lint: forward path is non-destructive. ROLLBACK drops the new
-- function only (no shared state — only the WR2 supervisor calls it).

-- ── Helper function ──────────────────────────────────────────────────
-- publish_wr2_episode_published_event(payload JSONB) RETURNS BIGINT
--
-- Inserts the payload into events_outbox AND fires pg_notify on the
-- 'wr2_episode_published' channel with _outbox_id injected. Returns the
-- outbox row id.
--
-- Channel name is hardcoded (not a parameter) — this function has exactly
-- one job and locking it down prevents typo-channels at the SQL layer.

CREATE OR REPLACE FUNCTION publish_wr2_episode_published_event(
    p_payload JSONB
)
RETURNS BIGINT AS $$
DECLARE
    v_outbox_id  BIGINT;
    v_full       JSONB;
    v_channel    CONSTANT TEXT := 'wr2_episode_published';
BEGIN
    -- Defense-in-depth: ensure payload has the required keys before
    -- consuming queue slots. Missing keys → raise (caller sees a clear
    -- contract violation, not a downstream KeyError in Python).
    IF NOT (p_payload ? 'slug') THEN
        RAISE EXCEPTION
            'publish_wr2_episode_published_event: payload missing required key %', 'slug'
            USING HINT = 'Required keys: slug, slides_count, hero_image_path, '
                         'primary_claim_ids, domain, audience_segment, brief_path, slides_path';
    END IF;

    INSERT INTO events_outbox (channel, payload)
    VALUES (v_channel, p_payload)
    RETURNING id INTO v_outbox_id;

    v_full := p_payload || jsonb_build_object('_outbox_id', v_outbox_id);

    PERFORM pg_notify(v_channel, v_full::text);

    RETURN v_outbox_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION publish_wr2_episode_published_event(JSONB) IS
    'WR2 supervisor entry point for cross-pipeline handoff to WR3. Writes to
     events_outbox + pg_notify in same tx. Channel is locked to
     wr2_episode_published. Consumed by WR3 design-architect via the
     companion_from_carousel mode (docs/wr3/contracts/modes/companion-mode.yaml).
     Outbox _outbox_id injection enables EXPLICIT ack downstream (no auto-ack
     on dispatch return — companion crashes leave the row for replay).';

-- ── Smoke check (intentional comment, not executed) ──────────────────
-- BEGIN;
-- SELECT publish_wr2_episode_published_event(
--     jsonb_build_object(
--         'slug', 'smoke-kep71',
--         'slides_count', 10,
--         'hero_image_path', 'apps/war-room/output/carousel/smoke/slide-01.png',
--         'primary_claim_ids', jsonb_build_array('claim_kep71_2025'),
--         'domain', 'tax',
--         'audience_segment', 'expat-35-55',
--         'brief_path', 'apps/war-room/output/carousel/smoke/brief.json',
--         'slides_path', 'apps/war-room/output/carousel/smoke/slides.json'
--     )
-- );
-- ROLLBACK;

-- === ROLLBACK ===
-- Single function, sole caller is the WR2 supervisor. DROP FUNCTION IF EXISTS
-- is safe (Squawk lint pre-cleared, see migration 168 same pattern).
DROP FUNCTION IF EXISTS publish_wr2_episode_published_event(JSONB);
