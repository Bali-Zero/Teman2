# Modular Worker Plane Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and prove, before the protected compatibility merge, the companion-worker runtime, least-privilege role contract, no-public-service Fly declaration, exact-digest staging deploy tooling, readiness/failure-injection behavior, and a 30-minute side-effect-free resource profile. Phase 2 produces code, tests, CI contracts, and an independently reviewed post-merge runbook; it does not create or mutate a Fly app or a live staging database role.

**Architecture:** Phase 2 adds the isolated process-plane implementation without moving ownership or touching live staging. The proposed companion is constrained to one 1 GB Machine from the primary release digest, receives `WORKER_DATABASE_URL` instead of the API/RAG database credential, exposes only a top-level Fly check on `0.0.0.0:9091/ready`, and loads workload adapters by string reference only after validated runtime mode selection. Before merge, all Fly and role mutations are exercised through injected subprocess/database evidence; failure injection runs against a local process and disposable PostgreSQL fixture; the 30-minute resource profile runs on Pro/CI with synthetic or disposable inputs and no external effects. The phase also defines a private `nuzantara-rag-staging` API/RAG target so the post-merge staging drill has a real legacy owner to drain and reactivate. After protected merge, `.github/workflows/fly-deploy.yml` performs the exact production sequence defined below and exports the immutable successfully deployed digest. Only production-rollout Task 2 may consume that artifact through the environment-protected `.github/workflows/worker-plane-production.yml`, whose staging job deploys both named apps by exact `--image` digest, applies the additive schema once through the staging primary, reconciles separate primary/worker roles, and proves live forward/reverse behavior. `.github/workflows/worker-plane-phase2.yml` is pre-merge CI only and has no live credentials, environment, or manual mutation dispatch.

**Tech Stack:** Python 3.11+, asyncio, asyncpg, minimal stdlib HTTP server, psutil, PostgreSQL ownership/heartbeat tables and Phase 1 services, Fly.io Machines/apps, GitHub Actions, pytest/pytest-asyncio, Ruff, TOML, JSON evidence artifacts.

## Global Constraints

- Phase 0 and Phase 1 must be implemented, committed, independently reviewed, and verifier-green earlier on this same feature branch before Phase 2 implementation begins. They do not need to be merged separately; the protected compatibility merge happens only after all implementation phases and their panels pass. Migration `247_worker_plane_ownership.sql` is the latest schema migration entering this phase.
- Phase 2 creates no SQL migration. It reuses `BusinessContext`/`business_context`, `RuntimeOwner`/`runtime_owner`, `worker_workload_ownership`, `worker_owner_heartbeats`, `worker_ownership_audit`, `OwnershipRepository`, `OwnershipService`, `OwnershipGrant`, `OwnerHeartbeat`, `ClaimContext`, `BuildFloorEvidence`, and `LivenessReport` exactly as defined in Phase 1. Business ownership and runtime placement remain independent; this phase introduces no compatibility alias between them. Migration number `248` is reserved for Phase 3; `249` remains free after the Phase 3 plan.
- Work only in an isolated worktree created by `scripts/agent_start.py`. Preserve unrelated files and never mutate the shared checkout.
- Run backend Python from `apps/backend-rag/.venv` with `PYTHONPATH=.`. Heavy tests and the 30-minute side-effect-free profile run on Pro/CI only. Air-M5 may edit, run static checks, and dispatch the branch; it must not install Fly, Docker, PostgreSQL, Qdrant, or rendering/inference dependencies. Phase 2 must not contact Fly or any live staging database from any machine.
- `nuzantara-rag-staging`, `nuzantara-worker-staging`, and `nuzantara-worker` are declaration-only targets in this phase. Phase 2 must not create, mutate, deploy, scale, inspect, reconcile, read heartbeats from, or dispatch a live workflow against any of them. All live staging operations belong exclusively to production-rollout Task 2 after the protected compatibility merge.
- `.github/workflows/fly-deploy.yml` already auto-runs production migrations and API/RAG deployment on a protected `main` push; it does not deploy the separate production companion. Phase 2 must test and harden its exact order as: pre-deploy gate -> old-image idempotent SQL pass -> one remote build whose fresh-image release command runs `apply-all && schema_audit` before promotion -> immutable digest convergence -> idempotent post-deploy SQL-v2 -> manifest-driven Python migrations with no orphan script -> explicit fresh-image `schema_audit` -> blocking public health/contract checks -> immutable digest export. A centralized `always()` rollback/escalation job must cover every failure after promotion, including convergence, SQL, Python, schema-audit, health, contract, and export failure; digest export must be impossible unless all post-promotion gates succeed and rollback did not run. The single manual `.github/workflows/worker-plane-production.yml` has statically separate `worker-staging` and `worker-production` environment jobs. Its staging job accepts only that artifact and passes the exact digest to both named staging apps with `fly deploy --image`; its production job remains undispatchable until rollout Task 3 receives the green post-staging gate. Neither job rebuilds an equivalent tag. The CI-only `.github/workflows/worker-plane-phase2.yml` contains no `workflow_dispatch`, Fly token, protected environment, or live mutation command.
- Worker-plane topology, workload capability, and staging fault mutation have one live surface: `.github/workflows/worker-plane-production.yml`; guard/ownership changes have the separate Phase 3 `.github/workflows/worker-plane-live-control.yml`. The existing primary producer remains `.github/workflows/fly-deploy.yml`. Legacy direct deploy/migration scripts must be retired to fail-closed guidance, and a source ratchet must reject any protected-app build, deploy, secret/grant, migration, or Machine mutation outside those exact workflows. Unrelated explicitly cataloged app recovery paths may remain only when their literal app targets cannot resolve to the four protected apps and the exception has owner plus expiry.
- Before merge, deploy tooling consumes a candidate digest contract and injected Fly JSON only. No packet, verifier, or exit document may claim a primary/staging digest match, staging deployment, live grant audit, live heartbeat, live shadow observation, or live rollback.
- `apps/backend-rag/fly.worker.toml` intentionally has no `[deploy].release_command`. The API/RAG primary is the sole migration runner in each environment: production through `apps/backend-rag/fly.toml`, staging through `apps/backend-rag/fly.staging.toml`. A worker may never run migrations.
- Both declared staging configs have no `[http_service]`, no `[[services]]`, no public hostname dependency, and no public application route. The worker's only platform probe is a top-level `[[checks]]` entry for internal port `9091` and path `/ready`; the private API/RAG target uses process-scoped internal checks and the same image/process commands as production. Phase 2 proves these properties statically.
- The app receives `WORKER_DATABASE_URL`; it must reject `DATABASE_URL`. Its PostgreSQL role contains exactly the effective grant union derived from `WORKLOAD_CATALOG` and configured modes. Effective grants include direct grants, inherited role membership, ownership, and `PUBLIC`; any excess or missing privilege fails readiness.
- Provider secrets are absent from the declared config and every pre-merge fixture. A shadow adapter may execute cataloged read-only aggregate queries against disposable fixtures and write its own fixture heartbeat; it may not claim, update domain rows, invoke `OwnershipService.assert_claim_allowed`, execute a side effect, or import a provider client.
- The legacy owner remains `active` in `worker_workload_ownership`. A companion `shadow` heartbeat is observational evidence and is never interpreted as an ownership transition or build-floor vote for the current owner.
- Fixed absolute budgets are one declared shared-CPU 1x 1 GB Machine, readiness within 60 seconds, RSS at or below 750 MiB steady state, RSS at or below 850 MiB peak over a 30-minute local Pro/CI run, and no more than eight disposable database connections. A breach blocks the phase; no implementation task may resize the proposed VM or amend a ceiling. This profile is implementation evidence, not live Fly capacity evidence.
- The base entrypoint must not eagerly import `backend.app.setup.app_factory`, any `backend.app.routers` module, Qdrant clients, workflow executors, legal ingestion, LangGraph, Torch, Transformers, or inference models. Adapter imports happen only after catalog and grant validation selects that adapter.
- Readiness is behavioral. Killing or wedging the worker event loop while the probe thread remains alive must make `/ready` return 503 within the configured watchdog interval. HTTP 200 requires a current event-loop tick, live database round trip, an exact canonical `route_catalog_hash()`, current build-SHA heartbeat, and passing effective-grant audit.
- Do not inspect or persist job payloads or client records. Shadow metrics and evidence contain counts, ages, canonical route-catalog hashes, build IDs, memory, connections, and reason codes only.
- Every test is written and observed failing for the stated reason before implementation. Refactoring follows GREEN and reruns the focused suite without changing behavior.
- Every task receives a fresh read-only review through `superpowers:subagent-driven-development` before commit. The reviewer receives the task contract, exact diff, RED output, GREEN output, and checks for scope, test quality, security, and rollback. Resolve every blocking observation, rerun tests, request rereview, then create one atomic conventional commit.
- Never use `--no-verify`, `--amend`, force push, or direct push to `main`. No production or live staging change is authorized by this plan. The implementation must make live actions impossible unless the protected post-merge workflow supplies environment approval, the exported immutable production digest, commit SHA, and explicit confirmation.
- The phase cannot exit with placeholder implementation, skipped required gates, expired exceptions, an unresolved Blocking/Important review finding, or evidence copied from a different build digest.

## File Responsibility Map

