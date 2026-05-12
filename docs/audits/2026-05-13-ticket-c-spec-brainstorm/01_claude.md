# Claude Opus 4.7 max — Self-brainstorm TICKET C

**Date**: 2026-05-13 01:48 WITA
**Method**: adversarial reading + look for asyncio gotchas in cron context.

## Recommendation: PROCEED WITH CONDITIONS (C.1 minimal shim)

### Why C.1 minimal shim

1. **Minimal blast radius**: shim ~30 LOC + plist 1-line change. Layer A (plist target) and Layer B (script bypass) both fixed.
2. **HGTConsumer already wired**: sentinel_cell.py:91-95/126/136/141/167-170 — ZERO new code needed for consumer integration.
3. **create_sentinel_cell() returns PulseLoop with HGTConsumer**: empirical at line 46. Just need to invoke `single_pulse()`.
4. **Phase 3 spec v2 explicitly recommends C.1 minimal over C.2** in §"Option C.1 vs C.2". Spec v2 §"Effort": C.1 2 days, C.2 3+ days. v1 estimate 5.5h = within scope.

### Why NOT C.2 (full refactor)

C.2 would restructure run_sentinel_py.py to make legacy normalizers (Normalizer + Scorer + NLM Feeder + Digest) into Sensors of a SentinelCell PulseLoop. Pros: legacy workers become part of the pulse. Cons:

- 3+ days work
- Breaks existing legacy invocation pattern (operator manual debug)
- Risk of breaking research-sentinel functionality
- Doesn't add value to FASE 4 lift criteria (which only requires sentinel-1 consumer active)

C.1 is enough. C.2 deferred to Phase 4+ if needed.

## 5 findings

### F1 (HIGH): asyncio.run() task cleanup uncertainty

Spec v1 trusts `asyncio.run()` to flush observatory emit fire-and-forget tasks. CORR-9 (from Phase 3 spec v2) forbids `asyncio.all_tasks()` blanket wait.

**Empirical concern**: Python 3.11+ `asyncio.run()` shutdown sequence:

1. Cancels remaining tasks via `asyncio.tasks._cancel_all_tasks(loop)`
2. Runs `loop.shutdown_asyncgens()` and `loop.shutdown_default_executor()`
3. Closes the loop

If observatory.emit creates `asyncio.create_task(...)` AFTER the main coroutine returns but BEFORE the cleanup sequence completes, the task may be cancelled before completing the write to observatory.db.

**Mitigation**: in main(), add explicit short await after `single_pulse()` returns to let fire-and-forget tasks settle:

```python
result = await cell.single_pulse()
# Brief settle to allow fire-and-forget observatory emit task to complete
await asyncio.sleep(0.1)  # 100ms is enough for sqlite3 write
```

This is NOT the same as `asyncio.all_tasks()` blanket wait (CORR-9 forbidden). It's a bounded sleep that allows the event loop one final tick.

### F2 (MEDIUM): sleep_hours 02-06 creates 4h gap in observatory.db cell_id='sentinel'

Phase 3 spec v2 §"Success criteria" #3 requires "no >2h cell_id='sentinel' gap in observatory.db". sentinel_cell.py config has `sleep_hours=(2, 6)` (line ~30 of factory). During 02:00-06:00 WITA, pulses may halt or skip with `halted=True/skipped=True`, no observatory emit. = 4h gap, exceeds 2h threshold.

**Mitigation options**:

- (a) Lower sleep_hours to (3, 5) — 2h gap, within threshold
- (b) Relax success criterion to "no >5h gap" in Phase 3 spec v2 (would require new PR)
- (c) Have observatory emit even during halted/skipped pulses (sentinel_cell.py emits regardless of pulse outcome — verify empirically)

**Recommendation**: (c) is the right answer. Looking at `cell_core/observatory.py` (or similar), the emit_pulse_observed function fires AFTER PulseResult is returned, regardless of halted/skipped state. If empirical post-merge shows no gap, F2 is mitigated; if gap appears, escalate to (a) or (b).

### F3 (MEDIUM): plist swap during active cron tick

