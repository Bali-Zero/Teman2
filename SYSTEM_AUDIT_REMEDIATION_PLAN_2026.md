# SYSTEM_AUDIT_REMEDIATION_PLAN_2026

Date: 2026-03-13
Based on: `SYSTEM_AUDIT_REPORT_2026.md`
Scope: backend, frontend, Qdrant, Knowledge Graph, infra config, validation tooling
Mode: remediation plan only, no runtime modifications executed in this phase

## 1. Objective

Convert the audit findings into an execution-ready remediation plan that:

1. removes the highest-risk contract drift,
2. restores trust in retrieval and observability,
3. hardens secret posture,
4. reduces graph/data hygiene debt,
5. prepares Nuzantara for 2026 scale without uncontrolled regressions.

## 2. Operating Rules

- No destructive data operation without a dry run, backup strategy, and written rollback.
- No collection rename in production without a compatibility window.
- No graph cleanup job runs directly on production first.
- Every remediation stream must end with automated verification.
- Secret-related work must never log, print, commit, or paste real values.

## 3. Delivery Strategy

Execution is split into `3` waves:

- `Wave 0`: containment and truth alignment
- `Wave 1`: contract and data hygiene repair
- `Wave 2`: performance, frontend hardening, and monitoring normalization

Recommended branch strategy:

- `audit/p0-collections-and-secrets`
- `audit/p1-kg-hygiene-and-backend-runtime`
- `audit/p2-frontend-and-observability`

## 4. Priority Matrix

### P0

- Canonicalize Qdrant collection map and payload contracts
- Remove tracked hardcoded keys and rotate affected secrets
- Fix duplicate FastAPI router registration
- Restore evaluation suite consistency on core RAG evaluation components

### P1

- KG hygiene cleanup pipeline
- Centralize Qdrant and HTTP client lifecycle
- Normalize health/readiness semantics
- Resolve graph-engine dead branches

### P2

- Tighten frontend type-safety escape hatches
- Enforce CSP after cleanup
- Reduce visual-system inconsistency

## 5. Wave 0: Containment And Truth Alignment

### Stream A. Freeze The Current Truth

Purpose:

- stop further drift while remediation is in progress.

Tasks:

1. Create a canonical inventory of live Qdrant collections and intended aliases.
2. Create a canonical inventory of KG source collections currently present in Postgres.
3. Capture current backend health, detailed health, Qdrant metrics, and route count as baseline artifacts.
4. Snapshot the list of tracked files containing secret-like strings.

Deliverables:

- `docs/audit/qdrant-collection-inventory-2026-03-13.md`
- `docs/audit/kg-lineage-inventory-2026-03-13.md`
- `docs/audit/runtime-baseline-2026-03-13.md`
- `docs/audit/secret-surface-2026-03-13.md`

Acceptance criteria:

- a single reviewed document lists every live collection and whether it is `canonical`, `legacy`, or `unknown`.
- every backend collection reference is classified as `valid`, `alias`, or `stale`.

Validation:

- re-run read-only Qdrant collection listing
- re-run KG lineage query by `source_collection`
- re-run route enumeration

Rollback:

- not applicable, documentation only

### Stream B. Stop Secret Bleed

Purpose:

- eliminate the repository-level secret hygiene issue immediately.

Tasks:

1. Remove hardcoded keys from tracked code and legacy docs.
2. Replace fallback keys with strict env access and explicit error handling.
3. Create a secret rotation checklist for every exposed provider.
4. Delete local secret backup artifacts from the workstation after safe confirmation of current source-of-truth secret locations.
5. Extend `.gitignore` if needed to block future accidental `.env.backup*` files.

Primary files to inspect/change:

- `app_dashboard.py`
- `apps/backend-rag/scripts/test_gemini_key_*.py`
- `apps/backend-rag/scripts/list_gemini_models.py`
- `docs/archive/transient/intel_scraper/*`
- repo root `.gitignore`

Acceptance criteria:

- no tracked file contains literal provider keys detectable by regex scan
- no production code path contains a default API key fallback
- local secret backup files are removed or archived outside repo workspace