| Area                 | Files owned by this phase                                                                                                                                                                                                                                                                                                                                                                                             | Responsibility                                                                                                                                                                                                        |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Infrastructure truth | `.claude/rules/infrastructure.md`, `CLAUDE.md`, `apps/backend-rag/fly.toml`, `apps/backend-rag/fly.staging.toml`, `docs/architecture/runtime-inventory.md`                                                                                                                                                                                                                                                            | Replace fixed app-count claims with a dated repository inventory, approved private staging primary/worker and production companion targets, and the existing external-Qdrant declaration without adding a live claim. |
| Worker runtime       | `apps/backend-rag/backend/workers/runtime.py`, `runtime_config.py`, `registry.py`, `readiness.py`, `metrics.py`                                                                                                                                                                                                                                                                                                       | Lazy startup, mode validation, watchdog, readiness, telemetry, and adapter loading.                                                                                                                                   |
| Grant boundary       | `apps/backend-rag/backend/worker_plane/grant_audit.py`, `apps/backend-rag/scripts/worker_database_role.py`                                                                                                                                                                                                                                                                                                            | Derive and audit effective grants without duplicating ownership authority.                                                                                                                                            |
| Shadow adapter       | `apps/backend-rag/backend/workers/adapters/workflow_shadow.py`                                                                                                                                                                                                                                                                                                                                                        | Read-only aggregate observation of `workflow_jobs`.                                                                                                                                                                   |
| Fly contract         | `apps/backend-rag/fly.staging.toml`, `apps/backend-rag/fly.worker.toml`, `apps/backend-rag/scripts/check_worker_fly_config.py`, `deploy_worker_staging.py`, `deploy_worker_production.py`                                                                                                                                                                                                                             | Static private-topology declarations plus injected exact-digest staging/production deploy, scoped capability, update, and rollback command contracts; no Phase 2 live invocation.                                     |
| CI and evidence      | `.github/workflows/fly-deploy.yml`, CI-only `.github/workflows/worker-plane-phase2.yml`, live `.github/workflows/worker-plane-production.yml`, `scripts/worker_plane/check_live_mutation_routes.py`, `apps/backend-rag/scripts/verify_worker_plane_phase2.py`, `docs/architecture/worker-plane-phase2-exit.md`, `docs/runbooks/worker-companion-staging.md`, `docs/runbooks/worker-companion-production-bootstrap.md` | Protected primary ordering/rollback/digest export, one coordinated post-merge staging/production capability workflow, retired alternate mutation paths, local G13/G14/resource/G9 proof, and pre-merge exit record.   |

## Interfaces and Invariants

The runtime configuration contract is deliberately small:

```python
@dataclass(frozen=True)
class WorkerRuntimeConfig:
    build_id: str
    build_epoch: int
    instance_id: str
    database_url: SecretStr
    route_catalog_hash: str
    modes: Mapping[str, OwnershipMode]
    ready_host: str = "0.0.0.0"
    ready_port: int = 9091

def load_worker_runtime_config(environ: Mapping[str, str]) -> WorkerRuntimeConfig: ...
def adapter_reference(workload_name: str, mode: OwnershipMode) -> str | None: ...
async def run(config: WorkerRuntimeConfig) -> None: ...
def main() -> None: ...
```

`registry.py` stores only lazy string references. Phase 2 has exactly one non-`None` mapping: `("workflow_queue", OwnershipMode.SHADOW) -> "backend.workers.adapters.workflow_shadow:run_shadow"`. Every `OFF` mapping returns `None`; any `ACTIVE` or `DRAINING` request fails startup because Phase 2 ships no active adapter.

Readiness uses one immutable report shape:

```python
@dataclass(frozen=True)
class WorkerReadinessReport:
    ready: bool
    build_id: str
    route_catalog_hash: str
    event_loop_current: bool
    database_current: bool
    heartbeat_current: bool
    grants_exact: bool
    reason_codes: tuple[str, ...]

async def evaluate_worker_readiness(...) -> WorkerReadinessReport: ...
```

The hash has one source of truth: `backend.app.setup.router_manifest.route_catalog_hash()`. Runtime configuration reads an expected `WORKER_ROUTE_CATALOG_HASH`, recomputes the canonical function locally, and fails before opening resources when they differ. No worker-specific serializer, copied hash algorithm, or generic `catalog_hash` alias is permitted.

The HTTP probe returns only this aggregate report and HTTP 200/503; it never serializes environment values, DSNs, role names, SQL, job identifiers, or payload fields.

---

## Task 1: Reconcile infrastructure governance and freeze the companion release policy

**Files:**

- Modify: `.claude/rules/infrastructure.md`
- Modify: `CLAUDE.md`
- Modify: `apps/backend-rag/fly.toml`
- Create: `docs/architecture/runtime-inventory.md`
- Create: `apps/backend-rag/scripts/check_runtime_inventory.py`
- Create: `apps/backend-rag/scripts/tests/test_check_runtime_inventory.py`

The inventory names the repository-declared primary app/process groups, the existing external-Qdrant declaration, proposed staging target `nuzantara-worker-staging`, approved future production target `nuzantara-worker`, snapshot date, and repository source for each fact. It explicitly marks live state as deferred/unknown and never substitutes a fixed app count for an inventory. The release policy states that the companion omits a release command, that the protected primary workflow owns production migrations, and that production-rollout Task 2 may deploy the worker only after receiving the immutable digest exported by that completed primary deployment.

- [ ] Write tests that reject a fixed Fly app-count sentence, internal/self-hosted Qdrant claims that conflict with `fly.toml`, an unnamed staging target, an unnamed production target, missing repository sources, any unproved live-state claim, or a worker policy that can run migrations independently.
- [ ] Add a fixture proving an inventory can distinguish repository-declared, previously evidenced, live-unknown, and approved-not-yet-created resources without presenting them as the same state.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_check_runtime_inventory.py -q
  ```

  Expected: collection fails because `check_runtime_inventory.py` and the runtime inventory do not exist.

- [ ] Implement the deterministic checker and update all three infrastructure sources. In `fly.toml`, preserve the existing external-Qdrant secret comment and primary migration runner; do not add a worker process group.
- [ ] Refactor duplicated parsing into pure functions `load_inventory(path)` and `validate_runtime_inventory(inventory, source_texts) -> list[str]`; rerun the focused test.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_check_runtime_inventory.py -q
  PYTHONPATH=. python scripts/check_runtime_inventory.py --inventory ../../docs/architecture/runtime-inventory.md
  ```

  Expected: tests pass and the checker exits 0 while reporting the declared primary runtime, proposed staging target, future production target, and external-Qdrant declaration without a fixed total or a new live claim.

- [ ] Obtain a fresh SDD read-only review of only this task's diff and test evidence; correct every blocking scope or truthfulness finding and obtain a passing rereview.
- [ ] Commit:

  ```bash
  git add .claude/rules/infrastructure.md CLAUDE.md apps/backend-rag/fly.toml docs/architecture/runtime-inventory.md apps/backend-rag/scripts/check_runtime_inventory.py apps/backend-rag/scripts/tests/test_check_runtime_inventory.py
  git commit -m "docs(infra): reconcile companion worker inventory" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 2: Add a lazy fail-closed worker entrypoint

**Files:**

- Create: `apps/backend-rag/backend/workers/runtime_config.py`
- Create: `apps/backend-rag/backend/workers/registry.py`
- Create: `apps/backend-rag/backend/workers/runtime.py`
- Create: `apps/backend-rag/backend/tests/workers/test_runtime_config.py`
- Create: `apps/backend-rag/backend/tests/workers/test_runtime_import_boundary.py`
- Create: `apps/backend-rag/backend/tests/workers/test_runtime_registry.py`

- [ ] Write configuration tests for required `WORKER_BUILD_ID`, integer `WORKER_BUILD_EPOCH`, stable `WORKER_INSTANCE_ID`, `WORKER_DATABASE_URL`, expected `WORKER_ROUTE_CATALOG_HASH`, exact equality with canonical `backend.app.setup.router_manifest.route_catalog_hash()`, valid JSON mode map, unknown workload, unsupported active/draining mode, `DATABASE_URL` presence, malformed port, and secret-safe exceptions.
- [ ] Write an import-isolation subprocess test that imports `backend.workers.runtime`, records `sys.modules`, and fails if any forbidden application/router/Qdrant/inference module loads.
- [ ] Write registry tests proving every `OFF` adapter is `None`, only workflow shadow resolves in this phase, adapter resolution validates `WORKLOAD_CATALOG`, and import occurs only when `load_adapter` is called.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/workers/test_runtime_config.py backend/tests/workers/test_runtime_import_boundary.py backend/tests/workers/test_runtime_registry.py -q
  ```

  Expected: the three modules are absent and import/configuration tests fail during collection.

