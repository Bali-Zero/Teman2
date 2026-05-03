# Orchestrator Core — State Machine (Wave 1)

**Scope:** `backend/services/rag/agentic/orchestrator_core.py` (1,499 LOC) + `reasoning.py` (1,408 LOC).
**Generated:** 2026-04-22, session/orchestrator-audit.
**Method:** Manual read of `process_query_core`, `execute_react_loop`, `execute_react_loop_stream`, policy helpers (`_reasoning_policy.py`, `_reasoning_loop_helpers.py`, `_reasoning_evidence.py`). Mermaid stateDiagram-v2 dialect.

The system has two nested state machines:

1. **Orchestrator pipeline** (outer) — linear pipeline from query arrival to `CoreResult` emission, with multiple early-return gates. Lives in `OrchestratorCore.process_query_core`.
2. **ReAct loop** (inner) — multi-step reasoning loop with tool calls. Lives in `ReasoningEngine.execute_react_loop[_stream]`.

---

## 1. Outer state machine — `process_query_core`

### 1.1 Mermaid diagram

```mermaid
stateDiagram-v2
    [*] --> PrepareContext

    PrepareContext : prepare_query_context\n(parallel: context load + entity/KG)

    PrepareContext --> QueryPlanner : ok

    QueryPlanner : QueryPlanner\n(active | shadow | off)
    QueryPlanner --> GatesCheck : plan ready\n(or skipped)

    GatesCheck : query_gates.run_all_gates\n(security / greeting / identity /\nclarification / out-of-domain)
    GatesCheck --> GateReturn : gate_result.triggered
    GateReturn : emit CoreResult(model=*-gate)\nverification=blocked|passed|skipped
    GateReturn --> [*]

    GatesCheck --> FAQCacheCheck : not triggered
    FAQCacheCheck : faq_cache.get(query)\n(exact match, <1ms)
    FAQCacheCheck --> FAQReturn : cache hit
    FAQReturn : emit CoreResult(model=faq_cache)
    FAQReturn --> [*]

    FAQCacheCheck --> SemanticCacheCheck : miss / error
    SemanticCacheCheck : semantic_cache.get_cached_result\n(+ query_embedding)
    SemanticCacheCheck --> SemanticReturn : cache hit
    SemanticReturn : emit CoreResult(model=cache,\ncache_hit=true)
    SemanticReturn --> [*]

    SemanticCacheCheck --> MultiAgentCheck : miss / error
    MultiAgentCheck : requires_multi_agent(query)?
    MultiAgentCheck --> MultiAgentReturn : yes + final_answer
    MultiAgentReturn : emit CoreResult(\nmodel=multi-agent-coordinator)
    MultiAgentReturn --> [*]

    MultiAgentCheck --> SSRCheck : no / failure\n(falls through to ReAct on error)
    SSRCheck : SpecializedServiceRouter\n(autonomous_research | cross_oracle | client_journey)
    SSRCheck --> SSRReturn : detected + response
    SSRReturn : emit CoreResult(\nmodel=specialized-router)
    SSRReturn --> [*]

    SSRCheck --> NLMSpeculative : no match
    NLMSpeculative : resolve_notebook\n(spawn async nlm_task,\nnon-blocking)
    NLMSpeculative --> Routing : task scheduled (or skipped)

    Routing : routing_manager.route_query\n(→ model_tier, deep_think_mode,\nAgentState init)
    Routing --> BuildPrompt

    BuildPrompt : prompt_builder.build_system_prompt\n+ create_chat_with_history
    BuildPrompt --> ReActLoop

    state ReActLoop {
        [*] --> InnerSM
        InnerSM : (see §2)
        InnerSM --> [*]
    }

    ReActLoop --> GradingGates : state.final_answer set

    GradingGates : _run_grading_gates\n(AnswerGrader / HallucinationGrader /\nPricingGrader / ReasoningGrader)
    GradingGates --> MetricsExtract : shadow mode (always)\nor ACTIVE consequences applied

    MetricsExtract : extract timings / sources / collections
    MetricsExtract --> RecordMetrics : ok

    RecordMetrics : record_rag_metrics /\nrecord_token_usage /\nlog_query_completion
    RecordMetrics --> LogAnalytics

    LogAnalytics : _log_query_analytics\n(query_analytics repo, non-blocking)
    LogAnalytics --> BuildResponse

    BuildResponse : response_builder.build_core_result\n(+ langgraph_workflow append)
    BuildResponse --> NLMMerge

    NLMMerge : evidence in [0.15, 0.60]\n+ not trusted → CAUTIOUS
    NLMMerge --> NLMAwait : cautious + (cached | task)
    NLMAwait : await nlm_task (timeout=3s)\n→ attach result.nlm_enrichment
    NLMAwait --> KGAutoExpansion
    NLMMerge --> NLMCancel : not cautious + task pending
    NLMCancel : task.cancel()\n(graceful)
    NLMCancel --> KGAutoExpansion
    NLMMerge --> KGAutoExpansion : no NLM path

    KGAutoExpansion : evidence > 0.6\n→ spawn expand_from_response\n(fire-and-forget)
    KGAutoExpansion --> Final

    Final : emit CoreResult (enriched)
    Final --> [*]
```

### 1.2 Transitions table (outer)

