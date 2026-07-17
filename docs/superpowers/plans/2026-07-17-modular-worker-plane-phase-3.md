# Modular Worker Plane Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement fenced active adapters for `workflow_queue` and then `legal_full_ingestion`, prove effect ambiguity and lease recovery under fault injection, prove forward plus reverse ownership transitions with deterministic CLI simulations and disposable PostgreSQL, and define a protected one-workload live-control actuator without invoking it against staging or production.

**Architecture:** Phase 3 extends, rather than replaces, the Phase 1 ownership plane and Phase 2 companion runtime. Migration `248_worker_effect_ledger.sql` adds a stable effect projection, append-only attempt history, cutover-run audit, and narrow transition functions. `OwnershipRepository`, `OwnershipService`, the Phase 1 grant, and canonical Phase 0 catalogs remain authoritative. Every automatic prepare, begin, finish, and reconcile transaction locks the grant, workload-specific domain claim, and stable effect row in that order; it validates the live `runtime_owner`, generation, immutable claim stamp, unexpired claim lease, expected attempt/state, and retry contract before any DML. This closes ownership changes both before dispatch and before a late completion or reconciliation. The cutover coordinator inventories workload-specific live leases, pending runs, and every blocking effect state before adoption/activation. Workflow completes disposable-database fault gates and forward/reverse simulations before legal implementation begins. Phase 3 creates no live resource and invokes no live mutation. It does, however, build and fake-test the exact environment-protected `worker-plane-live-control.yml` path that production-rollout Tasks 2–3 later use for single-workload census, guard, drain, barrier, activate, reverse, and disarm actions on the exact protected-merged digest.

**Tech Stack:** Python 3.11+, asyncio, asyncpg, PostgreSQL/PLpgSQL migration 248, Phase 0 catalogs, Phase 1 ownership/fencing services, Phase 2 lazy worker runtime, HTTPX, Qdrant deterministic IDs, Google Drive/Sheets adapters, pytest/pytest-asyncio, GitHub Actions, Fly.io companion app, JSON evidence artifacts.

## Global Constraints

- Phase 0, Phase 1, and Phase 2 must be implemented, committed, independently reviewed, and verifier-green earlier on this same feature branch. They do not need separate merges. Phase 3 admission uses only checked-in code, CI evidence, and disposable PostgreSQL; it neither requires nor authorizes a candidate staging deploy.
- Migration allocation is exact: Phase 3 owns only `apps/backend-rag/backend/db/migrations_v2/248_worker_effect_ledger.sql`. It follows `246_event_quarantine.sql` and `247_worker_plane_ownership.sql`. The next free number after this plan is `249`.
- Preserve the existing public contracts and names: `BusinessContext`, `RuntimeOwner`, `RuntimeProfile`, `OwnershipMode`, `SideEffectClass`, `DeliverySemantics`, `PiiClass`, `WorkloadSpec`, `WORKLOAD_CATALOG`, `get_workload_spec`, `EventPolicy`, `EVENT_CATALOG`, `get_event_policy`, `SideEffectCapability`, `SIDE_EFFECT_CATALOG`, `get_side_effect_capability`, `TableOwnership`, `load_table_ownership_catalog`, `validate_table_ownership`, `OwnershipGrant`, `OwnerHeartbeat`, `ClaimContext`, `BuildFloorEvidence`, `LivenessReport`, `OwnershipRepository`, `OwnershipService`, and their Phase 1 methods. `business_context` remains bounded/data ownership; `runtime_owner` remains the only execution field on grants, claims, heartbeats, leases, and CAS operations. New effect/cutover code composes these symbols; it does not introduce a compatibility alias, second ownership repository, grant table, worker catalog, or claim service.
- Work only in an isolated worktree. Backend commands use `apps/backend-rag/.venv` with `PYTHONPATH=.`. Heavy tests, disposable PostgreSQL suites, and failure injection run on Pro or CI. Air-M5 may edit and run static checks but must route heavy execution to Pro/CI.
- Workloads are implemented strictly in this order: `workflow_queue`, hard disposable-evidence checkpoint, `legal_full_ingestion`. No legal implementation task begins until workflow has passed G3/G4/G12/G15, forward/reverse disposable simulations, targeted SDD rereview, and its code-readiness checkpoint document is committed.
- Each workload proves the compatibility-floor algorithm with authoritative synthetic expected-instance/heartbeat fixtures bound to the exact candidate digest. Live legacy-owner and target-worker heartbeats are deliberately deferred to production-rollout Task 2; missing/stale/old/mismatched fixture evidence blocks the simulated drain.
- The authoritative grant uses one owner. Target `shadow` remains a runtime observation mode while the legacy owner stays authoritative. Cutover changes the same ownership row; there is never a second active grant.
- A same-`runtime_owner` mode transition from `active` to `draining` preserves generation and increments only row version. It blocks new claims but permits already-stamped claims to finish through `OwnershipService.assert_effect_allowed`. Assigning a different `runtime_owner` uses Phase 1 `worker_advance_ownership`, increments generation, and writes `worker_ownership_audit`.
- Drain waits for the workload adapter's locked inventory to report no live old-generation claim lease, no unadopted/uncancelled pending run, no `prepared` intent, no retryable `failed` effect, no `attempting` effect, and no delivery-semantics-blocking `outcome_unknown`. Provider timeout plus clock margin must also elapse where applicable. Lease expiry alone never authorizes a retry or activation.
- `effect_key` derives only from stable business identity and effect purpose. Queue row ID, attempt count, claim token, build, `runtime_owner`, and ownership generation are forbidden components. Ledger rows contain opaque references and sanitized error classes, never payloads, document text, client identity, provider response bodies, credentials, or OSINT.
- Delivery semantics reuse canonical `DeliverySemantics` from `backend.architecture.catalogs.models`: `provider-idempotent` reuses the same provider-supported stable key; `reconcilable` queries the destination by stable reference and retries only after confirmed absence; `non-reconcilable` never retries an ambiguous dispatch automatically and enters `outcome_unknown` for audited operator resolution. No `ExternalEffectContract`, `external_contract` field, or parallel enum/registry is introduced.
- Provider-secret and database-grant requirements are derived and validated one workload at a time from the canonical `WorkloadSpec.database_grant_profile` and the selected adapter's explicit injected dependencies, without adding a parallel metadata registry or applying them to a live environment. Legal requirements remain excluded from the workflow handoff. Actual staging grants/secrets and later removal are deferred to production-rollout Task 2 and its reverse-cutover window.
- Existing legacy lifespan wiring, additive claim columns, Phase 1 triggers, migration 247 tables/functions, and legacy code paths remain present. The disposable reverse simulation and later live staging rollback both use a newer generation, never a static flag flip, manual row edit, or generation decrement.
- Periodic schedule identity is generation-independent `(workload_name, scheduled_for)`. G12 uses an isolated schedule fixture even though workflow and legal are queue workloads. Pending runs are adopted or cancelled in the cutover transaction and audited; they are never cloned under a new generation key.
- Disposable simulations and the later staging rollout use only synthetic/public fixtures and opaque IDs; no client message, client document, KTP, passport, NPWP, akta, WhatsApp payload, or OSINT record is a canary.
- Every test is written and observed failing for the stated reason before production code. Refactor only after GREEN and rerun the focused suite.
- Every implementation task receives a fresh read-only review through `superpowers:subagent-driven-development`. Provide task contract, exact diff, RED/GREEN output, migration/cutover implications, and rollback effect. Fix blocking findings, rerun, and obtain rereview before one atomic conventional commit.
- The hard workflow-to-legal checkpoint and the final legal checkpoint each recapture a complete API/RAG G9 candidate on Pro/self-hosted CI with the canonical Phase 0 protocol and compare it to `backend/architecture/baselines/phase0_snapshot.json`. All four numeric maps for both owners must be present and no metric may exceed `1.10x` without an exact approved unexpired exception. A worker G13/G14 result cannot substitute for G9.
- Never use `--no-verify`, `--amend`, force push, or direct push to `main`. This phase may not dispatch the protected workflow or mutate any live staging/production app, database, secret, grant, guard, heartbeat, or ownership row. The live-control code must reject direct/pre-merge/wrong-digest/wrong-app invocation and is exercised only with fakes/disposable PostgreSQL here. Live staging and production dispatch belongs exclusively to the rollout after protected merge, using the exact merged digest and immutable gate/admission artifacts.
- The phase cannot exit with placeholder code/reviews, skipped fault cases, unresolved unknown non-reconcilable effects, a budget regression, or unresolved Blocking/Important panel findings.

## File Responsibility Map

| Area               | Files owned by this phase                                                                                                                                         | Responsibility                                                                                                                                           |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Effect schema      | `backend/db/migrations_v2/248_worker_effect_ledger.sql`, `backend/worker_plane/effects.py`, `effect_ledger.py`                                                    | Stable effect projection, append-only attempts, resolution audit, and late-fence transitions.                                                            |
| Catalog capability | `backend/architecture/catalogs/models.py`, `effects.py`, `workers.py`                                                                                             | Reuse `DeliverySemantics`; extend existing capabilities only with timeout/reconciliation data.                                                           |
| Cutover control    | `backend/worker_plane/cutover.py`, `scripts/worker_cutover.py`, `scripts/worker_live_control.py`, `.github/workflows/worker-plane-live-control.yml`               | Disposable simulation plus protected exact-digest one-workload live census/guard/drain/barrier/activate/reverse/disarm actuation; no pre-merge dispatch. |
| Workflow move      | `backend/services/workflow/queue.py`, `executor.py`, `chains/intel.py`, `backend/services/intel/workflow_ports.py`, `backend/workers/adapters/workflow_active.py` | Router-free dependency injection, active runner, Telegram effect boundary.                                                                               |
| Legal move         | `backend/services/ingestion/legal_ingestion_service.py`, `legal_full_ingestion_worker.py`, `legal_pipeline_ports.py`, `backend/workers/adapters/legal_active.py`  | Stable document identity, separate injected Qdrant/KG operations, single Drive ownership, effect-bound provider stages.                                  |
| Rollout handoff    | workload evidence schemas, CLI simulations, CI, and runbooks                                                                                                      | Freeze exact merged-digest staging preconditions and commands for production-rollout Task 2 without executing live mutations in Phase 3.                 |
| Acceptance         | integration/fault tests, `scripts/verify_worker_plane_phase3.py`, CI, final reviews                                                                               | G3/G4/G12/G15 and phase exit.                                                                                                                            |

## Interfaces and State Machines

Migration 248 creates exactly three tables and no replacement ownership table:

```sql
CREATE TABLE IF NOT EXISTS worker_effect_ledger (
    effect_key TEXT PRIMARY KEY,
    workload_name TEXT NOT NULL REFERENCES worker_workload_ownership(workload_name),
    effect_name TEXT NOT NULL,
    business_ref TEXT NOT NULL,
    delivery_semantics TEXT NOT NULL CHECK (
        delivery_semantics IN ('provider-idempotent', 'reconcilable', 'non-reconcilable')
    ),
    state TEXT NOT NULL CHECK (
        state IN ('prepared', 'attempting', 'confirmed', 'failed', 'outcome_unknown')
    ),
    current_attempt_id UUID,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    provider_reference TEXT,
    reconciliation_status TEXT NOT NULL DEFAULT 'not_checked' CHECK (
        reconciliation_status IN ('not_checked', 'confirmed_present', 'confirmed_absent', 'unavailable')
    ),
    last_error_class TEXT,
    resolution_actor TEXT,
    resolution_reason TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS worker_effect_attempts (
    event_id BIGSERIAL PRIMARY KEY,
    effect_key TEXT NOT NULL REFERENCES worker_effect_ledger(effect_key),
    attempt_id UUID NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    event_kind TEXT NOT NULL CHECK (
        event_kind IN ('began', 'reconciled', 'confirmed', 'failed', 'outcome_unknown')
    ),
    expected_state TEXT NOT NULL,
    resulting_state TEXT NOT NULL,
    runtime_owner TEXT NOT NULL CHECK (runtime_owner IN ('api', 'rag', 'worker', 'drive')),
    ownership_generation BIGINT NOT NULL CHECK (ownership_generation > 0),
    claim_build_epoch BIGINT NOT NULL CHECK (claim_build_epoch >= 0),
    claim_token UUID NOT NULL,
    claim_claimed_at TIMESTAMPTZ NOT NULL,
    claim_lease_expires_at TIMESTAMPTZ NOT NULL,
    provider_reference TEXT,
    reconciliation_status TEXT,
    error_class TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (effect_key, attempt_number, event_kind)
);

CREATE TABLE IF NOT EXISTS worker_cutover_run_audit (
    id BIGSERIAL PRIMARY KEY,
    workload_name TEXT NOT NULL,
    run_key TEXT NOT NULL,
    source_generation BIGINT NOT NULL,
    target_generation BIGINT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('adopt', 'cancel')),
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workload_name, run_key, target_generation, action)
);
```

Migration 248 defines and tests narrow, workload-specific projection/history
functions. There is no public mutation function that accepts a caller-selected
workload. Workflow and legal each receive their own four-function automatic
family plus one separately authorized resolution function:
`worker_prepare_<workflow|legal>_effect`,
`worker_begin_<workflow|legal>_effect_attempt`,
`worker_reconcile_<workflow|legal>_effect`,
`worker_finish_<workflow|legal>_effect`, and
`worker_resolve_<workflow|legal>_unknown_effect`. Every function hard-codes its
catalog workload; `<workload>` is part of the function name, never a runtime
argument. For these two queue workloads the domain-claim locator is exactly the
UUID primary key of `workflow_jobs.id` or `legal_ingest_jobs.id`. The matching
lease value is `workflow_jobs.visible_at` or `legal_ingest_jobs.visibility_at`.
The following signatures are the exact migration contract:

