# Phase 3 HGT Execution Spec — 4-Panel Review Briefing

**Date**: 2026-05-12 21:35 WITA
**Spec under review**: `/Users/nuzantara/Desktop/nuzantara/docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md`
**Predecessor spec**: `/Users/nuzantara/Desktop/nuzantara/research/symbiosis/2026-05-12-gap3-hgt-3tickets-empirical-spec.md`
**Phase 2 closure**: `/Users/nuzantara/Desktop/nuzantara/research/symbiosis/2026-05-12-phase2-live-execution-complete.md`

## Context

This is **Phase 3 of the SYMBIOSIS organism turn-on**. Phase 1 (visibility/stability, plist EMIT-true) and Phase 2 (core plumbing, events_outbox drain + cell:skills seed) are complete on `main`.

**Goal of Phase 3**: lift the HGT HALT (commit `68efc17e3`, 2026-05-08) so the cell:skills Redis stream is fed by ≥2 production publishers (intel-scraper-cell + optionally crm-cell) AND consumed by sentinel cell PulseLoop.

**Empirical state right now (2026-05-12 21:00 WITA)**:

- `redis-cli XLEN cell:skills` = **18** (Phase 2.5 seed, unchanged)
- `redis-cli XINFO GROUPS cell:skills` → sentinel-1 group exists, 0 consumers, lag=18, pending=0, last-delivered-id=0-0 (NEVER consumed)
- 3 HGT HALT premises (crm_cell stub line 79, IntelScraperCellRunner zero production import, run_sentinel_py.py:120-135 bypass) ALL still valid 4 days after HALT commit
- 4 plists EMIT=true (seo-cell.daily, seo-cell.28d-check, sentinel.hourly, cell.organism)
- Observatory.db 24h: cell=1166 events, seo-guardian=3 events

## 3 tickets in the spec

- **TICKET A** (1.5 days) — split A.1 (publisher refactor, 1 day, autonomous-capable) + A.2 (production caller wire, 0.5 day, operator-gated)
- **TICKET B** (1 day) — wire IntelScraperCellRunner into run_intel_pipeline.py + 4 integration tests + 3 dry-run nights before production
- **TICKET C** (2 days) — new shim `run_sentinel_cell.py` invoking `create_sentinel_cell().tick()` + plist swap (operator)

Total ~5 days code + 7 day soak + 0.5 day FASE 4 lift.

## 6 cross-file discoveries (from reading actual source code, NOT in Gap 3 spec)

1. **CrmHGTPublisher.publish() is SYNC**, IntelScraperHGTBridge.publish() is ASYNC — schema-divergence
2. **CrmHGTPublisher StructuralPattern schema** does NOT match cell_core.hgt canonical 9-field shape
3. **`crm` domain not registered** in `cell_core.hgt.domains`
4. **sentinel_cell.py ALREADY wires HGTConsumer** (line 25/91/95/167-170) — consumer side ready, only entry script bypass
5. **IntelScraperHGTBridge accesses HGTPublisher private attribute** (`publisher._cell_name`) — code smell
6. **TICKET A production caller is the actual hard problem** — defer A.2 to operator decision

## Reviewer questions (the spec asks each panelist 4 specific questions)

### For Gemini 3.1 Pro (Q1.1-1.4)

- Is `CrmHGTBridge` (Option A.γ) right, or mirror intel-scraper-cell shape verbatim (A.β)?
- Sync compatibility shim worth the cognitive load or break test_stubs.py?
- TICKET B staged rollout (3 dry-runs) sufficient?
- 7-day soak adequate or longer needed?

### For DeepSeek Reasoner (Q2.1-2.4)

- Verify line numbers cited match on-disk
- Mini Redis split-brain — does TICKET B `_make_cell_runner()` use the right REDIS_URL (100.93.236.6 vs localhost)?
- Sync shim async loop nesting safety
- XLEN cell:skills delta calibration (18→28 in 7 days)

### For NB-1 ground truth (Q3.1-3.4)

- Where in apps/backend-rag/backend/services/crm/ does StructuralPattern naturally arise?
- Right place to register "crm" domain in cell_core.hgt?
- Does apps/cell-core/hgt_coordinator/ graduation mechanism actually exist?
- Other cells/runners affected by A/B/C not mentioned?

## Verdict format requested

Each reviewer SHOULD produce a verdict:

- **PROCEED**: spec is sound, execute as-is
- **PROCEED WITH CONDITIONS**: spec OK but apply N corrections
- **WEAK**: spec has issues, need 3-5 corrections before execution
- **BLOCK**: spec has fundamental flaw, rewrite required

Plus enumerated findings (numbered Q1.1, Q1.2, ... or F1, F2, F3, ...) with for each:

- Finding statement
- Evidence (line number / commit / external reference)
- Severity (critical / high / medium / low)
- Recommended action

## Pattern history

Phase 2 spec went WEAK after 4-panel (Gemini BLOCK → DeepSeek WEAK → NB-1 PROCEED with conditions). 7 corrections applied, then PROCEED. Phase 2 live execution succeeded.

Phase 1 was executed WITHOUT 4-panel review and got verdict WEAK at closure-doc time AFTER the work was done. Pattern lesson: NEVER execute before review.

## What this review SHOULD NOT do

- Do NOT propose code changes outside the spec scope (no scope creep into Phase 4 / Phase 5)
- Do NOT recommend reactivating decommissioned components (apps/mata-garuda/.disabled-2026-05-06/council/)
- Do NOT propose anything that violates CLAUDE.md hard rules (Anthropic OAuth-only, no paid Anthropic API, no edits to dependencies.py SPOF, etc.)

## Reference

- Spec v1 (under review): `docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md`
- Empirical predecessor: `research/symbiosis/2026-05-12-gap3-hgt-3tickets-empirical-spec.md`
- Phase 2 closure: `research/symbiosis/2026-05-12-phase2-live-execution-complete.md`
- Phase 2 spec v2: `docs/superpowers/specs/2026-05-12-phase2-core-plumbing-fix-spec.md`
- HGT HALT commit: `68efc17e3` (use `git show 68efc17e3` for full message)
- CLAUDE.md rules: `/Users/nuzantara/Desktop/nuzantara/CLAUDE.md`
- SYMBIOSIS.md principles: `/Users/nuzantara/Desktop/nuzantara/SYMBIOSIS.md`
