# SYSTEM_AUDIT_REPORT_2026

Date: 2026-03-13
Auditor mode: Senior AI System Architect & Lead Auditor
Scope: `apps/backend-rag`, `apps/mouth`, `apps/graph-engine`, live read-only Postgres, live read-only Qdrant, Fly/Vercel config, repo secret surface
Audit mode: Read-only analysis only

## 1. Executive Summary

Nuzantara is functionally alive, but the ecosystem shows structural drift between documented architecture, live infrastructure, and code paths. The two highest-risk themes are:

1. Qdrant collection/schema drift between live collections and backend references.
2. Knowledge Graph semantic hygiene degradation despite good referential integrity.

The platform still has strong foundations:

- Backend health reports the live embedding model as `text-embedding-3-small` with `1536` dimensions.
- Live Qdrant reports `9` collections and backend health reports `82,736` total documents.
- Live KG referential integrity is intact: `0` orphan source edges and `0` orphan target edges.
- Frontend TypeScript typecheck passes.
- Local backend import chain passes in the project venv.

But production readiness for 2026 scale is limited by:

- legacy/incorrect collection names in code (`kbli_2025_final`, `legal_unified`, `tax_genius`) while live Qdrant exposes `*_hybrid` variants,
- duplicate FastAPI route registration,
- dead LangGraph branches,
- secret hygiene debt in tracked legacy files/scripts,
- high Qdrant search latency with low cache efficiency,
- failing RAG evaluation suite (`12` failures in `backend/tests/services/rag/`),
- inconsistent health/readiness signals across monitoring surfaces.

## 2. Constraints And Observability Limits

- Machine: `Pro` (`nuzantara@Nuzantara`)
- Peer machine status: `Air` unreachable during session start
- Repo sync status: remote sync could not be verified because peer SSH was unreachable
- MCP readiness at session start was partial; direct tool calls later succeeded for Postgres, Qdrant, and Nuzantara health tools
- Qdrant was reachable via read-only tool, but local shell resolution to the configured Qdrant host failed
- `nuzantara-mcp-advanced` readiness check reported a missing `jose` dependency in its own execution context, but the same import succeeded in the project venv locally

Implication: live DB/vector evidence is strong; shell-based remote checks were partially constrained by environment/tooling.

## 3. Method

The audit combined:

- static code scan with `rg`, AST-based import mapping, and config inspection,
- live read-only Postgres queries for KG integrity,
- live read-only Qdrant collection and payload inspection,
- backend/infra health tools,
- frontend typecheck,
- backend validation through `pytest backend/tests/services/rag/ -q`.

Official KBLI 2025 source alignment was checked against BPS publications dated 2025-12-01:

- BPS publication: `Klasifikasi Baku Lapangan Usaha Indonesia 2025`
- BPS regulation: `Peraturan Badan Pusat Statistik Nomor 7 Tahun 2025 tentang Klasifikasi Baku Lapangan Usaha Indonesia`

## 4. Top Findings

Scoring note:

- `evidence_score` is constrained to `0.15` to `0.60`
- higher means stronger observed evidence and stronger actionability

### F1. Qdrant Collection Drift And KBLI Payload Contract Mismatch

- Priority: `P0`
- Evidence score: `0.60`

What was observed:

- Live Qdrant collections:
  - `kbli_2025_final_hybrid`
  - `legal_unified_hybrid_hybrid`
  - `tax_genius_hybrid`
  - `bali_zero_pricing_hybrid`
  - `visa_oracle`
  - `kbli_tka_hybrid`
  - `training_conversations_hybrid`
  - `immigration_circulars`
  - `intel_authoritative_sources`
- Backend code still references legacy names:
  - `kbli_2025_final` in [backend/app/routers/kbli_notebook.py](apps/backend-rag/backend/app/routers/kbli_notebook.py)
  - `kbli_2025_final`, `legal_unified`, `tax_genius` in [backend/app/modules/knowledge/service.py](apps/backend-rag/backend/app/modules/knowledge/service.py)
  - routing constants in [backend/services/routing/query_router.py](apps/backend-rag/backend/services/routing/query_router.py)
