# TICKET C 4-Panel Brainstorm — Briefing

**Date**: 2026-05-13 01:45 WITA
**Spec under review**: research/symbiosis/2026-05-13-ticket-c-narrow-spec.md
**Predecessor**: TICKET B EXECUTION merged (PR #639 → main ad09a0876 at 01:33 WITA)

## Context

TICKET C is the FINAL piece of Phase 3 — wires the sentinel consumer side. Switches `com.matagaruda.sentinel.hourly` cron from legacy `run_sentinel_py.py` (bypass, no PulseLoop) to new `run_sentinel_cell.py` shim that drives `create_sentinel_cell().single_pulse()`. After plist swap + first hourly tick:

- observatory.db gains cell_id='sentinel' events (currently 0 in 24h)
- sentinel-1 consumer group transitions from idle to active (entries-read > 0)
- 14-day soak begins; cell:skills has 2 publishers (crm-cell A.2 + intel-scraper B) feeding the consumer

## CRITICAL discovery (vs Phase 3 spec v2)

Phase 3 spec v2 §TICKET C says `await cell.tick()`. EMPIRICAL: PulseLoop at `packages/cell-core/cell_core/pulse.py:82` exposes `async def single_pulse() -> PulseResult`, NOT `tick()`. Spec v1 corrects to `single_pulse()`.

## Empirical state (2026-05-13 01:45)

- A.0 ✅, A.1 ✅, A.2 ✅, B ✅ all merged
- sentinel_cell.py:46 create_sentinel_cell() exists
- HGTConsumer wired lines 25/91/95/126/136/141/167-170
- run_sentinel_py.py:120-135 legacy bypass (Normalizer→Scorer→NLM Feeder→Digest)
- plist invokes run_sentinel_py.py legacy
- observatory.db cell_id='sentinel' 24h = 0 events
- sentinel-1 consumer group: 0 consumers, 0 pending, last-delivered-id=0-0 (never consumed)
- redis-cli XLEN cell:skills = 18 (Phase 2.5 seed)
- CELL_OBSERVATORY_EMIT=true in plist env

## Architecture (Option C.1 minimal)

- NEW run_sentinel_cell.py shim (~30 LOC):
  - asyncio.run(main()) wraps create_sentinel_cell().single_pulse()
  - Returns 0 if health != 'red', else 1
  - NO asyncio.all_tasks() blanket wait (CORR-9)
- 6-step OPERATOR plist swap workflow (chmod 0444 antibody restore)
- 4 unit tests
- Rollback procedure documented

## Reviewer questions

### Gemini Q1.1-Q1.3

- C.1 minimal shim vs C.2 full refactor (sensors)?
- cron hourly + single_pulse() vs cell.run() with 5-min loop?
- sleep_hours (02-06) creates 4h gap — accettare o lossen success criteria?

### DeepSeek Q2.1-Q2.3

- Verify cited file:line numbers
- Method name correction (tick → single_pulse) — other Phase 3 spec method errors?
- Fire-and-forget observatory emit — asyncio.run() awaits before returning?

### NB-1 Q3.1-Q3.3 (stale 2026-03-23 caveat)

- create_sentinel_cell + HGTConsumer wiring already in March 23 snapshot?
- sentinel single_pulse() runs cleanly under cron historically?
- Existing test patterns for cron-invoked PulseLoop scripts?

## Verdict format

PROCEED / PROCEED WITH CONDITIONS / WEAK / BLOCK + numbered findings + corrections + effort + risks.

## References

- Spec v1: research/symbiosis/2026-05-13-ticket-c-narrow-spec.md
- Phase 3 spec v2: docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md
- A.0 → B sequence: PR #626 → #629 → #632 → #635 → #636 → #637 → #639
