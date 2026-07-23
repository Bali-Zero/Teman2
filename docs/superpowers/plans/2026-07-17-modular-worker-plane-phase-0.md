# Modular Worker Plane Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish executable architectural inventories, reproducible performance baselines, process-local workload-death detection, single-owner scheduler startup, cross-consumer Redis recovery, durable-event quarantine, and fresh-database workflow migration provenance without moving a production workload to the worker process.

**Architecture:** Phase 0 is an evidence and safety-foundation release. It separates bounded-business ownership from runtime-process ownership, adds typed catalogs and deterministic checks around the existing monolith, repairs two missing historical workflow migration sources, and fixes two already-active durability mechanisms in place. It also removes the accidental second `NotificationScheduler` startup from the RAG/full lifespan while preserving the intended API owner. No workload moves to the new worker process, no ownership guard is armed, and all existing public APIs remain behaviorally compatible except that abandoned Redis entries become recoverable and stale durable PostgreSQL events become quarantined instead of silently acknowledged.

**Tech Stack:** Python 3.11+, FastAPI, asyncpg, PostgreSQL v2 SQL migrations, Redis Streams/redis-py, pytest/pytest-asyncio, Ruff, GitHub Actions, JSON and Markdown evidence artifacts.

## Global Constraints

- Work only in an isolated agent worktree created by `scripts/agent_start.py`; never mutate the shared checkout.
- Phase 0 is implemented, reviewed, and committed on the same feature branch as Phases 1-5. Do not merge, deploy, or arm any ownership guard between phases; protected merge and every production action belong only to the final production-rollout plan.
- Read `docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md` before implementation and treat its Phase 0 exit criteria and gates G6, G7, G9, G16, and G17 as binding. Phase 0 implements only the process-local precursor to G11; the full external worker-stop/Fly/DB-heartbeat/oldest-job proof is deferred to Phase 2 staging and the protected rollout.
- Run backend Python only from `apps/backend-rag/.venv` with `PYTHONPATH=.` from `apps/backend-rag`.
- Keep intended workload placement unchanged: workflow and legal ingestion remain in the full/RAG lifespan; notification and WA outbox remain in the API lifespan; Drive remains in its existing process. The duplicate Notification Scheduler call currently reachable from `main_rag.py -> app_factory.py` is an accidental second owner and must be removed, not preserved as placement.
- Do not add Kafka, Celery, a new service image, a new database, or a second event framework.
- Do not inspect or persist client records. Baseline artifacts contain identifiers, counts, hashes, queue depths, and latency aggregates only.
- Do not change the frozen embedding model `text-embedding-3-small` or vector dimensions.
- Never hardcode secrets or prices. Use existing settings, keychain, and `PricingTool` boundaries.
- Use complete type annotations, async I/O, absolute imports, and `logger`; do not add `print()` in production modules.
- Every test is written first and must fail for the stated reason before production code is added.
- Every implementation task ends in one atomic conventional commit. Never use `--no-verify`, `--amend`, force push, or direct push to `main`.
- Historical workflow migrations 039 and 041 must reproduce the committed legacy DDL exactly in their forward blocks; their rollback blocks are non-destructive `SELECT 1;` markers because production may already own data created by the legacy runner.
- Migration `246_clients_wa_intake_autocreate.sql` is owned by intake-v2-entry PR #2669. Phase 0 owns `247_event_quarantine.sql` and Phase 1 starts at `248_worker_plane_ownership.sql` only after this feature branch is rebased onto an `origin/main` that contains that authoritative `246` source and the complete leased `247`–`251` block is still collision-free. If PR #2669 is unmerged, renumbered, or changed at that boundary, Phase 0 stops before creating migration source/test bytes; rerun allocation, acquire a fresh full-block lease, update all covered documents, and rerun the initial panel.
- `BusinessContext` names bounded business/data ownership and never contains `api`, `rag`, `worker`, or `drive`. `RuntimeOwner` names the executing process and never substitutes for table or domain ownership.
- Ruff is run only on Python files added or modified by this feature relative to the recorded merge base; broad baseline-red directories are not used as a Phase 0 quality signal.
- A phase may not exit with `TODO`, `TBD`, `FIXME`, `NotImplementedError`, placeholder review text, expired ownership exceptions, or a skipped required gate.

---

## Task 1: Freeze the current runtime and architecture baseline

**Files:**

- Create: `apps/backend-rag/backend/architecture/__init__.py`
- Create: `apps/backend-rag/backend/architecture/catalogs/__init__.py`
- Create: `apps/backend-rag/backend/architecture/catalogs/models.py`
- Create: `apps/backend-rag/backend/architecture/baselines/__init__.py`
- Create: `apps/backend-rag/backend/architecture/baselines/phase0.py`
- Create: `apps/backend-rag/backend/architecture/baselines/phase0_comparator.py`
- Create: `apps/backend-rag/backend/architecture/baselines/phase0_probe_protocol.json`
- Create: `apps/backend-rag/backend/architecture/baselines/phase0_snapshot.json`
- Create: `apps/backend-rag/backend/architecture/baselines/phase0_comparison_exceptions.json`
- Create: `apps/backend-rag/scripts/capture_worker_plane_baseline.py`
- Create: `apps/backend-rag/scripts/compare_worker_plane_baseline.py`
- Create: `apps/backend-rag/backend/tests/architecture/test_phase0_baseline.py`
- Create: `apps/backend-rag/backend/tests/architecture/test_phase0_comparator.py`
- Create: `apps/backend-rag/backend/tests/architecture/test_catalog_models.py`
- Modify: `apps/backend-rag/backend/app/setup/router_manifest.py`
- Modify: `apps/backend-rag/backend/tests/setup/test_router_manifest.py`

The canonical `route_catalog_hash()` must exist before the first snapshot is captured. It hashes a stable, sorted serialization of the existing `RouterEntry` records and their Phase 0 inventory metadata; no baseline helper may synthesize or hardcode a route hash. `phase0_probe_protocol.json` is the immutable G9 measurement contract: protocol ID `phase0-api-rag-pro-ci-v1`; exact runtime-owner set `api,rag`; a single-host Pro/self-hosted-CI topology; fixed argv-array launch profiles and readiness probes; `300` warm-up seconds; one `60`-second sample window; fixed synthetic HTTP request schedule; maximum steady RSS and PostgreSQL connection count over that window; and `5xx / total` over the same request sample. The capture harness rejects shell command strings, unknown launch profiles, a changed owner set, or a CLI window override.

The snapshot schema is fixed and contains only these top-level keys: `captured_at`, `git_commit`, `protocol_id`, `protocol_sha256`, `topology_id`, `warm_seconds`, `sample_seconds`, `route_catalog_hash`, `route_count_by_process`, `startup_seconds_by_process`, `steady_state_memory_mb_by_process`, `database_connections_by_process`, `http_error_rate_by_process`, `queue_depths`, `oldest_pending_age_seconds`, `declared_workloads`, `declared_business_contexts`, and `declared_runtime_owners`. Queue metrics cover `workflow_jobs`, `legal_ingest_jobs`, `notification_alerts`, `wa_outbox`, PostgreSQL `events_outbox`, and Redis consumer-group pending counts. Startup is measured from allowlisted process spawn to the process-specific ready assertion. A non-canonical offline/schema probe may represent a metric that cannot be read as `{\"status\": \"unavailable\", \"reason\": <non-secret string>}`; the checked canonical `phase0_snapshot.json` may not contain unavailable/missing G9 values and must contain numeric values for all four metric maps for both `api` and `rag`.

`compare_phase_baseline(baseline, candidate, exceptions, now) -> BaselineComparison` is the deterministic G9 comparator reused by every later phase. It first requires identical protocol digest, topology ID, owner set, warm-up, sample window, and HTTP sample count. Startup seconds, steady-state memory, and DB connections must be at most `baseline * 1.10`; a zero baseline for those non-rate metrics permits only zero. HTTP 5xx is evaluated from exact integer `error_count` and `request_count` retained by the capture: the candidate passes when its rate is at most `max(baseline_rate * 1.10, 1 / request_count)` and its error count is at most `max(1, ceil(baseline_error_count * 1.10))`. This admits at most one isolated 5xx when the canonical baseline is zero while still failing two errors or any shortened sample. Missing/unavailable baseline or candidate data fails closed. A time-bounded exception contains exactly `metric`, `process`, `owner`, `reason`, `expires_on`, `approved_by`, and `approval_evidence`; it is valid only with a non-empty owner approval artifact and cannot suppress a different metric/process. The checked exception file starts as `[]`.