```sql
worker_set_ownership_mode(
    p_workload_name TEXT,
    p_expected_runtime_owner TEXT,
    p_expected_generation BIGINT,
    p_expected_version BIGINT,
    p_expected_mode TEXT,
    p_new_mode TEXT,
    p_actor TEXT,
    p_reason TEXT
) RETURNS worker_workload_ownership

worker_prepare_<workload>_effect(
    p_domain_claim_id UUID,
    p_effect_key TEXT,
    p_effect_name TEXT,
    p_business_ref TEXT,
    p_delivery_semantics TEXT,
    p_expected_state TEXT,
    p_claim_runtime_owner TEXT,
    p_claim_generation BIGINT,
    p_claim_build_epoch BIGINT,
    p_claim_token UUID,
    p_expected_claimed_at TIMESTAMPTZ,
    p_expected_lease_expires_at TIMESTAMPTZ
) RETURNS worker_effect_ledger

worker_begin_<workload>_effect_attempt(
    p_domain_claim_id UUID,
    p_effect_key TEXT,
    p_expected_attempt_id UUID,
    p_expected_state TEXT,
    p_new_attempt_id UUID,
    p_claim_runtime_owner TEXT,
    p_claim_generation BIGINT,
    p_claim_build_epoch BIGINT,
    p_claim_token UUID,
    p_expected_claimed_at TIMESTAMPTZ,
    p_expected_lease_expires_at TIMESTAMPTZ
) RETURNS worker_effect_ledger

worker_reconcile_<workload>_effect(
    p_domain_claim_id UUID,
    p_effect_key TEXT,
    p_expected_attempt_id UUID,
    p_expected_state TEXT,
    p_status TEXT,
    p_provider_reference TEXT,
    p_claim_runtime_owner TEXT,
    p_claim_generation BIGINT,
    p_claim_build_epoch BIGINT,
    p_claim_token UUID,
    p_expected_claimed_at TIMESTAMPTZ,
    p_expected_lease_expires_at TIMESTAMPTZ
) RETURNS worker_effect_ledger

worker_finish_<workload>_effect(
    p_domain_claim_id UUID,
    p_effect_key TEXT,
    p_expected_attempt_id UUID,
    p_expected_state TEXT,
    p_state TEXT,
    p_provider_reference TEXT,
    p_error_class TEXT,
    p_claim_runtime_owner TEXT,
    p_claim_generation BIGINT,
    p_claim_build_epoch BIGINT,
    p_claim_token UUID,
    p_expected_claimed_at TIMESTAMPTZ,
    p_expected_lease_expires_at TIMESTAMPTZ
) RETURNS worker_effect_ledger

worker_resolve_<workload>_unknown_effect(
    p_effect_key TEXT,
    p_expected_attempt_id UUID,
    p_expected_state TEXT,
    p_terminal_state TEXT,
    p_actor TEXT,
    p_reason TEXT,
    p_provider_reference TEXT
) RETURNS worker_effect_ledger
```

For first prepare, `p_expected_state` is SQL `NULL`; an idempotent replay must
pass `prepared` and match the same stable identity. For a first begin,
`p_expected_attempt_id` is SQL `NULL`; every retry supplies the exact current
attempt ID. The automatic functions lock, in order, the Phase 1 grant, the
fixed workload's domain-claim row, the stable projection, and the current
attempt-history row when one is expected. In that same transaction they compare
the live grant and all scalar fields from
`ClaimContext`, require the exact immutable `(runtime_owner, generation,
build_epoch, claim_token, claimed_at)` domain-claim stamp, compare the current
lease value with `p_expected_lease_expires_at`, require it to be unexpired at
database time, and compare the expected projection attempt/state before DML.
Begin persists the immutable claim identity and dispatch-time lease snapshot on
its `began` attempt event. Finish and reconcile additionally lock that exact
event and verify its immutable effect/attempt/claim stamp against the projection
before transitioning it. Finish may confirm a provider result only when the
attempt's immutable claim identity equals the current live claim identity.
Reconcile may inspect an older exact attempt under a newly acquired live claim
after timeout plus margin, but the stale caller's old `ClaimContext` still fails
the live grant/domain-claim checks. A permitted lease renewal changes only the
domain row's current lease value; finish/reconcile compare that value with the
passed current expected lease stamp and require it to be unexpired.
Prepare, begin, finish, and reconcile all perform these checks; a provider
response that arrives after ownership changes or after the claim expires cannot
complete through the stale stamp. A worker must renew its domain lease before a
long dispatch completes, without changing the immutable stamp.

`worker_set_ownership_mode` locks the Phase 1 grant, matches expected owner,
generation, version, and mode, preserves `runtime_owner`, generation, and build
floor, increments version, and writes `worker_ownership_audit`. The two static
resolution functions do not inspect a live grant or claim: they lock only the
workload-bound projection/history rows and compare exact effect key, expected
attempt ID, expected `outcome_unknown` state, terminal result, actor, reason,
and provider reference. No generic mutating SQL helper sits behind any of these
functions; shared SQL helpers are validation/read-only only. A trigger denies
`UPDATE` and `DELETE` on `worker_effect_attempts`; correction is a later audited
event. Invalid/stale transitions use SQLSTATE `55000`.

The atomic late-fence coordinator is a Python service because domain claim
tables differ. Its fixed lock order is grant -> workload adapter domain claim ->
effect projection -> current began-attempt event when applicable. Every
automatic `EffectMutationPort` method requires the
workload-bound domain locator, `claim: ClaimContext`,
`expected_claimed_at`, and `expected_lease_expires_at`, opens one asyncpg
transaction, and calls only that workload's named SQL function. The SQL
function repeats the locked comparisons, so direct function execution cannot
bypass the fence. Prepare commits only after its in-transaction checks. Begin
commits `attempting` plus `began` before the provider call. Finish and
reconciliation repeat the same live grant/domain-claim validation, verify the
locked attempt's recorded immutable stamp, and enforce the exact attempt/state;
finish also requires the attempt creator's immutable claim identity to equal the
current claim identity. Any missing claim, expired lease, changed grant,
stale token/generation/build/claimed-at stamp, or unexpected attempt/state
blocks mutation.

The Python extension reuses canonical `DeliverySemantics`:

```python
from backend.architecture.catalogs.models import DeliverySemantics

class EffectState(str, Enum):
    PREPARED = "prepared"
    ATTEMPTING = "attempting"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"

class EffectLedgerRepository: ...  # read-only queries only
class EffectExecutor: ...
class CutoverService: ...
```

`SideEffectCapability` keeps canonical `delivery_semantics` and adds only `provider_timeout_seconds`, `clock_margin_seconds`, and `reconcile_symbol`. The new fields are mandatory where applicable and validated by `get_side_effect_capability`; no parallel registry is created. `CutoverAdapter.inventory_blockers` returns locked live leases, pending runs, prepared intents, retryable failures, attempts in flight, and blocking unknowns. `activate_target` cannot proceed while any category is nonempty.

---

## Task 1: Gate pre-248 Phase 3 admission without a live deployment

**Files:**

- Create: `apps/backend-rag/scripts/worker_phase3_preflight.py`
- Create: `apps/backend-rag/scripts/tests/test_worker_phase3_preflight.py`
- Create: `docs/architecture/worker-plane-phase3-admission.md`
- Modify: `apps/backend-rag/scripts/worker_plane_guard.py`
- Modify: `apps/backend-rag/scripts/tests/test_worker_plane_guard.py`

- [ ] Write `worker-plane-phase3-admission.md` from current same-branch evidence: green Phase 0/1/2 verifier hashes, reviewed commit SHAs, exact source commit/build artifact hash, workload order, and an explicit declaration that migration 248 is not yet applied and live staging/production targets are excluded. Record that production-rollout Task 2 will replace the source hash with the exact protected-merged digest before any staging action.
- [ ] Write tests requiring those same-branch verifier/review hashes, migration head exactly 247 in disposable PostgreSQL, every Phase 1 pilot guard `UNARMED`, no live deployment/heartbeat/ownership evidence as an admission dependency, G13/G14 code-and-CI proof, and a nonempty disposable `TEST_DATABASE_URL`. Reject an armed guard, a staging/production target, a live-mutation command, an empty database URL, an admission file that implies a prior phase was merged separately, or `legal_full_ingestion` code admission before the committed workflow code-readiness checkpoint.
- [ ] Keep `worker_plane_guard.py` read-only for admission: add an explicit `admission-status` result that reports migration head, guard states, and candidate artifact hash from injected/disposable inputs. Because Task 1 is pre-248, it must not query an effect ledger or require unknown-effect evidence; because it is pre-live-staging, it must not query or require live legacy/worker heartbeats.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_worker_phase3_preflight.py scripts/tests/test_worker_plane_guard.py -q
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/worker_phase3_preflight.py --workload workflow_queue --database-url "$TEST_DATABASE_URL" --candidate-evidence /tmp/worker-phase3-code-candidate.json --output /tmp/worker-phase3-preflight.json
  ```

  Expected: Phase 3 preflight is absent; no fixed check yet proves head 247 plus all guards unarmed from disposable PostgreSQL.

- [ ] Implement the preflight as a read-only fixed-check runner with SHA-256-bound JSON input and an allowlisted disposable database target. It must reject prose-only evidence, another source commit/artifact hash, unresolved prior-phase findings, any armed guard, any migration head other than 247, or any command/evidence that implies live staging or production mutation. It deliberately performs no effect-ledger or heartbeat check at this pre-248/pre-deploy boundary.
- [ ] Refactor evidence validation into pure typed parsers and keep all disposable database and artifact reads injected.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_worker_phase3_preflight.py scripts/tests/test_worker_plane_guard.py -q
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/worker_phase3_preflight.py --workload workflow_queue --database-url "$TEST_DATABASE_URL" --candidate-evidence /tmp/worker-phase3-code-candidate.json --output /tmp/worker-phase3-preflight.json
  ```

  Expected: tests pass; the command exits 0 only for same-branch verifier/review evidence, exact code artifact hash, schema head 247, and all guards unarmed in disposable PostgreSQL. It emits no live staging, heartbeat, or effect-ledger requirement.

- [ ] Obtain a fresh SDD read-only review of the pre-248 boundary, disposable-database allowlist, all-guards-unarmed requirement, evidence freshness, and absence of live staging dependencies; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/scripts/worker_phase3_preflight.py apps/backend-rag/scripts/tests/test_worker_phase3_preflight.py apps/backend-rag/scripts/worker_plane_guard.py apps/backend-rag/scripts/tests/test_worker_plane_guard.py docs/architecture/worker-plane-phase3-admission.md
  git commit -m "chore(worker-plane): gate phase three admission" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 2: Add migration 248 and extend the existing side-effect catalog

**Files:**

- Create: `apps/backend-rag/backend/db/migrations_v2/248_worker_effect_ledger.sql`
- Create: `apps/backend-rag/backend/tests/db/test_migration_248_worker_effect_ledger.py`
- Create: `apps/backend-rag/backend/worker_plane/effects.py`
- Create: `apps/backend-rag/backend/worker_plane/effect_ledger.py`
- Modify: `apps/backend-rag/backend/worker_plane/repository.py`
- Create: `apps/backend-rag/backend/tests/worker_plane/test_effect_ledger.py`
- Modify: `apps/backend-rag/backend/architecture/catalogs/models.py`
- Modify: `apps/backend-rag/backend/architecture/catalogs/effects.py`
- Modify: `apps/backend-rag/backend/architecture/catalogs/data/table_ownership.json`
- Modify: `apps/backend-rag/backend/tests/fixtures/schema_tables.txt`
- Modify: `apps/backend-rag/backend/tests/architecture/test_catalogs.py`
- Modify: `apps/backend-rag/scripts/tests/test_check_table_ownership.py`

The exact capability keys added or completed are:

| Workload               | Effect name                      | Class        | Delivery semantics  | Timeout | Margin | Reconciliation                    |
| ---------------------- | -------------------------------- | ------------ | ------------------- | ------: | -----: | --------------------------------- |
| `workflow_queue`       | `telegram_approval_notification` | irreversible | non-reconcilable    |     15s |     5s | none                              |
| `legal_full_ingestion` | `qdrant_index`                   | irreversible | provider-idempotent |     60s |    10s | same deterministic document ID    |
| `legal_full_ingestion` | `knowledge_graph_upsert`         | irreversible | provider-idempotent |     30s |     5s | same database uniqueness key      |
| `legal_full_ingestion` | `drive_upload`                   | irreversible | reconcilable        |     60s |    10s | canonical folder/name lookup      |
| `legal_full_ingestion` | `notebooklm_source_add`          | irreversible | non-reconcilable    |     30s |    10s | none                              |
| `legal_full_ingestion` | `sheets_catalog_append`          | irreversible | reconcilable        |     30s |    10s | effect key lookup in `Sheet1!I:I` |

All three migration-created control tables carry the Phase 1 ownership-block
grammar: `-- business-context: platform`, repeatable sorted `-- writer-binding:`
lines, `-- migration-source:
backend/db/migrations_v2/248_worker_effect_ledger.sql`, and no legacy singular
writer annotation. The exact bindings are:

| Table                      | Binding ID/kind                               | Workload/runtime                     | Operations and modes                                                                                                          |
| -------------------------- | --------------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `worker_effect_ledger`     | `legal-effect-projection` / `grant-fenced`    | `legal_full_ingestion`; `rag,worker` | `begin-attempt=active,draining;finish-effect=active,draining;prepare-effect=active,draining;reconcile-effect=active,draining` |
| `worker_effect_ledger`     | `legal-effect-resolution` / `static`          | `api`                                | `resolve-unknown`                                                                                                             |
| `worker_effect_ledger`     | `workflow-effect-projection` / `grant-fenced` | `workflow_queue`; `rag,worker`       | `begin-attempt=active,draining;finish-effect=active,draining;prepare-effect=active,draining;reconcile-effect=active,draining` |
| `worker_effect_ledger`     | `workflow-effect-resolution` / `static`       | `api`                                | `resolve-unknown`                                                                                                             |
| `worker_effect_attempts`   | `legal-effect-attempts` / `grant-fenced`      | `legal_full_ingestion`; `rag,worker` | `begin-attempt=active,draining;finish-effect=active,draining;reconcile-effect=active,draining`                                |
| `worker_effect_attempts`   | `legal-attempt-resolution` / `static`         | `api`                                | `resolve-unknown`                                                                                                             |
| `worker_effect_attempts`   | `workflow-effect-attempts` / `grant-fenced`   | `workflow_queue`; `rag,worker`       | `begin-attempt=active,draining;finish-effect=active,draining;reconcile-effect=active,draining`                                |
| `worker_effect_attempts`   | `workflow-attempt-resolution` / `static`      | `api`                                | `resolve-unknown`                                                                                                             |
| `worker_cutover_run_audit` | `cutover-audit-admin` / `static`              | `api`                                | `record-legal-run`; `record-workflow-run`                                                                                     |

For the two grant-fenced tables, each operation's interface list contains the
workload-specific Python wrapper and its workload-specific SQL callable, exactly
as follows. These are distinct symbols across bindings; none accepts a
workload-name argument:

| Operation          | Workflow interfaces                                                                                                   | Legal interfaces                                                                                                |
| ------------------ | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `begin-attempt`    | `backend.worker_plane.effect_ledger:begin_workflow_effect_attempt`, `sql:public.worker_begin_workflow_effect_attempt` | `backend.worker_plane.effect_ledger:begin_legal_effect_attempt`, `sql:public.worker_begin_legal_effect_attempt` |
| `finish-effect`    | `backend.worker_plane.effect_ledger:finish_workflow_effect`, `sql:public.worker_finish_workflow_effect`               | `backend.worker_plane.effect_ledger:finish_legal_effect`, `sql:public.worker_finish_legal_effect`               |
| `prepare-effect`   | `backend.worker_plane.effect_ledger:prepare_workflow_effect`, `sql:public.worker_prepare_workflow_effect`             | `backend.worker_plane.effect_ledger:prepare_legal_effect`, `sql:public.worker_prepare_legal_effect`             |
| `reconcile-effect` | `backend.worker_plane.effect_ledger:reconcile_workflow_effect`, `sql:public.worker_reconcile_workflow_effect`         | `backend.worker_plane.effect_ledger:reconcile_legal_effect`, `sql:public.worker_reconcile_legal_effect`         |

Every `prepare-effect`, `begin-attempt`, `finish-effect`, and
`reconcile-effect` interface above is grant-fenced. Its Python wrapper requires
the workload-specific domain-claim locator, `claim: ClaimContext`,
`expected_claimed_at`, and `expected_lease_expires_at`; the matching SQL
function receives the scalar workload-hard-coded runtime owner, generation,
build epoch, claim token, claimed-at stamp, and lease-expiry stamp. Inside the
same mutation transaction it locks the current ownership grant, the
workload-specific domain claim, the projection, and the current began-attempt
event when applicable in that order, then validates the live grant, the
immutable domain-claim stamp, and the attempt's internally consistent immutable
stamp before any DML. Finish additionally requires the attempt creator stamp to
equal the current claim stamp; reconcile may operate on the exact locked older
attempt only through a different current live claim after the ambiguity window.
Prepare and begin require the lease to be live at database time. Finish and
reconcile require that the same
claim remains live (or was renewed without changing its immutable owner,
generation, token, and claimed-at stamp), plus the exact expected attempt ID
and state. A check performed before opening that transaction is not authority.

Unknown resolution is deliberately not grant-fenced. The distinct static
`workflow-effect-resolution`/`workflow-attempt-resolution` bindings map only to
`backend.worker_plane.effect_ledger:resolve_workflow_unknown_effect` and
`sql:public.worker_resolve_workflow_unknown_effect`; the distinct legal
bindings map only to `backend.worker_plane.effect_ledger:resolve_legal_unknown_effect`
and `sql:public.worker_resolve_legal_unknown_effect`. Each protected wrapper
hard-codes its workload and requires exact effect key, expected attempt ID,
expected `outcome_unknown` state, actor, reason, terminal result, and provider
reference when confirmed. It accepts no `ClaimContext`, works while the
workload is `off` or drained, and runs only through the least-privilege static
management role, which has `EXECUTE` on the named resolution functions and no
direct table DML; worker roles cannot execute them.

`worker_effect_attempts` uses the same workload-specific grant-fenced
interfaces for its three automatic history-producing operations and omits
`prepare-effect`; its static resolution binding uses the matching protected
resolution interface. The static audit
binding maps `record-workflow-run` to
`backend.worker_plane.effect_ledger:record_workflow_cutover_run_audit` plus
`sql:public.worker_record_workflow_cutover_run_audit`, and maps
`record-legal-run` to
`backend.worker_plane.effect_ledger:record_legal_cutover_run_audit` plus
`sql:public.worker_record_legal_cutover_run_audit`. Those protected audit
wrappers hard-code workload identity. Shared serializers, row mappers, and state
validators behind every wrapper are pure/read-only; `EffectLedgerRepository` is
read-only and cannot be used as a generic SQL mutation entrypoint.

Migration 248 also extends the two existing Phase 1 bootstrap-table policies;
it does not create replacement bindings. Both catalog rows add
`backend/db/migrations_v2/248_worker_effect_ledger.sql` to their sorted
`migration_sources`, and each migration annotation reproduces the complete
post-extension binding:

- `worker_workload_ownership` keeps static `worker-grant-admin`/`api` and adds
  operation `set-mode` with exactly
  `backend.worker_plane.repository:WorkerPlaneRepository.set_ownership_mode`
  and `sql:public.worker_set_ownership_mode`.
- `worker_ownership_audit` keeps static `worker-ownership-audit`/`api` and adds
  both of those interfaces to its existing `append-audit` interface list.

`worker_set_ownership_mode(p_workload_name TEXT,
p_expected_runtime_owner TEXT, p_expected_generation BIGINT,
p_expected_version BIGINT, p_expected_mode TEXT, p_new_mode TEXT, p_actor TEXT,
p_reason TEXT) RETURNS worker_workload_ownership` is the sole SQL authority for
the drain-only `active -> draining` transition. It locks the grant, matches all
expected fields, preserves runtime owner, generation, and build floor,
increments only the version, and appends the actor/reason mode-change audit in
the same transaction. The Python method calls only this function. The protected
management role receives function `EXECUTE` but no raw DML on either table.

- [ ] Write migration tests for exactly three newly created tables: stable `worker_effect_ledger`, append-only `worker_effect_attempts`, and `worker_cutover_run_audit`, plus ownership-extension tests for the existing `worker_workload_ownership` and `worker_ownership_audit` tables. Cover all columns/constraints, including `worker_effect_attempts.runtime_owner`, `ownership_generation`, `claim_build_epoch`, `claim_token`, `claim_claimed_at`, and dispatch-time `claim_lease_expires_at`; projection indexes such as `(workload_name, state)`; attempt-history indexes such as `(effect_key, attempt_number, event_id)` and `(ownership_generation, event_kind)`; all exact workload-specific SQL functions; fixed row-lock order; SQLSTATE; append-only `UPDATE`/`DELETE` denial; non-destructive rollback; `business-context` plus every repeatable writer binding/interface/mode and sorted migration source above; migration uniqueness `246 -> 247 -> 248` with no other 248 file; and the shared G16 checker against a disposable real PostgreSQL schema, refreshed fixture, annotations, and catalog. Prove `worker_set_ownership_mode` is an exact expected-field CAS, permits only `active -> draining`, preserves owner/generation/build floor, increments version, and atomically audits; direct bootstrap-table DML and worker-role execution fail. Add guilt fixtures for the legacy singular writer annotation, one generic effect writer accepting `workload_name`, reused interfaces across the workflow/legal bindings, missing SQL/Python twins, a mode/interface operation-key mismatch, a missing 248 migration source, or a set-mode write outside the two extended static bindings.
- [ ] Write state-machine tests proving the stable effect key is independent of owner/generation/token/attempt; prepare is idempotent only for identical stable identity; a conflicting same key fails; concurrent begin has one winner; prior-generation attempt history remains immutable; retry creates a new attempt for the same projection only when canonical `DeliverySemantics` permits it; reconcilable retry requires `confirmed_absent`; non-reconcilable ambiguity cannot retry; confirmed cannot reopen; and stale finish/reconcile calls with an old claim stamp, expected attempt, or state fail without changing a newer attempt. Change ownership between prepare and dispatch and again before a late finish/reconcile to prove the in-transaction grant/claim recheck closes both races. Resolution requires the exact key, expected attempt, expected `outcome_unknown` state, actor, reason, terminal result, and provider reference when confirmed; it succeeds through the static API role even when the workload is `off` or drained and is denied to normal worker roles. Errors are sanitized; cutover rejects `prepared`, retryable `failed`, `attempting`, and delivery-semantics-blocking `outcome_unknown` rows.
- [ ] Extend catalog tests to require canonical `DeliverySemantics` object identity, no `ExternalEffectContract`, no `external_contract` serialized field or duplicate delivery enum, a resolvable `reconcile_symbol` for reconcilable effects, positive timeouts/margins, ledger fence checkpoints, and the exact six capability rows above.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/db/test_migration_248_worker_effect_ledger.py backend/tests/worker_plane/test_effect_ledger.py backend/tests/architecture/test_catalogs.py scripts/tests/test_check_table_ownership.py -q
  ```

  Expected: migration/types/repository are absent and current capabilities cannot express ambiguity contracts.

- [ ] Implement migration 248, `EffectState`, immutable `EffectRecord`, immutable `EffectAttemptEvent`, read-only `EffectLedgerRepository` queries, the eight grant-fenced workload mutation wrappers, two static workload resolution wrappers, two protected workload-specific cutover-audit wrappers, and the exact static `WorkerPlaneRepository.set_ownership_mode`/`worker_set_ownership_mode` pair named above. Each Python wrapper calls only its matching workload-specific SQL callable and hard-codes workload plus operation; no public or private mutating helper accepts a caller-selected workload. Grant-fenced wrappers require and transactionally revalidate the exact claim/lease stamp; static resolution and mode-change wrappers are management-plane operations and accept no `ClaimContext`. Reuse canonical `DeliverySemantics`; do not introduce an effect-contract type. Logs contain only key hash, fixed workload, effect, attempt number, generation, state, and error class.
- [ ] Extend the existing `SideEffectCapability` and `SIDE_EFFECT_CATALOG`; do not create a new registry. Update table ownership for all three new tables with `BusinessContext.PLATFORM` and the exact repeatable grant-fenced/static bindings above; do not serialize a singular runtime writer. Apply migrations through 248 to disposable PostgreSQL, regenerate `backend/tests/fixtures/schema_tables.txt` through the shared checker's explicit refresh mode, review the sorted diff, and keep the fixture staged with this migration.
- [ ] Refactor SQL row mapping, serialization, and catalog validation into pure/read-only helpers only; preserve Phase 0 imports and serialized fields. Add a source ratchet that rejects a generic effect-ledger writer, a `workload_name` selector on any effect mutation wrapper, SQL DML outside the exact cataloged wrapper/function pair, any automatic prepare/begin/finish/reconcile wrapper without the full `ClaimContext` plus immutable lease stamp and in-transaction grant/domain-claim validation, or any unbound set-mode/resolution path. Require exact Python/SQL symbol resolution, exact operation parity, and migration-source parity for both Phase 1 table extensions.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/db/test_migration_248_worker_effect_ledger.py backend/tests/worker_plane/test_effect_ledger.py backend/tests/architecture/test_catalogs.py backend/tests/db/test_migration_uniqueness.py -q
  pytest scripts/tests/test_check_table_ownership.py -q
  PYTHONPATH=. python ../../scripts/lint_migration_numbers.py
  PYTHONPATH=. python ../../scripts/lint_migration_rollback.py
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/check_table_ownership.py --migration-dir backend/db/migrations_v2 --schema-file backend/tests/fixtures/schema_tables.txt --refresh-schema-file --database-url "$TEST_DATABASE_URL" --catalog backend/architecture/catalogs/data/table_ownership.json
  PYTHONPATH=. python scripts/check_table_ownership.py --migration-dir backend/db/migrations_v2 --schema-file backend/tests/fixtures/schema_tables.txt --database-url "$TEST_DATABASE_URL" --catalog backend/architecture/catalogs/data/table_ownership.json
  ```

  Expected: all tests/checkers pass; 248 is unique/latest; invalid effect transitions and cutover barriers fail closed.