| # | From | To | Condition / guard |
|---|------|-----|-------------------|
| O1 | `PrepareContext` | `QueryPlanner` | Always (context + entities ready or fallback empty) |
| O2 | `QueryPlanner` | `GatesCheck` | Always (active / shadow / off all pass through) |
| O3 | `GatesCheck` | `GateReturn → [*]` | `gate_result.triggered == True` |
| O4 | `GatesCheck` | `FAQCacheCheck` | `gate_result.triggered == False` |
| O5 | `FAQCacheCheck` | `FAQReturn → [*]` | `faq_cache.get(query)` returned non-None |
| O6 | `FAQCacheCheck` | `SemanticCacheCheck` | miss or exception (graceful degradation) |
| O7 | `SemanticCacheCheck` | `SemanticReturn → [*]` | `cached` truthy |
| O8 | `SemanticCacheCheck` | `MultiAgentCheck` | miss or handled exception |
| O9 | `MultiAgentCheck` | `MultiAgentReturn → [*]` | `_multi_agent_coordinator and requires_multi_agent(query)` and `ma_result["final_answer"]` |
| O10 | `MultiAgentCheck` | `SSRCheck` | coordinator absent, `requires_multi_agent` false, or exception |
| O11 | `SSRCheck` | `SSRReturn → [*]` | `_specialized_router` detected category with `ssr_result["response"]` |
| O12 | `SSRCheck` | `NLMSpeculative` | no SSR match |
| O13 | `NLMSpeculative` | `Routing` | always (spawn-and-continue pattern) |
| O14 | `Routing` | `BuildPrompt` | always |
| O15 | `BuildPrompt` | `ReActLoop` | always |
| O16 | `ReActLoop` | `GradingGates` | `ReasoningEngine.execute_react_loop` returns (success path). On raise, `RuntimeError` propagates (no GradingGates). |
| O17 | `GradingGates` | `MetricsExtract` | always (grader errors caught, non-blocking) |
| O18 | `MetricsExtract` | `RecordMetrics` → `LogAnalytics` → `BuildResponse` | always linear |
| O19 | `BuildResponse` | `NLMMerge` | always |
| O20 | `NLMMerge` | `NLMAwait` | `0.15 ≤ evidence_score ≤ 0.60` AND `not trusted_tools_used` AND (cache hit OR task pending) |
| O21 | `NLMMerge` | `NLMCancel` | not cautious AND task pending → `task.cancel()` |
| O22 | `NLMMerge` | `KGAutoExpansion` | no NLM path taken |
| O23 | `NLMAwait`/`NLMCancel` | `KGAutoExpansion` | always |
| O24 | `KGAutoExpansion` | `Final → [*]` | `evidence_score > 0.6` → spawn task. Else: proceed to `Final` directly. Non-blocking either way. |

### 1.3 Invariants (outer)

Must hold at every early-return edge (`GateReturn`, `FAQReturn`, `SemanticReturn`, `MultiAgentReturn`, `SSRReturn`, `Final`):

- **I-O1**: A `CoreResult` is returned (never `None` nor an exception) on the happy path.
- **I-O2**: `entities` field on `CoreResult` reflects `extracted_entities` computed in `PrepareContext` (even on cache/gate returns).
- **I-O3**: `timings.total = time.time() - start_time`, always ≥ 0.
- **I-O4**: `nlm_task` (if created) is either awaited (`NLMAwait`) or cancelled (`NLMCancel`) — never leaked. This is why NLM speculative fire is placed *after* cache gates.
- **I-O5**: `tool_execution_counter["count"]` is monotonically non-decreasing across the pipeline.
- **I-O6**: `state.evidence_score ∈ [0.0, 1.0] ∪ {None}` when `BuildResponse` runs.
- **I-O7**: On `GateReturn`, `model_used` ends with `"-gate"` (security/greeting/casual/identity/clarification/out-of-domain). On `FAQReturn` → `"faq_cache"`, `SemanticReturn` → `"cache"`, `MultiAgentReturn` → `"multi-agent-coordinator"`, `SSRReturn` → `ssr_result.get("model", "specialized-router")`.

---

## 2. Inner state machine — `execute_react_loop`

### 2.1 Mermaid diagram

