---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS Gap 7 — UUID Split-Brain Phase 0.5a consolidated spec (post empirical survey)
sources: 6
status: spec-ready-for-execution
empirical_survey_wita: 2026-05-12 15:25
---

# Gap 7 — UUID Split-Brain: Phase 0.5a Consolidated Spec

**Empirical survey time**: 2026-05-12 15:25 WITA
**Outcome**: Refines NB-1 audit "25 files" claim to **22 files** verified on disk + **2 duplicate registries** confirmed. Spec ready for execution by future PR (no autonomous code changes this PR — operator decision required for scope/timeline).

## Empirical survey results (verbatim from disk)

Survey command:

```bash
grep -rl "f6ecd115\|d9438180\|NB_NOTEBOOK_IDS\|nlm_notebook_registry\|nlm_deep_research/registry" \
  apps/ --include="*.py" 2>/dev/null \
| grep -vE "__pycache__|\.venv" | sort -u | wc -l
```

Result: **22 unique Python files**.

Per-file hardcoded UUID density (count of `"<UUID>"` literal patterns):

| Hardcoded count | File | Notes |
|---:|---|---|
| 31 | `apps/backend-rag/backend/services/oracle/nlm_orchestrator.py` | Largest offender — has full NB-0..NB-30 mapping inline |
| 8 | `apps/evaluator/nlm_deep_research/multimodal_pipeline.py` | |
| 8 | `apps/bali-intel-scraper/scripts/nlm_research_step.py` | |
| 7 | `apps/evaluator/nlm_deep_research/gap_scanner.py` | |
| 7 | `apps/evaluator/nlm_deep_research/cross_notebook_correlator.py` | |
| 7 | `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py` | **THIS IS THE SSOT** — 7 UUIDs are the canonical registry data |
| 7 | `apps/backend-rag/backend/services/oracle/cross_notebook_correlator.py` | Duplicates the SSOT for offline reasons (worker module) |
| 5 | `apps/evaluator/nlm_deep_research/freshness_monitor.py` | |
| 5 | `apps/backend-rag/backend/core/legal_config.py` | **NB_NOTEBOOK_IDS DUPLICATE** — see below |
| 4 | `apps/evaluator/nlm_deep_research/yt_monitor.py` | |
| 1 | `apps/evaluator/nlm_deep_research/nb5_pipeline.py` | |
| 0 | `apps/backend-rag/backend/services/oracle/nlm_shadow_retrieval.py` | imports registry indirectly |
| 0 | `apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py` | uses `from nlm_notebook_registry` ✅ |
| 0 | `apps/backend-rag/backend/services/rag/agentic/orchestrator_streaming_core.py` | uses `from nlm_notebook_registry` ✅ |
| Test files | 8 files | not counted (tests intentionally hardcode for fixture isolation) |

**Production files with hardcoded UUIDs: 11** (excluding test fixtures).

## The two competing registries

### SSOT canonical: `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py`

`NLM_NOTEBOOKS: dict[str, dict]` — domain-keyed (immigration, company, tax, property, operations, etc.), each entry has `notebook_id`, `primary_notebook_id`, `label`, `keywords`. Rich metadata. Used by `resolve_notebook()` + `is_stale()` (S1.3 stale-ingestion gate).

Currently imported by ONLY 2 production files (`orchestrator_core.py` + `orchestrator_streaming_core.py`).

### Duplicate (anti-pattern): `apps/backend-rag/backend/core/legal_config.py NB_NOTEBOOK_IDS`

```python
NB_NOTEBOOK_IDS: Final[dict[str, str]] = {
    "NB-2": "cff93ab0-813a-42f2-a8de-36987e724271",  # Immigration
    "NB-3": "933509f9-1561-403d-bd44-4a7a67a36df2",  # Company Setup
    "NB-4": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",  # Tax
    "NB-5": "d9438180-5e63-4e2a-a473-6061101f6a8d",  # Property
    "NB-6": "85207af3-352f-4554-8d2a-18f42cc541ba",  # Operations
}
```

5 UUIDs that EXACTLY duplicate the values in `NLM_NOTEBOOKS[domain]["notebook_id"]`. Used by the legal-config flow only. Risk: when an NB UUID changes (e.g. legacy NB-2 cff93ab0 superseded by a new ingestion), `legal_config` will go stale silently because it has no link back to the canonical registry.

### NOT a duplicate (per NB-1 review): `apps/evaluator/nlm_deep_research/registry.py`

Per NB-1: "Falso positivo: `apps/evaluator/nlm_deep_research/registry.py` (gestisce JSON metadata per-NB, non infra UUID)". Verified: this file handles per-NB JSON metadata (citations, last refresh, source counts) keyed by NB-ID — it's a CONSUMER of the canonical UUIDs, not a competing registry.

## Phase 0.5a scope (minimal, 4h target per NB-1 consensus)

**Goal**: every production reference to a NotebookLM UUID goes through `nlm_notebook_registry.NLM_NOTEBOOKS` (or its convenience functions `get_notebook_id_for_domain(domain)`, `resolve_notebook(query)`).

### Changes required

