# Visa Subgraph Multi-Step Planner — Design

**Status:** Approved (task-prescribed, autonomous execution authorized)
**Date:** 2026-04-11
**Branch:** `feat/visa-multi-step-planner`
**Worktree:** `.worktrees/visa-planner`

## Problem

The current visa subgraph (`apps/graph-engine/src/nuzantara_graph/subgraphs/visa.py`, 246 lines) answers user visa questions in a single retrieve→synthesize pass. It picks one `VisaType` via regex heuristics, fetches one hardcoded spec block, runs one vector search, and hands off to the main REASON node.

This collapses multi-hop questions ("I overstayed 3 days, then left — can I come back on e-visa?"), ignores contradictory sources, and cannot attribute claims to evidence. We want a planner that decomposes, retrieves with citations per sub-question, self-critiques, then composes.

## Contract (Backward Compatibility)

The exported symbol `make_visa_subgraph(services) -> async callable` must remain the entry point — it is imported by `graph/builder.py` as `NodeName.SUBGRAPH_VISA` and wired to exit into `REASON`.

The returned callable must return a `dict[str, Any]` containing **at minimum**:

```python
{
  "retrieved_documents": list[RetrievedDocument],
  "kg_entities": list[dict[str, Any]],
  "kg_relationships": list[dict[str, Any]],
  "domain": str,
  "current_node": "subgraph_visa",
}
```

Additional keys (e.g. `visa_planner_trace`) are permitted; the core graph will ignore them.

## Pipeline (LangGraph `StateGraph`)

```
         ┌─────────────┐
         │  entry      │
         └──────┬──────┘
                │
         ┌──────▼──────┐
         │ b211_rewrite│  ← synchronous pre-filter
         └──────┬──────┘
                │
         ┌──────▼──────┐
         │  decompose  │  ← 1 LLM call, JSON output
         └──────┬──────┘
                │
         ┌──────▼──────┐
         │ plan_execute│  ← topo-sorted, per-node retrieval + self_critique
         └──────┬──────┘
                │
         ┌──────▼──────┐
         │   compose   │  ← 1 LLM call → citation enforcer
         └──────┬──────┘
                │
         ┌──────▼──────┐
         │  terminate  │  → returns dict[str, Any]
         └─────────────┘
```

### Step contracts

**`b211_rewrite(query) -> (rewritten_query, system_note | None)`**
Pure function. If the query mentions `b211`, `b211a`, or "social visit visa", rewrite to reference `KITAS/ITAS or e-visa (C-series)` and emit a system note chunk that the composer must cite.

**`decompose(query) -> list[SubQuestion]`**
1 LLM call with `generate_json`. Returns 1..5 sub-questions. Each has:
```python
SubQuestion(idx: int, text: str, needs_kb: bool, depends_on: list[int])
```
The returned list is normalized by `_topo_sort()`: cycles are broken by dropping the offending back-edge and logging a warning. Truncates to ≤5 sub-questions. Enforces depth ≤3 by re-indexing when a chain would exceed depth.

**`execute(sub_questions, services) -> list[NodeEvidence]`**
Topological execution. For each sub-question:
1. If `needs_kb`, call `services.vector_store.search_by_text(sub_q.text, top_k=5)`
2. Wrap results as `Chunk(doc_id, span_start, span_end, score, content)`
3. Call `compose_fragment(sub_q, chunks)` (1 LLM call) → `answer_fragment`
4. Run `ContradictionGrader.score(node_ev, prior_evidence)` → float in [0,1]
5. If score > 0.4 AND the node has not yet been retried → re-plan this one sub-question (with the prior evidence as context) and re-execute. Max 1 retry per sub-question.

Tracks a global `llm_call_count`. Raises `LlmBudgetExceeded` if it would exceed 8.

**`compose(query, node_evidences) -> str`**
1 LLM call. Prompt demands `[doc_id:start-end]` citation after every sentence. Post-processed by `_enforce_citations()`:
- Split on sentence boundaries
- Each sentence must contain at least one `[id:span]` where `id` is a known `doc_id` or the `SYSTEM:b211_rewrite` synthetic id
- If missing, attempt auto-attribution from verbatim matches
- If still missing, replace the sentence with a fallback: `"(unable to cite this claim; refer to the documents below)"`
- If ALL sentences fail, return the system fallback: `"I cannot produce a cited answer for this query. Please rephrase or contact support."`

**`terminate(state) -> dict`**
Converts `NodeEvidence` list into `RetrievedDocument` list (each chunk becomes one doc), sets `domain` based on the dominant visa type mentioned across sub-questions (falls back to `"general"`), and returns the contract dict.

