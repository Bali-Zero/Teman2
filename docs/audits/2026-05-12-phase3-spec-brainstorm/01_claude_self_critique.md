# Claude Opus 4.7 max — Self-critique on Phase 3 spec v1

**Date**: 2026-05-12 21:50 WITA
**Method**: deliberately adversarial reading of my own spec, looking for what I would catch if I were reviewing someone else's work.

## Verdict (self-imposed)

**PROCEED WITH CONDITIONS** — spec is empirically anchored and structurally sound, but I've identified 6 substantive findings I'd flag if reviewing for a peer. The most concerning are F1 (async event loop nesting in sync shim), F2 (Mini Redis split-brain not addressed in TICKET B), and F3 (TICKET A.1 acceptance criteria silently fail).

## Findings

### F1 (severity: high) — `CrmHGTPublisher.publish()` sync shim async loop nesting is broken

**Spec location**: Spec v1 TICKET A.1 code block, lines defining the deprecated `CrmHGTPublisher.publish()` shim:

```python
def publish(self, pattern: StructuralPattern) -> bool:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            logger.warning("...")
            return False
        return loop.run_until_complete(self._bridge.publish(pattern))
    except RuntimeError:
        return asyncio.run(self._bridge.publish(pattern))
```

**Problem**: this design has 3 issues:

1. **`asyncio.get_event_loop()` is deprecated** in Python 3.12+ when there's no running loop (raises DeprecationWarning; future Python may raise). `apps/mata-garuda` runs Python 3.14.3 per the SessionStart hook. The fallback `asyncio.run()` is correct but the primary path is wrong.

2. **`loop.run_until_complete()` on a non-running event loop** can succeed but pollutes the loop's coroutine state. Better: always use `asyncio.run()` (which manages a fresh loop). The branching adds zero value but adds bug surface.

3. **The "if loop.is_running() return False" branch is silent failure**. Test fixtures using `pytest-asyncio` async tests will hit this path silently — they'll call `CrmHGTPublisher().publish(...)`, get False back, and assume the pattern was filtered (PII/confidence) rather than knowing it was rejected by the sync-shim incompatibility. The `test_legacy_sync_publisher_delegates_to_bridge` test (#8 in TICKET A.1 test list) only covers the happy path with no running loop.

**Recommended action**: collapse the sync shim to:

```python
def publish(self, pattern: StructuralPattern) -> bool:
    """SYNC shim. Production callers MUST use CrmHGTBridge.publish (async) directly."""
    import asyncio
    try:
        # If we're already in an event loop, refuse — caller must use async path.
        asyncio.get_running_loop()
        logger.error(
            "CrmHGTPublisher.publish called from inside a running event loop. "
            "Use CrmHGTBridge.publish (async) directly. Raising RuntimeError."
        )
        raise RuntimeError("CrmHGTPublisher.publish is sync-only — use CrmHGTBridge")
    except RuntimeError:
        # No running loop — safe to run fresh.
        return asyncio.run(self._bridge.publish(pattern))
```

Loud failure beats silent failure. Test #8 should assert RuntimeError raised when called from an async test, not silent False.

### F2 (severity: high) — TICKET B Redis URL doesn't address Mini Pro split-brain scar

**Spec location**: TICKET B `_make_cell_runner()`:

```python
redis_client = redis_async.from_url(
    os.environ.get("REDIS_URL", "redis://localhost:6379"),
    decode_responses=False,
)
```

