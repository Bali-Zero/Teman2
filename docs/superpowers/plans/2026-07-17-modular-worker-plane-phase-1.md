# Modular Worker Plane Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make route placement and workload ownership executable from canonical catalogs, ship a dynamically refreshed PostgreSQL fencing protocol into the four named pilot claim/effect paths, prove database guard arming and audited disarming against disposable PostgreSQL, and enforce single-consumer and table-ownership invariants without moving or arming any live workload yet.

**Architecture:** Phase 1 converts the Phase 0 catalogs from checked inventories into runtime authority. Router mounting and RAG proxy decisions come from the same `RouterEntry`; worker grants, expected-instance census, modes, generations, heartbeats, build floors, and audit history live in PostgreSQL. Workflow, legal, notification, and WA adopt the full claim/effect protocol as named pilots; every other cataloged durable loop receives startup ownership validation, heartbeat, and liveness wiring but remains observation-only. Additive database triggers stay inert in deployable code; their arm/disarm behavior is exercised only on disposable PostgreSQL until the final protected rollout.

**Tech Stack:** Python 3.11+, FastAPI/Starlette, asyncpg, PostgreSQL v2 SQL migrations and PL/pgSQL, pytest/pytest-asyncio, HTTPX/TestClient, Ruff, GitHub Actions, Phase 0 architecture catalogs.

## Global Constraints

- Complete, review, and commit Phase 0 first on this same feature branch. Do not merge, deploy, or arm between phases; migration `247_event_quarantine.sql` must remain the latest migration before this phase begins.
- Work only in an isolated agent worktree. Preserve unrelated changes and never mutate the shared checkout.
- Read `docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md` and the Phase 0 exit evidence before implementation.
- Run backend Python only from `apps/backend-rag/.venv`, with `PYTHONPATH=.` from `apps/backend-rag`.
- Keep process placement unchanged for the entire phase. Workflow/legal remain on their current RAG/full owner; notification/WA remain on API; Drive remains Drive. Phase 1 installs compatibility and control-plane mechanics, not cutover.
- Preserve the Phase 0 vocabulary split: `BusinessContext`/`business_context` identifies bounded business/data ownership, while `RuntimeOwner`/`runtime_owner` identifies execution placement. No compatibility alias may conflate the two axes. Route/table business ownership stays on the business axis; table write eligibility uses the separate tagged `writer_bindings` policy; grants, expected instances, heartbeats, claims, leases, and CAS transitions stay on the runtime axis.
- The workload grant's `runtime_owner` identifies the one executing owner and must be a member of the exact bounded `WorkloadSpec.candidate_runtime_owners`; candidate membership alone grants no claim or effect authority. `WorkloadSpec.business_context` remains unchanged across cutover, and the catalog `concurrency` field governs legitimate parallel loops inside that runtime owner.
- Preserve each workload's source-closed, sorted, unique symbolic-only `provider_secret_symbols` provider-runtime injection allowlist; never place a value, assignment, URI, or resolved credential/identifier in a catalog or artifact. Phase 2 derives and hashes the exact protected injection set from this field. For this release notification is pinned to explicit SendGrid and declares exactly HMAC plus `SENDGRID_API_KEY`; WA declares exactly `WHATSAPP_API_TOKEN` plus `WHATSAPP_PHONE_NUMBER_ID`. SMTP/auto-detect and any undeclared provider dependency fail closed.
- A mutable table shared by workloads uses a distinct workload-specific mutation wrapper per grant-fenced binding. One generic writer with a caller-selected workload, or one interface reused across bindings on the same table, is forbidden; common helpers behind wrappers are pure/read-only. This is the required shape for the Phase 3 effect-ledger projection and attempt tables.
- Ownership modes have fixed semantics: `off` and `shadow` cannot claim or execute side effects; `draining` cannot claim new work but may finish already fenced claims; `active` may claim and finish.
- The ownership generation is monotonic. Every forward or reverse ownership change increments it; rollback is a reverse cutover through the same compare-and-set function, never a decrement or stale-owner reactivation.
- Runtime code refreshes its grant before every claim and every irreversible/late side effect. A startup-only grant cache is forbidden. Cache TTL, if used, is at most one-third of the workload lease.
- Phase 1 produces compatibility-release code containing heartbeats, expected-instance census, claim metadata, kill switches, claim checks, and late-effect checks. Production deployment, the full compatibility observation window, and every production guard arm are deferred to the final protected rollout before any ownership transition.
- Migration 248 installs database trigger guards but leaves every `guard_armed` value false. `worker_arm_claim_guard` may succeed in this phase only against disposable-PostgreSQL evidence after `worker_build_floor_ready` proves the complete authoritative expected-instance census; every live staging and production guard remains false throughout Phase 1.
- Phase 1 consumes only migration `248_worker_plane_ownership.sql`; the next free migration number after this plan is 249. Migration 248 does not create a generic job table, side-effect ledger, or schedule-run ledger.
- Missing workload, missing owner/generation/build epoch, stale heartbeat, ownership mismatch, stale generation, old build, unavailable ownership storage, or kill switch all fail closed for claims and irreversible effects.
- Phase 1 never merges independently, deploys to production, changes production ownership, or arms a production guard. Those actions belong only to the final rollout after the full branch passes all phases and reviews. Never edit ownership, census, or guard rows manually in any environment.
- Do not add Kafka, Celery, a new service image, a new data store, or a parallel routing/ownership manifest.
- Preserve public router paths, status codes, streaming behavior, authentication, and timeouts. Route-catalog migration is structural only.
- Every test is written and observed failing for the stated reason before implementation.
- Every task ends in an atomic conventional commit; never use `--no-verify`, `--amend`, force push, or direct push to `main`.
- A phase may not exit with `TODO`, `TBD`, `FIXME`, `NotImplementedError`, placeholder reviews, an expired catalog exception, or an unresolved Blocking/Important panel finding.

---

## Task 1: Make the router manifest authoritative for mounting and proxy routing (G1)

**Files:**

- Modify: `apps/backend-rag/backend/app/setup/router_manifest.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`
- Modify: `apps/backend-rag/backend/app/rag_proxy.py`
- Modify: `apps/backend-rag/backend/tests/setup/test_router_manifest.py`
- Modify: `apps/backend-rag/backend/tests/setup/test_manifest_registration_parity.py`
- Modify: `apps/backend-rag/backend/tests/setup/test_router_registration_parity.py`
- Modify: `apps/backend-rag/backend/tests/unit/app/test_rag_proxy_intake_split.py`
- Create: `apps/backend-rag/backend/tests/setup/test_router_catalog_mutation.py`

The canonical API is:

```python
def routers_for_group(group: str, *, include_disabled: bool = False) -> tuple[RouterEntry, ...]: ...
def proxy_entries() -> tuple[RouterEntry, ...]: ...
def matches_proxy_path(path: str) -> bool: ...
def route_catalog_hash() -> str: ...
def include_manifest_routers(app: FastAPI, group: str) -> None: ...
```

Every `RouterEntry` now explicitly sets `process_groups`, `exposure`, `proxy_match`, `auth_class`, `streaming`, `timeout_class`, and `business_context`; Phase 0 compatibility defaults are removed after all entries are populated. `include_routers`, `include_light_routers`, and `include_heavy_routers` remain synchronous public wrappers but delegate to `include_manifest_routers`. The existing public `rag_proxy.is_heavy_route` delegates to `matches_proxy_path`. The handwritten `HEAVY_PREFIXES` constant is deleted, and validation rejects any second prefix list.

- [ ] Write a mutation test that clones one manifest entry, changes its `process_groups` from API-only to RAG, and proves the generated mount set changes without modifying registration code.
- [ ] In the same test, change only that entry's `proxy_match` and prove `matches_proxy_path` and `rag_proxy.is_heavy_route` change together. Assert the router mounts and proxy decision share the same mutated entry.
- [ ] Add a source guard that fails if `HEAVY_PREFIXES`, a second `RouterEntry` tuple, or explicit production `include_router` calls outside the manifest registration helper reappear.
- [ ] Preserve current parity snapshots and add assertions for public route path, method, auth class, streaming flag, timeout class, and process group.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/setup/test_router_catalog_mutation.py backend/tests/setup/test_router_manifest.py backend/tests/setup/test_manifest_registration_parity.py backend/tests/setup/test_router_registration_parity.py backend/tests/unit/app/test_rag_proxy_intake_split.py -q
  ```

  Expected: the mutation test shows mounting/proxy still depend on separate handwritten code and the duplicate-prefix guard finds `HEAVY_PREFIXES`.

- [ ] Populate every existing manifest entry with explicit metadata. Add validation for missing metadata, overlapping ambiguous prefix matches, streaming routes without streaming timeout class, and proxy entries not mounted by RAG.
- [ ] Implement `include_manifest_routers` using lazy imports and the existing condition/prefix/attribute semantics; convert the three legacy registration functions to thin wrappers so behavior remains stable.
- [ ] Replace RAG proxy prefix logic with `matches_proxy_path`. Keep the existing public `is_heavy_route(path: str) -> bool` signature.
- [ ] Run GREEN plus the route snapshot:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/setup backend/tests/unit/app/test_rag_proxy_intake_split.py -q
  PYTHONPATH=. python -c "from backend.app.setup.router_manifest import validate_manifest; errors=validate_manifest(); assert not errors, errors"
  git diff --check
  ```

  Expected: mutation and parity tests pass; the current public route snapshot is unchanged; validation returns no errors.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/app/setup/router_manifest.py apps/backend-rag/backend/app/setup/router_registration.py apps/backend-rag/backend/app/rag_proxy.py apps/backend-rag/backend/tests/setup apps/backend-rag/backend/tests/unit/app/test_rag_proxy_intake_split.py
  git commit -m "refactor(routing): derive mounts and proxy from one catalog" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 2: Add the ownership, heartbeat, audit, and additive claim schema

**Files:**