- [ ] Write `test_catalog_models.py` first. Assert the exact, disjoint serialized values of `BusinessContext` and `RuntimeOwner`; assert a runtime value cannot parse as a business context and a domain value cannot parse as a runtime owner; and reject the legacy `OwnerContext`, `owner_context`, and `owner-context` vocabulary. Run that test RED before changing `RouterEntry`; expected: `architecture.catalogs.models` does not exist.
- [ ] Create `catalogs/models.py` with only the shared `BusinessContext` and `RuntimeOwner` enums needed by the baseline/router layer, plus strict parse helpers. Then extend `RouterEntry` with inventory-only fields `exposure`, `proxy_match`, `auth_class`, `streaming`, `timeout_class`, and `business_context`, keeping Phase 0-compatible defaults. Its existing process-group data is parsed as `RuntimeOwner`; do not add an `owner_context` field that conflates the two axes. Write a deterministic hash test that changes one field and observes a new hash, and implement `route_catalog_hash()` before importing it from the baseline module.
- [ ] Write `test_phase0_baseline.py` with tests that reject a missing top-level key, raw payload/client fields, negative depths/ages, an unknown business context/runtime owner, a changed protocol/topology/window, and a snapshot whose `git_commit` or route hash does not match the capture inputs. Add `test_checked_phase0_snapshot_is_canonical_and_complete`, which recomputes the protocol digest and rejects unavailable/missing/non-numeric values in any of the four G9 maps for either `api` or `rag`. Add `test_router_manifest.py` coverage that mutates `business_context` and process group independently and observes deterministic hash changes.
- [ ] Add a test proving `capture_snapshot(...)` accepts injected route, startup, memory, PostgreSQL connection, HTTP-stat, queue, and Redis probes so the test never contacts production.
- [ ] Write `test_phase0_comparator.py` first with exact-threshold innocence (`1.10`), `1.100001` guilt, zero-baseline non-rate metrics, zero-5xx baseline with exactly one candidate error accepted and two rejected at the fixed request count, shortened/mismatched HTTP sample rejection, unavailable/missing baseline, unavailable/missing candidate, protocol/topology/window mismatch, expired exception, mismatched metric/process, absent approval evidence, and a valid owner-approved exception. The comparator must emit per-metric ratios, integer HTTP counts, and stable reason codes without payloads.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/architecture/test_catalog_models.py backend/tests/architecture/test_phase0_baseline.py backend/tests/architecture/test_phase0_comparator.py backend/tests/setup/test_router_manifest.py -q
  ```

  Expected: collection first fails because the shared ownership enums do not exist; after the enum-only GREEN checkpoint, collection still fails because the baseline/comparator modules do not exist and the router manifest lacks the split ownership metadata.

- [ ] Pass the enum-separation tests before importing those types into `RouterEntry`. Implement the canonical router hash and pass its focused tests next. Then implement immutable typed records `MetricValue`, `QueueSnapshot`, and `Phase0Snapshot`; implement `validate_snapshot(snapshot) -> list[str]`, `capture_snapshot(...) -> Phase0Snapshot`, and deterministic `write_snapshot(snapshot, path) -> None` with sorted JSON keys. Implement `BaselineException`, `BaselineFinding`, `BaselineComparison`, `compare_phase_baseline(...)`, and the JSON CLI wrapper without shell expansion.
- [ ] Implement `capture_worker_plane_baseline.py` as an async CLI with `--output`, `--protocol`, `--database-url`, `--redis-url`, `--metrics-url`, `--require-complete-g9`, and `--offline`. Live timing/topology values come only from the checked protocol file; no CLI window override is accepted. `--offline` writes explicit unavailable metric records, not zeros, and refuses `--require-complete-g9`. Never log connection strings. Implement `compare_worker_plane_baseline.py --baseline --candidate --exceptions --output` as the only CLI for the G9 ratio decision.
- [ ] Use `--offline` only to write `/tmp/phase0-offline-schema.json` in unit/schema tests. Never check that artifact in and never copy it to `phase0_snapshot.json`.
- [ ] On Pro or the dedicated self-hosted CI topology, capture the checked canonical `phase0_snapshot.json` with `--require-complete-g9`. The command must fail unless both API and RAG complete the exact protocol and all four G9 maps are numeric for both owners. Record the current source commit and real measurements; never substitute remembered production numbers. Every later phase captures its candidate with the same checked protocol and compares it to this canonical file. Missing/unavailable or protocol/topology/window drift remains a closed gate.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. python scripts/capture_worker_plane_baseline.py --offline --protocol backend/architecture/baselines/phase0_probe_protocol.json --output /tmp/phase0-offline-schema.json
  test "${CI:-}" = "true" || test "$(hostname)" = "Nuzantara"
  test -n "${PHASE0_DATABASE_URL:-}" && test -n "${PHASE0_REDIS_URL:-}" && test -n "${PHASE0_METRICS_URL:-}"
  PYTHONPATH=. python scripts/capture_worker_plane_baseline.py --protocol backend/architecture/baselines/phase0_probe_protocol.json --database-url "$PHASE0_DATABASE_URL" --redis-url "$PHASE0_REDIS_URL" --metrics-url "$PHASE0_METRICS_URL" --require-complete-g9 --output backend/architecture/baselines/phase0_snapshot.json
  PYTHONPATH=. pytest backend/tests/architecture/test_catalog_models.py backend/tests/architecture/test_phase0_baseline.py backend/tests/architecture/test_phase0_comparator.py backend/tests/setup/test_router_manifest.py -q
  git diff --check
  ```

  Expected: the temporary offline schema probe preserves explicit unavailable values; the checked canonical snapshot is captured only on the fixed Pro/CI protocol with all four API/RAG maps available; all baseline/manifest/comparator tests pass; `git diff --check` is silent.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/architecture apps/backend-rag/scripts/capture_worker_plane_baseline.py apps/backend-rag/scripts/compare_worker_plane_baseline.py apps/backend-rag/backend/tests/architecture/test_catalog_models.py apps/backend-rag/backend/tests/architecture/test_phase0_baseline.py apps/backend-rag/backend/tests/architecture/test_phase0_comparator.py apps/backend-rag/backend/app/setup/router_manifest.py apps/backend-rag/backend/tests/setup/test_router_manifest.py
  git commit -m "chore(architecture): freeze worker plane phase zero baseline" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 2: Add executable workload, event, side-effect, route, and table inventories

**Files:**

- Modify: `apps/backend-rag/backend/architecture/catalogs/__init__.py`
- Expand: `apps/backend-rag/backend/architecture/catalogs/models.py`
- Create: `apps/backend-rag/backend/architecture/catalogs/workers.py`
- Create: `apps/backend-rag/backend/architecture/catalogs/events.py`
- Create: `apps/backend-rag/backend/architecture/catalogs/effects.py`
- Create: `apps/backend-rag/backend/architecture/catalogs/tables.py`
- Create: `apps/backend-rag/scripts/check_architecture_catalogs.py`
- Create: `apps/backend-rag/scripts/check_table_ownership.py`
- Create: `apps/backend-rag/scripts/tests/test_check_table_ownership.py`
- Modify: `apps/backend-rag/backend/app/setup/router_manifest.py`
- Create: `apps/backend-rag/backend/tests/architecture/test_catalogs.py`
- Modify: `apps/backend-rag/backend/tests/setup/test_router_manifest.py`

The public model contract is:

```python
class BusinessContext(str, Enum):
    PLATFORM = "platform"
    CRM = "crm"
    IMMIGRATION = "immigration"
    COMPANY = "company"
    TAX = "tax"
    PROPERTY = "property"
    CONTENT = "content"
    INTELLIGENCE = "intelligence"
    OPERATIONS = "operations"

class RuntimeOwner(str, Enum):
    API = "api"
    RAG = "rag"
    WORKER = "worker"
    DRIVE = "drive"

class RuntimeProfile(str, Enum):
    CLOUD_WORKER = "cloud-worker"
    DRIVE = "drive"
    LOCAL_PRO_MINI = "local-pro-mini"

class OwnershipMode(str, Enum):
    OFF = "off"
    SHADOW = "shadow"
    DRAINING = "draining"
    ACTIVE = "active"

class SideEffectClass(str, Enum):
    NONE = "none"
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"

class DeliverySemantics(str, Enum):
    PROVIDER_IDEMPOTENT = "provider-idempotent"
    RECONCILABLE = "reconcilable"
    NON_RECONCILABLE = "non-reconcilable"

class PiiClass(str, Enum):
    NONE = "none"
    REDACTED = "redacted"
    RESTRICTED = "restricted"
```

`WorkloadSpec` includes `name`, `business_context`, `runtime_owner`, `candidate_runtime_owners`, `runtime_profile`, `queue_or_schedule`, `concurrency`, `lease_seconds`, `retry_policy`, `kill_switch`, `heartbeat_slo`, `side_effect_class`, `delivery_semantics`, `database_grant_profile`, `provider_secret_symbols`, and `pii_class`. `business_context` answers who owns the policy/data; `runtime_owner` answers which process currently executes it; `candidate_runtime_owners` is the explicit, non-empty, duplicate-free, sorted set of processes eligible across a reviewed cutover; `runtime_profile` answers which placement class is allowed. `provider_secret_symbols` is the sorted, duplicate-free protected provider-runtime injection allowlist. Every name matches `^[A-Z][A-Z0-9_]*$`; it may be empty but never contains assignments, URIs, whitespace, secret material, or resolved values. It can include credentials and opaque operational identifiers installed through the same protected/redacted secret-transport path, but never their values. Phase 2 hashes and reconciles the exact symbol set and rejects any selected adapter dependency absent from it. For this release `notification_scheduler` is pinned to an explicitly injected SendGrid provider and declares exactly `("EFFECT_KEY_HMAC_SECRET_V1", "SENDGRID_API_KEY")`; worker mode cannot call the legacy SMTP/auto-detect factory, and a non-SendGrid source configuration blocks cutover until a separately cataloged profile is reviewed. The HMAC is only privacy-preserving identity, not provider idempotency or delivery proof. `wa_outbox` declares exactly `("WHATSAPP_API_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")`; the webhook-only app secret is excluded. No value enters source, fixtures, snapshots, logs, or review artifacts. These fields are independently validated and cannot be substituted for one another. The current runtime must be in the candidate set. The four named migration pilots may list their verified current owner plus `worker`; every other Phase 0 workload remains a singleton candidate unless a later reviewed phase explicitly expands it. The minimum required durable entries are `workflow_queue`, `legal_full_ingestion`, `notification_scheduler`, `wa_outbox`, `practice_status_listener`, `postgres_event_bus`, and `drive_poll`, plus every additional durable call site found by the census of `app_factory.py`, `main_api.py`, `service_initializer.py`, and `drive_poll_worker.py`. The census must record that `NotificationScheduler` currently has two startup call sites (`main_api.py` and the full lifespan used by `main_rag.py`) and classify that as a blocking duplicate for Task 5. CrossEncoder warm-up, health-only probes, cache listeners, and one-shot startup initialization are classified explicitly as non-durable or best-effort rather than silently omitted. The existing Drive worker stays explicitly owned at runtime by `RuntimeOwner.DRIVE`. No workload or effect may claim generic exactly-once or effectively-once delivery.

`EventPolicy` includes `event_type`, `transport`, `durable`, `consumer_cardinality`, `max_replay_age_seconds`, `stale_action`, and `pii_class`; durable PostgreSQL events use `stale_action="quarantine"`. Best-effort expiry is permitted only when the exact event type is cataloged with `durable=False` and `stale_action="expire"`.

`SideEffectCapability` binds `workload_name`, `effect_name`, `side_effect_class`, `delivery_semantics`, `idempotency_store`, `fence_checkpoint`, and `pii_class`, so different irreversible effects in one workload cannot inherit an ambiguous generic promise. In Phase 0 this is an audited declaration of the required ambiguity strategy, not proof that an effect ledger or `outcome_unknown` state already exists. `provider-idempotent` and `reconcilable` declarations must name the concrete current store/reconciliation lookup; a `non-reconcilable` declaration may record no current ambiguity store, but that absence is an explicit activation blocker that Phase 3 must close before cutover. The exact notification email capability is `workload_name="notification_scheduler"`, `effect_name="email"`, and `delivery_semantics="non-reconcilable"`: neither SMTP nor the current SendGrid adapter exposes a stable reconciliation lookup, so an ambiguous dispatch must become `outcome_unknown` and must never be retried automatically.

`TableOwnership` has one fixed common shape: `table_name`, `business_context`, sorted non-empty `writer_bindings`, sorted non-empty `migration_sources`, and optional dated exception metadata. Every binding has a stable, unique `binding_id`, and the tuple is sorted by that ID. Each binding owns a non-empty `operation_interfaces` map from operation to sorted non-empty interface references; Python references use absolute `module:symbol`, migration-defined callables use `sql:<schema>.<function>`, and no other grammar is accepted. An operation/interface pair belongs to exactly one binding, and one interface reference cannot appear in different bindings for the same table even under renamed operations. A shared mutable table therefore uses a distinct workload-specific mutation wrapper per grant-fenced binding; each wrapper hard-codes workload/operation and performs the live-grant check. A caller-selected workload passed to a generic writer is forbidden, and common helpers behind wrappers are pure/read-only rather than hidden mutation entrypoints. `writer_bindings` is a tuple of this discriminated union:

- `{"binding_id":"...","kind":"static","runtime_owner":"api|rag|worker|drive","operation_interfaces":{"operation":["module:symbol"]}}` has exactly one runtime and forbids candidate/workload/mode fields;
- `{"binding_id":"...","kind":"grant-fenced","workload_name":"...","candidate_runtime_owners":[...],"operation_modes":{"operation":[...]},"operation_interfaces":{"operation":["module:symbol"]}}` has one exact workload and forbids a static owner. `operation_modes` and `operation_interfaces` have the same non-empty sorted key set. Candidate eligibility never authorizes a write: the declared interface must compare workload, runtime owner, generation, operation, and mode with the live `OwnershipGrant` at the mutation boundary and fail closed on absence/drift;
- `{"binding_id":"...","kind":"heartbeat-evidence","workload_candidates":{"workload":[...]},"operation_interfaces":{"heartbeat-upsert":["module:symbol"]}}` maps every exact workload to its checked candidate set, permits only the expected-instance-checked self-heartbeat interface, and can mutate no grant, census, audit, job, claim, schedule, or side effect.

No additional top-level or variant field is accepted. A real table contains only the binding instances needed to cover its write surface; the three variants above describe the union, not three mandatory bindings per table. `legacy_exception`, when non-null, contains exactly `table_name`, `business_context`, `binding_id`, `operation`, `write_interface`, `reason`, `approved_by`, and `expires_on` and cannot expand candidates, modes, operations, or control-plane authority.

Ordinary tables use one singleton `static` binding. In Phase 1, migrated workload state tables give claim/effect transitions to `grant-fenced` bindings while retaining explicitly cataloged static producer operations such as enqueue where required; the bootstrap grant/census/audit tables stay behind static protected CAS/register/retire interfaces to avoid recursive self-authorization, and the heartbeat table uses only `heartbeat-evidence` so a target can prove build compatibility before cutover without receiving work authority. Views and immutable reference tables are represented with a non-mutating interface. The final live table catalog and schema fixture are intentionally generated in Task 8, after Tasks 4 and 7 have added migrations 039, 041, and 247.

- [ ] Write catalog tests for exact enum serialization, required workload entries, unique workload/event/effect keys, valid business contexts and runtime owners, non-empty/sorted/duplicate-free candidate sets containing the current runtime, sorted/unique symbolic-only `provider_secret_symbols`, and guilt cases for a value, assignment, URI, whitespace, duplicate, or undeclared injected symbol. Require exact `notification_scheduler=("EFFECT_KEY_HMAC_SECRET_V1", "SENDGRID_API_KEY")`, exact `wa_outbox=("WHATSAPP_API_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")`, and exact `notification_scheduler/email=non-reconcilable`; prove the HMAC supplies neither provider idempotency nor reconciliation. Add a source dependency-closure test over every selected workload adapter and transitive provider factory: every `os.getenv`/settings dependency installed through the protected provider-runtime path must appear in that workload's exact symbol set, every cataloged symbol must be consumed by the selected adapter, notification worker mode must construct SendGrid explicitly without SMTP/auto-detect, and outbound WA must not require `WHATSAPP_APP_SECRET`. Add a guilt case where `api|rag|worker|drive` is used as a business context, a guilt case where a domain is used as a runtime owner, positive leases/SLOs, and the rule that every irreversible effect declares a fence checkpoint and exactly one canonical delivery semantic. Require a concrete store for `provider-idempotent`/`reconcilable`; permit a missing store only for `non-reconcilable`, while emitting a machine-readable activation blocker. Add a guilt test rejecting `best_effort`, `at_least_once`, `effectively_once`, and underscore variants as delivery-semantics values.
- [ ] Add a source census test that scans `app_factory.py`, `main_api.py`, `service_initializer.py`, and `workers/drive_poll_worker.py` for perpetual loops, durable `create_task`, scheduler, listener, and `.start()` call sites. Maintain a checked classification fixture mapping every hit to a catalog workload or a reasoned `request-scoped|best-effort|startup-only` class; an unclassified hit or a durable hit absent from `WORKLOAD_CATALOG` fails.
- [ ] Add table-engine tests using temporary synthetic schema/catalog fixtures. Innocence covers one ordinary table with a complete singleton static binding, one migrated table with a static `enqueue` binding plus a two-candidate grant-fenced `claim|late-effect` binding matching `WorkloadSpec`, one shared table with two exact workload bindings using distinct workload-specific mutation wrappers, and one heartbeat-evidence table restricted to self-upsert. Guilt rejects duplicate/unassigned tables, a missing/duplicate/unsorted `binding_id`, invalid business context, unequal `operation_modes`/`operation_interfaces` keys, overlapping or uncovered operation/interface pairs, reuse of one generic mutation interface across two bindings even under renamed operations, a generic writer accepting caller-selected workload, mixed tagged-binding fields, a static binding with zero or two runtimes, empty/duplicate/unsorted/wildcard candidates, an unknown workload, candidate drift from the workload catalog, `off|shadow` mutation modes, claim outside `active`, a heartbeat interface that can mutate non-heartbeat state, an unresolved interface, and an exception expired at the injected clock. Do not create the live `schema_tables.txt` or `table_ownership.json` yet.
- [ ] Populate every existing `RouterEntry` with explicit inventory metadata, validate it, and prove `route_catalog_hash()` changes deterministically when `business_context` changes independently of runtime process groups. Do not yet make mounting or proxy decisions depend on the new fields. Regenerate `phase0_snapshot.json` from the now-complete canonical route catalog with the same Pro/CI protocol and `--require-complete-g9`; an offline regeneration is forbidden.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/architecture/test_catalogs.py backend/tests/setup/test_router_manifest.py scripts/tests/test_check_table_ownership.py -q
  ```

  Expected: catalog/checker imports fail and router manifest tests report the missing split metadata/hash behavior.

- [ ] Extend the Task 1 model module with the remaining typed contracts and implement `WORKLOAD_CATALOG`, `EVENT_CATALOG`, `SIDE_EFFECT_CATALOG`, `get_workload_spec(name)`, `get_event_policy(event_type)`, `get_side_effect_capability(workload_name, effect_name)`, `load_table_ownership_catalog()`, and `validate_table_ownership(schema_tables, catalog, workload_catalog, now)`. Implement `StaticWriterBinding`, `GrantFencedWriterBinding`, `HeartbeatEvidenceWriterBinding`, and one `TableOwnership` wrapper containing a strict tuple of those discriminated bindings; retain the already-tested distinct `BusinessContext` and `RuntimeOwner` types.
- [ ] Implement `introspect_schema_tables(conn) -> tuple[str, ...]` without reading rows and `check_table_ownership.py` as the single table-ownership engine with `--schema-file`, `--catalog`, and optional live `--database-url` modes, injected-clock exception validation, and exact schema/catalog parity. Implement `check_architecture_catalogs.py` for workload/event/effect validation and have it call the shared table engine rather than reimplementing G16. Unit tests use only synthetic fixtures here; Task 8 performs the canonical empty-DB bootstrap, migration-through-247, fixture refresh, and live parity proof. Exit 1 on any missing/duplicate/expired assignment, unknown workload, invalid irreversible declaration, activation blocker misreported as ready, or live/fixture/catalog drift.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  test "${CI:-}" = "true" || test "$(hostname)" = "Nuzantara"
  test -n "${PHASE0_DATABASE_URL:-}" && test -n "${PHASE0_REDIS_URL:-}" && test -n "${PHASE0_METRICS_URL:-}"
  PYTHONPATH=. python scripts/capture_worker_plane_baseline.py --protocol backend/architecture/baselines/phase0_probe_protocol.json --database-url "$PHASE0_DATABASE_URL" --redis-url "$PHASE0_REDIS_URL" --metrics-url "$PHASE0_METRICS_URL" --require-complete-g9 --output backend/architecture/baselines/phase0_snapshot.json
  PYTHONPATH=. pytest backend/tests/architecture/test_catalogs.py backend/tests/setup/test_router_manifest.py -q
  PYTHONPATH=. pytest scripts/tests/test_check_table_ownership.py -q
  ```

  Expected: the canonical snapshot is refreshed from real complete G9 probes against the final route hash for this task; all typed catalog, split-ownership, census, manifest, and synthetic table-engine tests pass. This task does not claim G16 against a live fresh database.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/architecture/catalogs apps/backend-rag/backend/architecture/baselines/phase0_snapshot.json apps/backend-rag/backend/app/setup/router_manifest.py apps/backend-rag/scripts/check_architecture_catalogs.py apps/backend-rag/scripts/check_table_ownership.py apps/backend-rag/scripts/tests/test_check_table_ownership.py apps/backend-rag/backend/tests/architecture/test_catalogs.py apps/backend-rag/backend/tests/setup/test_router_manifest.py
  git commit -m "feat(architecture): add executable worker plane catalogs" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 3: Pin the direct-asyncpg baseline and enforce a ratchet

**Files:**

- Create: `apps/backend-rag/backend/architecture/baselines/direct_asyncpg_routers.txt`
- Create: `apps/backend-rag/backend/architecture/baselines/direct_asyncpg_routers.sha256`
- Create: `apps/backend-rag/backend/architecture/baselines/direct_asyncpg_exceptions.json`
- Create: `apps/backend-rag/scripts/check_router_asyncpg_ratchet.py`
- Create: `apps/backend-rag/scripts/tests/test_check_router_asyncpg_ratchet.py`
- Create: `.github/workflows/router-asyncpg-ratchet.yml`

The only measurement rule is the repository command below. At the Phase 0 base it yields exactly 67 sorted paths and SHA-256 `4002789a56196bd8cdce5440c1c596191f4e349ae6a91cb7e9f3d8ca8d24991a`:

```bash
LC_ALL=C rg -l '^\s*(from asyncpg(\.|\s)|import asyncpg(\s|$|,))' \
  apps/backend-rag/backend/app/routers --glob '*.py' | LC_ALL=C sort
```

- [ ] Write tests for exact baseline success, one newly introduced router import failure, removal success, changed baseline hash failure, exception acceptance, malformed exception failure, and expired exception failure. An exception record contains `path`, `owner`, `reason`, and `expires_on`; the initial file is `[]`.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_check_router_asyncpg_ratchet.py -q
  ```

  Expected: import/CLI tests fail because the ratchet script does not exist.

- [ ] Generate the sorted path baseline with the pinned command and write its newline-terminated SHA-256 to the companion file. Assert count 67 and the fixed hash before committing.
- [ ] Implement the ratchet so removals pass without rewriting the baseline, additions fail unless covered by a live exception, baseline file mutation is rejected when its hash companion is stale, and output names every violating path.
- [ ] Add a pull-request workflow that installs only the lightweight test dependencies, runs the ratchet unit tests, then runs the ratchet against the checkout.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_check_router_asyncpg_ratchet.py -q
  PYTHONPATH=. python scripts/check_router_asyncpg_ratchet.py
  test "$(wc -l < backend/architecture/baselines/direct_asyncpg_routers.txt | tr -d ' ')" = 67
  test "$(shasum -a 256 backend/architecture/baselines/direct_asyncpg_routers.txt | awk '{print $1}')" = 4002789a56196bd8cdce5440c1c596191f4e349ae6a91cb7e9f3d8ca8d24991a
  ```

  Expected: tests and ratchet pass; both exact baseline assertions exit 0.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/architecture/baselines/direct_asyncpg_* apps/backend-rag/scripts/check_router_asyncpg_ratchet.py apps/backend-rag/scripts/tests/test_check_router_asyncpg_ratchet.py .github/workflows/router-asyncpg-ratchet.yml
  git commit -m "test(architecture): pin direct asyncpg router ratchet" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 4: Restore workflow migration provenance for fresh databases

