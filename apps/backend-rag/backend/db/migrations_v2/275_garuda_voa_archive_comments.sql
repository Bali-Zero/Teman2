-- ============================================================
-- 275_garuda_voa_archive_comments.sql
-- Forward metadata correction for the retired GARUDA VOA funnel.
--
-- Migration 261 may already be recorded with its full-file checksum, so its
-- historical comments must remain byte-for-byte unchanged. This migration
-- updates the database catalog without rewriting that applied artifact.
-- ============================================================

COMMENT ON TABLE garuda_voa_checks IS
    'Historical GARUDA VOA verdict archive. Owner-only, read-only access; no public writer exists.';

COMMENT ON COLUMN garuda_voa_checks.hash IS
    'Historical archive row identifier used for lookup. It is not a credential, authentication token, or authorization mechanism; owner authentication is enforced separately.';

COMMENT ON COLUMN garuda_voa_checks.decline_reasons IS
    'Historical engine-internal English audit prose, parallel to decline_codes. Owner audit only; never serialized by the archive GET.';

COMMENT ON COLUMN garuda_voa_checks.decline_codes IS
    'Historical machine-code audit array, parallel to decline_reasons. The owner archive GET validates entries against DeclineCode and deduplicates them in stored order; unknown entries fail closed.';

COMMENT ON COLUMN garuda_voa_checks.published_filing_deadline IS
    'Historical D-7 Ngurah Rai filing deadline. The only Safe Clock checkpoint exposed by the owner archive.';

-- === ROLLBACK ===
COMMENT ON TABLE garuda_voa_checks IS
    'GARUDA VOA public request funnel result store. One row = one shareable /visa/voa/<hash> page. No PII columns by design -- see file header.';

COMMENT ON COLUMN garuda_voa_checks.hash IS
    '16-char URL-safe hash (new_visa_hash(), reused from visa_check). Public identifier in /visa/voa/<hash>.';

COMMENT ON COLUMN garuda_voa_checks.decline_reasons IS
    'Engine-internal English audit prose, parallel to decline_codes. May name an internal checkpoint (e.g. D-10) -- server-side/audit only, never serialized to a visitor.';

COMMENT ON COLUMN garuda_voa_checks.decline_codes IS
    'Stable neutral machine codes (services.garuda_flow.eligibility.DeclineCode), parallel to decline_reasons. The ONLY decline-reason form ever returned on the wire (VoaResponse.reason_codes).';

COMMENT ON COLUMN garuda_voa_checks.published_filing_deadline IS
    'D-7 Ngurah Rai filing deadline -- the ONLY Safe Clock checkpoint ever shown to a visitor (charter, spec Sec6).';