- Create: `apps/backend-rag/backend/db/migrations_v2/248_worker_plane_ownership.sql`
- Create: `apps/backend-rag/backend/tests/db/test_migration_248_worker_plane_ownership.py`
- Expand: `apps/backend-rag/backend/worker_plane/models.py`
- Create: `apps/backend-rag/backend/worker_plane/repository.py`
- Create: `apps/backend-rag/backend/tests/worker_plane/test_repository.py`
- Modify: `docs/architecture/worker-plane-migration-allocation.md`

Migration 248 has a non-destructive rollback marker and creates exactly these four control tables. From its first RED test it also carries one ownership block immediately before every `CREATE TABLE` and each ownership-affecting `ALTER TABLE`. The parser grammar is exact and line-oriented:

```text
-- table-ownership-begin: <qualified-table>
-- business-context: <BusinessContext value>
-- writer-binding: <binding-id>|static|<RuntimeOwner>|<operation=interface-reference CSV;...>
-- writer-binding: <binding-id>|grant-fenced|<workload>|<candidate RuntimeOwner CSV>|<operation=modes CSV;...>|<operation=interface-reference CSV;...>
-- writer-binding: <binding-id>|heartbeat-evidence|<workload=candidates CSV;...>|heartbeat-upsert=<interface-reference CSV>
-- migration-source: backend/db/migrations_v2/248_worker_plane_ownership.sql
-- table-ownership-end
```

`writer-binding` is repeatable and sorted by its stable, unique `binding-id`; each operation map, candidate list, mode list, and interface list is sorted too. Commas, pipes, semicolons, and equals signs have the literal meanings shown above, no wildcard or omitted field is accepted, and fields for one binding kind are invalid in another. A Python interface reference is an absolute `module:symbol`; a migration-defined callable is `sql:<schema>.<function>`; no third form is valid. For `grant-fenced`, the mode-map and interface-map operation keys must match exactly. Migration 248 declares the exact Task 2 control-plane interfaces below; Task 5 atomically adds the listed SQL callables to the same binding IDs when it creates them, so no task references a not-yet-existing symbol. The static `api` writer is the management-plane repository principal: after Task 5 the guard CLI can invoke only these protected functions through its least-privilege database role and never receives direct table DML. The three bootstrap tables cannot depend on a grant they themselves create, but their unlisted interface, missing actor/reason/version, raw DML, SQL error, or audit failure all fail closed.

| Table                       | Binding ID/kind                                    | Runtime/candidates              | Exact Task 2 operation interfaces                                                                                                                                                                                                                                                                                                                                                                   | Task 5 additions to same operation keys                                                                                                                                                                           |
| --------------------------- | -------------------------------------------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `worker_workload_ownership` | `worker-grant-admin` / `static`                    | `api`                           | `arm-guard=backend.worker_plane.repository:WorkerPlaneRepository.set_guard_armed;compare-and-set-grant=backend.worker_plane.repository:WorkerPlaneRepository.compare_and_set_grant;disarm-guard=backend.worker_plane.repository:WorkerPlaneRepository.disarm_guard`                                                                                                                                 | `arm-guard=sql:public.worker_arm_claim_guard;compare-and-set-grant=sql:public.worker_advance_ownership;disarm-guard=sql:public.worker_disarm_claim_guard`                                                         |
| `worker_expected_instances` | `worker-census-admin` / `static`                   | `api`                           | `register=backend.worker_plane.repository:WorkerPlaneRepository.register_expected_instance;retire=backend.worker_plane.repository:WorkerPlaneRepository.retire_expected_instance`                                                                                                                                                                                                                   | `register=sql:public.worker_register_expected_instance;retire=sql:public.worker_retire_expected_instance`                                                                                                         |
| `worker_ownership_audit`    | `worker-ownership-audit` / `static`                | `api`                           | `append-audit=backend.worker_plane.repository:WorkerPlaneRepository.compare_and_set_grant,backend.worker_plane.repository:WorkerPlaneRepository.disarm_guard,backend.worker_plane.repository:WorkerPlaneRepository.register_expected_instance,backend.worker_plane.repository:WorkerPlaneRepository.retire_expected_instance,backend.worker_plane.repository:WorkerPlaneRepository.set_guard_armed` | `append-audit=sql:public.worker_advance_ownership,sql:public.worker_arm_claim_guard,sql:public.worker_disarm_claim_guard,sql:public.worker_register_expected_instance,sql:public.worker_retire_expected_instance` |
| `worker_owner_heartbeats`   | `worker-heartbeat-evidence` / `heartbeat-evidence` | exact `workload=candidates` map | `heartbeat-upsert=backend.worker_plane.repository:WorkerPlaneRepository.record_heartbeat`                                                                                                                                                                                                                                                                                                           | `heartbeat-upsert=sql:public.worker_record_heartbeat`                                                                                                                                                             |

Heartbeat evidence is intentionally different from work authority: an expected target may publish self heartbeat evidence before cutover, but cannot change census, grant, job state, or effects.

For altered workload tables, the block preserves each Phase 0 business context and every existing producer/admin binding, then adds exactly these fenced consumer bindings:

| Table                 | Binding ID                 | Workload                 | Candidate runtimes | Fenced operation modes                                               | Exact operation interfaces                                                                                                                                                                                                                                                                                                                                                          |
| --------------------- | -------------------------- | ------------------------ | ------------------ | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `workflow_jobs`       | `workflow-consumer`        | `workflow_queue`         | `rag,worker`       | `claim=active;late-effect=active,draining`                           | `claim=backend.services.workflow.queue:_dequeue_one;late-effect=backend.services.workflow.queue:_ack_job,backend.services.workflow.queue:_fail_job,backend.services.workflow.queue:_heartbeat`                                                                                                                                                                                      |
| `legal_ingest_jobs`   | `legal-ingestion-consumer` | `legal_full_ingestion`   | `rag,worker`       | `claim=active;late-effect=active,draining`                           | `claim=backend.services.ingestion.legal_full_ingestion_worker:_claim_job;late-effect=backend.services.ingestion.legal_full_ingestion_worker:_update_job`                                                                                                                                                                                                                            |
| `notification_alerts` | `notification-consumer`    | `notification_scheduler` | `api,worker`       | `claim=active;late-effect=active,draining;schedule=active`           | `claim=backend.app.modules.notifications.service:NotificationService.claim_pending_alerts;late-effect=backend.app.modules.notifications.service:NotificationService._update_alert_status;schedule=backend.app.modules.notifications.scheduler:NotificationScheduler._daily_check`                                                                                                   |
| `wa_outbox`           | `wa-outbox-consumer`       | `wa_outbox`              | `api,worker`       | `claim=active;late-effect=active,draining;reconcile=active,draining` | `claim=backend.services.integrations.wa_outbox_worker:process_outbox_once;late-effect=backend.services.integrations.wa_outbox_worker:_coalesce_thread_bursts,backend.services.integrations.wa_outbox_worker:_lease_heartbeat_loop,backend.services.integrations.wa_outbox_worker:_process_claimed_row;reconcile=backend.services.integrations.wa_outbox_worker:process_outbox_once` |

The candidates must equal the corresponding `WorkloadSpec.candidate_runtime_owners`; they are not inferred from current grants and are never an authority union. At runtime the shared write-authority check admits a fenced operation only when the live `OwnershipGrant` has the exact workload, caller runtime owner, generation, and permitted mode. Missing storage, missing grant, candidate drift, generation drift, `off`, `shadow`, or a new claim in `draining` fails closed.

The four control tables are:

```sql
CREATE TABLE IF NOT EXISTS worker_workload_ownership (
    workload_name TEXT PRIMARY KEY,
    runtime_owner TEXT NOT NULL CHECK (runtime_owner IN ('api', 'rag', 'worker', 'drive')),
    generation BIGINT NOT NULL CHECK (generation > 0),
    mode TEXT NOT NULL CHECK (mode IN ('off', 'shadow', 'draining', 'active')),
    min_compatible_build_epoch BIGINT NOT NULL DEFAULT 0
        CHECK (min_compatible_build_epoch >= 0),
    guard_armed BOOLEAN NOT NULL DEFAULT FALSE,
    kill_switch BOOLEAN NOT NULL DEFAULT FALSE,
    lease_seconds INTEGER NOT NULL CHECK (lease_seconds > 0),
    version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0),
    changed_by TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS worker_owner_heartbeats (
    workload_name TEXT NOT NULL REFERENCES worker_workload_ownership(workload_name)
        ON DELETE CASCADE,
    runtime_owner TEXT NOT NULL CHECK (runtime_owner IN ('api', 'rag', 'worker', 'drive')),
    instance_id TEXT NOT NULL,
    generation BIGINT NOT NULL,
    build_id TEXT NOT NULL,
    build_epoch BIGINT NOT NULL CHECK (build_epoch >= 0),
    mode TEXT NOT NULL CHECK (mode IN ('off', 'shadow', 'draining', 'active')),
    started_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (workload_name, runtime_owner, instance_id)
);

CREATE TABLE IF NOT EXISTS worker_expected_instances (
    workload_name TEXT NOT NULL REFERENCES worker_workload_ownership(workload_name)
        ON DELETE CASCADE,
    runtime_owner TEXT NOT NULL CHECK (runtime_owner IN ('api', 'rag', 'worker', 'drive')),
    instance_id TEXT NOT NULL,
    expected_generation BIGINT NOT NULL CHECK (expected_generation > 0),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by TEXT NOT NULL,
    registration_reason TEXT NOT NULL,
    retired_at TIMESTAMPTZ,
    retired_by TEXT,
    retirement_reason TEXT,
    version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0),
    PRIMARY KEY (workload_name, runtime_owner, instance_id, expected_generation),
    CHECK (
        (retired_at IS NULL AND retired_by IS NULL AND retirement_reason IS NULL)
        OR
        (retired_at IS NOT NULL AND retired_by IS NOT NULL AND retirement_reason IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS worker_ownership_audit (
    id BIGSERIAL PRIMARY KEY,
    workload_name TEXT NOT NULL,
    previous_runtime_owner TEXT CHECK (
        previous_runtime_owner IS NULL
        OR previous_runtime_owner IN ('api', 'rag', 'worker', 'drive')
    ),
    new_runtime_owner TEXT NOT NULL CHECK (new_runtime_owner IN ('api', 'rag', 'worker', 'drive')),
    previous_generation BIGINT,
    new_generation BIGINT NOT NULL,
    previous_mode TEXT,
    new_mode TEXT NOT NULL,
    previous_version BIGINT,
    new_version BIGINT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

Add nullable `claim_runtime_owner TEXT`, `claim_generation BIGINT`, `claim_build_epoch BIGINT`, `claim_token UUID`, and `claimed_at TIMESTAMPTZ` to `workflow_jobs`, `legal_ingest_jobs`, and `notification_alerts`. `claim_runtime_owner`, when present, is constrained to `api|rag|worker|drive`. `wa_outbox` already has `claim_token` and `claimed_at`; add only runtime owner, generation, and build epoch. Add indexes needed to locate live heartbeats and fenced claims. No claim column is `NOT NULL` in this compatibility phase.

These are the only new control tables. The migration does not add a generic job queue, generic side-effect/effect-attempt ledger, or schedule-run ledger; those contracts remain domain-specific until a later phase explicitly designs them. The migration contains explicit workload seed rows whose names/owners/lease settings match `WORKLOAD_CATALOG`; expected instances are never guessed or silently self-declared by runtime startup. Before a build floor can become ready, an audited CLI imports the authoritative instance inventory for that environment from the deployment platform/process inventory. A parity test compares the SQL workload seed values with the Python catalog, because SQL migrations do not import Python at runtime.

The Python data contract is immutable `OwnershipGrant`, `ExpectedOwnerInstance`, `OwnerHeartbeat`, `ClaimContext`, `BuildFloorEvidence`, and `LivenessReport`. `OwnershipGrant`, `ExpectedOwnerInstance`, and `OwnerHeartbeat` each expose `runtime_owner: RuntimeOwner`; `ClaimContext` contains `workload_name`, `runtime_owner: RuntimeOwner`, `generation`, `build_id`, `build_epoch`, `instance_id`, and `claim_token`. None exposes a compatibility alias that conflates runtime placement with business ownership.

The repository contract is:

```python
async def get_grant(self, workload_name: str) -> OwnershipGrant | None: ...
async def record_heartbeat(self, heartbeat: OwnerHeartbeat) -> None: ...
async def list_live_heartbeats(self, workload_name: str, now: datetime) -> list[OwnerHeartbeat]: ...
async def list_expected_instances(
    self, workload_name: str, runtime_owner: RuntimeOwner, generation: int
) -> list[ExpectedOwnerInstance]: ...
async def register_expected_instance(
    self, instance: ExpectedOwnerInstance, actor: str, reason: str
) -> ExpectedOwnerInstance: ...
async def retire_expected_instance(
    self,
    workload_name: str,
    runtime_owner: RuntimeOwner,
    instance_id: str,
    generation: int,
    expected_version: int,
    actor: str,
    reason: str,
) -> ExpectedOwnerInstance: ...
async def compare_and_set_grant(
    self,
    workload_name: str,
    expected_version: int,
    new_runtime_owner: RuntimeOwner,
    new_mode: OwnershipMode,
    min_compatible_build_epoch: int,
    actor: str,
    reason: str,
) -> OwnershipGrant: ...
async def set_guard_armed(
    self, workload_name: str, expected_version: int, actor: str, reason: str
) -> OwnershipGrant: ...
async def disarm_guard(
    self, workload_name: str, expected_version: int, actor: str, reason: str
) -> OwnershipGrant: ...
```

- [ ] Before writing migration-248 tests/source, run `git fetch origin`, heartbeat all five allocation leases, and from the repository root run `apps/backend-rag/.venv/bin/python scripts/check_worker_plane_migration_allocation.py --base-ref origin/main --feature-ref HEAD --record docs/architecture/worker-plane-migration-allocation.md --next-number 248`. Update the record with the new fetched base commit plus unchanged upstream-246 blob identity and collision proof. Any changed 246 identity, occupied 247–251 number, missing lease, or feature-branch mapping drift stops Phase 1 and invalidates affected packets.
- [ ] Rerun the unchanged comprehensive allocation-checker test, then prove the Phase 0-owned 247 basename exists exactly once on the feature ref while 248 is still absent and all later assigned numbers remain unoccupied there. The Phase 0 test already covers this `--next-number 248` state in a temporary repository; do not phase-edit the generic checker merely to accept the live branch.
- [ ] Write migration tests for exact columns of all four control tables, census retirement consistency, runtime-owner checks on current/previous/new/claim columns, absence of any context-named execution column or compatibility alias, indexes, foreign keys, nullable claim compatibility, non-destructive rollback, migration uniqueness, and `guard_armed DEFAULT FALSE`. Parse every migration-248 ownership block and assert exact table coverage, sorted grammar, stable unique binding IDs, static bootstrap authority, heartbeat-evidence-only scope, all four fenced bindings above, exact catalog candidate parity, preservation of existing producer/admin bindings, and rejection of wildcard, mixed-kind fields, duplicate/uncovered operation-interface pairs, or a singular legacy `write-runtime-owner` annotation.
- [ ] Write repository tests using an injected fake pool for mapping records, heartbeat upsert, live-heartbeat lease filtering, expected-instance registration/listing, audited CAS retirement, compare-and-set success, stale-version conflict, monotonic generation/version, audited CAS guard disarm, audit insertion, and rollback-as-reverse-CAS.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/db/test_migration_248_worker_plane_ownership.py backend/tests/worker_plane/test_repository.py -q
  ```

  Expected: migration/model/repository tests fail because schema 248 and repository symbols do not exist.

- [ ] Implement migration 248 with the exact per-table annotation blocks, idempotent DDL, fixed explicit workload seed rows matching `WORKLOAD_CATALOG`, indexes on `(workload_name, lease_expires_at)`, `(build_epoch, lease_expires_at)`, and active expected-instance lookup, plus a non-destructive `SELECT 1;` rollback block. Add tests that fail when a SQL workload seed, candidate set, writer binding, operation mode, or declared interface drifts from the catalog.
- [ ] Implement strict row-to-model mapping and repository operations using asyncpg transactions. CAS updates must use `WHERE version = expected_version`, increment generation and version, insert the audit row in the same transaction, and raise a typed `OwnershipConflict` when no row updates.
- [ ] Ensure logs contain workload/owner/generation/build epoch but never claim payloads or secrets.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/db/test_migration_248_worker_plane_ownership.py backend/tests/worker_plane/test_repository.py backend/tests/db/test_migration_uniqueness.py -q
  PYTHONPATH=. python ../../scripts/lint_migration_numbers.py
  PYTHONPATH=. python ../../scripts/lint_migration_rollback.py
  ```

  Expected: schema, repository, uniqueness, and rollback gates pass.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/db/migrations_v2/248_worker_plane_ownership.sql apps/backend-rag/backend/tests/db/test_migration_248_worker_plane_ownership.py apps/backend-rag/backend/worker_plane/models.py apps/backend-rag/backend/worker_plane/repository.py apps/backend-rag/backend/tests/worker_plane/test_repository.py docs/architecture/worker-plane-migration-allocation.md
  git commit -m "feat(worker-plane): add ownership and heartbeat schema" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 3: Implement dynamic ownership, heartbeat, kill-switch, and build-floor services

**Files:**

- Create: `apps/backend-rag/backend/worker_plane/ownership_service.py`
- Create: `apps/backend-rag/backend/worker_plane/heartbeat.py`
- Modify: `apps/backend-rag/backend/worker_plane/liveness.py`
- Modify: `apps/backend-rag/backend/app/routers/health.py`
- Modify: `apps/backend-rag/backend/app/setup/app_factory.py`
- Modify: `apps/backend-rag/backend/app/main_api.py`
- Modify: `apps/backend-rag/backend/app/setup/service_initializer.py`
- Modify: `apps/backend-rag/backend/workers/drive_poll_worker.py`
- Create: `apps/backend-rag/backend/tests/worker_plane/test_ownership_service.py`
- Create: `apps/backend-rag/backend/tests/worker_plane/test_heartbeat.py`
- Modify: `apps/backend-rag/backend/tests/worker_plane/test_liveness.py`
- Modify: `apps/backend-rag/backend/tests/unit/app/setup/test_service_initializer.py`
- Modify: `apps/backend-rag/backend/tests/unit/workers/test_drive_poll_worker.py`

The service contract is:

```python
async def refresh_grant(self, workload_name: str) -> OwnershipGrant: ...
async def assert_table_write_allowed(
    self,
    table_name: str,
    workload_name: str,
    operation: str,
    write_interface: str,
    claim: ClaimContext,
) -> None: ...
async def assert_claim_allowed(self, claim: ClaimContext) -> None: ...
async def assert_effect_allowed(self, claim: ClaimContext, effect_name: str) -> None: ...
async def verify_build_floor(self, workload_name: str) -> BuildFloorEvidence: ...
async def arm_claim_guard(self, workload_name: str, actor: str, reason: str) -> OwnershipGrant: ...
```

`assert_table_write_allowed` loads the one table record, selects exactly one binding for the requested operation/interface pair, requires a grant-fenced binding for migrated consumer transitions, verifies that its candidate set still equals `WorkloadSpec`, and then compares the live grant's workload, runtime owner, generation, and mode. The caller passes its canonical absolute `module:symbol`; the Task 7 source ratchet proves that literal matches the enclosing mutation symbol, so a caller cannot widen authority by naming a different catalog interface. The same interface may not appear in another binding for that table, even under a renamed operation. Missing/overlapping binding, interface drift, absent grant, or unavailable catalog/grant storage fails closed. `assert_claim_allowed` is the claim-specific wrapper and permits only current `active` owner/generation/build at or above floor with kill switch false. `assert_effect_allowed` is the late-effect wrapper, permits `active` and `draining` only for an already-fenced claim, and validates the named `SideEffectCapability`. All three refresh from PostgreSQL at the checkpoint; database/Redis/cache failure is a typed fail-closed error for claims/irreversible effects. `WORKER_BUILD_ID`, monotonic integer `WORKER_BUILD_EPOCH`, and stable per-machine `WORKER_INSTANCE_ID` are required outside tests.

Phase 1 is compatibility instrumentation, not the final transaction-bound authority for provider side effects. Its `ClaimContext` deliberately does not yet carry the immutable domain `claimed_at` and current expected lease-expiry stamps, and a pre-call `assert_effect_allowed` cannot close the ownership/lease time-of-check-to-time-of-use window by itself. Therefore all live guards remain unarmed and no workload cutover or provider-effect activation is permitted on Phase 1 evidence alone. Workflow/legal become activatable only after Phase 3 replaces these checkpoints with workload-specific wrappers that lock grant -> domain claim -> effect projection/attempt and validate the full claim/lease stamp in the mutation transaction; notification/WA require the corresponding Phase 4 wrappers. Phase 1 tests prove compatibility wiring, observability, and fail-closed prechecks, not final transactional fencing.

The heartbeat task selects only the table's `heartbeat-evidence` binding and checks its exact workload/candidate tuple plus a matching expected-instance census identity before calling `record_heartbeat`. It may report build/mode/generation evidence for a reviewed target before that target owns work, but it never calls `assert_table_write_allowed`, mutates the grant/census, or creates a claim. A candidate not in the checked catalog, an unregistered identity, or unavailable census storage fails closed and writes no heartbeat.

`verify_build_floor` is set equality, not “all heartbeats we happened to see.” For the grant's current `runtime_owner` and generation it requires a non-empty active `worker_expected_instances` census, one fresh matching heartbeat at or above the floor for every expected instance, and no fresh unregistered heartbeat. A missing expected heartbeat, unexpected instance, stale census generation, duplicate identity, runtime-owner/generation mismatch, stale lease, or old build returns a typed not-ready reason. Runtime heartbeat registration cannot mutate the census; only audited register/retire commands can do so, and retirement uses expected-version CAS.

- [ ] Write tests for active success; off/shadow/draining claim rejection; draining existing-effect success; wrong owner; stale generation; old build; kill switch; missing grant; storage outage; reversible effect; irreversible effect without capability; and cache expiry no longer than `lease_seconds / 3`. Add table-authority tests for one exact operation/interface binding selection, a spoofed interface literal, unknown/uncovered/overlapping operation/interface pair, mismatched mode/interface key sets, candidate/catalog drift, wrong workload/interface, and proof that merely belonging to a candidate set cannot authorize a claim.
- [ ] Write build-floor tests: false with no expected census, no heartbeat for one expected instance, one old build, owner/generation mismatch, stale compatibility heartbeat, unexpected unregistered heartbeat, duplicate identity, or retired/stale-generation census row; true only when the non-empty expected-instance set equals the fresh compatible heartbeat set exactly. Add heartbeat-policy tests proving a cataloged expected target can upsert evidence before ownership transfer, while unknown candidate, unregistered instance, payload beyond heartbeat fields, and every attempted grant/census/job/effect mutation are rejected.
- [ ] Write startup conflict tests proving a runtime configured to execute a workload not assigned to that owner fails initialization before creating its task. Legitimate internal concurrency under one owner remains allowed. Cover durable call sites from the Phase 0 classification fixture in `app_factory.py`, `main_api.py`, `service_initializer.py`, and `drive_poll_worker.py`.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/worker_plane/test_ownership_service.py backend/tests/worker_plane/test_heartbeat.py backend/tests/worker_plane/test_liveness.py -q
  ```

  Expected: ownership/heartbeat imports fail and Phase 0 liveness has no database heartbeat source.

