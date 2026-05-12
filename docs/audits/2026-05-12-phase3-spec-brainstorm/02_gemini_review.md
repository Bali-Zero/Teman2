# Phase 3 HGT Execution Spec — Gemini 3.1 Pro Architectural Review

### 1. Verdict

**PROCEED WITH CONDITIONS**

The structural approach of the spec is sound and the empirical anchoring provides strong confidence. However, the sync compatibility shim introduces severe runtime risk, and the manual dry-run for Ticket B can be eliminated by improving the fail-safe boundaries.

---

### 2. Answers to Q1.1 – Q1.4

**Q1.1 (Option A.α/β/γ choice):**
Option A.γ (Bridge wrapping canonical `HGTPublisher`) is architecturally correct. Relying on the centralized `HGTPublisher` ensures that schema guarantees (the 9-field shape) are homogeneously enforced for the cell-core coordinator, regardless of which cell emits them. Isolating the domain-specific legacy mapping (`StructuralPattern`) to a Bridge class keeps the boundaries clean.

**Q1.2 (Sync compatibility shim cost-benefit):**
The SYNC compatibility shim (`asyncio.run()` inside `CrmHGTPublisher`) is unacceptable. It is a major runtime risk: if called from within an existing event loop (such as `pytest-asyncio` fixtures or an asynchronous web framework), it will crash with `RuntimeError: asyncio.run() cannot be called from a running event loop`. The cognitive load and crash risk vastly outweigh the cost of breaking `test_stubs.py`. Migrate the tests to async.

**Q1.3 (Staged rollout adequacy for TICKET B):**
A 3-night dry-run is excessively cautious **if and only if** you implement a hard fail-safe. If the `_make_cell_runner()` initialization or the `async with runner.run(...)` block is wrapped in a broad `try/except Exception` that gracefully falls back to the legacy scraper pipeline, the blast radius to the nightly cron drops to zero. With an explicit fallback, you can skip the dry-run and deploy straight to production.

**Q1.4 (7-day soak adequacy):**
A 7-day soak is adequate. The goal of this phase is validating the architectural plumbing (HGT publisher → Redis stream → Sentinel consumer group `pending=0`). Seven days covers a complete weekly cycle (weekend and 5 weekdays), which is sufficient to expose memory leaks, stream connection drops, and consumer stall modes across both the daily (Scraper) and hourly (Sentinel) frequencies. Soaking for 8+ days yields no meaningful architectural data for the plumbing itself.

---

### 3. Numbered Findings

**F1: High-Risk Sync Shim (`asyncio.run`)**

- **Severity**: Critical
- **Evidence**: `apps/crm-cell/crm_cell/hgt_publisher.py` Option A.γ code block: _"SYNC shim — runs the async bridge in a fresh event loop"_
- **Recommended Action**: Delete `CrmHGTPublisher` completely or convert it to a purely `async def publish()` method. Fix `test_stubs.py` to use async fixtures.

**F2: Ticket B Unmitigated Blast Radius**

- **Severity**: High
- **Evidence**: Spec v1 Risk note: _"Failure mode: if `_make_cell_runner()` raises (e.g. Redis URL malformed), the pipeline aborts."_
- **Recommended Action**: Do not allow the pipeline to abort. Add a `try/except Exception` fallback block around the HGT runner logic in `run_intel_pipeline.py` that continues the legacy extraction if the cell integration fails.

**F3: Leaky Task Awaiting in Ticket C**

- **Severity**: Medium
- **Evidence**: `apps/mata-garuda/scripts/run_sentinel_cell.py`: `pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]; await asyncio.wait(pending, timeout=10.0)`
- **Recommended Action**: Using `asyncio.all_tasks()` is an anti-pattern. Third-party libraries (like `redis-py` or `httpx` connection pools) often leave background daemon tasks running. This will cause the script to hang for the full 10-second timeout unnecessarily. Explicitly track observatory emit tasks or use `asyncio.TaskGroup`.

**F4: Encapsulation Violation (Code Smell)**

- **Severity**: Low
- **Evidence**: `CrmHGTBridge.__init__`: `self._cell_origin = getattr(publisher, "cell_name", None) or publisher._cell_name`
- **Recommended Action**: Add an `@property def cell_name(self) -> str:` to `cell_core.hgt.publisher.HGTPublisher` so bridges can read it natively without violating encapsulation.

---

### 4. Top Convergent Corrections for Spec V2

1. **Remove the Sync Shim**: Update Ticket A to completely remove the `asyncio.run` wrapper. The `publish` method must be `async`. Mandate the rewrite of `test_stubs.py` to be async-native.
2. **Mandate Fallback in Ticket B**: Rewrite the proposed code change for `run_intel_pipeline.py` to include a strict `try/except` fallback to the legacy pipeline execution. Upon adding this code, remove the 3-day dry-run requirement.
3. **Fix Ticket C Async Cleanup**: Replace the `asyncio.all_tasks()` trap in `run_sentinel_cell.py` with explicit reference tracking or remove the wait entirely if the underlying Observatory library manages its own graceful shutdown.
4. **Extend the Refusals List**: Add a new refusal: _"No synchronous `asyncio.run` execution inside HGT publisher application code."_
5. **Update HGTPublisher API**: Include a minor refactor in the spec to expose `cell_name` as a public property on the canonical `HGTPublisher` class to resolve the `getattr`/`type: ignore` code smell.
