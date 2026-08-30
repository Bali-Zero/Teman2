-- 299_wa_outbox_fall_off_reason_price_split_fee.sql
--
-- THE DEFECT (2026-08-30, measured live, on code already carrying #5293/#5295):
-- `wa_outbox` row 379 (thread of cycle-357 case q1, 2026-08-30T17:54:35Z)
-- answered an Investor-KITAS price question with:
--
--   "biaya layanan kami: offshore Rp17.000.000, [...]
--    PNBP pemerintah Rp9.500.000 untuk 2 tahun"
--
-- a government levy presented to the client as a SEPARATE payable amount
-- beside the Bali Zero price. Zero's ruling of 2026-07-17 is one
-- all-inclusive client-facing price, never a PNBP-vs-fee split. The
-- existing `finalize_pricing_outside_package` veto could not catch this:
-- it proves every amount is CONSISTENT with the frozen package's sources,
-- never that the answer is COMPLIANT with the single-price rule — and the
-- Rp9.500.000 figure was laundered in from a retrieved chunk, which that
-- veto accepts by design (see its own docstring's declared residual).
--
-- THE CURE (same PR, `wa_finalize.py::price_split_offenders`): a second,
-- independent veto that fires when a government-fee marker (PNBP /
-- government fee / biaya pemerintah / state fee) carries its own currency
-- amount in the same sentence, unless that sentence also states the levy
-- is included in the price. Runs unconditionally on the codex leg's
-- finalize path, not only when price_sources were supplied.
--
-- CONVERGE, not create: DROP CONSTRAINT IF EXISTS then re-ADD the widened
-- CHECK, mirroring 290/291/297 exactly — a CREATE-IF-NOT-EXISTS here would
-- be a no-op on a DB that already carries the narrower constraint.
--
-- Ownership: wa_outbox carries no OWNER/GRANT statement anywhere in
-- migrations_v2, and 290/291/297 already ran this exact DROP/ADD pair
-- against the same table under the same runtime role, cleanly.

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
        'finalize_price_split_fee',
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