Validation:

```bash
rg -n --hidden -g '!**/.git/**' -g '!**/node_modules/**' -g '!**/.venv/**' \
  -e 'AIza[0-9A-Za-z\-_]{35}' \
  -e 'sk-[A-Za-z0-9]{20,}' \
  -e 'ghp_[A-Za-z0-9]{36,}' \
  -e 'AKIA[0-9A-Z]{16}' .
```

Rollback:

- for docs/scripts only, revert specific file changes if a false positive removal breaks a non-secret test fixture
- do not restore real secrets into git history

## 6. Wave 1: Contract And Data Hygiene Repair

### Stream C. Qdrant Collection Contract Unification

Purpose:

- remove the highest-risk retrieval fragmentation.

Target outcome:

- one canonical collection map used across backend, graph, MCP, and operational docs.

Tasks:

1. Build a source-of-truth collection registry module.
2. Replace string literals like `kbli_2025_final`, `legal_unified`, `tax_genius` where stale.
3. Decide the canonical forms for:
   - KBLI
   - legal
   - tax
   - pricing
   - visa
4. Add compatibility aliases for one transition period instead of mass-breaking renames.
5. Update health and query routing surfaces to report canonical names only.

Likely implementation points:

- `apps/backend-rag/backend/app/modules/knowledge/service.py`
- `apps/backend-rag/backend/services/routing/query_router.py`
- `apps/backend-rag/backend/app/routers/kbli_notebook.py`
- `apps/backend-rag/backend/generals/onboarding_context.py`
- prompt references in `apps/backend-rag/backend/prompts/zantara_core.py`

Design decision required:

- whether canonical names become the live `*_hybrid` names, or whether a translation layer maps canonical logical names to live physical collection names.

Recommended choice:

- use logical names in application code, physical names in one registry.

Acceptance criteria:

- no application code hardcodes stale physical names outside the registry
- KBLI, legal, tax, and pricing retrieval resolve through the same registry
- backend health returns the same collection naming language used by the codebase

Validation:

```bash
rg -n 'kbli_2025_final|legal_unified|tax_genius|bali_zero_pricing' apps/backend-rag/backend
```

Expected result after remediation:

- only the registry module may contain physical names

Rollback:

- keep registry aliases for legacy names for one deploy cycle
- feature-flag collection map if needed

### Stream D. KBLI Payload Contract Repair

Purpose:

- align KBLI source, vector payload, and consumer expectations.

Current problem:

- source JSON is flat,
- vector payload uses nested `metadata`,
- KBLI Notebook expects top-level keys in some flows,
- project rule says KBLI payloads should remain flat.

Decision gate:

- choose one of two models:
  1. enforce truly flat Qdrant payloads,
  2. formalize nested `metadata` as the platform standard.

Recommended choice:

- flat payload for KBLI documents, because the project rule is explicit and the KBLI domain is critical.

Tasks:

1. Define the exact KBLI Qdrant payload schema.
2. Update reindexer and gold-content indexer to emit that schema only.
3. Update KBLI Notebook filters/search parsing to match the canonical schema.
4. Add schema assertions in ingestion and tests.
5. Backfill or reindex the affected collection.

Primary files:

- `apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py`
- `apps/backend-rag/backend/scripts/index_kbli_gold_content.py`
- `apps/backend-rag/backend/app/routers/kbli_notebook.py`
- tests for KBLI notebook, KG enrichment, and search flows

Acceptance criteria:

- exact-match filter by KBLI code works against the live collection
- semantic search returns payloads consumable without special nested metadata handling
- test coverage exists for both direct lookup and semantic search

Validation:

1. dry-run payload build from source JSON
2. unit tests on schema serializer
3. integration test against a local/dev Qdrant collection
4. manual check for known code, e.g. `07101`

Rollback:

- keep old collection live until the new collection is validated
- switch collection mapping only after verification

### Stream E. FastAPI Route Registry Cleanup

Purpose:

- remove route duplication and restore registry trust.

Tasks:

1. Remove duplicate `analytics.router` inclusion.
2. Add a route uniqueness test on `(path, method)`.
3. Add a startup assertion in non-production environments if duplicate path-method pairs exist.

Primary file:

- `apps/backend-rag/backend/app/setup/router_registration.py`

Acceptance criteria:

- duplicate path-method pair count is `0`
- route count stabilizes and does not include repeated analytics endpoints

Validation:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python -m backend.app.main_cloud
```

and route-enumeration test/assertion

Rollback:

- revert the single router registration change if a hidden side effect appears

### Stream F. RAG Evaluation Stack Repair

Purpose:

- restore the audit/benchmark suite as a trusted quality gate.

Current failing areas:

- `benchmark.py`
- `dataset_builder.py`
- `ragas_evaluator.py`

Subtasks:

#### F1. `benchmark.py`

Fixes:

1. Align reranker patch target with the current implementation.
2. Normalize `search_type` contract:
   - either tests accept `hybrid_rrf`,
   - or the code maps it to a stable public label.
3. Ensure `evaluate_sample()` propagates the actual sample query.
4. Fix async DB write contract so tests use awaitable mocks consistently.

Acceptance criteria:

- all `test_benchmark.py` tests green

#### F2. `dataset_builder.py`

Fixes:

1. Ensure all placeholders are resolvable or fail explicitly.
2. Replace floor-only allocation with remainder-aware sample distribution.
3. Enforce invalid-ratio assertion behavior consistently.
4. Guarantee dataset size equals requested target size.

Acceptance criteria:

- all `test_dataset_builder.py` tests green
- no unresolved `{placeholder}` remains in generated questions

#### F3. `ragas_evaluator.py`

Fixes:

1. Fix awaitable contract around mocked LLM responses.
2. Ensure evaluator methods accept AsyncMock-driven tests cleanly.
3. Remove `MagicMock`/await mismatch in integration paths.

Acceptance criteria:

- all `test_ragas_evaluator.py` tests green

Wave-level validation:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/rag/evaluation/ -q
PYTHONPATH=. pytest backend/tests/services/rag/ -q
```

Rollback:

- revert each submodule independently
- keep benchmark label compatibility if external dashboards depend on current naming

## 7. Wave 1B: Knowledge Graph Hygiene

### Stream G. KG Cleanup Pipeline

Purpose:

- reduce semantic noise without breaking referential integrity.

Observed live debt:

- `1,953` self-loops
- `2,106` duplicate edge groups
- `2,148` excess duplicate edges
- `111` suspicious placeholder-like nodes
- `1,528` suspicious placeholder-like edges

Tasks:

1. Define allowed self-loop relationship types.
2. Define duplicate collapse policy for `(source_entity_id, target_entity_id, relationship_type)`.
3. Define suspicious entity patterns to quarantine:
   - `unknown`
   - `none`
   - `...`
   - malformed KBLI placeholders
4. Build a dry-run cleanup script that outputs:
   - affected node count
   - affected edge count
   - exact IDs
5. Run cleanup first on staging/dev snapshot.
6. Add continuous hygiene metrics to observability.

Likely code areas:

- `apps/backend-rag/backend/services/knowledge_graph/`
- `apps/backend-rag/backend/scripts/`
- SQL utilities/migration scripts

Acceptance criteria:

- no orphan edges introduced
- duplicate edge groups reduced materially
- placeholder node count reduced materially
- self-loops only remain where explicitly allowed

Validation SQL:

- orphan edge checks
- duplicate triple counts
- suspicious pattern counts
- before/after node and edge totals

Rollback:

- full SQL backup or table snapshot before cleanup
- cleanup script must support restore or reverse insert/delete manifest

### Stream H. KG Lineage Normalization

Purpose:

- eliminate collection/source naming fragmentation in KG provenance.

Tasks:

1. Define canonical `source_collection` values.
2. Map legacy variants:
   - `legal_unified_hybrid_hybrid`
   - `legal_unified_hybrid`
   - `kbli_2025_import`
   - `kbli_unified`
3. Decide whether to preserve raw lineage in a secondary provenance field.
4. Backfill normalized lineage values.

