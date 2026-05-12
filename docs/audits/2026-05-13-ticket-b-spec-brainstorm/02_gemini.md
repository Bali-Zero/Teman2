**Verdict**: PROCEED WITH CONDITIONS

### Answers to Questions

**Q1.1**: Option β (async sidecar) is the optimal architectural fit. It tightly bounds the blast radius to an additive post-processing phase, entirely avoiding mutation of the 2158 LOC synchronous `IntelPipeline.run()`. This elegantly isolates the new async cell mechanics from the legacy procedural subprocess shelling.
**Q1.2**: Deferring pattern emission is **unacceptable**. Deferring `publish_pattern()` directly contradicts the ticket's core goal ("`redis-cli XLEN cell:skills` increments") and breaks the FASE 4 lift criteria ("≥3 nights with positive delta"). Counters flow to the EventBridge (`observatory.db`), not the HGTBridge (`cell:skills`). You MUST ship ≥1 structural pattern in v1 (e.g., `source_reliability` or `sitemap_pattern`) to satisfy the stream increment constraint.
**Q1.3**: `asyncio.run()` at the end of `main()` is safe because `run_intel_pipeline.py` has no pre-existing event loop. However, unbounded network I/O to Redis or PostgreSQL inside `emit_pipeline_run` could hang indefinitely, stalling the cron job. A strict async timeout is required.

### Numbered Findings

1. **F1** (SEVERITY: HIGH) — Contradiction in HGT increment logic.
   - **Evidence**: `research/symbiosis/2026-05-13-ticket-b-narrow-spec.md` (Implementation File 2 `cell_post_emit.py`: "NOTE: pattern emission via session.publish_pattern() deferred... v1 ships counters only").
   - **Action**: Require emission of at least 1 structural pattern in TICKET B to satisfy the soak criteria. Counters do not emit to `cell:skills`.
2. **F2** (SEVERITY: MEDIUM) — Unbounded async execution risk in cron.
   - **Evidence**: `research/symbiosis/2026-05-13-ticket-b-narrow-spec.md` (Implementation File 1 `run_intel_pipeline.py`: `asyncio.run(emit_pipeline_run(pipeline.state))`).
   - **Action**: Wrap the call with `asyncio.wait_for(..., timeout=60)` to guarantee the script terminates even if Redis/PG connections stall.
3. **F3** (SEVERITY: LOW) — Potential Redis connection leak on runner assembly failure.
   - **Evidence**: `research/symbiosis/2026-05-13-ticket-b-narrow-spec.md` (Implementation File 2 `_make_cell_runner_with_preflight`: `except Exception as exc:` returns `None` without `await client.aclose()`).
   - **Action**: Add `await client.aclose()` in the exception block of `_make_cell_runner_with_preflight` for clean shutdown.

### Top Corrections for Spec v2

1. Implement ≥1 structural pattern broadcast (e.g., `source_reliability`) within `emit_pipeline_run` to ensure `cell:skills` increments and unblocks the 14-day soak validation.
2. Enforce a timeout wrapper in the `run_intel_pipeline.py` shim: `asyncio.run(asyncio.wait_for(emit_pipeline_run(...), timeout=60))`.
3. Ensure proper resource cleanup (`await client.aclose()`) in the runner assembly `except` block.

### Effort Estimate

**~1.5 days** (Spec v1 estimate of ~1 day + 0.5 days to implement and test the single structural pattern emission).

### Sequencing

A.0 → A.1 → A.2 → **B (with ≥1 pattern & timeout)** → C → 14-day soak → FASE 4 lift.
