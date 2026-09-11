-- 297_wa_outbox_fall_off_reason_finalize_sub_reasons.sql
--
-- THE DEFECT (2026-08-28, measured live): migration 291 ended this exact
-- blindness for the package-builder leg's `unbuildable:*` head and left
-- its twin untouched one row down in the same map. `finalize:<reason>`
-- carries a SECOND, genuinely distinct signal after its colon — WHICH of
-- wa_finalize.py's eleven DEFECT branches refused to let the text leave —
-- and `_normalize_fall_off_reason` collapses all of them into the single
-- stored value "finalize_defect" by mapping the head alone.
--
-- Cost, measured: `wa_outbox` row 363 (thread 394, 2026-08-28T21:43:52Z).
-- The codex broker generated an answer THREE times, every job
-- `outcome = consumed_ok` with a null `error_class` and 9711/10137/8521 ms
-- of real execution — and the finalize stage discarded all three. The row
-- recorded "finalize_defect" three times, which names the STAGE and hides
-- the CAUSE: a pricing veto against the frozen package, an oversized
-- output, a monologue leak and a secret-egress hit are four different
-- defects with four different cures, and this column could not tell them
-- apart. The per-attempt `defect_reason` existed only in an app log line,
-- and Fly retains logs for roughly 60 seconds — by the time the incident
-- was investigated the window had closed, exactly as it had for row 348
-- the previous morning (see migration 291's own header).
--
-- THE CURE: eleven new category codes, one per known `defect_reason`, so
-- the branches stop colliding on write. "finalize_defect" itself stays in
-- the allowed set (widened, not replaced) as the fallback bucket for a
-- future, not-yet-catalogued reason — the same "unrecognised -> generic
-- bucket, never raise" discipline 290 and 291 already use.
--
-- One value is deliberately NOT a faithful echo of its source string:
-- `secret_egress:<pattern-name>` is stored as the bare
-- "finalize_secret_egress". The suffix names which scanner pattern hit,
-- and this column is read by dashboards and pasted into reports — the
-- scanner's own docstring keeps the matched content out of logs for the
-- same reason, and an unbounded suffix would also break the closed
-- vocabulary a CHECK constraint exists to enforce.
--
-- CONVERGE, not create: DROP CONSTRAINT IF EXISTS then re-ADD the widened
-- CHECK, mirroring 290 and 291 exactly — a CREATE-IF-NOT-EXISTS here
-- would be a no-op on a DB that already carries the narrower constraint,
-- leaving the suite green over a migration that never ran.
--
-- Ownership: wa_outbox carries no OWNER/GRANT statement anywhere in
-- migrations_v2, and 290/291 already ran this exact
-- DROP CONSTRAINT IF EXISTS / ADD CONSTRAINT pair against the same table
-- under the same runtime role, cleanly. No role/grant statement is needed.
--
-- SCOPE: this migration widens a CHECK constraint and nothing else. It
-- does NOT address the second defect the same incident exposed — that
-- `_coalesce_thread_bursts` silently supersedes a pending row which
-- already has real generated content behind it, with no apology and no
-- alert. That one is a behaviour change and belongs in its own PR.

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
        'finalize_internal_monologue_leak',
        'finalize_pricing_outside_package',
        'finalize_secret_egress',
        'finalize_empty_rag_answer',
        'finalize_persona_escalate_marker',
        'finalize_empty_after_escalate_strip',
        'finalize_workflow_only_output',
        'finalize_empty_after_channel_format',
        'finalize_oversized_output',
        'finalize_rag_abstain',
        'finalize_blank_send_text',
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
