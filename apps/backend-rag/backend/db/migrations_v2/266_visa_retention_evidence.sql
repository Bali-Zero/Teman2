-- Migration 266: Visa Oracle retention observability boundary.
--
-- Exposes only aggregate, applicant/decision-identifier-free evidence to the
-- bounded retention worker. No duration, scheduler cadence, role or grant is
-- invented here; migration 264's approved policy remains the sole authority.

CREATE FUNCTION public.visa_decision_retention_evidence()
RETURNS TABLE (
    expired_rows BIGINT,
    expired_held_rows BIGINT,
    max_lag_seconds DOUBLE PRECISION,
    observed_at TIMESTAMPTZ
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH observation AS (
        SELECT clock_timestamp() AS observed_at
    )
    SELECT
        count(decision.id) FILTER (
            WHERE decision.retention_until <= observation.observed_at
              AND decision.legal_hold = FALSE
        )::BIGINT AS expired_rows,
        count(decision.id) FILTER (
            WHERE decision.retention_until <= observation.observed_at
              AND decision.legal_hold = TRUE
        )::BIGINT AS expired_held_rows,
        COALESCE(
            max(
                GREATEST(
                    EXTRACT(EPOCH FROM observation.observed_at - decision.retention_until),
                    0
                )
            ) FILTER (
                WHERE decision.retention_until <= observation.observed_at
                  AND decision.legal_hold = FALSE
            ),
            0
        )::DOUBLE PRECISION AS max_lag_seconds,
        observation.observed_at
    FROM observation
    LEFT JOIN public.visa_decisions AS decision
      ON decision.retention_until IS NOT NULL
    GROUP BY observation.observed_at;
$$;

REVOKE ALL ON FUNCTION public.visa_decision_retention_evidence() FROM PUBLIC;

COMMENT ON FUNCTION public.visa_decision_retention_evidence() IS
    'PII-free decision purge backlog, held-expired count and max purge lag; operator grant required.';

-- === ROLLBACK ===

DROP FUNCTION IF EXISTS public.visa_decision_retention_evidence();