- [ ] Obtain a fresh SDD database/security review of migration 248, transition races, PII surface, catalog compatibility, and rollback; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/db/migrations_v2/248_worker_effect_ledger.sql apps/backend-rag/backend/tests/db/test_migration_248_worker_effect_ledger.py apps/backend-rag/backend/worker_plane/effects.py apps/backend-rag/backend/worker_plane/effect_ledger.py apps/backend-rag/backend/worker_plane/repository.py apps/backend-rag/backend/tests/worker_plane/test_effect_ledger.py apps/backend-rag/backend/architecture/catalogs/models.py apps/backend-rag/backend/architecture/catalogs/effects.py apps/backend-rag/backend/architecture/catalogs/data/table_ownership.json apps/backend-rag/backend/tests/fixtures/schema_tables.txt apps/backend-rag/backend/tests/architecture/test_catalogs.py apps/backend-rag/scripts/tests/test_check_table_ownership.py
  git commit -m "feat(worker-plane): add fenced external effect ledger" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 3: Enforce G15 at one reusable effect boundary

**Files:**

- Create: `apps/backend-rag/backend/worker_plane/effect_executor.py`
- Create: `apps/backend-rag/backend/worker_plane/claim_fence.py`
- Create: `apps/backend-rag/backend/tests/worker_plane/test_effect_executor.py`
- Create: `apps/backend-rag/scripts/resolve_worker_effect.py`
- Create: `apps/backend-rag/scripts/tests/test_resolve_worker_effect.py`
- Modify: `apps/backend-rag/backend/worker_plane/ownership_service.py`

`EffectExecutor.execute(mutations, capability, claim, domain_claim_id,
expected_claimed_at, expected_lease_expires_at, effect_key, business_ref,
dispatch, reconcile)` first prepares the stable projection through an injected
typed `EffectMutationPort`. The port instance is selected by adapter
construction, contains no `workload_name` parameter, and binds exactly one of
the cataloged workflow or legal wrapper families above. Prepare, begin,
finish, and reconcile each open one transaction that locks the Phase 1 grant,
the adapter's domain claim row, the effect projection, and the current
began-attempt event when applicable in that order; reads database time;
validates the live grant plus the full `ClaimContext`, immutable domain-claim
stamp, current lease stamp, exact expected attempt/state, and the locked
attempt's immutable recorded stamp; and only then performs its transition.
Immediately before dispatch,
`mutations.begin_attempt` commits `attempting` plus a new append-only `began`
event. Only then may the provider call run. Finish and reconciliation repeat
the same transaction-bound fence, so a stale caller or a late provider response
from an older attempt cannot overwrite a newer one. Finish requires the current
claim to be the attempt creator; reconciliation under a newer live claim may
only classify the exact locked older attempt after timeout plus margin. A timeout,
cancellation, transport break,
or process death after `attempting` is ambiguous. Recovery under a newly
claimed live domain row may convert the exact stale `attempting` attempt to
`outcome_unknown` after timeout plus margin before applying delivery semantics;
it never infers success from `prepared` or from an earlier attempt.

- [ ] Write tests for stable-key validation rejecting job ID/claim token/generation/attempt fragments; fixed grant -> domain claim -> effect -> current began-attempt lock order for prepare/begin/finish/reconcile as applicable; expired or changed claim lease; stale `runtime_owner`/generation/build/token/claimed-at stamp; a began-attempt whose recorded immutable claim stamp differs; ownership changing after prepare but before dispatch; ownership changing after dispatch but before late finish/reconcile; commit-before-dispatch; provider-idempotent same-key retry; reconcilable present/no-send; reconcilable absent/retry; reconciliation unavailable/unknown; non-reconcilable timeout/unknown/no retry; concurrent duplicate dispatch; cancellation; sanitized exceptions; immutable cross-generation attempt history; stale finish/reconcile after a newer attempt; and confirmed terminal reuse. Add source/behavior guilt cases proving a workflow port cannot mutate a legal effect, no mutation method accepts a workload selector, and a generic SQL-writing repository helper is absent.
- [ ] Write CLI tests for `list-unknown`, `show` by effect-key hash, and `resolve`. `resolve` requires exact key, expected attempt ID, expected `outcome_unknown` state, actor, reason, terminal result, provider reference when confirmed, and an exact allowlisted workload confirmation that selects one workload-bound static wrapper; it accepts no `ClaimContext`, remains usable when that workload is `off` or fully drained, and has no bulk mode. Prove the protected static API management role can execute only the named resolution function, while normal worker roles and direct table DML are denied.
- [ ] Add a source test proving every provider call routed through the executor depends on the atomic `ClaimFenceAdapter` plus the injected `EffectMutationPort.begin_attempt` path, which resolves only to `worker_begin_workflow_effect_attempt` or `worker_begin_legal_effect_attempt`; reject any separate check with a race window, caller-selected workload writer, or generic automatic retry wrapper around non-reconcilable dispatch.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/worker_plane/test_effect_executor.py scripts/tests/test_resolve_worker_effect.py -q
  ```

  Expected: executor and resolution CLI are absent; ambiguity cannot be represented end to end.

- [ ] Implement typed `ClaimFenceAdapter`, workload-bound `EffectMutationPort`, `EffectOutcome`, `EffectAmbiguous`, `EffectRetryBlocked`, and `EffectExecutor`. Construct the workflow and legal ports only from their exact cataloged wrappers. Keep `OwnershipService` names/signatures intact; add only the transaction-bound helper needed to validate the locked grant and workload-specific domain claim for every automatic prepare/begin/finish/reconcile transition.
- [ ] Implement the audited resolution CLI with read-only default, parameterized SQL, redacted JSON, explicit confirmation, and the protected static API management role. Its mutation path selects one of the two fixed static resolution wrappers and never calls a grant-fenced wrapper or accepts a workload selector inside the wrapper.
- [ ] Refactor canonical delivery-semantics strategies into pure private functions without creating separate ledgers, ownership services, contract models, delivery enums, or mutation helpers; rerun tests.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/worker_plane/test_effect_executor.py scripts/tests/test_resolve_worker_effect.py backend/tests/worker_plane/test_ownership_service.py -q
  ```

  Expected: tests pass; ambiguous non-reconcilable dispatch produces exactly one unknown row and no second provider call.

- [ ] Obtain a fresh SDD adversarial review of SEND/record crash windows, concurrency, retry rules, and operator resolution audit; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/worker_plane/effect_executor.py apps/backend-rag/backend/worker_plane/claim_fence.py apps/backend-rag/backend/tests/worker_plane/test_effect_executor.py apps/backend-rag/scripts/resolve_worker_effect.py apps/backend-rag/scripts/tests/test_resolve_worker_effect.py apps/backend-rag/backend/worker_plane/ownership_service.py
  git commit -m "feat(worker-plane): make external ambiguity explicit" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 4: Implement drain, adoption, activation, and reverse cutover

**Files:**

- Create: `apps/backend-rag/backend/worker_plane/cutover.py`
- Create: `apps/backend-rag/backend/tests/worker_plane/test_cutover.py`
- Create: `apps/backend-rag/scripts/worker_cutover.py`
- Create: `apps/backend-rag/scripts/tests/test_worker_cutover.py`
- Create: `apps/backend-rag/scripts/worker_live_control.py`
- Create: `apps/backend-rag/scripts/tests/test_worker_live_control.py`
- Create: `.github/workflows/worker-plane-live-control.yml`
- Modify: `apps/backend-rag/backend/worker_plane/repository.py`

`CutoverService` uses the existing repository/service and migration functions. It exposes `preflight`, `start_drain`, `inspect_barrier`, `activate_target`, and `reverse_cutover`. `start_drain` calls the static Phase 1 `worker-grant-admin` operation `WorkerPlaneRepository.set_ownership_mode`, which invokes only `worker_set_ownership_mode` through the protected management role and therefore preserves `runtime_owner`/generation. It never issues raw bootstrap-table DML. `activate_target` holds one asyncpg transaction, locks the grant, rechecks version/`runtime_owner`/generation/builds, and calls the workload adapter's locked `inventory_blockers`. The inventory must include live domain leases, unadopted/uncancelled pending runs, `prepared` intents, retryable `failed` effects, `attempting` effects, and delivery-semantics-blocking unknowns. Only an empty inventory permits atomic adoption/cancellation, `worker_cutover_run_audit`, and Phase 1 `worker_advance_ownership` to target `active` at generation N+1. Reverse cutover repeats the same protocol to return the legacy runtime owner at N+2.

`worker_cutover.py` remains disposable-only. `worker_live_control.py` is a separate fail-closed adapter over the same `OwnershipService`, guard functions, and `CutoverService`; it contains no duplicate SQL. It exposes one-workload `status`, `census`, `register-instance`, `retire-instance`, `arm`, `disarm`, `drain`, `barrier`, `activate`, and `reverse`. Every mutating call requires `environment`, the exact named primary/worker app pair for that environment, merged SHA plus `sha256:` digest, immutable release-gate path/hash, active-goal reference, an append-only admission row matching the intended mutation, `--expected-runtime-owner`, expected version/generation, actor/reason, evidence output, exact workload confirmation, and a database credential supplied only through protected stdin/environment. It also consumes the latest successful protected capability-workflow identity and immutable state as `--capability-run-id`, `--effective-grant-union-sha256`, and `--allowed-secret-symbols-sha256`; the admission row binds all three to the environment, apps, digest, and workload. Census registration and retirement use `--runtime-owner`; no command accepts a business-context value in either runtime-owner flag.

The capability and live-control workflows share an environment/workload concurrency group, so a capability mutation cannot race a grant/ownership mutation. Immediately before every mutating database CAS, never only at preflight, live control proves the capability run is still the latest successful protected run, recomputes the effective database-grant union (including direct grants, inherited membership, ownership, and `PUBLIC`) and the allowlisted secret-symbol set (names only, never values), compares both hashes with the capability artifact and admission row, and re-reads the immutable gate/admission binding. Missing, stale, excess, changed, or concurrently superseded state fails closed before CAS and leaves the source runtime owner active. It rejects `--all`, direct CLI mutation outside GitHub Actions, non-main ancestry, stale/mismatched gate, admission, or capability evidence, production credentials in staging, wrong workload order, wrong app, and missing expected state before opening the database. `.github/workflows/worker-plane-live-control.yml` has distinct static `worker-staging-control` and `worker-production-control` environment jobs and may invoke exactly one command for one workload per approved dispatch; it uploads redacted before/after/CAS/barrier/capability-re-audit evidence even on failure and never changes a Fly image, provider secret, or database grant.

- [ ] Write tests for stale expected version; wrong `runtime_owner`/generation; old/stale legacy or target build; active-to-draining generation preservation; new-claim rejection while draining; existing fenced-effect completion while draining; each blocker category independently (live lease, pending run, `prepared`, retryable `failed`, provider timeout/margin not elapsed, `attempting`, and blocking unknown); adapter lock/inventory failure; atomic adoption/cancellation; transaction rollback; activation N+1; reverse N+2; and no dual-active interval.
- [ ] Write disposable CLI tests for `preflight`, `drain`, `barrier`, `activate`, `reverse`, and `status`. Every mutating command requires workload, expected version/`runtime_owner`/generation, actor, reason, evidence output, explicit `--environment disposable`, nonempty `TEST_DATABASE_URL`, and matching confirmation. Any live staging/production app or database target and every all-workloads command are rejected. A `--dry-run` mode emits the later protected workflow input plan, including the three capability bindings, without executing it.
- [ ] Write fake-command/disposable-database tests for every `worker_live_control.py` command and both workflow environment jobs. Cover missing/wrong GitHub marker, pre-merge SHA, mutable tag, digest/gate/admission hash mismatch, missing/stale/wrong protected capability run ID, missing/mismatched effective-grant-union hash, missing/mismatched allowed-secret-symbol hash, effective privilege excess or omission, secret-symbol excess or omission, a newer/in-flight capability run, mutation between preflight and CAS, missing immediate recomputation/re-audit, wrong app pair/environment/DSN class, missing expected `runtime_owner`/version/generation, skipped workload, `--all`, stale census, guard arm before build floor, drain with a second active runtime owner, every barrier blocker, activation with a nonempty barrier, exact N -> N+1 -> N+2 forward/reverse history, audited disarm, CAS conflict, transaction rollback, redaction, capability re-audit evidence upload on success/failure, and proof that no image/secret/grant command can be constructed. No test contacts Fly or a live database.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/worker_plane/test_cutover.py scripts/tests/test_worker_cutover.py scripts/tests/test_worker_live_control.py -q
  ```

  Expected: cutover service/CLI are absent and no atomic drain/adopt/activate path exists.

- [ ] Implement typed `DrainEvidence`, `PendingRunDisposition`, `CutoverEvidence`, and `CutoverService`. Extend `OwnershipRepository` only with transaction access needed to call existing Phase 1 SQL authority on one connection; do not duplicate CAS SQL in Python.
- [ ] Calculate the barrier wait as the maximum of every locked catalog/domain lease expiry and every in-flight capability's provider timeout plus clock margin. Report all blocker categories without payloads; a generic ownership-only SQL assertion is insufficient.
- [ ] Implement the disposable-only CLI simulation with evidence hashes, a disposable database allowlist, and a default read-only status. It fails closed for any live staging or production target. Its dry-run output emits the canonical `worker-plane-live-control.yml` inputs for the exact protected-merged digest without credentials.
- [ ] Implement `worker_live_control.py` and `.github/workflows/worker-plane-live-control.yml` exactly as the protected contract above. Parse and validate every immutable artifact before opening the injected connection; require and bind the protected capability run ID plus effective-grant-union and allowed-secret-symbol hashes; acquire the shared capability/live-control concurrency group; immediately recompute and re-audit both effective-state hashes and latest-run status before every mutating CAS; call only canonical Phase 1/3 services; use typed arguments and parameterized SQL through those services; transport the live DSN by protected stdin/environment; append a mutation/result hash chain with the re-audit proof; and fail closed without a compensating blind mutation. In Phase 3, exercise every path only against fakes or disposable PostgreSQL and prove the workflow is manual, environment-protected, and not dispatchable by push/PR.
- [ ] Define the adapter protocol around locked `inventory_blockers` plus `apply_run_dispositions`. The adapter owns workload-specific domain-row locking and returns live leases, pending runs, and relevant effect blockers to the same transaction; queue workloads may return an empty scheduled-run subset, while G12 supplies a fixture implementation.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/worker_plane/test_cutover.py scripts/tests/test_worker_cutover.py scripts/tests/test_worker_live_control.py backend/tests/worker_plane/test_repository.py backend/tests/worker_plane/test_ownership_service.py -q
  ```

  Expected: all tests pass; forward and reverse transitions are monotonic, transactional, and blocked by any lease/effect/run condition.