```mermaid
stateDiagram-v2
    [*] --> LoopEntry

    LoopEntry : while current_step < max_steps
    LoopEntry --> StepIncrement : enter
    StepIncrement : current_step += 1
    StepIncrement --> BuildMessage

    BuildMessage : step 1 → initial_prompt\nelse → "Observation: {last}\\nContinue..."
    BuildMessage --> SendMessage

    SendMessage : llm_gateway.send_message(\nenable_function_calling=True)
    SendMessage --> ParseToolCalls : ok
    SendMessage --> LoopBreak : Resource/TimeoutError/ValueError/RuntimeError\n(→ break, no final_answer set)

    ParseToolCalls : parse_tool_calls_from_response\n(native → regex → none)
    ParseToolCalls --> HasToolCalls : tool_calls non-empty
    ParseToolCalls --> NoToolCall : empty

    HasToolCalls : gather(execute_tool x N)\n(parallel)
    HasToolCalls --> ProcessResults : all done
    ProcessResults : for each result:\n- append AgentStep\n- extend context_gathered\n- handle vector_search sources\n- handle generate_image
    ProcessResults --> QualityCheck

    QualityCheck : _validate_context_quality\n(score vs ABSTAIN_THRESHOLD=0.15)
    QualityCheck --> ContinueLoop : quality < 0.15\n+ current_step < max_steps\n→ continue
    QualityCheck --> EarlyExitCheck : quality ≥ 0.15\nor max_steps reached

    EarlyExitCheck : should_early_exit_on_vector_search?\n(vector_search, len>500,\nintent not in COMPLEX_QUERY_INTENTS)
    EarlyExitCheck --> LoopBreak : true
    EarlyExitCheck --> LoopEntry : false (continue)

    NoToolCall : check "Final Answer:" / max_steps
    NoToolCall --> SetFinalAnswer : "Final Answer:" in text\nOR current_step ≥ max_steps
    NoToolCall --> ThoughtStep : else (append thought)
    ThoughtStep --> LoopEntry

    SetFinalAnswer : state.final_answer = extract(\ntext_response)\n+ AgentStep(is_final=True)
    SetFinalAnswer --> LoopBreak

    LoopBreak --> TrustedCheck

    TrustedCheck : detect_trusted_tool_usage\n(state.steps, _TRUSTED_TOOL_NAMES)
    TrustedCheck --> EvidenceCalc

    EvidenceCalc : compute_evidence_score\n→ state.evidence_score
    EvidenceCalc --> AnswerContentCheck

    AnswerContentCheck : detect_pricing_data_in_answer\n→ trusted_tools_used=True
    AnswerContentCheck --> HasToolsCheck : skip if no final_answer

    HasToolsCheck : detect_llm_has_tools(gateway)\nif has_tools: trusted=True
    HasToolsCheck --> LowEvidenceGate

    LowEvidenceGate : should_apply_low_evidence_policy\n(final_answer AND score<0.15\nAND not skip_rag AND not trusted)
    LowEvidenceGate --> CriticalBranch : true + is_critical_domain(query)
    LowEvidenceGate --> Tier1Regen : true + non-critical
    LowEvidenceGate --> GenerateIfNeeded : false

    CriticalBranch : STRICT ABSTAIN\n→ state.final_answer = localized_stub("abstain_detailed")
    CriticalBranch --> GenerateIfNeeded

    Tier1Regen : build_tier1_prompt + send_message\n(→ state.final_answer regenerated)
    Tier1Regen --> GenerateIfNeeded : ok
    Tier1Regen --> AbstainFallback : Resource/Timeout/ValueError/RuntimeError
    AbstainFallback : state.final_answer = stub("abstain")
    AbstainFallback --> GenerateIfNeeded

    GenerateIfNeeded : no final_answer?
    GenerateIfNeeded --> CtxAnswer : has context_gathered\n+ score ≥ 0.15 (or skip_rag or trusted)
    GenerateIfNeeded --> CtxAbstain : no context + is_critical
    GenerateIfNeeded --> CtxTier1 : no context + non-critical
    GenerateIfNeeded --> SkipRagAnswer : skip_rag + no context
    GenerateIfNeeded --> PipelineVerify : already has final_answer

    CtxAnswer --> PipelineVerify
    CtxAbstain --> PipelineVerify
    CtxTier1 --> PipelineVerify
    SkipRagAnswer --> PipelineVerify

    PipelineVerify : response_pipeline.process\n(verification_score check)
    PipelineVerify --> SelfCorrection : score<0.7 + has context
    SelfCorrection : rephrase_prompt + retry\n(→ re-run pipeline)
    SelfCorrection --> Done
    PipelineVerify --> Done : score≥0.7 or no pipeline
    PipelineVerify --> PostProcessFallback : ValueError/RuntimeError/KeyError
    PostProcessFallback --> Done

    Done --> [*]
```

### 2.2 Transitions table (inner)

| # | From | To | Condition / guard |
|---|------|-----|-------------------|
| R1 | `LoopEntry` | `StepIncrement` → `BuildMessage` | `current_step < max_steps` |
| R2 | `LoopEntry` | (loop exit) | `current_step ≥ max_steps` |
| R3 | `SendMessage` | `ParseToolCalls` | success |
| R4 | `SendMessage` | `LoopBreak` | `ResourceExhausted | ServiceUnavailable | asyncio.TimeoutError | ValueError | RuntimeError` — **the loop breaks without setting `final_answer`**, downstream logic must generate one |
| R5 | `ParseToolCalls` | `HasToolCalls` | native or regex parse yielded ≥1 valid call |
| R6 | `ParseToolCalls` | `NoToolCall` | `parse_mode == "none"` (no calls) |
| R7 | `HasToolCalls` | `ProcessResults` | `asyncio.gather` returns (tool exceptions captured per-call as `f"Error: {e}"`) |
| R8 | `ProcessResults` | `QualityCheck` | always |
| R9 | `QualityCheck` | `ContinueLoop` | `quality_score < 0.15` AND `current_step < max_steps` → `continue` |
| R10 | `QualityCheck` | `EarlyExitCheck` | quality acceptable OR max reached |
| R11 | `EarlyExitCheck` | `LoopBreak` | `should_early_exit_on_vector_search(tool_name, result, intent)` True |
| R12 | `EarlyExitCheck` | `LoopEntry` | early-exit False (continue loop) |
| R13 | `NoToolCall` | `SetFinalAnswer` | `"Final Answer:" in text_response` OR `current_step ≥ max_steps` |
| R14 | `NoToolCall` | `ThoughtStep` | neither (keep thinking) |
| R15 | `ThoughtStep` | `LoopEntry` | always |
| R16 | `SetFinalAnswer` | `LoopBreak` | always |
| R17 | `TrustedCheck` | `EvidenceCalc` | always |
| R18 | `EvidenceCalc` | `AnswerContentCheck` | always |
| R19 | `AnswerContentCheck` | `HasToolsCheck` | always (may have flipped trusted=True) |
| R20 | `HasToolsCheck` | `LowEvidenceGate` | always (may have flipped trusted=True) |
| R21 | `LowEvidenceGate` | `CriticalBranch` | `should_apply_low_evidence_policy(...)` True AND `is_critical_domain(query)` True |
| R22 | `LowEvidenceGate` | `Tier1Regen` | `should_apply_low_evidence_policy(...)` True AND non-critical |
| R23 | `LowEvidenceGate` | `GenerateIfNeeded` | policy not applicable (answer ok, skip_rag, or trusted) |
| R24 | `Tier1Regen` | `AbstainFallback` | send_message raised; final_answer ← localized "abstain" stub |
| R25 | `GenerateIfNeeded` | `CtxAnswer` | `not final_answer AND context_gathered AND (score≥0.15 OR skip_rag OR trusted)` |
| R26 | `GenerateIfNeeded` | `CtxAbstain` | `not final_answer AND context_gathered AND score<0.15 AND not skip_rag AND not trusted AND is_critical` |
| R27 | `GenerateIfNeeded` | `CtxTier1` | same as R26 but non-critical |
| R28 | `GenerateIfNeeded` | `SkipRagAnswer` | `not final_answer AND not context_gathered AND skip_rag` |
| R29 | `PipelineVerify` | `SelfCorrection` | `processed["verification_score"] < 0.7` AND `state.context_gathered` |
| R30 | `PipelineVerify` | `PostProcessFallback` | `ValueError | RuntimeError | KeyError` raised |

