# DeepSeek Reasoner — Phase 3 HGT Execution Spec Review

**Verdict: PROCEED WITH CONDITIONS**

---

## Q2.1 — Line number verification

**Self-consistency check**: The spec’s citation tree is internally coherent — Discovery 1 claims `crm_cell/hgt_publisher.py:56` is sync and `intel-scraper/backend/cell/hgt_publisher.py:140` is async; the empirical table uses the same references. The empirical state table includes a line `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py:46` for `create_sentinel_cell()`, but Discovery 4 (which reads the _actual source_) says the HGTConsumer is at lines 25/91/95/126/167-170 — **notably, line 46 is not explicitly mentioned** in Discovery 4 as the factory location. This is a **potential false premise**.

- The spec claims line 46 is `create_sentinel_cell()` PulseLoop factory. Without the file, I cannot confirm. If the factory is actually at line 46, the discovery should have said so. The omission suggests line 46 may not contain the factory. **Given the absence of cross-check, I flag this as UNVERIFIED — severity PENDING**.
- All other citations appear consistent with the file explorations described. I cannot verify actual on-disk content without access, but the spec’s own cross-file discoveries (1–6) are cited from the source code and do not contradict each other.

**Recommendation for spec v2**: Add an explicit empirical block that re-cites the exact lines for `create_sentinel_cell()` and `HGTConsumer` using `grep -n` output, so line numbers are auditable.

---

## Q2.2 — Redis URL split-brain (TICKET B environment risk)

**Finding**: The `_make_cell_runner()` default `redis://localhost:6379` is **almost certainly wrong for production**. The Phase 2 closure doc and prior split-brain scar (NLM feeder Pro+Mini) established that intel-scraper HGT must publish to **Mini’s Redis** at `100.93.236.6` to avoid polluting Pro’s namespace and because that’s where `cell:skills` is sharded.

Evidence gaps:

- The spec references `com.balizero.intel.nightly.plist` in open question Q2.2 but **never actually reads or cites its REDIS_URL EnvironmentVariable**. Without that verification, the default is a ticking bomb.
- If the plist sets `REDIS_URL=redis://100.93.236.6:6379`, then the default `localhost` is only a fallback and is harmless in production. But if the plist does **not** set it, the production pipeline will publish to localhost Redis (usually non-existent or wrong stream) — the HGT publish silently fails, and the entire XLEN ≥28 target becomes impossible.
- The spec’s own Discovery 5 of the Phase 2 spec warned about this. The TICKET B code ignores it.

**Risk**: High. Production cron silent failure for 7+ days.

**Recommended action**:

1. Explicitly document the required environment variable in the spec: `REDIS_URL` must point to Mini’s Redis IP (`100.93.236.6`) for the nightly cron.
2. Add a **defensive assertion** in `_make_cell_runner()`: if `REDIS_URL` is not set or points to localhost, log a CRITICAL warning and abort unless `--allow-localhost-redis` is passed.
3. Verify the plist content and include the relevant `plist` excerpt in the spec as evidence.

---

## Q2.3 — Async event loop nesting safety (sync shim)

**Analysis of the sync shim in `CrmHGTPublisher.publish()` (deprecated re-export):**

```python
def publish(self, pattern):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            logger.warning(...)
            return False    # <-- silent failure
        return loop.run_until_complete(self._bridge.publish(pattern))
    except RuntimeError:
        return asyncio.run(self._bridge.publish(pattern))
```

This is **unsafe in several contexts**:

1. **Inside a running event loop (e.g., pytest async test):** The shim returns `False` and logs a warning. The caller has no way to distinguish between “publish failed actually” and “publish was called from a running loop”. Test `test_legacy_sync_publisher_delegates_to_bridge` (test 8) may **pass when it should fail** if the test runs in an async fixture where the loop is running and `publish()` returns False.

2. **`asyncio.run()` in the fallback:** If `get_event_loop()` raises `RuntimeError` (no loop in thread), then `asyncio.run()` creates a new loop. This is safe but incompatible with `uvloop` or custom event loop policies that may be set globally. The spec’s ecosystem uses asyncio (not mentioned uvloop), but the risk of subtle incompatibility remains.