**Files:**

- Create: `apps/backend-rag/backend/db/migrations_v2/039_workflow_jobs.sql`
- Create: `apps/backend-rag/backend/db/migrations_v2/041_workflow_jobs_context.sql`
- Create: `apps/backend-rag/backend/tests/db/test_workflow_migration_provenance.py`
- Modify: `apps/backend-rag/backend/tests/db/test_migration_165.py`

The forward blocks must be reconstructed from repository history, not from memory:

```bash
git show fdf2695792:apps/backend-rag/backend/db/migrations_v2/039_workflow_jobs.sql
git show ee7cf05b42:apps/backend-rag/backend/db/migrations_v2/041_workflow_jobs_context.sql
```

Migration 039 creates `workflow_jobs` with UUID `id`, `chain_id`, `thread_id`, `status`, JSONB `payload`, `visible_at`, retry counters, timestamps, `error_msg`, dequeue/thread indexes, and its update trigger/function. Migration 041 adds `client_id`, `practice_id`, `initiated_by`, and `context_label` plus the historical foreign keys/indexes. The exact forward SQL from those commits is authoritative.

- [ ] Write structural tests that require both exact-number files, compare normalized forward blocks to `git show` fixtures committed inside the test, require `-- === ROLLBACK ===`, and reject destructive rollback verbs.
- [ ] Extend migration 165 tests to require its canonical ledger references `(39, '039_workflow_jobs')` and `(41, '041_workflow_jobs_context')` and to prove fresh-database order 039 -> 041 -> 165.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/db/test_workflow_migration_provenance.py backend/tests/db/test_migration_165.py -q
  ```

  Expected: provenance tests fail because 039 and 041 are absent from `migrations_v2`.

- [ ] Restore each historical forward block byte-for-byte apart from the appended rollback delimiter and a non-destructive `SELECT 1;` rollback statement. Do not add Phase 1 claim columns here.
- [ ] Run the repository migration-number and rollback linters, then execute the database tests against the disposable test database if `TEST_DATABASE_URL` is available.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/db/test_workflow_migration_provenance.py backend/tests/db/test_migration_165.py backend/tests/db/test_migration_uniqueness.py -q
  PYTHONPATH=. python ../../scripts/lint_migration_numbers.py
  PYTHONPATH=. python ../../scripts/lint_migration_rollback.py
  ```

  Expected: all provenance/ordering tests and both migration linters pass.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/db/migrations_v2/039_workflow_jobs.sql apps/backend-rag/backend/db/migrations_v2/041_workflow_jobs_context.sql apps/backend-rag/backend/tests/db/test_workflow_migration_provenance.py apps/backend-rag/backend/tests/db/test_migration_165.py
  git commit -m "fix(migrations): restore workflow queue provenance" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 5: Enforce one Notification Scheduler owner and add process-local liveness

**Files:**

- Create: `apps/backend-rag/backend/worker_plane/__init__.py`
- Create: `apps/backend-rag/backend/worker_plane/models.py`
- Create: `apps/backend-rag/backend/worker_plane/liveness.py`
- Modify: `apps/backend-rag/backend/app/main_api.py`
- Modify: `apps/backend-rag/backend/app/setup/app_factory.py`
- Modify: `apps/backend-rag/backend/app/routers/health.py`
- Create: `apps/backend-rag/backend/tests/architecture/test_notification_scheduler_single_owner.py`
- Create: `apps/backend-rag/backend/tests/worker_plane/test_liveness.py`
- Create: `apps/backend-rag/backend/tests/unit/app/routers/test_health_worker_liveness.py`
- Modify: `apps/backend-rag/backend/tests/unit/app/setup/test_app_factory.py`

The deployed process graph currently reaches `init_scheduler(...)` from both `main_api.py` and the full lifespan in `app_factory.py`; `main_rag.py` imports that full lifespan. Phase 0 makes the intended current ownership real: only the API lifespan starts and stops `NotificationScheduler`; the RAG/full lifespan never starts it. The existing `DISABLE_BACKGROUND_WORKERS` kill switch continues to suppress API startup. This is duplicate-owner removal, not a cutover to the future worker process.

Phase 0 liveness is catalog-driven, observation-only, and explicitly a **process-local precursor to G11**, not the completed production gate. `WorkloadObservation` contains `workload_name`, `declared_mode`, `business_context`, `runtime_owner`, `owner_alive`, `heartbeat_age_seconds`, `oldest_pending_age_seconds`, `heartbeat_slo_seconds`, and `queue_slo_seconds`. `evaluate_workload_liveness(observations, now) -> LivenessReport` is unhealthy when a declared active durable workload has no live process-local owner, a stale/missing local heartbeat, or an oldest pending item beyond its catalog SLO. It is degraded, not healthy, when a required probe is unavailable. Disabled/non-durable startup work cannot make the report unhealthy. Full G11 remains deferred until Phase 2 can stop a separate staging worker/Fly process and prove failure through a PostgreSQL heartbeat, oldest-job probe, and alert while API/RAG remain healthy.

- [ ] Write `test_notification_scheduler_single_owner.py` first. Assert the source/runtime census sees exactly one `init_scheduler(...)` call in `main_api.py`, none in the full/RAG lifespan, `main_rag.py` cannot start the scheduler, the API starts exactly one scheduler when enabled, the kill switch starts zero, and API shutdown awaits exactly one `stop()` before closing its DB pool. Extend `test_app_factory.py` to reject reintroduction of scheduler startup in the full lifespan.
- [ ] Write table-driven tests for healthy active ownership, active owner stopped while catalog/config remain, stale heartbeat, oldest-job breach, disabled workload, non-durable startup activity, unavailable probe, and multiple simultaneous failures.
- [ ] Add router tests for `GET /health/workloads`: HTTP 200 for healthy/degraded and HTTP 503 for an unhealthy declared-active workload. Assert the response includes workload names, reason codes, observed ages, business context, and runtime owner but no payload data.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/architecture/test_notification_scheduler_single_owner.py backend/tests/worker_plane/test_liveness.py backend/tests/unit/app/routers/test_health_worker_liveness.py backend/tests/unit/app/setup/test_app_factory.py -q
  ```

  Expected: the single-owner test exposes both current scheduler startup call sites; liveness imports and route lookup also fail because the new module/endpoint do not exist.

- [ ] Remove Notification Scheduler initialization and its scheduler-specific shutdown branch from `app_factory.lifespan`. Add scheduler shutdown to `main_api.lifespan_light` before the DB pool closes. Preserve the API kill switch, initialization error handling, and existing scheduler public API.
- [ ] Implement frozen `WorkloadObservation`, `LivenessFinding`, and `LivenessReport` models plus pure `evaluate_workload_liveness` logic with reason codes `owner_missing`, `heartbeat_stale`, `backlog_stale`, and `probe_unavailable`.
- [ ] Add an injectable async probe builder in `liveness.py` that reads catalog metadata, app task state, and aggregate queue/heartbeat ages. Keep Phase 0 heartbeat sources compatible with current process-local task state; Phase 1 will replace them with PostgreSQL owner heartbeats without changing the endpoint contract.
- [ ] Add `/health/workloads` and wire its status into `/health/detailed`. Do not make the basic load-balancer `/health` depend on unavailable optional probes in Phase 0.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/architecture/test_notification_scheduler_single_owner.py backend/tests/worker_plane/test_liveness.py backend/tests/unit/app/routers/test_health_worker_liveness.py backend/tests/unit/app/setup/test_app_factory.py -q
  PYTHONPATH=. pytest backend/tests/unit/app/routers/test_health*.py -q
  ```

  Expected: API is the sole scheduler owner and stops it cleanly; RAG/full starts none; process-local owner-death scenarios return 503 from the workload endpoint; existing health tests remain green.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/worker_plane apps/backend-rag/backend/app/main_api.py apps/backend-rag/backend/app/setup/app_factory.py apps/backend-rag/backend/app/routers/health.py apps/backend-rag/backend/tests/architecture/test_notification_scheduler_single_owner.py apps/backend-rag/backend/tests/worker_plane apps/backend-rag/backend/tests/unit/app/routers/test_health_worker_liveness.py apps/backend-rag/backend/tests/unit/app/setup/test_app_factory.py
  git commit -m "fix(workers): enforce one notification scheduler owner" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 6: Implement Redis cross-consumer reclaim and fail-closed irreversible dedupe (G6)

**Files:**

- Create: `infra/eventbus/policy.py`
- Modify: `infra/eventbus/subscriber.py`
- Modify: `infra/eventbus/meta_dispatcher.py`
- Modify: `infra/eventbus/research_sentinel.py`
- Modify: `infra/eventbus/intel_dedup_gateway.py`
- Create: `infra/eventbus/tests/__init__.py`
- Create: `infra/eventbus/tests/test_subscriber_reclaim.py`
- Create: `infra/eventbus/tests/test_daemon_reclaimer_wiring.py`
- Create: `infra/eventbus/tests/test_policy_parity.py`
- Modify: `infra/eventbus/README.md`
- Create: `scripts/generate_eventbus_policy.py`
- Create: `scripts/deploy_eventbus_runtime.py`
- Create: `scripts/tests/test_deploy_eventbus_runtime.py`

`infra/eventbus/` is the repository snapshot; `~/scripts/eventbus/` is the authoritative LaunchAgent runtime. Runtime daemons must not import the backend monorepo under an environment the LaunchAgents do not provide. Therefore `infra/eventbus/policy.py` is a generated, standalone transport-policy module containing the three `SideEffectClass` string values plus a canonical-source digest. `scripts/generate_eventbus_policy.py --check` imports the backend catalog only at development/CI time and fails if the standalone file drifts. `subscriber.py` and the daemons import `.policy` only, and a subprocess test imports them with the same minimal `PYTHONPATH=<runtime-parent>` boundary used by LaunchAgents.

Extend `EventSubscriber.__init__` with keyword-only `reclaim_idle_ms: int = 60_000`, `reclaim_batch_size: int = 100`, `is_reclaimer: bool = False`, and `idempotency_ttl_seconds: int = 86_400`. The designated reclaimer uses `XAUTOCLAIM` when supported and falls back to `XPENDING` plus `XCLAIM`; ordinary consumers never race to reclaim. `_reclaim_abandoned() -> Iterator[EventEnvelope]` runs before new-message mode and between blocking reads. `is_seen(event_id, *, side_effect_class) -> IdempotencyResult` must raise `IdempotencyUnavailable` for `IRREVERSIBLE` effects when Redis is unavailable; reversible/no-effect consumers retain explicit at-least-once fail-open behavior. `meta_dispatcher.py` must pass its irreversible classification explicitly before Telegram/launchctl/HTTP/file side effects.

