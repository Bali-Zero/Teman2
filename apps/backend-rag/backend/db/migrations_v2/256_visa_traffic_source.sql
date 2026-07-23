-- Migration 256: Visa Oracle SHADOW traffic-source marker
--
-- Migration 255's evidence substrate cannot distinguish real end-user
-- traffic from synthetic corpus traffic: a row written by the live SHADOW
-- path and a row written by the gold-corpus replay driver look identical in
-- visa_decisions.  Without that distinction the G-a volume/breadth gate is
-- gameable -- a synthetic corpus could manufacture the 1,000 distinct
-- requests / 7 consecutive days / 30 visa codes the gate demands, and the
-- collector would count them as production adoption.  Fable final-gate
-- deltas 1-2 (binding, 2026-07-23) therefore require a traffic_source
-- marker so the evidence collector can split G-a into G-a-vol (real traffic
-- only) and G-a-breadth (synthetic corpus, honestly labeled) and so a gate
-- auditor can verify the split from the audit log alone.
--
-- Precedent: migration 187 (probe-sandbox isolation) established the
-- storage-level isolation-flag pattern for synthetic data.  Unlike 187's
-- NOT NULL DEFAULT false boolean, this marker is deliberately NULLABLE:
-- rows predating this migration carry NULL, which means "unknown
-- provenance" and is reported as `legacy` by the evidence collector,
-- counted toward NEITHER gate.  NULLs are never backfilled with guesses --
-- legacy rows keep failing closed exactly as they did under 255.
--
-- The CHECK constraint is the storage-level barrier: writers may only ever
-- label a row 'real', 'synthetic_gold', or 'synthetic_driver'.  As of this
-- migration no writer sets the column yet; labeling lands with the
-- synthetic-corpus drivers and the read-path wiring in later PRs, and
-- until then every row stays legacy (fail-closed).
--
-- The partial index mirrors 255's: the evidence collector is the only
-- reader of this column and it always filters MATCH/SHADOW, so the index
-- covers exactly that slice, ordered by created_at for windowed scans.
--
-- This migration does not change VISA_ENGINE_MATCH_MODE and cannot arm ENFORCE.

ALTER TABLE public.visa_decisions
    ADD COLUMN traffic_source TEXT
        CHECK (
            traffic_source IS NULL
            OR traffic_source IN (
                'real',
                'synthetic_gold',
                'synthetic_driver'
            )
        );

CREATE INDEX idx_visa_decisions_shadow_traffic_source
    ON public.visa_decisions (traffic_source, created_at)
    WHERE engine_surface = 'MATCH' AND engine_mode = 'SHADOW';

-- === ROLLBACK ===
DROP INDEX IF EXISTS public.idx_visa_decisions_shadow_traffic_source;

ALTER TABLE IF EXISTS public.visa_decisions
    DROP COLUMN IF EXISTS traffic_source;