**Problem**: The cicatrix scar `cicatrix-scars.md` "STRUCTURAL: NLM feeder split-brain — base_worker redis-cli has no host arg, prod has two local Redis instances (2026-05-06)" documents that Pro Redis (frozen, 258 entries, last 2026-05-05) and Mini Redis (fresh, OSINT producer) are split-brain. The scar fix was: `GARUDA_REDIS_HOST=100.93.236.6` (Mini's Tailscale IP) on `nlm-feeder-stream.hourly.plist`.

The intel-scraper-cell HGT publisher writes to `cell:skills` Redis stream. The sentinel-1 consumer-group (Discovery 4) reads from `cell:skills`. Both must point at the SAME Redis instance. Currently `redis-cli XLEN cell:skills` returns 18 on **Pro localhost** (because Phase 2.5 seed was on Pro). The intel-nightly cron runs on Pro. The sentinel cron runs on Pro. If `REDIS_URL` env var is not set on `com.balizero.intel.nightly.plist`, the fallback `redis://localhost:6379` is Pro localhost — correct.

But this is a **fragile invariant**. The spec should either:

1. Explicitly state "Phase 3 assumes Pro localhost Redis 6379 for cell:skills (NOT Mini)" with rationale that sentinel runs on Pro
2. Add a precondition check in `_make_cell_runner()`: connect to Redis, verify it's the same instance that has cell:skills with XLEN ≥18 (the seed signature). If wrong instance, abort.

Without option 1 or 2, a future operator changing REDIS_URL in plist to debug something will silently fork the publisher and consumer onto different Redis instances. Same scar class as the NLM feeder split-brain.

**Recommended action**: add option 2 (Redis instance signature check) to `_make_cell_runner()` + document option 1 in TICKET B "Hidden coupling notes". Also: explicit check in `apps/mata-garuda/scripts/run_sentinel_cell.py` that the Redis instance has cell:skills XLEN > 0 (the publisher path is alive).

### F3 (severity: medium) — TICKET A.1 acceptance criterion #4 is ambiguous

**Spec location**: TICKET A.1 Acceptance criteria:

> 4. No production caller exists yet (TICKET A.2 scope) → `redis-cli XLEN cell:skills` should remain 18 after A.1 merge (no new entries)

**Problem**: this is impossible to verify reliably. Between A.1 merge and the verification check, Phase 2.5's seed script could be re-run (unlikely but possible). Or intel-scraper-cell could ship Phase 3 TICKET B first (the spec doesn't strictly enforce A.1 → B sequencing — it just recommends).

Also: the criterion assumes the runner ONLY changes when production caller is added. But what if a test accidentally writes to cell:skills (forgot to mock Redis)? The test would pollute production state.

**Recommended action**:

1. Replace criterion #4 with: "A.1 merge does NOT introduce any callers of `CrmHGTBridge.from_redis(<non-None redis_client>)` outside `tests/`. Verify via `grep -rln 'CrmHGTBridge.from_redis' apps/ --include='*.py' | grep -v 'tests/' | wc -l → 0`."
2. Add a test setup helper in `tests/conftest.py` that wraps any `CrmHGTBridge` test with a mock Redis (asyncio Mock object) by default, with explicit opt-in for integration tests using `fakeredis.aioredis.FakeRedis`.
3. Add a CI check that fails if any non-test file imports `CrmHGTBridge.from_redis` (until A.2 ships and operator explicitly approves the caller).

### F4 (severity: medium) — Soak window math doesn't account for intel-scraper-cell publish rate

**Spec location**: Success criteria #1 "XLEN cell:skills ≥28 (seed 18 + ≥10 published by intel-scraper-cell)"

**Problem**: intel-scraper-cell nightly cron runs at 03:00 WITA daily. In 7 nights = 7 publish opportunities. Each opportunity publishes 0..N patterns depending on how many structural findings the scraper extracts. Empirically, looking at `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` flow (NB-1 would help here), how many `StructuralPattern` instances does a typical nightly run produce?

If each nightly produces ~1.5 patterns, 7 nights = ~10.5 patterns, criterion met just barely. If nightly produces 0.3 patterns (most nights nothing structural), 7 nights = 2 patterns, criterion FAILS. The spec assumes ≥1.4 patterns/night without empirical evidence.

**Recommended action**:

1. Before TICKET B ships: enumerate empirically how many `StructuralPattern.from_*()` instances are created in a recent successful intel-nightly run by adding a counter log + 1 dry-run.
2. Calibrate the 7-day target. If empirical rate is <1 pattern/night, extend soak to 14 days OR add lower-bar criterion "XLEN ≥20 in 14 days" (margin above seed of 18).
3. Add a separate criterion: "AT LEAST 1 successful publish event observed in observatory.db via cell_id='intel-scraper-cell' tagged events" — proves the chain works even if total count is low.

### F5 (severity: medium) — Refusals list is missing 3 items

**Spec location**: §"Refusals (autonomous scope)" lists 8 refusals.

**Missing**:

- **#9 No edits to `packages/cell-core/cell_core/hgt/publisher.py` or `consumer.py`** (these are the canonical HGT primitives — changes affect all 3 cells AND any future cell, blast radius is monorepo-wide)
- **#10 No edits to plist `com.balizero.intel.nightly.plist`** (production cron — same operator-gated scar as sentinel.hourly)
- **#11 No write to `cell:skills` Redis stream outside via official publisher path** (i.e. no `redis-cli XADD cell:skills` debug commands during execution — would pollute the substrate)

