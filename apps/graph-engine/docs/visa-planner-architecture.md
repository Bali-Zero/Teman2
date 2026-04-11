# Visa Subgraph Multi-Step Planner — Architecture

**Entry point:** `nuzantara_graph.subgraphs.visa.make_visa_subgraph(services) -> async callable`

**Contract:** Invoked by the main graph as the `SUBGRAPH_VISA` node. Mutates
`GraphState` with `retrieved_documents`, `kg_entities`, `kg_relationships`,
`domain`, `current_node`, and adds a `visa_planner_trace` key for
introspection.

## StateGraph (ASCII)

```
           ┌───────────────────┐
           │   b211_rewrite    │  — regex replace + system note
           └─────────┬─────────┘
                     │
           ┌─────────▼─────────┐
           │     decompose     │  — 1 LLM call → list[SubQuestion]
           └─────────┬─────────┘
                     │
           ┌─────────▼─────────┐
           │    plan_execute   │  — topo loop over sub-questions
           │                   │    ↳ retrieve → fragment → critique
           │                   │    ↳ optional retry (max 1 / node)
           └─────────┬─────────┘
                     │
           ┌─────────▼─────────┐
           │      compose      │  — 1 LLM call → citation enforcer
           └─────────┬─────────┘
                     │
           ┌─────────▼─────────┐
           │     terminate     │  — packs into RetrievedDocument list
           └─────────┬─────────┘
                     │
                    END
```

## Termination Proof

Let `N = len(sub_questions)` after `decompose` truncates to ≤ 5.

1. `decompose` runs exactly once.
2. `plan_execute` iterates a topologically sorted list **once**. Each
   sub-question receives:
   - one retrieve call (free, no LLM)
   - one `compose_fragment` LLM call
   - optionally one retry LLM call if `contradiction_score > 0.4` AND
     `retries_used < 1`
3. `retries_used` is monotonically increasing and **never reset**.
4. `llm_call_count` is a globally monotonic counter with a hard cap
   (`max_llm_calls`, default 8). Any step that would exceed the cap is
   skipped.
5. `compose` runs exactly once.
6. The StateGraph edges form a straight line
   (`b211_rewrite → decompose → plan_execute → compose → END`). There is
   **no conditional loop-back edge**.

Total LLM calls ≤ `1 + N×2 + 1 = 2N + 2`. For `N=5` that is 12, clamped to
8 by the budget check.

∎ The graph halts for every input because: (a) the StateGraph is acyclic,
(b) the inner loop is a finite `for` over a finite topologically-sorted
list, (c) per-node retries are bounded by a monotonic counter, (d) the
global LLM budget is a hard ceiling.

## Failure Mode Table

| Failure | Detection | Recovery |
|---|---|---|
| Decompose LLM returns invalid JSON | `json.JSONDecodeError` / type check | Fall back to single sub-question = original query |
| Decompose LLM unavailable (no API key) | `ValueError` from `LLMGateway` | Same fallback |
| Decompose returns cyclic deps | `topo_sort` detects via idx ordering | Drop back-edge, log warning, continue |
| Decompose returns depth > max_depth | depth counter in `topo_sort` | Collapse to shallowest ancestor; re-root if needed |
| Decompose returns > max_sub_questions | length check | Truncate to first 5 |
| Vector store returns empty | `len(chunks) == 0` | Node evidence empty; composer emits fallback |
| Vector store raises | try/except in `_retrieve_chunks` | Empty chunks, log warning, continue |
| `contradiction_score > 0.4` | `ContradictionGrader.score()` | Re-plan that one sub-q once (if budget allows) |
| All nodes produce empty evidence | `compose()` sees no chunks | Returns `_SYSTEM_FALLBACK` |
| Composer LLM returns uncitable answer | `enforce_citations` linter | Drop uncitable sentences; fall back if all drop |
| LLM budget exhausted mid-execute | `llm_call_count >= max_llm_calls` | Skip remaining LLM calls, proceed with current evidence |
| B211 pre-filter matches | regex match | Rewrite query + inject system note chunk |
| LangGraph compile / ainvoke exception | try/except in `make_visa_subgraph` wrapper | Log error, return empty contract dict |

## Citation Enforcement Rationale

Every factual claim in a visa answer must be traceable to a document or a
system note. Otherwise:

1. **Hallucination risk.** Zantara has historically fabricated legal
   requirements (see `.claude/rules/cicatrix-scars.md`). Prompt
   instructions are unreliable; a deterministic post-processor is the only
   guarantee.
2. **User verification.** Users cannot verify claims against primary
   sources without stable `doc_id:start-end` anchors.
3. **Compliance.** Indonesian visa rules change monthly; wrong claims
   have legal consequences for clients.

The enforcer:

1. Splits the LLM output on sentence boundaries.
2. For each sentence, checks for a `[doc_id:start-end]` citation whose
   `doc_id` is in the set of known chunks.
3. If none, attempts auto-attribution via token overlap (≥ 50 % of
   significant tokens match one chunk's content).
4. If still none, replaces the sentence with
   `(unable to cite this claim; refer to the documents below)`.
5. If **every** sentence fails, returns
   `I cannot produce a fully-cited answer for this query. Please rephrase
   or contact support for visa assistance.`

## B211 Handling

The B211 visit visa no longer exists. A pre-filter rewrites any match to
`KITAS/ITAS or e-visa (C-series)` and injects a system note chunk with
`doc_id="SYSTEM:b211_rewrite"`. This guarantees the composer can cite the
rewrite without needing knowledge-base evidence.

## Known Limitations

1. **Span offsets are approximate.** We default to `(0, len(content))`
   because the vector store does not expose character-level offsets. Real
   spans would require pipeline re-ingestion.
2. **Contradiction detection is heuristic.** Number disagreement +
   negation polarity flip catches obvious cases. Subtle semantic
   contradictions (e.g. "60 days" vs "two months") are not detected.
3. **No live-model tier in initial delivery.** All tests mock
   `LLMGateway`. A `@pytest.mark.live` tier can be added when a gated
   test fixture for Gemini exists.
4. **Language detection is naive.** The planner relies on the LLM to
   mirror the input language.