- [ ] Implement `OwnershipService`, typed failures `OwnershipUnavailable`, `ClaimRejected`, `EffectRejected`, and `BuildFloorNotReady`, with structured reason codes.
- [ ] Implement one heartbeat task per declared workload/instance. It validates the exact heartbeat-evidence binding and expected census row, writes only the heartbeat with `lease_expires_at`, records the catalog mode/metadata, and stops cleanly during lifespan shutdown. It may never self-register an expected instance or infer work authority from candidate membership.
- [ ] Before starting every call site classified durable by the Phase 0 census in `app_factory.py`, `main_api.py`, `service_initializer.py`, and `drive_poll_worker.py`, validate its declared `runtime_owner` against the live grant and wire its heartbeat/liveness lifecycle. In this task all seed grants still point to current runtime owners; do not move a workload. Non-durable/best-effort/startup-only classifications remain explicit and are not silently promoted.
- [ ] Keep non-pilot durable loops observation-only: they receive startup validation, heartbeat, and liveness, but no claim/effect adaptation and are ineligible for guard arming or cutover unless a later reviewed plan adds them to the pilot set.
- [ ] Switch `/health/workloads` from process-local liveness to live PostgreSQL heartbeats while preserving the Phase 0 response contract. An active grant with no live heartbeat is HTTP 503.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/worker_plane backend/tests/unit/app/routers/test_health_worker_liveness.py -q
  PYTHONPATH=. pytest backend/tests/setup -q
  ```

  Expected: all dynamic ownership, startup conflict, heartbeat, and workload-health tests pass.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/worker_plane apps/backend-rag/backend/app/routers/health.py apps/backend-rag/backend/app/setup/app_factory.py apps/backend-rag/backend/app/main_api.py apps/backend-rag/backend/app/setup/service_initializer.py apps/backend-rag/backend/workers/drive_poll_worker.py apps/backend-rag/backend/tests/worker_plane apps/backend-rag/backend/tests/unit/app/routers/test_health_worker_liveness.py apps/backend-rag/backend/tests/unit/app/setup/test_service_initializer.py apps/backend-rag/backend/tests/unit/workers/test_drive_poll_worker.py
  git commit -m "feat(worker-plane): enforce dynamic ownership and heartbeats" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 4: Ship fencing compatibility into the four named pilot claim/effect paths

**Files:**

- Modify: `apps/backend-rag/backend/services/workflow/queue.py`
- Modify: `apps/backend-rag/backend/services/ingestion/legal_full_ingestion_worker.py`
- Modify: `apps/backend-rag/backend/app/modules/notifications/scheduler.py`
- Modify: `apps/backend-rag/backend/app/modules/notifications/service.py`
- Modify: `apps/backend-rag/backend/services/integrations/wa_outbox_worker.py`
- Modify: `apps/backend-rag/backend/app/setup/app_factory.py`
- Modify: `apps/backend-rag/backend/app/main_api.py`
- Create: `apps/backend-rag/backend/tests/services/workflow/test_queue.py`
- Modify: `apps/backend-rag/backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py`
- Create: `apps/backend-rag/backend/tests/unit/app/modules/notifications/test_scheduler_fencing.py`
- Modify: `apps/backend-rag/backend/tests/unit/services/test_wa_outbox_worker.py`
- Modify: `apps/backend-rag/backend/tests/unit/services/test_wa_outbox_scheduler.py`

Exactly these four pilots receive a `ClaimContext` created from a freshly read grant: workflow queue, legal full ingestion, notification scheduler, and WA outbox. Claim SQL writes `claim_runtime_owner`, generation, build epoch, UUID token, and timestamp atomically with the existing claim transition. Existing catalog `runtime_owner` values remain unchanged and all `guard_armed` rows remain false. Other durable loops wired in Task 3 remain heartbeat/liveness-only and are not implicitly claimed as fenced.

The four integrations below remain compatibility shims until their Phase 3/4 transaction-bound effect wrappers land. Passing these RED/GREEN tests must not be described as proof that a provider call is safe across lease expiry or reclaim, and it never admits a live guard arm, ownership move, or provider capability.

Required signature changes:

```python
async def _dequeue_one(conn: asyncpg.Connection, claim: ClaimContext) -> dict[str, Any] | None: ...
async def _claim_job(conn: asyncpg.Connection, claim: ClaimContext) -> asyncpg.Record | None: ...
async def NotificationService.claim_pending_alerts(
    self, claim: ClaimContext, limit: int = 100
) -> list[ClientAlert]: ...
async def process_outbox_once(
    pool: asyncpg.Pool,
    whatsapp_service: Any,
    bot_generate_fn: BotGenerateFn,
    *,
    claim: ClaimContext,
) -> str: ...
```

Workflow checks the exact `workflow_jobs` binding inside `_dequeue_one`, `_ack_job`, `_fail_job`, and `_heartbeat`, while `assert_effect_allowed` runs immediately before `execute_chain`. Legal checks the `legal_ingest_jobs` binding inside `_claim_job` and every `_update_job`, while the narrower effect check runs before each Qdrant/KG write, Drive upload, NotebookLM bridge call, and Sheets write. Notification checks the `notification_alerts` binding inside `_daily_check`, `claim_pending_alerts`, and `_update_alert_status`, while the effect check runs immediately before email delivery. WA checks the `wa_outbox` binding inside the exact cataloged reconciliation, claim, coalescing, lease-heartbeat, and claimed-row mutation symbols, while the effect check runs immediately before Graph API send; existing per-thread advisory lock and per-row claim token stay intact. Every table mutation path calls `assert_table_write_allowed` with its cataloged table, workload, operation, and canonical enclosing interface before the narrower claim/effect check; no module performs an ad hoc candidate-set check.

- [ ] Add RED tests to each path for fresh matching claim success, stale generation rejection before claim, ownership change after claim causing late-effect rejection, kill switch before effect, claim metadata persistence, and storage outage fail-closed.
- [ ] Add tests that current retry/status/visibility semantics, notification dedupe, WA coalescing/advisory lock, and workflow heartbeat still behave exactly as before for a valid claim.
- [ ] Add a source-level compatibility test requiring `assert_table_write_allowed`, `assert_claim_allowed`, and `assert_effect_allowed` in all four real legacy modules, not only in a new worker runner, and rejecting a direct write to their fenced transitions outside the declared interface symbols.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/services/workflow/test_queue.py backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py backend/tests/unit/app/modules/notifications/test_scheduler_fencing.py backend/tests/unit/services/test_wa_outbox_worker.py backend/tests/unit/services/test_wa_outbox_scheduler.py -q
  ```

  Expected: new claim parameters/metadata/checkpoints are absent; stale-owner late effects currently execute.

