-- Synthetic Dual Consul slice; ownership belongs to the existing Lab run.
-- Slot 306 was free on origin/main and Pro HEAD at implementation. Recheck at merge.
-- Broker connections own admission; model processes receive no database connection.
-- Retained approval tombstones prevent revoke A -> bind B -> resurrect A.
SET LOCAL lock_timeout = '5s';

CREATE TABLE public.autonomous_lab_consul_leases (
    run_id TEXT PRIMARY KEY REFERENCES public.autonomous_lab_runs(run_id),
    owner_id TEXT NOT NULL CHECK (owner_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,191}$'),
    generation BIGINT NOT NULL CHECK (generation > 0),
    resource TEXT NOT NULL CHECK (resource ~ '^synthetic:[A-Za-z0-9][A-Za-z0-9_.:/-]{0,191}$'),
    intent_hash TEXT NOT NULL CHECK (intent_hash ~ '^[a-f0-9]{64}$'),
    approval_hash TEXT NOT NULL CHECK (approval_hash ~ '^[a-f0-9]{64}$'),
    review_hash TEXT NOT NULL CHECK (review_hash ~ '^[a-f0-9]{64}$'),
    packet_hash TEXT NOT NULL CHECK (packet_hash ~ '^[a-f0-9]{64}$'),
    lease_expires_at TIMESTAMPTZ NOT NULL CHECK (isfinite(lease_expires_at)),
    grant_expires_at TIMESTAMPTZ NOT NULL CHECK (isfinite(grant_expires_at)),
    revoked_at TIMESTAMPTZ CHECK (revoked_at IS NULL OR isfinite(revoked_at)),
    revoked_approval_hashes TEXT[] NOT NULL DEFAULT '{}'
        CHECK (array_position(revoked_approval_hashes, NULL) IS NULL
            AND array_to_string(revoked_approval_hashes, ',') ~ '^([a-f0-9]{64}(,[a-f0-9]{64})*)?$'),
    CHECK (lease_expires_at <= grant_expires_at),
    CHECK (revoked_at IS NULL OR approval_hash = ANY (revoked_approval_hashes))
);

-- === ROLLBACK ===
DROP TABLE IF EXISTS public.autonomous_lab_consul_leases;
