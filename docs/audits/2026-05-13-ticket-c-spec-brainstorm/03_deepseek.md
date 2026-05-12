## Verdict

**PROCEED WITH CONDITIONS** — 2 blocking issues (F1, F2) plus 3 medium and 2 low findings must be resolved before plist swap. Code changes are safe; operator action is gated.

---

## Answers to DeepSeek Q2.1–Q2.3

### Q2.1 — File:line number verification

| Claimed location                                                                  | Empirical evidence from briefing                                                                                                                                                                               | Verdict                                                                         |
| --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `sentinel_cell.py:46` `create_sentinel_cell()`                                    | ✅ `grep -n "def create_sentinel_cell"` → exact line 46                                                                                                                                                        | **Confirmed**                                                                   |
| `sentinel_cell.py:95` HGTConsumer init                                            | Phase 3 spec v2 says lines 91/95; spec v1 says line 95. Both cite lines, not body. The briefing confirms lines 25/91/95/126/136/141/167-170 contain HGTConsumer wiring. Line 95 is plausible as the init call. | **Plausible, not independently verified.** Need grep of actual line 95 content. |
| `sentinel_cell.py:167-170` reflect phase with `ensure_group()` + `consume_once()` | Phase 3 spec v2 cites these lines. Spec v1 inherits. Briefing confirms HGTConsumer wiring at those lines.                                                                                                      | **Plausible.** Strong empirical cross-reference.                                |
| `pulse.py:82` `single_pulse()`                                                    | Phase 3 spec v2 cites line 82. Briefing confirms `async def single_pulse(self) -> PulseResult:` at line 82.                                                                                                    | **Confirmed**                                                                   |
| `run_sentinel_py.py:120-135` legacy bypass                                        | Briefing confirms "Normalizer→Scorer→NLM Feeder→Digest" at these lines.                                                                                                                                        | **Confirmed**                                                                   |

**Minor discrepancy**: spec v1 says `sentinel_cell.py:95` for HGTConsumer, Phase 3 spec v2 says `line 91/95`. This does not affect correctness. **No false citations found.**

### Q2.2 — Other Phase 3 spec method name errors

- `PulseLoop` methods at `pulse.py`:
  - `async def run(self) -> None:` (line 73) — infinite loop, NOT used.
  - `async def single_pulse(self) -> PulseResult:` (line 82) — correct.
- `HGTConsumer` methods invoked at `sentinel_cell.py:167-170`:
  - `ensure_group()` — **unverified**. Source of `HGTConsumer` not given; assume exists.
  - `consume_once()` — **unverified**. Same assumption.
- `CrmHGTBridge.publish()` — correct (async).
- `IntelScraperHGTBridge.publish()` — correct (async).
- No `tick()` anywhere in PulseLoop, confirmed.

**Potential error (unverified)**: If `HGTConsumer` actually exposes `ensure_consumer_group()` or `consume()`, the shim will work because it doesn't call them directly — the cell’s reflect phase does. But future debugging may be misled. **Recommended: quick `grep` of `cell_core/hgt/consumer.py` to confirm method names.**

### Q2.3 — Fire-and-forget observatory emit with asyncio.run()

**The spec’s claim is incorrect.** `asyncio.run(main())` does **not** await fire-and-forget tasks created via `create_task` unless they are explicitly gathered. Its shutdown sequence:

1. Cancels all pending tasks (`loop.run_until_complete(loop.shutdown_asyncgens())`).
2. Closes the loop.

Per Python docs: _"If there are any pending tasks, they will be cancelled and an `asyncio.CancelledError` will be raised in each."_ The spec's statement _"asyncio.run() shutdown sequence awaits all pending tasks via the default ThreadPoolExecutor"_ is **false** — `asyncio.run` uses the event loop, not `ThreadPoolExecutor`. Fire-and-forget observatory emit tasks risk being cancelled **before** writing to observatory.db.

**This is the single biggest logical hole in the spec.** Acceptance criterion 5 (observatory.db rows) may silently fail.

---

## Numbered Findings

### F1 (CRITICAL) — Observatory emit task may be cancelled on exit

