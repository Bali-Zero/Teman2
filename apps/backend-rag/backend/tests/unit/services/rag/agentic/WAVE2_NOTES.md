# Wave 2 Notes — Orchestrator Outer Pipeline

**Branch:** `session/orchestrator-outer`
**Baseline:** commit `f26edf748` (Wave 1) + `dfeb0e1bb` (U2/U4 fix)
**Scope:** 9 outer pipeline gaps (O2, O9, O10, O11, O13p, O16-sync, O20, O21, O24) + U1/U3/U5/U6 from docs/audits/2026-04-22-orchestrator-state-machine.md.

---

## Outcome summary

| Area | Status | Tests added | Source LOC changed |
|------|--------|-------------|--------------------|
| O2 QueryPlanner active | ✅ | 1 | 0 (no code change) |
| O9 MultiAgent fast-path | ✅ | 1 | 0 |
| O10 MultiAgent exception fallback | ✅ | 1 | 0 |
| O11 SpecializedServiceRouter (3 branches) | ✅ | 3 | 0 |
| O13-partial NLM task creation / skip | ✅ | 2 | 0 |
| O16-sync ReAct raise propagation | ✅ | 2 | 0 |
| O20 Cautious NLM await + merge | ✅ | 1 | 0 |
| O21 Non-cautious NLM cancel (I-O4) | ✅ | 1 | 0 |
| O24 KG Auto-Expansion gate | ✅ | 2 (pos + neg) | 0 |
| **U1** Tier1 narrow exception | ✅ Docstring + 2 tripwire | 2 | +9 (docstring) |
| **U3** NLM cancel-path swallow | ✅ Log visibility | 0 | +14 (logging) |
| **U5** Stream vs non-stream unification | ✅ Option A helper | 5 | +54 net (extract + rewire) |
| **U6** Parallel step overshoot | ✅ In-code invariant comment | 0 | +10 (docstring) |

**Total new tests:** 21 (14 outer pipeline + 2 U1 tripwire + 5 U5 helper unit tests).
**Total LOC changed:** ~87 additions, ~25 deletions in source (reasoning.py + _reasoning_policy.py + orchestrator_core.py).

---

## Tests

### Outer pipeline (14)

File: `test_orchestrator_state_machine_wave2.py` — new file.

Fixture strategy: built a scoped `orch` fixture that mirrors
`test_orchestrator_coverage.py::orchestrator_setup` but returns the
orchestrator directly and resets `core._multi_agent_coordinator`,
`core._specialized_router`, `core.nlm_enrichment_service`,
`core._kg_auto_expansion`, `core.faq_cache` to `None` so each test opts in
to exactly the collaborator it exercises. `reasoning_engine.execute_react_loop`
returns a shared `_stub_final_state` that individual tests mutate in-place
(setting `evidence_score`, `trusted_tools_used`) to drive downstream NLM /
KG-expansion paths.

Notable points:
- **O9/O10** use the real `requires_multi_agent` detection (cost + timeline
  keywords), no monkey-patching — we actually trigger the branch with a real
  query string, confirming the entry-point predicate still works.
- **O20 (cautious merge)** uses a real `asyncio.create_task`-spawning
  coroutine (not a pre-resolved Future) so the `asyncio.wait_for(nlm_task)`
  path inside `process_query_core` is exercised for real.
- **O21 (cancel)** uses an `asyncio.Event` that the slow NLM coroutine sets
  in its `except CancelledError` branch — asserting the event was set
  proves `I-O4` (task always awaited or cancelled) for this path.
- **O24 (KG expansion)** uses `asyncio.sleep(0.05)` after `process_query`
  to let the fire-and-forget `spawn(expand_from_response(...))` task run
  before asserting the callable was invoked. Negative case (ev < 0.6)
  confirms the branch is gated correctly.

### U5 helper unit tests (5)

File: `test_abstain_bypass_policy.py` — new class `TestApplySharedTrustedFlippers` appended.

Locks the contract of the new helper:
- Early-True preserved (never flips True→False).
- Pricing marker flips True on empty-tools gateway.
- Has-tools + final_answer flips True without pricing.
- Empty answer + no tools stays False.
- Empty answer with tools does NOT flip (guard on `if final_answer`).

