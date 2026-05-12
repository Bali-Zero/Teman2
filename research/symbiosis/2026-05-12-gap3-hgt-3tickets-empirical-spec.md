---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS Gap 3 — HGT FASE 4 recovery 3-ticket consolidated spec (post empirical re-verification)
sources: 6
status: spec-ready-for-execution
empirical_survey_wita: 2026-05-12 15:35
---

# Gap 3 — HGT FASE 4 Recovery: 3-Ticket Empirical Spec

**Empirical re-verification time**: 2026-05-12 15:35 WITA
**Outcome**: All 3 HGT HALT premises from commit `68efc17e3` (2026-05-08) **still empirically true** on 2026-05-12. Spec consolidates the 3 prerequisite tickets with verbatim line numbers + acceptance criteria + effort refresh.

## Premises re-verified

### Prereq A — `crm_cell/hgt_publisher.py` STUB

`apps/crm-cell/crm_cell/hgt_publisher.py` (read 2026-05-12 15:35):

- **Line 79** still: `# Sprint 4: call into self._hgt_stream.xadd(...)`
- **No production caller**: `grep -rln "CrmHGTPublisher\|crm_cell.hgt_publisher" apps/` returns only `__init__.py` (re-export) and the file itself
- `__init__` accepts `hgt_stream=None` (line 51), no validation

### Prereq B — `IntelScraperCellRunner` shelf-ready, not invoked

- **Class defined** at `apps/bali-intel-scraper/backend/cell/runner.py:175`
- **Test coverage exists** (`tests/unit/cell/test_runner.py:29,54,214,260,290`)
- **Production import**: `grep "IntelScraperCellRunner\|cell.runner" apps/bali-intel-scraper/scripts/run_intel_pipeline.py` returns **0** matches

### Prereq C — `run_sentinel_py.py:120-135` legacy worker bypass

Read on 2026-05-12 15:35 WITA, lines 120-135 explicitly:

```python
print(f"  Normalizer: {n_stats}")
s_stats = run_scorer(kb, max_items=50)
print(f"  Scorer: {s_stats}")

# 3. Feed to NLM (grows the brain over time)
print("\n[NLM FEED]")
nlm_stats = run_nlm_feeder(kb, max_items=30)
print(f"  NLM Feeder: {nlm_stats}")
kb.close()

# 3. Digest
print("\n[DIGEST]")
from scripts.run_ai_digest import main as run_digest
run_digest()
```

`grep "PulseLoop\|pulse_loop\|tick()" run_sentinel_py.py` returns **0** matches. The cell-core `PulseLoop` is NEVER instantiated; the script runs the legacy worker pipeline directly. REFLECT phase (where HGT publisher hook lives in cell-core) never fires.

## The 3 prerequisite tickets (consolidated)

### TICKET A — Implement crm_cell xadd + production caller (1-2 days)

**Files to modify**:
- `apps/crm-cell/crm_cell/hgt_publisher.py` (replace line 79 stub)
- `apps/crm-cell/crm_cell/__init__.py` (export `create_crm_hgt_publisher()` factory)
- New: `apps/crm-cell/crm_cell/hgt_factory.py` (instantiates `redis.asyncio.Redis` stream + `CrmHGTPublisher`)
- Caller: identify where in `apps/backend-rag/backend/services/crm/` or `apps/crm-cell/` a `StructuralPattern` would be born. Candidate: CRM bulk import script after `lkpm_ingest_completed` event — extract patterns like "Brevo template T123 bounces 80%+ for client segment X" and publish via HGT.

**Code change (line 79)**:

```python
# Before (current stub):
logger.info("[STUB] hgt: pattern %s would publish ...", pattern.pattern_kind, ...)
# Sprint 4: call into self._hgt_stream.xadd(...)
return True

# After:
if self._hgt_stream is None:
    logger.warning("hgt: stream not configured, pattern %s dropped", pattern.pattern_kind)
    return False
try:
    await self._hgt_stream.xadd("cell:skills", {
        "pattern_kind": pattern.pattern_kind,
        "confidence": str(pattern.confidence),
        "payload": json.dumps(pattern.payload),
        "cell_origin": "crm-cell",
    })
    logger.info("hgt: pattern %s published", pattern.pattern_kind)
    return True
except Exception as exc:
    logger.warning("hgt: publish failed (non-blocking): %s", exc)
    return False
```

