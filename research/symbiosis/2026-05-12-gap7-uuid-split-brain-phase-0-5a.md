---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS gap-closure loop · Gap 7 (MISSING FROM ORIGINAL LOOP, surfaced by NB-1 review)
sources: 2
status: follow-up
loop_branch: feat/symbiosis-loop-2026-05-12
discovered_by: NB-1 overall review 2026-05-12 04:15 WITA
---

# Gap 7 — UUID Split-Brain Phase 0.5a (follow-up spec)

**Generated**: 2026-05-12 04:40 WITA · Gap surfaced by NB-1 review of PR #588 · NOT in original 5-gap loop.

## NB-1 verdict

> Phase 0.5 hardcoded UUIDs 3x SOTTO-STIMATO (25 files NOT 8)
>
> Plan claim: "8 hardcoded UUID files to consolidate"
> Evidence empirical (`grep -rln "[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}" apps/`): 25 files
>
> TWO competing registries already exist:
>
> - `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py`
> - `apps/evaluator/nlm_deep_research/registry.py`
>
> Phase 0.5 deve consolidare 2 esistenti, non solo creare nuovo SSOT.
> Phase 0.5 effort 10h→25-28h (consensus already) è ANCORA sotto-stimato. 25 files refactor + tests + deploy = realistic 35-45h.

## NB-1 cited canonical SSOT (Phase 0.5 winner)

> Q2.2: Phase 0.5 Registry SSOT canonical
> Vincitore: `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py` (già "the authoritative registry")
> Da rimuovere duplicato: `apps/backend-rag/backend/core/legal_config.py NB_NOTEBOOK_IDS`
> Falso positivo: `apps/evaluator/nlm_deep_research/registry.py` (gestisce JSON metadata per-NB, non infra UUID)

> 4-layer routing rischio split-brain:
> Query "PT PMA + Tax" → intent_classifier → tax_genius vs nlm_feeder/federation_capability_table → company → NB-3 (sbagliato, doveva NB-4)

## Why this gap was missed

The original 5-gap loop focused on cell observability + HGT + Consiglio + matagaruda dup. NotebookLM UUID hardcoding was a separate audit finding from `cicatrix-scars.md` references that I did not survey when scoping the briefing.

## Empirical verification (TODO for future PR)

```bash
cd ~/Desktop/nuzantara
grep -rln "[a-f0-9]\{8\}-[a-f0-9]\{4\}-[a-f0-9]\{4\}-[a-f0-9]\{4\}-[a-f0-9]\{12\}" apps/ | wc -l
# Expected: ~25 files (per NB-1 audit). Verify on 2026-05-12 disk state.
```

NOT run in this loop — would be a scan operation outside doc-only scope.

## Action items (for separate PR)

1. **Phase 0.5a (UUID SSOT minimal)** — 4h estimate (per NB-1 consensus): consolidate 25 hardcoded UUIDs into `oracle/nlm_notebook_registry.py` only
2. **Phase 0.5b (routing consolidation)** — 16h: 4-layer routing (federation_capability_table.py + intent_classifier.py + nlm_feeder.py + CLAUDE.md prose) → single source of truth
3. **Phase 0.5c (doc reconciliation)** — 4h: incrementale 2h bursts to align docs with code
4. **CRITICAL blocker for Phase 3**: without 0.5a, Phase 3 SurfaceRouter routes to inconsistent surfaces

**This loop NO action**: doc-only follow-up spec, decision deferred to Zero in a separate PR.

## Refusals enforced

1. NO autonomous UUID consolidation (touches 25 files — out of doc-only scope)
2. NO autonomous removal of `legal_config.py NB_NOTEBOOK_IDS` duplicate
3. NO autonomous edit of `oracle/nlm_notebook_registry.py`

## Sources

1. NB-1 query response 2026-05-12 04:15 WITA (`/tmp/symbiosis-nlm-review-2026-05-12/06_overall_review.md`)
2. NB-1 reference cited_text `740990fc-e7fa-462b-939a-18ea47690793` (Phase 0.5 audit 2026-05-04) + `b8b95433-7450-4a8a-a6dd-287c22ba3e3c` (canonical registry decision)