### 2.3 Invariants (inner)

- **I-R1 (loop termination)**: `state.current_step ≤ state.max_steps + (len(tool_calls)-1)` at any point. The body has three exits: `break` (early-exit / SetFinalAnswer / error), `continue` (low quality), or natural loop condition (`current_step ≥ max_steps`). No infinite loop is possible provided `max_steps ≥ 1`.
- **I-R2 (final answer guaranteed)**: Past the `Done` state, `state.final_answer` is a non-empty string. Either set by (a) `SetFinalAnswer`, (b) low-evidence policy override (tier1 or strict abstain), (c) `CtxAnswer` / `CtxAbstain` / `CtxTier1`, (d) `SkipRagAnswer`, (e) pipeline self-correction, (f) fallback stub. **Exception:** if `SendMessage` raises on step 1 AND no subsequent branch regenerates, answer can be `None` — but in practice `should_apply_low_evidence_policy` requires `final_answer` to be truthy, so the policy short-circuits. See unclear #U1 below.
- **I-R3 (trusted bypass monotonic)**: Once `trusted_tools_used` flips to True, it stays True. Three independent flippers (detected tool usage, pricing markers in answer, LLM-had-tools).
- **I-R4 (evidence score is final)**: After `EvidenceCalc`, `state.evidence_score` is set (float 0..1). Subsequent branches may read but not re-compute it.
- **I-R5 (context_gathered monotonic)**: Only appended, never truncated. Used to accumulate tool observations across steps.
- **I-R6 (ABSTAIN threshold)**: `EvidenceScoreConstants.ABSTAIN_THRESHOLD = 0.15`. Below → ABSTAIN (critical) or Tier 1 fallback (non-critical).
- **I-R7 (parallel step counter bump)**: If N>1 tool calls executed in parallel, `current_step += len(tool_calls) - 1` after the loop body. Each parallel call produces its own `AgentStep`.
- **I-R8 (tool error isolation)**: A raise inside `_exec_tool_wrapper` is caught and returns `f"Error: {str(e)}"` as the observation — the loop does NOT break on a single tool failure, it continues with the error string in `tool_result`.

### 2.4 Trusted tool set (`_TRUSTED_TOOL_NAMES`)

```python
frozenset({"calculator", "crm_query", "get_pricing", "team_knowledge", "timesheet", "vector_search"})
```

When any of these succeeds, `trusted_tools_used = True` and the strict evidence gate is bypassed.

### 2.5 Early-exit predicate

`should_early_exit_on_vector_search(tool_name, tool_result, intent_type)`:

- tool_name == "vector_search", AND
- `len(tool_result) > 500` AND `"No relevant documents"` not in result, AND
- `intent_type not in COMPLEX_QUERY_INTENTS = {"business_complex", "business_strategic", "devai_code"}`

For complex queries, early exit is **disabled** — loop proceeds to allow KG/multi-tool reasoning.

---

## 3. Unclear / needs owner clarification

Flagged where the code doesn't make the intended behavior obvious from reading alone.

### U1 — Step-1 `send_message` raise path

At `reasoning.py:289-292`, if `llm_gateway.send_message` raises on step 1, the loop `break`s immediately. `state.final_answer` is still `None`, `context_gathered` is empty. Downstream:

- `should_apply_low_evidence_policy` requires `final_answer` truthy → False → skipped.
- `GenerateIfNeeded` (line 609) requires `state.context_gathered` truthy → False → skipped.
- `elif not state.final_answer` at line 732 handles: skip_rag path OR critical abstain OR non-critical Tier 1.

So in practice, Tier 1 or abstain stub fires even when step 1 fails. **But** if Tier 1's `send_message` *also* raises, `AbstainFallback` triggers via `_get_localized_stub("abstain", language)`. The final_answer is guaranteed non-None only if `_get_localized_stub` itself doesn't raise — which isn't tested.

**Question for owner:** Is the double-failure path (step-1 raise + Tier-1 raise) intentionally covered by the stub fallback, or is there a silent "empty answer" escape in practice? Worth a dedicated test.

### U2 — QueryPlanner in shadow vs active mode

Line 732-747 of `orchestrator_core.py`: when `_USE_QUERY_PLANNER=True`, `query_plan` is computed synchronously. When `_ENABLE_CRAG_ROUTER=True` AND `query_plan`, a `CRAGRouter` is instantiated and `crag_decision` computed. **However**, `crag_decision` is never consumed later in `process_query_core` — it's assigned to a local variable and that's it. This looks like dead code or a partial implementation.

**Question for owner:** Is `crag_decision` supposed to influence the routing manager, tier selection, or tool selection downstream? Currently it has no effect on behavior. Untestable until wired.

### U3 — `nlm_task` cancellation swallowed exception

Line 1021-1025: `await nlm_task` inside an `except (asyncio.CancelledError, Exception)` after `.cancel()`. The bare `Exception` catches any unrelated error from `nlm_enrichment_service.query`. If the service raised a bug (not a cancellation), it's silently swallowed — no logging, no metric. Non-blocking pattern, but noisy-failure debugging is harder. Not a bug; just worth knowing.

### U4 — `grading_gates` ACTIVE consequences