1. **Delete `NB_NOTEBOOK_IDS` from `legal_config.py`** and replace with import + lookup function. Add `from backend.services.oracle.nlm_notebook_registry import get_notebook_id_for_domain` + new helper `nb_legal_target_to_id(target: str) -> str` that maps "NB-2" → `get_notebook_id_for_domain("immigration")["notebook_id"]`.
2. **Refactor `nlm_orchestrator.py`** (31 hardcoded — the biggest offender). The 31 UUIDs are likely NB-0..NB-30 inline mapping. Move to `NLM_NOTEBOOKS` if missing, or to a new `NLM_NOTEBOOK_INDEX` dict in the registry if the 31 represent operational variants. Inspect first to decide.
3. **Refactor `oracle/cross_notebook_correlator.py`** (7 hardcoded). Same as #2.
4. **Refactor `evaluator/nlm_deep_research/*`** (5 files: multimodal_pipeline, gap_scanner, cross_notebook_correlator, freshness_monitor, yt_monitor, nb5_pipeline = 32 hardcoded UUIDs combined). Each imports `nlm_notebook_registry` instead of inlining.
5. **Refactor `bali-intel-scraper/scripts/nlm_research_step.py`** (8 hardcoded).
6. **Tests**: leave test_*.py files alone (fixtures intentionally hardcode).
7. **CI guard**: add `apps/backend-rag/backend/tests/setup/test_uuid_ssot.py` that greps production code (excluding tests) for hardcoded UUID patterns and fails CI if any are introduced outside `nlm_notebook_registry.py`.

### Out of scope for Phase 0.5a (defer to 0.5b / 0.5c)

- **Phase 0.5b** "routing consolidation" (16h) — `federation_capability_table.py` + `intent_classifier.py` + `nlm_feeder.py` + CLAUDE.md prose → single source of truth. Deferred.
- **Phase 0.5c** "doc reconciliation" (4h incremental) — align docs with code. Deferred.

## Effort revision

NB-1 audit consensus was 4h for Phase 0.5a (UUID SSOT minimal). Empirical survey suggests this is realistic IF the 31-UUID file (`nlm_orchestrator.py`) is a straightforward NB-X mapping. If those 31 are operational variants requiring schema extension to `NLM_NOTEBOOKS`, effort balloons to 8-12h.

**Recommend**: ~4h scope-bounded for the 11 production files. Each file is a single-PR or 2-file-PR change (refactor + tests). Total: 6-8 small PRs, mergeable in parallel.

## Risk assessment

- **Low**: `legal_config.py` change (5 UUIDs → 1 import). Mechanical.
- **Medium**: `nlm_orchestrator.py` (31 UUIDs). Needs inspection of the actual usage pattern to decide registry shape.
- **Medium**: `evaluator/nlm_deep_research/*` (5 files). Risk of breaking the deep-research pipeline if registry shape mismatches expectations.
- **Low**: CI guard test addition. Standard pattern.

Mitigation: each file's refactor PR runs the existing test suite + adds a regression test that asserts the file no longer contains hardcoded UUIDs (grep-style negative assertion).

## Execution sequencing

1. **Week 1 day 1** (~2h): refactor `legal_config.py` (smallest, mechanical). Verify operators use it. Ship.
2. **Week 1 day 1** (~1h): add CI guard test (negative grep assertion). Ship.
3. **Week 1 day 2** (~2h): refactor `evaluator/nlm_deep_research/*` (5 files, similar pattern).
4. **Week 1 day 2** (~2h): refactor `oracle/cross_notebook_correlator.py` + `bali-intel-scraper/scripts/nlm_research_step.py`.
5. **Week 1 day 3** (~3h): refactor `nlm_orchestrator.py` (31 UUIDs — biggest, requires schema decision).
6. **Total**: ~10h spread across ~3 days. Closer to NB-1's "0.5a 4h" if you stop after step 1+2 (the duplicate-registry kill is the critical part for SSOT integrity); steps 3-5 are cleanup that can be incremental.

## What this loop produces

**Doc only**. Spec landed in repo, ready for the operator to schedule the refactor PRs. No autonomous code changes (`apps/backend-rag/` is high-blast-radius; bulk refactor needs human review per CLAUDE.md `backend.app.dependencies` SPOF guard).

## Status post Gap 7 spec

- ✅ Empirical survey complete (22 files, 11 production with hardcoded UUIDs)
- ✅ Duplicate registry identified: `legal_config.NB_NOTEBOOK_IDS`
- ✅ False-positive ruled out: `nlm_deep_research/registry.py` (it's a metadata consumer)
- 📋 Refactor execution: deferred to operator (~4-10h depending on scope)

## Loop gap status final

- ✅ Gap 1 Cell silenti — closed empirically
- ✅ Gap 2 Consiglio — KILL revoked
- 📋 Gap 3 HGT TICKET A/B/C — deferred (in-progress)
- ✅ Gap 4 Ghost MEMORY.md — closed
- ✅ Gap 5 matagaruda — closed no-op (cicatrix already resolved)
- ✅ Gap 6 MATA GARUDA Gov 313 — apoptosi executed
- ✅ Gap 7 UUID Split-Brain — **spec ready, execution deferred**

**6/7 gaps closed or spec-ready**. Only Gap 3 (HGT) remains with substantive future work (3 prereq tickets each 1-2 days).

## Sources

1. Empirical grep survey 2026-05-12 15:25 WITA (`grep -rl ... apps/ --include="*.py"`)
2. Per-file hardcoded-UUID count via awk pipeline
3. `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py:1-50` (canonical SSOT)
4. `apps/backend-rag/backend/core/legal_config.py:15-30` (duplicate `NB_NOTEBOOK_IDS`)
5. NB-1 review report `/tmp/symbiosis-nlm-review-2026-05-12/06_overall_review.md` (Q2.2 canonical SSOT decision)
6. PR #588 commit `4dacb4f41` Gap 7 follow-up spec (less empirical, this doc supersedes)