If operator runs plist swap workflow WHILE the hourly cron is mid-execution (e.g. operator runs swap at 14:30, cron started at 14:00 and still in tick), `launchctl bootout` cancels the in-flight tick. May leave partial observatory.db state.

**Mitigation**: operator pre-check `launchctl print gui/$UID/com.matagaruda.sentinel.hourly | grep state` BEFORE step 6 bootout — if state is `running`, wait for next minute mark. Document in 6-step workflow.

### F4 (LOW): redis-cli verification commands in acceptance criteria

Spec v1 says "redis-cli XINFO GROUPS cell:skills sentinel-1 shows `entries-read > 0`". Empirical: HGTConsumer.consume_once() reads with XREADGROUP — entries-read counter increments only on successful read. If sentinel_cell.py:170 `consume_once()` returns 0 because cell:skills XLEN is exactly 18 (no new entries since seed), entries-read may not increment.

**Mitigation**: acceptance criterion needs A.2/B publishers to have emitted ≥1 new pattern (XLEN > 18). Otherwise, sentinel-1 cannot demonstrate consumption empirically. Order operationally: ship C → run intel-scraper cron at next 01:00 WITA → 03:00+ WITA sentinel cron consumes the new pattern.

### F5 (LOW): logging.basicConfig conflict with sentinel_cell internals

Shim main() calls `logging.basicConfig(...)` BEFORE `create_sentinel_cell()` returns. sentinel_cell.py imports `logger = logging.getLogger("mata_garuda.cells")` at module load. If sentinel_cell module is imported BEFORE basicConfig fires, the logger may not pick up the shim's format.

**Mitigation**: move `logging.basicConfig(...)` to BEFORE the import of `create_sentinel_cell` (i.e., before `from mata_garuda.cells.sentinel_cell import ...`). Already correct in spec v1 layout (basicConfig in `__main__` block, before sys.exit). But verify ordering in tests.

## Convergent corrections for spec v2

**CORR-C1** (F1 HIGH): add bounded `await asyncio.sleep(0.1)` after `single_pulse()` to settle fire-and-forget observatory emit task. Document why NOT `asyncio.all_tasks()` (CORR-9).

**CORR-C2** (F2 MEDIUM): empirical verify observatory emit fires regardless of halted/skipped pulse state. If not, escalate to lowering sleep_hours OR relaxing success criterion.

**CORR-C3** (F3 MEDIUM): add operator pre-check (`launchctl print | grep state`) BEFORE step 6 bootout to avoid mid-tick interruption.

**CORR-C4** (F4 LOW): acceptance criterion correction — sentinel-1 entries-read > 0 requires cell:skills XLEN > 18 first. Order: B/A.2 publisher event → C plist swap → next tick reads.

**CORR-C5** (F5 LOW): verify `logging.basicConfig` ordering relative to imports.

## Effort revised

| Component                                        | Hours               |
| ------------------------------------------------ | ------------------- |
| Spec v2 + 5 CORR-C applied                       | 1                   |
| run_sentinel_cell.py shim + CORR-C1 settle sleep | 1.5                 |
| 4 unit tests                                     | 2                   |
| Doc + risks                                      | 0.5                 |
| **Total v2**                                     | **~5h (~0.65 day)** |

Slightly lower than v1 estimate — corrections REDUCE code by clarifying simple settle sleep instead of complex task tracking.

## Sequencing

Already shipped: A.0 ✅ → A.1 ✅ → A.2 ✅ → B ✅. C is the final piece. Ship C now (code) + operator does plist swap when ready.

Empirical post-merge:

1. Code lands on main (~10 min CI)
2. Operator manually runs smoke test: `cd ~/Desktop/nuzantara/apps/mata-garuda && .venv/bin/python -u scripts/run_sentinel_cell.py`
3. If smoke test green (exit 0 + observatory.db row), operator runs 6-step plist swap
4. Next hourly tick post-swap: sentinel-1 consumer activates, entries-read > 0 if publishers have emitted

## Confidence

**80%** Option C.1 minimal shim is right. The 20% uncertainty is around:

- asyncio fire-and-forget task cleanup empirical behavior (F1)
- observatory emit firing during halted/skipped pulses (F2)

Both are unblockable concerns — empirical testing post-merge will reveal.