- [ ] Implement `WorkerRuntimeConfig`, `load_worker_runtime_config`, `adapter_reference`, `load_adapter`, `run`, and `main`. `runtime.py` may import only stdlib plus the narrow worker-plane modules until adapter selection finishes.
- [ ] Add startup validation that all named workloads exist in `WORKLOAD_CATALOG`, every mode is `OFF` or the sole workflow `SHADOW`, build identity is nonempty, `WORKER_ROUTE_CATALOG_HASH` matches the canonical `route_catalog_hash()` result, and `DATABASE_URL` is absent.
- [ ] Refactor startup stages into pure validation followed by async resource construction so a configuration failure creates no pool, thread, task, or heartbeat.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/workers/test_runtime_config.py backend/tests/workers/test_runtime_import_boundary.py backend/tests/workers/test_runtime_registry.py -q
  PYTHONPATH=. python -c "import sys; import backend.workers.runtime; forbidden=[m for m in sys.modules if m.startswith(('backend.app.routers','backend.app.setup.app_factory','backend.core.qdrant','torch','transformers'))]; assert forbidden == [], forbidden"
  ```

  Expected: all tests pass and the explicit forbidden import list is empty.

- [ ] Obtain a fresh SDD review focused on lazy loading, environment fail-closed behavior, exact Phase 1 symbol reuse, and secret-safe errors; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/workers/runtime.py apps/backend-rag/backend/workers/runtime_config.py apps/backend-rag/backend/workers/registry.py apps/backend-rag/backend/tests/workers/test_runtime_config.py apps/backend-rag/backend/tests/workers/test_runtime_import_boundary.py apps/backend-rag/backend/tests/workers/test_runtime_registry.py
  git commit -m "feat(worker-plane): add lazy companion runtime" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 3: Derive and audit the dedicated PostgreSQL role

**Files:**

- Create: `apps/backend-rag/backend/worker_plane/grant_audit.py`
- Create: `apps/backend-rag/backend/tests/worker_plane/test_grant_audit.py`
- Create: `apps/backend-rag/scripts/worker_database_role.py`
- Create: `apps/backend-rag/scripts/tests/test_worker_database_role.py`
- Modify: `apps/backend-rag/backend/architecture/catalogs/workers.py`
- Modify: `apps/backend-rag/backend/architecture/catalogs/data/table_ownership.json`

`derive_required_grants(modes)` returns the exact set of `DatabaseGrant(object_type, object_name, privilege)` implied by `WorkloadSpec.database_grant_profile` and runtime mode. The Phase 2 base needs control-plane access sufficient for `OwnershipRepository.get_grant`, heartbeat upsert through `worker_record_heartbeat`, and grant inspection. Workflow shadow adds only `SELECT` on the columns needed to count eligible rows and calculate oldest age. It receives no claim function execution, no update/delete/insert on `workflow_jobs`, and no provider table or Qdrant credential.

- [ ] Write tests for `OFF` union, workflow `SHADOW` union, unknown profile, duplicate grants, missing required grant, direct excess grant, inherited excess grant, ownership-derived privilege, `PUBLIC` privilege, schema usage, function execute, and role-membership cycles.
- [ ] Write CLI tests for `plan`, `audit`, `reconcile-staging`, `reconcile-production-base`, and `reconcile-production-workload` using injected database adapters. Staging reconciliation requires `--app nuzantara-worker-staging`, actor, reason, confirmation, the protected staging-workflow marker, and `WORKER_ROLE_ADMIN_DATABASE_URL`. Production-base reconciliation requires `--app nuzantara-worker`, the protected `worker-production` environment marker, merged commit/digest, unchanged green post-staging gate file/hash, active-goal admission file, and an exact `OFF` grant profile. Production-workload reconciliation additionally requires one allowlisted workload, its expected prior grant hash, and a matching per-workload admission row; it derives the cumulative grant union from the canonical catalog and rejects a skipped workload, provider-secret value, excess profile, or ownership/guard mutation. Every mutating command rejects direct pre-merge invocation and never prints either DSN.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/worker_plane/test_grant_audit.py scripts/tests/test_worker_database_role.py -q
  ```

  Expected: the grant-audit module and role CLI are absent.

- [ ] Implement `DatabaseGrant`, `GrantAuditResult`, `derive_required_grants`, `read_effective_grants`, and `audit_worker_database_grants`. Inspect `information_schema` and `pg_catalog` for direct, inherited, owned, default, and `PUBLIC` capabilities; report sorted missing/excess sets.
- [ ] Implement `worker_database_role.py` with parameterized SQL identifiers validated against a strict role-name pattern. Every reconcile command revokes excess privileges before granting missing ones and runs a final audit in the same transaction. Production subcommands validate the immutable gate/admission artifacts before opening the admin connection and cannot change a guard, ownership row, login secret, or provider secret. In Phase 2 every mutating path is exercised only against fakes/disposable PostgreSQL; the runtime credential remains separate and cannot reconcile itself.
- [ ] Update the existing catalog and table ownership data rather than adding another grant manifest. Run `check_table_ownership.py` to prove all referenced objects and write interfaces resolve.
- [ ] Refactor catalog-to-grant conversion into a pure deterministic layer and keep database introspection async and injected for tests.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/worker_plane/test_grant_audit.py scripts/tests/test_worker_database_role.py -q
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/check_table_ownership.py --migration-dir backend/db/migrations_v2 --schema-file backend/tests/fixtures/schema_tables.txt --database-url "$TEST_DATABASE_URL" --catalog backend/architecture/catalogs/data/table_ownership.json
  ```

  Expected: all grant cases pass; ownership check exits 0; shadow profile contains no claim or mutation privilege.

- [ ] Obtain a fresh SDD security review of role derivation, inherited/`PUBLIC` privilege detection, distinct protected staging/production mutation gates, cumulative per-workload production grants, absence of live Phase 2 reconciliation, and catalog reuse; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/worker_plane/grant_audit.py apps/backend-rag/backend/tests/worker_plane/test_grant_audit.py apps/backend-rag/scripts/worker_database_role.py apps/backend-rag/scripts/tests/test_worker_database_role.py apps/backend-rag/backend/architecture/catalogs/workers.py apps/backend-rag/backend/architecture/catalogs/data/table_ownership.json
  git commit -m "feat(worker-plane): audit scoped companion database role" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 4: Serve behavioral readiness and persist the build heartbeat

**Files:**

- Create: `apps/backend-rag/backend/workers/readiness.py`
- Create: `apps/backend-rag/backend/workers/metrics.py`
- Create: `apps/backend-rag/backend/workers/staging_fault_control.py`
- Modify: `apps/backend-rag/backend/workers/runtime.py`
- Modify: `apps/backend-rag/backend/worker_plane/liveness.py`
- Create: `apps/backend-rag/backend/tests/workers/test_readiness.py`
- Create: `apps/backend-rag/backend/tests/workers/test_runtime_watchdog.py`
- Modify: `apps/backend-rag/backend/tests/worker_plane/test_liveness.py`

The readiness server lives in a daemon thread separate from the asyncio worker loop. It reads a thread-safe snapshot updated by the loop and returns 503 when the last event-loop tick is older than 10 seconds, the database probe is older than 10 seconds, the `OwnerHeartbeat.runtime_owner` carrying the current build is not current, the route catalog hash differs, or `GrantAuditResult.exact` is false. Phase 2 proves these behaviors in-process and against disposable PostgreSQL only. Fixture worker heartbeats may use mode `off` or `shadow`, but `verify_build_floor` continues to count only live heartbeats matching the authoritative current `runtime_owner`/generation; the equivalent live staging check is deferred to production-rollout Task 2.

`staging_fault_control.py` supplies the exact live falsification hook used later by rollout Task 2 without exposing a network endpoint. It installs one process-local signal handler that cancels/wedges the worker event-loop task while deliberately leaving the probe thread alive. Installation requires all of: `ENVIRONMENT=staging`, exact app `nuzantara-worker-staging`, `WORKER_STAGING_FAULT_INJECTION=synthetic-only`, an admitted synthetic fixture hash, and the protected-workflow marker. Production, another app, missing synthetic admission, or normal startup rejects the hook before registration. Phase 2 exercises the controller only with injected signals; `.github/workflows/worker-plane-production.yml` later owns the only live `staging-fault-wedge` and same-digest `staging-fault-recover` actions.

- [ ] Write HTTP tests for 200 all-current, stale event-loop tick, failed DB query, stale/missing build heartbeat, catalog mismatch, missing grant, excess grant, and serialization without secrets/role/DSN.
- [ ] Write G13's process-shape test: start the probe thread, use the injected staging fault controller to cancel the main loop while leaving the thread alive, advance the injected monotonic clock past 10 seconds, and assert `/ready` returns 503 with `event_loop_stale`. Add fail-closed tests for production, wrong app, missing protected marker, missing/mismatched synthetic fixture hash, unapproved signal, repeat injection, and any attempt to expose a socket/HTTP fault endpoint.
- [ ] Add liveness tests proving an observational worker shadow heartbeat neither replaces the RAG legacy owner nor satisfies the legacy owner's build floor.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/workers/test_readiness.py backend/tests/workers/test_runtime_watchdog.py backend/tests/worker_plane/test_liveness.py -q
  ```

  Expected: readiness modules are absent and Phase 1 liveness cannot distinguish an observational shadow heartbeat.