The three real daemon constructors use distinct groups derived from `meta-dispatcher`, `intel-dedup-gateway`, and `research-sentinel`. Each constructor must pass `is_reclaimer=True`; an AST/runtime census proves exactly one designated reclaimer constructor per concrete group and fails on a duplicate or missing designation. The generic subscriber example/CLI is not a deployed fixed group and remains non-reclaimer by default.

- [ ] Write a fake-Redis or disposable-Redis test where consumer A reads an entry without ack, its idle time exceeds the threshold, and consumer B with `is_reclaimer=True` receives that exact entry and can ack it.
- [ ] Add tests for XAUTOCLAIM cursor continuation, fallback XCLAIM, non-reclaimer isolation, max-delivery DLQ, DLQ-write failure leaving the original pending, and irreversible idempotency-store outage raising before the handler runs.
- [ ] Write `test_daemon_reclaimer_wiring.py` first. Parse and import the actual three daemon constructors, assert their stable group names are unique, assert each group has exactly one `is_reclaimer=True`, and assert `meta_dispatcher.py` calls `is_seen(..., side_effect_class=SideEffectClass.IRREVERSIBLE)` before any routed action. A constructor that relies on the default or a second reclaimer for one group is RED.
- [ ] Write policy-parity/import tests first. `generate_eventbus_policy.py --check` must fail against a changed backend enum or generated digest, and a clean subprocess with only the staged runtime parent on `PYTHONPATH` must import `eventbus.subscriber`, `eventbus.meta_dispatcher`, `eventbus.intel_dedup_gateway`, and `eventbus.research_sentinel` without importing `backend`.
- [ ] Write `test_deploy_eventbus_runtime.py` first with a temporary source/destination and fake launchctl/heartbeat probe. Cover dry-run immutability, allowlisted copy plus SHA manifest, backup, restart of all three labels, smoke success, smoke failure restoring the exact backup, and refusal unless `--merged-sha` is an ancestor of `origin/main`. The test must prove no payload/log data is copied into evidence.
- [ ] Run RED:

  ```bash
  source apps/backend-rag/.venv/bin/activate
  PYTHONPATH=apps/backend-rag:. pytest infra/eventbus/tests/test_subscriber_reclaim.py infra/eventbus/tests/test_daemon_reclaimer_wiring.py infra/eventbus/tests/test_policy_parity.py scripts/tests/test_deploy_eventbus_runtime.py -q
  ```

  Expected: constructor/signature tests fail, actual daemon constructors lack designated reclaimers, meta-dispatcher lacks an explicit irreversible policy, the standalone policy/deployer do not exist, and abandoned entries remain owned by consumer A.

- [ ] Implement `IdempotencyUnavailable`, `ReclaimResult`, `_reclaim_with_xautoclaim`, `_reclaim_with_xclaim`, `_reclaim_abandoned`, and the designated-reclaimer loop. Preserve the existing same-consumer PEL drain.
- [ ] Change DLQ parking to acknowledge the source only after `XADD bz:dlq` succeeds. Emit structured error logs with stream/group/id and no payload.
- [ ] Generate the standalone `SideEffectClass`, change `is_seen` to return `IdempotencyResult` or raise on irreversible failure, and update `meta_dispatcher.py` to pass/check the irreversible policy before invoking handlers. Wire `is_reclaimer=True` into all three actual daemon constructors and document the one-reclaimer-per-group invariant.
- [ ] Implement `deploy_eventbus_runtime.py` with `--dry-run` as the default and an explicit `--apply --merged-sha <sha>` path. On Pro only, it verifies the merged commit, backs up `~/scripts/eventbus`, copies the allowlisted snapshot with a hash manifest, restarts `com.balizero.meta-dispatcher`, `com.balizero.intel-dedup-gateway`, and `com.balizero.research-sentinel`, and waits for import/heartbeat/log smoke assertions. Any failure restores the backup and restarts the previous runtime. Phase 0 CI runs only `--dry-run`; the protected post-merge production rollout owns `--apply`.
- [ ] Run GREEN:

  ```bash
  source apps/backend-rag/.venv/bin/activate
  PYTHONPATH=apps/backend-rag:. pytest infra/eventbus/tests/test_subscriber_reclaim.py infra/eventbus/tests/test_daemon_reclaimer_wiring.py infra/eventbus/tests/test_policy_parity.py scripts/tests/test_deploy_eventbus_runtime.py -q
  PYTHONPATH=apps/backend-rag:. pytest infra/eventbus/tests -q
  apps/backend-rag/.venv/bin/python scripts/generate_eventbus_policy.py --check
  apps/backend-rag/.venv/bin/python scripts/deploy_eventbus_runtime.py --dry-run --source infra/eventbus --destination /tmp/eventbus-runtime-dry-run
  ```

  Expected: consumer B reclaims consumer A's pending entry; every deployed concrete group has exactly one reclaimer; meta-dispatcher fails closed on irreversible idempotency loss; standalone imports work under the LaunchAgent boundary; DLQ failures leave the source pending; dry-run performs no runtime mutation.

- [ ] Commit:

  ```bash
  git add infra/eventbus/policy.py infra/eventbus/subscriber.py infra/eventbus/meta_dispatcher.py infra/eventbus/research_sentinel.py infra/eventbus/intel_dedup_gateway.py infra/eventbus/tests infra/eventbus/README.md scripts/generate_eventbus_policy.py scripts/deploy_eventbus_runtime.py scripts/tests/test_deploy_eventbus_runtime.py
  git commit -m "fix(eventbus): reclaim abandoned Redis stream entries" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 7: Quarantine stale durable PostgreSQL events instead of acknowledging them (G17)

**Files:**

- Create: `apps/backend-rag/backend/db/migrations_v2/247_event_quarantine.sql`
- Create: `apps/backend-rag/backend/services/events/quarantine.py`
- Modify: `apps/backend-rag/backend/services/events/__init__.py`
- Modify: `apps/backend-rag/backend/services/events/outbox.py`
- Modify: `apps/backend-rag/backend/services/events/event_bus.py`
- Modify: `apps/backend-rag/backend/services/federation_alerts/daemon.py`
- Modify: `apps/backend-rag/backend/app/routers/health.py`
- Create: `apps/backend-rag/backend/tests/db/test_migration_247_event_quarantine.py`
- Create: `apps/backend-rag/backend/tests/services/events/test_outbox_quarantine.py`
- Create: `docs/architecture/worker-plane-migration-allocation.md`
- Create: `scripts/check_worker_plane_migration_allocation.py`
- Create: `scripts/tests/test_worker_plane_migration_allocation.py`
- Create: `scripts/worker_plane/check_migration_lock_safety.py`
- Create: `scripts/tests/test_check_migration_lock_safety.py`
- Modify: `apps/backend-rag/backend/tests/services/events/test_outbox.py`
- Modify: `apps/backend-rag/backend/tests/services/events/test_outbox_stale_ttl.py`
- Modify: `apps/backend-rag/backend/tests/services/events/test_event_bus_replay.py`
- Modify: `apps/backend-rag/backend/tests/services/federation_alerts/test_daemon.py`

Migration 247 adds nullable `quarantined_at TIMESTAMPTZ`, `quarantine_reason TEXT`, and `quarantined_by TEXT` to `events_outbox`, plus a partial index on unconsumed/unquarantined rows and a partial index on quarantined rows. It does not duplicate payloads or delete/ack rows. Its rollback drops only the new indexes/columns and is allowed only before quarantine data exists; the plan's operational exit keeps it additive through the rollback window.

Before the first migration test or source byte is created, fetch
`origin/main` and create the allocation record. It stores the exact base commit,
the Git blob OID for upstream
`246_clients_wa_intake_autocreate.sql`, the task-owned Redis lease identity,
and the exact phase mapping `247`–`251`. A repository-root
`check_worker_plane_migration_allocation.py` invocation reads the record and a
selected Git base without network access, proves globally unique numeric
prefixes, proves upstream 246 has the recorded basename/blob identity, proves
all five worker-plane target basenames are absent from that base, rejects each
pre-reallocation target basename in every covered authority document, and
fails if another path occupies any leased number. Beginning with the Phase 0
packet, the checker is rerun after every `git fetch origin`, immediately before
creating each later migration, before every immutable packet freeze, and before
protected merge. The earlier initial plan-authority packet instead uses the
smaller Git-object/lease preflight in master-plan Step 4b because this checker
is itself a reviewed Phase 0 artifact. Any mismatch
invalidates the complete block and requires a fresh five-file allocation,
fresh leases, consistent covered-document edits, and a new panel.

- [ ] Write `scripts/tests/test_check_migration_lock_safety.py` RED before migration 247. The fixed checker scans the complete selected migration range and rejects every index/table rewrite that lacks exactly one policy: a dedicated audited `CREATE INDEX CONCURRENTLY` outside the transactional v2 runner, or a `proven-small` record with current production read-only row count/relation bytes, capture timestamp, owner, `lock_timeout_ms <= 1000`, `statement_timeout_ms <= 30000`, scale-clone row count at least the production count, concurrent synthetic-writer maximum stall at most 1000 ms, and zero timed-out statements. Cover missing/stale counts, transactional `CONCURRENTLY`, an unclassified partial index, smaller clone, writer-stall breach, timeout breach, and one valid mixed bundle. The checker reads no client rows or secrets and emits only relation-level counts, sizes, durations, hashes, and stable reason codes.
- [ ] Implement `scripts/worker_plane/check_migration_lock_safety.py` as a typed, deterministic, no-shell CLI. Its pre-merge invocation is `apps/backend-rag/.venv/bin/python scripts/worker_plane/check_migration_lock_safety.py --migration-dir apps/backend-rag/backend/db/migrations_v2 --from 246 --to 251 --evidence docs/architecture/worker-plane-migration-lock-safety.json`. Migration 247's first RED fixture must classify both partial indexes under that policy. Later migrations extend the same evidence atomically and rerun the unchanged guilt suite/checker before their packet freezes; a missing later file is allowed only before its allocated phase begins, but protected merge requires the complete 246–251 range and fresh scale-clone evidence.

- [ ] Write `scripts/tests/test_worker_plane_migration_allocation.py` first. Cover the exact upstream 246 basename/blob OID; exact Phase 0/1/3/4/5 mapping to 247/248/249/250/251; global prefix uniqueness; all five targets absent on the base; rejection of an upstream collision on any leased number; rejection of an unexpected 246 identity; and anti-regression scans for each of the five pre-reallocation target basenames. Exercise every valid `--next-number` state in temporary Git repositories so later phases rerun this same generic checker/test without modifying either. The test uses fake lease metadata and never contacts Redis or the network.
- [ ] Run that test RED; expected failure: the checker and allocation record do not exist. Implement the typed checker with deterministic JSON/error codes and no shell-string execution. Its exact repository-root CLI is `apps/backend-rag/.venv/bin/python scripts/check_worker_plane_migration_allocation.py --base-ref origin/main --feature-ref HEAD --record docs/architecture/worker-plane-migration-allocation.md --next-number 247`. Then run `git fetch origin`, acquire/heartbeat all five target-path leases with task ID `019f734c-8e0c-7562-a448-14e73ac2e43d`, create `docs/architecture/worker-plane-migration-allocation.md` with `origin/main` commit, upstream-246 blob OID, exact mapping, and sanitized lease/collision proof, and run that command GREEN against the fetched base. Stop before any migration source/test if a lease or proof fails.

Because migration 247 changes an existing mutable table, it also carries the
ownership grammar from its first RED test rather than waiting for Phase 1. The
block immediately precedes the first ownership-affecting `ALTER TABLE` and is
line-oriented and exact:

```text
-- table-ownership-begin: public.events_outbox
-- business-context: platform
-- writer-binding: <the complete sorted repeatable writer binding from table_ownership.json>
-- migration-source: backend/db/migrations_v2/247_event_quarantine.sql
-- table-ownership-end
```

There is no delta-only annotation and no legacy singular writer field. Before
the Phase 0 packet freezes, Task 8's source-write census materializes the
complete `events_outbox` policy in `table_ownership.json` and reproduces that
policy byte-for-byte in the migration block. At minimum the policy accounts for
the exact canonical interfaces
`backend.services.events.outbox:publish`,
`backend.services.events.outbox:acknowledge`,
`backend.services.events.outbox:replay_unconsumed_summary`,
`backend.services.events.outbox:prune_consumed`, and
`backend.services.events.quarantine:quarantine_outbox_event`, plus every
current SQL-trigger or legacy direct writer found by the deterministic census.
Each direct writer must be routed through one of those cataloged operations or
named by an exact, dated, non-wildcard legacy exception; an unaccounted writer
blocks Phase 0. Migration 247 may be amended only before its Phase 0 immutable
packet and protected merge; after either boundary a new migration number is
required.

`quarantine_outbox_event(conn, outbox_id, reason, quarantined_by) -> bool` atomically updates only `consumed_at IS NULL AND quarantined_at IS NULL`. `get_quarantine_summary(conn) -> QuarantineSummary` returns count and oldest age without payloads. The existing public `replay_unconsumed(conn, dispatch_fn, *, channel, max_age_minutes) -> int` signature and integer meaning remain stable for all current callers. New `replay_unconsumed_summary(...) -> ReplaySummary` performs the richer selection: it reads unconsumed/unquarantined rows including those older than the replay window, determines policy from `EVENT_CATALOG`, and performs one of three explicit actions: dispatch, quarantine durable stale, or acknowledge explicitly cataloged best-effort expiry. The compatibility wrapper calls the summary function and returns the same successful replay count the old API returned; it never changes existing callers to a dataclass implicitly.

- [ ] Write migration tests for the three columns, both partial indexes, no destructive forward statements, explicit rollback marker, migration number uniqueness, and the exact complete `public.events_outbox` ownership block. Reject a missing/delta-only block, a legacy singular writer annotation, catalog/migration binding drift, or any unaccounted current mutation interface.
- [ ] Write outbox tests proving a stale durable row is quarantined with `consumed_at IS NULL`, excluded from subsequent replay, visible in the summary, and logged/alerted without its payload.
- [ ] Add tests proving an explicitly cataloged best-effort row may be acknowledged as expired, an uncataloged event fails closed and remains unconsumed, fresh durable rows still dispatch/ack, and dispatch errors remain unconsumed/unquarantined.
- [ ] Extend `test_outbox.py` and `test_daemon.py` first to pin the current positional `dispatch_fn`, keyword arguments, and integer return contract of `replay_unconsumed`. Add separate summary tests. Update `test_event_bus_replay.py` to expect the richer summary path, while federation-alert daemon tests prove its stable integer wrapper call still works.
- [ ] Replace the existing stale-TTL assertion that expects `consumer_id=*stale_skip` for all events; only explicit best-effort policy retains that behavior.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/db/test_migration_247_event_quarantine.py backend/tests/services/events/test_outbox.py backend/tests/services/events/test_outbox_quarantine.py backend/tests/services/events/test_outbox_stale_ttl.py backend/tests/services/events/test_event_bus_replay.py backend/tests/services/federation_alerts/test_daemon.py -q
  ```

  Expected: migration/module tests fail; the durable stale-event assertion shows the current silent acknowledgement.