- [ ] Thread `OwnershipService` and `ClaimContext` through current lifespan owners. Refresh on every polling iteration and at each late-effect checkpoint; do not capture a startup grant in a closure.
- [ ] Update atomic claim SQL with the additive columns. Keep `FOR UPDATE SKIP LOCKED`, visibility timeouts, retries, advisory locks, and existing dedupe behavior.
- [ ] Implement `draining`: no new claim after mode changes, but an already-stamped claim may complete only while owner/generation remain current and its late-effect check passes.
- [ ] Ensure a rejected claim/effect emits a structured reason/workload/generation log and metric but never logs job payload, phone number, email, or client identity.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/services/workflow/test_queue.py backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py backend/tests/unit/app/modules/notifications/test_scheduler_fencing.py backend/tests/unit/services/test_wa_outbox_worker.py backend/tests/unit/services/test_wa_outbox_scheduler.py -q
  PYTHONPATH=. pytest backend/tests/unit/services/test_wa_inbox_bot.py backend/tests/services/events -q
  ```

  Expected: every stale/late-effect test fails closed and all existing behavior tests remain green for valid ownership.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/services/workflow/queue.py apps/backend-rag/backend/services/ingestion/legal_full_ingestion_worker.py apps/backend-rag/backend/app/modules/notifications/scheduler.py apps/backend-rag/backend/app/modules/notifications/service.py apps/backend-rag/backend/services/integrations/wa_outbox_worker.py apps/backend-rag/backend/app/setup/app_factory.py apps/backend-rag/backend/app/main_api.py apps/backend-rag/backend/tests/services/workflow/test_queue.py apps/backend-rag/backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py apps/backend-rag/backend/tests/unit/app/modules/notifications/test_scheduler_fencing.py apps/backend-rag/backend/tests/unit/services/test_wa_outbox_worker.py apps/backend-rag/backend/tests/unit/services/test_wa_outbox_scheduler.py
  git commit -m "feat(worker-plane): fence legacy workload claim paths" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 5: Add inert database claim guards and build-floor-controlled arming

**Files:**

- Modify: `apps/backend-rag/backend/db/migrations_v2/248_worker_plane_ownership.sql`
- Modify: `apps/backend-rag/backend/tests/db/test_migration_248_worker_plane_ownership.py`
- Modify: `apps/backend-rag/backend/architecture/catalogs/data/table_ownership.json`
- Modify: `apps/backend-rag/backend/worker_plane/repository.py`
- Modify: `apps/backend-rag/backend/worker_plane/ownership_service.py`
- Create: `apps/backend-rag/backend/tests/worker_plane/test_database_claim_guard.py`
- Create: `apps/backend-rag/scripts/worker_plane_guard.py`
- Create: `apps/backend-rag/scripts/tests/test_worker_plane_guard.py`

Migration 248 defines these SQL callables:

```sql
worker_assert_claim_allowed(
    p_workload_name TEXT,
    p_runtime_owner TEXT,
    p_generation BIGINT,
    p_build_epoch BIGINT,
    p_require_active BOOLEAN DEFAULT TRUE
) RETURNS VOID

worker_record_heartbeat(
    p_workload_name TEXT,
    p_runtime_owner TEXT,
    p_instance_id TEXT,
    p_generation BIGINT,
    p_build_id TEXT,
    p_build_epoch BIGINT,
    p_mode TEXT,
    p_lease_seconds INTEGER,
    p_metadata JSONB DEFAULT '{}'::jsonb
) RETURNS VOID

worker_build_floor_ready(
    p_workload_name TEXT,
    p_now TIMESTAMPTZ DEFAULT NOW()
) RETURNS BOOLEAN

worker_register_expected_instance(
    p_workload_name TEXT,
    p_runtime_owner TEXT,
    p_instance_id TEXT,
    p_expected_generation BIGINT,
    p_actor TEXT,
    p_reason TEXT
) RETURNS worker_expected_instances

worker_retire_expected_instance(
    p_workload_name TEXT,
    p_runtime_owner TEXT,
    p_instance_id TEXT,
    p_expected_generation BIGINT,
    p_expected_version BIGINT,
    p_actor TEXT,
    p_reason TEXT
) RETURNS worker_expected_instances

worker_arm_claim_guard(
    p_workload_name TEXT,
    p_expected_version BIGINT,
    p_actor TEXT,
    p_reason TEXT
) RETURNS VOID

worker_disarm_claim_guard(
    p_workload_name TEXT,
    p_expected_version BIGINT,
    p_actor TEXT,
    p_reason TEXT
) RETURNS VOID

worker_advance_ownership(
    p_workload_name TEXT,
    p_expected_version BIGINT,
    p_new_runtime_owner TEXT,
    p_new_mode TEXT,
    p_min_build_epoch BIGINT,
    p_actor TEXT,
    p_reason TEXT
) RETURNS worker_workload_ownership
```

Every rejection raises SQLSTATE `55000`. `worker_build_floor_ready` locks/reads the current grant and compares the complete non-retired expected-instance set with fresh matching heartbeats; an empty census, missing expected instance, fresh unexpected instance, old build, stale lease, or owner/generation mismatch is false. Expected-instance registration and retirement are audited; retirement requires the row's expected version. `worker_arm_claim_guard` and `worker_disarm_claim_guard` lock the grant, require `p_expected_version`, change `guard_armed` only from the expected state, increment grant version, and insert the matching audit event in the same transaction. A stale version, already-armed arm, already-disarmed disarm, or audit failure leaves state unchanged.

Adding these callables also extends, in the same patch, migration 248's existing control-table annotation blocks and the matching catalog bindings with the exact `sql:public.<function>` interfaces listed in Task 2. It does not create new binding IDs or operation keys. A dedicated least-privilege management role receives only `EXECUTE` on those functions; direct `INSERT|UPDATE|DELETE|COPY` on the grant, census, and audit tables is revoked from the guard CLI role. The heartbeat callable remains constrained by the heartbeat-evidence binding and expected-instance check. Missing role setup, callable/catalog drift, or a direct control-table write fails migration tests and the shared ownership checker.

`worker_enforce_claim_transition() RETURNS trigger` reads the workload/transition kind from `TG_ARGV` and enforces only when that workload's `guard_armed` is true. Trigger transitions are: workflow `pending -> in_progress`; legal a new claim token or non-terminal `visibility_at` advance; notification a new claim token; WA `pending -> claimed`. In the same trigger statement it locks the current `worker_workload_ownership` row and requires `NEW.claim_runtime_owner`, `NEW.claim_generation`, `NEW.claim_build_epoch`, and `NEW.claim_token` to equal the live active grant/candidate/build-floor values; a generation or token read before the transaction is never authority. This rejects both pre-compatible field-absent SQL and compatible SQL stamped with a stale generation after a concurrent ownership CAS.

- [ ] Extend migration tests for all functions, SQLSTATE, row locking, guard default false, all four named triggers, and trigger predicates. Add tests proving migration application itself never arms a guard, runtime heartbeat writes cannot create/retire census rows, and a compatible claim carrying generation N is rejected at the database after a concurrent CAS to N+1 even when its application pre-check passed.
- [ ] Write disposable-PostgreSQL tests: build floor fails for every expected/actual set mismatch; valid compatible claim passes; missing metadata passes while unarmed; missing metadata fails after a disposable guard arm; wrong owner/generation/build fails; a transaction that pauses after reading generation N then resumes its compatible claim after the grant advances to N+1 fails in the trigger without mutating the job; legal visibility-only legacy SQL fails; reverse CAS increments generation; audited disarm restores inert compatibility; stale-version disarm and audit insertion failure leave the guard armed. Assert every new SQL callable appears under the existing binding ID and operation key in both migration annotations and catalog, the management role has only the required function `EXECUTE`, raw control-table DML is denied, and a missing/extra SQL interface fails closed.
- [ ] Write `worker_plane_guard.py` tests for `status`, `floor`, `census`, `register-instance`, `retire-instance`, `arm`, and `disarm`. Every command requires a nonempty `--database-url` and explicit environment classification; every Phase 1 mutating command additionally requires `--environment disposable`, exact `--workload`, `--actor`, `--reason`, `--output`, `--expected-version`, and explicit `--confirm-workload`. `register-instance`/`retire-instance` additionally require `--runtime-owner`, `--instance-id`, and `--generation`; an unrecognized business-context value supplied as runtime owner fails before opening the database. `census` reports expected versus fresh actual sets keyed by `runtime_owner`. No command has an `--all` mode, and live targets fail closed in this phase.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/db/test_migration_248_worker_plane_ownership.py backend/tests/worker_plane/test_database_claim_guard.py scripts/tests/test_worker_plane_guard.py -q
  ```

  Expected: SQL functions/triggers/CLI are absent; pre-compatible SQL is still accepted after simulated arming.