## Termination Proof

Let `N = len(sub_questions)` and `R = max_retries_per_node = 1`.

- `decompose()` truncates N to ≤5. Guaranteed single execution.
- `execute()` iterates the topologically sorted list once. Each iteration calls `compose_fragment` once. If the contradiction score exceeds 0.4, the node is re-planned and re-executed — but the retry budget for that node is strictly decremented and never reset. So per-node calls ≤ 2.
- Total LLM calls ≤ 1 (decompose) + N × 2 (fragments) + 1 (compose) ≤ 12 in theory, but the global counter caps at 8. If the cap would be exceeded, remaining retries are skipped and the node falls back to its first-attempt evidence.
- `compose()` runs exactly once.
- No edge in the StateGraph loops back to a prior node. The only intra-node loop is the bounded retry inside `execute()`.

**Conclusion:** The planner halts on every input because (a) the graph is acyclic, (b) execute() is a finite for-loop over a finite list, (c) the retry budget is monotonically decreasing, (d) the global LLM budget is a hard ceiling.

## Failure Modes

| Failure | Detection | Recovery |
|---|---|---|
| Decompose LLM returns invalid JSON | `json.JSONDecodeError` | Fall back to single sub-question = original query, log warning |
| Decompose LLM unavailable (no API key) | `ValueError` from `LLMGateway` | Fall back to single sub-question = original query |
| Decompose returns cyclic deps | `_topo_sort` detects | Drop back-edge, log warning, continue |
| Decompose returns depth >3 | depth counter in `_topo_sort` | Collapse to depth 3 by merging leaf sub-qs |
| Decompose returns >5 sub-qs | length check | Truncate to first 5 |
| Vector store empty | `len(chunks) == 0` | Node evidence is empty; composer emits note chunk |
| Vector store raises | try/except in `execute()` | Node evidence is empty, log warning, continue |
| Contradiction score > 0.4 | `ContradictionGrader.score()` | Re-plan that one sub-q once (if retry budget allows) |
| All nodes produce empty evidence | `all(ev.chunks == [] for ev)` | Composer returns the "no evidence" fallback with citation to `SYSTEM:no_evidence` |
| Composer LLM returns uncitable answer | `_enforce_citations` | Drop uncitable sentences; if all drop, return system fallback |
| LLM budget exceeded mid-execute | `LlmBudgetExceeded` | Skip remaining retries, proceed with current evidence |
| B211 pre-filter matches | substring check | Rewrite query, inject system note chunk |

## Citation Enforcement Rationale

Every factual claim in a visa answer must be traceable to a document or a system note. Otherwise:
- Zantara hallucinates legal requirements (this has happened — cf. `rules/cicatrix-scars.md`)
- Users cannot verify claims against primary sources
- Compliance risk: visa rules change monthly and wrong claims have legal consequences

The enforcer is a **post-processing linter**, not a prompt instruction. LLMs ignore prompt rules under load; a deterministic check is the only way to guarantee every sentence carries a citation.

Format: `[doc_id:start-end]` — e.g. `[visa_kitas_2024.pdf:120-340]` or `[SYSTEM:b211_rewrite:0-200]`. The span numbers may be approximate (full-document by default) — this is declared in the architecture doc as a known limitation, not silently ignored.

## B211 Handling

The task specifies that B211 no longer exists. We add a pre-filter, not a special case in the LLM prompt, because:
1. Prompt instructions get diluted by larger prompts
2. A deterministic rewrite gives us a citable `SYSTEM:b211_rewrite` chunk
3. The same filter works for synonyms ("social visit visa", "Visit Visa B211A")

Pre-filter regex: `(?i)\b(b[-\s]?211[a]?|social[-\s]visit[-\s]visa|visit[-\s]visa[-\s]b[-\s]?211[a]?)\b`

Replacement: `KITAS/ITAS or e-visa (C-series)`. Attached note:
```
The B211 visit visa was abolished. Current options for temporary stay are
C-series e-visas (C1 tourism, C2 business, C7 social-cultural) or KITAS/ITAS
for stays longer than 60 days. This sub-question was rewritten accordingly.
```

## LLM Provider Policy

Graph-engine uses `Services.llm` (a `LLMGateway` wrapping Gemini). We do NOT import from `apps/backend-rag/backend/llm/` — that crosses app boundaries. The existing `LLMGateway` already honors a provider registry (primary → fallback cascade with circuit breakers).

Direct `anthropic` / `openai` imports are forbidden. The planner calls `services.llm.generate_json(...)` and `services.llm.generate(...)` only.

