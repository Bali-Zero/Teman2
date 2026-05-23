-- migration 195_organism_incident_ledger
-- W37 (2026-05-23): durable Postgres ledger for Organism Supervisor dispatch
-- decisions + actuator outcomes.
--
-- Context: the W27/W31 auto-heal chain (Cell -> Organism ->
-- fly_machines_restart) currently emits decisions only to
-- ~/logs/organism/decisions.jsonl (append-only file). Codex during the W27
-- 4-LLM panel flagged this as insufficient: an incident ledger in Postgres
-- is needed so (a) decisions survive disk-full / logrotate, (b) operator
-- can query via SQL ("show me all auto-restarts in last 30d"), (c)
-- cross-incident correlation is possible (which machine restarted most,
-- MTTR by class), (d) the Reflexion synthesis pipeline can use it as a
-- ground-truth source weekly.
--
-- Schema design:
--
-- * one row per Organism *dispatch* (one dispatch = one ActionDecision
--   leaving the Dispatcher with outcome=dispatched). Subsequent
--   actuator-emitted done/failed events UPDATE the same row via
--   correlation_id match (organism actuators emit a single event per .run()
--   call carrying the same correlation_id).
-- * incident_id groups multiple related dispatches the operator considers
--   one incident (e.g. retry storm). Auto-generated UUID; future patches
--   may set it explicitly to a stable value when an upstream incident-
--   tracker exists.
-- * correlation_id is the join key to events_outbox._outbox_id and to the
--   Redis organism:events stream. NOT unique by itself (a retry can reuse
--   the correlation_id of the originating event, though current code does
--   not).
--
-- Failure semantics:
--
-- * insertion is BEST-EFFORT -- if Postgres is unreachable, the dispatch
--   path MUST NOT fail. The Supervisor logs a WARN and the
--   ~/logs/organism/decisions.jsonl trail (which already exists) remains
--   the authoritative source until the next supervisor restart.
-- * the actuator-side UPDATE is also best-effort. A missing row (e.g.
--   Postgres came back up after the dispatch INSERT failed but before the
--   actuator emit) is silently skipped -- operator can reconstruct from
--   decisions.jsonl + the actuator's own WAL files.
--
-- Idempotency:
--
-- * CREATE TABLE IF NOT EXISTS -- safe to re-apply
-- * Indexes use IF NOT EXISTS -- safe to re-apply
-- * No existing data references this table -- pure additive (Wave 1
--   crm-guardian extra=ignore policy satisfied).

CREATE TABLE IF NOT EXISTS incident_ledger (
    id              BIGSERIAL PRIMARY KEY,
    incident_id     UUID NOT NULL DEFAULT gen_random_uuid(),
    correlation_id  TEXT NOT NULL,
    cell_id         TEXT NOT NULL,
    app             TEXT NOT NULL,
    machine_id      TEXT,
    actuator        TEXT NOT NULL,
    outcome         TEXT NOT NULL,
    consecutive_red INTEGER,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    error           TEXT,
    CONSTRAINT incident_ledger_outcome_chk
        CHECK (outcome IN (
            'dispatched',
            'deferred_cb',
            'deferred_mutex',
            'deferred_blackout',
            'deferred_defer_actuator',
            'rejected_unknown',
            'awaiting_human',
            'shadow_logged',
            'done',
            'failed'
        ))
);

-- Recent-incidents-by-app query (operator dashboard)
CREATE INDEX IF NOT EXISTS idx_incident_ledger_app_started
    ON incident_ledger (app, started_at DESC);

-- Join-with-events_outbox query (correlation-id lookup)
CREATE INDEX IF NOT EXISTS idx_incident_ledger_correlation
    ON incident_ledger (correlation_id);

-- Cross-incident grouping (one incident_id may span N dispatches)
CREATE INDEX IF NOT EXISTS idx_incident_ledger_incident
    ON incident_ledger (incident_id, started_at);

-- Open-incidents view: dispatches still missing a terminal outcome
-- (done/failed). Used by Reflexion + ops dashboards.
CREATE INDEX IF NOT EXISTS idx_incident_ledger_open
    ON incident_ledger (started_at DESC)
    WHERE completed_at IS NULL;

COMMENT ON TABLE incident_ledger IS
    'W37 durable ledger of Organism Supervisor auto-heal decisions + actuator outcomes. One row per dispatch; UPDATE-in-place via correlation_id when actuator emits done/failed. Joinable to events_outbox via correlation_id.';

COMMENT ON COLUMN incident_ledger.incident_id IS
    'Groups multiple related dispatches the operator treats as one incident. Default = fresh UUID per dispatch; upstream patches may pass a stable value.';

COMMENT ON COLUMN incident_ledger.correlation_id IS
    'Joins to events_outbox._outbox_id and to the Redis organism:events stream correlation_id field.';

COMMENT ON COLUMN incident_ledger.outcome IS
    'Dispatch outcome at insert (dispatched / deferred_x / rejected_x / awaiting_human / shadow_logged) or terminal actuator state after UPDATE (done / failed).';

-- Rollback procedure documented in research/operations/2026-05-23-w37-incident-ledger.md
-- (kept out of this file so the migration runner does not interpret it).
SELECT 1;