- [ ] Obtain a fresh SDD transaction/reversibility review of lock order, generation behavior, complete blocker inventory, disposable-only CLI enforcement, protected live-control authorization, secret redaction, single-workload blast radius, and workflow environment separation; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/worker_plane/cutover.py apps/backend-rag/backend/tests/worker_plane/test_cutover.py apps/backend-rag/scripts/worker_cutover.py apps/backend-rag/scripts/tests/test_worker_cutover.py apps/backend-rag/scripts/worker_live_control.py apps/backend-rag/scripts/tests/test_worker_live_control.py .github/workflows/worker-plane-live-control.yml apps/backend-rag/backend/worker_plane/repository.py
  git commit -m "feat(worker-plane): add transactional workload cutover" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 5: Prove generation-independent schedule adoption and reverse cutover (G12)

**Files:**

- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_schedule_cutover_fixture.py`
- Create: `apps/backend-rag/backend/tests/fixtures/worker_plane/schedule_fixture.sql`
- Modify: `apps/backend-rag/backend/tests/worker_plane/test_cutover.py`

The isolated fixture table has logical uniqueness `UNIQUE(workload_name, scheduled_for)`, separate nullable ownership generation/claim fields, and no client data. It is created inside the disposable test transaction, not migration 248. The fixture enqueues a future run, cuts over before due, adopts it in the cutover transaction, executes one logical effect, reverses cutover, and repeats with another future run.

- [ ] Write the fixture test first and assert the run key excludes generation, queue ID, attempt, and claim token.
- [ ] Add forward cutover tests for one adopted future run, concurrent old/new scheduler attempts, and at most one business-identity effect.
- [ ] Add reverse cutover tests for generation N+2, dynamic legacy-owner claim within SLO, exactly one second logical run, zero lost claims, and zero cross-generation overlap.
- [ ] Add transaction-failure tests proving adoption/audit/ownership all roll back together.
- [ ] Run RED on Pro/CI with disposable PostgreSQL:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_schedule_cutover_fixture.py backend/tests/worker_plane/test_cutover.py -q
  ```

  Expected: the schedule adapter/fixture cannot atomically adopt a generation-independent run.

- [ ] Implement only the generic cutover-adapter changes needed by the fixture. Do not add notification scheduler production code in Phase 3.
- [ ] Refactor fixture helpers for deterministic clocks and concurrency barriers; rerun at least ten times to expose race failures.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  for run in 1 2 3 4 5 6 7 8 9 10; do
    PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_schedule_cutover_fixture.py -q || exit 1
  done
  ```

  Expected: every run passes; each scheduled time produces exactly one logical run/effect across forward and reverse ownership.

- [ ] Obtain a fresh SDD race/identity review of G12 evidence; fix and repeat the ten-run gate before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/tests/integration/worker_plane/test_schedule_cutover_fixture.py apps/backend-rag/backend/tests/fixtures/worker_plane/schedule_fixture.sql apps/backend-rag/backend/tests/worker_plane/test_cutover.py
  git commit -m "test(worker-plane): prove schedule adoption across rollback" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 6: Make workflow execution router-free and add its active adapter

**Files:**

- Create: `apps/backend-rag/backend/services/intel/workflow_ports.py`
- Create: `apps/backend-rag/backend/workers/adapters/workflow_active.py`
- Modify: `apps/backend-rag/backend/workers/registry.py`
- Modify: `apps/backend-rag/backend/services/workflow/queue.py`
- Modify: `apps/backend-rag/backend/services/workflow/executor.py`
- Modify: `apps/backend-rag/backend/services/workflow/chains/intel.py`
- Modify: `apps/backend-rag/backend/app/routers/intel.py`
- Modify: `apps/backend-rag/backend/app/setup/app_factory.py`
- Modify: `apps/backend-rag/backend/tests/services/workflow/test_queue.py`
- Create: `apps/backend-rag/backend/tests/services/workflow/test_worker_adapter.py`
- Create: `apps/backend-rag/backend/tests/services/workflow/test_intel_effects.py`

`workflow_ports.py` owns `IntelWorkflowServices`, constructed from `IntelApprovalService` and `IntelStagingService`. Both router and worker inject it. `intel.py` no longer imports `backend.app.routers.intel`. The Telegram effect key is exactly `workflow_queue:telegram_approval_notification:intel:{item_type}:{item_id}:approval-v1`; neither workflow job ID nor ownership generation appears. The active adapter builds only database, ownership, read-only effect-ledger queries, the workflow-bound `EffectMutationPort`, and workflow service dependencies, implements the workflow `ClaimFenceAdapter` and cutover blocker inventory against the real queue row, then calls the existing `run_worker` with fresh dynamic grant checks. The port exposes no workload selector and resolves only to the cataloged `workflow-effect-projection`/`workflow-effect-attempts` wrappers.

- [ ] Write a source/import test proving the workflow adapter and chain import no router, app factory, Qdrant, legal worker, or unrelated provider.
- [ ] Write behavior tests preserving chain registration, queue SKIP LOCKED, visibility heartbeat, retries, checkpoint/thread behavior, and valid legacy-owner execution.
- [ ] Write Telegram tests for stable effect key, atomic grant/queue/effect fence immediately before dispatch, expired or changed queue claim -> no send, confirmed send, timeout after dispatch -> one unknown, restart -> no second send, manually resolved failure -> terminal, and ownership change after claim -> no send.
- [ ] Write startup tests proving the worker active adapter cannot load while its runtime is off/shadow/draining or while the authoritative grant is legacy; the legacy lifespan continues to load until cutover.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/services/workflow/test_queue.py backend/tests/services/workflow/test_worker_adapter.py backend/tests/services/workflow/test_intel_effects.py -q
  ```

  Expected: router import is detected, active adapter is absent, and ambiguous Telegram dispatch can be retried without ledger proof.

- [ ] Implement dependency injection, active adapter, workflow `ClaimFenceAdapter`, workflow-bound `EffectMutationPort`, complete workflow blocker inventory, and `EffectExecutor` boundary. Every workflow execution injects that port explicitly; no generic mutation repository or caller-selected workload writer is reachable. Keep public router behavior and existing queue status/visibility semantics compatible.
- [ ] Change legacy lifespan wiring to consult the live grant dynamically: it runs while RAG owns active/draining and stops claiming on drain; it remains available for reverse cutover. Do not delete it.
- [ ] Refactor shared dependency creation into service modules, not router singletons, and rerun route/manifest snapshots.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/services/workflow backend/tests/setup backend/tests/unit/app/test_rag_proxy_intake_split.py -q
  PYTHONPATH=. python -c "import sys; import backend.workers.adapters.workflow_active; assert not any(m.startswith('backend.app.routers') for m in sys.modules)"
  ```

  Expected: tests and route snapshots pass; adapter is router-free; G15 Telegram cases produce no blind resend.

- [ ] Obtain a fresh SDD workflow/domain-boundary review of router removal, legacy compatibility, effect identity, and dynamic ownership; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/services/intel/workflow_ports.py apps/backend-rag/backend/workers/adapters/workflow_active.py apps/backend-rag/backend/workers/registry.py apps/backend-rag/backend/services/workflow/queue.py apps/backend-rag/backend/services/workflow/executor.py apps/backend-rag/backend/services/workflow/chains/intel.py apps/backend-rag/backend/app/routers/intel.py apps/backend-rag/backend/app/setup/app_factory.py apps/backend-rag/backend/tests/services/workflow
  git commit -m "feat(workflow): add fenced companion worker adapter" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 7: Pass workflow G3/G4/G15 failure injection

**Files:**

- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_workflow_lease_recovery.py`
- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_workflow_restart_matrix.py`
- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_workflow_effect_ambiguity.py`
- Create: `apps/backend-rag/scripts/verify_workflow_cutover.py`
- Create: `apps/backend-rag/scripts/tests/test_verify_workflow_cutover.py`
- Modify only if a failing gate proves a defect: `apps/backend-rag/backend/services/workflow/queue.py`
- Modify only if a failing gate proves a defect: `apps/backend-rag/backend/workers/adapters/workflow_active.py`
- Modify only if a failing gate proves a defect: `apps/backend-rag/backend/worker_plane/effect_executor.py`
- Modify only if a failing gate proves a defect: `apps/backend-rag/backend/worker_plane/cutover.py`

- [ ] Write G3 test: kill after claim/before ack; replacement cannot claim before `visible_at`, reclaims after expiry, and the stable Telegram effect has at most one dispatch or one unresolved unknown with zero automatic resend.
- [ ] Write G4 mixed-workload test: restart worker process, drop/recover PostgreSQL, timeout the workflow dependency, duplicate delivery, retain a stale legacy owner, and reconnect. Every accepted job ends `done`, pending with future visibility, or `failed`; no row disappears or stays `in_progress` beyond lease plus SLO.
- [ ] Write G15 process-boundary test that kills the old owner immediately after the fake Telegram provider observes request bytes and before confirmation write. Require exactly one `outcome_unknown`, drain activation blocked, replacement provider call count still one, and audited resolution before activation.
- [ ] Write verifier tests binding every result to workload, candidate digest, build, starting/ending generations, aggregate job counts, effect counts, and timestamps. Missing fault case or an unexplained count delta fails.
- [ ] Run RED on Pro/CI with disposable PostgreSQL:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_workflow_lease_recovery.py backend/tests/integration/worker_plane/test_workflow_restart_matrix.py backend/tests/integration/worker_plane/test_workflow_effect_ambiguity.py scripts/tests/test_verify_workflow_cutover.py -q
  ```

  Expected: at least one crash/reconnect/ambiguity scenario violates the required terminal-or-retry invariant or the verifier is absent.

- [ ] Implement only fixes exposed by the tests in the workflow adapter, queue, effect executor, or cutover barrier. Preserve queue semantics and do not begin legal work.
- [ ] Refactor deterministic fault controls and rerun the matrix ten times for concurrency stability.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  for run in 1 2 3 4 5 6 7 8 9 10; do
    PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_workflow_lease_recovery.py backend/tests/integration/worker_plane/test_workflow_restart_matrix.py backend/tests/integration/worker_plane/test_workflow_effect_ambiguity.py -q || exit 1
  done
  PYTHONPATH=. python scripts/verify_workflow_cutover.py --environment disposable --evidence /tmp/workflow-disposable-fault-evidence.json --output /tmp/workflow-disposable-fault-verified.json
  ```

  Expected: all repetitions and verifier pass G3/G4/G15 with zero lost job and no blind resend.

- [ ] Obtain a fresh SDD fault-model review of process kill timing, lease clocks, count conservation, and G15 observability; fix and repeat before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/tests/integration/worker_plane/test_workflow_lease_recovery.py apps/backend-rag/backend/tests/integration/worker_plane/test_workflow_restart_matrix.py apps/backend-rag/backend/tests/integration/worker_plane/test_workflow_effect_ambiguity.py apps/backend-rag/scripts/verify_workflow_cutover.py apps/backend-rag/scripts/tests/test_verify_workflow_cutover.py apps/backend-rag/backend/services/workflow/queue.py apps/backend-rag/backend/workers/adapters/workflow_active.py apps/backend-rag/backend/worker_plane/effect_executor.py apps/backend-rag/backend/worker_plane/cutover.py
  git commit -m "test(workflow): prove restart and ambiguity recovery" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 8: Prove workflow cutover readiness in disposable PostgreSQL before legal begins

**Files:**

- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_workflow_cutover_simulation.py`
- Modify: `apps/backend-rag/scripts/verify_workflow_cutover.py`
- Modify: `apps/backend-rag/scripts/tests/test_verify_workflow_cutover.py`
- Create: `docs/runbooks/workflow-worker-cutover.md`
- Create: `docs/architecture/worker-plane-phase3-workflow-checkpoint.md`
- Create: `.github/workflows/worker-plane-phase3.yml`

This task is a code-readiness gate, not a deployment gate. It applies migration 248 only to disposable PostgreSQL and runs the real cutover service/CLI against synthetic workflow rows and fake provider boundaries. All guards start and finish `UNARMED`; any temporary guard exercise is confined to the disposable database and audited. It does not deploy a candidate, read a live heartbeat, add a live secret/grant, or mutate staging/production. The runbook freezes the exact steps that production-rollout Task 2 must execute later on `nuzantara-worker-staging` using the exact protected-merged digest.

- [ ] Write integration tests for exact source commit/artifact binding, disposable schema head 248, all guards initially/finally unarmed, workflow-only synthetic rows, legal-capability exclusion, and rejection of any staging/production app, database, secret, grant, heartbeat, or ownership target.
- [ ] In disposable PostgreSQL, simulate: preflight -> worker shadow fixture -> legacy draining -> complete locked barrier -> worker active N+1 -> synthetic provider canary -> worker draining -> complete locked barrier -> legacy active N+2 -> legacy canary. Require G12, no overlap, no lost claim, and no unresolved blocker. Repeat the full simulation ten times with deterministic clocks.
- [ ] Verify aggregate synthetic queue counts, zero dual-owner/generation interval, zero unexplained job-count delta, no unresolved unknown, and every blocker category. End with the legacy fixture owner active at the newer generation and every guard unarmed; never edit a grant directly.
- [ ] Write the hard code-readiness checkpoint with source commit/artifact hash, disposable database identifier, migration/fixture hashes, generation history, commands, evidence hashes, synthetic canary results, fault verifier, final fixture state, dry-run reverse commands, and hashes of a fresh complete G9 candidate/comparison. Add a prominent deferred-live section requiring production-rollout Task 2 to deploy/migrate/arm/cut over/observe only the exact protected-merged digest and to collect real heartbeat/build-floor, scoped-grant/secret, budget, and full-cycle evidence there.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  test -n "${TEST_DATABASE_URL:-}"
  for run in 1 2 3 4 5 6 7 8 9 10; do
    PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_workflow_cutover_simulation.py -q || exit 1
  done
  PYTHONPATH=. python scripts/verify_workflow_cutover.py --environment disposable --database-url "$TEST_DATABASE_URL" --evidence /tmp/workflow-disposable-evidence.json --output /tmp/workflow-disposable-verified.json
  test -n "${PHASE0_DATABASE_URL:-}" && test -n "${PHASE0_REDIS_URL:-}" && test -n "${PHASE0_METRICS_URL:-}"
  PYTHONPATH=. python scripts/capture_worker_plane_baseline.py --protocol backend/architecture/baselines/phase0_probe_protocol.json --database-url "$PHASE0_DATABASE_URL" --redis-url "$PHASE0_REDIS_URL" --metrics-url "$PHASE0_METRICS_URL" --require-complete-g9 --output /tmp/worker-plane-phase3-workflow-g9-candidate.json
  PYTHONPATH=. python scripts/compare_worker_plane_baseline.py --baseline backend/architecture/baselines/phase0_snapshot.json --candidate /tmp/worker-plane-phase3-workflow-g9-candidate.json --exceptions backend/architecture/baselines/phase0_comparison_exceptions.json --output /tmp/worker-plane-phase3-workflow-g9-comparison.json
  PYTHONPATH=. python scripts/worker_phase3_preflight.py --workload legal_full_ingestion --database-url "$TEST_DATABASE_URL" --requires-workflow-checkpoint ../../docs/architecture/worker-plane-phase3-workflow-checkpoint.md --candidate-evidence /tmp/legal-code-candidate.json --output /tmp/legal-code-preflight.json
  ```

  Expected: ten disposable simulations, the workflow verifier, and the complete numeric API/RAG G9 comparison pass; live targets are rejected; legal code preflight exits 0 only after the committed workflow code-readiness checkpoint and its G9 hashes are valid.

- [ ] Obtain a fresh SDD operational review of disposable forward/reverse proof, complete blocker inventory, all-guards-unarmed final state, evidence determinism, and the explicit production-rollout Task 2 handoff. Resolve blockers, repeat affected simulations, and obtain rereview.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/tests/integration/worker_plane/test_workflow_cutover_simulation.py apps/backend-rag/scripts/verify_workflow_cutover.py apps/backend-rag/scripts/tests/test_verify_workflow_cutover.py docs/runbooks/workflow-worker-cutover.md docs/architecture/worker-plane-phase3-workflow-checkpoint.md .github/workflows/worker-plane-phase3.yml
  git commit -m "test(workflow): freeze disposable cutover readiness" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

### Hard Workflow-to-Legal Checkpoint

- [ ] Do not begin Task 9 until Task 8 is committed, its fresh SDD rereview passes, `verify_workflow_cutover.py` is green on checked disposable evidence, its canonical complete G9 comparison is green, all guards finish unarmed, and no synthetic workflow `prepared`, retryable `failed`, `attempting`, or delivery-semantics-blocking `outcome_unknown` row remains. Live staging evidence is neither required nor permitted at this checkpoint.

## Task 9: Make legal ingestion single-owner and deterministically identifiable

**Files:**

- Modify: `apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py`
- Modify: `apps/backend-rag/backend/services/ingestion/legal_full_ingestion_worker.py`
- Modify: `apps/backend-rag/backend/tests/services/ingestion/test_legal_ingestion_service.py`
- Modify: `apps/backend-rag/backend/tests/unit/services/ingestion/test_legal_ingestion_service.py`
- Modify: `apps/backend-rag/backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py`

Add this backward-compatible signature parameter:

```python
async def ingest_legal_document(
    ...,
    document_id: str | None = None,
    persist_source_to_drive: bool = True,
) -> dict[str, Any]: ...
```

The full worker calls it with `document_id=f"legal:{tipo}:{nomor}:{anno}"` and `persist_source_to_drive=False`. This prevents the service's internal Stage 1.5 Drive upload from duplicating the worker-controlled Drive stage. Existing API callers retain `True`. The deterministic ID feeds Qdrant chunk UUID derivation and KG uniqueness.

- [ ] Write tests proving default API behavior still uploads once, worker mode skips internal Drive, the outer worker owns exactly one Drive stage, stable document ID is identical across retry/generation, Qdrant chunk IDs remain deterministic, KG upsert remains conflict-safe, and no job ID/attempt/generation contaminates identity.
- [ ] Write a source test that rejects any second Drive upload call in the worker path and requires `persist_source_to_drive=False` at its service call.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/services/ingestion/test_legal_ingestion_service.py backend/tests/unit/services/ingestion/test_legal_ingestion_service.py backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py -q
  ```

  Expected: parameter is absent, generated document identity varies by time, and worker path can upload Drive twice.

- [ ] Implement the parameter and stable identity with no other pipeline change. Keep public/API defaults backward compatible.
- [ ] Refactor the worker's legal identity builder into pure `legal_document_identity(tipo, nomor, anno) -> str` with normalized validated components.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/services/ingestion/test_legal_ingestion_service.py backend/tests/unit/services/ingestion/test_legal_ingestion_service.py backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py -q
  ```

  Expected: tests pass; API still persists its source once; full worker uses stable identity and one controlled Drive stage.

- [ ] Obtain a fresh SDD legal-pipeline review of compatibility, deterministic identity, and duplicate Drive prevention; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py apps/backend-rag/backend/services/ingestion/legal_full_ingestion_worker.py apps/backend-rag/backend/tests/services/ingestion/test_legal_ingestion_service.py apps/backend-rag/backend/tests/unit/services/ingestion/test_legal_ingestion_service.py apps/backend-rag/backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py
  git commit -m "fix(legal): make worker ingestion identity deterministic" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 10: Bind every legal provider stage to its capability and add the active adapter

**Files:**

- Create: `apps/backend-rag/backend/workers/adapters/legal_active.py`
- Create: `apps/backend-rag/backend/services/ingestion/legal_pipeline_ports.py`
- Modify: `apps/backend-rag/backend/workers/registry.py`
- Modify: `apps/backend-rag/backend/services/ingestion/legal_full_ingestion_worker.py`
- Modify: `apps/backend-rag/backend/services/integrations/sheets_service.py`
- Modify: `apps/backend-rag/backend/app/setup/app_factory.py`
- Create: `apps/backend-rag/backend/tests/services/ingestion/test_legal_effect_contracts.py`
- Create: `apps/backend-rag/backend/tests/services/ingestion/test_legal_worker_adapter.py`
- Create: `apps/backend-rag/backend/tests/unit/services/integrations/test_sheets_service.py`

Legal effect keys are exact stable identities:

```text
legal_full_ingestion:qdrant_index:legal:{tipo}:{nomor}:{anno}
legal_full_ingestion:knowledge_graph_upsert:legal:{tipo}:{nomor}:{anno}
legal_full_ingestion:drive_upload:legal:{tipo}:{nomor}:{anno}
legal_full_ingestion:notebooklm_source_add:legal:{tipo}:{nomor}:{anno}:{notebook_id}
legal_full_ingestion:sheets_catalog_append:legal:{tipo}:{nomor}:{anno}:{sheet_id}
```

`legal_pipeline_ports.py` defines separate injected `QdrantIndexOperation` and `KnowledgeGraphUpsertOperation` protocols plus their independently testable results. A composite ingestion call may prepare shared artifacts, but it cannot hide both durable writes behind one callback or mark one operation confirmed because the other succeeded. Drive reconciliation uses the existing canonical filename/folder lookup. Qdrant/KG retries reuse deterministic IDs. NLM remains non-reconcilable: timeout/cancel after dispatch becomes unknown and blocks progress. Sheets stores the effect key in column I, calls `find_row_by_value` on `Sheet1!I:I`, and appends A:I only after confirmed absence.

- [ ] Write capability tests for all five exact keys, canonical `DeliverySemantics` lookup, atomic claim fence, separate injected Qdrant and KG calls/results, failure of either operation not confirming the other, Qdrant same-ID retry, KG conflict-safe retry, Drive found/no upload, Drive absent/one upload, NLM timeout/unknown/no retry, Sheets existing/no append, Sheets absent/one append with column I key, and missing provider dependency failing readiness before claim.
- [ ] Write adapter import/startup tests proving no router/app factory import, lazy legal/Qdrant/provider load only when legal is selected active, workflow remains active independently, and legal cannot activate before the hard checkpoint.
- [ ] Write legacy-path tests proving RAG legal owner stops new claims in draining, may finish fenced stages, and can dynamically resume after reverse cutover.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/services/ingestion/test_legal_effect_contracts.py backend/tests/services/ingestion/test_legal_worker_adapter.py backend/tests/unit/services/integrations/test_sheets_service.py backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py -q
  ```

  Expected: provider stages bypass the ledger, Sheets has no stable-key dedupe, and active legal adapter is absent.

- [ ] Route each durable provider operation through its own `EffectExecutor` call with the explicitly injected legal-bound `EffectMutationPort`; do not wrap status-only database updates as external effects and do not collapse Qdrant plus KG into one effect. The port exposes no workload selector and resolves only to the cataloged `legal-effect-projection`/`legal-effect-attempts` wrappers. A required provider missing/config error becomes a typed retry/terminal state rather than a silent successful skip.
- [ ] Implement `legal_active.py` with lazy dependency construction, independent Qdrant/KG ports, the legal `ClaimFenceAdapter`, legal-bound `EffectMutationPort`, complete legal blocker inventory, and existing `run_worker`; extend the registry only after the workflow disposable code-readiness checkpoint and legal code preflight pass. Shared effect-ledger helpers remain pure/read-only and cannot perform DML.
- [ ] Derive the minimal legal database-grant requirements from `get_workload_spec("legal_full_ingestion").database_grant_profile` and the provider-secret symbols from the explicit injected dependencies of `legal_active.py`; record only those names in sanitized dry-run evidence and the rollout handoff, without creating another manifest or applying them anywhere. Tests reject excess API/RAG, workflow-unrelated, or absent-provider capability. Actual staging grants/secrets are applied only by production-rollout Task 2 on the exact protected-merged digest.
- [ ] Refactor provider operations into separately injected typed ports and reconciliation functions referenced by `SideEffectCapability.reconcile_symbol`; preserve canonical `DeliverySemantics` and add no parallel contract field or enum.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/services/ingestion/test_legal_effect_contracts.py backend/tests/services/ingestion/test_legal_worker_adapter.py backend/tests/unit/services/integrations/test_sheets_service.py backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py -q
  PYTHONPATH=. python -c "import sys; import backend.workers.adapters.legal_active; assert not any(m.startswith('backend.app.routers') for m in sys.modules)"
  ```

  Expected: tests pass; every provider stage obeys its declared contract; NLM ambiguity cannot auto-retry; adapter remains lazy/router-free.

- [ ] Obtain a fresh SDD legal-effects review of all five capability implementations, reconciliation evidence, declared secret/grant scope, no-live-application enforcement, and legacy rollback path; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/workers/adapters/legal_active.py apps/backend-rag/backend/services/ingestion/legal_pipeline_ports.py apps/backend-rag/backend/workers/registry.py apps/backend-rag/backend/services/ingestion/legal_full_ingestion_worker.py apps/backend-rag/backend/services/integrations/sheets_service.py apps/backend-rag/backend/app/setup/app_factory.py apps/backend-rag/backend/tests/services/ingestion/test_legal_effect_contracts.py apps/backend-rag/backend/tests/services/ingestion/test_legal_worker_adapter.py apps/backend-rag/backend/tests/unit/services/integrations/test_sheets_service.py apps/backend-rag/backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py
  git commit -m "feat(legal): fence companion provider effects" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 11: Pass legal faults and prove reverse cutover in disposable PostgreSQL

**Files:**

- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_legal_lease_recovery.py`
- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_legal_restart_matrix.py`
- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_legal_effect_ambiguity.py`
- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_legal_cutover_simulation.py`
- Create: `apps/backend-rag/scripts/verify_legal_cutover.py`
- Create: `apps/backend-rag/scripts/tests/test_verify_legal_cutover.py`
- Create: `docs/runbooks/legal-worker-cutover.md`
- Create: `docs/architecture/worker-plane-phase3-legal-checkpoint.md`
- Modify only if a failing gate proves a defect: `apps/backend-rag/backend/services/ingestion/legal_full_ingestion_worker.py`
- Modify only if a failing gate proves a defect: `apps/backend-rag/backend/workers/adapters/legal_active.py`
- Modify only if a failing gate proves a defect: `apps/backend-rag/backend/worker_plane/effect_executor.py`
- Modify only if a failing gate proves a defect: `apps/backend-rag/backend/worker_plane/cutover.py`