- The KBLI Notebook router assumes top-level payload keys like `kode_kbli` and `judul`, but live KBLI payloads are shaped as:
  - top-level `text`
  - nested `metadata.kode_kbli`, `metadata.judul`, etc.
- The KBLI reindex pipeline explicitly writes nested payloads under `metadata` in:
  - [backend/scripts/reindex_kbli_2025_final.py](apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py)
  - [backend/scripts/index_kbli_gold_content.py](apps/backend-rag/backend/scripts/index_kbli_gold_content.py)
- Checked live Qdrant collections expose empty `payload_schema` while strict mode is enabled on at least:
  - `kbli_2025_final_hybrid`
  - `legal_unified_hybrid_hybrid`
  - `kbli_tka_hybrid`

Why this matters:

- Retrieval can silently fragment across stale collection names.
- Filtered KBLI lookups are structurally misaligned with live payload shape.
- Empty payload schemas reduce confidence in filter performance and indexed retrieval behavior at scale.

Positive nuance:

- The source KBLI JSON in `apps/kbli-navigator/data/kbli-2025.json` is flat and aligned with BPS/PP28 fields.
- The drift is primarily in vector payload and collection contract, not in the raw KBLI source dataset itself.

Recommended next step:

- Establish one canonical live collection map and one canonical KBLI payload contract.
- Migrate all backend references to live `*_hybrid` collection names or publish a compatibility layer.
- Eliminate nested `metadata` wrapping for KBLI payloads if the platform rule is truly "flat payload", or formally update the rule and all consumers.

### F2. Knowledge Graph Referential Integrity Is Good, Semantic Hygiene Is Not

- Priority: `P0`
- Evidence score: `0.58`

Live Postgres evidence:

- `kg_nodes`: `81,913` rows
- `kg_edges`: `276,853` rows
- orphan source edges: `0`
- orphan target edges: `0`
- self-loops: `1,953`
- duplicate edge groups: `2,106`
- excess duplicate edges: `2,148`
- suspicious placeholder-like nodes: `111`
- suspicious placeholder-like edges: `1,528`

Examples of suspicious node IDs returned from live data:

- `biaya_unknown`
- `izin_unknown`
- `kbli_none`
- `kbli_kbli_...`
- `doc_no_unknown`
- `bismillah_none`

Collection/source drift is also visible in KG lineage:

- both `legal_unified_hybrid_hybrid` and `legal_unified_hybrid` are present in KG lineage
- KBLI lineage spans `kbli_2025_final`, `kbli_2025_import`, and `kbli_unified`

Why this matters:

- Referential integrity alone does not guarantee a clean reasoning graph.
- Placeholder nodes, duplicates, and self-loops inflate traversal paths and reduce semantic precision.
- The graph is already larger than documented (`81,913/276,853` live vs older `56k/161k` narrative), so hygiene debt compounds quickly.

Recommended next step:

- Add a KG hygiene pipeline that prunes placeholder entities, deduplicates `(source, target, relationship_type)` triples, and flags self-loop relation classes that are not explicitly allowed.
- Freeze canonical source collection names and backfill lineage normalization.

### F3. Secret Hygiene Debt Exists In Tracked Legacy Code And In Local Workspace Sprawl

- Priority: `P0`
- Evidence score: `0.57`

Tracked exposure observed:

- Hardcoded Google Maps fallback key in [app_dashboard.py](app_dashboard.py)
- Hardcoded Gemini API keys in tracked backend scripts under `apps/backend-rag/scripts/`
- Historical docs under `docs/archive/transient/intel_scraper/` include literal Google API keys

Workspace-level local secret sprawl observed:

- Untracked local `.env` files exist in:
  - `apps/backend-rag/.env`
  - `apps/backend-rag/.env.backup_20260218_104730`
  - `apps/bali-intel-scraper/.env`
  - `apps/mouth/.env.local`
  - `apps/mouth/.env.production.local`
  - `apps/war-room/.env`
- The backup file alone exposes the existence of duplicate secret-bearing local snapshots.

Tracked `.env` files are limited to examples/tests:

- tracked: `.env.example`, `apps/backend-rag/.env.example`, `apps/backend-rag/.env.test`, `apps/mouth/.env.example`

Why this matters:

- The tracked hardcoded keys are a real repository hygiene issue even if currently revoked.
- Local secret backups materially increase workstation blast radius.
- This violates the project rule against hardcoded secrets and weakens auditability.

