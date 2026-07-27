-- ============================================================
-- 261_garuda_voa_checks.sql
-- Persistence for the GARUDA VOA public request funnel (Slice A).
-- Date: 2026-07-27
--
-- One row = one shareable /visa/voa/<hash> page, same convention as
-- 124_visa_checks.sql (Visa Check Match branch): the verdict (decision +
-- Safe Clock dates) is computed once at submission and FROZEN -- a shared
-- result link must not flip ACCEPT->DECLINE just because someone opens it
-- later. Append-only for result rows; edits only to view_count/share_count.
--
-- PII boundary -- load-bearing (BUILD-SPEC-SLICE-A-2026-07-27.md Sec3): this
-- table carries ONLY enum / date / boolean / ISO-code columns. No name, no
-- passport number, no email, no phone. This is precisely why the funnel
-- (backend/app/routers/garuda_voa.py) can sit on an unauthenticated route
-- registered in backend/app/auth/public_endpoints.py -- the shape of this
-- table IS the safety argument, not a flag. Any future column MUST keep
-- this property or the route can no longer be public.
--
-- Client-facing boundary: this table does NOT store the D-14/D-10/D-3/D-1
-- internal Bali Zero checkpoints -- they are pure deterministic offsets of
-- expiry_date (see services/garuda_flow/safe_clock.py::compute_stay) and
-- can be recomputed on demand from entry_date/expiry_date if a future
-- staff-ops surface needs them. Only published_filing_deadline (D-7, the
-- one checkpoint a visitor may ever be shown) is persisted directly.
--
-- Same boundary for decline REASONS (amended 2026-07-27, cross-family
-- review): decline_reasons stores the engine's English audit prose
-- verbatim for the case sheet -- it can name an internal checkpoint (e.g.
-- "below D-10 pilot threshold") and must stay server-side only.
-- decline_codes stores the parallel array of stable, neutral, wire-safe
-- machine codes (services/garuda_flow/eligibility.py::DeclineCode) -- this
-- is the ONLY decline-reason form backend/app/routers/garuda_voa.py may
-- ever serialize to a visitor (as VoaResponse.reason_codes).
--
-- Companion:
--   backend/services/garuda_flow/ -- constants, eligibility, safe_clock, intake, repository
--   backend/app/routers/garuda_voa.py -- POST /api/visa/voa, GET /api/visa/voa/{hash}
-- ============================================================

CREATE TABLE IF NOT EXISTS garuda_voa_checks (
    hash                       VARCHAR(20) PRIMARY KEY,
    created_at                 TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    view_count                 INT NOT NULL DEFAULT 0,
    share_count                INT NOT NULL DEFAULT 0,

    -- Intake (spec Sec5 -- the WHOLE PII contract; enum/date/bool/ISO-code only)
    case_type                  VARCHAR(16) NOT NULL
                               CHECK (case_type IN ('issuance', 'extension')),
    nationality                VARCHAR(3)  NOT NULL,
    entry_date                 DATE NOT NULL,
    passport_expiry_date       DATE NOT NULL,
    voa_expiry_date            DATE,               -- extension cases only
    extension_already_used     BOOLEAN NOT NULL DEFAULT FALSE,
    purpose                    VARCHAR(24) NOT NULL,
    travellers                 INT NOT NULL,
    self_pay                   BOOLEAN NOT NULL,

    -- Verdict (frozen at submission time)
    decision                   VARCHAR(8) NOT NULL
                               CHECK (decision IN ('ACCEPT', 'DECLINE')),
    decline_reasons            JSONB NOT NULL DEFAULT '[]'::jsonb,
    decline_codes              JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Safe Clock -- client-facing surface only (see boundary note above)
    expiry_date                DATE NOT NULL,
    last_legal_day             DATE NOT NULL,
    expiry_is_estimated        BOOLEAN NOT NULL,
    published_filing_deadline  DATE NOT NULL,

    -- Issuance-only submission-window gate (owner ruling 2026-07-27,
    -- services/garuda_flow/operating_calendar.py). Bali Zero's OWN
    -- submit-by commitment, never an immigration deadline. NULL for every
    -- extension row (untouched by this rule) and for an issuance row whose
    -- entry_date fell past operating_calendar.COVERAGE_END (fail-closed).
    submit_by_date              DATE,

    -- Pricing (server-side, PricingTool SSOT -- never hardcoded)
    price_idr                  BIGINT,
    price_source               VARCHAR(64)
);

COMMENT ON TABLE garuda_voa_checks IS
    'GARUDA VOA public request funnel result store. One row = one shareable /visa/voa/<hash> page. No PII columns by design -- see file header.';

COMMENT ON COLUMN garuda_voa_checks.hash IS
    '16-char URL-safe hash (new_visa_hash(), reused from visa_check). Public identifier in /visa/voa/<hash>.';

COMMENT ON COLUMN garuda_voa_checks.decision IS
    'Pilot intake screen verdict (services.garuda_flow.eligibility.screen), frozen at submission time.';

COMMENT ON COLUMN garuda_voa_checks.decline_reasons IS
    'Engine-internal English audit prose, parallel to decline_codes. May name an internal checkpoint (e.g. D-10) -- server-side/audit only, never serialized to a visitor.';

COMMENT ON COLUMN garuda_voa_checks.decline_codes IS
    'Stable neutral machine codes (services.garuda_flow.eligibility.DeclineCode), parallel to decline_reasons. The ONLY decline-reason form ever returned on the wire (VoaResponse.reason_codes).';

COMMENT ON COLUMN garuda_voa_checks.published_filing_deadline IS
    'D-7 Ngurah Rai filing deadline -- the ONLY Safe Clock checkpoint ever shown to a visitor (charter, spec Sec6).';

COMMENT ON COLUMN garuda_voa_checks.submit_by_date IS
    'Issuance-only submission-window cutoff (owner ruling 2026-07-27, services/garuda_flow/operating_calendar.py) -- Bali Zero own operational commitment, never an immigration deadline. NULL for extension rows and for issuance rows past operating_calendar.COVERAGE_END.';

COMMENT ON COLUMN garuda_voa_checks.price_idr IS
    'All-inclusive Bali Zero price in IDR. SOURCE: PricingTool; never hardcoded.';

-- Branch analytics: time-series for KPI dashboards.
CREATE INDEX IF NOT EXISTS idx_garuda_voa_checks_created
    ON garuda_voa_checks (created_at DESC);

-- Pilot funnel-health dashboards: accept/decline rate over time.
CREATE INDEX IF NOT EXISTS idx_garuda_voa_checks_decision_created
    ON garuda_voa_checks (decision, created_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_garuda_voa_checks_decision_created;
DROP INDEX IF EXISTS idx_garuda_voa_checks_created;
DROP TABLE IF EXISTS garuda_voa_checks;
