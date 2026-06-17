-- 224_intake_flow_v2.sql — Intake flow v2: honest queue statuses + reject audit outcome.
--
-- Fly-safe by design: 212-219 auto-ran on Fly too (empty intake tables exist there), so
-- this file is PURE DDL on tables guaranteed to exist on both DBs. The DATA side of the
-- v2 cutover (legacy-status remap + one-time expired-claim reap) deliberately does NOT
-- live here: the intake worker performs it at boot (services/intake/worker.py
-- ``remap_legacy_statuses`` — idempotent, local-only, no apply-ordering footgun).
-- On the Pro apply manually like 212-219:
--   psql postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev \
--     -f apps/backend-rag/backend/db/migrations_v2/224_intake_flow_v2.sql
--
-- WHY (worker state-machine fix, see services/intake/worker.py):
--   The v1 machine overloaded status as BOTH stage-cursor AND claim-marker: claiming a
--   job flipped status -> 'processing', destroying the stage position. A crash mid-stage
--   re-entered the machine at the WRONG stage (the "OCR done but status never advanced"
--   backlog scar). v2 makes the claim lease-only (status untouched) and renames statuses
--   to honest "what is DONE" names. The no-op OCR passthrough stage is dropped (classify
--   already performs OCR), so 5 stages become 4:
--
--     v1: pending -classify-> processing -ocr-> ocr -extract-> classified
--           -validate-> extracted -route-> done
--     v2: pending -classify(+OCR)-> ocr_done -extract-> extracted
--           -validate-> validated -route-> done
--
--   The CHECK below accepts BOTH name sets (permissive union) so legacy rows stay valid
--   until the worker's boot-time remap retires them: processing/ocr -> ocr_done,
--   classified -> extracted, extracted -> validated. A later cleanup migration can
--   tighten the constraint once no legacy rows exist anywhere.
-- === FORWARD ===

-- 1. Status CHECK: permissive union of v1 + v2 names (worker boot-remap retires v1).
ALTER TABLE intake_queue DROP CONSTRAINT IF EXISTS chk_iq_status;
ALTER TABLE intake_queue ADD CONSTRAINT chk_iq_status CHECK (status IN
    ('pending','ocr_done','extracted','validated',
     'processing','ocr','classified',
     'review_pending','review_claimed','routed','rejected','done','dead','duplicate'));

-- 2. Claimable-scan index over the v2 claimable set (legacy rows are remapped at worker
--    boot before any claim happens, so they never need this index).
DROP INDEX IF EXISTS idx_iq_claimable;
CREATE INDEX idx_iq_claimable
    ON intake_queue (next_visible_at, id)
    WHERE status IN ('pending','ocr_done','extracted','validated');

-- 3. Reject forensic audit: allow outcome='rejected' in intake_commit_audit so
--    reject_review can write a forensic row (who rejected what, and why).
ALTER TABLE intake_commit_audit DROP CONSTRAINT IF EXISTS chk_ica_outcome;
ALTER TABLE intake_commit_audit ADD CONSTRAINT chk_ica_outcome CHECK (outcome IN
    ('committed','dry_run','blocked','failed','rolled_back','rejected'));

COMMENT ON CONSTRAINT chk_iq_status ON intake_queue IS
    'v2 stage machine (migration 224): status = what is DONE; claim is lease-only (worker.py). Permissive union with v1 names until boot-remap retires them.';

-- === ROLLBACK ===
-- ALTER TABLE intake_queue DROP CONSTRAINT IF EXISTS chk_iq_status;
-- ALTER TABLE intake_queue ADD CONSTRAINT chk_iq_status CHECK (status IN
--     ('pending','processing','ocr','classified','extracted','ocr_done','validated',
--      'review_pending','review_claimed','routed','rejected','done','dead','duplicate'));
-- DROP INDEX IF EXISTS idx_iq_claimable;
-- CREATE INDEX idx_iq_claimable
--     ON intake_queue (next_visible_at, id)
--     WHERE status IN ('pending','processing','ocr','classified','extracted');
-- ALTER TABLE intake_commit_audit DROP CONSTRAINT IF EXISTS chk_ica_outcome;
-- ALTER TABLE intake_commit_audit ADD CONSTRAINT chk_ica_outcome CHECK (outcome IN
--     ('committed','dry_run','blocked','failed','rolled_back'));