3. **Multiple callers sharing one sync shim:** If production code accidentally calls `CrmHGTPublisher.publish()` (the deprecated name) from a running event loop, it gets `False` instead of an error. The logging is only at `WARNING`; a miswired production caller could silently lose patterns for days.

**Worst-case scenario**: An async test runs `publish()` in an event loop that is already running; the shim returns False; the test asserts the return is True → **test passes despite failure to publish** (if the assertion checks the return value, but the spec’s test 8 just checks “delegates to bridge in fresh loop, returns same result” – it runs in a fresh loop, so it’s fine. But any other test that uses the sync shim inside an async fixture will be broken).

**Recommended action**: **Remove the sync shim entirely.** The spec states “zero production callers exist today” – so there is no blast radius. The existing `test_stubs.py` can be migrated to use `CrmHGTBridge` directly. The backwards-compatibility class `CrmHGTPublisher` should raise `DeprecationWarning` and not implement a fallback. The risk of silent False is far worse than breaking test_stubs.py (which can be fixed with ~3 minutes of work).

---

## Q2.4 — XLEN cell:skills delta calibration (18 → ≥28)

**Calibration analysis**:

- Seed: 18 (Phase 2.5, unchanged)
- 7-day soak after TICKET B ships
- Intel-scraper nightly cron runs **once per day** → maximum 7 publish opportunities
- Target: at least **10 new entries** from `intel-scraper-cell.hgt` (total ≥28)

**Is 10 in 7 realistic?**  
The intel-scraper-cell pipeline extracts patterns from articles. Assuming 50–200 articles per night, and a confidence floor of 0.7 with multiple structural patterns (source reliability, topic trends, etc.), the `IntelScraperHGTBridge` could produce 1–3 skills per run. **2 per night yields 14 in 7 nights** — above target. **1 per night yields 7** — below target. The spec’s 10 target is **just barely achievable** if the per-run average is ≥1.43.

**Hidden assumptions**:

- It assumes every nightly run produces at least one pattern that passes all confidence/PII/scope gates. If any run produces 0 (e.g., low article volume, all patterns filtered), the target slips.
- It does not account for weekends/holidays when cron might not run (though it’s a cron, so it should run every night).
- The dry-run phase (3 nights) is not included in the soak because dry-run does not write to cell:skills. So the soak window is **after** production switch — i.e., after the operator flips to production mode. That’s correct.

**Risk**: The calibration is tight but not impossible. The bigger risk is that a **low-pattern night** falls at the end of the 7-day window, causing the target to be missed and FASE 4 activation delayed.

**Recommended action**:

- Lower the threshold to **≥5** (to account for variance) or keep ≥10 but **include crm-cell entries** (if TICKET A.2 ships during the soak). The spec currently says intel-scraper only.
- Alternatively, require **at least 3 nights with ≥1 new entry** instead of an absolute count — this is more robust against empty nights.
- Add an explicit monitoring query during the soak: `redis-cli XLEN cell:skills` compared to previous day’s value daily.

---

## Numbered Findings

### F1 (HIGH): Sync shim `CrmHGTPublisher.publish()` silently returns False inside running event loops

- **Evidence**: Spec code at line `if loop.is_running(): ... return False`. The shim is included for backwards compatibility but the spec says “callers MUST use CrmHGTBridge directly”. Yet the test suite includes test 8 which uses the sync shim. If any other test or future caller accidentally uses it from an async context, patterns will be lost silently.
- **Recommended action**: Remove the sync shim entirely. The zero-caller blast radius makes migration trivial. Keep the class name but have `publish()` raise `DeprecationWarning` and `NotImplementedError` directing users to `CrmHGTBridge`.

### F2 (HIGH): TICKET B Redis URL default is a production split-brain risk

- **Evidence**: `_make_cell_runner()` defaults to `redis://localhost:6379`. Phase 2 scar established intel-scraper must publish to Mini Redis (100.93.236.6). The plist content for `com.balizero.intel.nightly.plist` is **not cited** in the spec, so the actual REDIS_URL is unknown.
- **Recommended action**:
  1. Read the plist and include its REDIS_URL value in the spec.
  2. Change default to `redis://100.93.236.6:6379` or make the function require `REDIS_URL` to be set explicitly (fail-fast if not set).
  3. Add a preflight check: if `REDIS_URL` points to localhost and `--production` is set, abort.