- [ ] Implement migration 247 and `quarantine.py`. Send an `AlertService` critical alert through an injected callback after the transaction commits; alert failure must not undo quarantine and must be reflected in structured logs/metrics.
- [ ] Implement `replay_unconsumed_summary` to include all unconsumed/unquarantined candidates in deterministic ID order, classify row age and payload age through `EventPolicy`, and return `ReplaySummary(dispatched, acknowledged_best_effort, quarantined, failed)`. Keep `replay_unconsumed` as the stable integer wrapper with its existing positional/keyword signature and update the package exports explicitly.
- [ ] Update EventBus reconnect replay to call the summary API, pass exact event policy/channel context, log summary fields, and never use a global stale skip for durable events. Audit and test every current consumer: `backend/tests/services/events/test_outbox.py`, `backend/services/events/event_bus.py`, `backend/services/federation_alerts/daemon.py`, and `backend/tests/services/federation_alerts/test_daemon.py`; no caller may accidentally receive `ReplaySummary` where it expects `int`.
- [ ] Add quarantine count/oldest age to `/health/workloads`; nonzero newly quarantined durable events are degraded and an increasing/old threshold is unhealthy per catalog SLO.
- [ ] Run GREEN:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/db/test_migration_247_event_quarantine.py backend/tests/services/events/test_outbox.py backend/tests/services/events/test_outbox_quarantine.py backend/tests/services/events/test_outbox_stale_ttl.py backend/tests/services/events/test_event_bus_replay.py backend/tests/services/federation_alerts/test_daemon.py -q
  PYTHONPATH=. python ../../scripts/lint_migration_numbers.py
  PYTHONPATH=. python ../../scripts/lint_migration_rollback.py
  ```

  Expected: stale durable rows remain queryable and unacknowledged; best-effort expiry occurs only for an explicit catalog policy; migration gates pass.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/backend/db/migrations_v2/247_event_quarantine.sql apps/backend-rag/backend/services/events/__init__.py apps/backend-rag/backend/services/events/quarantine.py apps/backend-rag/backend/services/events/outbox.py apps/backend-rag/backend/services/events/event_bus.py apps/backend-rag/backend/services/federation_alerts/daemon.py apps/backend-rag/backend/app/routers/health.py apps/backend-rag/backend/tests/db/test_migration_247_event_quarantine.py apps/backend-rag/backend/tests/services/events/test_outbox.py apps/backend-rag/backend/tests/services/events/test_outbox_quarantine.py apps/backend-rag/backend/tests/services/events/test_outbox_stale_ttl.py apps/backend-rag/backend/tests/services/events/test_event_bus_replay.py apps/backend-rag/backend/tests/services/federation_alerts/test_daemon.py docs/architecture/worker-plane-migration-allocation.md docs/architecture/worker-plane-migration-lock-safety.json scripts/check_worker_plane_migration_allocation.py scripts/tests/test_worker_plane_migration_allocation.py scripts/worker_plane/check_migration_lock_safety.py scripts/tests/test_check_migration_lock_safety.py
  git commit -m "fix(events): quarantine stale durable outbox rows" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 8: Wire Phase 0 gates into CI and prove the exit criteria

**Files:**

- Create: `apps/backend-rag/scripts/verify_worker_plane_phase0.py`
- Create: `apps/backend-rag/scripts/tests/test_verify_worker_plane_phase0.py`
- Create: `apps/backend-rag/scripts/capture_schema_tables.py`
- Create: `apps/backend-rag/scripts/tests/test_capture_schema_tables.py`
- Modify: `apps/backend-rag/backend/architecture/baselines/phase0_snapshot.json`
- Create: `apps/backend-rag/backend/architecture/catalogs/data/table_ownership.json`
- Create: `apps/backend-rag/backend/tests/fixtures/schema_tables.txt`
- Create: `.github/workflows/worker-plane-phase0.yml`
- Create: `docs/architecture/worker-plane-phase0-exit.md`
- Verify/modify: `scripts/check_worker_plane_review.py`
- Verify/modify: `scripts/tests/test_check_worker_plane_review.py`
- Verify/modify: `scripts/freeze_worker_plane_review.py`
- Verify/modify: `scripts/launch_worker_plane_review_panel.py`
- Verify/modify: `scripts/review_routes/glm-5.2-v1.json`
- Verify/modify: `scripts/tests/test_worker_plane_review_packet.py`
- Verify/modify: `scripts/tests/test_launch_worker_plane_review_panel.py`

The verifier runs named checks and emits machine-readable JSON with `gate`, `status`, `command`, and `evidence_hash`. Required gates are: catalog completeness, route snapshot stability, G6 reclaim plus daemon wiring/runtime-sync dry-run, G7 67-path/hash ratchet, G9 canonical live baseline plus comparator, process-local liveness precursor (explicitly not full G11), migration provenance, G16 fresh-database ownership completeness, and G17 durable quarantine. G9 recomputes `phase0_probe_protocol.json`'s digest, requires its exact topology/window/owner set in `phase0_snapshot.json`, and rejects any missing, unavailable, or non-numeric API/RAG value in startup, steady RSS, DB connections, or HTTP error rate. The verifier exits nonzero if any required gate is missing, skipped, stale, or red. The evidence must label full G11 `deferred-to-phase2-staging`; it may not alias the process-local test to `G11=pass`.

- [ ] Write verifier tests for all-green, one-red, missing gate, duplicate gate, stale evidence hash, a command that exits zero without producing its expected assertion marker, an offline/unavailable canonical G9 baseline, a protocol-digest mismatch, a topology/window mismatch, and one absent API/RAG metric.
- [ ] Run RED:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  pytest scripts/tests/test_verify_worker_plane_phase0.py -q
  ```

  Expected: tests fail because the verifier does not exist.

