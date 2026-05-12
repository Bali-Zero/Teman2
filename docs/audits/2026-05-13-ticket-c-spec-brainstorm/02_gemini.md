# TICKET C Brainstorm Verdict

**Verdict**: PROCEED WITH CONDITIONS

## Answers to Q1.1 - Q1.3

- **Q1.1 (C.1 minimal shim vs C.2 full refactor):** Option C.1 (minimal shim) is the correct architectural choice. Phase 3's objective is to start the 14-day soak period by activating the consumer group. A full sensor refactor introduces unnecessary blast radius and delays the soak phase. The minimal shim safely bridges the gap and minimizes operational complexity.
- **Q1.2 (cron hourly + single_pulse() vs cell.run() with 5-min loop):** `cron hourly + single_pulse()` is superior. It perfectly preserves the operational footprint of the legacy LaunchAgent plist. Moving to a 5-minute `cell.run()` loop would require converting the cron job into a `KeepAlive` daemon, needlessly increasing deployment risk right before the validation period.
- **Q1.3 (sleep_hours 02-06 creates 4h gap):** Accettare (Accept). The 4-hour gap provides an excellent organic test for Redis stream backpressure and consumer group resilience. The `cell:skills` stream will naturally buffer events from the 24/7 intel-scraper, and the Sentinel consumer will drain the backlog when it wakes up at 06:00, proving the recovery capabilities of the system.

## Findings

- **F1: Asyncio Teardown / Telemetry Loss Hazard** (Severity: CRITICAL)
  - _Evidence_: `packages/cell-core/cell_core/pulse.py:82` / `00_briefing.md` `run_sentinel_cell.py` shim design
  - _Action_: `single_pulse()` initiates fire-and-forget observatory emissions. If the shim exits immediately via `asyncio.run()`, the event loop is destroyed before network buffers flush. The shim must include graceful asyncpg/httpx cleanup and a short `asyncio.sleep()` yield before returning to prevent dropped `cell_id='sentinel'` events.
- **F2: Invalid Method Invocation in Spec** (Severity: HIGH)
  - _Evidence_: `packages/cell-core/cell_core/pulse.py:82` vs Phase 3 spec v2
  - _Action_: The spec incorrectly references `await cell.tick()`. It must be corrected to `await cell.single_pulse()`, as this is the actual exposed method of `PulseLoop`.
- **F3: Missing Teardown Pattern** (Severity: MEDIUM)
  - _Evidence_: `apps/mata-garuda/scripts/run_sentinel_py.py:120-135` (Legacy Bypass)
  - _Action_: The new shim must not just naively wrap `single_pulse()`; it must mirror the canonical cron-invoked pattern found in `apps/evaluator/seo_cell/run_seo_cell.py`, which correctly handles structured logging and graceful connection shutdown.

## Top corrections for spec v2

1.  **Method Signature:** Replace `await cell.tick()` with `await cell.single_pulse()`.
2.  **Graceful Shutdown:** Mandate explicit connection teardown and event loop flushing in `run_sentinel_cell.py` so fire-and-forget observatory events are actually emitted to `observatory.db`.
3.  **Success Criteria Update:** Explicitly document the 4-hour `sleep_hours` gap as an accepted condition to validate stream buffering and recovery during the 14-day soak.

## Effort

**Low (~1-2 hours):** The implementation requires only the ~30 LOC `run_sentinel_cell.py` shim, 4 unit tests, and executing the pre-defined 6-step plist swap workflow.

## Sequencing

1.  **Code:** Implement the `run_sentinel_cell.py` shim (wrapping `create_sentinel_cell().single_pulse()`) with graceful async teardown.
2.  **Test:** Write and pass the 4 unit tests verifying return codes based on health states.
3.  **Deploy:** Ship the shim to production alongside the existing legacy script.
4.  **Cutover:** Execute the 6-step OPERATOR plist swap workflow to point cron at the new shim.
5.  **Verify:** Monitor `observatory.db` on the next hourly tick to confirm `cell_id='sentinel'` events > 0.
6.  **Soak:** Confirm `sentinel-1` consumer group is active, then begin the 14-day soak.
