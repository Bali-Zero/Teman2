DROP TABLE IF EXISTS ops_receipts;
--> statement-breakpoint
DROP TABLE IF EXISTS ops_target_fences;
--> statement-breakpoint
DROP TABLE IF EXISTS ops_intents;
--> statement-breakpoint
CREATE TABLE ops_intents (
  intent_id text PRIMARY KEY NOT NULL,
  actor_key text NOT NULL,
  effective_role text NOT NULL CHECK (effective_role = 'operator'),
  policy_version text NOT NULL,
  idempotency_key text NOT NULL,
  intent_kind text NOT NULL CHECK (intent_kind IN ('rerun_collector', 'rebuild_edition', 'quarantine_story', 'release_story', 'refresh_research_job')),
  params_json text NOT NULL,
  request_hash text NOT NULL CHECK (length(request_hash) = 64 AND request_hash NOT GLOB '*[^0-9a-f]*'),
  reason_code text NOT NULL CHECK (reason_code IN ('collector_recovery', 'edition_recovery', 'content_safety', 'gates_reverified', 'research_recovery')),
  status text NOT NULL CHECK (status IN ('queued', 'claimed', 'running', 'succeeded', 'failed', 'cancelled_revoked', 'outcome_unknown')),
  attempt_limit integer NOT NULL DEFAULT 3 CHECK (attempt_limit BETWEEN 1 AND 3),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND attempt_limit),
  worker_id text,
  claim_token text,
  fencing_token integer NOT NULL DEFAULT 0 CHECK (fencing_token >= 0),
  target_key text NOT NULL,
  target_fencing_token integer NOT NULL DEFAULT 0 CHECK (target_fencing_token >= 0),
  heartbeat_at text,
  lease_deadline text,
  effect_token text,
  pre_effect_attested_at text,
  attested_policy_version text,
  attestation_expires_at text,
  effect_consumed_at text,
  expires_at text NOT NULL,
  started_at text,
  completed_at text,
  failure_code text CHECK (failure_code IS NULL OR failure_code IN ('capability_unavailable', 'invalid_target', 'effect_failed', 'lease_lost', 'authorization_revoked', 'intent_expired', 'retry_exhausted', 'stale_target_fence', 'outcome_ambiguous', 'internal_error')),
  created_at text NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(actor_key, idempotency_key)
);
--> statement-breakpoint
CREATE INDEX ops_intents_claim_idx ON ops_intents(status, expires_at, lease_deadline, created_at);
--> statement-breakpoint
CREATE INDEX ops_intents_actor_idx ON ops_intents(actor_key, created_at);
--> statement-breakpoint
CREATE TABLE ops_target_fences (
  target_key text PRIMARY KEY NOT NULL,
  next_fencing_token integer NOT NULL DEFAULT 0 CHECK (next_fencing_token >= 0),
  effect_fencing_token integer NOT NULL DEFAULT 0 CHECK (effect_fencing_token >= 0),
  updated_at text NOT NULL
);
--> statement-breakpoint
CREATE TABLE ops_receipts (
  receipt_id text PRIMARY KEY NOT NULL,
  intent_id text NOT NULL UNIQUE REFERENCES ops_intents(intent_id),
  status text NOT NULL CHECK (status IN ('succeeded', 'failed', 'cancelled_revoked', 'outcome_unknown')),
  receipt_json text NOT NULL,
  receipt_hash text NOT NULL CHECK (length(receipt_hash) = 64 AND receipt_hash NOT GLOB '*[^0-9a-f]*'),
  request_hash text NOT NULL CHECK (length(request_hash) = 64 AND request_hash NOT GLOB '*[^0-9a-f]*'),
  key_id text NOT NULL,
  body_hash text NOT NULL CHECK (length(body_hash) = 64 AND body_hash NOT GLOB '*[^0-9a-f]*'),
  fencing_token integer NOT NULL CHECK (fencing_token >= 0),
  attested_policy_version text,
  created_at text NOT NULL DEFAULT CURRENT_TIMESTAMP
);
--> statement-breakpoint
CREATE TABLE ops_audit_events (
  event_id text PRIMARY KEY NOT NULL,
  intent_id text NOT NULL REFERENCES ops_intents(intent_id),
  event_type text NOT NULL CHECK (event_type IN ('created', 'cancelled_revoked', 'claimed', 'reclaimed', 'started', 'heartbeat', 'pre_effect_attested', 'succeeded', 'failed', 'outcome_unknown')),
  actor_key text,
  worker_id text,
  status text NOT NULL CHECK (status IN ('queued', 'claimed', 'running', 'succeeded', 'failed', 'cancelled_revoked', 'outcome_unknown')),
  failure_code text CHECK (failure_code IS NULL OR failure_code IN ('capability_unavailable', 'invalid_target', 'effect_failed', 'lease_lost', 'authorization_revoked', 'intent_expired', 'retry_exhausted', 'stale_target_fence', 'outcome_ambiguous', 'internal_error')),
  fencing_token integer,
  created_at text NOT NULL DEFAULT CURRENT_TIMESTAMP
);
--> statement-breakpoint
CREATE INDEX ops_audit_intent_idx ON ops_audit_events(intent_id, created_at);
