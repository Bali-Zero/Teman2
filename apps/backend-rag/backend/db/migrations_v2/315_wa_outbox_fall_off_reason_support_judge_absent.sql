-- 315_wa_outbox_fall_off_reason_support_judge_absent.sql
--
-- THE DEFECT this widening closes (B2.4 PR-2, design B2-4-design.md §1.3,
-- ruling I96): the support judge moved from the Fly-side package builder
-- (in-container, rejected by I96) to the wa-codex-daemon on Pro, judging
-- the CLAIMED job with a real Codex seat BEFORE generating. The verdict
-- now travels back inside an authenticated completion envelope
-- (`wa_completion_envelope.py`) instead of a value the builder computed
-- itself — which means "no verdict travelled back" (an absent/invalid/
-- MAC-mismatched envelope, OR the daemon's own judge unable to rule) is a
-- NEW, distinct outcome this column has never had a code for. Ruling
-- I96-5 names it explicitly: an absent judge must be LOUD, via a durable,
-- SQL-countable counter — not silently folded into an existing bucket
-- like "wait_failed" or "unknown", which would make the fail-closed gate
-- itself invisible to any dashboard reading this column.
--
-- THE CURE: one new category code, `support_judge_absent`, covering BOTH
-- of `wa_codex_leg.py`'s two raise sites for this outcome — a decoded-
-- envelope failure (`no_verdict`: absent, invalid, MAC mismatch, hash
-- mismatch, including a REATTACHED leg's envelope for a different
-- package_hash) and a typed broker wait failure with
-- `error_class = "support_judge_unavailable"` (`unavailable`: the
-- daemon's own judge could not rule at all). The two details are
-- DELIBERATELY collapsed into the SAME durable value (I96-5: "the durable
-- column value is the SQL-countable COUNTER") — the sub-detail lives only
-- in the ERROR log next to each raise site, mirroring how 291/297 keep a
-- richer detail out of this column when it would otherwise need an
-- unbounded suffix (the `secret_egress:<pattern-name>` precedent).
--
-- CONVERGE, not create: DROP CONSTRAINT IF EXISTS then re-ADD the widened
-- CHECK, mirroring 290/291/297 exactly — a CREATE-IF-NOT-EXISTS here
-- would be a no-op on a DB that already carries the narrower constraint,
-- leaving the suite green over a migration that never ran.
--
-- Ownership: wa_outbox carries no OWNER/GRANT statement anywhere in
-- migrations_v2, and 290/291/297 already ran this exact
-- DROP CONSTRAINT IF EXISTS / ADD CONSTRAINT pair against the same table
-- under the same runtime role, cleanly. No role/grant statement is needed.

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
        'support_judge_absent',
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
