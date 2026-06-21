-- Migration 234: document_routing_proposal — allow status='quarantine' + 'auto_routed' + 'duplicate'.
--
-- Three review-load-reduction levers (research/operations/2026-06-21-intake-review-time-reduction.md):
--
--   * 'quarantine' (LEVA 1 — noise pre-filter): a proposal whose document is
--     noise — doc_type='unknown' AND OCR produced effectively no legible text
--     (the empty-OCR class that poisoned 782 rows in the 2026-06-12 backlog run).
--     It is parked OUT of the main /review feed (reviewers never tap through it)
--     but is NOT deleted: consultable via the quarantine endpoint, recoverable to
--     review_pending if a real document was mis-binned. NON-terminal.
--
--   * 'auto_routed' (LEVA 2 — auto-attach double-concordant): a proposal the
--     system committed to the CRM without a human, because the doc carried a
--     strong identifier (passport/NPWP/NIB) resolving to ONE client AND the
--     sender phone concorded with that SAME client (double signal → subject
--     confirmed, resolves sender≠subject). Distinct from human 'routed' so the
--     audit trail can tell apart machine vs human commits + drive the 48h undo.
--     TERMINAL (like 'routed'), reversible via rollback → 'review_pending'.
--
--   * 'duplicate' (LEVA 3 — dedup wall): the resolved client ALREADY carries a
--     document of this type on their kita profile, so this is a re-arrival of
--     something already filed. It must NOT re-enter /review for a human to
--     re-catalog (the 3×sk_kemenkumham-for-one-client class). Parked OUT of the
--     feed, consultable for audit. NON-terminal (recoverable like quarantine if
--     a genuine second copy is wanted). Armed by INTAKE_DEDUP_WALL_ENABLED.
--
-- Same DROP+ADD CHECK pattern as migration 226 (cheap metadata swap; every
-- existing row keeps a value that is still in the new set, so the ADD validates
-- with no row rewrite).
--
-- On the Pro apply manually like 212-233:
--   psql postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev \
--     -f apps/backend-rag/backend/db/migrations_v2/234_routing_proposal_quarantine_autorouted.sql
-- === FORWARD ===

ALTER TABLE document_routing_proposal DROP CONSTRAINT IF EXISTS chk_rp_status;
ALTER TABLE document_routing_proposal ADD CONSTRAINT chk_rp_status CHECK (status IN
    ('review_pending','review_claimed','routed','rejected','dead','superseded',
     'quarantine','auto_routed','duplicate'));

COMMENT ON CONSTRAINT chk_rp_status ON document_routing_proposal IS
    'Proposal lifecycle (migration 234): review states + terminal routed/auto_routed/rejected/dead + superseded (re-pipelined) + quarantine (noise parked) + duplicate (LEVA-3 dedup wall: client already has this doc_type on profile, parked out of /review).';

-- === ROLLBACK ===
-- (Only safe when no rows carry status='quarantine' or 'auto_routed'.)
-- ALTER TABLE document_routing_proposal DROP CONSTRAINT IF EXISTS chk_rp_status;
-- ALTER TABLE document_routing_proposal ADD CONSTRAINT chk_rp_status CHECK (status IN
--     ('review_pending','review_claimed','routed','rejected','dead','superseded'));
