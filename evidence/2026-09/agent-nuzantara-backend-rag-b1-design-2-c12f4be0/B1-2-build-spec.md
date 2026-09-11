# B1.2 build spec — the nine tripwires, re-based by ADDITION

Mandate B1 (BLUE), PR B1.2. Base `0141b8130a192483a67865376281518ce7b69f2f` (origin/main at open,
2026-09-11T16:58Z). Input: `evidence/2026-09/agent-nuzantara-backend-rag-b1-score-contract-107e45b6/B1-2-inventory.md`
(on main) and rc1a commit `92f40801235cf33b32a8d71f241b6400cad64536` (never pushed; read by sha only).
Paths below are relative to `apps/backend-rag/backend/`.

## Decision (Dux): every variant is a DENSE-path fixture carrying a MEASURED cosine

The only real number that exists for these (query, context) texts is rc1a's `text-embedding-3-small`
cosine (prod `rag` container, 2026-09-10T18:03Z, one request, 20 texts, 216 prompt tokens). On the
hybrid path the value is a function of ranks in two lists, and no rank was ever measured for these
texts — inventing one would be exactly what D3 forbids. So each variant declares B1.1 inventory
row 2, `score_kind = dense_formatted`, `score_raw = cosine`, and the `score` the REAL formatter
produces from it.

Pre-measured by the Dux on the base, through `result_formatter.format_search_results(...,
score_kind=DENSE_FORMATTED)` and the real scorer: all nine variants PASS their unchanged assertions
(scorer output 0.0600 on every variant; originals 0.0400–0.0800).

## 1. Registry — `tests/fixtures/pipeline_score_fixtures.py` (Sonnet 5)

- `@dataclass(frozen=True) class DenseSourceSpec` with fields, all explicit per D3:
  `inventory_row: int` (=2) · `score_kind: str` (=`score_provenance.DENSE_FORMATTED`) ·
  `provider: str` (="openai") · `model: str` (="text-embedding-3-small") ·
  `measured_at: str` (="2026-09-10T18:03Z") · `measurement_ref: str` (="rc1a 92f40801235cf33b32a8d71f241b6400cad64536 measured_cosines.py") ·
  `qdrant_server: str` (="1.16.3") · `fallback_path: str` (="search_service dense branch / core/qdrant_db.py:1362 internal fallback") ·
  `fusion: None` (dense path has no fusion) · `lists: tuple[str, ...]` (=("dense",)) · `dense_rank0: int` ·
  `cosine: float` · `collection: str` (="kbli_2025_final_hybrid") · `primary_collection: None` ·
  `boosts: tuple[str, ...]` (=() — no boost applies) · `transform: str` (="distance = 1 - cosine; score = 1/(1+distance)") ·
  `rounding_digits: int` (=4) · `score: float` (literal, pinned) ·
  `carried_keys: Mapping[str, Any]` (non-score keys of the original source, verbatim, e.g. id/title) ·
  `unsourced_context_cosines: tuple[float, ...]` (=() unless stated).
- `PIPELINE_TRIPWIRE_FIXTURES: Final[Mapping[str, tuple[DenseSourceSpec, ...]]]` keyed by the ORIGINAL node id.
- `pipeline_sources(node_id: str) -> list[dict[str, Any]]`: a FRESH list, original list order, each
  `{**carried_keys, "score": score, "score_kind": score_kind, "score_raw": cosine}`. Unknown id → `KeyError`
  naming the registry (never a default).

