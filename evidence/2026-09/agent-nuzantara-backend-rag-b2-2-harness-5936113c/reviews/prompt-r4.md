ROLE: adversarial reviewer, READ-ONLY. You did not write this code. Do not modify any file, do not use the network, never print env values or secrets.

CONTEXT BUDGET IS THE FAILURE MODE: your previous attempt on these files hit the context rollover at 166K tokens while reading the 1650-line test file and produced NO verdict, which counts for nothing. So: NEVER read a file whole. Use ONLY the line ranges below (sed -n 'a,bp'), at most ~250 lines per read. Do NOT run pytest. After reading A's ranges, WRITE A PROVISIONAL VERDICT BLOCK before opening B; update it at the end.

REPO: /Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-2-harness (HEAD bf5bea8360; candidate files untracked). Code root apps/backend-rag.

SPEC OF RECORD (ruling I54 + I55): evidence/2026-09/agent-nuzantara-backend-rag-b2-2-harness-5936113c/brief.yml keys `harness_contract` (HC1-HC10) and `harness_contract_amendment_I55` (A55_1-A55_4; amendment wins), sha256 7a9bae8b3c6f88d47e7fea369d154412dac0040d1846d9367a171675dcace1df. Consumer = the WA bot package builder, not any router.

CANDIDATE BYTES (sha256):
A. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/retrieval_harness.py  2a2024817db48460c76f41c03fa945d041c1acd57a7a5e2f842f88a20159172b
B. apps/backend-rag/backend/tests/unit/services/rag/test_b2_2_retrieval_harness.py  37ba990fab740f564657b29e431f2960733c6cee9ce01c6071e6ad2a9b845819

READ MAP. A: 171-300 (_import_pure_leaf, local guard/named-vector helpers, bm25 presence), 399-450 (RetrievalError, _safe_exception_summary), 583-700 (_plan_for_query, filter, _cap_chunks), 697-945 (run_query), 1042-1160 (build_report, _require_numeric), 1261-1410 (main). B: 741-1003 (A55 tests), 1028-1104 (HC8), 1135-1245 (HC5 + HC7 subprocess script), 1347-1496 (plan-file gate). One-hop production, only if needed: wa_package_builder.py 50-100, 236-300, 510-640; search_service.py 247-300, 452-540, 1107-1257; core/qdrant_db.py 1258-1380; services/rag/agentic/query_planner.py 240-265.

OUT OF SCOPE: measure_residual_cosines.py and its test, the manifest, thresholds.

ALREADY REVIEWED by another seat (tp1-qwen3.8-max, ACCEPT-WITH-FINDINGS on the previous sha): its two MINORs (empty-text hits kept; chunk carried the resolved instead of the planned collection name) are cured in these bytes at A run_query's hit loop, with a guilt-tested test in B TestA55CollectionResolution. Verify the cure, do not re-derive the rest from scratch.

SETTLE THESE (cite file:line):
1. HC1/HC2/A55_1: collections planned/deduped/resolved/substituted exactly as production (canonicalize, get_collection None -> legal_unified, ValueError-equivalent hard stop when legal_unified is absent, duplicate searches kept); the Qdrant request (filter incl. current-law guard, limit 3, prefetch 9, dense branch, score_kind presence rule, formatter args); shaping/sort/_cap_chunks/redaction/scorer args identical to the builder. Is the local _cap_chunks / _requires_current_law_guard / _uses_named_vectors replica exact and pinned?
2. A55_2 / HC6: every returned {'error': ...} and every exception hard-stops before scoring or writing; in-hybrid dense fallback marks score_kind_divergent and is excluded from inference.
3. HC8: RetrievalError messages interpolate query_key and collection names — is anything interpolated that is NOT harness-generated (exception text, URL, header, chunk text)? query_key/collection come from the synthetic artifact and the planner; say whether that meets HC8's intent or is a finding.
4. HC5: _import_pure_leaf — same file executed, no stub residue in sys.modules, a real later import unaffected, and what happens if the leaf import RAISES (stub left behind?). Does B's fresh-subprocess test prove config absent through build_plan and a refused --execute?
5. HC7: all guards installed in ONE fresh subprocess before importing A, on dotted paths that exist and are production's, guilt cases in that same subprocess.
6. F3: --execute refuses before importing CollectionManager unless plan-file bytes hash AND plan equals recomputation.

OUTPUT (plain text):
VERDICT: ACCEPT | ACCEPT-WITH-FINDINGS | BLOCK
ok: true   (only for ACCEPT or ACCEPT-WITH-FINDINGS with no BLOCKER)  |  ok: false
FINDINGS (numbered: BLOCKER/MAJOR/MINOR/NIT, file:line, failure, minimal cure)
NON-FINDINGS (one line each, file:line)
The final block must repeat the VERDICT and ok lines. An unfinished review without a VERDICT line counts for nothing.
