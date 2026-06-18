-- Migration 226: document_routing_proposal — allow status='superseded'.
--
-- Intake catalog v2 retroactive reprocess: when a review_pending proposal is
-- known-bad (doc_type=unknown / entity NO_MATCH) and its queue row is reset for
-- a fresh pipeline pass (bumped pipeline_version → new routing_key → NEW
-- proposal row), the OLD proposal must leave the review feed without lying:
-- it was neither 'rejected' (a human decision) nor 'dead' (a pipeline failure).
-- 'superseded' = "replaced by a newer proposal for the same queue row".
--
-- Same DROP+ADD CHECK pattern as migration 224 (chk_iq_status): cheap metadata
-- swap, validates existing rows (all current values remain in the new set).
--
-- On the Pro apply manually like 212-225:
--   psql postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev \
--     -f apps/backend-rag/backend/db/migrations_v2/226_routing_proposal_superseded.sql
-- === FORWARD ===

ALTER TABLE document_routing_proposal DROP CONSTRAINT IF EXISTS chk_rp_status;
ALTER TABLE document_routing_proposal ADD CONSTRAINT chk_rp_status CHECK (status IN
    ('review_pending','review_claimed','routed','rejected','dead','superseded'));

COMMENT ON CONSTRAINT chk_rp_status ON document_routing_proposal IS
    'Proposal lifecycle (migration 226): review states + terminal routed/rejected/dead + superseded (replaced by a re-pipelined proposal for the same queue row).';

-- === ROLLBACK ===
-- (Only safe when no rows carry status='superseded'.)
-- ALTER TABLE document_routing_proposal DROP CONSTRAINT IF EXISTS chk_rp_status;
-- ALTER TABLE document_routing_proposal ADD CONSTRAINT chk_rp_status CHECK (status IN
--     ('review_pending','review_claimed','routed','rejected','dead'));