- [ ] Implement `WorkerReadinessReport`, `ReadinessSnapshot`, `WorkerProbeServer`, `evaluate_worker_readiness`, aggregate process metrics, and the staging-only injected-signal fault controller. Use monotonic time for watchdog freshness and UTC database time for heartbeat leases. The controller receives a typed cancellation callback, never a shell command, provider client, or database mutation primitive.
- [ ] Wire `runtime.run` to tick the watchdog, issue `SELECT 1`, recompute the canonical `route_catalog_hash()`, run `audit_worker_database_grants`, and persist the Phase 1 `OwnerHeartbeat` at an interval no longer than one-third of the catalog lease.
- [ ] Refactor probe encoding into a pure function and close the pool/server/task deterministically on signals; readiness becomes 503 before shutdown begins.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/workers/test_readiness.py backend/tests/workers/test_runtime_watchdog.py backend/tests/worker_plane/test_liveness.py -q
  ```

  Expected: all readiness cases pass; a live probe thread cannot mask a dead event loop; shadow heartbeats do not alter owner/build-floor truth.

- [ ] Obtain a fresh SDD concurrency/health review, including clock choice, race handling, shutdown, and G13 falsifiability; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/workers/readiness.py apps/backend-rag/backend/workers/metrics.py apps/backend-rag/backend/workers/staging_fault_control.py apps/backend-rag/backend/workers/runtime.py apps/backend-rag/backend/worker_plane/liveness.py apps/backend-rag/backend/tests/workers/test_readiness.py apps/backend-rag/backend/tests/workers/test_runtime_watchdog.py apps/backend-rag/backend/tests/worker_plane/test_liveness.py
  git commit -m "feat(worker-plane): gate companion readiness on behavior" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 5: Define and statically verify the private staging topology

**Files:**

- Create: `apps/backend-rag/fly.staging.toml`
- Create: `apps/backend-rag/fly.worker.toml`
- Create: `apps/backend-rag/scripts/check_worker_fly_config.py`
- Create: `apps/backend-rag/scripts/tests/test_check_worker_fly_config.py`
- Modify: `apps/backend-rag/Dockerfile`
- Create: `apps/backend-rag/backend/tests/workers/test_worker_container_contract.py`

`fly.staging.toml` uses `app = "nuzantara-rag-staging"`, `primary_region = "sin"`, the existing Dockerfile, and the exact production API/RAG process commands needed to reproduce the two legacy owners. It sets `ENVIRONMENT=staging`, has no production hostname, mount, public service, or embedded secret, and owns the staging database migration release command `python -m backend.db.migrate apply-all && python -m backend.db.schema_audit`. Its API and RAG readiness probes are private and process-scoped. `fly.worker.toml` uses `app = "nuzantara-worker-staging"`, the same region/Dockerfile, process command `python -m backend.workers.runtime`, environment `PORT=9091`, one `shared-cpu-1x`/1 GB VM, and a top-level HTTP check on port 9091 path `/ready`. It contains neither a service block nor a release command. The Dockerfile continues to produce the same image for all planes; it may only add a generic module entry compatibility check, not a worker-specific build stage.

- [ ] Write TOML tests for both exact app names, shared Dockerfile/digest-compatible process commands, region, private checks, missing service blocks, environment keys, and exactly one migration owner. Reject a production app/hostname, mount, hardcoded `DATABASE_URL`, provider keys, Qdrant keys, public ports, auto-resize metadata, worker release command, or a second Dockerfile. Require the staging primary release command to run both `apply-all` and `schema_audit` and the worker to run neither.
- [ ] Write a container-contract test that inspects the Dockerfile and proves the worker module exists in the same final stage as API/RAG code and that no worker-only dependency install or build target appears.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_check_worker_fly_config.py backend/tests/workers/test_worker_container_contract.py -q
  ```

  Expected: the two staging TOML contracts and their checker do not exist.

- [ ] Implement both configs and the checker. Keep process-scoped/top-level checks explicit and prove neither config creates Fly Proxy public routing. The private API/RAG config must reproduce the legacy lifecycle owners without copying production volumes or secrets.
- [ ] Refactor config validation into data-driven allowed/forbidden key sets; keep the concrete staging values asserted separately.
- [ ] Run GREEN on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_check_worker_fly_config.py backend/tests/workers/test_worker_container_contract.py -q
  PYTHONPATH=. python scripts/check_worker_fly_config.py --primary-staging-config fly.staging.toml --worker-config fly.worker.toml
  ```

  Expected: all tests pass; the checker reports one private API/RAG staging primary, one 1 GB private worker, zero services, exactly one staging migration owner, and zero worker release commands.

- [ ] Obtain a fresh SDD infrastructure review of exact-digest compatibility, no-public-service semantics, VM ceilings, and release-command omission; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/fly.staging.toml apps/backend-rag/fly.worker.toml apps/backend-rag/scripts/check_worker_fly_config.py apps/backend-rag/scripts/tests/test_check_worker_fly_config.py apps/backend-rag/Dockerfile apps/backend-rag/backend/tests/workers/test_worker_container_contract.py
  git commit -m "feat(infra): define private worker staging topology" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 6: Add the side-effect-free workflow shadow adapter and budget sampler

**Files:**

- Create: `apps/backend-rag/backend/workers/adapters/__init__.py`
- Create: `apps/backend-rag/backend/workers/adapters/workflow_shadow.py`
- Modify: `apps/backend-rag/backend/workers/registry.py`
- Modify: `apps/backend-rag/backend/workers/runtime.py`
- Create: `apps/backend-rag/backend/tests/workers/adapters/test_workflow_shadow.py`
- Create: `apps/backend-rag/backend/tests/workers/test_resource_budgets.py`
- Create: `apps/backend-rag/scripts/profile_worker_shadow.py`
- Create: `apps/backend-rag/scripts/tests/test_profile_worker_shadow.py`

`WorkflowShadowObservation` contains only `observed_at`, `eligible_count`, `oldest_eligible_age_seconds`, `queue_depth`, and `query_seconds`. `run_shadow` performs one parameterized aggregate `SELECT` against a disposable `workflow_jobs` fixture, never opens a transaction that can write, never calls `_dequeue_one`, and never reads `payload`. The profiler samples readiness duration, process RSS, disposable database connection count for the worker role fixture, event-loop lag, shadow query duration, and canonical route-catalog hash every 10 seconds for exactly 30 minutes in pre-merge acceptance mode. It does not connect to Fly or a live staging database.

- [ ] Write tests proving the SQL is `SELECT`-only, selects no `payload`, returns only aggregates, uses no `OwnershipService.assert_claim_allowed`, performs no external call, and sleeps between observations.
- [ ] Add a source/import test that fails if the shadow module imports `backend.services.workflow.executor`, `backend.services.workflow.chains`, any router, Qdrant, provider SDK, or inference package.
- [ ] Write profiler tests with an injected clock/process/database sampler for startup over 60 seconds, steady RSS over 750 MiB, peak over 850 MiB, connections over eight, duration under 1,800 seconds, missing samples, and one all-pass record.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/workers/adapters/test_workflow_shadow.py backend/tests/workers/test_resource_budgets.py scripts/tests/test_profile_worker_shadow.py -q
  ```

  Expected: adapter/profiler imports fail and no budget evaluator exists.