`_run_grading_gates` (line 1212-1229): when `_ENABLE_GRADING_GATES=True`, failed `answer` or `hallucination` grade clamps `state.evidence_score` to `min(existing, 0.15)` — pushing into ABSTAIN territory. This happens **after** the ReAct loop's own evidence gate ran. The downstream `NLMMerge` uses the (possibly clamped) score; `KGAutoExpansion` gate `>0.6` also. But the final answer has already been generated by reasoning.py before grading runs. So a "clamp to 0.15" here cannot regenerate the answer — it only affects NLM enrichment and KG expansion paths. **Intentional?** Suspected yes (active mode is about downstream confidence, not re-answering), but worth confirming.

### U5 — Streaming loop divergence

`execute_react_loop_stream` (line 905+) has extra logic not in sync:

- Line 1036-1040: `crm_query` explicit early exit + `trusted_tools_used=True` flag (sync does NOT have this — it relies on `detect_trusted_tool_usage` after the loop).
- Line 1095-1103: fallback scans for `detect_trusted_context_markers` / `detect_substantial_context` (sync path doesn't scan context markers explicitly).

**Impact:** Streaming can reach "trusted" earlier than sync for the same sequence of tool calls. State machines are not identical. Tests that mix streaming + sync must account for this drift.

### U6 — Parallel tool count vs `max_steps`

`reasoning.py:403-404`: after N>1 parallel tool executions, `state.current_step += len(tool_calls) - 1`. Combined with the per-iteration `current_step += 1` (line 248), total increment is `len(tool_calls)`. If `max_steps=3` and step 1 runs 5 tools in parallel, `current_step` jumps to 5, exceeding `max_steps`. Next `while` check fails, loop exits. **Is this intentional?** Seems so — fair budget enforcement — but the test for `max_steps` vs parallel-tool interaction is missing.

---

## 4. Coverage boundaries (what this diagram does NOT model)

Out of scope for Wave 1, tracked for Wave 2+:

- **`execute_react_loop_stream`** — expanded in §5 (Wave 3). Wave 2 only closed U5 (shared-flipper divergence via `apply_shared_trusted_flippers`). Wave 3 fully diagrams the streaming loop, its yield protocol, and sync-vs-stream transition drift.
- **Gating internals** — `QueryGates.run_all_gates` is a composite of 6 gates (security → greeting → casual → identity → clarification → out_of_domain). Wave 3 opens the black box in `apps/backend-rag/backend/tests/unit/services/rag/agentic/QUERY_GATES.md`.
- **QueryPlanner internal states** — shadow mode spawns a background task; the sync-active branch is linear.
- **`prepare_query_context`** — parallel sub-SM inside `PrepareContext`: entity extraction, legacy KG retrieval, LangGraph workflow synthesis. All three run via `asyncio.gather(..., return_exceptions=True)` — any raise is converted to fallback values. Not diagrammed.
- **`response_pipeline.process`** — Wave 3 breaks open the pipeline in `RESPONSE_PIPELINE.md` (VerificationStage → PostProcessingStage → CitationStage → FormatStage).

---

## 5. Streaming ReAct loop — `execute_react_loop_stream` (Wave 3)

**Scope:** `reasoning.py::execute_react_loop_stream` (lines 914-1407). Post-Wave 2 (SCAR §U5) the two paths share `apply_shared_trusted_flippers` for the final-answer-level trusted-flipper pair (pricing markers + has-tools). Everything else documented below is either **intentional divergence** or **streaming-only protocol** (yield events, per-tool execution, token chunking).

### 5.1 Mermaid diagram

```mermaid
stateDiagram-v2
    [*] --> StreamLoopEntry

    StreamLoopEntry : while current_step < max_steps
    StreamLoopEntry --> StreamStepIncrement : enter
    StreamStepIncrement : current_step += 1
    StreamStepIncrement --> YieldThinking

    YieldThinking : yield {"type": "thinking",\n"data": "Step N: Processing..."}
    YieldThinking --> StreamBuildMessage

    StreamBuildMessage : step 1 → initial_prompt + images\nelse → "Original user query: ...\\n\\nObservation: ..."\n(no images beyond step 1)
    StreamBuildMessage --> StreamSendMessage

    StreamSendMessage : llm_gateway.send_message(\nenable_function_calling=True,\nimages=step_images)
    StreamSendMessage --> StreamParseFirst : ok
    StreamSendMessage --> StreamYieldError : Resource/Timeout/ValueError/RuntimeError
    StreamYieldError : yield {"type": "error",\n"data": {"message": ...}}
    StreamYieldError --> StreamLoopBreak

    StreamParseFirst : parse_tool_calls_from_response\n→ tool_call = tool_calls[0] if tool_calls\n(stream takes ONLY first — never parallel)
    StreamParseFirst --> StreamHasToolCall : tool_call is not None
    StreamParseFirst --> StreamNoToolCall : tool_call is None

    StreamHasToolCall : yield {"type": "tool_call",\n"data": {tool, args}}
    StreamHasToolCall --> StreamExecTool

    StreamExecTool : execute_tool(...)\n(NO try/except wrapper —\nraises propagate unlike sync)
    StreamExecTool --> StreamCitationHandle : ok
    StreamCitationHandle : if vector_search: handle_vector_search_sources
    StreamCitationHandle --> StreamImageHandle

    StreamImageHandle : if generate_image:\nhandle_generate_image_result +\nyield {"type": "image", ...} if payload
    StreamImageHandle --> StreamAppendStep

    StreamAppendStep : AgentStep(step=current_step,\naction=tool_call, observation=result)\n→ state.steps.append\n→ context_gathered.append if non-empty
    StreamAppendStep --> StreamYieldObservation

    StreamYieldObservation : yield {"type": "observation",\n"data": result[:500]}
    StreamYieldObservation --> StreamVecEarlyExit

    StreamVecEarlyExit : should_early_exit_on_vector_search?\n(same predicate as sync)
    StreamVecEarlyExit --> StreamLoopBreak : True
    StreamVecEarlyExit --> StreamCrmEarlyExit : False

    StreamCrmEarlyExit : tool_name == "crm_query"\n+ len(result) > 10 ?\n(STREAM-ONLY, §U5)
    StreamCrmEarlyExit --> StreamTrustedCrmSet : True →\nstate.trusted_tools_used = True\n+ break
    StreamTrustedCrmSet --> StreamLoopBreak
    StreamCrmEarlyExit --> StreamComplexLog : False
    StreamComplexLog : vector_search + intent in\nCOMPLEX_QUERY_INTENTS → log only\n(loop continues)
    StreamComplexLog --> StreamLoopEntry

    StreamNoToolCall : "Final Answer:" in text\nOR current_step ≥ max_steps ?
    StreamNoToolCall --> StreamSetFinalAnswer : True
    StreamNoToolCall --> StreamAppendThoughtStep : False
    StreamSetFinalAnswer : state.final_answer =\nextract_final_answer_text(...)\n+ AgentStep(is_final=True)
    StreamSetFinalAnswer --> StreamLoopBreak
    StreamAppendThoughtStep : AgentStep(thought only)
    StreamAppendThoughtStep --> StreamLoopEntry

    StreamLoopBreak --> StreamTrustedPre

    StreamTrustedPre : state.trusted_tools_used OR\ndetect_trusted_tool_usage(steps)\n(same as sync)
    StreamTrustedPre --> StreamEvidenceCalc

    StreamEvidenceCalc : compute_evidence_score(...)\n→ state.evidence_score
    StreamEvidenceCalc --> StreamLowConfEmit

    StreamLowConfEmit : await emit_low_confidence_event(\ncontext="streaming")
    StreamLowConfEmit --> StreamYieldEvidence

    StreamYieldEvidence : yield {"type": "evidence_score",\n"data": {"score": ...}}
    StreamYieldEvidence --> StreamMarkersFlip

    StreamMarkersFlip : if not trusted:\ndetect_trusted_context_markers(context)\n(STREAM-ONLY, §U5 intentional widen)
    StreamMarkersFlip --> StreamSubstantialFlip : marker hit → trusted=True
    StreamMarkersFlip --> StreamSubstantialFlip : no hit

    StreamSubstantialFlip : if not trusted:\ndetect_substantial_context(context)\n(STREAM-ONLY, §U5)
    StreamSubstantialFlip --> StreamSharedFlippers

    StreamSharedFlippers : apply_shared_trusted_flippers(\npricing markers + has-tools)\n(SHARED with sync, Wave 2 U5 fix)
    StreamSharedFlippers --> StreamLowEvidenceGate

    StreamLowEvidenceGate : should_apply_low_evidence_policy?
    StreamLowEvidenceGate --> StreamCriticalAbstain : True + is_critical
    StreamLowEvidenceGate --> StreamTier1Regen : True + non-critical
    StreamLowEvidenceGate --> StreamSkipLog : False + skip_rag<0.15
    StreamLowEvidenceGate --> StreamTrustedLog : False + trusted<0.15
    StreamLowEvidenceGate --> StreamGenerateIfNeeded : no branch matches

    StreamCriticalAbstain : state.final_answer =\n_get_localized_stub("abstain", language)\n(NB: SYNC uses "abstain_detailed")
    StreamCriticalAbstain --> StreamGenerateIfNeeded
    StreamTier1Regen : build_tier1_prompt + send_message
    StreamTier1Regen --> StreamGenerateIfNeeded : ok
    StreamTier1Regen --> StreamTier1Stub : Resource/Timeout/ValueError/RuntimeError
    StreamTier1Stub : state.final_answer =\n_get_localized_stub("abstain", language)
    StreamTier1Stub --> StreamGenerateIfNeeded
    StreamSkipLog --> StreamGenerateIfNeeded
    StreamTrustedLog --> StreamGenerateIfNeeded

    StreamGenerateIfNeeded : no final_answer?
    StreamGenerateIfNeeded --> StreamCtxAnswer : context gathered\n+ (score≥0.15 OR skip_rag OR trusted)
    StreamGenerateIfNeeded --> StreamCtxAbstainItalian : context + critical + low score\n(HARDCODED Italian, not localized stub)
    StreamGenerateIfNeeded --> StreamCtxTier1 : context + non-critical + low
    StreamGenerateIfNeeded --> StreamSkipRagAnswer : skip_rag + no context
    StreamGenerateIfNeeded --> StreamNoCtxCritical : no context + critical
    StreamGenerateIfNeeded --> StreamNoCtxTier1 : no context + non-critical
    StreamGenerateIfNeeded --> StreamStubFilter : already has final_answer

    StreamCtxAnswer --> StreamStubFilter
    StreamCtxAbstainItalian --> StreamStubFilter
    StreamCtxTier1 --> StreamStubFilter
    StreamSkipRagAnswer --> StreamStubFilter
    StreamNoCtxCritical --> StreamStubFilter
    StreamNoCtxTier1 --> StreamStubFilter

    StreamStubFilter : if final_answer contains\n"no further action needed" /\n"observation: none"\n→ stub("confused", language)
    StreamStubFilter --> StreamPipelineVerify

    StreamPipelineVerify : if final_answer AND response_pipeline:\nresponse_pipeline.process(...)\n→ update final_answer, sources
    StreamPipelineVerify --> StreamPipelineFallback : ValueError/RuntimeError/KeyError
    StreamPipelineFallback : post_process_response(final_answer, query)
    StreamPipelineFallback --> StreamTokenChunking
    StreamPipelineVerify --> StreamTokenChunking : ok

    StreamTokenChunking : if final_answer:\nfor chunk in chunks(20):\nyield {"type": "token", "data": chunk}
    StreamTokenChunking --> StreamYieldSources

    StreamYieldSources : if state.sources:\nyield {"type": "sources", "data": ...}
    StreamYieldSources --> [*]
```

### 5.2 Transitions table (streaming-only or diverging)

The table below enumerates **transitions introduced or diverging from §2 (sync)**. Transitions that behave identically to sync (e.g. R1 LoopEntry → StepIncrement, R8 QualityCheck mechanics) are not duplicated here.

| # | From | To | Condition / guard | Sync counterpart |
|---|------|-----|-------------------|------------------|
| S1 | `StreamStepIncrement` | `YieldThinking` | always — yields `{"type": "thinking"}` before LLM call | N/A (sync emits no event) |
| S2 | `StreamBuildMessage` | `StreamSendMessage` | step > 1 prompt includes `"Original user query: {query}"` header that sync omits — helps streaming keep context across yields | §R1-modified |
| S3 | `StreamBuildMessage` | `StreamSendMessage` | images only on step 1 (`step_images = images if state.current_step == 1 else None`) — sync has no image param | new |
| S4 | `StreamSendMessage` | `StreamYieldError → StreamLoopBreak` | `ResourceExhausted | ServiceUnavailable | asyncio.TimeoutError | ValueError | RuntimeError` → yield `{"type": "error"}` + break | §R4 (sync: `set_span_status("error")` + break, no yield) |
| S5 | `StreamParseFirst` | `StreamHasToolCall` | `tool_calls[0] if tool_calls else None` — stream takes **only the first tool call**, never parallel. Sync does `asyncio.gather` on all. | §R5 (sync native/regex parse → N-parallel) |
| S6 | `StreamHasToolCall` | `StreamExecTool` | yields `{"type": "tool_call", "data": {tool, args}}` before execution | N/A |
| S7 | `StreamExecTool` | `StreamCitationHandle` | `execute_tool` called directly — **NO try/except wrapper**. A raise propagates, breaking the generator. Sync has `_exec_tool_wrapper` that captures raises as `"Error: {e}"`. | §R7 + I-R8 divergent |
| S8 | `StreamImageHandle` | `StreamAppendStep → StreamYieldObservation` | if `generate_image` result has payload → yield `{"type": "image"}` event. Sync only persists. | new |
| S9 | `StreamYieldObservation` | `StreamVecEarlyExit` | yields first 500 chars of `tool_result` | N/A |
| S10 | `StreamVecEarlyExit` | `StreamLoopBreak` | same predicate as §R11 (`should_early_exit_on_vector_search`) | §R11 |
| S11 | `StreamCrmEarlyExit` | `StreamTrustedCrmSet → StreamLoopBreak` | **STREAM-ONLY (§U5):** `tool_name == "crm_query" AND len(tool_result) > 10` → `state.trusted_tools_used = True` + break. Sync has no CRM-specific early exit — it relies on the post-loop `detect_trusted_tool_usage`. | N/A (sync-relies-on-post-loop) |
| S12 | `StreamComplexLog` | `StreamLoopEntry` | `vector_search + intent in COMPLEX_QUERY_INTENTS` → log only, loop continues (sync: same behavior, same log) | §R12 (same semantics) |
| S13 | `StreamNoToolCall` | `StreamAppendThoughtStep → StreamLoopEntry` | same as §R14 | §R14 |
| S14 | `StreamLoopBreak` | `StreamTrustedPre` | always — post-loop path begins | §R17 |
| S15 | `StreamEvidenceCalc` | `StreamLowConfEmit` | `await emit_low_confidence_event(..., log_context="streaming")` — sync calls without the `log_context` kwarg (§R18 is decomposed here) | new kwarg |
| S16 | `StreamLowConfEmit` | `StreamYieldEvidence` | yield `{"type": "evidence_score", "data": {"score": ...}}` | N/A |
| S17 | `StreamMarkersFlip` | `StreamSubstantialFlip` | **STREAM-ONLY (§U5, WAVE 2 locked):** if `not trusted_tools_used` then `detect_trusted_context_markers(state.context_gathered)`. Sync does NOT run this — deliberate widening of stream's trusted path. | N/A |
| S18 | `StreamSubstantialFlip` | `StreamSharedFlippers` | **STREAM-ONLY (§U5):** if still `not trusted`, `detect_substantial_context` flips to True based on total context length. Sync does NOT. | N/A |
| S19 | `StreamSharedFlippers` | `StreamLowEvidenceGate` | SHARED: `apply_shared_trusted_flippers(...)` — identical call-site as sync per Wave 2. | §R19-R20 (same) |
| S20 | `StreamLowEvidenceGate` | `StreamCriticalAbstain` | **KEY DIVERGENCE:** stream sets `_get_localized_stub("abstain", language)`. Sync sets `_get_localized_stub("abstain_detailed", language)`. Two different stub keys for the *same* semantic branch. | §R21 (stub key drift) |
| S21 | `StreamLowEvidenceGate` | `StreamTier1Regen` | same as sync §R22 but without `accumulated_usage + final_usage` accumulation (stream never tracks tokens) | §R22 (token-tracking drift) |
| S22 | `StreamTier1Regen` | `StreamTier1Stub` | same narrow exception tuple as sync U1 contract (tripwire locked in Wave 2) | §R24 |
| S23 | `StreamGenerateIfNeeded` | `StreamCtxAbstainItalian` | **KEY DIVERGENCE:** stream sets a **hardcoded Italian string** (lines 1217-1224) for critical-domain + low-score + has-context case. Sync uses `_get_localized_stub("abstain_detailed", language)`. Breaks language invariant for non-Italian users in streaming. | §R26 (language drift) |
| S24 | `StreamGenerateIfNeeded` | `StreamNoCtxCritical` | no-context critical path: `_get_localized_stub("abstain", language)` (same key as S20) | sync uses same key for this branch |
| S25 | `StreamStubFilter` | `StreamPipelineVerify` | filter stub responses containing `"no further action needed"` / `"observation: none"` — applies **only in streaming**. Sync does not filter these before pipeline. | N/A (sync passes raw to pipeline) |
| S26 | `StreamPipelineVerify` | `StreamPipelineFallback → StreamTokenChunking` | `ValueError | RuntimeError | KeyError` → `post_process_response(final_answer, query)`. Same as sync §R30. | §R30 |
| S27 | `StreamPipelineVerify` | `StreamTokenChunking` | ok — final_answer updated from `processed["response"]`; `state.sources` updated from `processed["citations"]` if present | §R30 sync path |
| S28 | `StreamTokenChunking` | `StreamYieldSources` | **STREAM-ONLY:** chunk final_answer into 20-char pieces → yield `{"type": "token"}` per chunk. Sync returns the answer as a single string. | N/A |
| S29 | `StreamYieldSources` | `[*]` | if `hasattr(state, "sources") and state.sources` → yield `{"type": "sources", "data": ...}` as closing event | N/A |

### 5.3 Invariants (streaming)

Paired with §2.3 (sync). **Invariant names use the `I-S*` prefix** to distinguish from inner-sync invariants `I-R*`.

- **I-S1 (yield ordering)**: the event stream follows a strict partial order per iteration: `thinking → [tool_call → observation → (optional image)]` or `thinking → (terminal, no tool_call)`. After loop break: `evidence_score → (token chunks) → (sources)`. A consumer can rely on `evidence_score` arriving **before** the first `token`.
- **I-S2 (single tool per step)**: streaming executes at most one tool per iteration (`tool_calls[0]`). Unlike sync (which parallelizes N tools with `asyncio.gather`), streaming budget is literally `max_steps = step count`. I-R7 does NOT apply.
- **I-S3 (tool raise kills generator)**: `execute_tool` has no wrapper in the streaming path. If a tool implementation raises, the AsyncGenerator raises and the consumer sees an incomplete event stream (no `evidence_score`, no `token`). This differs from I-R8 (sync converts tool raise to `"Error: {e}"` observation). **This is an intentional difference; streaming callers must handle generator exceptions.**
- **I-S4 (CRM early-exit trusted flip)**: in streaming, a successful `crm_query` (result > 10 chars) sets `state.trusted_tools_used = True` **inside the loop** and breaks. Sync sets trusted only *after* the loop via `detect_trusted_tool_usage` scanning `state.steps`. The end state is equivalent (trusted=True after CRM success) but the timing and the code path differ.
- **I-S5 (context widening is streaming-only)**: `detect_trusted_context_markers` and `detect_substantial_context` flippers run **only in streaming**. Sync's evidence gate is stricter: the same query + tools + context can be "low-evidence-blocked" in sync yet "trusted-path-passed" in stream. Documented intent; do not cross-port.
- **I-S6 (stub key drift, language-sensitive)**: in the override-existing-answer branch (`should_apply_low_evidence_policy == True` + is_critical), sync uses `stub("abstain_detailed", language)` and stream uses `stub("abstain", language)`. For the no-context critical branch, both use `stub("abstain", language)`. Callers/tests asserting on stub text must therefore distinguish (override vs no-context) x (sync vs stream).
- **I-S7 (hardcoded Italian leak)**: the no-context/low-score + has-context + is-critical branch (§S23) **does not honor the detected language**. Italian speakers see the right text; all other users see Italian. Deliberate current behavior — flagged for Wave 4+ refactor.
- **I-S8 (token chunk size invariant)**: `chunk_size = 20` characters. A final_answer of length `L` produces `ceil(L / 20)` token events. Consumers cannot assume word boundaries.
- **I-S9 (generator closure)**: a streaming invocation yields at minimum one event. Even on step-1 raise → yields `{"type": "error"}` then ends. On happy path: ≥ 1 thinking + ≥ 1 token. On empty final_answer (unreachable in practice per I-R2 via fallbacks), the token loop iterates 0 times and sources may or may not yield.

### 5.4 Sync ↔ stream drift summary (for Wave 4 planning)

| Drift | Direction | Fixable? |
|-------|-----------|----------|
| Stub key for override-answer critical branch (`"abstain"` vs `"abstain_detailed"`) | stream softer | YES — unify to `"abstain_detailed"` if semantic parity is desired |
| Hardcoded Italian vs `_get_localized_stub` in §S23 | stream broken for non-IT | YES — replace with `_get_localized_stub` call |
| Step 2+ prompt prefix (`"Original user query:"`) | stream helps LLM keep context | behavioral choice; keep |
| `detect_trusted_context_markers` / `detect_substantial_context` absent in sync | stream more permissive | per §U5 WAVE 2 decision: keep divergence, do NOT cross-port |
| `crm_query` in-loop trusted flip | stream sets trusted earlier | redundant but harmless post helper unification |
| Tool raise handling (stream propagates, sync captures) | stream harder to recover | behavioral choice; consumers handle generator exceptions |
| Token usage tracking | stream does not track | consumer protocol; not currently needed |
| `post_process_response` awaited in sync vs not in stream fallback | divergent `await` | harmless — `post_process_response` is sync-callable in both |

---

**End of Wave 3 streaming state machine map.** Sub-machine coverage (`QueryGates` + `ResponsePipeline`) documented in `apps/backend-rag/backend/tests/unit/services/rag/agentic/QUERY_GATES.md` and `RESPONSE_PIPELINE.md`. Regression tests in `test_orchestrator_state_machine_wave3_stream.py` / `_wave3_nlm.py` / `test_query_gates_composite.py` / `test_response_pipeline_stages.py`.