- [ ] Write G3 lease tests: kill after legal claim; no pre-expiry reclaim; post-expiry reclaim; deterministic Qdrant/KG result; Drive/Sheets reconciliation; NLM ambiguity produces one unknown and no retry.
- [ ] Write G4 mixed tests: restart worker, disconnect/reconnect PostgreSQL, timeout each provider, duplicate delivery, stale legacy owner, and Qdrant dependency outage. Every accepted legal job becomes complete, retryable/visible, failed/dead under existing schema, or explicitly blocked by unknown; none disappears or remains claimed beyond lease/SLO.
- [ ] Write G15 process kill after each provider observes dispatch but before confirmation. Assert provider-idempotent same key, reconcilable lookup-before-retry, and NLM unknown/no second call. Cutover barrier must reject the unresolved NLM row.
- [ ] Write verifier tests for count conservation, exact capability cases, source commit/artifact/generation binding, forward N+1, reverse N+2, no cross-generation overlap, and one public synthetic legal PDF fixture with no document body in evidence. The verifier rejects live staging/production targets and does not accept live state as Phase 3 exit evidence.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_legal_lease_recovery.py backend/tests/integration/worker_plane/test_legal_restart_matrix.py backend/tests/integration/worker_plane/test_legal_effect_ambiguity.py backend/tests/integration/worker_plane/test_legal_cutover_simulation.py scripts/tests/test_verify_legal_cutover.py -q
  ```

  Expected: at least one provider ambiguity/reconnect case violates contract or verifier is absent.

- [ ] Implement only fixes exposed by legal fault tests. Repeat the full matrix ten times.
- [ ] In disposable PostgreSQL, simulate legal shadow fixture -> legacy drain -> barrier -> worker active N+1 -> public-fixture canary -> worker drain -> barrier -> legacy active N+2 -> legacy canary. Resolve or deliberately fail the simulation if any non-reconcilable unknown exists. Repeat the full forward/reverse simulation ten times with fake provider boundaries and deterministic clocks.
- [ ] Require the workflow disposable checkpoint remains valid throughout the legal simulation, synthetic queue age stays within its catalog SLO, effects reconcile, no job-count delta exists, every guard finishes unarmed, and the dry-run reverse command remains valid. Reject any attempt to add a live grant/secret, read a live heartbeat, deploy/migrate staging, or mutate staging/production ownership.
- [ ] Write `worker-plane-phase3-legal-checkpoint.md` as a code-readiness handoff: bind it to source commit/artifact, disposable evidence, and fresh complete G9 candidate/comparison hashes, then explicitly defer staging deploy, migration 248, guard arming, scoped grants/secrets, live compatibility-floor heartbeats, forward/reverse cutover, canaries, budget checks, and full-cycle observation to production-rollout Task 2 on the exact protected-merged digest.
- [ ] Refactor deterministic fault controls and evidence schema, then run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  for run in 1 2 3 4 5 6 7 8 9 10; do
    PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_legal_lease_recovery.py backend/tests/integration/worker_plane/test_legal_restart_matrix.py backend/tests/integration/worker_plane/test_legal_effect_ambiguity.py backend/tests/integration/worker_plane/test_legal_cutover_simulation.py -q || exit 1
  done
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/verify_legal_cutover.py --environment disposable --database-url "$TEST_DATABASE_URL" --evidence /tmp/legal-disposable-evidence.json --output /tmp/legal-disposable-verified.json
  test -n "${PHASE0_DATABASE_URL:-}" && test -n "${PHASE0_REDIS_URL:-}" && test -n "${PHASE0_METRICS_URL:-}"
  PYTHONPATH=. python scripts/capture_worker_plane_baseline.py --protocol backend/architecture/baselines/phase0_probe_protocol.json --database-url "$PHASE0_DATABASE_URL" --redis-url "$PHASE0_REDIS_URL" --metrics-url "$PHASE0_METRICS_URL" --require-complete-g9 --output /tmp/worker-plane-phase3-legal-g9-candidate.json
  PYTHONPATH=. python scripts/compare_worker_plane_baseline.py --baseline backend/architecture/baselines/phase0_snapshot.json --candidate /tmp/worker-plane-phase3-legal-g9-candidate.json --exceptions backend/architecture/baselines/phase0_comparison_exceptions.json --output /tmp/worker-plane-phase3-legal-g9-comparison.json
  ```

  Expected: ten matrices, disposable forward/reverse simulations, and the complete numeric API/RAG G9 comparison pass; the verifier shows no lost job, overlap, blind resend, or unresolved ambiguity; all guards finish unarmed and every live target is rejected.

- [ ] Obtain a fresh SDD fault/operations review of every provider case, disposable reverse simulation, workflow non-regression, all-guards-unarmed final state, live-target rejection, and production-rollout Task 2 handoff; fix, repeat affected evidence, and rereview.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/tests/integration/worker_plane/test_legal_lease_recovery.py apps/backend-rag/backend/tests/integration/worker_plane/test_legal_restart_matrix.py apps/backend-rag/backend/tests/integration/worker_plane/test_legal_effect_ambiguity.py apps/backend-rag/backend/tests/integration/worker_plane/test_legal_cutover_simulation.py apps/backend-rag/scripts/verify_legal_cutover.py apps/backend-rag/scripts/tests/test_verify_legal_cutover.py docs/runbooks/legal-worker-cutover.md docs/architecture/worker-plane-phase3-legal-checkpoint.md apps/backend-rag/backend/services/ingestion/legal_full_ingestion_worker.py apps/backend-rag/backend/workers/adapters/legal_active.py apps/backend-rag/backend/worker_plane/effect_executor.py apps/backend-rag/backend/worker_plane/cutover.py
  git commit -m "test(legal): prove disposable cutover and provider recovery" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 12: Enforce the complete Phase 3 exit verifier and CI gate

**Files:**

- Create: `apps/backend-rag/scripts/verify_worker_plane_phase3.py`
- Create: `apps/backend-rag/scripts/tests/test_verify_worker_plane_phase3.py`
- Modify only if exit-verifier integration exposes a defect: `apps/backend-rag/scripts/worker_live_control.py`
- Modify only if exit-verifier integration exposes a defect: `apps/backend-rag/scripts/tests/test_worker_live_control.py`
- Modify: `.github/workflows/worker-plane-phase3.yml`
- Modify only if exit-verifier integration exposes a defect: `.github/workflows/worker-plane-live-control.yml`
- Create: `docs/architecture/worker-plane-phase3-exit.md`

The verifier requires previous phase verifiers, the recorded current-goal authorization reference, unique migration 248, live-schema G16 proof on disposable PostgreSQL, catalog capabilities, effect state machine, G3, G4, G12, G15, workflow and legal disposable code-readiness checkpoints, forward/reverse simulations for both, monotonic synthetic generation histories, exact source commit/artifact hash, declared least-privilege grant/secret requirements, live-target rejection, G13/G14 code/CI budgets, and both hard-checkpoint Phase 0 G9 comparisons with complete numeric API/RAG startup/RSS/connection/error maps and no unapproved >10% regression. It also requires zero overlap, conserved jobs, all guards unarmed at exit, and zero unresolved blockers. It must require the already-created fake-tested protected `worker-plane-live-control.yml` contract: immutable protected capability-workflow run ID, effective-grant-union hash, allowed-secret-symbol hash, admission binding, shared concurrency group, immediate recomputation/re-audit before every mutating CAS, stale/missing/excess/TOCTOU rejection, and redacted success/failure evidence. The handoff defers every live staging action to production-rollout Task 2 on the exact protected-merged digest.

- [ ] Write verifier tests for every missing/stale/skipped gate; wrong workload order; another commit/artifact; generation decrement/gap inconsistent with audit; unresolved attempting; unresolved non-reconcilable unknown; lost job; duplicate business effect; absent reverse synthetic canary; absolute-budget or G9 relative regression; armed final guard; live staging/production target; missing full G16 disposable-schema evidence; missing/unsafe live-control workflow contract; absent capability run/grant-union/secret-symbol binding; stale, missing, excess, or TOCTOU capability state; no immediate pre-CAS re-audit proof; missing rollout handoff; or legal evidence before workflow checkpoint.
- [ ] Implement a fixed allowlisted verifier that validates evidence hashes and independently queries only disposable aggregate state. Prose and live environment state cannot satisfy a Phase 3 gate.
- [ ] Add CI for migration 248, catalogs/table ownership, effect executor, cutover, ten-run schedule fixture, workflow/legal focused suites, fault matrices, route/import boundaries, prior phase verifiers, Ruff, migration linters, marker scan, and diff check.
- [ ] Run RED before implementing the verifier:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_verify_worker_plane_phase3.py -q
  ```

  Expected: verifier import fails.

- [ ] Refactor verifier result composition into deterministic typed records and keep disposable database probes isolated.
- [ ] Run the complete GREEN gate on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/architecture backend/tests/worker_plane backend/tests/services/workflow backend/tests/services/ingestion backend/tests/integration/worker_plane -q
  pytest scripts/tests/test_worker_phase3_preflight.py scripts/tests/test_resolve_worker_effect.py scripts/tests/test_worker_cutover.py scripts/tests/test_worker_live_control.py scripts/tests/test_verify_workflow_cutover.py scripts/tests/test_verify_legal_cutover.py scripts/tests/test_verify_worker_plane_phase3.py scripts/tests/test_check_table_ownership.py -q
  PYTHONPATH=. python ../../scripts/lint_migration_numbers.py
  PYTHONPATH=. python ../../scripts/lint_migration_rollback.py
  PYTHONPATH=. python scripts/check_event_fanout.py
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/check_table_ownership.py --migration-dir backend/db/migrations_v2 --schema-file backend/tests/fixtures/schema_tables.txt --database-url "$TEST_DATABASE_URL" --catalog backend/architecture/catalogs/data/table_ownership.json
  PYTHONPATH=. python scripts/verify_worker_plane_phase3.py --environment disposable --database-url "$TEST_DATABASE_URL" --workflow-evidence /tmp/workflow-disposable-evidence.json --legal-evidence /tmp/legal-disposable-evidence.json --g9-baseline backend/architecture/baselines/phase0_snapshot.json --g9-protocol backend/architecture/baselines/phase0_probe_protocol.json --g9-exceptions backend/architecture/baselines/phase0_comparison_exceptions.json --workflow-g9-candidate /tmp/worker-plane-phase3-workflow-g9-candidate.json --workflow-g9-comparison /tmp/worker-plane-phase3-workflow-g9-comparison.json --legal-g9-candidate /tmp/worker-plane-phase3-legal-g9-candidate.json --legal-g9-comparison /tmp/worker-plane-phase3-legal-g9-comparison.json --output /tmp/worker-plane-phase3-final.json
  actionlint ../../.github/workflows/worker-plane-phase3.yml ../../.github/workflows/worker-plane-live-control.yml
  ruff check backend/architecture backend/worker_plane backend/workers backend/services/workflow backend/services/ingestion backend/services/intel/workflow_ports.py scripts
  python - <<'PY'
  from pathlib import Path
  roots = [Path('backend/worker_plane'), Path('backend/workers'), Path('../../docs/architecture/worker-plane-phase3-exit.md')]
  markers = ('TO'+'DO', 'T'+'BD', 'FIX'+'ME', 'NotImplemented'+'Error')
  hits = [(str(p), m) for root in roots for p in ([root] if root.is_file() else root.rglob('*')) if p.is_file() for m in markers if m in p.read_text(errors='ignore')]
  assert not hits, hits
  PY
  git diff --check
  ```

  Expected: all commands exit 0; verifier reports every required gate pass; marker scan has no hits; diff check is silent.

- [ ] Obtain a fresh SDD whole-phase evidence review; resolve every blocking gap, rerun full verifier, and obtain passing rereview.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/scripts/verify_worker_plane_phase3.py apps/backend-rag/scripts/tests/test_verify_worker_plane_phase3.py apps/backend-rag/scripts/worker_live_control.py apps/backend-rag/scripts/tests/test_worker_live_control.py .github/workflows/worker-plane-phase3.yml .github/workflows/worker-plane-live-control.yml docs/architecture/worker-plane-phase3-exit.md
  git commit -m "ci(worker-plane): enforce phase three readiness gates" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 13: Run the independent Phase 3 review panel

**Files:**

- Create: `scripts/review_sets/phase-3.json`
- Create: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/00-review-brief.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/00-review-packet.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/input-manifest.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/freeze-receipt.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/01-fable-5-architecture.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/01-fable-5-architecture.raw.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/01-fable-5-architecture.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/01-fable-5-architecture.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/02-gemini-3.1-pro-high.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/02-gemini-3.1-pro-high.raw.txt`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/02-gemini-3.1-pro-high.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/02-gemini-3.1-pro-high.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/03-glm-5.2-adversarial.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/03-glm-5.2-adversarial.raw.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/03-glm-5.2-adversarial.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/03-glm-5.2-adversarial.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/<attempt-id>/99-disposition.md`
- Modify as findings require: only Phase 3 implementation/test/docs files listed above