If `services.llm.google_api_key == ""`, the gateway raises `ValueError` — the planner catches this and returns the single-sub-question fallback rather than crashing the whole request.

## File Layout

```
apps/graph-engine/src/nuzantara_graph/subgraphs/
├── __init__.py              # exports make_visa_subgraph from visa package
├── visa/                    # NEW — replaces visa.py
│   ├── __init__.py          # re-exports make_visa_subgraph
│   ├── planner.py           # StateGraph, make_visa_subgraph, terminate()
│   ├── types.py             # SubQuestion, Chunk, NodeEvidence, PlannerState
│   ├── decompose.py         # decompose() + B211 rewrite
│   ├── execute.py           # plan_execute() + topo sort
│   ├── compose.py           # compose() + _enforce_citations()
│   └── specs.py             # VISA_SPECS (moved from old visa.py)
├── company.py               # unchanged
├── property.py              # unchanged
└── tax.py                   # unchanged

apps/graph-engine/src/nuzantara_graph/graders/
└── contradiction_grader.py  # NEW — plain class, not BaseGrader subclass

apps/graph-engine/tests/unit/subgraphs/
└── test_visa_planner.py     # NEW — 15 cases, all unit-tier

apps/graph-engine/docs/
└── visa-planner-architecture.md  # NEW — one-page doc
```

The old `subgraphs/visa.py` is deleted. Python resolves `from nuzantara_graph.subgraphs.visa import make_visa_subgraph` to the package's `__init__.py`.

## Test Plan (15 cases)

All cases use `MockLLMGateway` with a response dict that returns pre-baked decompose JSON. All cases are `@pytest.mark.asyncio` and tagged `@pytest.mark.unit`. Live tests are a separate marker not needed for this delivery (unit tier only).

| # | Case | Mock setup | Asserts |
|---|---|---|---|
| 1 | overstay fine | decompose→1 sub-q, 3 chunks | `chunks_used >= 1`, answer cites chunk |
| 2 | KITAS→KITAP transition timeline | decompose→2 sub-qs sequential | 2 NodeEvidence, compose merges them |
| 3 | B211 rewrite | query="B211 social visa" | no "B211" in sub-qs, SYSTEM:b211_rewrite present in final docs |
| 4 | investor vs working KITAS | decompose→2 parallel sub-qs | both retrieved, both cited |
| 5 | e-visa EU citizens | decompose→1 sub-q | single node evidence |
| 6 | newborn child | decompose→1 sub-q | graceful handling even with no KB hits |
| 7 | contradictory chunks | 2 chunks with "30 days" vs "60 days" | contradiction_score > 0.4, retry triggered (max 1) |
| 8 | overstay + re-entry multi-hop | decompose→2 sub-qs with `depends_on=[0]` | topo order respected |
| 9 | Indonesian-language query | query in ID | decompose returns ID sub-qs, no crash |
| 10 | empty KB | vector store returns [] | returns empty evidence + fallback note |
| 11 | pure legal no KB match | vector store returns [] | composer emits fallback, no fabrication |
| 12 | circular dependency | decompose returns `[(0, deps=[1]), (1, deps=[0])]` | `_topo_sort` drops one edge, logs |
| 13 | max depth | decompose returns chain of 5 with depth=4 | collapsed to depth 3 |
| 14 | no-citation attempt | compose returns "The fee is 500000 IDR." (no brackets) | enforcer refuses or auto-attributes |
| 15 | cost ceiling ≤8 calls | run case 7 which triggers max retries | `llm_call_count <= 8` |

Total: 15 unit-tier tests. All must pass without a live model or network.

## Three Commits

1. `feat(visa-planner): scaffold visa package, types, B211 rewrite, pre-filter tests`
2. `feat(visa-planner): DAG executor, contradiction grader, core tests`
3. `feat(visa-planner): composer, citation enforcement, final tests, architecture doc`

Each commit leaves the tests green.

## Known Limitations

1. **Span offsets are approximate.** Vector store returns full-document chunks; we set `span_start=0, span_end=len(content)`. Real character-level spans would require a re-ingestion pipeline.
2. **Contradiction detection is heuristic.** Token overlap + number disagreement catches obvious cases but misses subtle semantic contradictions (e.g. "60 days" vs "two months").
3. **No live LLM tests in this delivery.** All tests use mocks. A `@pytest.mark.live` tier can be added when a shared test fixture for the Gemini gateway exists.
4. **Language detection is naive.** The planner does not explicitly detect language; it passes the raw query to `decompose()` and trusts the LLM to respond in the same language.