**Recommended action**: add #9, #10, #11 to the refusals list in spec v2.

### F6 (severity: low) — TICKET C plist edit instructions lack `chmod 0444` re-application

**Spec location**: TICKET C plist modification section. The XML snippet shows the modified `ProgramArguments` but the operator workflow ("operator-driven per chmod 0444 plist corruption scar") doesn't explicitly include the re-application of `chmod 0444` after the edit.

**Problem**: a careless operator following the spec verbatim might do:

```
chmod u+w plist
plutil -replace ProgramArguments -json '[...]' plist
launchctl bootout + bootstrap
```

…and forget to `chmod 0444 plist` at the end. The plist corruption scar antibody (chmod 0444) becomes ineffective until the next session.

**Recommended action**: add a verbatim 4-step operator workflow in TICKET C:

```bash
# 1. Unlock plist for edit
chmod u+w ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# 2. Modify ProgramArguments (point to run_sentinel_cell.py)
plutil -replace ProgramArguments -json '["/bin/bash","-lc","source ~/.nuzantara-secrets.env 2>/dev/null; /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_sentinel_cell.py"]' \
  ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# 3. Re-lock plist (CRITICAL — restores corruption antibody)
chmod 0444 ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# 4. Reload in launchd
launchctl bootout gui/$(id -u)/com.matagaruda.sentinel.hourly
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
```

Add `plutil -lint <plist>` between steps 2 and 3 as a sanity check.

## Answers to my own implicit "Claude self-critique" questions

### Did I propose the right Option A architecture (A.γ Bridge)?

Yes, but the rationale is incomplete in the spec. The Bridge pattern is correct because:

1. It mirrors IntelScraperHGTBridge (consistency)
2. It doesn't break the legacy `StructuralPattern` shape (zero callers but tests exist)
3. It localizes the translation to one place

But Option A.β (mirror intel-scraper-cell verbatim) is also defensible: it eliminates the schema-translation cognitive load entirely. The spec doesn't capture this trade-off well. **Spec v2 should add a 4-row decision table A.α/β/γ/δ (where δ = collapse both cells onto a single canonical HGTPublisher with no per-cell bridge) with pros/cons.**

### Did I correctly handle Discovery 5 (private attribute access)?

I noted it as a code smell but propagated it to `CrmHGTBridge` with `getattr(publisher, "cell_name", None) or publisher._cell_name`. Better would be: open a separate ticket to add `HGTPublisher.cell_name` as a public property in `packages/cell-core/cell_core/hgt/publisher.py`, then both bridges use the public attribute. **Add this as TICKET A.0 (5min mechanical) — blocking A.1 if you want clean code.**

### Is the 4-panel review approach itself the right move here?

Yes. Phase 2's review caught 7 corrections; without them, Phase 2 LIVE would have OOM'd Fly machine. Phase 3 has higher blast radius (production cron change + plist swap) so review-before-execute is even more important.

But: am I "performing rigor" by adding a self-critique step? The honest answer: I'd find 1-2 of these issues without the explicit "be adversarial" frame, but probably miss F1, F4, F6 without it. The frame is worth doing.

## Top 5 convergent corrections for spec v2

1. **CORR-1 (F1)**: replace sync shim implementation with loud failure pattern (RuntimeError on running loop, not silent False)
2. **CORR-2 (F2)**: add Redis instance signature check to `_make_cell_runner()` + explicit Pro localhost invariant doc
3. **CORR-3 (F4)**: empirically calibrate publish-rate before setting 7-day target; consider 14-day soak with lower bar
4. **CORR-4 (F5)**: add 3 missing refusals (#9, #10, #11)
5. **CORR-5 (decision table A.α/β/γ/δ)**: make Option A trade-off explicit with row-per-option pros/cons; also document TICKET A.0 sub-ticket for cell_name public property

(F3 + F6 are real but tactical — apply when writing spec v2 without further discussion.)

## Meta-observation

I'm tempted to grade my own spec as "PROCEED" because writing it well makes me invested. The proper grade is "PROCEED WITH CONDITIONS" because 5 substantive corrections is non-trivial.

I'll hold this self-grade until Gemini + DeepSeek + NB-1 land. If they converge on 3-4 of the same findings I'll feel calibrated. If they find 5+ findings I missed, I need to recalibrate my self-critique rigor for future specs.
