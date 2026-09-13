ROLE: adversarial reviewer, READ-ONLY. You did not write this code. Keep the review NARROW: open only the files and line ranges named below plus what one hop of a named call needs. Do not modify any file, do not use the network, never print env values or secrets.

REPO: /Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-2-harness (HEAD bf5bea8360; candidate files are untracked). Code root apps/backend-rag.

THE SPEC OF RECORD (binding, accepted by the imperator as ruling I54): evidence/2026-09/agent-nuzantara-backend-rag-b2-2-harness-5936113c/brief.yml, keys `harness_contract` HC1-HC10 AND `harness_contract_amendment_I55` A55_1-A55_4 (the amendment wins on conflict), sha256 7a9bae8b3c6f88d47e7fea369d154412dac0040d1846d9367a171675dcace1df. It REPLACES the earlier "route through QueryRouter" design: the consumer is the WA bot package builder (wa_package_builder.py:520-640), not any router.

CANDIDATE BYTES (sha256):
A. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/retrieval_harness.py  7f31f597dfd2a7ee3a578270169c3739b1cb46049538ae611a40e4cc71ef5861
B. apps/backend-rag/backend/tests/unit/services/rag/test_b2_2_retrieval_harness.py  782e31ea1edcadedf27c58c72bff5aabb59c8b4e9aa984552232add78f928d18

OUT OF SCOPE (already dispositioned, do not review): measure_residual_cosines.py and its test (spent one-shot tool, executed bytes shipped verbatim), the frozen manifest, thresholds.

ATTACK (cite file:line you opened):
1. HC1/HC2 fidelity: does A search exactly QueryPlanner().plan(query).collections in the builder's order, and send the SAME Qdrant request SearchService.hybrid_search sends on its non-cached path (filter for user_level 1, limit 3, prefetch 9, dense branch fallback, score_kind presence rule, format_search_results args), then shape/sort/cap/redact/score as wa_package_builder.py does? Name any divergence that changes a score or a gate decision.
2. HC4: can any path in A reach an embedding, a generation, a send, a Redis get/set, QueryExpander, a reranker, or SearchService construction?
3. HC5: does anything at module scope of A (transitively) import backend.app.core.config? Does B prove it in a FRESH subprocess, including the bad-plan-file path?
4. HC6: any retrieval failure (absent collection, points_count 0, exception, zero hits across all planned collections) that still scores or writes; any way --execute runs without the plan file matching by sha AND by recomputation; any flag overriding the artifact pin.
5. HC7: are ALL guards installed in ONE fresh subprocess BEFORE importing A, on dotted paths that exist AND are the ones production calls (verify one hop each), with the guilt cases in that same subprocess?
6. HC8: can any exception text, URL, header or chunk text reach stderr/stdout/a file?
7. HC3/HC10: is translation_changes_query in the plan and embedding_divergent excluded from inference; does the report name relief-band cases and carry the support=None sentence verbatim?

OUTPUT (plain text). Write the VERDICT block FIRST, before any exploration narrative, and keep it as the final block too:
VERDICT: ACCEPT | ACCEPT-WITH-FINDINGS | BLOCK
ok: true   (only for ACCEPT or ACCEPT-WITH-FINDINGS with no BLOCKER)  |  ok: false
FINDINGS (numbered: severity BLOCKER/MAJOR/MINOR/NIT, file:line, failure, minimal cure)
NON-FINDINGS (one line each with file:line)
An unfinished review without a VERDICT line counts for nothing.

BUILDER DISCLOSURES (attack them, do not take them on trust):
8. HC5: backend/services/rag/agentic/__init__.py, backend/services/search/__init__.py and backend/services/ingestion/__init__.py import Settings-constructing modules eagerly, so A imports query_planner / keyword_translator through `_import_pure_leaf` (bare ModuleType stubs for not-yet-imported ancestor packages for one import, then every trace purged from sys.modules). Is it correct (same file executed, no stub residue, no corruption of a later real import, nothing half-imported left if the import raises)? The imperator accepted it as a DECLARED fragility; your job is to find where it actually breaks.
9. A55_1: the planner's first TAX/PROPERTY/PRICING collection 'nuzantara_general_hybrid' is unknown to CollectionManager; production silently substitutes legal_unified (search_service.py:526-532). A replicates that inline with a parity test reading those source lines. Is the replica exact (canonicalization order, the ValueError when legal_unified is also absent, duplicate searches)?
10. A55_2: qdrant_db.py hybrid_search RETURNS {'error': ...} on HTTP failure (:1363-1375) instead of raising. Does A hard-stop on every such return, and on the dense fallback inside hybrid_search (:1353-1362) mark score_kind_divergent and exclude it from inference?