- [ ] Implement SQL functions with `SELECT ... FOR UPDATE`, explicit missing-value rejection, authoritative expected-instance set equality, monotonic CAS/audit, and inert trigger behavior while unarmed. Guard disarm is a first-class audited CAS primitive, never a manual SQL recovery instruction.
- [ ] Implement repository/service wrappers that call the SQL functions instead of duplicating ownership mutation logic in Python.
- [ ] Implement the guard CLI using asyncpg, redacted structured JSON evidence, and no shell interpolation. It must refuse `arm` when the authoritative census is empty, an expected heartbeat is absent, an unexpected heartbeat is fresh, any build is below floor, any owner/generation mismatches, or the requested guard is already in an unexpected state. The Phase 1 evidence path may arm/disarm only a disposable database; live staging and production credentials are forbidden here.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/db/test_migration_248_worker_plane_ownership.py backend/tests/worker_plane/test_database_claim_guard.py scripts/tests/test_worker_plane_guard.py -q
  PYTHONPATH=. python ../../scripts/lint_migration_numbers.py
  PYTHONPATH=. python ../../scripts/lint_migration_rollback.py
  ```

  Expected: unarmed compatibility works; disposable armed guards reject every stale/missing/old-build claim; arming refuses every incomplete-census floor; audited CAS disarm is proven; both migration linters pass; no live guard was touched.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/db/migrations_v2/248_worker_plane_ownership.sql apps/backend-rag/backend/tests/db/test_migration_248_worker_plane_ownership.py apps/backend-rag/backend/architecture/catalogs/data/table_ownership.json apps/backend-rag/backend/worker_plane/repository.py apps/backend-rag/backend/worker_plane/ownership_service.py apps/backend-rag/backend/tests/worker_plane/test_database_claim_guard.py apps/backend-rag/scripts/worker_plane_guard.py apps/backend-rag/scripts/tests/test_worker_plane_guard.py
  git commit -m "feat(worker-plane): guard claims after compatible build floor" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 6: Enforce the global-ack event fan-out rule at CI, subscribe, and runtime

**Files:**

- Modify: `apps/backend-rag/backend/architecture/catalogs/events.py`
- Modify: `apps/backend-rag/backend/services/events/event_bus.py`
- Create: `apps/backend-rag/scripts/check_event_fanout.py`
- Create: `apps/backend-rag/scripts/tests/test_check_event_fanout.py`
- Modify: `apps/backend-rag/backend/tests/services/events/test_channel_consumer_parity.py`
- Create: `apps/backend-rag/backend/tests/services/events/test_event_fanout_guard.py`
- Create: `.github/workflows/event-fanout-guard.yml`

For any durable transport using one global `consumed_at`/`consumer_id`, `EventPolicy.consumer_cardinality` must be `1`. `EventBus.subscribe` rejects a second durable subscriber for that type before mutating `_subscribers`. Startup validation rejects a catalog/runtime mismatch. CI scans catalog declarations and known subscription registration sites. A real fan-out requirement is not solved by bypassing the guard; it requires a later per-consumer acknowledgement design.

- [ ] Write tests for a single durable subscriber, second durable subscriber rejection, multiple best-effort in-process subscribers, duplicate same-handler idempotence, startup catalog/runtime mismatch, and no partial subscriber registration after failure.
- [ ] Write checker tests with fixtures for valid single consumer, invalid durable fan-out, hidden alias registration, dynamic unknown event, and explicitly cataloged best-effort fan-out.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/services/events/test_event_fanout_guard.py backend/tests/services/events/test_channel_consumer_parity.py scripts/tests/test_check_event_fanout.py -q
  ```

  Expected: EventBus accepts a second durable handler and the checker does not exist.

- [ ] Implement `FanoutContractError`, pre-mutation subscribe validation, catalog startup validation, and deterministic checker output naming event/transport/handlers.
- [ ] Add CI workflow running unit tests plus the real repository scan. Unknown dynamic registrations fail closed and require a cataloged static resolver, not an ignore glob.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/services/events/test_event_fanout_guard.py backend/tests/services/events/test_channel_consumer_parity.py scripts/tests/test_check_event_fanout.py -q
  PYTHONPATH=. python scripts/check_event_fanout.py
  ```

  Expected: single-consumer durable events pass; every second durable subscriber is rejected at all three gates.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/architecture/catalogs/events.py apps/backend-rag/backend/services/events/event_bus.py apps/backend-rag/scripts/check_event_fanout.py apps/backend-rag/scripts/tests/test_check_event_fanout.py apps/backend-rag/backend/tests/services/events/test_channel_consumer_parity.py apps/backend-rag/backend/tests/services/events/test_event_fanout_guard.py .github/workflows/event-fanout-guard.yml
  git commit -m "feat(events): enforce durable single-consumer fanout" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 7: Enforce table ownership on migrations and write interfaces (G16)

**Files:**

- Modify: `apps/backend-rag/backend/architecture/catalogs/tables.py`
- Modify: `apps/backend-rag/backend/architecture/catalogs/data/table_ownership.json`
- Modify: `apps/backend-rag/scripts/check_table_ownership.py`
- Modify: `apps/backend-rag/scripts/tests/test_check_table_ownership.py`
- Modify: `apps/backend-rag/backend/tests/fixtures/schema_tables.txt`
- Create: `apps/backend-rag/backend/tests/fixtures/migrations/998_unassigned_table.sql`
- Create: `apps/backend-rag/backend/tests/fixtures/migrations/999_owned_table.sql`
- Create: `.github/workflows/table-ownership.yml`

Every table-creating or ownership-affecting migration must carry the exact per-table block grammar defined in Task 2. `TableOwnership` contains one `business_context` and a complete, non-overlapping tuple of tagged writer bindings; it has no singular `write_runtime_owner`. An ordinary table has one static binding. A migrated queue/state table may retain explicitly named static producer/admin operations, but every claim, schedule, late-effect, and reconciliation transition is assigned to a grant-fenced binding with an exact catalog workload, bounded candidate set, allowed-mode map, and exact operation-to-interface map. `operation_modes` and `operation_interfaces` have identical keys, preventing a binding from granting the Cartesian product of unrelated operations and symbols. `worker_workload_ownership`, `worker_expected_instances`, and `worker_ownership_audit` remain static protected bootstrap authority to avoid self-authorizing their own grant. `worker_owner_heartbeats` has only a heartbeat-evidence binding: exact expected candidates can publish self telemetry, never work or control-plane mutations.

Extend the single checker created in Phase 0; do not create a second migration-only ownership engine. It applies migrations through 248 to disposable PostgreSQL, introspects `pg_catalog`, compares that live set with the refreshed sorted schema fixture, parses every ownership-affecting migration block, resolves the catalog interfaces, and requires exact parity with `table_ownership.json` and `WORKLOAD_CATALOG`. A dated legacy exception contains `table_name`, `business_context`, `binding_id`, `operation`, `write_interface`, `reason`, `approved_by`, and `expires_on`. It may temporarily account for a known legacy source path already inside a valid finite binding; it can never create a wildcard candidate, waive workload/candidate parity, authorize `off|shadow`, bypass live owner/generation/mode checks, or exempt a control-plane mutation.

- [ ] Write checker tests where 998 fails for no annotation/assignment and 999 passes with a matching per-table block and catalog entry containing a static `enqueue` binding plus grant-fenced `claim|late-effect` binding. Add a shared-table innocence fixture with two exact workload bindings and distinct workload-specific mutation wrappers. Independently test mismatched business context, missing/duplicate table assignment, missing/duplicate/unsorted binding ID, mixed binding-kind fields, static zero/two-owner cardinality, unknown/empty/duplicate/unsorted/wildcard candidates, candidate drift from `WorkloadSpec`, unknown workload, unequal mode/interface operation keys, overlapping or uncovered operation/interface pairs, reuse of one generic mutation interface across bindings even under renamed operations, a caller-selected workload passed to a generic writer, claim modes other than exactly `active`, late-effect modes outside `active,draining`, absent/unresolvable interface, a heartbeat binding with any operation beyond `heartbeat-upsert`, immutable view/reference innocence, and rejection of the legacy singular `write-runtime-owner` annotation. An expired/under-specified exception fails at an injected clock. Explicit `--schema-file <path> --refresh-schema-file` writes the sorted live disposable-PostgreSQL table set without reading row data.
- [ ] Add a source test that imports/resolves every Python interface and maps repository SQL writes (`INSERT`, `UPDATE`, `DELETE`, `COPY`, and mutating stored-procedure calls) to the exact table, operation, and enclosing declared symbol. Reject a write outside its binding, an operation/interface claimed by two bindings, a caller literal that differs from its enclosing symbol, cross-business-context direct writes, and any grant-fenced interface missing `assert_table_write_allowed(table, workload, operation, enclosing_interface, claim)` before its mutation. Prove a static producer can enqueue while the current consumer grant belongs to another runtime, and prove both old and target candidate consumers are denied unless each exactly matches the live grant's runtime owner, generation, and mode. Extend the same ratchet to reject `write_runtime_owner`, `write-runtime-owner`, `OwnerContext`, `owner_context`, and `owner-context` in architecture, worker-plane, catalog, and migration sources apart from the test's explicit deny strings; only `business_context`, `runtime_owner`, and `writer_bindings` are valid concepts.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_check_table_ownership.py -q
  ```

  Expected: the existing checker lacks Phase 1 per-table binding annotations, source-write coverage, workload candidate parity, and live-schema parity; unassigned migration 998 is not yet rejected by that extension.