- [ ] Implement the shadow adapter and `ResourceBudgetReport`. Define steady RSS as the maximum sample after readiness plus 60 seconds; peak is the maximum of every sample. Count role connections with a cataloged `pg_stat_activity` aggregate and never capture query text or client metadata.
- [ ] Implement `profile_worker_shadow.py --duration-seconds 1800 --sample-seconds 10 --output <path>` with shorter durations allowed only when `--test-mode` is present. Pre-merge acceptance evidence rejects `test_mode=true`, records `environment=local-pro|ci`, and rejects any live Fly target or non-disposable DSN.
- [ ] Refactor sampling and threshold evaluation into pure functions; preserve raw aggregate samples in a redacted JSON evidence file.
- [ ] Run GREEN unit tests on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/workers/adapters/test_workflow_shadow.py backend/tests/workers/test_resource_budgets.py scripts/tests/test_profile_worker_shadow.py -q
  ```

  Expected: tests pass; mutation, provider, forbidden imports, and live-target access are impossible in the tested adapter/profile; each budget breach fails explicitly.

- [ ] Obtain a fresh SDD review of read-only SQL, PII minimization, duration/threshold math, and silent-limit-raise prevention; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/workers/adapters apps/backend-rag/backend/workers/registry.py apps/backend-rag/backend/workers/runtime.py apps/backend-rag/backend/tests/workers/adapters apps/backend-rag/backend/tests/workers/test_resource_budgets.py apps/backend-rag/scripts/profile_worker_shadow.py apps/backend-rag/scripts/tests/test_profile_worker_shadow.py
  git commit -m "feat(worker-plane): observe workflow queue in shadow" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 7: Implement the single protected exact-digest staging and production contract

**Files:**

- Create: `apps/backend-rag/scripts/deploy_worker_staging.py`
- Create: `apps/backend-rag/scripts/tests/test_deploy_worker_staging.py`
- Create: `apps/backend-rag/scripts/deploy_worker_production.py`
- Create: `apps/backend-rag/scripts/tests/test_deploy_worker_production.py`
- Modify: `.github/workflows/fly-deploy.yml`
- Create: `.github/workflows/worker-plane-phase2.yml`
- Create: `.github/workflows/worker-plane-production.yml`
- Modify: `apps/backend-rag/scripts/deploy_staging.sh`
- Modify: `apps/backend-rag/scripts/deploy_backend.sh`
- Modify: `apps/backend-rag/backend/scripts/deploy_fly.sh`
- Modify: `apps/backend-rag/scripts/run_migrations.py`
- Modify: `scripts/preflight.sh`
- Create: `scripts/worker_plane/check_live_mutation_routes.py`
- Create: `scripts/tests/test_check_live_mutation_routes.py`
- Modify: `.github/CODEOWNERS`
- Modify: `.github/workflows/hot-zone-pr-gate.yml`

The staging orchestrator implements post-merge subcommands `inspect`, `deploy-primary-legacy`, `deploy-worker-off`, `admit-workload-capability`, `revoke-workload-capability`, `promote-shadow`, and `rollback-topology`, but Phase 2 never invokes them against Fly. It targets exactly `nuzantara-rag-staging` plus `nuzantara-worker-staging`. Command construction and evidence parsing are dependency-injected so pre-merge tests use fabricated Fly JSON and fake subprocesses. A successful protected `main` deployment in `.github/workflows/fly-deploy.yml` must finish this exact chain: pre-deploy gate; old-image idempotent migration pass; rolling deploy whose fresh-image release command runs `apply-all && schema_audit` before promotion; post-deploy SQL-v2; Python migrations; explicit post-deploy fresh-image `schema_audit`; public health; immutable digest export. A centralized `always()` rollback/escalation job covers every post-promotion failure and digest export depends on every successful post-promotion job. The export resolves one converged immutable Machine `image_ref.digest`, requires `sha256:<64hex>`, binds it to `github.sha` and the workflow run/provenance, and publishes `production-compatibility-digest.json`.

The one manual `.github/workflows/worker-plane-production.yml` accepts an enum `target_environment=staging|production` and selects one of two statically declared environment-protected jobs; no dynamic environment or app name is accepted. Its staging job targets exactly `nuzantara-rag-staging` plus `nuzantara-worker-staging` and accepts only the successful primary workflow run ID, artifact hash, exact digest, merged commit, active-goal reference, and matching append-only admission row. It verifies the artifact byte-for-byte and passes its immutable registry digest to both staging deployments with `fly deploy --image`, without checkout-driven build. It records prior digests/state; installs the staging primary DSN into `nuzantara-rag-staging` as `DATABASE_URL` through protected stdin; applies migrations only through that primary's release command and manifest-driven post-release runner; verifies live G16/schema audit; creates a separately scoped worker role/`WORKER_DATABASE_URL`; and boots the worker all-off. Per-workload admission is ordered `workflow_queue -> legal_full_ingestion -> notification_scheduler -> wa_outbox`, derives cumulative primary/worker database grants and the exact source-closed provider-runtime symbol set from canonical catalogs, requires expected prior grant/symbol hashes, transports synthetic staging values only by stdin, and never logs them. Notification admission requires the exact HMAC-plus-SendGrid set and a worker adapter that bypasses SMTP/auto-detect; WA admission requires the exact outbound token-plus-phone-ID set. Any missing, excess, unused, or undeclared transitive provider dependency fails before mutation. Revocation removes only the named workload and reconciles the remaining catalog union. Guard and ownership mutation are excluded and belong to Phase 3 live control.

The staging job also exposes exactly two synthetic-only fault actions: `staging-fault-wedge` validates the `workflow_queue` staging admission/capability artifact, exact digest, exact worker app, synthetic fixture hash, and fault-enable symbol before invoking the process-local signal hook from Task 4; `staging-fault-recover` restarts only the same worker Machine on the same digest and verifies job conservation, 503-to-200 recovery, current heartbeat, and unchanged primary health. Either action rejects production, another workload/app, client data, a mutable image, or an absent synthetic admission before constructing a Fly command. This action is implemented and fake-tested in Phase 2 but invoked live only by rollout Task 2.

The production job may be dispatched only by rollout Task 3 with the unchanged green post-staging gate artifact, merged commit, exact staging-proven digest, active-goal reference, and matching admission row. Its typed `deploy_worker_production.py` actuator exposes only `inspect`, `bootstrap-off`, `admit-workload-capability`, `revoke-workload-capability`, and `rollback-digest` in the compatibility release. It targets only `nuzantara-worker`, never rebuilds or redeploys API/RAG, and may create the named companion app only after the gate. `bootstrap-off` invokes `worker_database_role.py reconcile-production-base`, installs `WORKER_DATABASE_URL` through stdin without logging it, rejects `DATABASE_URL`, carries no workload provider secret/grant, starts every workload `off`, and proves private readiness plus digest-bound heartbeat. Capability admission accepts exactly the next cataloged workload, reconciles the cumulative grant union, installs only cataloged provider-secret symbols, and cannot arm a guard or change ownership. On failure it restores a recorded prior companion digest; for a first bootstrap it scales the new app to zero, removes its runtime secret, and disables login on the new base role without destroying the app or touching API/RAG.

`.github/workflows/worker-plane-phase2.yml` is only a required PR/push CI verifier for the code above. Tests assert it has no `workflow_dispatch`, environment, Fly secret/token, `fly` mutation, or reusable path that can reach a live mutation. Existing direct scripts `deploy_staging.sh`, `deploy_backend.sh`, `backend/scripts/deploy_fly.sh`, and `run_migrations.py` become fail-closed compatibility shims that emit the protected workflow/runbook reference and exit nonzero without invoking Fly or SQL; `scripts/preflight.sh` becomes read-only and cannot restart a Machine. `check_live_mutation_routes.py` tokenizes executable shell/Python/YAML and rejects Docker/remote builds, Fly deploy/secrets/Machine lifecycle, or live role/migration mutation resolving to `nuzantara-rag`, `nuzantara-rag-staging`, `nuzantara-worker-staging`, or `nuzantara-worker` outside `fly-deploy.yml`, `worker-plane-production.yml`, and the later `worker-plane-live-control.yml`. It also rejects a mutable `--image`, worker release/public service, any live mutation in Phase 2 CI, and unowned/unexpired exceptions. CODEOWNERS and the hot-zone gate cover every Fly config, these workflows, actuators, retired shims, and the ratchet itself.

- [ ] Write subprocess-fake tests for protected-workflow marker absence, pre-merge commit rejection, mutable tag/reference rejection, production artifact/digest/commit mismatch, either staging app using the wrong digest, schema not current, primary/worker role audit failure, production DSN or secret symbol in staging, public service discovery, readiness failure, wrong/missing build heartbeat, off-mode escape, shadow promotion before off evidence, skipped workload, wrong prior grant/secret hash, excess secret, secret redaction/stdin transport, cumulative staging admission/revocation, two-digest rollback success, first-create rollback, and rollback failure escalation. Add fault-action tests for wrong environment/app/workload/digest, missing capability/admission/synthetic hash, client-data marker, unavailable signal hook, readiness remaining 200, heartbeat not stale, missing backlog alert evidence, wrong-digest recovery, primary regression, and lost synthetic job. Add production-actuator tests for wrong app/environment/gate/admission/order, wrong prior grant hash, unlisted/excess secret, secret redaction/stdin transport, base-only bootstrap, cumulative grant reconciliation, per-workload admission/revocation, prior-digest restore, and new-app scale-to-zero plus secret removal/login disable. No test may contact Fly.
- [ ] Add workflow tests proving the primary chain is exactly old-image migration -> one build/deploy with fresh-image release-command apply/audit -> immutable digest convergence -> post-deploy SQL-v2 -> manifest-driven Python migrations -> explicit fresh-image schema audit -> blocking health/contracts -> digest export. Include an orphan `apply_migration_122.py` fixture so a hardcoded 119/120/121 list fails. Prove one centralized `always()` rollback runs for convergence, SQL, Python, audit, health, contract, or export failure after promotion; export is skipped on every failure/rollback; and the artifact is bound to the deployed commit and converged immutable digest. Prove `worker-plane-production.yml` is manual with static staging/production environment jobs, deploys the exact artifact to both named staging apps with no build, owns exactly one staging migration path, uses distinct primary/worker credentials, admits/revokes only ordered catalog-derived cumulative grants and exact synthetic-secret symbols, implements only the bounded staging fault actions, excludes guard/ownership mutation, and cannot cross-target. Prove the production job rejects a missing/stale post-staging gate or admission row, targets only `nuzantara-worker`, uses the same artifact digest with no build, grants only catalog-derived base/cumulative capability, starts all modes `off`, admits only the next workload, cannot fault-inject/arm/change ownership, and cannot redeploy the primary app. Prove Phase 2 CI is credential-free and non-mutating.
- [ ] Write ratchet and shim tests that fail on the current direct checkout-build staging script, direct protected-app deploy, direct secret set/unset, live SQL/role mutation, mutating preflight, mutable image tag, unprotected workflow environment, dynamic protected-app name, or a new unowned/expired exception. Each retired shim must terminate nonzero before the injected fake Fly/SQL executable is called. The allowed live workflow/config/checker paths are CODEOWNERS/hot-zone protected, and the allowlist can only shrink.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_deploy_worker_staging.py scripts/tests/test_deploy_worker_production.py ../../../scripts/tests/test_check_live_mutation_routes.py -q
  ```

  Expected: coordinated staging/production orchestrator tests fail because the scripts and CI jobs do not exist.

