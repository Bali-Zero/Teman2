# Test Gaps — Wave 1

**Source of truth:** `STATE_MACHINE.md` (this directory).
**Baseline:** `apps/backend-rag/backend/tests/unit/services/rag/agentic/` — the following files collectively own the coverage:

| File | Scope | Passing tests found |
|------|-------|---------------------|
| `test_orchestrator_coverage.py` | outer pipeline (process_query, stream_query, gates, init) | 37 pass, 7 skip |
| `test_orchestrator_core_coverage.py` | OrchestratorCore direct (faq/semantic cache, kg extract, workflow format) | — |
| `test_reasoning.py`, `test_reasoning_comprehensive.py`, `test_reasoning_coverage.py` | inner ReAct loop + evidence + stubs | — |
| `test_abstain_bypass_policy.py` | policy helpers (detect_*) | — |

Existing tests were enumerated by `grep -n '^class\|def test_'`. The gap audit below walks STATE_MACHINE.md transition IDs and marks each as covered / partial / missing.

---

## 1. Outer state machine (O1–O24)

| ID | Transition | Status | Existing test(s) | Gap |
|----|------------|--------|------------------|-----|
| O1 | PrepareContext → QueryPlanner | covered | `test_entity_extraction_with_entities`, `test_context_load_exception` | — |
| O2 | QueryPlanner → GatesCheck | **missing** | — | Neither shadow nor active mode is exercised. Whether `_USE_QUERY_PLANNER`, `_ENABLE_CRAG_ROUTER`, `_ENABLE_HYDE` flip behaviour is untested. (NB: `crag_decision` is currently dead code — see STATE_MACHINE §U2.) |
| O3 | GatesCheck → GateReturn | covered | `test_prompt_injection_gate`, `test_greeting_gate`, `test_casual_response_gate`, `test_identity_gate`, `test_clarification_gate`, `test_out_of_domain_gate` | — |
| O4 | GatesCheck → FAQCacheCheck | covered implicitly | `test_cache_hit`, `test_clarification_gate_low_confidence` | — |
| O5 | FAQCacheCheck → FAQReturn | **partial** | `test_orchestrator_core_coverage.py::TestCheckFaqCache::test_faq_cache_hit` exists but is *unit* on `check_faq_cache`, not an end-to-end `process_query_core` assertion. | No end-to-end test asserts `CoreResult.model_used == "faq_cache"` from `process_query_core`. |
| O6 | FAQCacheCheck error-path | covered | `test_faq_cache_exception_returns_none` | — |
| O7 | SemanticCacheCheck → SemanticReturn | covered | `test_cache_hit`, `test_orchestrator_core_coverage.py::TestCheckSemanticCache::test_cache_hit` | — |
| O8 | Semantic → MultiAgent | covered | `test_cache_exception` | — |
| O9 | MultiAgentCheck → MultiAgentReturn | **missing** | — | `MultiAgentCoordinator` path is untested. `requires_multi_agent(query)` branch never exercised in orchestrator tests. |
| O10 | MultiAgent failure/fallback | **missing** | — | Exception in `_multi_agent_coordinator.process` (line 796) → falls back to ReAct. Not tested. |
| O11 | SSRCheck → SSRReturn | **missing** | — | SpecializedServiceRouter early-return (autonomous_research / cross_oracle / client_journey) has zero tests. |
| O12 | SSRCheck → NLMSpeculative | covered implicitly | all tests that reach ReAct loop | — |
| O13 | NLMSpeculative → Routing | **partial** | No test verifies `nlm_task` lifecycle (created vs. skipped based on `resolve_notebook`). | Missing: NLM task cancellation on non-cautious evidence (O21). Missing: NLM task await on cautious evidence (O20). |
| O16 | ReAct raises | covered | `test_stream_fatal_error_handling` (stream path) | Sync path (`execute_react_loop` raise) propagates as `RuntimeError` — untested from orchestrator level. |
| O20 | NLMMerge cautious → Await | **missing** | — | `0.15 ≤ evidence ≤ 0.60 AND not trusted` → merge NLM enrichment into `result.nlm_enrichment`. No test. |
| O21 | NLMMerge cancel path | **missing** | — | `evidence_score` outside cautious range → `nlm_task.cancel()`. No test. |
| O24 | KGAutoExpansion gate (evidence > 0.6) | **missing** | — | Fire-and-forget path. Not tested. |

**Outer gaps summary:** 9 transitions missing (O2, O9, O10, O11, O13-partial, O16-sync, O20, O21, O24). Priority ranking: O20/O21 (NLM task lifecycle = invariant I-O4, load-bearing), O9/O11 (fast-path returns with distinct `model_used`), O16 (ReAct raise propagation).

---

## 2. Inner state machine (R1–R30)