Acceptance criteria:

- lineage dashboards group by canonical values only
- raw source lineage remains inspectable if needed

Rollback:

- preserve original lineage in backup column or migration snapshot

## 8. Wave 2: Runtime Efficiency And Architecture Hardening

### Stream I. HTTP Client Lifecycle Consolidation

Purpose:

- reduce connection churn and external API latency.

Current hotspots:

- `GoogleDriveService` opens `13` fresh `httpx.AsyncClient()` instances across methods

Tasks:

1. Introduce shared async client lifecycle per integration service.
2. Centralize timeout and retry policies.
3. Add explicit close hooks on shutdown.
4. Audit other services for repeated per-request client construction.

Targets:

- `google_drive_service.py`
- `team_drive_service.py`
- `zoho_oauth_service.py`
- high-traffic dashboard/observability fetchers

Acceptance criteria:

- repeated external API methods do not instantiate a fresh client per call
- shutdown cleanly closes clients

Validation:

- unit tests on client reuse
- basic latency comparison before/after

Rollback:

- keep old method-local client path behind a temporary fallback if needed

### Stream J. Qdrant Client Centralization

Purpose:

- reduce wrapper sprawl and inconsistent client behavior.

Tasks:

1. inventory all direct `QdrantClient(...)` instantiations
2. split them into categories:
   - request-scoped dependency
   - service-owned singleton
   - one-off script utility
3. centralize backend request-path usage behind dependency/factory modules
4. keep scripts separate but standardized

Acceptance criteria:

- application request path no longer instantiates ad hoc clients in routers
- stats/health/search usage goes through common abstraction

Validation:

```bash
rg -n 'QdrantClient\(' apps/backend-rag/backend/app apps/backend-rag/backend/services
```

Expected result after remediation:

- only approved factory/dependency locations remain

Rollback:

- revert file-by-file if dependency injection introduces startup regressions

### Stream K. Concurrency And Capacity Recalibration

Purpose:

- align runtime concurrency with the actual single-worker memory model.

Tasks:

1. profile current request classes by memory and latency.
2. verify whether current `200/250` Fly request concurrency is realistic for `1` uvicorn worker on `4gb`.
3. if not, reduce concurrency limits or move expensive workloads off request path.
4. increase cache hit rate before increasing throughput expectations.

Acceptance criteria:

- no contradiction between worker count, memory budget, and concurrency settings
- documented capacity envelope exists for the current VM class

Validation:

- controlled load test
- p95 latency and memory profile
- queueing behavior under concurrent search

Rollback:

- Fly config rollback to previous concurrency limits

## 9. Wave 2B: Graph Engine Repair

### Stream L. Dead Branch Removal Or Wiring

Purpose:

- make graph architecture match actual executable behavior.

Tasks:

1. decide whether `pricing`, `followup`, and `tools` are first-class routes now.
2. if yes:
   - wire them in `route_after_understand`
   - connect `GRADE_PRICING` with real graph edges
   - add tests
3. if no:
   - remove dead nodes and route enums
   - simplify tests and documentation

Targets:

- `apps/graph-engine/src/nuzantara_graph/graph/constants.py`
- `apps/graph-engine/src/nuzantara_graph/graph/router.py`
- `apps/graph-engine/src/nuzantara_graph/graph/builder.py`
- `packages/shared-schemas/src/nuzantara_schemas/state.py`

Acceptance criteria:

- every declared node is reachable or intentionally terminal
- every route enum returned by router logic is exercised by tests
- no dead graph branch remains

Validation:

```bash
cd apps/graph-engine
pytest tests/ -q
```

Rollback:

- revert graph branch work as a single atomic change if transition logic becomes unstable

## 10. Wave 2C: Frontend Hardening

### Stream M. Type-Safety Reduction Plan

Purpose:

- reduce the gap between passing typecheck and actual type discipline.

Current counts in production code:

- `95` `any`
- `7` `console.log`
- `4` `@ts-ignore` / `@ts-expect-error`

Priority order:

1. workspace/admin process flows
2. `PrimeMap3D`
3. analytics and workflow helpers
4. error boundaries and Sentry shims

Tasks:

1. replace `Record<string, any>` with shared safer types where possible
2. remove production `console.log` calls
3. replace `useState<any>` and `window as any` in critical UI surfaces
4. tighten `tsconfig` after counts fall:
   - evaluate disabling `allowJs`
   - evaluate disabling `skipLibCheck`

Acceptance criteria:

- production `console.log` count reduced to `0`
- critical-surface `any` count materially reduced
- typecheck still green

Validation:

```bash
cd apps/mouth
npm run typecheck
rg -n '\bany\b|console\.log\(|@ts-ignore|@ts-expect-error' src -g '*.{ts,tsx}' -g '!**/*.test.*' -g '!**/__tests__/**'
```

Rollback:

- file-level revert if a typing change creates runtime regressions

### Stream N. Frontend Security And Visual Consistency

Purpose:

- finish the frontend hardening started by the current Next config.

Tasks:

1. move CSP from `Report-Only` to enforced after violations are resolved.
2. choose one canonical font stack:
   - Geist via `next/font`
   - or Inter via CSS
3. remove forced dark-mode root if product design should support broader theming.
4. align design tokens and document the canonical typography/color system.

Acceptance criteria:

- no conflicting global font path
- enforced CSP in production
- visual system documented in one place

Validation:

- `next build`
- browser smoke test on key pages
- CSP violation log review before enforcement

Rollback:

- keep report-only CSP feature flag for one deploy cycle

## 11. Monitoring And Readiness Normalization

### Stream O. Health Signal Reconciliation

Purpose:

- make health/readiness outputs trustworthy and non-contradictory.

Tasks:

1. define strict semantics for `healthy`, `degraded`, `unavailable`, `initializing`.
2. align:
   - `check_health`
   - `check_health_detailed`
   - advanced readiness
   - registry-level health
3. ensure all readiness checks run inside the same dependency/runtime model.
4. surface component degradations without labeling the overall system healthy unless thresholds are met.

Acceptance criteria:

- adjacent health tools do not give contradictory top-level states for the same deployment state
- deployment readiness uses the project venv or packaged runtime consistently

Validation:

- run all health tools back-to-back and compare outputs

Rollback:

- preserve old endpoints while introducing a versioned, normalized health contract if needed

## 12. Recommended Execution Order

### Week 1

1. Stream A: freeze truth
2. Stream B: stop secret bleed
3. Stream E: route registry cleanup
4. Stream F: evaluation stack repair

### Week 2

1. Stream C: collection registry unification
2. Stream D: KBLI payload contract repair
3. Stream O: health/readiness normalization

### Week 3

1. Stream G: KG cleanup pipeline dry run
2. Stream H: KG lineage normalization
3. Stream J: Qdrant client centralization
4. Stream I: HTTP client lifecycle consolidation

### Week 4

1. Stream K: concurrency/capacity recalibration
2. Stream L: graph-engine branch repair
3. Stream M: frontend type-safety reduction
4. Stream N: CSP and visual-system normalization

## 13. Definition Of Done

The remediation program is complete only when all of the following are true:

1. No tracked hardcoded keys remain.
2. Backend collection names resolve through one canonical registry.
3. KBLI payload schema is documented, enforced, and tested.
4. FastAPI route duplication count is zero.
5. RAG evaluation suite is green.
6. KG duplicate/self-loop/placeholder metrics are reduced and monitored.
7. Health/readiness tools produce consistent top-level states.
8. Frontend production code has no `console.log` and materially fewer unsafe `any` escapes.
9. Capacity assumptions are documented and matched by Fly concurrency settings.

## 14. Immediate Next Branch

If execution starts now, the recommended first branch is:

- `audit/p0-collections-and-secrets`

Tasks in that branch only:

1. create the collection registry
2. remove tracked hardcoded keys
3. fix duplicate analytics router registration
4. add route uniqueness test
5. add collection-name regression tests

This branch has the highest risk reduction per unit of effort and least coupling to later cleanup waves.