**Test scope** (`tests/unit/test_hgt_publisher.py` — new, ~5 tests):
- `test_publish_below_confidence_floor_returns_false`
- `test_publish_pii_payload_blocked`
- `test_publish_calls_xadd_with_correct_args`
- `test_publish_missing_stream_returns_false_and_warns`
- `test_publish_xadd_exception_swallowed_returns_false`

**Acceptance**:
1. `redis-cli XLEN cell:skills` > 0 after at least one production caller produces a pattern
2. CI tests green (`pytest apps/crm-cell/tests/unit/test_hgt_publisher.py -v`)
3. Manual smoke: trigger an `lkpm_ingest_completed` event, observe `cell:skills` stream entry within 30s

**Effort estimate**: 1.5 days (1 day implementation + tests, 0.5 day caller integration).

### TICKET B — Wire IntelScraperCellRunner into run_intel_pipeline.py (1 day)

**Files to modify**:
- `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` (add runner instantiation)
- `apps/bali-intel-scraper/tests/integration/test_intel_pipeline_with_runner.py` (new)

**Code change** (in `run_intel_pipeline.py`):

```python
# Add near top imports:
from backend.cell.runner import IntelScraperCellRunner

# In IntelPipeline.run() main flow:
runner = IntelScraperCellRunner(
    scar_recorder=scar_recorder,
    hgt_bridge=hgt_publisher,  # the existing HGTPublisher instance
    event_bridge=event_bridge,
)

# After each major pipeline step (validation, filter, enrichment, SEO):
async with runner as r:
    outcome = await r.run(step_name=current_step, articles_processed=n)
    if outcome.scars:
        logger.warning("step %s produced %d scars", current_step, len(outcome.scars))
```

**Acceptance**:
1. `grep "IntelScraperCellRunner" apps/bali-intel-scraper/scripts/run_intel_pipeline.py` returns ≥1 match (regression test in CI)
2. E2E smoke: `python scripts/run_intel_pipeline.py --mode dry-run --limit 1` produces ≥1 `cell_pulse_observed` event in observatory.db within 5min
3. Pipeline regression: same 8-step pipeline outcomes (validation, filter, enrichment, SEO outputs) as pre-wire

**Effort estimate**: 1 day (mostly already done in tests/unit — needs production wiring + integration smoke test).

**Risk note**: this touches the live production cron `com.balizero.intel.nightly` at 03:00 WITA. Suggest staged rollout: dry-run-only for 3 nights, then production.

### TICKET C — Switch sentinel cron entry to PulseLoop-aware path (2-3 days)

This is the **biggest** ticket because Layer B (the in-script bypass at `run_sentinel_py.py:120-135`) requires actual refactor of the sentinel workflow.

**Option C.1** (minimal — most useful for HGT activation, 2 days):

Add new entry script `apps/mata-garuda/scripts/run_sentinel_cell.py`:

```python
"""Cell-core-aware sentinel runner. Drives the full PulseLoop instead of
calling legacy workers directly. The Layer B bypass at run_sentinel_py.py:126
is preserved as a fallback for legacy compatibility; this new script is
the canonical HGT-enabled path going forward."""

import asyncio
from mata_garuda.cells.sentinel_cell import create_sentinel_cell

async def main() -> int:
    cell = create_sentinel_cell()
    result = await cell.tick()  # full sense→think→act→reflect→dream→mature
    print(f"sentinel pulse done health={result.health_status}")
    # Cleanup wait for observatory emit fire-and-forget task
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.wait(pending, timeout=10.0)
    return 0 if result.health_status != "red" else 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
```

Update plist `~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist` to invoke `run_sentinel_cell.py` instead of `run_sentinel_py.py`. The Layer A (plist target) and Layer B (script bypass) are both fixed by this single switch.

**Option C.2** (full refactor — preserves legacy worker pipeline as a sensor input to the cell, 3+ days):