Recommended next step:

- Remove hardcoded keys from tracked legacy scripts/docs immediately.
- Replace fallback keys with mandatory env lookup plus fail-closed behavior.
- Remove backup `.env` artifacts from the workspace and standardize on secret manager + `.env.example` only.

### F4. FastAPI Route Registry Contains Duplicate Analytics Registration

- Priority: `P1`
- Evidence score: `0.56`

Observed in code:

- [backend/app/setup/router_registration.py](apps/backend-rag/backend/app/setup/router_registration.py) includes `analytics.router` twice:
  - line `158`
  - line `259`

Observed at runtime:

- App inspection showed `528` API routes
- Duplicate path+method pairs observed: `5`
- All duplicates were analytics endpoints:
  - `/api/analytics/completion-rates`
  - `/api/analytics/monthly-report/{year}/{month}`
  - `/api/analytics/response-times`
  - `/api/analytics/revenue`
  - `/api/analytics/sla-compliance`

Why this matters:

- Duplicate route registration is avoidable route-table bloat.
- It increases confusion in OpenAPI/runtime introspection and is exactly the kind of registry drift that becomes harder to reason about at scale.

Recommended next step:

- Deduplicate router registration and add a route-table regression test that asserts unique `(path, method)` pairs.

### F5. Performance Posture Is Async-Correct In Principle, But Runtime Bottlenecks Remain

- Priority: `P1`
- Evidence score: `0.52`

Observed positives:

- Core runtime heavily favors `httpx` async usage.
- No evidence of `requests` use in the main backend request path; remaining `requests` hits are in legacy scripts, tests, docs, or side tools.
- Qdrant wrapper in [backend/core/qdrant_db.py](apps/backend-rag/backend/core/qdrant_db.py) uses pooled `httpx.AsyncClient` and the correct embedding model.

Observed bottlenecks:

- Fly runtime is pinned to `--workers 1` in [apps/backend-rag/Dockerfile](apps/backend-rag/Dockerfile)
- Same Fly config allows request concurrency of `200` soft / `250` hard on a `4gb`, `2 cpu` machine in [apps/backend-rag/fly.toml](apps/backend-rag/fly.toml)
- Live Qdrant metrics:
  - `search_avg_time_ms`: `1244.5`
  - `query_cache` hit rate from detailed health: `3.6%`
- `GoogleDriveService` creates a fresh `httpx.AsyncClient()` in `13` separate call sites in [backend/services/integrations/google_drive_service.py](apps/backend-rag/backend/services/integrations/google_drive_service.py)
- Direct `QdrantClient(...)` instantiation still appears `24` times across routers/services, despite the dependency layer explicitly stating it should replace direct instantiation

Why this matters:

- Single-worker operation is understandable for memory constraints, but it pushes more pressure onto async efficiency, queueing, and connection reuse.
- Low cache effectiveness plus repeated client creation increases latency variance and external API overhead.

Recommended next step:

- Treat `1 worker` as an explicit capacity limit and size concurrency accordingly.
- Introduce shared/persistent HTTP clients for Drive/Zoho-like integration services.
- Collapse direct `QdrantClient` construction behind centralized dependencies/factories.

### F6. Graph Engine Contains Dead Or Unreachable Branches

- Priority: `P1`
- Evidence score: `0.49`

Observed in `apps/graph-engine`:

- `NodeName.GRADE_PRICING` is declared in [src/nuzantara_graph/graph/constants.py](apps/graph-engine/src/nuzantara_graph/graph/constants.py) and added in [src/nuzantara_graph/graph/builder.py](apps/graph-engine/src/nuzantara_graph/graph/builder.py), but has no inbound or outbound edges
- `RouteDecision.TOOLS` is mapped in the graph builder, but `route_after_understand()` never returns it in [src/nuzantara_graph/graph/router.py](apps/graph-engine/src/nuzantara_graph/graph/router.py)
- The understand prompt supports intents including `pricing` and `followup`, but router logic only branches on:
  - `greeting`
  - `business_setup`
  - `visa`
  - `property`
  - `tax`
  - default `retrieve`

Why this matters:

- The graph advertises more decision surface than it actually executes.
- Dead branches reduce test relevance and increase the risk of false architectural assumptions.

Recommended next step:

- Either wire pricing/tool/followup branches fully, or remove the dead node/route declarations until they are production-ready.

### F7. Frontend Type Safety And Design System Are Functional But Not Yet 2026-Clean

- Priority: `P2`
- Evidence score: `0.41`

Observed positives:

- `npm run typecheck` passes in `apps/mouth`
- `strict: true` is enabled
- security headers and image controls are present in [apps/mouth/next.config.ts](apps/mouth/next.config.ts)

Observed debt:

- `tsconfig.json` still allows `allowJs: true` and `skipLibCheck: true`
- production code scan found:
  - `95` `any` usages
  - `7` `console.log` usages
  - `4` `@ts-ignore` / `@ts-expect-error` usages
- High-impact `any` clusters appear in:
  - `PrimeMap3D`
  - analytics helpers
  - workflow API helpers
  - article composer/news-room workspace code
- Visual-system drift:
  - `Geist` is configured in [src/app/layout.tsx](apps/mouth/src/app/layout.tsx)
  - `body` is then hard-overridden to `"Inter"` in [src/app/globals.css](apps/mouth/src/app/globals.css)
  - root HTML forces `className="dark"`
- CSP is configured as `Content-Security-Policy-Report-Only` rather than enforced in [apps/mouth/next.config.ts](apps/mouth/next.config.ts)

Why this matters:

- The frontend is stable enough to ship, but not yet at the level of strictness and design coherence expected from a 2026 baseline.
- Passing typecheck currently overstates real type robustness because escape hatches remain common in application code.

Recommended next step:

- Reduce `any` usage in critical workspace/admin surfaces first.
- Remove production `console.log` calls.
- Decide whether Geist or Inter is the canonical font system and enforce one path only.
- Graduate CSP from report-only to enforced once violations are cleared.

### F8. Validation And Monitoring Surfaces Are Not Internally Consistent

- Priority: `P1`
- Evidence score: `0.47`

Observed validation results:

- Local import chain in project venv:
  - `from backend.app.dependencies import get_current_user` => `OK`
- `nuzantara-mcp-advanced.check_deployment_readiness`:
  - `ready=false`
  - import-chain failure due `ModuleNotFoundError: No module named 'jose'`
- This conflicts with the local venv reality where `jose` is installed and import succeeds

Observed backend/RAG validation:

- `pytest backend/tests/services/rag/ -q`
  - `12 failed`
  - `616 passed`
  - `125 skipped`
- Failures cluster in:
  - `backend/services/rag/evaluation/benchmark.py`
  - `backend/services/rag/evaluation/dataset_builder.py`
  - `backend/services/rag/evaluation/ragas_evaluator.py`

Observed health inconsistency:

- `check_health`: `healthy`
- `check_health_detailed`: `degraded`
- `check_system_health` from advanced tooling reported overall healthy backend while many component booleans were false in the tool output

Why this matters:

- Operational dashboards currently overstate certainty.
- Tooling drift between local venv, MCP runner, and service registry reduces trust in readiness decisions.

Recommended next step:

- Standardize deployment-readiness checks on the same environment/venv as production packaging.
- Tighten health semantics so "healthy" and "degraded" are not emitted simultaneously from neighboring surfaces for the same slice of the stack.

## 5. Backend Architecture Snapshot

Observed backend structure:

- router files: `86`
- service files: `272`
- routers importing services: `52`
- router-to-router import edges: `10`
- direct Qdrant instantiation sites in routers/services: `24`

Interpretation:

- The backend is still centralized enough to reason about, but some routers are behaving as mini-orchestrators and directly coupling to peer routers or infra clients.

Notable hotspots:

- [backend/app/setup/router_registration.py](apps/backend-rag/backend/app/setup/router_registration.py)
- [backend/app/modules/knowledge/service.py](apps/backend-rag/backend/app/modules/knowledge/service.py)
- [backend/app/routers/kbli_notebook.py](apps/backend-rag/backend/app/routers/kbli_notebook.py)
- [backend/app/routers/dashboard_summary.py](apps/backend-rag/backend/app/routers/dashboard_summary.py)
- [backend/services/integrations/google_drive_service.py](apps/backend-rag/backend/services/integrations/google_drive_service.py)