| #   | original node id (relative to `tests/`)                                                                                                                 | original sources                                                                                                 | cosine              | dense_rank0   | score                   |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------- | ------------- | ----------------------- |
| 1   | `unit/services/rag/agentic/test_abstain_bypass_policy.py::TestTrustedToolDetection::test_successful_but_irrelevant_vector_hit_stays_below_abstain_gate` | `[{"score": 0.91}]`                                                                                              | 0.16                | 0             | 0.5435                  |
| 2   | `unit/services/rag/agentic/test_reasoning.py::TestCalculateEvidenceScore::test_no_keyword_overlap`                                                      | `[{"score": 0.9}]`                                                                                               | 0.04                | 0             | 0.5102                  |
| 3   | `services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::test_stop_words_only_query_keyword_ratio_zero`                               | `[{"score": 0.8}]`                                                                                               | 0.14                | 0             | 0.5376                  |
| 4   | `services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::test_short_words_only_yields_near_zero`                                      | `[{"score": 0.8}]`                                                                                               | 0.16                | 0             | 0.5435                  |
| 5   | `services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::test_entity_mismatch_company_vs_visa`                                        | `[{"score": 0.6}]`                                                                                               | 0.30                | 0             | 0.5882                  |
| 6   | `services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::test_semantic_penalty_not_applied_when_final_score_at_or_below_015`          | `[{"score": 0.35}]`                                                                                              | 0.20                | 0             | 0.5556                  |
| 7   | `services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::test_kitas_query_with_kbli_results_low_score`                                 | `[{"id": 1, "title": "KBLI 2025", "score": 0.85}, {"id": 2, "title": "Business Classification", "score": 0.75}]` | id1 0.35 · id2 0.51 | id1 1 · id2 0 | id1 0.6061 · id2 0.6711 |
| 8   | `services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::test_nonsense_query_zero_score`                                               | `[{"id": 1, "title": "Random Doc", "score": 0.8}]`                                                               | 0.22                | 0             | 0.5618                  |
| 9   | `services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::test_entity_type_mismatch_detection`                                          | `[{"id": 1, "score": 0.9}]`                                                                                      | 0.40 (top chunk)    | 0             | 0.625                   |

Row 7: list order is the ORIGINAL order (inputs stay byte-identical); ranks are declared per source.
Row 9: one source, as in the original; it is the top dense hit (max of the two measured chunk cosines);
the other chunk's cosine is `unsourced_context_cosines=(0.32,)`.

Module docstring (short): what the registry is, that values are measured-not-invented, that a kind is
declared and never inferred from magnitude, and that originals are PRESERVED beside the variants (D3/D5).

## 2. Variants — beside each original (GLM 5.2 prepares, Dux verifies)

In the same file and class, immediately after the original function, add `<original_name>_pipeline_variant`:

- same decorators as the original; a one-line docstring;
- first body line: `from backend.tests.fixtures.pipeline_score_fixtures import pipeline_sources` (local import,
  so every touched test file diff is +N/-0);
- one comment line: `# B1.1 inventory row 2 (dense_formatted): PIPELINE_TRIPWIRE_FIXTURES[<node id>]`;
- the rest of the body byte-identical to the original EXCEPT the sources literal, replaced by
  `pipeline_sources("<node id>")`. Every `assert` statement, message and `print` identical.

## 3. Guard — `tests/unit/services/rag/test_tripwire_pipeline_variants_guard.py` (Sonnet 5)

- G1: for every registry key, every dict from `pipeline_sources` has `score_kind` in
  `score_provenance.SCORE_KINDS` and not `UNKNOWN`, a float `score_raw`, a float `score`.
- G2: every spec's pinned `score`, `score_kind` and `score_raw` equal what
  `format_search_results({"ids","documents","metadatas","distances":[1-cosine],"scores":[cosine]},
spec.collection, score_kind=spec.score_kind)` returns — the fixture is pinned to the live transform.
- G3: registry key set == exactly the nine node ids above; each names a function that exists (AST).
- G4: for each original, its `_pipeline_variant` exists in the same class; AST inside the variant finds
  a `pipeline_sources("<its node id>")` call and NO dict literal carrying a `"score"` key without a
  `"score_kind"` constant from `SCORE_KINDS` (a re-introduced unlabelled value goes red).
- G5: the `assert` statements of each variant equal its original's (`ast.dump` comparison, in order).
- Parse files from the test tree relative to the guard's own `__file__`; no network, no app init.

## 4. Proofs the PR body carries

- Before/after pytest counts on the four touched files + guard (`PYTHONPATH=. SKIP_SENTRY_INIT=1
.venv/bin/python -m pytest <files>` from `apps/backend-rag`), both green.
- The assertion-line diff (scratch script, output only) — empty.
- Guard RED under two mutations in a throwaway copy restored with `cp` (never `git checkout --`):
  (a) drop `score_kind` from one registry entry → G1/G2 red; (b) add `{"score": 0.9}` inside a variant → G4 red.
- Innocence: the six files of B1 §4 at their origin/main counts.
- `git diff --numstat` on the four existing test files: deletions = 0.

## Fence

Writable: the registry, the guard, the four existing tripwire test files (additions only), this evidence
dir. Nothing under `backend/services/**`, `backend/core/**`, no corner, no `zantara_core.py`, no
`wa_codex_leg.py`, no migration, no network, no embedding/generation call.