- **Evidence**: `asyncio.run()` cancels pending tasks. spec v1 §"Risks" table incorrectly claims asyncio.run() flushes. The emit task from `cell_core.observatory.emit_pulse_observed` (assumed `create_task`) is fire-and-forget. If the event loop exits before the task reaches the async write to sqlite, the pulse row is lost.
- **Action**: **Before plist swap**, either:
  1. Change `single_pulse()` to return a future and await all emitted tasks (e.g., collect tasks from observatory).
  2. Or add explicit `await asyncio.sleep(0.1)` after `single_pulse()` to yield control to pending tasks (not guaranteed but statistically safe for short writes).
  3. Or make observatory emit synchronous (preferred: `run_coroutine_threadsafe` not needed; use blocking sqlite from async off-thread is acceptable).
  4. **Minimum**: Document the risk and add a unit test that verifies observatory.db row is written after `asyncio.run(main())` completes.
- **Severity**: Acceptance criteria unmet → soak fails → Phase 3 stalls.

### F2 (HIGH) — sleep_hours 02-06 creates 4h gap, violating success criterion “no >2h gap”

- **Evidence**: Phase 3 spec v2 success criterion 3: _"observatory.db shows cell_id='sentinel' rows hourly with no >2h gap"_. spec v1 acknowledges sleep_hours=(2,6) produces a 4h gap but lists it as LOW risk “acceptance criteria unmet”. This is a contradiction.
- **Action**: Either:
  1. **Relax** success criterion to: _"no >2h gap except during configured sleep window (02-06)"_.
  2. Or **change** sleep_hours to `(2, 4)` to keep gap ≤2h (but that reduces rest period).
  3. Or **remove** sleep_hours for sentinel cell (not recommended — power/cooling reason).
- **Severity**: Without resolution, the 14-day soak cannot pass criterion 3.

### F3 (MEDIUM) — HGTConsumer method names unverified

- **Evidence**: Phase 3 spec v2 and spec v1 assume `ensure_group()` and `consume_once()` exist in `cell_core/hgt/consumer.py`. Not confirmed empirically.
- **Action**: Before merge, run: `grep -n "def ensure_group\|def consume_once" packages/cell-core/cell_core/hgt/consumer.py`. If names differ, adjust or adapt.
- **Severity**: Runtime error on first tick → cron fails silently (exit 1 or exception). Rollback needed.

### F4 (MEDIUM) — plist swap workflow lacks log verification after reload

- **Evidence**: spec v1 6-step workflow ends with `launchctl print ... | grep ProgramArguments` — only checks plist, not actual execution.
- **Action**: Add step 7: after bootstrap, wait 10s, then check logs:
  ```bash
  # Check last 5 lines of sentinel log
  tail -5 ~/Library/Logs/com.matagaruda.sentinel.hourly.log 2>/dev/null || \
  # If no log, check stdout via launchctl
  launchctl print gui/$(id -u)/com.matagaruda.sentinel.hourly | grep -i "last exit"
  ```
- **Severity**: Silent failure of new script (e.g., import error) goes undetected until next hourly tick.

### F5 (MEDIUM) — shim uses fragile sys.path manipulation for cron invocation

- **Evidence**: `_PACKAGE_PATH = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(_PACKAGE_PATH))` — depends on script location being exactly `apps/mata-garuda/scripts/run_sentinel_cell.py`. If ever moved or symlinked, import fails.
- **Action**: Set `PYTHONPATH` in plist EnvironmentVariables instead:
  ```bash
  plutil -replace EnvironmentVariables -json '{"PYTHONPATH":"/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda"}'
  ```
  (Check existing env: `plutil -extract EnvironmentVariables xml1` first, then merge.)
- **Severity**: Low probability but brittle.

### F6 (LOW) — Unit tests are stub skeletons

- **Evidence**: spec v1 §"File 3: tests" shows only docstrings and comments, no actual mock code.
- **Action**: For v2 spec, provide concrete mock implementations. E.g.:
  ```python
  @pytest.mark.asyncio
  async def test_main_returns_0_on_green_health():
      mock_cell = AsyncMock()
      mock_cell.single_pulse.return_value = Mock(health_status="green")
      with patch("scripts.run_sentinel_cell.create_sentinel_cell", return_value=mock_cell):
          assert await main() == 0
  ```
- **Severity**: Tests are not actionable; need completion before merge.

### F7 (LOW) — plist EnvironmentVariables may already contain other vars; replacement could destroy them

