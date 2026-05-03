# Wave 3 Notes — Orchestrator Streaming + Sub-Machines

**Branch:** `session/orchestrator-streaming`
**Baseline:** commit `d4fa14115` (Wave 2 PR #179 merged on `main`)
**Scope:** Full streaming ReAct loop state machine + QueryGates sub-gate decomposition + ResponsePipeline sub-machine + O13 NLM content merge closure.

---

## Outcome summary

| Part | Area | Doc deliverable | Tests added | Source LOC changed |
|------|------|-----------------|-------------|--------------------|
| P1 | `execute_react_loop_stream` state machine | `docs/audits/2026-04-22-orchestrator-state-machine.md` §5 (new) | 15 stream regression | 0 |
| P2 | `QueryGates.run_all_gates` 6 sub-gates | `QUERY_GATES.md` (new, subdir) | 12 composite | 0 |
| P3 | `ResponsePipeline.process` 4 stages | `RESPONSE_PIPELINE.md` (new, subdir) | 9 stage | 0 |
| P4 | O13 NLM content merge closure | (covered in docs/audits/2026-04-22-orchestrator-state-machine.md) | 4 merge | 0 |
| **Total** | | **3 new docs + 1 STATE_MACHINE update** | **40 tests** | **0 production LOC** |

Target was 22–34 tests: **delivered 40 tests**. All 40 pass; wave 1 + 2 + 3 cross-regression = 107 pass / 0 fail.

No production code was modified: Wave 3 is **documentation + regression tests only**. Wave 4 candidates (see below) include deliberate source changes to fix drift flagged in §5.4 of docs/audits/2026-04-22-orchestrator-state-machine.md.

---

## Part 1 — Streaming ReAct loop state machine (P1)

**File delivered:** update to `docs/audits/2026-04-22-orchestrator-state-machine.md` §5 ("Streaming ReAct loop").

Wave 1 had diagrammed only `execute_react_loop` (sync) fully; `execute_react_loop_stream` appeared as a single divergence flag (§U5). Wave 2 unified the shared flipper pair via `apply_shared_trusted_flippers`. Wave 3 now fully maps the streaming path.

### New sections in docs/audits/2026-04-22-orchestrator-state-machine.md

- **§5.1 Mermaid stateDiagram-v2** — full streaming loop including yield protocol, single-tool-per-step semantics, CRM early-exit, context-marker flippers, token chunking, stub filter, pipeline fallback.
- **§5.2 Transitions table S1..S29** — each transition keyed to its sync counterpart in §2 or marked "new". 29 stream-only or diverging transitions identified.
- **§5.3 Invariants I-S1..I-S9** — 9 invariants specific to the streaming path:
  - I-S1 yield ordering
  - I-S2 single tool per step
  - I-S3 tool raise propagates (vs sync I-R8 capture)
  - I-S4 CRM in-loop trusted flip
  - I-S5 stream-only context widening
  - I-S6 stub key drift (`abstain` vs sync `abstain_detailed`)
  - I-S7 hardcoded Italian leak in §S23
  - I-S8 20-char token chunk size
  - I-S9 generator closure
- **§5.4 Sync↔stream drift summary** — 8-row table of drifts classified by severity/fixability for Wave 4 planning.

### Test deliverable (P1)

File: `test_orchestrator_state_machine_wave3_stream.py` — **15 tests** (target 8-12). Organized in 11 groups, each keyed to a transition ID or streaming invariant. Highlights:

- **Group 3** (CRM early-exit) and **Group 5** (stream-only context widening) are the first direct regression tests for the I-S4 and I-S5 streaming-only behaviors — previously documented but not tested.
- **Group 6** (stub key drift) is a **tripwire**: if a future refactor unifies `abstain` / `abstain_detailed`, the assertion fails and the change must be deliberate.
- **Group 9** (images step 1 only) and **Group 8** (step 2+ prompt prefix) lock previously undocumented streaming-only behaviors that could silently regress during prompt engineering work.

---

## Part 2 — QueryGates sub-gate decomposition (P2)

**File delivered:** `apps/backend-rag/backend/tests/unit/services/rag/agentic/QUERY_GATES.md` (new).

### Content

- **§1 Composite Mermaid diagram** — 6 gates evaluated in order (security → greeting → casual → identity → clarification → out_of_domain → fallthrough).
- **§2 Per-gate table** — for each of G1..G6 + FT: trigger condition, side effect, return type.
- **§2.1 Upstream predicate table** — maps each gate to its source function/module.
- **§3 Composite execution order** — code snippet of `run_all_gates` + 5 invariants I-G1..I-G5:
  - I-G1 security priority
  - I-G2 short-circuit (at most one gate fires)
  - I-G3 clarification opt-in (history argument, not service presence)
  - I-G4 fallthrough shape (triggered=False)
  - I-G5 gate_result_to_core_result mapping table
- **§4 Error propagation** — no try/except inside `run_all_gates`; tripwire documented.

### Test deliverable (P2)

File: `test_query_gates_composite.py` — **12 tests** (target 6-10). 7 groups covering each invariant explicitly + error-propagation tripwire. Highlights:

- **Group 3** (clarification opt-in) — 3 tests: missing history, missing service, below-threshold. These close the CoreResult mapping for the most complex sub-gate.
- **Group 6** (gate_result_to_core_result mapping) — 3 tests lock the I-G5 mapping explicitly (security / clarification / greeting). Any new gate category that skews the verification_status values will fail one of these tests.

---

## Part 3 — ResponsePipeline sub-machine (P3)

**File delivered:** `apps/backend-rag/backend/tests/unit/services/rag/agentic/RESPONSE_PIPELINE.md` (new).

### Content

- **§1 Composite Mermaid diagram** — 4-stage default pipeline (Verification → PostProcessing → Citation → Format) with intra-stage error paths and outer `(failed)` marker behavior.
- **§2 Per-stage tables** — for each `PipelineStage`: trigger, skip condition, happy path, error path, output fields.
- **§3 Pipeline-level invariants I-P1..I-P7**:
  - I-P1 None input raises
  - I-P2 chain continues on stage failure
  - I-P3 stages_completed monotonic
  - I-P4 default cardinality + order
  - I-P5 response shape guarantee
  - I-P6 short-response verification_score=1.0 quirk
  - I-P7 citation score float coercion

### Test deliverable (P3)

File: `test_response_pipeline_stages.py` — **9 tests** (target 5-8). 7 groups:

- **Group 4** (CitationStage) — 2 tests covering the non-trivial dedupe+sort+trim behavior with score coercion.
- **Group 6** (chain continues on failure) — custom `_RaisingStage` + `_MarkerStage` subclasses prove I-P2 + I-P3 together: a mid-chain raise doesn't abort, the next stage still runs, and `stages_completed` faithfully records the `(failed)` marker.

---

## Part 4 — O13 NLM content merge paths (P4)

**File delivered:** `test_orchestrator_state_machine_wave3_nlm.py` — **4 tests** (target 3-4).

Wave 2 closed O13-partial (task creation + skip). Wave 3 closes the merge content paths:

- **Content overlap** — LLM and NLM answer both mention "KITAS" / "12 months"; behavior lock: merge only attaches `nlm_enrichment`, does NOT rewrite `result.answer`.
- **Conflicting facts** — LLM says 6 months, NLM says 12 months; tripwire: no arbitration layer is present (both claims coexist in the response).
- **Merge timeout** — `asyncio.wait_for(nlm_task, timeout=3.0)` raises `TimeoutError` → `nlm_result=None`, `result.nlm_enrichment=None`, LLM answer survives. Exercises line 1012 (`except (asyncio.TimeoutError, asyncio.CancelledError)`).
- **Cached result bypass** — locks the single-invocation guarantee: NLM service `query` invoked exactly once on the merge path, not duplicated between speculative + merge call sites.

### Why these 4 (not more)

The NLM merge block in `orchestrator_core.py:1000-1060` has three meaningful entry conditions:
1. cautious + cache hit → attach from cache (the "fast" merge)
2. cautious + task only → `wait_for` with 3s timeout → attach or timeout
3. non-cautious + task pending → cancel + `I-O4` closed in Wave 2

The 4 new tests cover the distinguishable semantic outcomes **content-wise** (overlap / conflict / timeout / call-count). Additional tests on the merge branch (e.g. `asyncio.CancelledError` during `wait_for`) duplicate Wave 2's `TestNLMMergeLifecycle::test_non_cautious_evidence_cancels_nlm_task`.

---

## Test results

| Suite | Pre-Wave 3 | Post-Wave 3 | Delta |
|-------|-----------|-------------|-------|
| `test_orchestrator_state_machine_wave1.py` | 15 pass | 15 pass | 0 |
| `test_orchestrator_state_machine_wave2.py` | 16 pass | 16 pass | 0 |
| `test_abstain_bypass_policy.py` | 36 pass | 36 pass | 0 |
| `test_orchestrator_state_machine_wave3_stream.py` | — | **15 pass** | +15 |
| `test_orchestrator_state_machine_wave3_nlm.py` | — | **4 pass** | +4 |
| `test_query_gates_composite.py` | — | **12 pass** | +12 |
| `test_response_pipeline_stages.py` | — | **9 pass** | +9 |
| **Total Wave 3** | — | **40 new tests** | **+40, 0 regressions** |

Full wave 1 + 2 + 3 suite: **107 pass / 0 fail**.

---

## Reality check

- **State machine streaming — completeness:** 29 transitions (S1-S29) identified, diagrammed, and keyed to sync counterparts where applicable. 9 streaming invariants (I-S1-I-S9) documented. Drift table (§5.4) with 8 rows for Wave 4. ✅
- **QueryGates — sub-gate documentation / testing:** 6 sub-gates + FT fallthrough documented (G1-G6 + FT). 5 invariants (I-G1-I-G5) explicit. **12 tests** covering each sub-gate's trigger/skip behavior, composite short-circuit, CoreResult mapping, and raise propagation. ✅
- **response_pipeline — path testing:** 4 stages (Verification / PostProcessing / Citation / Format) documented. 7 invariants (I-P1-I-P7). **9 tests** covering each stage's happy + skip + error path + pipeline-level None-raise + chain-continues-on-failure invariant. ✅
- **O13 Wave 3 closure:** Yes. Remaining merge content paths (overlap / conflict / timeout / cache-bypass) all covered. 4 tests. The Wave 2 NLM lifecycle tests (create / skip / await / cancel) plus Wave 3's 4 content tests close O13 completely. ✅

### Where Wave 3 fell short of the ideal

- **Stream-path I-S6/I-S7 drift**: locked by tripwires but not fixed. The `"abstain"` vs `"abstain_detailed"` stub-key drift (I-S6) and the hardcoded-Italian leak in §S23 (I-S7) are documented as Wave 4 candidates. Fixing them requires a behavior-change PR with i18n audit, not just tests.
- **QueryGates error propagation**: we locked the "raise propagates" contract via a tripwire (Group 7). If a future refactor decides to graceful-degrade, that test will fail deliberately. We did NOT add a `run_all_gates` wrapper to recover gracefully — out of scope.
- **ResponsePipeline default-pipeline in-context test**: tests exercise each stage in isolation + `_RaisingStage` custom chain. They do NOT run the default pipeline end-to-end with a real LLM response + sources. That's the smoke test level; unit-level stage contracts are locked.

---

## Wave 4 candidates

Not implemented in Wave 3 but natural follow-ups, ranked by blast radius:

1. **Fix I-S7 hardcoded Italian leak** (stream §S23) — replace the inline Italian string with `_get_localized_stub("abstain_no_context", language)` and add the key to every stub file. User-visible correctness fix for non-Italian streaming users. Behavior change, needs 1 source commit + stub file updates.
2. **Unify I-S6 stub key drift** (`abstain` vs `abstain_detailed`) — pick one semantic ("we have an answer but we override" vs "we need to abstain entirely") and use the same key in both sync and stream for the same branch. Tripwire breaks intentionally; update accordingly.
3. **Grading gates ACTIVE integration** — §U4 clamp behavior in active mode is unit-tested only. No integration test runs `_ENABLE_GRADING_GATES=True` through `process_query_core` and asserts the clamp affects downstream NLM / KG decisions.
4. **QueryPlanner shadow vs active metrics** — the `planner_match_rate` metric and the active-mode logging path still lack dedicated tests (Wave 2 added O2 active-mode call-chain test only).
5. **FAQ / semantic cache end-to-end** — O5/O7 assert on unit methods; an `assert result.model_used == "faq_cache"` through `process_query_core` would close the gap.
6. **ARCH-4 cross-notebook correlator** — `resolve_multi_notebook` ≥2 match branch spawns a `cross_notebook_correlator` task; not tested.
7. **I-O5 monotonic tool counter** — no test asserts that `tool_execution_counter["count"]` is monotonic across an entire pipeline invocation.
8. **Refactor streaming to reduce I-S3 surprise** — either wrap streaming `execute_tool` in a try/except (matching sync I-R8) or explicitly document that streaming callers MUST catch generator-level exceptions. Currently silent.

---

**End Wave 3 notes.** Next PR: `session/orchestrator-i18n-wave4` if drift fixes are prioritized, or `session/orchestrator-integration-wave4` for grading-gates / cache E2E.
