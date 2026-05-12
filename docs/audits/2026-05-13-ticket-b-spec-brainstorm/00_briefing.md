# TICKET B 4-Panel Brainstorm — Briefing

**Date**: 2026-05-13 00:55 WITA
**Spec under review**: research/symbiosis/2026-05-13-ticket-b-narrow-spec.md
**Predecessor**: TICKET A.2 EXECUTION merged (PR #636 → main `848e76a65` at 00:52 WITA)

## Context

TICKET B wires IntelScraperCellRunner into the production cron script `run_intel_pipeline.py`. Empirical re-verify (00:55 WITA) revealed an architectural CHALLENGE not foreseen by Phase 3 spec v2:

**`IntelPipeline.run()` at line 2019 is SYNC** (`def run(self):`), not async. Spec v2 §TICKET B assumed an async refactor was viable. EMPIRICAL: the script is 2158 LOC, procedural step-runner, calls subprocess for each of 8 pipeline steps.

`IntelScraperCellRunner.run()` is `@contextlib.asynccontextmanager` (line 202).

Spec v1 proposes **Option β: async sidecar** that runs in `asyncio.run()` AROUND the sync pipeline (~30 LOC addition + new file ~120 LOC, low blast radius).

## Empirical state (2026-05-13 00:55 WITA)

- A.0 ✅, A.1 ✅, A.2 ✅ all merged
- redis-cli XLEN cell:skills = 18 (will increment after A.2 first event burst)
- IntelScraperCellRunner exists at apps/bali-intel-scraper/backend/cell/runner.py:175
- run_intel_pipeline.py has 0 IntelScraperCellRunner imports (target of B)
- com.balizero.intel.nightly.plist HAS NO REDIS_URL env (default localhost = Pro Redis canonical)
- IntelPipeline.run() is SYNC, IntelScraperCellRunner.run() is ASYNC

## 4 candidate approaches (briefly)

- **α**: refactor IntelPipeline.run() to async (touches 2158 LOC, high blast)
- **β**: async sidecar AROUND sync pipeline (RECOMMENDED, ~150 LOC additive) ✅ spec v1
- **γ**: subprocess IPC after pipeline (state-file JSON read, IPC fragility)
- **δ**: ignore IntelScraperCellRunner entirely, emit directly via IntelScraperHGTBridge (loses scar/event bridging features)

## Spec v1 chose β

Reasoning:

1. Low blast radius (no edit to existing pipeline.run())
2. Reuses existing IntelScraperCellRunner async-context-manager shape
3. Failures bounded — try/except around asyncio.run() returns non-fatal warning
4. Pattern emission deferred to v2 (v1 ships counters only — proves pipeline)

## Reviewer questions

### For Gemini 3.1 Pro

Q1.1: α vs β vs γ vs δ — best for production cron blast radius?
Q1.2: Pattern emission deferral (v1 counters only) acceptable, or ship ≥1 pattern (e.g. source_reliability)?
Q1.3: `asyncio.run()` at end of main() — clean shutdown risk?

### For DeepSeek Reasoner

Q2.1: Verify file:line numbers (run_intel_pipeline.py:2019, runner.py:175, hgt_publisher.py:116).
Q2.2: pipeline.state['articles'] — does `source` field populate reliably across 8 steps?
Q2.3: Hidden coupling cell_post_emit + IntelScraperEventBridge.emit_run — DATABASE_URL env missing in cron context?

### For NB-1 (stale 2026-03-23 caveat)

Q3.1: IntelPipeline class sync/async on March 23 snapshot?
Q3.2: state['articles'] source field reliability?
Q3.3: Existing intel-scraper async wrappers known?

## Verdict format

PROCEED / PROCEED WITH CONDITIONS / WEAK / BLOCK + numbered findings + corrections + effort + risks.

## Reference

- Spec v1: research/symbiosis/2026-05-13-ticket-b-narrow-spec.md
- Parent Phase 3 spec v2: docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md
- A.0+A.1+A.2 merged sequence: PR #626 → #629 → #632 → #635 → #636