- [ ] Implement the verifier as a typed subprocess orchestrator with fixed command allowlist and timeouts; it must not shell-expand user input.
- [ ] Write `test_capture_schema_tables.py` first. Cover `--assert-empty`, sorted qualified non-system tables, newline termination, no row reads, expected latest migration 247, and refusal when the target is not the disposable test database. Implement the capture CLI by importing the same `introspect_schema_tables` engine used by `check_table_ownership.py`.
- [ ] After migrations 039, 041, and 247 exist, create a brand-new disposable PostgreSQL database and prove it is empty. From `apps/backend-rag`, run `PYTHONPATH=.:../crm-cell python scripts/ci_bootstrap_schema.py` before the canonical `PYTHONPATH=. python -m backend.db.migrate apply-all`; the bootstrap is mandatory because SQLModel/legacy tables are not all created by v2 migrations. Assert the migration ledger's latest entry is exactly 247, then refresh `schema_tables.txt` from live `pg_catalog`, populate `table_ownership.json`, run the deterministic source-write census, and rewrite migration 247's `events_outbox` block to the same complete sorted policy before freezing any Phase 0 review input. The shared checker must prove live DB + fixture + catalog + migration-block + source-interface parity and reject every unaccounted trigger/direct writer. Do not reuse a Task 2 fixture or claim parity from migration text.
- [ ] Re-run `scripts/tests/test_worker_plane_review_packet.py` against the committed pre-panel bootstrap before modifying it. Add a RED guilt fixture for every Phase 0-discovered gap before changing implementation. Coverage remains: committed-Git-object reads only; clean tracked status; exact `ensure_ascii=False` canonical JSON and raw-UTF-8 `(role,path)` ordering; duplicate/unknown-role/non-normalized-path rejection; non-circular fields; deterministic length framing; embedded delimiter/newline/NUL bytes; truncated, extra, reordered, wrong-hash, wrong-size, wrong-blob, and trailing-byte rejection; content-addressed read-only placement; a general packet with one or more covered entries plus exactly one instructions entry; the initial implementation-plan preset's exact nine covered paths plus its sole instructions brief; and `projection(H1) == projection(H0)` when H1 adds only excluded attestations. A covered byte/role/path change must change the projection.
- [ ] Implement `scripts/freeze_worker_plane_review.py` exactly to the master-plan canonical contract. It accepts repository, source commit, upstream commit, base commit, one or more repeated `--covered`, exactly one `--instructions`, and an absolute external output store; only the named initial implementation-plan preset enforces its exact nine covered paths. It reads bytes only through Git objects; emits canonical manifest, length-framed packet, and external freeze receipt; round-trips to EOF; validates every blob/hash/length; installs exact files `packet.bin`, `input-manifest.json`, `freeze-receipt.json`, and `glm-5.2-v1.json` by packet SHA-256 under a read-only content-addressed directory; copies and hash-validates the committed canonical route-config bytes into that directory; and provides `compare-projection --repo <repository> --left <commit> --right <commit> --covered ... --instructions <path>` that ignores excluded attestation outputs but fails on any covered input delta.
- [ ] Re-run `scripts/tests/test_launch_worker_plane_review_panel.py` against the committed pre-panel bootstrap, then add RED guilt fixtures before any Phase 0-driven change. Fake stdin-consuming clients must continue to prove one packet-file read and one deterministic review-input buffer feed three times byte-identically, including the attested manifest SHA, exact packet length, trailing newlines, and NUL; verified read-only materialization of `00-review-packet.bin`, `input-manifest.json`, and `freeze-receipt.json` in the output directory; empty `0700` cwd; no prompt bytes in argv; absolute binaries only; exact Fable `--safe-mode --permission-mode plan` and GLM `--safe-mode --permission-mode dontAsk`, both with `--tools "" --disable-slash-commands --strict-mcp-config --mcp-config '{"mcpServers":{}}'`; exact Gemini `--mode plan --sandbox` with **no** `-p`/prompt argument and minimum version 1.1.2; no provider `--session-id`; no `zsh -ic`/shim/shell/worktree access; required unique receipt-only `launcher_invocation_uuid`; nullable `provider_session_id`/`reported_model`; sanitized GLM keychain injection; immutable executable/config/argv/review-input/stdout/stderr hashes; and independent output visibility.
- [ ] Implement the launcher with `subprocess.run(..., input=review_input_bytes, shell=False, cwd=<empty-dir>, capture_output=True)` and the exact absolute routes/config defined in the master plan. Read and hash the content-addressed packet once before any spawn, construct the canonical external attestation header plus exact packet once, pass that same buffer to all seats, preserve stdout/stderr byte-for-byte, and never persist a token or full environment. Before launch, atomically materialize byte-identical, post-copy-hash-verified, read-only `00-review-packet.bin`, `input-manifest.json`, and `freeze-receipt.json` in `--output-dir`; these are validator inputs, never the complete reviewer-input envelope. A missing binary/config hash, changed packet inode/hash, review-input attestation mismatch, failed materialization, nonzero exit, or output write failure fails the panel.
- [ ] Re-run `scripts/tests/test_check_worker_plane_review.py` against the committed pre-panel bootstrap, then add a RED guilt fixture before any validator change. Preserve the valid packet/review/disposition fixture and guilt fixtures for a missing heading, renamed heading, extra level-one heading, wrong order, invalid verdict, placeholder content, absent launcher proof, manifest or packet SHA mismatch, missing/duplicate/extra disposition finding IDs, unresolved Blocking/Important findings, raw-response SHA mismatch, a reviewer that repeats packet rather than manifest SHA, and attestation-only H1 whose projection differs from H0.
- [ ] Implement `scripts/check_worker_plane_review.py` as a deterministic read-only validator requiring `--repo`, `--h0`, `--h1`, the same `--covered`/`--covered-set` plus `--instructions`, `--packet`, `--input-manifest`, `--freeze-receipt`, `--disposition`, and exactly three `--files`. It accepts only regular files inside `--repo` whose mutable bytes equal their Git blobs at `H1`; validates packet round-trip/EOF, canonical `input_manifest_sha256`, external `packet_sha256`, `projection(H1) == projection(H0)`, exact heading order `# Verdict`, `# Blocking findings`, `# Important findings`, `# What survives review`, `# Required amendments`, `# Falsification test`; verdict enum `GO|GO-WITH-CHANGES|NO-GO` plus confidence; non-placeholder body; distinct requested routes; required launcher UUID; nullable provider session/model; exact executable/config/argv hashes; empty-cwd/tool-denial proof; and each raw stdout and stderr companion SHA-256. Every non-`None` Blocking or Important item must have a stable unique `[FINDING-ID]`. The disposition covers exactly those IDs once and leaves no Blocking/Important item unresolved. Run GREEN with the same test command.
- [ ] Add CI steps for the focused architecture, Redis, event, migration, and health suites. Give the canonical G9 capture its own Pro/self-hosted-CI job using the checked protocol, required service URLs, and `--require-complete-g9`; do not let a generic runner replace it with offline output. Upload the snapshot, protocol, and JSON evidence hashes even on failure, but never upload credentials.
- [ ] Write `worker-plane-phase0-exit.md` with commands, actual evidence hashes, known non-blocking environmental unavailability, and an explicit statement that workload placement has not changed. Do not paste test output or claim a gate passed before running it.
- [ ] Record the G6 operational handoff in the exit document without executing it premerge: after the final protected merge, the rollout must run `ssh pro 'cd ~/Desktop/nuzantara && PYTHONPATH=apps/backend-rag:. apps/backend-rag/.venv/bin/python scripts/deploy_eventbus_runtime.py --apply --merged-sha <exact-merged-sha>'`, retain its before/after manifest and smoke evidence, and use the script's automatic backup rollback on failure. Until that handoff passes, report repository G6 green but runtime G6 pending; never imply that editing `infra/eventbus/` changed `~/scripts/eventbus/`.
- [ ] Run the full Phase 0 gate:

  ```bash
  cd apps/backend-rag
  source .venv/bin/activate
  PYTHONPATH=. pytest backend/tests/architecture backend/tests/worker_plane backend/tests/setup backend/tests/db/test_workflow_migration_provenance.py backend/tests/db/test_migration_247_event_quarantine.py backend/tests/services/events backend/tests/services/federation_alerts/test_daemon.py -q
  PYTHONPATH=.:../.. pytest ../../infra/eventbus/tests -q
  pytest scripts/tests/test_check_router_asyncpg_ratchet.py scripts/tests/test_verify_worker_plane_phase0.py scripts/tests/test_capture_schema_tables.py -q
  pytest ../../scripts/tests/test_worker_plane_review_packet.py ../../scripts/tests/test_launch_worker_plane_review_panel.py ../../scripts/tests/test_check_worker_plane_review.py -q
  PYTHONPATH=. python scripts/check_router_asyncpg_ratchet.py
  cd ../..
  apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_check_migration_lock_safety.py -q
  apps/backend-rag/.venv/bin/python scripts/worker_plane/check_migration_lock_safety.py --migration-dir apps/backend-rag/backend/db/migrations_v2 --from 246 --to 247 --evidence docs/architecture/worker-plane-migration-lock-safety.json
  cd apps/backend-rag
  test -n "${TEST_DATABASE_URL:-}"
  PYTHONPATH=. python scripts/capture_schema_tables.py --database-url "$TEST_DATABASE_URL" --assert-empty
  DATABASE_URL="$TEST_DATABASE_URL" PYTHONPATH=.:../crm-cell python scripts/ci_bootstrap_schema.py
  DATABASE_URL="$TEST_DATABASE_URL" PYTHONPATH=. python -m backend.db.migrate apply-all
  PYTHONPATH=. python scripts/capture_schema_tables.py --database-url "$TEST_DATABASE_URL" --expected-latest-migration 247 --output backend/tests/fixtures/schema_tables.txt
  PYTHONPATH=. python scripts/check_architecture_catalogs.py --schema-file backend/tests/fixtures/schema_tables.txt
  PYTHONPATH=. python scripts/check_table_ownership.py --schema-file backend/tests/fixtures/schema_tables.txt --database-url "$TEST_DATABASE_URL" --catalog backend/architecture/catalogs/data/table_ownership.json --expected-latest-migration 247
  test "${CI:-}" = "true" || test "$(hostname)" = "Nuzantara"
  test -n "${PHASE0_DATABASE_URL:-}" && test -n "${PHASE0_REDIS_URL:-}" && test -n "${PHASE0_METRICS_URL:-}"
  PYTHONPATH=. python scripts/capture_worker_plane_baseline.py --protocol backend/architecture/baselines/phase0_probe_protocol.json --database-url "$PHASE0_DATABASE_URL" --redis-url "$PHASE0_REDIS_URL" --metrics-url "$PHASE0_METRICS_URL" --require-complete-g9 --output backend/architecture/baselines/phase0_snapshot.json
  PYTHONPATH=. python scripts/verify_worker_plane_phase0.py --output /tmp/worker-plane-phase0-evidence.json
  cd ../..
  BASE_COMMIT="$(git merge-base origin/main HEAD)"
  git diff --name-only --diff-filter=ACMR "$BASE_COMMIT...HEAD" -- '*.py' -z | xargs -0 apps/backend-rag/.venv/bin/ruff check
  git diff --check
  ```

  Expected: all commands exit 0; the freshly bootstrapped schema has exact migration/catalog parity through 247; Ruff sees only feature-touched Python files; the final checked G9 baseline comes from the fixed live Pro/CI protocol with complete numeric API/RAG measurements and its protocol hash verifies; the verifier JSON contains every Phase 0-required gate with `status="pass"` and labels full G11 as deferred rather than passed.

