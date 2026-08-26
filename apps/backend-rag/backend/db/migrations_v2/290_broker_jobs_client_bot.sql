-- Migration 290: broker_jobs client-bot generalization (I DUE BOT F1/F3, lane B2)
--
-- Number chosen with a safety margin, not sequentially, per the W40 migration-
-- number-collision cicatrice (.claude/rules/cicatrix-superscar.md #9, and
-- 283_wa_reply_claims.sql's own header for the full incident): this branch
-- (feature/due-bot) is a long-lived local-first integration branch whose
-- migrations_v2/ history has drifted BEHIND origin/main (this branch's own
-- highest number is 283; origin/main's is 287, via unrelated GARUDA work
-- landed independently while this branch stayed local). Picking 284 here
-- would silently collide with origin/main's own 284_garuda_orders.sql at
-- final-PR-train time — verified via `git ls-tree origin/main --
-- .../migrations_v2/` before choosing this number, exactly the check W40's
-- postmortem says the CI lint cannot make for you (it only compares main
-- against the CURRENT PR, never two independently-numbered branches against
-- each other). 290 leaves margin above both branches' confirmed-live heads.
--
-- MANDATE.md F1 (verbatim): "the dark `services/integrations/wa_broker.py`
-- queue (add `surface`/`job_kind`/`output_schema_version` fields — do NOT
-- create a second jobs table)." research capture §2.1 names the exact
-- target shape (job_kind, surface, request_id, output_schema_version,
-- preferred_seat_pool). This migration is the additive half of that: it
-- widens `broker_jobs` to carry a client-bot codex-broker job
-- (job_kind='client_answer_v1') ALONGSIDE the existing WA-outbox rows
-- (job_kind IS NULL, unchanged meaning) — never a second table, per F1.
--
-- Design, in the same spirit as 270's own invariants:
-- - Purely additive to every EXISTING row: every new column is nullable, no
--   existing CHECK is tightened, no existing index changes shape. A legacy
--   WA row (job_kind IS NULL) is REQUIRED to still carry outbox_id/
--   thread_id/thread_epoch (enforced below by a new CHECK now that the
--   column-level NOT NULL these three carried is relaxed) — the DB, not
--   application code, keeps the historical invariant honest.
-- - `outbox_id`/`thread_id`/`thread_epoch` become NULLABLE at the column
--   level because a client-bot BrainRequest has no wa_outbox/
--   meta_inbox_threads row to reference at all (services/client_bot/
--   contracts.py's BrainRequest carries only request_id/message/profile/
--   grounding/deadline_at — CanonicalMessage, not a WA outbox row). The two
--   FKs (REFERENCES wa_outbox(id) / meta_inbox_threads(thread_id)) are
--   UNCHANGED and still enforced whenever a value IS present — Postgres FKs
--   are satisfied vacuously by NULL.
-- - `job_kind`/`surface` are narrow, closed CHECKs (not free TEXT) so a typo
--   cannot silently mint an unrouted job_kind — mirrors the existing `mode`
--   CHECK's own discipline on this same table.
-- - `request_id` is NOT given a uniqueness constraint here (deliberately;
--   see services/integrations/wa_broker.py::offer_client_job's docstring —
--   the WA leg's one-codex-leg-per-outbox invariant exists to protect a
--   RETRY LADDER across worker crashes, which the client-bot leg does not
--   have: ClientBrainProviderRouter.route() calls a provider's generate()
--   at most once per request). Declared, not silently omitted.
-- - No change to the payload-NULL-at-terminal CHECK
--   (broker_jobs_terminal_payload_null) — it already covers package/
--   evidence_inputs/result_text generically, and client-bot jobs use the
--   SAME three columns (evidence_inputs stays NULL for a client job; the
--   grounding bundle travels inside `package` instead, since client-bot's
--   GroundingBundle is a single frozen JSON object, not the WA leg's split
--   package/evidence_inputs shape).
-- - No change to `uq_broker_jobs_serve_outbox` (ON broker_jobs (outbox_id)
--   WHERE mode = 'serve'): a client-bot row's outbox_id is NULL, and
--   Postgres unique indexes treat NULLs as pairwise distinct, so any number
--   of client-bot 'serve' rows coexist under that index without a DDL
--   change — verified against PostgreSQL's own NULLS DISTINCT default
--   behavior (the ON CONFLICT/unique-index docs), not assumed.

BEGIN;

-- 1. Relax the three WA-outbox-only NOT NULLs. FK constraints (unnamed,
--    declared inline at CREATE TABLE time) are untouched — NULL still
--    satisfies a foreign key trivially, per the SQL standard. Squawk's
--    ban-drop-not-null fires on all three (rightly, in general) — silenced
--    here because step 4 immediately restores the exact same invariant as
--    a CHECK (broker_jobs_kind_identifiers_check): a legacy WA row still
--    cannot have a NULL outbox_id/thread_id/thread_epoch, the DB just
--    proves it a different way. Not a silent relaxation.
-- squawk-ignore ban-drop-not-null
ALTER TABLE broker_jobs ALTER COLUMN outbox_id DROP NOT NULL;
-- squawk-ignore ban-drop-not-null
ALTER TABLE broker_jobs ALTER COLUMN thread_id DROP NOT NULL;
-- squawk-ignore ban-drop-not-null
ALTER TABLE broker_jobs ALTER COLUMN thread_epoch DROP NOT NULL;

-- 2. Generic client-bot columns (research capture §2.1's target shape,
--    minus `package_json`/`result_json`/`outbox_id` duplicates — this table
--    already has `package`/`result_text`/`outbox_id`, reused as-is per F1's
--    "do not create a second jobs table").
ALTER TABLE broker_jobs ADD COLUMN IF NOT EXISTS job_kind TEXT;
ALTER TABLE broker_jobs ADD COLUMN IF NOT EXISTS surface TEXT;
ALTER TABLE broker_jobs ADD COLUMN IF NOT EXISTS request_id UUID;
ALTER TABLE broker_jobs ADD COLUMN IF NOT EXISTS output_schema_version TEXT;
ALTER TABLE broker_jobs ADD COLUMN IF NOT EXISTS preferred_seat_pool TEXT;

-- 3. Closed vocabularies, NULL = legacy WA row (unchanged meaning).
ALTER TABLE broker_jobs
    ADD CONSTRAINT broker_jobs_job_kind_check CHECK (
        job_kind IS NULL OR job_kind = 'client_answer_v1'
    );
ALTER TABLE broker_jobs
    ADD CONSTRAINT broker_jobs_surface_check CHECK (
        surface IS NULL
        OR surface IN ('whatsapp', 'instagram', 'portal', 'kbli_widget')
    );

-- 4. The invariant the column-level NOT NULLs used to carry, restated as a
--    CHECK now that they are relaxed: a legacy WA row (job_kind IS NULL)
--    MUST still have outbox_id/thread_id/thread_epoch; a client-bot row
--    (job_kind = 'client_answer_v1') carries request_id/surface instead and
--    must NOT carry the WA-only identifiers (a job cannot legitimately
--    claim to be both at once — catches a future INSERT bug at the DB, not
--    just in application code).
ALTER TABLE broker_jobs
    ADD CONSTRAINT broker_jobs_kind_identifiers_check CHECK (
        (job_kind IS NULL
            AND outbox_id IS NOT NULL AND thread_id IS NOT NULL
            AND thread_epoch IS NOT NULL
            AND request_id IS NULL AND surface IS NULL)
        OR
        (job_kind = 'client_answer_v1'
            AND request_id IS NOT NULL AND surface IS NOT NULL
            AND outbox_id IS NULL AND thread_id IS NULL)
    );

-- Claim/scan-path index: the daemon-facing claim() query
-- (wa_broker.claim_job) already scans `state = 'offered' ORDER BY
-- created_at` job_kind-agnostically (no WHERE on job_kind) — the existing
-- broker_jobs_offered_idx already covers a client-bot row exactly as it
-- covers a WA row, so no new index is needed there.

-- Lookup index for a client-bot request's own job (health checks,
-- support/debugging, and a future promotion-ladder metric querying "this
-- request's codex leg outcome").
CREATE INDEX IF NOT EXISTS broker_jobs_client_request_idx
    ON broker_jobs (request_id)
    WHERE job_kind = 'client_answer_v1';

COMMIT;

-- === ROLLBACK ===
-- Inline rollback per W42 lint requirement; statements omitted verbatim
-- because the guardrails hook blocks destructive SQL tokens even in
-- comments (same convention as migration 270/283). To revert, in a
-- transaction, in reverse order: drop broker_jobs_client_request_idx; drop
-- the two CHECK constraints added in step 3-4
-- (broker_jobs_kind_identifiers_check, broker_jobs_surface_check,
-- broker_jobs_job_kind_check); drop the five columns added in step 2
-- (preferred_seat_pool, output_schema_version, request_id, surface,
-- job_kind); re-add NOT NULL to thread_epoch/thread_id/outbox_id (only
-- safe if zero rows have job_kind = 'client_answer_v1' at that point — a
-- live client-bot job row would violate the restored NOT NULL and abort
-- the migration; drain/delete such rows first, deliberately not automated
-- here). Purely additive forward DDL: no existing WA-outbox row's data is
-- rewritten by this migration, so the rollback's only real risk is losing
-- any in-flight client-bot broker_jobs rows, which is the correct
-- direction to fail (client-bot codex leg ships dark, CLIENT_BOT_
-- CODEX_BROKER_ENABLED default False — there should be none in a rollback
-- scenario on a machine that never armed it).