### F3 (MEDIUM): XLEN calibration target (≥28) is borderline unrealistic without crm-cell contribution

- **Evidence**: 7 nights × ∼1.43 patterns/night needed. No guarantee that each run produces ≥2 patterns. Spec says “crm-cell entries optional” but then uses `≥28` as hard gate for FASE 4 lift.
- **Recommended action**: Soften to `≥23` (5 new) or include crm patterns. Alternatively, use “≥3 nights with positive delta” instead of absolute count.

### F4 (MEDIUM): Line 46 cite for `create_sentinel_cell()` is unverified against Discovery 4

- **Evidence**: Discovery 4 lists lines 25/91/95/126/167-170 for HGTConsumer wiring but does **not** confirm line 46 as the factory location. The empirical state table says `sentinel_cell.py:46` is the PulseLoop factory. This is a potential false premise.
- **Recommended action**: Re-run `grep -n "def create_sentinel_cell" apps/mata-garuda/mata_garuda/cells/sentinel_cell.py` and cite the actual line number in the spec. If it’s not line 46, correct all references.

### F5 (MEDIUM): No hard gate enforcing TICKET B before TICKET C deployment

- **Evidence**: Sequencing says B → C, but no automated check or CI dependency prevents C from shipping before B. If C ships first, sentinel-1 consumer-group reads zero new entries for the entire B development window — wasted cron cycles and confusing metrics.
- **Recommended action**: Add a CI gate: TICKET C’s tests should fail if `redis-cli XLEN cell:skills` < seed+1 (or mock). Also add a refusal in §Refusals: “Do not ship TICKET C before TICKET B has completed dry-run phase and is in production.”

### F6 (LOW): `CrmHGTBridge.from_redis()` with `None` Redis is poorly defined

- **Evidence**: The spec says `from_redis(None)` → publish returns False without exception. But it creates `HGTPublisher(redis_client=None, ...)`. The `HGTPublisher` constructor may not expect None; it might attempt to use the client later and crash. The test covers the return False case but not the internal state.
- **Recommended action**: Validate that `HGTPublisher` handles `redis_client=None` gracefully (i.e., its `publish()` returns False). Add a unit test for `HGTPublisher(None).publish(skill)`. If it doesn’t, either make it robust or have `from_redis` return a no-op bridge.

### F7 (LOW): Refusals list is missing several items

- **Evidence**: The 8 refusals cover plist bootstrap, A.2 caller, secrets, kill-switch, git push, emit flags, dependencies.py, operator-controlled docs. Missing:
  - **Do not deploy TICKET C before TICKET B** (as above)
  - **Do not merge any ticket that breaks CI on main** (implicit but should be explicit for an autonomous phase)
  - **Do not modify `packages/cell-core/cell_core/hgt/coordinator/`** (mentioned in FASE 4 but not in refusals)
  - **Do not edit `CLAUDE.md` for any project without cross-operator approval** (currently only root CLAUDE.md is protected; per-project CLAUDE.md files are not mentioned)
- **Recommended action**: Add missing refusals to spec v2.

---

## Convergent Corrections (Top 5 for spec v2)

1. **Remove the sync shim `CrmHGTPublisher.publish()`** entirely. Replace with a `DeprecationWarning` stub that redirects to `CrmHGTBridge`. Update tests to use the async bridge directly.

2. **Fix REDIS_URL default in TICKET B** to `redis://100.93.236.6:6379` or make it mandatory with a hard abort if unset. Verify the production plist sets the correct value and cite it.

3. **Verify and fix the line number for `create_sentinel_cell()`** — add a `grep -n` output to the empirical state table.

4. **Soften the XLEN target** or allow crm-cell contributions. Define a monitoring query for daily delta during the soak.

5. **Add explicit CI gates**: unit test that the sync shim (if retained) raises an error when called from a running loop; integration test that validates REDIS_URL points to correct IP in CI mock; sequencing test that blocks TICKET C if B not shipped.
