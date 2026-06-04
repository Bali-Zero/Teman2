-- 213_intake_review_lease.sql — FASE 5A review-queue claim/lease columns (LOCAL Pro DB only)
-- Adds the reviewer-lease primitives to document_routing_proposal so the HITL
-- review-queue API (5A) can atomically "claim" a proposal for one reviewer.
-- Panel P0#5 (06-fase5-hitl-writer-design §8): claim with TTL alone is a race —
-- approve/reject/patch MUST also carry an opaque claim_token verified on every
-- mutation. 5A introduces the columns; the token is enforced here on claim/release
-- and (FASE 5C) on approve/reject/patch.
-- READ-ONLY w.r.t. CRM: this migration ONLY touches document_routing_proposal.
-- PII 100% locale (Law 2 / UU-PDP): MAI applicare su Fly. Solo nuzantara_dev @127.0.0.1:5432.
-- === FORWARD ===

ALTER TABLE document_routing_proposal
    ADD COLUMN IF NOT EXISTS lease_owner      TEXT,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS claim_token      UUID,
    ADD COLUMN IF NOT EXISTS claimed_at       TIMESTAMPTZ;

-- Fast scan of currently-claimed proposals (lease reaper / queue filter).
CREATE INDEX IF NOT EXISTS idx_rp_lease
    ON document_routing_proposal (lease_expires_at)
    WHERE status = 'review_claimed';

COMMENT ON COLUMN document_routing_proposal.lease_owner IS
    'Email of the reviewer who claimed this proposal (FASE 5A HITL). NULL = unclaimed.';
COMMENT ON COLUMN document_routing_proposal.lease_expires_at IS
    'TTL of the reviewer claim. Past this, the proposal is reclaimable (lease reaper / claim steals expired).';
COMMENT ON COLUMN document_routing_proposal.claim_token IS
    'Opaque per-claim token (P0#5). FASE 5C approve/reject/patch MUST present this exact token + a non-expired lease.';

-- === ROLLBACK ===
-- DROP INDEX IF EXISTS idx_rp_lease;
-- ALTER TABLE document_routing_proposal
--     DROP COLUMN IF EXISTS claimed_at,
--     DROP COLUMN IF EXISTS claim_token,
--     DROP COLUMN IF EXISTS lease_expires_at,
--     DROP COLUMN IF EXISTS lease_owner;