- [ ] Implement both orchestrators with typed `subprocess.run` argument lists, JSON parsing, explicit timeouts, redacted evidence, stdin-only secret transport, and no shell interpolation. Every staging mutation requires both exact `--confirm-primary-app nuzantara-rag-staging` and `--confirm-worker-app nuzantara-worker-staging`, the static protected-job marker, a merged commit reachable from `origin/main`, the verified primary workflow-run artifact, and the matching immutable digest. Every production mutation requires `--confirm-app nuzantara-worker`, the static protected-job marker, unchanged gate artifact/hash, matching admission row, merged commit/digest, and exact expected prior state. Implement the two staging fault actions with the same typed/fakeable command builder and synthetic-only checks. Each actuator rejects the other environment/app, and direct pre-merge invocation fails before constructing a mutating command.
- [ ] Modify `.github/workflows/fly-deploy.yml` to add manifest-driven Python migration discovery, explicit post-deploy schema/consumer audit, centralized post-promotion rollback/escalation, and the exact digest artifact described above. Remove the health-only rollback path or delegate it to the single controller so a release cannot roll back twice. Add the single manual staging/production workflow contract and the credential-free Phase 2 CI workflow, but dispatch neither live in Phase 2. The live workflow consumes only the verified artifact digest and commit SHA and rejects a rebuilt tag or digest without artifact provenance; its production job additionally requires the unchanged green post-staging gate hash.
- [ ] Replace the named direct deploy/migration scripts with fail-closed guidance shims, remove Machine restart behavior from `scripts/preflight.sh`, implement the source ratchet, and extend CODEOWNERS/hot-zone patterns. Tests must scan the repository from its root and prove no alternate protected-app build/deploy/secret/grant/migration route remains usable.
- [ ] Add `rollback-topology`/`rollback-digest` as `if: failure()` steps in both deferred manual workflows and upload inspection/deploy/schema/heartbeat/grant/digest evidence even on failure. Unit tests prove two-app staging rollback, prior-digest production restore, first-bootstrap scale-to-zero, workload-capability revocation, and primary-production-app exclusion; no rollback is executed in Phase 2.
- [ ] Refactor Fly command construction into pure allowlisted builders and rerun all fake-command tests.
- [ ] Run GREEN on Pro/CI without contacting Fly:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_deploy_worker_staging.py scripts/tests/test_deploy_worker_production.py scripts/tests/test_worker_database_role.py ../../../scripts/tests/test_check_live_mutation_routes.py -q
  PYTHONPATH=. python scripts/check_worker_fly_config.py --primary-staging-config fly.staging.toml --worker-config fly.worker.toml
  PYTHONPATH=../.. .venv/bin/python ../../scripts/worker_plane/check_live_mutation_routes.py --repo-root ../..
  ```

  Expected: production ordering/rollback/export plus coordinated staging and production command/workflow contracts pass without network access; direct/pre-merge and cross-environment mutation are rejected; protected post-merge paths use one artifact digest and no rebuild; staging has a real legacy-owner primary plus separate all-off worker; bootstrap is base-only/all-off; capability admission is ordered/catalog-derived; and every simulated failure ends with full prior-state restoration or first-bootstrap scale-to-zero plus capability rollback.

- [ ] Obtain a fresh SDD deployment/reversibility review of the existing primary workflow ordering, post-deploy immutable digest export, pre-merge hard stop, distinct protected staging/production dispatch, heartbeat build binding, base-only bootstrap, ordered capability mutation, secret redaction, simulated failure rollback, and primary-target exclusion; fix and rereview before commit.
- [ ] Commit:

  ```bash
  git add apps/backend-rag/scripts/deploy_worker_staging.py apps/backend-rag/scripts/tests/test_deploy_worker_staging.py apps/backend-rag/scripts/deploy_worker_production.py apps/backend-rag/scripts/tests/test_deploy_worker_production.py apps/backend-rag/scripts/deploy_staging.sh apps/backend-rag/scripts/deploy_backend.sh apps/backend-rag/backend/scripts/deploy_fly.sh apps/backend-rag/scripts/run_migrations.py scripts/preflight.sh scripts/worker_plane/check_live_mutation_routes.py scripts/tests/test_check_live_mutation_routes.py .github/workflows/fly-deploy.yml .github/workflows/worker-plane-phase2.yml .github/workflows/worker-plane-production.yml .github/CODEOWNERS .github/workflows/hot-zone-pr-gate.yml
  git commit -m "ci(worker-plane): gate post-merge worker deployment" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 8: Prove the pre-merge G13 and G14 contracts locally

**Files:**

- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_phase2_staging_contract.py`
- Create: `apps/backend-rag/backend/tests/integration/worker_plane/test_phase2_failure_injection.py`
- Create: `apps/backend-rag/scripts/verify_worker_plane_phase2.py`
- Create: `apps/backend-rag/scripts/tests/test_verify_worker_plane_phase2.py`
- Create: `docs/architecture/worker-plane-phase2-premerge-evidence.md`

The verifier requires Phase 0 and Phase 1 verifiers, infrastructure inventory, worker config, lazy-import boundary, injected/disposable role audit, static no-public-service proof, candidate immutable-digest contract tests, local off-mode readiness/build heartbeat, local dead-event-loop 503, disposable workflow-shadow non-mutation, the full 1,800-second Pro/CI resource record, and a fresh complete G9 comparison against the canonical Phase 0 snapshot. The canonical inputs remain `backend/architecture/baselines/phase0_snapshot.json`, `phase0_probe_protocol.json`, and `phase0_comparison_exceptions.json`; Phase 2 captures `/tmp/worker-plane-phase2-g9-candidate.json` with `scripts/capture_worker_plane_baseline.py --require-complete-g9`, then writes `/tmp/worker-plane-phase2-g9-comparison.json` with `scripts/compare_worker_plane_baseline.py`. Both API and RAG surfaces must contain numeric process-startup seconds, maximum steady-state RSS, aggregate PostgreSQL connection count, and HTTP 5xx rate under the frozen protocol/topology/window; each metric must be at most `1.10 * baseline`, unless the exact metric has a scoped, approved, unexpired exception. Worker G13/G14 evidence is separate and cannot substitute for G9. Evidence names the candidate digest used by fakes, commit, build epoch, local process ID hash, environment (`local-pro` or `ci`), start/end timestamps, sample count, ceilings, observed maxima, canonical `route_catalog_hash`, fixture grant hash, workload modes, baseline/protocol/exception/candidate/comparison hashes, and G9 verdict. It explicitly records every live staging gate as `deferred_to_production_rollout_task_2` and contains no secrets, role credential, job IDs, payloads, Fly inspection, or live staging claim.

- [ ] Write verifier tests for every required pre-merge gate missing, skipped, stale, from another candidate digest, shortened profile duration, sample gap over 20 seconds, budget breach, nonzero fixture mutation count, forbidden live evidence, a live gate falsely marked pass, and one valid all-pass/deferred evidence record. Add G9 cases for missing/unavailable/non-numeric API or RAG metrics, protocol/topology/window drift, baseline/candidate/comparison hash mismatch, any metric above 1.10, stale/overbroad/unapproved exception, and one fully numeric passing comparison.
- [ ] Add local-process/disposable-PostgreSQL integration fixtures that snapshot aggregate workflow status counts before/after shadow, kill the event loop while leaving the probe process alive, simulate database loss/reconnect, and verify mode remains shadow without any claim metadata change. Inject every Fly response; network access to Fly fails the test.
- [ ] Run RED on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_phase2_staging_contract.py backend/tests/integration/worker_plane/test_phase2_failure_injection.py scripts/tests/test_verify_worker_plane_phase2.py -q
  ```

  Expected: Phase 2 verifier is absent and at least one local failure-injection/deferred-live-gate proof cannot be expressed.

- [ ] Implement `verify_worker_plane_phase2.py` with `collect-premerge` and `validate` subcommands. `collect-premerge` invokes only fixed allowlisted static checks and local/disposable scenarios, accepts the completed profile plus an explicitly labeled `injected-fixture` candidate digest and the complete G9 candidate/comparison artifacts, writes the canonical pre-merge evidence, and has a network deny guard for Fly/provider hosts. `validate` invokes Phase 0 and Phase 1 verifiers and verifies hashes plus every numeric G9 bound rather than trusting prose. Neither subcommand contains or calls a live staging operation.
- [ ] Start the worker process locally on Pro/CI with all modes off and a disposable database role, prove the local readiness/build-heartbeat contract, switch only the fixture `workflow_queue` mode to shadow, and run the exact 30-minute side-effect-free profiler. Stop immediately and tear down the disposable fixture on a failed check.
- [ ] Execute local G13 failure injection: kill the worker event loop without terminating the probe thread/process; require the local `/ready` check to return 503 and the disposable heartbeat to become stale within the workload SLO; restart the same candidate build in all-off mode before continuing. Do not call a Fly endpoint.
- [ ] Compare pre/post disposable aggregate status and claim-metadata counts. Require zero workflow row mutation attributable to the worker, zero provider secret in the environment fixture, and zero network attempt to Fly or provider endpoints.
- [ ] Refactor evidence validation only after the first complete fixture passes; rerun the entire focused suite.
- [ ] Run GREEN and the 30-minute pre-merge acceptance profile on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/integration/worker_plane/test_phase2_staging_contract.py backend/tests/integration/worker_plane/test_phase2_failure_injection.py scripts/tests/test_verify_worker_plane_phase2.py -q
  PYTHONPATH=. python scripts/profile_worker_shadow.py --duration-seconds 1800 --sample-seconds 10 --output /tmp/worker-plane-phase2-profile.json
  test -n "${PHASE0_DATABASE_URL:-}" && test -n "${PHASE0_REDIS_URL:-}" && test -n "${PHASE0_METRICS_URL:-}"
  PYTHONPATH=. python scripts/capture_worker_plane_baseline.py --protocol backend/architecture/baselines/phase0_probe_protocol.json --database-url "$PHASE0_DATABASE_URL" --redis-url "$PHASE0_REDIS_URL" --metrics-url "$PHASE0_METRICS_URL" --require-complete-g9 --output /tmp/worker-plane-phase2-g9-candidate.json
  PYTHONPATH=. python scripts/compare_worker_plane_baseline.py --baseline backend/architecture/baselines/phase0_snapshot.json --candidate /tmp/worker-plane-phase2-g9-candidate.json --exceptions backend/architecture/baselines/phase0_comparison_exceptions.json --output /tmp/worker-plane-phase2-g9-comparison.json
  PYTHONPATH=. python scripts/verify_worker_plane_phase2.py collect-premerge --profile /tmp/worker-plane-phase2-profile.json --g9-candidate /tmp/worker-plane-phase2-g9-candidate.json --g9-comparison /tmp/worker-plane-phase2-g9-comparison.json --candidate-digest sha256:0000000000000000000000000000000000000000000000000000000000000001 --candidate-digest-source injected-fixture --output /tmp/worker-plane-phase2-premerge.json
  PYTHONPATH=. python scripts/verify_worker_plane_phase2.py validate --evidence /tmp/worker-plane-phase2-premerge.json --output /tmp/worker-plane-phase2-verified.json
  ```

  Expected: tests pass; verifier records complete numeric API/RAG G9 at or below the 1.10 bound (or only exact approved unexpired exceptions), the local G13 contract and G14 as pass, candidate-digest command contract as pass, every live staging gate as deferred, zero public-service declarations, zero fixture shadow mutations/effects, readiness at most 60 seconds, steady RSS at most 750 MiB, peak RSS at most 850 MiB, and at most eight disposable DB connections.

- [ ] Obtain a fresh SDD acceptance review of raw pre-merge evidence hashes, disposable-fixture provenance, absence of Fly access, deferred live gates, and failure-injection validity; fix every blocking weakness, repeat affected local tests, and obtain passing rereview before commit.
- [ ] Commit only verified non-sensitive pre-merge evidence:

  ```bash
  git add apps/backend-rag/backend/tests/integration/worker_plane/test_phase2_staging_contract.py apps/backend-rag/backend/tests/integration/worker_plane/test_phase2_failure_injection.py apps/backend-rag/scripts/verify_worker_plane_phase2.py apps/backend-rag/scripts/tests/test_verify_worker_plane_phase2.py docs/architecture/worker-plane-phase2-premerge-evidence.md
  git commit -m "test(worker-plane): prove pre-merge isolation contracts" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 9: Write the deferred staging runbook and complete the pre-merge exit gate