Restructure `run_sentinel_py.py` to make the legacy normalizer/scorer/nlm_feeder/digest pipeline EACH become a Sensor in a SentinelCell PulseLoop, where:
- Sensors run as before
- Thinker reasons about the pipeline outcomes
- Actor publishes HGT skills if confidence threshold met
- Reflect+Dream phases fire

Higher fidelity but significantly more work.

**Acceptance**:
1. After switch: `redis-cli XLEN cell:skills` shows growth when TICKET A + B are also done
2. `~/.cell-observatory/observatory.db` shows `cell_id='sentinel'` pulse events
3. No regression in research-sentinel functionality (intel harvest + NLM feed still happen)

**Effort estimate**: 2 days for C.1 (recommended), 3+ days for C.2.

## Sequencing: A → B → C → FASE 4 activation

The HGT HALT (commit `68efc17e3`) will be safe to lift ONLY when:

1. `redis-cli XLEN cell:skills` ≥10 entries from `crm_cell.hgt` + `intel_scraper_cell.hgt` in a 7-day window (proves publishers work end-to-end after A+B)
2. `cell:skills` consumer-group `sentinel-1` consumer actively consuming with `pending=0` (proves HGTConsumer wired after C)
3. `~/.cell-observatory/observatory.db` shows pulse events with `payload_json` referencing HGT skills (proves the consumer integrates skills into sentinel cell)

When all 3 metrics hold, the existing `apps/cell-core/hgt_coordinator/` quarantine mechanism can graduate verified-good skills from propose-only to applied — that's the FASE 4 promise per `docs/SYMBIOSIS_TURNON_PLAN.md`.

## Total effort

| Ticket | Effort | Risk |
|---|---:|---|
| A — crm_cell xadd + caller | 1.5 days | low (stub is fail-safe today) |
| B — IntelScraperCellRunner wire | 1 day | medium (touches production cron) |
| C — sentinel cell-aware entry | 2 days (C.1) | medium (Layer A+B switch) |
| **Total Phase 4 prereq** | **4.5 days** | medium |

After all 3 close + 7-day metrics window passes: HGT FASE 4 activation = ~1 day to flip kill-switch + monitor. **Grand total Gap 3 closure: ~6 days** (was ~3-5 days in NB-1 audit — empirical refresh slightly higher).

## What this loop produces

Doc-only. Spec landed for execution. **No autonomous code changes** because:
- TICKET A: crm-cell is the lightest, could be autonomous, but adding a real `redis.asyncio.Redis` client requires connection-config decisions that should be Antonello-reviewed
- TICKET B: production cron path, high-blast-radius — must be operator-driven
- TICKET C: sentinel is currently live; refactor needs staged rollout

## Loop gap status FINAL

- ✅ Gap 1 Cell silenti — closed empirically (seo-guardian emits to observatory)
- ✅ Gap 2 Consiglio — KILL revoked (live impl preserved)
- ✅ **Gap 3 HGT FASE 4** — **spec ready, 4.5d execution deferred to operator**
- ✅ Gap 4 Ghost MEMORY.md — replacement doc landed
- ✅ Gap 5 matagaruda double-firing — closed no-op (cicatrix already resolved)
- ✅ Gap 6 MATA GARUDA Gov 313 — apoptosi executed
- ✅ Gap 7 UUID Split-Brain — spec ready, 4-10h execution deferred

**ALL 7 gaps now closed or spec-ready**. SYMBIOSIS loop fully consolidated.

## Sources

1. `apps/crm-cell/crm_cell/hgt_publisher.py:51,79` (TICKET A current state)
2. `apps/bali-intel-scraper/backend/cell/runner.py:175` (TICKET B class def)
3. `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` grep IntelScraperCellRunner = 0 matches (TICKET B no import)
4. `apps/mata-garuda/scripts/run_sentinel_py.py:120-135` (TICKET C bypass verbatim)
5. Commit `68efc17e3` HGT HALT message (premises canonical)
6. PR #588 commit `687645bad` initial Gap 3 spec (superseded by this empirical refinement)