- [ ] Commit:

  ```bash
  git add apps/backend-rag/scripts/verify_worker_plane_phase0.py apps/backend-rag/scripts/tests/test_verify_worker_plane_phase0.py apps/backend-rag/scripts/capture_schema_tables.py apps/backend-rag/scripts/tests/test_capture_schema_tables.py apps/backend-rag/backend/architecture/baselines/phase0_snapshot.json apps/backend-rag/backend/architecture/catalogs/data/table_ownership.json apps/backend-rag/backend/tests/fixtures/schema_tables.txt scripts/freeze_worker_plane_review.py scripts/launch_worker_plane_review_panel.py scripts/review_routes/glm-5.2-v1.json scripts/check_worker_plane_review.py scripts/tests/test_worker_plane_review_packet.py scripts/tests/test_launch_worker_plane_review_panel.py scripts/tests/test_check_worker_plane_review.py .github/workflows/worker-plane-phase0.yml docs/architecture/worker-plane-phase0-exit.md
  git commit -m "ci(worker-plane): enforce phase zero exit gates" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

## Task 9: Package and pass the independent Phase 0 review panel

**Files:**

- Create: `scripts/review_sets/phase-0.json`
- Create: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/00-review-brief.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/00-review-packet.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/input-manifest.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/freeze-receipt.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/01-fable-5-architecture.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/01-fable-5-architecture.raw.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/01-fable-5-architecture.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/01-fable-5-architecture.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/02-gemini-3.1-pro-high.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/02-gemini-3.1-pro-high.raw.txt`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/02-gemini-3.1-pro-high.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/02-gemini-3.1-pro-high.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/03-glm-5.2-adversarial.md`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/03-glm-5.2-adversarial.raw.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/03-glm-5.2-adversarial.stderr.bin`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/03-glm-5.2-adversarial.invocation.json`
- Create per attempt: `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/<attempt-id>/99-disposition.md`
- Modify as findings require: only Phase 0 implementation/test/docs files listed above

The review directory exactly follows the master plan's `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-N/` convention. Freeze the Phase 0 diff/evidence plus its instruction brief as a canonical review-input projection with `scripts/freeze_worker_plane_review.py`; base/head/status remain external receipt metadata. The packet contains migration ordering, exact G6/G7/G9/process-local-liveness/G16/G17 commands, explicit full-G11 deferral, rollback constraints, and no client data. Raw/normalized reviews, receipts, packet objects, and disposition are excluded attestations. Each reviewer receives the same deterministic launcher-attested header plus the same in-memory packet bytes over stdin, has no tools or worktree access, and cannot see the other outputs before all seats return.

Each route receives a required `launcher_invocation_uuid`; `provider_session_id` and `reported_model` are nullable and never invented. Its immutable `.invocation.json` records the master-plan launcher proof, common `input_manifest_sha256`, external `packet_sha256`, and raw hashes. Requested route is not provider declaration. Each normalized file repeats only `input_manifest_sha256` in its verdict and otherwise preserves the unedited raw body under the exact six-heading contract.

- [ ] Write and test `scripts/review_sets/phase-0.json` as the canonical newline-terminated JSON object `{"covered":[...]}`, whose array is raw-UTF-8 sorted and duplicate-free and contains every committed Phase 0 implementation, test, catalog, migration, and non-generated evidence path that the panel must inspect. Exclude the review brief because it is passed separately as the sole `role=instructions` entry; also exclude packet/raw/normalized review, invocation receipt, disposition, and every other generated attestation path. The freezer must read this set from the recorded source commit, reject missing/non-canonical/unsorted/duplicate/nonexistent entries, and resolve every listed path to a covered Git blob. Commit the set file and review brief with the Phase 0 implementation/evidence before selecting `H0`.

- [ ] Commit the Phase 0 implementation/evidence first, require clean tracked status, then freeze from Git objects with the canonical tooling:

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
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/00-review-brief.md \
    --covered-set phase-0 --output-store "$REVIEW_STORE")"
  PACKET_SHA256="$(printf '%s\n' "$FREEZE_JSON" | "$PYTHON" -c 'import json, sys; print(json.load(sys.stdin)["packet_sha256"])')"
  ```

- [ ] Dispatch all three routes through the checked single-buffer launcher. It uses the exact absolute binaries/argv/config in the master plan, reads the content-addressed packet once, sends identical bytes via stdin, runs from empty sandbox cwd, supplies no tools, and atomically creates normalized reviews, raw stdout, stderr, and receipts in a fresh UUID attempt directory:

  ```bash
  ATTEMPT_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  REVIEW_ATTEMPT_DIR="docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/attempts/$ATTEMPT_ID"
  "$PYTHON" scripts/launch_worker_plane_review_panel.py \
    --frozen-review "$REVIEW_STORE/sha256/$PACKET_SHA256" \
    --output-dir "$REVIEW_ATTEMPT_DIR"
  ```

- [ ] Validate that all three receipts have different launcher UUIDs, the same manifest/packet hashes, exact binary/config/argv hashes, empty-cwd and no-tool proof, exit 0, and correct raw stdout/stderr hashes. Validate optional provider model/session fields only when present. The launcher already generated the normalized Markdown; never extract or normalize bodies manually.
- [ ] Classify every panel finding in `$REVIEW_ATTEMPT_DIR/99-disposition.md` as `Blocking`, `Important`, or `Advisory`, with `accepted/rejected`, evidence, owning commit, and rereview status. A rejection requires concrete repository evidence, not preference.
- [ ] Fix every accepted Blocking and Important finding with new RED/GREEN tests and one atomic conventional commit per finding. Every review-fix commit includes the required `Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>` trailer and does not combine unrelated cleanup.
- [ ] If a review fix changes runtime behavior, route/catalog inputs, probe code, or the protocol file, recapture the canonical baseline on the same Pro/CI protocol with `--require-complete-g9` before rebuilding evidence. An offline artifact can never replace this recapture.
- [ ] After any covered implementation, test, instruction, or non-generated evidence byte/role/path change, regenerate the projection/packet and rerun **Fable, Gemini, and GLM**, even if one reviewer found the issue. Changes only to raw/normalized reviews, invocation receipts, packets, or disposition require hash/integrity revalidation and `projection(H1) == projection(H0)`, not recursive model reruns. Repeat until there is no unresolved Blocking or Important finding and all three verdicts are `GO` or `GO-WITH-CHANGES`.
- [ ] Complete the disposition, commit exactly the canonical artifacts in this attempt as `H1`, revalidate projection equality, then validate review integrity and final gates. The checker runs only after that commit and rejects any supplied path that is not an equal mutable/Git-blob pair at `H1`:

  ```bash
  "${EDITOR:-vi}" "$REVIEW_ATTEMPT_DIR/99-disposition.md"
  git add -- "$REVIEW_ATTEMPT_DIR"
  git commit -m "docs(worker-plane): record phase zero independent review" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
  H1="$(git rev-parse 'HEAD^{commit}')"
  "$PYTHON" scripts/freeze_worker_plane_review.py compare-projection \
    --repo "$REPO_ROOT" --left "$H0" --right "$H1" \
    --covered-set phase-0 \
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/00-review-brief.md
  "$PYTHON" scripts/check_worker_plane_review.py \
    --repo "$REPO_ROOT" --h0 "$H0" --h1 "$H1" \
    --covered-set phase-0 \
    --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-0/00-review-brief.md \
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
  PYTHONPATH=. python scripts/verify_worker_plane_phase0.py --output /tmp/worker-plane-phase0-final.json
  git diff --check
  ```

  Expected: the exact worker-plane review-contract validation exits 0; final Phase 0 verifier is all-pass; invocation metadata is reproducible and hash-bound; no unresolved Blocking or Important row remains in `99-disposition.md`.

- [ ] Verify the immutable review record after rereview passes; do not create a later evidence commit because the checker already bound the exact attempt artifacts to `H1`:

  ```bash
  git show --stat --oneline "$H1"
  test -z "$(git status --porcelain --untracked-files=no)"
  ```

## Phase 0 Exit Gate

Phase 0 is complete only when all statements below are proven by the checked-in verifier and review disposition:

- [ ] Every durable lifespan loop and scheduler has one named `BusinessContext`, one distinct current `RuntimeOwner`, runtime profile, kill switch, delivery policy, heartbeat SLO, and side-effect classification; no API/RAG/worker/drive value is accepted as a business context.
- [ ] Every workload has source-closed, sorted, unique symbolic-only `provider_secret_symbols`; notification declares exactly HMAC plus SendGrid, WA declares exactly outbound token plus phone-number ID, no selected adapter dependency is absent, no catalog contains a resolved value, and Phase 2 can derive an exact least-privilege provider-runtime injection allowlist.
- [ ] Notification Scheduler starts exactly once in the intended API lifespan, stops before the API DB pool closes, and cannot start from the RAG/full lifespan; the API kill switch still suppresses it.
- [ ] Every mutable table has exactly one checked business/data owner and one complete, non-overlapping set of tagged `writer_bindings`. Ordinary static authority is a singleton; migrated static producer operations are distinct from grant-fenced consumer transitions; grant-fenced and heartbeat-evidence candidates are finite and catalog-bound; no mixed binding, uncovered/bypassing write path, expired exception, or unassigned migration is accepted.
- [ ] The canonical sorted route-catalog hash implementation existed before the first Phase 0 route snapshot was captured, and the checked-in snapshot records that hash.
- [ ] G16 was proven on a brand-new disposable PostgreSQL database by first running `scripts/ci_bootstrap_schema.py`, then the canonical v2 runner through newly present 039, 041, and 247, refreshing the fixture only after that sequence, and comparing live `pg_catalog`, the checked fixture, and the single ownership catalog through one shared checker.
- [ ] The checked-in direct-router asyncpg baseline contains exactly 67 paths with the pinned hash; the current measured set contains no path outside that baseline, while legitimate removals may make the current set smaller without weakening the ratchet.
- [ ] The checked G9 baseline was captured on Pro/self-hosted CI with protocol `phase0-api-rag-pro-ci-v1`, exact protocol digest/topology/owner set, five-minute warm-up, one fixed sample window, and numeric API/RAG values for process startup, steady-state RSS, aggregate DB connections, and HTTP 5xx rate; no offline/unavailable value is present. The deterministic comparator rejects protocol drift, any later value above `1.10x`, missing evidence, and invalid/expired owner exceptions.
- [ ] The process-local liveness precursor proves a stopped local owner cannot remain green while files/config/catalog remain. Full G11 is explicitly not claimed in Phase 0 and remains gated on Phase 2's separate staging-worker stop, PostgreSQL heartbeat, oldest-job, and alert proof.
- [ ] Redis consumer B reclaims consumer A's abandoned pending entry after the idle threshold, each real daemon group has exactly one designated reclaimer, poison pills reach DLQ only after a successful DLQ write, and meta-dispatcher's irreversible handlers fail closed when idempotency storage is unavailable.
- [ ] Repository G6 changes have a hash-checked post-merge sync/restart/smoke/rollback handoff for authoritative `~/scripts/eventbus/`; until that protected command passes on Pro, runtime G6 is reported pending rather than green.
- [ ] Stale durable PostgreSQL events are queryable in quarantine, unacknowledged, excluded from normal replay, and alerted; only explicitly cataloged best-effort events may expire.
- [ ] `replay_unconsumed(...) -> int` retains its exact existing caller contract, while `replay_unconsumed_summary(...) -> ReplaySummary` is the explicit richer API and every current caller/test has been audited.
- [ ] Fresh database migration order includes exact historical workflow migrations 039 and 041, while production rollback remains non-destructive.
- [ ] No workload has moved process, no Phase 1 ownership guard has been armed, migration 248 remains unapplied/unwritten, and Phase 0 has not been merged or deployed independently.
- [ ] Fable 5, Gemini 3.1 Pro High, and GLM 5.2 have independently reviewed the same immutable packet with launcher UUID/version/command/output-hash proof; every covered/instructions projection change regenerated the packet and reran all three, while attestation-only changes with equal projection received integrity revalidation only; every Blocking and Important finding is fixed and rereviewed.