**Files:**

- Create: `docs/runbooks/worker-companion-staging.md`
- Create: `docs/runbooks/worker-companion-production-bootstrap.md`
- Create: `docs/architecture/worker-plane-phase2-exit.md`
- Modify: `.github/workflows/worker-plane-phase2.yml`
- Modify as contract checks require: `.github/workflows/worker-plane-production.yml`

The staging runbook is an execution contract for production-rollout Task 2, not authorization to run commands during Phase 2. It covers production-workflow artifact retrieval, exact-digest staging deploy, all-off boot, role reconciliation/audit, readiness and build heartbeat, local-to-live G13 repetition, workflow-shadow promotion, database reconnect, 30-minute live budget collection, digest rollback, and evidence sanitization. Every mutating operation is staging-only, requires the protected post-merge workflow and explicit confirmation, and includes a stop condition. The production-bootstrap runbook is the separate contract for rollout Task 3: it consumes the unchanged staging-proven digest/gate, creates or reconciles only `nuzantara-worker`, installs only the base worker credential, proves all-off private readiness and heartbeat, and defines prior-digest or first-bootstrap scale-to-zero rollback without touching the primary app. Both state that Phase 2 implementers must not dispatch either live job or inspect/mutate live staging/production, and that raising memory, adding a public service, adding provider secrets, arming a new guard, changing ownership, or admitting a workload requires the later approved rollout step.

- [ ] Add CI steps for Phase 0/1 regression, runtime/import tests, grant audit tests, Fly config checks, integration fixtures, Ruff, migration uniqueness, architecture/table/event checks, verifier, and placeholder detection assembled without embedding forbidden marker words in the checked documents.
- [ ] Write the exit document from real code/test/profile hashes and observed disposable values. Separate repository-declared state, pre-merge verified state, and deferred live staging state. Every live staging gate is explicitly `deferred_to_production_rollout_task_2`; it is neither a Phase 2 failure nor a fabricated pass.
- [ ] Run the complete Phase 2 gate on Pro/CI:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/workers backend/tests/worker_plane backend/tests/integration/worker_plane/test_phase2_staging_contract.py backend/tests/integration/worker_plane/test_phase2_failure_injection.py -q
  pytest scripts/tests/test_check_runtime_inventory.py scripts/tests/test_worker_database_role.py scripts/tests/test_check_worker_fly_config.py scripts/tests/test_deploy_worker_staging.py scripts/tests/test_profile_worker_shadow.py scripts/tests/test_verify_worker_plane_phase2.py -q
  PYTHONPATH=. python scripts/check_runtime_inventory.py --inventory ../../docs/architecture/runtime-inventory.md
  PYTHONPATH=. python scripts/check_worker_fly_config.py --config fly.worker.toml
  PYTHONPATH=../.. .venv/bin/python ../../scripts/worker_plane/check_live_mutation_routes.py --repo-root ../..
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/check_table_ownership.py --migration-dir backend/db/migrations_v2 --schema-file backend/tests/fixtures/schema_tables.txt --database-url "$TEST_DATABASE_URL" --catalog backend/architecture/catalogs/data/table_ownership.json
  test -n "${PHASE0_DATABASE_URL:-}" && test -n "${PHASE0_REDIS_URL:-}" && test -n "${PHASE0_METRICS_URL:-}"
  PYTHONPATH=. python scripts/capture_worker_plane_baseline.py --protocol backend/architecture/baselines/phase0_probe_protocol.json --database-url "$PHASE0_DATABASE_URL" --redis-url "$PHASE0_REDIS_URL" --metrics-url "$PHASE0_METRICS_URL" --require-complete-g9 --output /tmp/worker-plane-phase2-g9-candidate.json
  PYTHONPATH=. python scripts/compare_worker_plane_baseline.py --baseline backend/architecture/baselines/phase0_snapshot.json --candidate /tmp/worker-plane-phase2-g9-candidate.json --exceptions backend/architecture/baselines/phase0_comparison_exceptions.json --output /tmp/worker-plane-phase2-g9-comparison.json
  PYTHONPATH=. python scripts/verify_worker_plane_phase2.py validate --evidence /tmp/worker-plane-phase2-premerge.json --output /tmp/worker-plane-phase2-final.json
  ruff check backend/workers backend/worker_plane/grant_audit.py scripts
  python - <<'PY'
  from pathlib import Path
  roots = [Path('backend/workers'), Path('backend/worker_plane'), Path('../../docs/architecture/worker-plane-phase2-exit.md'), Path('../../docs/runbooks/worker-companion-staging.md'), Path('../../docs/runbooks/worker-companion-production-bootstrap.md')]
  markers = ('TO'+'DO', 'T'+'BD', 'FIX'+'ME', 'NotImplemented'+'Error')
  hits = [(str(p), m) for root in roots for p in ([root] if root.is_file() else root.rglob('*')) if p.is_file() for m in markers if m in p.read_text(errors='ignore')]
  assert not hits, hits
  PY
  git diff --check
  ```

  Expected: all commands exit 0 without contacting Fly; verifier JSON contains every pre-merge gate as `pass` and every live staging gate as `deferred_to_production_rollout_task_2`; marker scan has no hits; diff check is silent.

- [ ] Obtain a fresh SDD operational review of the runbook's post-merge boundary, protected workflow preconditions, stop conditions, Air/Pro routing, no-live-Phase-2 guarantee, and exit evidence; resolve blockers and obtain rereview.
- [ ] Commit:

  ```bash
  git add docs/runbooks/worker-companion-staging.md docs/runbooks/worker-companion-production-bootstrap.md docs/architecture/worker-plane-phase2-exit.md .github/workflows/worker-plane-phase2.yml .github/workflows/worker-plane-production.yml
  git commit -m "docs(worker-plane): record phase two pre-merge exit" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Task 10: Run the independent Phase 2 review panel

**Files:**

- Create: `scripts/review_sets/phase-2.json`
- Create: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/00-review-brief.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/00-review-packet.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/input-manifest.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/freeze-receipt.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/01-fable-5-architecture.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/01-fable-5-architecture.raw.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/01-fable-5-architecture.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/01-fable-5-architecture.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/02-gemini-3.1-pro-high.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/02-gemini-3.1-pro-high.raw.txt`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/02-gemini-3.1-pro-high.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/02-gemini-3.1-pro-high.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/03-glm-5.2-adversarial.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/03-glm-5.2-adversarial.raw.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/03-glm-5.2-adversarial.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/03-glm-5.2-adversarial.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/<attempt-id>/99-disposition.md`
- Modify as findings require: only Phase 2 implementation/test/docs files listed above

The canonical review-input projection includes the Phase 2 diff/evidence, candidate immutable-digest contract, verifier/pre-merge evidence, topology/workflow contracts, base-only role contract, disposable grant/mutation/rollback proof, deferred-live-gate lists, and no-client-data declaration. Base/head/status are external receipt metadata. The packet contains no live Fly inspection. Raw/normalized reviews, packet/receipts, and disposition are excluded attestations. All three reviewers consume the same single in-memory stdin buffer from an empty sandbox cwd with no tools or worktree access.

Every reviewer file starts with exactly this machine-generated YAML front matter (real values replace angle-bracket placeholders), followed immediately by raw model text. `requested_route` records the exact CLI request; the launcher receipt separately records its launcher-generated UUID, exact argv, resolved executable/version, exit status, and stdout hash. Provider session/model fields are recorded verbatim only when emitted and otherwise remain null; they never backfill or masquerade as the requested route. A contradictory emitted declaration fails route audit, while absence does not invalidate otherwise complete launcher proof:

```yaml
---
requested_route: <claude-fable-5|Gemini 3.1 Pro (High)|glm-5.2>
launcher_invocation_uuid: <required launcher-generated UUID>
provider_session_id: <provider value or null>
reported_model: <provider value or null>
input_manifest_sha256: <64 lowercase hex>
packet_sha256: <64 lowercase hex>
launcher_proof_sha256: <64 lowercase hex>
---
```

The raw text uses the exact six headings and repeats only `input_manifest_sha256` in the verdict. The external validator proves packet transport integrity. Requested route is not provider declaration; nullable provider fields are validated only when emitted.

