# B1.1 build spec — the score contract, pinned end to end

Base sha `1d726045c9`. Root for relative paths: `apps/backend-rag/backend/`.
Every file:line below was re-read on this base; the vocabulary module
`core/score_provenance.py` is ALREADY WRITTEN and is the contract's single home.

## The two design rulings the implementer must not relitigate

**R1 — provenance is DECLARED by the caller that knows, never derived from `search_type`.**
`core/qdrant_db.py` emits `"search_type": "hybrid_rrf"` on the hybrid path (`:1338`, `:1373`,
`:1389`) and emits NO `search_type` at all from the dense `search()` returns (`:519`, `:597`,
`:608`), so `services/search/search_service.py:1142`'s
`raw_results.get("search_type", "hybrid_rrf")` labels a dense fallback as hybrid. That is a real
defect and B1 does NOT fix it: `search_type` is a served field (it is the label of the
`rag_vector_search` metric family, `app/metrics.py:852`, and it is returned in the response and
written to the cache), so changing its value is a served-behaviour change and belongs to B2. It is
recorded as an inventory row and as a declared residual. Instead, `search_service` — which knows
from its own branch which call it made — PASSES the kind down. A wrong `search_type` therefore can
no longer make a wrong `score_kind`.

**R2 — provenance lives INSIDE the sealed bytes, and the digest changes.**
`_package_hash` (`services/rag/agentic/wa_package_builder.py:434-453`) hashes `chunks` as raw
dicts with no per-field allowlist, and `_canonical_wire` (`:424-431`) is `json.dumps(sort_keys=True)`
over whatever it is given, so a per-chunk `score_kind` enters both `package_hash` and `wire_text()`
automatically. That is the objective, not a side effect: B1's §1 goal is that "the sealed package
proves the scorer receives the same provenance whose bytes were sealed". `__post_init__`
(`:153-170`) re-verifies hash==wire, so the two stay self-consistent by construction.
**The digest therefore CHANGES, and the PR says so in plain words.** The STOP condition attached to
it (`B1-design.md` §4(d), "a digest change with rows in flight is a STOP") is measured and NOT
triggered: `wa_outbox` holds only terminal rows, 241 `failed` + 179 `done`, newest
2026-09-01 09:27:53Z, zero `pending`/`generating` — receipt in `measured-fusion-table.md`.
**`evidence_inputs` is NOT touched**, deliberately: `tests/unit/services/test_wa_codex_leg.py:159`
and `:1302` pin its exact JSON substring in the wire, and B2 can read the kinds off the chunks.
`context_length` is `len(chunks)` at `:601` (the file's only occurrence) and is key-agnostic, so it
does not move.

## The writers (additive only — no field renamed or removed, no numeric value changed)

| #   | File:line                                                                                                              | Value today                                         | Declared kind                                            | `score_raw`                                                                          |
| --- | ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| 1   | `services/misc/result_formatter.py:89` via `search_service.py:1158` (hybrid branch)                                    | `1/(1+distance)` over server RRF                    | `hybrid_rrf_formatted`                                   | the fusion output, i.e. `raw_results["scores"][i]`                                   |
| 2   | same formatter via the dense branch (`search_service.py:1143-1154`) and the internal fallback `core/qdrant_db.py:1362` | `1/(1+distance)` over a cosine                      | `dense_formatted`                                        | the cosine, i.e. `raw_results["scores"][i]`                                          |
| 3   | `core/reranker.py:169-180` and `services/rag/reranker.py:345-352`                                                      | reranker `relevance_score` overwrites `score`       | `reranked`                                               | the value it replaced (the same number those writers already keep as `vector_score`) |
| 4   | `services/rag/agentic/wa_package_builder.py:529`                                                                       | literal `1.0`                                       | `curated_synthetic`                                      | `None` — nothing was consumed                                                        |
| 5   | `services/search/search_service.py:1100-1103` (cache hit)                                                              | whatever was cached, pre-formatted                  | `unknown` when the entry predates this PR                | `None`                                                                               |
| 6   | `services/rag/agentic/tools.py:279-288` (source projection)                                                            | passes `score` through, drops the rest              | carries kinds 1-5 through unchanged; `unknown` if absent | carried through                                                                      |
| 7   | `services/rag/agentic/wa_package_builder.py:289` then `:594-598`                                                       | chunk `score`, then projected to `[{"score": ...}]` | carries through; the PROJECTION must keep it             | carried through                                                                      |

## The two paths that are DOCUMENTED, not edited

| Path                | file:line                                                                | What it actually is                                                                                                                                                                                                                                                                                                                             |
| ------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Trusted-tool bypass | `services/rag/agentic/_reasoning_evidence.py:365-371`, constant at `:40` | `compute_evidence_score` returns a flat `0.85` and never touches `sources`. It is a WHOLE-PACKAGE label, not a per-source score. Two production call sites only, `services/rag/agentic/reasoning.py:657` and `:1375`, both assigning `state.evidence_score`. Kind: `trusted_tool_bypass`. B1 labels the constant in place and changes no value. |
| FAQ fast path       | `services/rag/agentic/orchestrator_core.py:428-441`                      | Returns `sources=[{"type": "faq_cache", ...}]` with **no `score` key at all**, and sets no `evidence_score` — so `CoreResult.evidence_score` falls to the Pydantic default `0.0` (`schema.py:91`). Not a numeric-score writer. Contract only.                                                                                                   |
| KG fast path        | `services/rag/agentic/orchestrator_core.py:1084-1103`                    | First source has no `score`; per-evidence entries splat `**ev` from outside this file, so a `score` MAY appear and its meaning is undeclared. Also falls to the `0.0` default. Kind for anything that does carry a number: `kg_entity`. Contract only; the splat is a declared unknown, recorded, not guessed.                                  |

## Crossing tests (new file `tests/unit/services/rag/agentic/test_score_contract_crossing.py`)

Each asserts the EXACT numeric `score` and the `score_kind` that arrive at the scorer, crossing
producer → formatter/reranker → source projection → package construction → DLP/capping →
canonical serialization → scorer input:

1. rank-1 hybrid, in ONE list → fusion `0.5` → formatted `0.6667`, kind `hybrid_rrf_formatted`.
2. rank-1 hybrid, in BOTH lists → fusion `1.0` → formatted `1.0`, same kind.
3. rank-5 hybrid (`rank0=4`) in one list → fusion `0.1667` → formatted `0.5455`, same kind.
   (All three numbers are taken from the MEASURED table, not from a local re-derivation.)
4. dense fallback at cosine `0.0` / `0.5` / `0.9` → formatted `0.5` / `0.6667` / `0.9091`,
   kind `dense_formatted`.
5. a reranked source → kind `reranked`, `score_raw` == the pre-rerank value == `vector_score`.
6. curated synthetic `1.0` → kind `curated_synthetic`, `score_raw` absent.
7. one collection boost applied → the boosted number is unchanged from today AND the kind survives
   the boost (a boost does not change what the number IS).
8. an `unknown` cache hit → a cached entry with no `score_kind` reads back as `unknown`.
9. **NEGATIVE, must fail on origin/main:** a dense fallback whose `raw_results` carries no
   `search_type` is labelled `dense_formatted` even though `search_service.py:1142` still calls it
   `"hybrid_rrf"` — the two disagree ON PURPOSE and the test pins the disagreement, because the
   kind comes from the caller and the `search_type` lie is B2's to fix.
10. **PROJECTION test (staff-room requirement 2):** the list handed to
    `calculate_evidence_score` at `wa_package_builder.py:594-598` carries `score_kind` on every
    element. This is the test that fails if anyone re-narrows the projection to `{"score": ...}`.
11. A printed real package from the fixture path shows every source with its kind (PR body).

## Innocence

The six files at their origin/main counts or better: `test_evidence_cross_language.py`,
`test_evidence_scoring_abstain.py`, `test_wa_package_builder.py`, `test_wa_greeting.py`,
`test_curated_qa_government_fee_gate.py`, `test_wa_finalize.py`. Plus the widest scorer suites,
which this PR must not move: `tests/services/rag/agentic/test_reasoning_utils.py` (84),
`tests/unit/services/rag/agentic/test_reasoning.py` (37),
`tests/services/rag/test_confidence_scoring.py` (21). Any test that pins the WIRE or the
`package_hash` by literal value is expected to move, and every such move is listed in the PR body
with the reason "digest change, declared, no rows in flight".