- [ ] Extend the shared checker with per-table annotation parsing, strict tagged-binding validation, exact workload candidate parity, forbidden legacy-ownership source ratchet, exact operation-to-interface source-write coverage, live disposable-schema comparison, narrow exception validation, and symbol resolution. Deterministic errors report table, migration, binding ID/kind, operation, declared/catalog business context, candidate delta, interface, and reason without inspecting row data; `check_architecture_catalogs.py` continues delegating to this same engine.
- [ ] Verify migration 248's Task 2 annotations for its four new control tables and four claim-column mutations, then update the executable catalog with the same bindings. The control-plane rows must show static protected grant/census/audit bindings and heartbeat-evidence-only telemetry; the four migrated tables must retain every cataloged producer operation and add exactly the table/workload/candidate/mode/interface bindings listed in Task 2. With a nonempty `TEST_DATABASE_URL` pointing only to disposable PostgreSQL after the canonical runner applies through 248, run the checker's explicit `--schema-file backend/tests/fixtures/schema_tables.txt --refresh-schema-file` mode, review the sorted diff, and commit that regenerated fixture. A mocked, parsed-DDL, or empty database URL cannot regenerate or satisfy G16.
- [ ] Add CI that creates disposable PostgreSQL, applies the canonical runner through 248, and runs the shared checker against all `migrations_v2` files, the canonical schema fixture, the live database, and the catalog. Text-only DDL extraction is a supplemental signal, never G16 proof.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_check_table_ownership.py -q
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/check_table_ownership.py --migration-dir backend/db/migrations_v2 --schema-file backend/tests/fixtures/schema_tables.txt --refresh-schema-file --database-url "$TEST_DATABASE_URL" --catalog backend/architecture/catalogs/data/table_ownership.json
  PYTHONPATH=. python scripts/check_table_ownership.py --migration-dir backend/db/migrations_v2 --schema-file backend/tests/fixtures/schema_tables.txt --database-url "$TEST_DATABASE_URL" --catalog backend/architecture/catalogs/data/table_ownership.json
  ```

  Expected: the live disposable schema, refreshed fixture, per-table migration bindings, workload candidates, resolved source writes, and real catalog agree exactly; 998 is rejected; 999 passes; every migrated consumer transition is dynamically fenced while producer operations remain usable; no exception is expired.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/architecture/catalogs/tables.py apps/backend-rag/backend/architecture/catalogs/data/table_ownership.json apps/backend-rag/scripts/check_table_ownership.py apps/backend-rag/scripts/tests/test_check_table_ownership.py apps/backend-rag/backend/tests/fixtures/schema_tables.txt apps/backend-rag/backend/tests/fixtures/migrations .github/workflows/table-ownership.yml apps/backend-rag/backend/db/migrations_v2/248_worker_plane_ownership.sql
  git commit -m "ci(architecture): enforce table ownership contracts" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 8: Prove stale-owner, old-build, and dual-active rejection end to end (G2)

**Files:**

- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_fencing_acceptance.py`
- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_compatibility_release.py`
- Create: `apps/backend-rag/scripts/verify_worker_plane_phase1.py`
- Create: `apps/backend-rag/scripts/tests/test_verify_worker_plane_phase1.py`
- Modify: `apps/backend-rag/backend/worker_plane/liveness.py`
- Modify: `apps/backend-rag/backend/app/routers/health.py`

The acceptance scenario uses a disposable PostgreSQL database and real migration 248. It seeds a workload at generation N with the current `runtime_owner` and an audited expected-instance census, starts two simulated runtime instances, and exercises real legacy claim SQL. The stale instance must be blocked at startup/config validation, enqueue/claim, and a late irreversible-effect checkpoint. A pre-compatible SQL statement without claim metadata must be rejected by a guard armed only inside this disposable scenario. A missing expected heartbeat, unexpected instance, or heartbeat below the build floor must make guard arming fail. The scenario then proves audited CAS disarm, performs a reverse CAS, and proves the returned prior `runtime_owner` has generation N+2 and can claim while the former target `runtime_owner` is stale.

- [ ] Write integration tests for: duplicate active configuration fails before task creation; same-owner internal concurrency succeeds; incomplete expected-instance census blocks arm; stale owner cannot claim; stale generation cannot claim; old build cannot promote/arm; pre-compatible SQL cannot claim after disposable arming; ownership changes between claim and effect block the effect; missing ownership store blocks irreversible effect; audited CAS disarm is reversible and stale-version-safe; and reverse cutover restores service with a new generation.
- [ ] Add liveness assertions for zero owner, two declared active owners, stale heartbeat, old build, queue SLO breach, and healthy single owner. `/health/workloads` must expose reason codes and HTTP 503 for every invalid ownership state.
- [ ] Write verifier tests requiring G1 canonical route mutation, four-table ownership schema, dynamic refresh for every cataloged durable loop, four-pilot claim compatibility, expected-instance build-floor arm/disarm proof on disposable PostgreSQL, database legacy-SQL rejection, event fanout, G2 scenario, and mandatory live G16 table ownership. Missing or skipped gates fail.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_fencing_acceptance.py backend/tests/integration/worker_plane/test_compatibility_release.py scripts/tests/test_verify_worker_plane_phase1.py -q
  ```

  Expected: at least one stale/old/pre-compatible scenario reaches claim/effect or the phase verifier is absent.

- [ ] Implement only the minimal fixes revealed by the integration tests. Do not add worker process placement or cutover wiring.
- [ ] Implement `verify_worker_plane_phase1.py` as a fixed allowlisted command runner with JSON evidence hashes and timeouts. It must also invoke the Phase 0 verifier to prevent regression.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_fencing_acceptance.py backend/tests/integration/worker_plane/test_compatibility_release.py scripts/tests/test_verify_worker_plane_phase1.py -q
  PYTHONPATH=. python scripts/verify_worker_plane_phase1.py --output /tmp/worker-plane-phase1-evidence.json
  ```

  Expected: every stale/dual/old/missing scenario fails closed; reverse cutover succeeds with a newer generation; verifier JSON is all-pass.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/tests/integration/worker_plane apps/backend-rag/scripts/verify_worker_plane_phase1.py apps/backend-rag/scripts/tests/test_verify_worker_plane_phase1.py apps/backend-rag/backend/worker_plane/liveness.py apps/backend-rag/backend/app/routers/health.py
  git commit -m "test(worker-plane): prove fencing and ownership acceptance" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 9: Prepare the pre-merge compatibility candidate and disposable proof

**Files:**

- Create: `docs/architecture/worker-plane-phase1-compatibility-release.md`
- Create: `docs/runbooks/worker-plane-ownership-guard.md`
- Modify only if evidence reveals a defect: Phase 1 implementation/test files above

This task proves release mechanics before merge; it is not a live deployment. The candidate contains migrations/schema, four-pilot application fencing, expected-instance census, dynamic heartbeat reporting for every cataloged durable loop, and kill switches while current owners remain assigned. No staging/production deploy, ownership cutover, live observation, or live guard arming occurs. Those actions begin only in the final rollout after the protected compatibility merge.

- [ ] Record the candidate commit, build ID, monotonic build epoch, disposable fixture grants, authoritative expected-instance fixture source, workload concurrency, kill-switch state, and audited rollback/disarm commands in the compatibility document.
- [ ] Run the complete local/CI verifier and obtain normal PR review. Stop if Phase 0 regresses or any route/behavior snapshot changes.
- [ ] Provision only disposable PostgreSQL, apply migrations through 248, and import its authoritative expected-instance inventory from a checked synthetic deployment/process-manifest fixture through audited `register-instance`/`retire-instance` operations. Runtime self-registration is not census evidence.
- [ ] Run the disposable heartbeat harness for at least one full lease plus one complete polling/scheduling interval for every cataloged durable loop. For scheduled notification work, prove registration and heartbeat without sending any notification.
- [ ] Collect aggregate, non-PII disposable evidence: expected and fresh fixture-instance sets are equal; all instances have the candidate `build_id/build_epoch`; owner/generation match; no duplicate active context; synthetic queue oldest age/depth stays within SLO; pilot claim metadata appears only on synthetic jobs; route snapshot is unchanged; guards begin false.
- [ ] Exercise each pilot kill switch on synthetic disposable work and prove claims stop before effects and resume after a valid dynamic grant refresh. Never use a live client message or document as the canary.
- [ ] Write the runbook for `status`, `floor`, `census`, `register-instance`, `retire-instance`, single-workload `arm`, audited CAS `disarm`, and reverse-CAS rollback. State that manual SQL updates are forbidden, rollback always advances generation, and production inventory import/observation/arming is executed only by the final rollout after protected merge.
- [ ] Verify the disposable build floor before simulated arm:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/worker_plane_guard.py status --environment disposable --database-url "$TEST_DATABASE_URL" --output /tmp/worker-plane-disposable-status.json
  PYTHONPATH=. python scripts/worker_plane_guard.py census --environment disposable --database-url "$TEST_DATABASE_URL" --output /tmp/worker-plane-disposable-census.json
  PYTHONPATH=. python scripts/worker_plane_guard.py floor --environment disposable --database-url "$TEST_DATABASE_URL" --output /tmp/worker-plane-disposable-floor.json
  ```

  Expected: every non-empty expected-instance set equals the compatible fresh heartbeat set; every guard remains unarmed; no ownership has moved.