## 6. KBLI 2025 Alignment

Official alignment:

- BPS officially published KBLI 2025 and BPS Regulation No. 7/2025 on `2025-12-01`
- The local KBLI 2025 dataset in `apps/kbli-navigator/data/kbli-2025.json` carries fields consistent with a flat business-domain representation:
  - `kode_kbli_2025`
  - `judul`
  - `uraian`
  - `per_skala`
  - `pma_status`
  - `pma_max_asing`
  - `sektor_id`
  - `status_mapping`

Alignment verdict:

- Raw source dataset: aligned
- Vector payload contract in backend: not aligned with the project's stated "flat payload" rule
- Consumer contract in KBLI Notebook / collection registry: not aligned with live Qdrant state

## 7. Security Snapshot

Good:

- Fly config keeps Qdrant URL out of plaintext config and expects secrets injection
- Frontend build does not ignore TypeScript build errors
- Backend requirements pin `python-jose[cryptography]>=3.4.0`

Weak:

- hardcoded secrets in tracked legacy files/scripts/docs
- local `.env` sprawl and backups
- CSP still report-only
- multiple admin/observability routes directly hit infra without centralized wrappers

## 8. Validation Summary

### Local backend import chain

- Command: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python -c "from backend.app.dependencies import get_current_user; print('OK')"`
- Result: `OK`

### Backend RAG suite

- Command: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/services/rag/ -q`
- Result:
  - `12 failed`
  - `616 passed`
  - `125 skipped`

Failure concentration:

- `benchmark.py`
  - stale test expectations (`hybrid` vs `hybrid_rrf`)
  - missing patched attribute `RerankerIntegration`
  - async mock mismatch in DB save path
- `dataset_builder.py`
  - placeholder templates not fully filled
  - integer truncation causes size/ratio drift
  - invalid-ratio guard not behaving as tests expect
- `ragas_evaluator.py`
  - async mock path accepts `MagicMock` where awaitable contract is expected

### MCP advanced readiness

- `ready=false`
- import-chain failure is likely runner-environment drift, because the project venv locally imports `jose` successfully
- core tests in MCP advanced output were also not green

## 9. Action Plan

### Immediate

1. Canonicalize live collection names and KBLI payload contract across backend, Qdrant, and KG ingestion.
2. Remove tracked hardcoded keys and delete local secret backup artifacts.
3. Fix duplicate analytics router registration and add a unique-route assertion test.

### Next Sprint

1. Run KG hygiene cleanup for duplicate edges, self-loops, and placeholder entities.
2. Consolidate direct `QdrantClient` construction behind shared dependencies/factories.
3. Rework evaluation stack failures in `benchmark.py`, `dataset_builder.py`, and `ragas_evaluator.py`.
4. Reconcile deployment readiness tooling with the actual project venv and packaging path.

### Scale 2026

1. Rebalance Fly concurrency against single-worker memory limits.
2. Improve cache hit rate and introduce connection reuse for integration services.
3. Reduce frontend `any` usage in critical admin/workspace flows and enforce CSP.
4. Either fully wire or remove dead LangGraph branches before expanding graph complexity.

## 10. Final Verdict

Nuzantara is not in a broken state, but it is carrying enough contract drift and hygiene debt that 2026 scaling would amplify retrieval inconsistency, observability confusion, and operational risk.

The most important distinction from this audit is:

- infrastructure core is alive,
- data/model contracts are drifting,
- graph semantics are accumulating debt,
- readiness signals are less trustworthy than they should be.

That combination is manageable now, but it should be corrected before the next scaling or reliability push.

## 11. Sources

- Official BPS KBLI 2025 publication:
  - https://www.bps.go.id/id/publication/2025/12/01/b9a8f9b5e6d8470e8f2c4fd0/klasifikasi-baku-lapangan-usaha-indonesia-2025.html
- Official BPS Regulation No. 7/2025:
  - https://www.bps.go.id/id/publication/2025/12/01/e2f1df1d2cbd4bfaa2f8c2b0/peraturan-badan-pusat-statistik-nomor-7-tahun-2025-tentang-klasifikasi-baku-lapangan-usaha-indonesia.html