### U1 tripwire (2)

File: `test_orchestrator_state_machine_wave2.py` — class `TestTier1RegenExceptionContract`.

Locks the narrow catch on Tier1 regen:
- ServiceUnavailable (in tuple) → abstain stub fallback (I-R2 preserved).
- TypeError (NOT in tuple) → propagates → wrapped as `RuntimeError("ReAct loop failed: ...")` by `orchestrator_core.execute_react_loop`.

If someone widens the catch to bare `Exception`, the TypeError would be silently
swallowed and the second test fails. If they narrow it below the existing
tuple, the first test (and the pre-existing Wave 1 test) fails.

---

## U5 decision: Option A — minimal helper extraction

**Chosen:** partial Option A. Extract the *shared* portion only; document the
stream-only pre-flippers as intentional widening.

### Rationale

The `_reasoning_evidence.py` module already documented
`detect_trusted_context_markers` and `detect_substantial_context` as
"streaming-only fallback — the sync pipeline does not use this." The
divergence is a deliberate design decision, not drift. Streaming is
intentionally more permissive about trusted-path detection because some
streaming early-exits (CRM) bypass the step-level `detect_trusted_tool_usage`
signal that non-stream relies on.

Fully unifying the two paths (pushing stream-only checks into non-stream)
would widen evidence-gating on the sync pipeline in ways the original
streaming author didn't intend. Hiding the divergence behind a
`streaming: bool` parameter just relocates the conditional without removing
drift.

Instead, we extracted **only the pair that IS identical** (pricing-in-answer
+ LLM-had-tools) into `apply_shared_trusted_flippers(trusted_tools_used,
final_answer, llm_gateway) -> bool`. Both pipelines now call this helper,
so that pair cannot drift. The stream-only pre-flippers stay in
`execute_react_loop_stream` with a long docstring flagging them as a
deliberate streaming-only widening with a cross-reference to this note.

### What Option A delivered

```python
# _reasoning_policy.py — new helper
def apply_shared_trusted_flippers(*, trusted_tools_used, final_answer, llm_gateway) -> bool:
    # 1. Pricing-in-answer
    # 2. LLM-had-tools + final_answer
    # Returns possibly updated trusted_tools_used; never flips True→False.
```

**Sync path** (reasoning.py:~523-540): the 18-line pricing + has-tools block
collapses into a 4-line call to the helper.

**Stream path** (reasoning.py:~1092-1122): keeps its two stream-only
pre-flippers (`detect_trusted_context_markers`, `detect_substantial_context`)
with an expanded docstring explaining why they don't exist in sync. Tail
calls the same helper.

### What we explicitly did NOT do

- Did not push stream's `detect_trusted_context_markers` /
  `detect_substantial_context` into the sync pipeline. That would be a
  behavior change (more permissive gating), not a refactor.
- Did not add a `streaming: bool` gate to the helper. Keeping the helper
  purely mechanical means any future widening is a deliberate new call
  at the use site, not a silent flag flip.
- Did not collapse `should_apply_low_evidence_policy` further; it was
  already extracted in Wave 1.

### Tests that prove equivalence

The sync path continues to pass all 15 wave-1 regression tests (no behavior
change). The stream path continues to pass `test_orchestrator_coverage.py`
streaming tests. The 5 new `TestApplySharedTrustedFlippers` tests lock the
helper's contract so either pipeline breaking parity will be caught at the
unit level.

---

## U1 outcome: tripwire + docstring

Left the narrow tuple `(ResourceExhausted, ServiceUnavailable,
asyncio.TimeoutError, ValueError, RuntimeError)` in place. Added an inline
comment above the try/except that makes the contract explicit: types outside
the tuple are intentionally let through to the outer caller
(`orchestrator_core.execute_react_loop`), which wraps them as
`RuntimeError("ReAct loop failed: ...")`. Widening to bare `Exception` would
hide real programmer errors (`TypeError`, `KeyError`, `AttributeError`)
behind a graceful-looking abstain stub.

The two tripwire tests fail loudly if either direction is changed:
- `test_tier1_regen_service_unavailable_caught_and_stubbed` — narrowing
  breaks this.
- `test_tier1_regen_typeerror_propagates_as_runtime` — widening to
  `Exception` breaks this.