- **Evidence**: Phase 2 set `CELL_OBSERVATORY_EMIT=true` in this plist. If we `plutil -replace EnvironmentVariables -json '...'`, it overwrites the entire dictionary, dropping the existing key.
- **Action**: Use `plutil -insert EnvironmentVariables -json` if missing, or `plutil -replace` only after reading existing. **Recommended**: keep current env block unchanged; only modify ProgramArguments.

---

## Top Corrections for Spec v2 (order of priority)

1. **Fix observatory emit reliability** (F1): Add `await asyncio.sleep(0.1)` after `single_pulse()` and document that this is a temporary mitigation. Also add a test that mocks `create_sentinel_cell` and asserts `observatory.emit` was awaited (or synchronous).

2. **Resolve sleep_hours gap** (F2): Amend success criterion to allow up to 4h gap during configured sleep window, or change sleep_hours to 02:00-04:00. Document the final decision.

3. **Verify HGTConsumer method signatures** (F3): Add grep check to pre-merge checklist.

4. **Strengthen plist swap workflow** (F4, F7): Add log verification step. Use read-modify-write for EnvironmentVariables.

5. **Remove sys.path hack** (F5): Use plist `PYTHONPATH`.

6. **Fill in test implementations** (F6): Provide concrete mock code.

7. **Add rollback test**: Verify that rolling back the plist (to `run_sentinel_py.py`) restores legacy behavior within one cron tick.

---

## Effort Estimate (revised)

| Component                             | Base (spec v1) | Additional (F1–F7 fixes)   | Total               |
| ------------------------------------- | -------------- | -------------------------- | ------------------- |
| run_sentinel_cell.py shim             | 1h             | +0.5h (add sleep)          | 1.5h                |
| 4 unit tests (implemented)            | 2h             | —                          | 2h                  |
| plist swap workflow update            | 0h (spec only) | +0.5h (logs, PYTHONPATH)   | 0.5h                |
| HGTConsumer method verification       | 0h             | +0.25h (grep)              | 0.25h               |
| Doc updates (success criteria, risks) | 0.5h           | +0.25h (gap clarification) | 0.75h               |
| Manual smoke + operator plist swap    | 1h             | +0.5h (test rollback)      | 1.5h                |
| **Total**                             | **4.5h**       | **+2h**                    | **~6.5h (0.8 day)** |

Within the original Phase 3 spec v2 estimate of 2 days.

---

## Sequencing Recommendation

**Ship C code now** (run*sentinel_cell.py + tests + docs) \_but **delay plist swap** until the following conditions are met:*

1. **F1 fixed** — observatory emit reliability ensured.
2. **F2 resolved** — success criterion gap documented.
3. **F3 verified** — `HGTConsumer` methods confirmed.
4. **Smoke test passes** — manual `run_sentinel_cell.py` execution (with mock Redis) writes row to observatory.db.

**Do NOT wait for 14-day soak from A+B.** The consumer side is independent of pattern volume; even with zero new patterns, sentinel-1 consumer group should show `entries-read > 0` after first tick. The soak is for FASE 4 lift criteria, not for C deployment.

**Sequence**:

1. Merge TICKET C code (with corrections) → main.
2. Operator runs manual smoke test.
3. If smoke passes → operator executes plist swap (revised 7-step workflow).
4. Observe next two hourly ticks (2 hours) to confirm observatory.db rows + consumer group activity.
5. If successful → 14-day soak begins automatically.

**Rollback** if first tick fails: documented 6-step rollback (already in spec) — takes <2 minutes.

---

## Summary of Findings Severity

| Finding                          | Severity | Blocks plist swap?                                  |
| -------------------------------- | -------- | --------------------------------------------------- |
| F1 — observatory emit lost       | CRITICAL | **Yes**                                             |
| F2 — sleep_hours gap vs criteria | HIGH     | Operator decision (must resolve before soak passes) |
| F3 — unverified consumer methods | MEDIUM   | **Yes** (runtime risk)                              |
| F4 — missing log verification    | MEDIUM   | Advisory                                            |
| F5 — sys.path hack               | MEDIUM   | Advisory                                            |
| F6 — test stubs incomplete       | LOW      | No (but must be filled before PR merge)             |
| F7 — plist env overwrite         | LOW      | Advisory                                            |

**Recommended verdict**: PROCEED WITH CONDITIONS — code can be written and merged, but plist swap is blocked until F1, F3 are resolved and F2 is documented. Operator must be briefed on the remaining risks.
