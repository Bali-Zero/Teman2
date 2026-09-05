-- Synthetic Dual Consul slice; ownership belongs to the existing Lab run.
-- Slot 306 was free on origin/main and Pro HEAD at implementation. Recheck at merge.
-- Broker connections own admission; model processes receive no database connection.
-- Retained approval tombstones prevent revoke A -> bind B -> resurrect A.
SET LOCAL lock_timeout = '5s';

-- The legacy Python migration 124 is not guaranteed to have run before the SQL
-- migration chain. Backfill its canonical Lab tables/indexes before the lease FK.
-- This immutable snapshot reuses every apply() statement verbatim after dedent;
-- the focused parity test detects drift. No worker or scheduler is activated.
-- BEGIN LEGACY 124 APPLY SNAPSHOT
CREATE TABLE IF NOT EXISTS autonomous_lab_runs (
    run_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending',
            'running',
            'paused',
            'succeeded',
            'failed',
            'cancelled'
        )),
    priority INTEGER NOT NULL DEFAULT 0,

    -- Machine placement and worker ownership.
    machine_role TEXT
        CHECK (
            machine_role IS NULL
            OR machine_role IN (
                'air_m5_cockpit',
                'pro_runtime',
                'mini_scheduler',
                'unknown'
            )
        ),
    worker_id TEXT,

    -- Receipt-safe control-plane payloads only.
    objective TEXT NOT NULL,
    receipt JSONB NOT NULL,
    target_paths TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',

    -- Retry and lease state.
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    last_error TEXT,

    -- Audit.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_autonomous_lab_runs_claimable
    ON autonomous_lab_runs (priority DESC, created_at ASC)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_autonomous_lab_runs_status_updated
    ON autonomous_lab_runs (status, updated_at);

CREATE INDEX IF NOT EXISTS idx_autonomous_lab_runs_worker
    ON autonomous_lab_runs (worker_id)
    WHERE worker_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS autonomous_lab_events_outbox (
    event_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL
        REFERENCES autonomous_lab_runs(run_id)
        ON DELETE CASCADE,
    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'run_enqueued',
            'run_claimed',
            'run_checkpointed',
            'run_paused',
            'run_succeeded',
            'run_failed',
            'run_cancelled',
            'material_ingested',
            'run_drafted',
            'experiment_ready',
            'verification_failed',
            'candidate_ready',
            'evaluation_recorded',
            'curator_decision_recorded',
            'shadow_run_completed'
        )),
    payload JSONB NOT NULL,

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending',
            'in_progress',
            'consumed',
            'failed_dlq'
        )),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_by TEXT,
    claimed_at TIMESTAMPTZ,
    consumed_at TIMESTAMPTZ,
    last_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_autonomous_lab_outbox_claimable
    ON autonomous_lab_events_outbox (created_at ASC)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_autonomous_lab_outbox_run_id
    ON autonomous_lab_events_outbox (run_id);

CREATE INDEX IF NOT EXISTS idx_autonomous_lab_outbox_status_updated
    ON autonomous_lab_events_outbox (status, updated_at);
-- END LEGACY 124 APPLY SNAPSHOT

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
-- Preserve shared Lab tables and their data, including tables bootstrapped above.
-- Reverting this slice removes only its lease table.
DROP TABLE IF EXISTS public.autonomous_lab_consul_leases;