The canonical Git-object review-input projection contains the current-goal authorization reference, complete patch and verifier evidence, migration 248 SQL/hash, disposable live-schema G16 proof, and the exact `business_context` plus sorted repeatable `writer_bindings` and `migration_sources` for all three new control tables and the two extended Phase 1 bootstrap tables. Its source-ratchet evidence proves distinct workflow/legal grant-fenced automatic wrappers, distinct static resolution wrappers, the static `worker-grant-admin` set-mode operation and matching `worker-ownership-audit` interface, exact operation-mode/interface key parity, no legacy singular writer field, no caller-selected workload writer, full in-transaction claim/lease/attempt fencing, and only pure/read-only shared helpers. It also contains the capability table, effect transition proof, workflow/legal compatibility-floor algorithms, every disposable forward/reverse generation and audit hash, both complete G9 candidate/comparison artifact hashes, G3/G4/G9/G12/G15 raw evidence, count conservation, exact source commit/artifact hash, declared grant/secret requirements, all-guards-unarmed proof, fake-tested `worker_live_control.py` plus `worker-plane-live-control.yml` contract, immutable protected capability-workflow run/grant-union/allowed-secret-symbol bindings, shared-concurrency and immediate pre-CAS re-audit proof with stale/missing/excess/TOCTOU failures, live-target rejection, production-rollout Task 2 handoff, rollback simulations, and no-client-data declaration. The brief is the sole `role=instructions` entry. Base/head/clean-status proof and transport hashes stay in external receipts; raw/normalized reviews, invocation receipts, packet objects, and disposition are excluded attestations. Initial panel reviews are independent. Every seat uses exactly `# Verdict` (verdict plus confidence), `# Blocking findings`, `# Important findings`, `# What survives review`, `# Required amendments`, and `# Falsification test`, with no other level-one heading.

- [ ] Write and test `scripts/review_sets/phase-3.json` as the canonical newline-terminated JSON object `{"covered":[...]}`, with a raw-UTF-8-sorted, duplicate-free path array covering every committed Phase 3 implementation, test, catalog, migration, and non-generated evidence path. Exclude `00-review-brief.md`, which is the sole instructions entry, and all generated packet/review/receipt/disposition attestations. The freezer loads the set only from the recorded source commit and rejects missing, non-canonical, unsorted, duplicate, nonexistent, or instructions-overlapping paths. Commit the set and brief with the Phase 3 implementation/evidence before selecting `H0`.
- [ ] Commit the Phase 3 implementation/evidence, require clean tracked status, and freeze the canonical projection from Git objects with the checked shared freezer:

  ```bash
  REPO_ROOT="$(git rev-parse --show-toplevel)"
  PYTHON="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
  REVIEW_STORE="${WORKER_PLANE_REVIEW_STORE:-${HOME}/.local/share/nuzantara/worker-plane-review-store}"
  case "$REVIEW_STORE" in /*) ;; *) echo "WORKER_PLANE_REVIEW_STORE must be absolute" >&2; exit 2 ;; esac
  case "$REVIEW_STORE" in "$REPO_ROOT"|"$REPO_ROOT"/*) echo "review store must be outside the repository" >&2; exit 2 ;; esac
  UPSTREAM="$(git rev-parse 'origin/main^{commit}')"
  H0="$(git rev-parse 'HEAD^{commit}')"
  BASE="$(git merge-base "$UPSTREAM" "$H0")"
  test -z "$(git status --porcelain --untracked-files=no)"
  FREEZE_JSON="$("$PYTHON" scripts/freeze_worker_plane_review.py freeze \
    --repo "$REPO_ROOT" --upstream "$UPSTREAM" --base "$BASE" --source "$H0" \
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/00-review-brief.md \
    --covered-set phase-3 --output-store "$REVIEW_STORE")"
  PACKET_SHA256="$(printf '%s\n' "$FREEZE_JSON" | "$PYTHON" -c 'import json, sys; print(json.load(sys.stdin)["packet_sha256"])')"
  ```

- [ ] Dispatch Fable as architecture/transaction/reversibility judge, Gemini as constructive distributed-systems/operations reviewer, and GLM as adversarial reviewer through the one checked canonical launcher:

  ```bash
  ATTEMPT_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  REVIEW_ATTEMPT_DIR="docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/attempts/$ATTEMPT_ID"
  "$PYTHON" scripts/launch_worker_plane_review_panel.py \
    --frozen-review "$REVIEW_STORE/sha256/$PACKET_SHA256" \
    --output-dir "$REVIEW_ATTEMPT_DIR"
  ```

  The launcher reads the immutable content-addressed packet once into one byte buffer and sends identical bytes over stdin to all three subprocesses from a newly created empty `0700` cwd, without a prompt argument or checkout tools. It uses the master plan's exact absolute Claude executable and no-tool safe-mode argv for Fable/GLM, the committed hash-validated GLM route config and keychain `ANTHROPIC_AUTH_TOKEN` isolation, and absolute `/Users/balizero/.local/bin/agy` with exact plan/sandbox argv for Gemini. It atomically preserves raw stdout, stderr, immutable invocation receipts, and launcher-normalized Markdown before any cross-seat visibility. Every receipt has a unique `launcher_invocation_uuid`, common `input_manifest_sha256`, external `packet_sha256`, exact executable/config/argv/raw hashes, and nullable `provider_session_id`/`reported_model` checked only when emitted; requested route is not provider declaration. Each normalized review repeats only `input_manifest_sha256` and preserves the unedited six-heading body; no manual normalization follows launch.

- [ ] Classify every finding in `99-disposition.md` as Blocking, Important, or Advisory, with accepted/rejected, concrete evidence, fixing commit, affected workload, and rereview state. Every non-`None` item under `# Blocking findings` maps to severity `Blocking`. Rejected findings require repository, CI, or disposable-database evidence; Phase 3 never obtains live-environment evidence.
- [ ] Fix each accepted Blocking or Important finding through a new failing test, minimal implementation, focused and full Phase 3 rerun, and one atomic conventional commit with the required coauthor. Any covered implementation, test, instruction, or non-generated evidence byte/role/path change produces a new projection and reruns all three reviewers; targeted rereview alone is invalid. Changes only to packet/raw/normalized review, invocation receipt, or disposition artifacts with equal `projection(H1) == projection(H0)` require deterministic integrity revalidation, never a recursive model rerun. A fix affecting workflow requires rechecking the legal dependency and both disposable readiness records.
- [ ] Repeat fix -> verify -> full three-seat rereview until all reviewers return `GO` or `GO-WITH-CHANGES` without a blocking condition and no Blocking/Important row is unresolved.
- [ ] Complete the disposition, commit exactly the fresh attempt directory as `H1`, compare the covered/instructions projection to `H0`, and only then validate integrity on Pro/CI. The checker rejects mutable files that do not equal regular Git blobs at `H1`:

  ```bash
  "${EDITOR:-vi}" "$REVIEW_ATTEMPT_DIR/99-disposition.md"
  git add -- "$REVIEW_ATTEMPT_DIR"
  git commit -m "docs(worker-plane): record phase three independent review" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  H1="$(git rev-parse 'HEAD^{commit}')"
  "$PYTHON" scripts/freeze_worker_plane_review.py compare-projection \
    --repo "$REPO_ROOT" --left "$H0" --right "$H1" \
    --covered-set phase-3 \
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/00-review-brief.md
  "$PYTHON" scripts/check_worker_plane_review.py \
    --repo "$REPO_ROOT" --h0 "$H0" --h1 "$H1" \
    --covered-set phase-3 \
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-3/00-review-brief.md \
    --packet "$REVIEW_ATTEMPT_DIR/00-review-packet.bin" \
    --input-manifest "$REVIEW_ATTEMPT_DIR/input-manifest.json" \
    --freeze-receipt "$REVIEW_ATTEMPT_DIR/freeze-receipt.json" \
    --disposition "$REVIEW_ATTEMPT_DIR/99-disposition.md" \
    --files \
    "$REVIEW_ATTEMPT_DIR/01-fable-5-architecture.md" \
    "$REVIEW_ATTEMPT_DIR/02-gemini-3.1-pro-high.md" \
    "$REVIEW_ATTEMPT_DIR/03-glm-5.2-adversarial.md"
  cd apps/backend-rag
  source .venv/bin/activate
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/verify_worker_plane_phase3.py --environment disposable --database-url "$TEST_DATABASE_URL" --workflow-evidence /tmp/workflow-disposable-evidence.json --legal-evidence /tmp/legal-disposable-evidence.json --g9-baseline backend/architecture/baselines/phase0_snapshot.json --g9-protocol backend/architecture/baselines/phase0_probe_protocol.json --g9-exceptions backend/architecture/baselines/phase0_comparison_exceptions.json --workflow-g9-candidate /tmp/worker-plane-phase3-workflow-g9-candidate.json --workflow-g9-comparison /tmp/worker-plane-phase3-workflow-g9-comparison.json --legal-g9-candidate /tmp/worker-plane-phase3-legal-g9-candidate.json --legal-g9-comparison /tmp/worker-plane-phase3-legal-g9-comparison.json --output /tmp/worker-plane-phase3-reviewed.json
  git diff --check
  ```

  Expected: review validator and verifier exit 0; no unresolved Blocking/Important finding remains; diff check is silent.

- [ ] Verify the immutable panel record already bound to `H1`; do not create a later artifact commit after validation:

  ```bash
  git show --stat --oneline "$H1"
  test -z "$(git status --porcelain --untracked-files=no)"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Phase 3 Exit Gate

Phase 3 is complete only when every statement below is proven from checked-in hashes and disposable aggregate state:

- [ ] The recorded current-goal authorization covers the unchanged Phase 3 scope; prior phase verifiers and G13/G14 code/CI gates remain green on the exact source commit/artifact hash without a candidate staging deployment.
- [ ] Migration sequence is exactly 246 quarantine, 247 ownership, 248 effect ledger; no second Phase 3 migration exists and 249 remains free.
- [ ] `OwnershipRepository`, `OwnershipService`, Phase 1 grant/heartbeat/claim symbols, and the canonical catalogs remain the single authorities; no parallel manifest or ownership implementation exists.
- [ ] Migration 248 state transitions prevent concurrent duplicate attempts, blind non-reconcilable retry, terminal reopen, stale effect generation, and activation with attempting/unresolved blockers.
- [ ] G12 proves generation-independent scheduled-run identity and exactly one logical run/effect across forward and reverse cutover.
- [ ] Workflow was proven first with authoritative disposable fixtures. Its legacy/target compatibility algorithm passed, drain preserved N, activation used N+1, reverse used N+2, synthetic canaries passed, G3/G4/G15 passed, all guards finished unarmed, and its checked code-readiness checkpoint preceded legal work.
- [ ] Legal was proven only after that checkpoint. Stable document identity prevents duplicate Qdrant/KG/Drive work; Drive/Sheets reconcile; NLM ambiguity becomes unknown without automatic retry; its disposable forward/reverse simulation passes, all guards finish unarmed, and live targets remain untouched.
- [ ] For both workloads, restart, provider timeout, duplicate delivery, stale owner, DB reconnect, dependency outage, and kill-after-dispatch tests conserve every accepted job and obey the declared effect contract.
- [ ] No sampled interval has active grants for two owners/generations. Every forward/reverse owner assignment increments generation; same-owner draining alone preserves it so fenced work can finish.
- [ ] In every disposable simulation, each old-generation lease expired or finished, provider timeout plus margin elapsed, each scheduled run was adopted/cancelled atomically, and every non-reconcilable unknown was resolved before simulated activation.
- [ ] Migration 248 is applied to disposable PostgreSQL and G16 proves live schema/fixture/catalog/annotation parity with a nonempty `TEST_DATABASE_URL`; the refreshed `schema_tables.txt` and checker tests are staged with migration 248.
- [ ] G16 and the static source ratchet prove `business_context=platform`, the exact sorted workflow/legal grant-fenced automatic bindings, workload-specific static resolution bindings, static cutover-audit binding, and the migration-248 extensions to Phase 1 `worker-grant-admin` plus `worker-ownership-audit`; every Python/SQL pair resolves, operation-mode/interface keys and migration sources match, automatic prepare/begin/finish/reconcile mutations carry the full live grant/domain-claim/lease/attempt fence, resolution and set-mode use only the protected management role, no legacy singular writer metadata or mutation API accepting `workload_name` exists, and no shared helper performs DML.
- [ ] No live staging or production app, database, guard, grant, secret, heartbeat, or ownership row was mutated in Phase 3. Production-rollout Task 2 is the sole live staging actuator and must use the exact protected-merged digest for deploy, migration 248, guard arming, live compatibility-floor proof, workflow then legal cutover, reverse rehearsal, canaries, budget checks, and full-cycle observation.
- [ ] `worker_live_control.py` and `.github/workflows/worker-plane-live-control.yml` pass fake/disposable tests for one-command/one-workload protected staging and production jobs, immutable gate/digest/admission/prior-state binding, immutable protected capability-workflow run ID plus effective-grant-union and allowed-secret-symbol hashes, shared concurrency, immediate recomputation/re-audit before every mutating CAS, stale/missing/excess/TOCTOU rejection, redaction, failure evidence, and rejection of direct SQL/Fly/image/secret/grant mutation; they were not dispatched in Phase 3.
- [ ] The Task 8 and Task 11 complete G9 candidates use the exact canonical Phase 0 protocol/topology/window and contain numeric API/RAG startup, maximum steady RSS, aggregate PostgreSQL connections, and HTTP 5xx rate. Both comparisons remain within 10%, or an exact unexpired owner-approved exception artifact is present and panel-reviewed; worker G13/G14 evidence is separate.
- [ ] Legacy workflow/legal code paths, additive schema, grants needed for reverse cutover, and audited rollback commands remain available through the recovery window.
- [ ] Fable 5, Gemini 3.1 Pro High, and GLM 5.2 independently reviewed one immutable projection through the canonical single-buffer launcher; every Blocking and Important finding was fixed and all three seats reran after every covered-input projection change.