- [ ] On disposable data only, arm one pilot guard through the audited CLI, rerun G2 with synthetic work, disarm through the expected-version CAS CLI, and prove both audit rows plus restored inert behavior. Finish with every disposable guard false. Never pass live staging or production credentials to this task.
- [ ] Record explicitly that live staging/production compatibility observation and all live guard arming remain pending in the final rollout; Phase 1 cannot claim live-environment evidence.
- [ ] Commit documentation/evidence without secrets or client data:

  ```bash
  git add docs/architecture/worker-plane-phase1-compatibility-release.md docs/runbooks/worker-plane-ownership-guard.md
  git commit -m "docs(worker-plane): record compatibility release evidence" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 10: Run the complete Phase 1 gate and independent review panel

**Files:**

- Create: `scripts/review_sets/phase-1.json`
- Create: `.github/workflows/worker-plane-phase1.yml`
- Create: `docs/architecture/worker-plane-phase1-exit.md`
- Create: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/00-review-brief.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/00-review-packet.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/input-manifest.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/freeze-receipt.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/01-fable-5-architecture.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/01-fable-5-architecture.raw.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/01-fable-5-architecture.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/01-fable-5-architecture.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/02-gemini-3.1-pro-high.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/02-gemini-3.1-pro-high.raw.txt`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/02-gemini-3.1-pro-high.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/02-gemini-3.1-pro-high.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/03-glm-5.2-adversarial.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/03-glm-5.2-adversarial.raw.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/03-glm-5.2-adversarial.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/03-glm-5.2-adversarial.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/<attempt-id>/99-disposition.md`
- Modify as findings require: only Phase 1 implementation/test/docs files listed above

The review directory follows the master plan convention and uses its canonical Git-object projection, length-framed packet, content-addressed store, single-buffer stdin launcher, empty cwd, and no-tool routes without variation. Each normalized file records `input_manifest_sha256`, external `packet_sha256`, required `launcher_invocation_uuid`, nullable provider fields, executable/config/argv/raw hashes, and the unedited exact six-heading body.

- [ ] Add CI running Phase 0 verifier, route mutation/parity, migration 248, ownership service, four compatibility paths, DB claim guards, fanout guard, G2 integration, G16 ownership, migration linters, Ruff, and placeholder scan.
- [ ] Run the complete local gate:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/setup backend/tests/worker_plane backend/tests/integration/worker_plane backend/tests/services/workflow/test_queue.py backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py backend/tests/unit/app/modules/notifications/test_scheduler_fencing.py backend/tests/unit/services/test_wa_outbox_worker.py backend/tests/services/events/test_event_fanout_guard.py backend/tests/db/test_migration_248_worker_plane_ownership.py -q
  pytest scripts/tests/test_worker_plane_guard.py scripts/tests/test_check_event_fanout.py scripts/tests/test_check_table_ownership.py scripts/tests/test_verify_worker_plane_phase1.py ../../scripts/tests/test_check_worker_plane_review.py -q
  PYTHONPATH=. python scripts/check_router_asyncpg_ratchet.py
  PYTHONPATH=. python scripts/check_event_fanout.py
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/check_table_ownership.py --migration-dir backend/db/migrations_v2 --schema-file backend/tests/fixtures/schema_tables.txt --database-url "$TEST_DATABASE_URL" --catalog backend/architecture/catalogs/data/table_ownership.json
  PYTHONPATH=. python scripts/verify_worker_plane_phase1.py --output /tmp/worker-plane-phase1-final.json
  ruff check backend/architecture backend/worker_plane backend/app/setup backend/app/rag_proxy.py backend/services/workflow backend/services/ingestion/legal_full_ingestion_worker.py backend/services/integrations/wa_outbox_worker.py scripts
  if rg -n 'TODO|TBD|FIXME|NotImplementedError' backend/architecture backend/worker_plane docs/architecture/worker-plane-phase1* docs/runbooks/worker-plane-ownership-guard.md; then exit 1; fi
  git diff --check
  ```

  Expected: all tests/checkers/verifiers pass; the inverted forbidden-marker scan exits 0 only when it finds no match; diff check is silent.

- [ ] Write and test `scripts/review_sets/phase-1.json` as the canonical newline-terminated JSON object `{"covered":[...]}`, with a raw-UTF-8-sorted, duplicate-free path array covering every committed Phase 1 implementation, test, catalog, migration, and non-generated evidence path. Exclude `00-review-brief.md`, which is the sole instructions entry, and exclude all generated packet/review/receipt/disposition attestations. The freezer must load the set from the recorded source commit and reject missing, non-canonical, unsorted, duplicate, nonexistent, or instructions-overlapping paths. Commit the set and brief with the Phase 1 implementation/evidence before selecting `H0`.
- [ ] Commit Phase 1 implementation/evidence, require clean tracked status, and freeze the immutable review projection from committed Git objects:

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
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/00-review-brief.md \
    --covered-set phase-1 --output-store "$REVIEW_STORE")"
  PACKET_SHA256="$(printf '%s\n' "$FREEZE_JSON" | "$PYTHON" -c 'import json, sys; print(json.load(sys.stdin)["packet_sha256"])')"
  ```

  Include base/head, patch hash, verifier hash, route mutation proof, exact four-table migration schema, disposable expected-instance/build-floor evidence, proof that all guards finish false and no live action occurred, G2/live-G16 output, audited disarm/rollback procedure, and a no-client-data declaration.

- [ ] Dispatch all three seats through the checked canonical launcher; it reads the frozen packet once, constructs one deterministic manifest-hash/packet-length attestation header plus the exact packet, and feeds that identical stdin buffer from an empty sandbox cwd. Fable uses safe-mode/plan, GLM uses safe-mode/`dontAsk`, both with `--tools "" --disable-slash-commands --strict-mcp-config --mcp-config '{"mcpServers":{}}'`; Gemini uses the exact stdin-headless plan+sandbox route with no `-p` or prompt argument. Use only absolute hashed binaries/config and atomically write normalized reviews, raw stdout, stderr, and receipts before any seat can see another:

  ```bash
  ATTEMPT_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  REVIEW_ATTEMPT_DIR="docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/attempts/$ATTEMPT_ID"
  "$PYTHON" scripts/launch_worker_plane_review_panel.py \
    --frozen-review "$REVIEW_STORE/sha256/$PACKET_SHA256" \
    --output-dir "$REVIEW_ATTEMPT_DIR"
  ```

- [ ] Validate distinct required launcher UUIDs, one common manifest/packet identity, exact route proof, exit 0, and raw stdout/stderr hashes. Provider session/model fields remain nullable and are checked only when emitted; requested route is not a provider declaration. The launcher already generated the normalized Markdown under the six-heading contract; no manual normalization is allowed.

- [ ] Build `99-disposition.md`: cover exactly every stable finding ID once; classify it Blocking, Important, or Advisory; record accepted/rejected with evidence, fixing commit, and rereview state. Rejection requires concrete repository evidence; Blocking/Important cannot remain unresolved.
- [ ] Fix every accepted Blocking and Important finding with a new RED test, minimal GREEN fix, atomic commit, and full verifier rerun. Any covered input byte/role/path change invalidates all seats and reruns Fable, Gemini, and GLM. Attestation/disposition-only changes require integrity revalidation plus `projection(H1) == projection(H0)`, not a recursive rerun.
- [ ] Repeat until all three reviewers return `GO` or `GO-WITH-CHANGES` with no unresolved blocking condition and `99-disposition.md` has zero unresolved Blocking/Important rows.
- [ ] Complete the disposition, commit the fresh attempt's exact canonical files as `H1`, prove the covered/instructions projection is unchanged, then validate review integrity. The checker runs only after `H1` exists and rejects any supplied path that is not committed there byte-for-byte:

  ```bash
  "${EDITOR:-vi}" "$REVIEW_ATTEMPT_DIR/99-disposition.md"
  git add -- "$REVIEW_ATTEMPT_DIR"
  git commit -m "docs(worker-plane): record phase one exit review" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  H1="$(git rev-parse 'HEAD^{commit}')"
  "$PYTHON" scripts/freeze_worker_plane_review.py compare-projection \
    --repo "$REPO_ROOT" --left "$H0" --right "$H1" \
    --covered-set phase-1 \
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/00-review-brief.md
  "$PYTHON" scripts/check_worker_plane_review.py \
    --repo "$REPO_ROOT" --h0 "$H0" --h1 "$H1" \
    --covered-set phase-1 \
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-1/00-review-brief.md \
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
  PYTHONPATH=. python scripts/verify_worker_plane_phase1.py --output /tmp/worker-plane-phase1-reviewed.json
  git diff --check
  ```

  Expected: review validator and Phase 1 verifier exit 0; no unresolved Blocking/Important finding remains.

- [ ] Verify the already committed final gate/review evidence; do not create a later artifact commit after the checker:

  ```bash
  git show --stat --oneline "$H1"
  test -z "$(git status --porcelain --untracked-files=no)"
  ```

## Phase 1 Exit Gate

Phase 1 is complete only when all statements below are proven:

- [ ] One `RouterEntry` mutation changes both mounting and RAG proxy behavior; public route snapshots remain unchanged; no manual heavy-prefix/second manifest exists.
- [ ] Workload ownership, authoritative expected-instance census, heartbeat, and audit tables plus additive claim columns exist from migration 248; rollback remains additive/non-destructive through the recovery window.
- [ ] Runtime grants refresh before every claim and late irreversible effect; startup-only ownership caches are absent.
- [ ] Every durable loop classified in Phase 0 has startup ownership validation, heartbeat, and liveness wiring across `app_factory.py`, `main_api.py`, `service_initializer.py`, and `drive_poll_worker.py`; only workflow, legal, notification, and WA are claim/effect-fencing pilots and all retain current placement.
- [ ] Database claim triggers remain inert in every live environment; disposable proof shows they can arm only when the complete authoritative expected-instance set equals fresh compatible heartbeats, reject pre-compatible SQL, and disarm through audited expected-version CAS.
- [ ] G2 proves dual-active configuration fails before claim, stale owner/generation/old build fail at all checkpoints, storage outage fails closed for irreversible effects, and reverse cutover increments generation and restores claim ability.
- [ ] Durable global-ack events accept only one consumer at catalog, subscribe, runtime-startup, and CI gates.
- [ ] G16 applies migrations through 248 to disposable PostgreSQL and proves live schema/fixture/catalog/annotation parity while rejecting unassigned/duplicate/expired ownership and unresolved write-interface symbols.
- [ ] Phase 0 G6/G7/G17 and the process-local liveness precursor remain green; full G11 remains explicitly `deferred-to-phase2-staging`, and no workload has moved to the future worker process.
- [ ] The compatibility candidate has been exercised only in disposable PostgreSQL for a full synthetic workload interval; simulated arm/disarm was single-workload and audited; all live staging/production deploy, observation, and arming remain deferred to the final rollout after protected merge.
- [ ] Fable 5, Gemini 3.1 Pro High, and GLM 5.2 independently reviewed the immutable packet; every Blocking and Important finding was fixed, every covered/instructions projection change reran all three seats, and attestation-only changes with equal projection received integrity revalidation only.
- [ ] No migration after `248_worker_plane_ownership.sql` was consumed in this phase; 249 remains the next free migration number.
