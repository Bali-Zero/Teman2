# Dual Consul v4: reproducible first slice

This increment implements an opt-in synthetic mission inside the existing
Autonomous Lab lifecycle. It prepares code and evidence for independent release
review. It does not activate a fleet service or qualify provider effects.

## Consumers and observable behavior

- `AutonomousLabWorker(stage_nodes=(ConsulSyntheticStage(...),))` consumes the new
  stage. Both Astra-builder/Fable-reviewer and Fable-builder/Astra-reviewer cases
  enqueue, claim, execute, checkpoint, and finish through the existing worker.
- `consul_store` binds PostgreSQL ownership and generation to the exact mission,
  synthetic resource, intent, authorization, review, and input-packet digests.
  Its transaction locks the Lab parent before the lease. The effect statement
  rechecks expiry using PostgreSQL's live clock.
- `consul_executor` accepts only `com.balizero.consul.synthetic_checkpoint`.
  A canonical `ActionIntent`, `ApprovalReceipt`, `VerificationReceipt`, started
  `ExecutionAttempt`, outbox checkpoint, and confirmed `OperationalReceipt`
  share the existing Research OS and Lab stores. The attempt, checkpoint, and
  result commit together; a failed result write rolls everything back.
- `python -m scripts.conductor.adapter_contracts` consumes a JSON admission
  packet on stdin and emits only admission/rejection metadata. Exit 0 admits
  text preparation, exit 2 denies it, and exit 1 identifies malformed input.
  It launches no provider. Its module docstring and `main()` document the packet.
- The existing MIR generator now reproduces the checked-in capability projection.
  Model cards and endpoint profiles are unchanged. Text observations do not
  promote an endpoint to operational eligibility.

The authorization and reviewer fields in the executable tests are synthetic.
They test exact binding and independence checks, not semantic model judgment.
The separate Fable review files record actual native model responses to frozen
implementation packets. Their metadata identifies the files and hashes reviewed.

## Focused verification

From the worktree root, activate the repository's existing virtualenv:

```sh
source apps/backend-rag/.venv/bin/activate
PYTHONPATH=apps/backend-rag python -m pytest \
  apps/backend-rag/backend/tests/unit/services/autonomous_lab/ \
  --tb=short --color=no
python -m pytest \
  scripts/tests/test_conductor_model_registry.py \
  scripts/tests/test_conductor_host_identity.py \
  scripts/tests/test_conductor_host_seat_maps.py \
  scripts/tests/test_conductor_calibration.py \
  scripts/tests/test_conductor_adapter_contracts.py -q --tb=short
python -m scripts.conductor.build_model_capability_index --check
```

Run the PostgreSQL proof on Pro, against a newly initialized disposable instance
and the dedicated database **`dual_consul_test`**. Supply its Unix socket directory
and port through `PGHOST` and `PGPORT`; the DSN deliberately accepts no query
overrides. The fixture resets only this slice's tables in that database and
serializes fixture setup with an advisory lock. Never point it at an operational
database. With the disposable instance already prepared:

```sh
source apps/backend-rag/.venv/bin/activate
DUAL_CONSUL_TEST_DSN=postgresql:///dual_consul_test \
  PYTHONPATH=apps/backend-rag python -m pytest \
  apps/backend-rag/backend/tests/integration/test_dual_consul_postgres.py \
  --tb=short --color=no
```

The integration proof uses the existing production JSON codec and actual Lab,
Research OS, and lease migrations. It covers both consul directions, current
owner success, stale generations, takeover, expiry, revocation, cancellation,
idempotent replay, atomic rollback, delayed writes crossing the expiry boundary,
and real two-connection lock serialization. Migration 306 is also rolled back,
reapplied, and consumed by a new synthetic mission.

The review's JSON-shape question led to a read-only production schema check:
both Lab tables were absent. Migration 306 therefore backfills the exact eight
DDL statements from legacy Python migration 124 before creating the lease FK.
A parity test compares the snapshot with the original producer, and a separate
PostgreSQL case runs 306 without pre-creating Lab tables. Rollback removes the
lease table and preserves the shared Lab tables and their data. This prerequisite
correction has its own frozen review packet after the first two accepted reviews.
The [preflight record](schema-preflight.json) contains only schema-presence results.

This caught a pre-existing Lab transport defect: `_jsonb()` already serializes
its value, while the production JSON codec serializes JSON-bound parameters
again. Binding that serialized value as `text` before casting to `jsonb` fixes
the existing store's worker path without changing the shared connection codec.

## Boundaries and reconciliation

The executor is an in-process trusted-broker component. A distinct OS service
identity, credential removal from model processes, native App Server discovery
and effective configuration isolation, provider launch/resume/cancellation,
global native-worker supervision, staging/canary activation, and production
reliability remain unqualified. No migration or daemon is installed on the fleet.

Replay through `execute_synthetic` requires a live, matching authorization and
lease even when a receipt already exists. An expired or revoked owner cannot use
replay to regain authority. After an ambiguous commit acknowledgment, inspect the
immutable Research OS result through an independently authorized read or renew
admission before replaying. This increment provides no remote-effect reconciliation.
Idempotency is per canonical intent; distinct authorized intents may produce
distinct checkpoints for the same run.

The existing `change_map`, `impact_map`, and workflow/merge-group rules remain
unchanged. The PostgreSQL suite is opt-in; no new general harness job is attached
to every PR. Raw selected review and design text preserves original bytes,
including whitespace, so its SHA-256 can be checked exactly.
Implementation evidence has a 160 KiB budget, separate from the 64 KiB selected
design-artifact budget; full native transcripts and reasoning blocks are excluded.
