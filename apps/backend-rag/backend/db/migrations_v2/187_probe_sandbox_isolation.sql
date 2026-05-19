-- Migration 187: Probe sandbox isolation (Phase C, perfect-production plan 2026-05-20)
--
-- Purpose: hard barrier between synthetic probe data and production
-- intel_items rows. Panel critique (Gemini + Codex 2/2 convergent) rejected
-- flag-only isolation as insufficient — `is_probe_sandbox=true` boolean
-- alone does not propagate to NotebookLM, Canva, embeddings, audit log,
-- dashboards. Migration 187 enforces tenant separation at the storage
-- layer via CHECK constraint + partial index.
--
-- Design doc: research/operations/2026-05-20-probe-sandbox-setup.md
-- Probe scripts: scripts/probes/intel_lake_e2e_probe.py
--
-- Invariants enforced (CHECK constraint):
--   - Rows with producer_name LIKE 'probe-sandbox-%' MUST have
--     is_probe_sandbox = true.
--   - Rows with is_probe_sandbox = true MUST have
--     producer_name LIKE 'probe-sandbox-%'.
--
-- Production query optimization:
--   - Partial index idx_intel_items_production excludes sandbox rows.
--   - Dashboard queries that forget WHERE NOT is_probe_sandbox will be
--     physically slow to scan sandbox rows — naturally enforces correct
--     query patterns via performance, not just data correctness.
--
-- Backward compatible: existing rows default to is_probe_sandbox=false.

BEGIN;

-- 1. Add column (default false — production semantics preserved)
ALTER TABLE intel_items
    ADD COLUMN IF NOT EXISTS is_probe_sandbox BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN intel_items.is_probe_sandbox IS
'Phase C 2026-05-20: hard barrier flag for synthetic probe data. MUST be true iff producer_name LIKE ''probe-sandbox-%''. Enforced via CHECK constraint chk_probe_sandbox_consistency. See research/operations/2026-05-20-probe-sandbox-setup.md';

-- 2. CHECK constraint — STRICT prefix-only barrier
-- Panel review 2026-05-20 (DeepSeek BLOCKER finding):
-- The previous `LIKE '%probe-sandbox%'` could be matched by a legitimate
-- producer URL containing the substring (e.g., a real article with slug
-- "probe-sandbox-attack-explained"). That would corrupt isolation.
-- Fix: anchor to the dedicated host `probe-sandbox.example.test` reserved
-- by RFC 2606 (.test TLD never resolves on the public internet, so no
-- real producer can ever legitimately use this hostname).
-- Probe scripts MUST use canonical_url starting with this exact prefix.
ALTER TABLE intel_items
    ADD CONSTRAINT chk_probe_sandbox_url
    CHECK (
        is_probe_sandbox = false
        OR canonical_url LIKE 'https://probe-sandbox.example.test/%'
    );

-- 3. Partial index for production-only queries
-- Dashboard / aggregation / audit queries SHOULD include `WHERE NOT is_probe_sandbox`.
-- This index makes the production filter free; sandbox rows are physically
-- absent from the index plan.
CREATE INDEX IF NOT EXISTS idx_intel_items_production
    ON intel_items(first_seen_at DESC)
    WHERE is_probe_sandbox = false;

-- 4. Partial index for sandbox-only queries (cleanup, debugging)
CREATE INDEX IF NOT EXISTS idx_intel_items_sandbox
    ON intel_items(first_seen_at DESC)
    WHERE is_probe_sandbox = true;

COMMIT;

-- === ROLLBACK ===
-- Drop indexes + constraint + column. Sandbox rows (if any exist) remain
-- in intel_items but lose the flag — they will appear in production
-- dashboards until manually deleted. Run cleanup before rollback:
--
--   DELETE FROM intel_items WHERE is_probe_sandbox = true;

BEGIN;

DROP INDEX IF EXISTS idx_intel_items_sandbox;
DROP INDEX IF EXISTS idx_intel_items_production;
ALTER TABLE intel_items DROP CONSTRAINT IF EXISTS chk_probe_sandbox_url;
ALTER TABLE intel_items DROP COLUMN IF EXISTS is_probe_sandbox;

COMMIT;