| ID | Transition | Status | Existing test(s) | Gap |
|----|------------|--------|------------------|-----|
| R1 | LoopEntry → StepIncrement | covered | `test_reasoning_loop_simple`, `test_reasoning_loop_with_tools` | — |
| R2 | LoopEntry → exit (max_steps) | **partial** | `test_max_steps_reached` (tests natural exit with `max_steps=1` + no tool call → final answer set). | **Missing** explicit test: LLM keeps emitting tool calls past `max_steps` → loop exits, fallback path generates final_answer. Intent-type variance not covered. |
| R3 | SendMessage ok | covered | all happy-path tests | — |
| R4 | SendMessage raises (step 1) | **partial** | `test_llm_error_breaks_loop` covers ResourceExhausted on step 1 — asserts `current_step==1` but does NOT assert the downstream `final_answer` resolution. | **Missing:** assert final_answer is set via fallback (stub / Tier 1 / abstain) after step-1 raise. See STATE_MACHINE §U1. |
| R4b | SendMessage raises (step 2+) | **missing** | — | Step 2 raise after successful step 1 tool call — does the loop break cleanly? Partial state preserved? |
| R7 | HasToolCalls → ProcessResults | covered partially | `test_reasoning_loop_with_tools` (single tool) | **Missing:** parallel N>1 tool calls — correct `step_number` assignment (`current_step + i`), correct `current_step += len(tool_calls) - 1` bump (invariant I-R7). |
| R8 partial | Tool execution raises internally | **missing** | — | `_exec_tool_wrapper` captures exception → observation="Error: ...". Loop continues. Invariant I-R8 not tested. |
| R9 | QualityCheck → ContinueLoop (low quality + budget remaining) | **missing** | — | `quality_score < 0.15 AND current_step < max_steps` → `continue`. No test. |
| R11 | EarlyExit on vector_search | **missing** | — | `should_early_exit_on_vector_search` True → break. No orchestrator-level or reasoning-level test asserts the loop terminates early and `final_answer` is regenerated downstream. |
| R12 | No early-exit for COMPLEX_QUERY_INTENTS | **missing** | — | Intent `business_complex`/`business_strategic`/`devai_code` + vector_search hit → loop continues. Critical for KG+RAG composition. |
| R13 | NoToolCall + "Final Answer:" | covered | `test_no_tool_call_final_answer` | — |
| R14 | NoToolCall + not final + budget remaining → ThoughtStep | **missing** | — | LLM returns plain text without "Final Answer:" marker and budget left → append thought-only AgentStep, loop continues. |
| R16 | SetFinalAnswer → LoopBreak | covered | `test_no_tool_call_final_answer` | — |
| R20 | LLM has tools flips trusted=True | covered | `test_llm_with_tools_available_trusts_output` | — |
| R21 | LowEvidenceGate critical branch | covered | `test_low_evidence_critical_domain_strict_abstain` | — |
| R22 | LowEvidenceGate → Tier 1 regen | **partial** | no explicit test for non-critical low-evidence regeneration path (`build_tier1_prompt` flow). | **Missing:** asserts on tier1 regeneration happy path (final_answer mutated, model_name preserved, token accumulation). |
| R24 | Tier 1 regen raises → AbstainFallback | **missing** | — | Double-failure (main LLM ok, tier1 retry raises). State: `final_answer = stub("abstain")`. |
| R25 | CtxAnswer (score ≥ 0.15) | covered | `test_reasoning_loop_with_tools` (implicit) | — |
| R26 | CtxAbstain (critical + no answer + low score) | **missing** | — | No `final_answer` + `context_gathered` + critical + low score → hardcoded Italian abstain. |
| R27 | CtxTier1 (non-critical + no answer) | **missing** | — | Same as R26 but non-critical → Tier 1 regen path from `TRANSPARENCY_INSTRUCTION_FINAL`. |
| R28 | SkipRagAnswer (skip_rag + no context) | covered | `test_skip_rag_bypasses_evidence_check` | — |
| R29 | PipelineVerify fails → SelfCorrection | **missing** | — | `response_pipeline.process` returns `verification_score < 0.7` → rephrase prompt + re-send. |
| R30 | PipelineVerify raises → PostProcessFallback | **missing** | — | `ValueError | RuntimeError | KeyError` from pipeline → fallback to `post_process_response`. |

**Inner gaps summary:** 14 transitions missing or partial. Priority ranking: R2 (loop budget enforcement, invariant I-R1), R4/R4b (SendMessage raise — invariant I-R2 guarantee of final_answer), R7 (parallel tool counter — invariant I-R7), R8 (tool error isolation — invariant I-R8), R11/R12 (early-exit predicate — shapes latency), R26/R27 (no-answer branches).

---

## 3. Invariant-focused gaps

Tests that explicitly assert *invariants* (not just single branches). These are the highest-value gaps:

| Invariant | Description | Current coverage | Gap |
|-----------|-------------|------------------|-----|
| I-R1 | Loop always terminates within bounded iterations | **partial** — `test_max_steps_reached` (natural) | Missing: looped LLM-returns-tool-call forever, but max_steps cap fires. |
| I-R2 | `final_answer` is non-empty after `Done` state, ALL branches | **partial** | Missing: double-failure path (§U1). |
| I-R3 | `trusted_tools_used` monotonicity | **partial** | Three flippers tested individually, none tested together (e.g. pricing marker after tools-available already set True). |
| I-R7 | `current_step += len(tool_calls) - 1` after parallel N>1 | **missing** | No test constructs a 2+ parallel tool response. |
| I-R8 | Tool raise → `Error: …` observation, loop continues | **missing** | — |
| I-O4 | `nlm_task` is always awaited or cancelled | **missing** | — |

---

## 4. Wave 1 selection — 15 tests

Priority: invariants first (I-R1, I-R2, I-R7, I-R8, I-O4), then high-blast-radius transitions (R2, R4, R7, R8, R9, R11, R12, R22, R26/R27, R29, R30).

| # | Test name | Transition(s) / Invariant | Rationale |
|---|-----------|---------------------------|-----------|
| 1 | `test_loop_terminates_at_max_steps_with_tool_calls` | R2 + I-R1 | LLM keeps returning tool calls — loop exits at `max_steps`, `current_step == max_steps`, fallback produces final_answer. |
| 2 | `test_step1_llm_raise_resource_exhausted_yields_abstain` | R4 + I-R2 | Step-1 `ResourceExhausted` — downstream fallback must set `final_answer` (abstain/Tier1 stub). Covers §U1. |
| 3 | `test_step2_llm_raise_preserves_step1_context` | R4b | After step 1 tool call, step 2 raises — loop breaks with partial state; `context_gathered` from step 1 preserved. |
| 4 | `test_parallel_tool_calls_bumps_step_counter` | R7 + I-R7 | 2 parallel tool calls at step 1 → `current_step=2` after iteration; 2 `AgentStep`s appended. |
| 5 | `test_tool_execution_error_does_not_break_loop` | R8 + I-R8 | Tool raises → observation starts with `"Error: "`, loop continues (not break). |
| 6 | `test_low_quality_context_continue_loop` | R9 | Quality score patched <0.15 + budget → `continue`; second iteration fires. |
| 7 | `test_early_exit_on_strong_vector_search` | R11 | Vector search returns `len>500`, intent=simple → loop breaks at step 1. |
| 8 | `test_complex_intent_no_early_exit` | R12 | Same payload as #7 but `intent_type="business_complex"` → loop does NOT early-exit (proceeds to step 2 or max_steps). |
| 9 | `test_thought_only_step_continues_loop` | R14 | LLM returns plain text without "Final Answer:" and not at max_steps → thought AgentStep appended, next iteration fires. |
| 10 | `test_tier1_regeneration_on_non_critical_low_evidence` | R22 | Non-critical query + low evidence + trusted=False → Tier1 regen path calls `build_tier1_prompt` and mutates final_answer. |
| 11 | `test_tier1_regen_failure_falls_back_to_abstain_stub` | R24 + I-R2 | Main LLM produces answer, tier1 send_message raises → final_answer = localized abstain stub. |
| 12 | `test_no_context_critical_triggers_abstain_message` | R26 | No final_answer + no context + critical domain → Italian abstain text with "visti", "KITAS". |
| 13 | `test_no_context_noncritical_triggers_tier1_fallback` | R27 | Same as R26 but non-critical → tier1 path with `TRANSPARENCY_INSTRUCTION_NO_CONTEXT`. |
| 14 | `test_pipeline_verification_fail_triggers_self_correction` | R29 | `response_pipeline.process` returns `verification_score=0.5` → second `send_message` (rephrase) fires. |
| 15 | `test_pipeline_error_falls_back_to_post_process` | R30 | `response_pipeline.process` raises `ValueError` → `post_process_response` applied, no raise escapes. |

**Excluded from Wave 1** (require refactor or deeper integration):

- **O9/O10 (MultiAgent)** — needs orchestrator-level fixture with `MultiAgentCoordinator` mocked. Cleaner to add when we do full outer-pipeline parametrization (Wave 2).
- **O11 (SpecializedRouter)** — same rationale.
- **O20/O21 (NLM lifecycle)** — requires `resolve_notebook` mock + `nlm_enrichment_service.query` task fixture + assertions on task.done()/cancelled(). Worth a dedicated NLM wave.
- **I-O4** at orchestrator level — same as O20/O21.
- **O2 (QueryPlanner crag_decision)** — dead code at the moment (see §U2). Skip until wired.

Wave 1 keeps tests focused on `ReasoningEngine.execute_react_loop` (the core inner SM), where existing fixture patterns (`engine` + patched `calculate_evidence_score` / `detect_query_language` / `is_critical_domain` / `post_process_response`) let us write high-signal tests with small blast radius.

---

**End of Wave 1 gap analysis.** Proceed to implement tests in `test_orchestrator_state_machine_wave1.py`.