---

## U3 outcome: log visibility at DEBUG

Replaced the bare `except (asyncio.CancelledError, Exception): pass` with
two branches:

1. `except asyncio.CancelledError: pass` — expected outcome of `cancel()`.
2. `except Exception as exc: logger.debug("NLM task cancel-path exception swallowed: %s: %s", type(exc).__name__, exc)`

This preserves the original non-blocking semantics (the speculative NLM
task runs outside the critical path, its failure cannot block the
response) while making a misbehaving NLM provider diagnosable with
`grep "NLM task cancel-path exception"`. No functional change.

---

## U6 outcome: in-code invariant comment

Kept the `state.current_step += len(tool_calls) - 1` as-is. Added a multi-line
comment above the statement that:
- Calls out the §U6 flag in docs/audits/2026-04-22-orchestrator-state-machine.md.
- Explains the budget-enforcement intent (5 parallel tools = 5 units consumed
  even if all run in one physical iteration).
- Restates I-R7 (each parallel tool produces its own AgentStep) as the
  paired invariant.

Not a test but a **design-intent lock**: the next dev to question this line
will see the rationale before touching it.

---

## Files changed

### Source (3)

- `apps/backend-rag/backend/services/rag/agentic/_reasoning_policy.py`
  +60 LOC: new `apply_shared_trusted_flippers` helper.
- `apps/backend-rag/backend/services/rag/agentic/reasoning.py`
  U5: collapsed 2 × 18-line blocks into helper calls (+1 import, net ~-20).
  U1: +9 LOC contract comment above tier1 regen try/except.
  U6: +10 LOC invariant comment above parallel step counter bump.
- `apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py`
  U3: split `except (CancelledError, Exception): pass` into separate
  branches with a DEBUG log on the unexpected-exception case (+14 LOC).

### Tests (3)

- `apps/backend-rag/backend/tests/unit/services/rag/agentic/test_orchestrator_state_machine_wave2.py`
  NEW file, 16 tests: 14 outer pipeline + 2 U1 tripwire.
- `apps/backend-rag/backend/tests/unit/services/rag/agentic/test_abstain_bypass_policy.py`
  +104 LOC: `TestApplySharedTrustedFlippers` (5 tests).
- `apps/backend-rag/backend/tests/unit/services/rag/agentic/WAVE2_NOTES.md`
  NEW, this file.

---

## Test results

| Suite | Before Wave 2 | After Wave 2 | Delta |
|-------|---------------|--------------|-------|
| `test_orchestrator_state_machine_wave1.py` | 15 pass | 15 pass | 0 |
| `test_orchestrator_coverage.py` | 37 pass / 7 skip | 37 pass / 7 skip | 0 |
| `test_reasoning*.py` | — | — | 0 regressions |
| `test_abstain_bypass_policy.py` | 31 pass | 36 pass | +5 |
| `test_orchestrator_state_machine_wave2.py` | — | **16 pass** | +16 |
| **Full `tests/unit/services/rag/agentic/`** | 925 pass / 30 skip | **946 pass / 30 skip** | **+21, 0 regression** |

---

## What Wave 3 should pick up

Not in scope for this PR but natural follow-ups:

1. **O5/O7 end-to-end** — FAQ and semantic cache hits currently assert on
   the unit methods; an `assert result.model_used == "faq_cache"` test
   through `process_query_core` would close the gap.
2. **I-O5 monotonic tool counter** — no test asserts that
   `tool_execution_counter["count"]` is monotonic across an entire
   pipeline invocation. One observational test would lock it.
3. **ARCH-4 cross-notebook correlator** — the `resolve_multi_notebook`
   >=2 match branch spawns a `cross_notebook_correlator` task; not tested.
4. **Grading gates ACTIVE** — §U4 clamp behavior in active mode is
   tested at the unit level (Wave 1 clamp patch) but no integration test
   runs the full pipeline with `_ENABLE_GRADING_GATES=True`.
5. **QueryPlanner shadow mode metrics** — the shadow path (no active
   CRAG router) logs a plan; no test asserts the log or the
   planner_match_rate metric.

---

**End Wave 2 notes.** Next PR should be `session/orchestrator-inner-wave3`
once scope is decided.