- [ ] Write and test `scripts/review_sets/phase-2.json` as the canonical newline-terminated JSON object `{"covered":[...]}`, with a raw-UTF-8-sorted, duplicate-free path array covering every committed Phase 2 implementation, test, catalog, migration, and non-generated evidence path. Exclude `00-review-brief.md`, which is the sole instructions entry, and all generated packet/review/receipt/disposition attestations. The freezer loads the set only from the recorded source commit and rejects missing, non-canonical, unsorted, duplicate, nonexistent, or instructions-overlapping paths. Commit the set and brief with the Phase 2 implementation/evidence before selecting `H0`.
- [ ] Commit Phase 2 implementation/evidence, require clean tracked status, and freeze from committed Git objects with the master-plan canonical tooling:

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
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/00-review-brief.md \
    --covered-set phase-2 --output-store "$REVIEW_STORE")"
  PACKET_SHA256="$(printf '%s\n' "$FREEZE_JSON" | "$PYTHON" -c 'import json, sys; print(json.load(sys.stdin)["packet_sha256"])')"
  ```

- [ ] Dispatch all three independent seats through the checked canonical single-buffer launcher. It uses the exact absolute binaries/hashed route config from the master plan, Fable/GLM safe-mode plan with `--tools "" --disable-slash-commands --strict-mcp-config --mcp-config '{"mcpServers":{}}'`, Gemini stdin-headless plan+sandbox with no `-p` or prompt argument, an empty cwd, and stdin only. Mutable user/project configuration is never accepted as route proof or as the GLM route source; supported safe client behavior that contradicts the pinned route/receipt contract fails closed. The launcher atomically writes normalized reviews, raw stdout, stderr, and receipts into a new attempt directory:

  ```bash
  ATTEMPT_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  REVIEW_ATTEMPT_DIR="docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/attempts/$ATTEMPT_ID"
  "$PYTHON" scripts/launch_worker_plane_review_panel.py \
    --frozen-review "$REVIEW_STORE/sha256/$PACKET_SHA256" \
    --output-dir "$REVIEW_ATTEMPT_DIR"
  ```

- [ ] Validate three distinct launcher UUIDs, one common manifest/packet hash, executable/config/argv/cwd/tool proofs, exit 0, and raw stdout/stderr hashes. Preserve outputs byte-for-byte; optional provider session/model values remain nullable. The launcher has already generated normalized Markdown; never normalize it manually.
- [ ] Classify every finding in `99-disposition.md` as Blocking, Important, or Advisory, with accepted/rejected decision, repository evidence, owning commit, and rereview state. A rejection requires falsifiable evidence.
- [ ] For each accepted Blocking or Important finding, write RED/GREEN, rerun the verifier, and commit atomically. A covered input byte/role/path change invalidates all seats and requires a regenerated projection/packet plus all-three rerun. Attestation/disposition-only changes require integrity revalidation and `projection(H1) == projection(H0)`, not recursive rerun. No reviewer request authorizes live staging.
- [ ] Repeat fix -> verify -> full three-seat rereview until no unresolved Blocking or Important finding remains and all three verdicts are `GO` or `GO-WITH-CHANGES` without a blocking condition.
- [ ] Complete the disposition, commit the exact fresh-attempt output set as `H1`, compare the covered/instructions projections, then validate final integrity on Pro/CI. The checker is last and accepts only paths committed byte-for-byte at `H1`:

  ```bash
  "${EDITOR:-vi}" "$REVIEW_ATTEMPT_DIR/99-disposition.md"
  git add -- "$REVIEW_ATTEMPT_DIR"
  git commit -m "docs(worker-plane): record phase two independent review" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  H1="$(git rev-parse 'HEAD^{commit}')"
  "$PYTHON" scripts/freeze_worker_plane_review.py compare-projection \
    --repo "$REPO_ROOT" --left "$H0" --right "$H1" \
    --covered-set phase-2 \
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/00-review-brief.md
  "$PYTHON" scripts/check_worker_plane_review.py \
    --repo "$REPO_ROOT" --h0 "$H0" --h1 "$H1" \
    --covered-set phase-2 \
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-2/00-review-brief.md \
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
  PYTHONPATH=. python scripts/verify_worker_plane_phase2.py validate --evidence /tmp/worker-plane-phase2-premerge.json --output /tmp/worker-plane-phase2-reviewed.json
  git diff --check
  ```

  Expected: review validator and verifier exit 0 without Fly access; the disposition has no unresolved Blocking/Important finding; all pre-merge gates pass, all live gates remain explicitly deferred, and diff check is silent.

- [ ] Verify the immutable review record already bound to `H1`; do not add a later evidence commit after validation:

  ```bash
  git show --stat --oneline "$H1"
  test -z "$(git status --porcelain --untracked-files=no)"
  # Then record task status, commit SHA, RED/GREEN evidence, and rereview in .superpowers/sdd/progress.md; never stage .superpowers/.
  ```

## Phase 2 Exit Gate

Phase 2 is complete only when all statements below are supported by checked-in code/CI contracts, disposable or injected test evidence, the 30-minute local Pro/CI profile, and an explicit handoff to production-rollout Task 2. Live staging evidence is neither required nor permitted before the protected compatibility merge:

- [ ] Phase 0 and Phase 1 final verifiers remain green; migration 247 remains the latest migration and no Phase 2 schema file exists.
- [ ] Infrastructure documentation distinguishes repository-declared state, previously evidenced state, live-unknown state, proposed staging target, and approved future production target; Qdrant is recorded from repository truth as external; no fixed app count or new live claim remains.
- [ ] Static config/tests prove the proposed `nuzantara-rag-staging` and `nuzantara-worker-staging` form a private same-image topology; exactly the staging primary owns migrations; the worker has no release command/public service and uses one shared-CPU 1x 1 GB Machine. Fake-subprocess tests prove exact-digest deployment of both, separate credentials, all-off worker boot, ordered staging capability admission/revocation, and full prior-state rollback without contacting Fly.
- [ ] `.github/workflows/fly-deploy.yml` enforces old-image migration -> one fresh-image build whose release command applies/audits -> immutable digest convergence -> post-deploy SQL -> manifest-driven Python migrations with no orphan -> explicit fresh-image schema audit -> blocking health/contracts -> digest export, with one centralized post-promotion rollback/escalation path for every intervening failure. `production-compatibility-digest.json` is impossible on failure. The single deferred `.github/workflows/worker-plane-production.yml` has statically separate manual environment-protected staging and production jobs: staging verifies artifact digest plus commit, deploys both staging apps by exact digest and never rebuilds; production requires the unchanged green post-staging gate, targets only `nuzantara-worker`, starts all workloads `off` with base-only capability, and has tested prior-digest plus first-bootstrap rollback branches. `.github/workflows/worker-plane-phase2.yml` is CI-only and contains no live mutation path.
- [ ] The runtime rejects `DATABASE_URL`, uses only `WORKER_DATABASE_URL`, has exactly cataloged effective privileges including inherited/`PUBLIC` analysis in disposable tests, contains no provider secrets, and refuses direct pre-merge role/app mutation.
- [ ] The local G13 contract passes: top-level `:9091/ready` and a build-SHA disposable database heartbeat gate readiness; killing the event loop while the probe thread lives makes readiness fail within the watchdog/SLO. Equivalent live platform/heartbeat proof is marked `deferred_to_production_rollout_task_2`.
- [ ] G14 passes locally: base import loads no app factory, router, Qdrant, workflow executor, legal, or inference stack; only the selected shadow adapter is lazy-loaded.
- [ ] Disposable integration tests boot all workloads `off` before workflow shadow. The legacy owner remains authoritative and active in the fixture; the worker shadow heartbeat neither claims ownership nor satisfies the legacy build floor.
- [ ] The 30-minute local Pro/CI shadow record proves readiness within 60 seconds, steady RSS at most 750 MiB, peak RSS at most 850 MiB, no more than eight disposable DB connections, complete sampling, and no external effects. It does not claim live 1 GB Fly Machine behavior.
- [ ] A fresh complete Phase 2 G9 candidate captured under `phase0-api-rag-pro-ci-v1` contains numeric API and RAG process-startup seconds, maximum steady-state RSS, aggregate PostgreSQL connection count, and HTTP 5xx rate. Every comparison is at most 1.10 times the canonical Phase 0 value or has an exact approved unexpired exception; baseline/protocol/exception/candidate/comparison hashes are bound into the verifier evidence. Worker G13/G14 evidence is not counted as G9.
- [ ] Pre/post disposable aggregates and source/import/grant/network-deny tests prove the companion implementation cannot claim jobs, mutate domain data, call providers, notify, or execute an external side effect in `off`/`shadow`.
- [ ] The staging runbook hands coordinated exact-digest deployment of private API/RAG legacy owners plus the all-off worker, staging-only migration/G16 checks, distinct role reconciliation, ordered test-secret/grant admission and revocation, readiness/heartbeat, dead-loop injection, live shadow, no-mutation comparison, and two-app rollback proof to production-rollout Task 2 with strict stop conditions. The production-bootstrap runbook hands the post-gate same-digest `nuzantara-worker` creation/deploy, base-role audit, all-off/readiness proof, and prior/new-app rollback to Task 3 without provider capability, guard mutation, ownership movement, primary redeploy, or app destruction.
- [ ] Fable 5, Gemini 3.1 Pro High, and GLM 5.2 independently reviewed one immutable packet; every Blocking and Important finding was fixed, every covered/instructions projection change reran all three seats, and attestation-only changes with equal projection received integrity revalidation only.
