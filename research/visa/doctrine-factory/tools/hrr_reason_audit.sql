-- QW-6a — HRR reason audit: repo-side read-only queries
--
-- GROUNDING (verified on disk, this session — cite, do not re-derive):
--   apps/backend-rag/backend/db/migrations_v2/252_visa_engine_write_substrate.sql
--     visa_decisions.verdict is the 5-value DecisionState CHECK enum:
--     'NEEDS_INPUT' | 'SUPPORTED_CANDIDATES' | 'HUMAN_REVIEW_REQUIRED' |
--     'NO_SUPPORTED_PATH' | 'TEMPORARILY_UNAVAILABLE'. There is NO
--     review_reason_codes/no_path_reason_codes column on this table — 252's
--     own header explicitly defers them ("rich per-candidate detail SHADOW
--     comparison does not need"). Also: visa_decisions.environment is a
--     CHECK enum IN ('TEST','STAGING','PRODUCTION'); visa_decisions.id is
--     the surrogate PK, distinct from visa_decisions.decision_id (the
--     engine's own domain UUID — the one to report/correlate against).
--   apps/backend-rag/backend/db/migrations_v2/255_visa_shadow_evidence.sql
--     adds grounding_summary JSONB NOT NULL DEFAULT '[]' ("candidate_summary
--     and grounding_summary contain only engine identifiers, reason codes,
--     and source-record UUIDs") and request_category/candidate_summary.
--   apps/backend-rag/backend/db/migrations_v2/256_visa_traffic_source.sql
--     adds traffic_source TEXT NULLable CHECK IN ('real','synthetic_gold',
--     'synthetic_driver'); NULL = legacy/unknown provenance, must NEVER be
--     folded into 'real' silently (fail-closed, per 256's own header).
--   apps/backend-rag/backend/services/visa_engine/shadow.py::_build_grounding_summary
--     the ACTUAL reason-code carrier: grounding_summary is a JSON array of
--     claims {"claim_kind": "VERDICT"|"CANDIDATE"|"REVIEW_REASON"|
--     "NO_PATH_REASON"|"NOTICE", "claim_code": <str>, "source_record_ids":
--     [...]}. For a HUMAN_REVIEW_REQUIRED verdict the reason codes are the
--     claim_code values of every claim with claim_kind='REVIEW_REASON'.
--   apps/backend-rag/backend/db/migrations_v2/250_visa_engine_core.sql
--     visa_rule_packs.sequence BIGINT — the pack-activation sequence number
--     ("pack seq-7") referenced by the plan's pre/post-seq-7 baseline. It is
--     UNIQUE only per (environment, jurisdiction, decision_domain) — NOT
--     globally. visa_decisions.jurisdiction/.decision_domain are each
--     single-valued CHECK enums today ('ID' / 'IMMIGRATION_VISA' only), so
--     pinning environment (below) is what makes "seq-7" mean one pack.
--
-- SCOPE (kimi adversarial review F1/F2/F5/F8, 2026-08-16 — hardened after
-- the first draft): every query below is pinned to
-- ``d.environment = 'PRODUCTION' AND d.engine_mode = 'SHADOW'``. Without
-- this, TEST/STAGING rows and a future ENFORCE-mode row would silently mix
-- into the "live ledger" figures this audit exists to measure, and — given
-- sequence's per-scope uniqueness above — a TEST pack "seq 7" and a
-- PRODUCTION pack "seq 7" would collapse into one bucket. To audit a
-- different scope, edit the WHERE clause explicitly; never drop it.
--
-- USAGE: run against the LIVE ledger with a READ-ONLY role only (QW-6b), via
--   psql -v min_sequence=7 -f hrr_reason_audit.sql "$VISA_DECISIONS_RO_DSN"
-- (psql :min_sequence has NO in-file default — psql errors on an unset
-- variable reference, so -v is mandatory, not optional; the Python module's
-- own --min-sequence default of 7 mirrors the plan's "post-seq-7" baseline).
-- Every query below also carries traffic_source explicitly in its GROUP
-- BY/SELECT list so a probe/synthetic row can never silently pollute a
-- "real" figure — this is QW-6a's mandatory contamination guard, not
-- optional polish.

-- =============================================================================
-- Query 1 — per-reason-code counts for HUMAN_REVIEW_REQUIRED decisions,
--           split by traffic_source (mandatory) and by min rule_pack sequence
--           (mandatory cutoff — pass -v min_sequence=7 for "post-seq-7").
--           A REVIEW_REASON claim with a NULL/malformed claim_code is kept
--           as its own NULL-reason_code row rather than dropped (F9) — an
--           auditor must see dirty data, not have it silently vanish.
-- =============================================================================
WITH hrr_claims AS (
    SELECT
        d.decision_id,
        d.traffic_source,
        rp.sequence                                      AS rule_pack_sequence,
        claim.value ->> 'claim_code'                     AS reason_code
    FROM public.visa_decisions d
    LEFT JOIN public.visa_rule_packs rp ON rp.id = d.rule_pack_id
    CROSS JOIN LATERAL jsonb_array_elements(d.grounding_summary) AS claim(value)
    WHERE d.verdict = 'HUMAN_REVIEW_REQUIRED'
      AND d.engine_surface = 'MATCH'
      AND d.environment = 'PRODUCTION'
      AND d.engine_mode = 'SHADOW'
      AND claim.value ->> 'claim_kind' = 'REVIEW_REASON'
)
SELECT
    COALESCE(traffic_source, 'legacy_unknown')  AS traffic_source_bucket,
    reason_code,
    COUNT(*)                                    AS reason_count,
    COUNT(DISTINCT decision_id)                 AS decisions_with_this_reason
FROM hrr_claims
WHERE rule_pack_sequence IS NOT NULL AND rule_pack_sequence >= :min_sequence
GROUP BY 1, 2
ORDER BY 1, reason_count DESC;

-- =============================================================================
-- Query 2 — conclusive-rate split: SUPPORTED_CANDIDATES / NEEDS_INPUT /
--           HUMAN_REVIEW_REQUIRED / NO_SUPPORTED_PATH / TEMPORARILY_UNAVAILABLE
--           counts + share, split by traffic_source (mandatory), post-seq-7.
--           "Conclusive" mirrors hrr_reason_audit.py::INCONCLUSIVE_VERDICTS
--           EXACTLY (kimi review F6): inconclusive = HUMAN_REVIEW_REQUIRED
--           + NEEDS_INPUT + TEMPORARILY_UNAVAILABLE; conclusive = everything
--           else (SUPPORTED_CANDIDATES and NO_SUPPORTED_PATH both count as
--           conclusive — the engine reached a definite answer either way).
--           This query computes conclusive_rate_pct DIRECTLY so a QW-6b
--           auditor never has to hand-sum verdicts to reproduce the Python
--           module's own headline number.
-- =============================================================================
WITH scoped AS (
    SELECT
        d.verdict,
        d.traffic_source,
        rp.sequence AS rule_pack_sequence
    FROM public.visa_decisions d
    LEFT JOIN public.visa_rule_packs rp ON rp.id = d.rule_pack_id
    WHERE d.engine_surface = 'MATCH'
      AND d.environment = 'PRODUCTION'
      AND d.engine_mode = 'SHADOW'
      AND rp.sequence IS NOT NULL
      AND rp.sequence >= :min_sequence
),
by_verdict AS (
    SELECT
        COALESCE(traffic_source, 'legacy_unknown') AS traffic_source_bucket,
        verdict,
        COUNT(*)                                    AS decision_count
    FROM scoped
    GROUP BY 1, 2
)
SELECT
    traffic_source_bucket,
    verdict,
    decision_count,
    SUM(decision_count) OVER (PARTITION BY traffic_source_bucket)             AS bucket_total,
    SUM(CASE WHEN verdict NOT IN
            ('HUMAN_REVIEW_REQUIRED', 'NEEDS_INPUT', 'TEMPORARILY_UNAVAILABLE')
        THEN decision_count ELSE 0 END)
        OVER (PARTITION BY traffic_source_bucket)                             AS bucket_conclusive,
    ROUND(
        100.0
        * SUM(CASE WHEN verdict NOT IN
                ('HUMAN_REVIEW_REQUIRED', 'NEEDS_INPUT', 'TEMPORARILY_UNAVAILABLE')
              THEN decision_count ELSE 0 END)
              OVER (PARTITION BY traffic_source_bucket)
        / NULLIF(SUM(decision_count) OVER (PARTITION BY traffic_source_bucket), 0),
        2
    )                                                                          AS bucket_conclusive_rate_pct
FROM by_verdict
ORDER BY 1, 2;

-- =============================================================================
-- Query 3 — optional split by rule_pack sequence / ruleset_activation_id.
--           Use to locate exactly which activation flipped the conclusive
--           rate. Deliberately NOT gated by :min_sequence (it IS the tool
--           for finding the sequence boundary) — still pinned to
--           environment/engine_mode (F1/F2/F8) so it never mixes scopes.
-- =============================================================================
SELECT
    rp.sequence                                 AS rule_pack_sequence,
    d.ruleset_activation_id,
    COALESCE(d.traffic_source, 'legacy_unknown') AS traffic_source_bucket,
    d.verdict,
    COUNT(*)                                     AS decision_count
FROM public.visa_decisions d
LEFT JOIN public.visa_rule_packs rp ON rp.id = d.rule_pack_id
WHERE d.engine_surface = 'MATCH'
  AND d.environment = 'PRODUCTION'
  AND d.engine_mode = 'SHADOW'
GROUP BY 1, 2, 3, 4
ORDER BY 1 NULLS FIRST, 2, 3, 4;
