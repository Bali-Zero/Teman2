-- 291_wa_outbox_fall_off_reason_unbuildable_sub_reasons.sql
--
-- THE DEFECT (2026-08-27/28, measured live): migration 290 gave every
-- non-served codex-leg outcome a durable, per-row reason in
-- wa_outbox.generation_fall_off_reason — but `_normalize_fall_off_reason`
-- (wa_codex_leg.py) collapses the package-builder leg's THREE genuinely
-- different failures — `unbuildable:greeting_domain`,
-- `unbuildable:no_collections`, `unbuildable:dlp_error`
-- (wa_package_builder.py's PackageUnbuildable call sites) — into the
-- single stored value "package_unbuildable" by splitting on the first ':'
-- and mapping the head alone. The sub-reason survived only in an app log
-- line (wa_package.py's `"wa_package: unbuildable reason=%s"`), and Fly
-- retains logs for roughly 60 seconds. Cost, measured 2026-08-27:
-- `wa_outbox` row 348 fell off with "package_unbuildable" at 05:28:34Z; a
-- real client got an apology instead of an answer, and two separate
-- investigations had to reason from source structure because the
-- sub-reason was already gone from the logs both times they looked. This
-- is the same blindness 290 cured, one level down.
--
-- THE CURE: three new category codes, one per known sub-reason, so the
-- three failures stop colliding on write. "package_unbuildable" itself
-- stays in the allowed set (widened, not replaced) as the fallback bucket
-- for a future, not-yet-catalogued PackageUnbuildable reason — same
-- "unrecognised -> generic bucket, never raise" discipline 290's own
-- "unknown" catch-all already uses one level up. This migration ONLY
-- widens the CHECK constraint; the columns it constrains
-- (generation_fall_off_reason, generation_fall_off_at) already exist
-- (migration 290) and are untouched here.
--
-- CONVERGE, not create: DROP CONSTRAINT IF EXISTS then re-ADD the widened
-- CHECK, mirroring 290's own shape exactly — a CREATE-IF-NOT-EXISTS here
-- would be a no-op on a DB that already has the narrower constraint,
-- which would leave the suite green over a migration that never actually
-- ran (this repo's own W-class scar for audit-adjacent DDL: see
-- cicatrix-scars.md, "an audit trigger can veto the transaction it
-- observes and CREATE TABLE IF NOT EXISTS hides it" and the companion
-- ledger-owned-DDL scar — both are instances of the same "IF NOT EXISTS
-- masks a stale constraint" failure mode this migration deliberately does
-- not repeat).
--
-- Ownership check (this repo's own scar: a DDL against an object owned by
-- a different role can abort the whole deploy, invisibly to CI):
-- wa_outbox carries no OWNER/GRANT statement anywhere in migrations_v2 —
-- grep-verified across every migration that touches it (206, 260, 270,
-- 283, 290, 296) — and migration 290 already ran this exact
-- DROP CONSTRAINT IF EXISTS / ADD CONSTRAINT pair against the same table,
-- under the same runtime role, cleanly. No role/grant statement is needed
-- here.

ALTER TABLE wa_outbox
    DROP CONSTRAINT IF EXISTS wa_outbox_generation_fall_off_reason_check;
ALTER TABLE wa_outbox
    ADD CONSTRAINT wa_outbox_generation_fall_off_reason_check
    CHECK (generation_fall_off_reason IS NULL OR generation_fall_off_reason IN (
        'provider_not_codex',
        'standing_autoreply_disabled',
        'standing_no_customer_message',
        'window_margin',
        'package_build_error',
        'package_unbuildable',
        'package_unbuildable_greeting_domain',
        'package_unbuildable_no_collections',
        'package_unbuildable_dlp_error',
        'build_contract_break',
        'offer_acquire_error',
        'offer_uncertain',
        'offer_refused',
        'offer_contract_break',
        'wait_error',
        'wait_failed',
        'stand_down_drift',
        'stand_down_fence_lost',
        'post_completion_error',
        'consume_lost',
        'finalize_defect',
        'internal_error',
        'unknown'
    ));

-- === ROLLBACK ===

ALTER TABLE wa_outbox
    DROP CONSTRAINT IF EXISTS wa_outbox_generation_fall_off_reason_check;
ALTER TABLE wa_outbox
    ADD CONSTRAINT wa_outbox_generation_fall_off_reason_check
    CHECK (generation_fall_off_reason IS NULL OR generation_fall_off_reason IN (
        'provider_not_codex',
        'standing_autoreply_disabled',
        'standing_no_customer_message',
        'window_margin',
        'package_build_error',
        'package_unbuildable',
        'build_contract_break',
        'offer_acquire_error',
        'offer_uncertain',
        'offer_refused',
        'offer_contract_break',
        'wait_error',
        'wait_failed',
        'stand_down_drift',
        'stand_down_fence_lost',
        'post_completion_error',
        'consume_lost',
        'finalize_defect',
        'internal_error',
        'unknown'
    ));
