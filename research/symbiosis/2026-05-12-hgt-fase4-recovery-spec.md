---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS gap-closure loop · Step 3 · Gap 3 HGT FASE 4 HALT recovery
sources: 8
status: draft
loop_step: 3
loop_branch: feat/symbiosis-loop-2026-05-12
mode: doc-only (no runtime HGT activation)
---

# HGT FASE 4 HALT — Recovery Spec (3 prerequisite tickets)

**Generated**: 2026-05-12 03:10 WITA · Step 3 of SYMBIOSIS gap-closure loop · branch `feat/symbiosis-loop-2026-05-12`.

## Terminology note (clarified after NB-1 review 2026-05-12 04:15 WITA)

"FASE 4 HGT" in this doc refers to the local sequencing of `docs/SYMBIOSIS_TURNON_PLAN.md` (6 maggio 2026) which defines 4 phases for Innervation Genoma activation. It is NOT the canonical Nuzantara "Phase 4" — NB-1 explicitly clarifies that the canonical product-architecture sequencing is **Phase 0.5 → Phase 5 → Phase 3** (`0.5a UUID SSOT critical blocker for Phase 3 SurfaceRouter; Phase 5 CSCP keeps surfaces consistent`).

When this doc says "activate FASE 4" or "FASE 4 HALT", read it as: "lift the HALT on the SYMBIOSIS_TURNON_PLAN.md Phase 4 = HGT activation phase", a SYMBIOSIS-local milestone independent from the canonical Phase 0.5/3/5 product roadmap.

## Terminology note (clarified after NB-1 review 2026-05-12 04:15 WITA)

"FASE 4 HGT" in this doc refers to the local sequencing of `docs/SYMBIOSIS_TURNON_PLAN.md` (6 maggio 2026) which defines 4 phases for Innervation Genoma activation. It is NOT the canonical Nuzantara "Phase 4" — NB-1 explicitly clarifies that the canonical product-architecture sequencing is **Phase 0.5 → Phase 5 → Phase 3** (`0.5a UUID SSOT critical blocker for Phase 3 SurfaceRouter; Phase 5 CSCP keeps surfaces consistent`).

When this doc says "activate FASE 4" or "FASE 4 HALT", read it as: "lift the HALT on the SYMBIOSIS_TURNON_PLAN.md Phase 4 = HGT activation phase", a SYMBIOSIS-local milestone independent from the canonical Phase 0.5/3/5 product roadmap.

## Context

Commit `68efc17e3` (2026-05-08 01:39:20 +0800) declared HGT FASE 4 activation HALT with the message:

> The brief assumed two publishers (crm-cell, bali-intel-scraper) had runnable `__main__` entry points and a consumer needed only launchd wiring. Pre-spawn investigation found:
>
> - `apps/crm-cell/crm_cell/hgt_publisher.py` is a STUB (line 79: "Sprint 4: call into self.\_hgt_stream.xadd(...)"); never writes to Redis. No `__main__`, no production caller in the monorepo.
> - `apps/bali-intel-scraper/backend/cell/hgt_publisher.py` is a library class. No `__main__`. The integration class `IntelScraperCellRunner` is shelf-ready but not invoked by `scripts/run_intel_pipeline.py`.
> - `HGTConsumer` is wired in `mata_garuda/cells/sentinel_cell.py` but the loaded sentinel cron uses a different entry script that bypasses the cell layer entirely.

**Verified empirically 2026-05-12 03:10 WITA**: all 3 premises still hold. This spec documents the 3 prerequisite tickets that must close BEFORE any FASE 4 activation attempt.

## Verification details (2026-05-12)

### Prereq violation 1 — `crm-cell` publisher is STUB

`apps/crm-cell/crm_cell/hgt_publisher.py` line 79 (read 2026-05-12):

```python
        logger.info(
            "[STUB] hgt: pattern %s would publish (confidence=%s, payload=%s)",
            pattern.pattern_kind, pattern.confidence, pattern.payload,
        )
        # Sprint 4: call into self._hgt_stream.xadd(...)
        return True
```

The class returns `True` (caller thinks publish succeeded) but never calls `xadd`. No Redis stream entry produced. The init signature accepts `hgt_stream=None` and never validates it.

`grep -r "CrmHGTPublisher" apps/crm-cell apps/backend-rag` returns nothing in production callers — the publisher is defined but never invoked.

### Prereq violation 2 — `bali-intel-scraper` runner shelf-ready, not invoked

`apps/bali-intel-scraper/backend/cell/runner.py` defines `IntelScraperCellRunner` (verified via 4 references in `tests/unit/cell/test_runner.py:29,54,214,260,290`). However:

- `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` does NOT import from `backend.cell.runner`. Verified via `grep "IntelScraperCellRunner\|cell.runner\|from backend.cell" apps/bali-intel-scraper/scripts/run_intel_pipeline.py` returns 0.
- The pipeline orchestrator runs 8 steps (Scraping → Validation → Filter → Enrichment → SEO → Approval → Images → Publishing) entirely outside the cell-core boundary.

So `IntelScraperCellRunner` exists, has tests, but is not invoked in any production code path.

### Prereq violation 3 — Sentinel cron entry bypasses cell layer

`launchctl list | grep sentinel`:

```
2402	0	com.balizero.research-sentinel
```

`~/Library/LaunchAgents/com.balizero.research-sentinel.plist` `ProgramArguments`:

```
['/bin/zsh', '-lc', 'set -a; [ -f /Users/nuzantara/.nuzantara-secrets.env ] && source /Users/nuzantara/.nuzantara-secrets.env; set +a; /Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 /Users/nuzantara/scripts/eventbus/research_sentinel.py >> /Users/nuzantara/logs/research-sentinel.log 2>&1']
```

The cron runs `~/scripts/eventbus/research_sentinel.py` (operator-side script). NOT `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py`. The cell-core SentinelCell with its `HGTConsumer` wiring is dormant.

**Two-layer bypass clarified after NB-1 review 2026-05-12 04:15 WITA**:

- **Layer A** (plist level): the operator plist invokes `~/scripts/eventbus/research_sentinel.py`, completely outside the `apps/mata-garuda/mata_garuda/cells/` tree.
- **Layer B** (Python entrypoint level, canonical per NB-1 R6 audit): even `apps/mata-garuda/scripts/run_sentinel_py.py:126` (the in-repo wrapper that DOES live in mata-garuda) is itself a partial bypass — it instantiates the SentinelCell but **calls a legacy worker directly without going through `PulseLoop.tick()`**, so the REFLECT phase (where skills + HGT publish hooks live) NEVER fires. NB-1 marks this as `🔵 LOW (2) Cell metaphor decorative — REFLECT (skill producer) never fires → explains why Skills layer is empty (R4 finding root cause)`.

So TICKET C below must address BOTH layers:

- Layer A: switch the plist to a sentinel-cell-aware entrypoint (or replace the operator-side script entirely)
- Layer B: fix `run_sentinel_py.py:126` to actually invoke `pulse_loop.tick()` (full sense→think→act→reflect→dream→mature lifecycle), not the legacy bypass call

**Two-layer bypass clarified after NB-1 review 2026-05-12 04:15 WITA**:

- **Layer A** (plist level): the operator plist invokes `~/scripts/eventbus/research_sentinel.py`, completely outside the `apps/mata-garuda/mata_garuda/cells/` tree.
- **Layer B** (Python entrypoint level, canonical per NB-1 R6 audit): even `apps/mata-garuda/scripts/run_sentinel_py.py:126` (the in-repo wrapper that DOES live in mata-garuda) is itself a partial bypass — it instantiates the SentinelCell but **calls a legacy worker directly without going through `PulseLoop.tick()`**, so the REFLECT phase (where skills + HGT publish hooks live) NEVER fires. NB-1 marks this as `🔵 LOW (2) Cell metaphor decorative — REFLECT (skill producer) never fires → explains why Skills layer is empty (R4 finding root cause)`.

So TICKET C below must address BOTH layers:

- Layer A: switch the plist to a sentinel-cell-aware entrypoint (or replace the operator-side script entirely)
- Layer B: fix `run_sentinel_py.py:126` to actually invoke `pulse_loop.tick()` (full sense→think→act→reflect→dream→mature lifecycle), not the legacy bypass call

## The 3 prerequisite tickets

### TICKET A — Implement `crm_cell/hgt_publisher.py` xadd + production caller

**Scope**:

1. Replace the line 79 comment `# Sprint 4: call into self._hgt_stream.xadd(...)` with a real Redis stream xadd
2. Validate `self._hgt_stream is not None` at init time; raise if missing
3. Find at least 1 production caller in `apps/crm-cell` or `apps/backend-rag/backend/services/crm/` that creates a `StructuralPattern` and calls `publish()`

**Acceptance criteria**:

- Unit test: `tests/unit/test_hgt_publisher.py` (does not exist yet) → 5 tests covering: confidence floor, PII guard, xadd call, missing stream raises, payload schema.
- Integration test: real Redis (test container) shows entry in `cell:skills` stream after publish.
- Production caller produces at least 1 pattern per day under realistic load (verified post-deploy via `XLEN cell:skills`).

**Effort estimate**: 1-2 days. Most code already in place; missing piece is the production caller's pattern-discovery logic + Redis container test.

**Risk**: low. The stub is fail-safe (logs and returns True without side effects). Replacing the comment with real xadd adds a new dependency on Redis being available — graceful degradation handled by `try/except` around `xadd` and best-effort return.

**Refusal in this loop**: NO autonomous implementation. Doc only. Implementation requires Sprint 4-grade design review + Redis test container setup that is out of scope for a 3h gap-closure loop.

### TICKET B — Wire `IntelScraperCellRunner` into `run_intel_pipeline.py`

**Scope**:

1. Add `from backend.cell.runner import IntelScraperCellRunner` to `apps/bali-intel-scraper/scripts/run_intel_pipeline.py`
2. Instantiate the runner once per pipeline invocation with the configured scar_recorder + hgt_bridge + event_bridge
3. After each major pipeline step (validation, filter, enrichment, SEO), invoke `runner.run(step_outcome)` so the cell layer observes the structural events
4. The runner's reflect step extracts structural patterns and feeds them to the HGT publisher

**Acceptance criteria**:

- `run_intel_pipeline.py` import of `IntelScraperCellRunner` returns 1 grep match
- Unit test extends `tests/unit/cell/test_runner.py` to cover pipeline-step integration shape
- E2E smoke: `python scripts/run_intel_pipeline.py --mode dry-run --limit 1` produces at least 1 `cell_pulse_observed` event in the local SQLite observatory

**Effort estimate**: 1 day. The runner already has tests; main work is the cycle into 4 pipeline steps + adapter to convert step_outcome → cell pulse input.

**Risk**: medium. Adding the cell layer to a live production pipeline introduces failure modes (cell exception masks pipeline error). Mitigation: wrap `runner.run()` in `try/except` and log to scar_recorder rather than crashing the pipeline.

**Refusal in this loop**: NO autonomous implementation. The wiring change touches a production cron path (intel scraper at 03:00 WITA) — out of scope.

### TICKET C — Switch sentinel cron entry to cell-core SentinelCell

**Scope**:

Option C.1 (low-risk migration):

1. Create new plist `~/Library/LaunchAgents/com.balizero.mata-garuda-sentinel.hourly.plist` (or repo-side `infra/launchagents/`) that invokes `apps/mata-garuda/scripts/run_sentinel_py.py`
2. Keep existing `com.balizero.research-sentinel` plist running in parallel for 1 week as fallback
3. After 1 week of clean runs in `~/logs/matagaruda-sentinel.log`, bootout the legacy plist

Option C.2 (atomic switch — riskier):

1. Edit `~/scripts/eventbus/research_sentinel.py` to delegate to `mata_garuda.cells.sentinel_cell.create_sentinel_cell()` and run one pulse
2. Keep operator-side script as launcher, but cell-core as the engine

**Acceptance criteria**:

- After switch: SentinelCell `HGTConsumer` is active, validated by `redis-cli XLEN cell:skills` showing growth when TICKET A + B publish
- `~/.cell-observatory/observatory.db` shows `cell_id='sentinel'` pulse events
- No regression in research-sentinel functionality (whatever it does today must still happen)

**Effort estimate**: 0.5 day for Option C.1, 1 day for Option C.2.

**Risk**:

- C.1 medium: two plists running concurrently for 1 week may cause double-firing of any sentinel side effects (Telegram alerts, etc.). Triage which side effects are exposed.
- C.2 high: live edit of operator-side script with no rollback path is fragile.

**Refusal in this loop**: NO autonomous plist install or operator-side script edit. PLIST CORRUPTION SCAR mandates manual user action.

## Sequencing: A → B → C → activate FASE 4

The HALT premise will be lifted ONLY when all 3 prerequisites are closed AND:

1. `redis-cli XLEN cell:skills` shows ≥10 entries from `crm_cell.hgt` and `intel_scraper_cell.hgt` in a 7-day window (proves publishers work end-to-end)
2. `redis-cli XLEN cell:skills` consumer-group state shows `sentinel-1` consumer actively consuming with `pending=0` (proves HGTConsumer wired)
3. `~/.cell-observatory/observatory.db` shows pulse events with `payload_json` references to HGT skills (proves the consumer integrates skills into sentinel cell)

When all 3 hold, the existing `apps/cell-core/hgt_coordinator/` quarantine mechanism can graduate the verified-good skills from propose-only to applied — that's the FASE 4 promise.

## Why doc-only this loop

This loop is 3h wall-clock with mixed mode. The 3 tickets above add up to ~3-5 person-days each, even before integration testing. Out of scope.

The value of THIS step is: a verifiable, dated, fact-checked spec that the next implementer (Antonello or contracted dev) can pick up without redoing the HALT-root-cause analysis.

## What this step does NOT do

1. **NO** runtime HGT activation
2. **NO** edit of `crm_cell/hgt_publisher.py` stub
3. **NO** edit of `run_intel_pipeline.py`
4. **NO** new plist install
5. **NO** edit of operator-side `~/scripts/eventbus/research_sentinel.py`

## Sources

1. Commit `68efc17e3` HALT message (verified 2026-05-12 via `git log -1 68efc17e3 --format=%b`)
2. `apps/crm-cell/crm_cell/hgt_publisher.py` lines 60-85 (read 2026-05-12)
3. `apps/bali-intel-scraper/backend/cell/hgt_publisher.py` (read 2026-05-12)
4. `apps/bali-intel-scraper/backend/cell/runner.py:5,77` (`IntelScraperCellRunner` class)
5. `apps/bali-intel-scraper/tests/unit/cell/test_runner.py:29,54,214,260,290` (5 references — tests exist, production doesn't)
6. `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` (grep returns 0 for `cell.runner` import)
7. `~/Library/LaunchAgents/com.balizero.research-sentinel.plist` ProgramArguments
8. `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py:46-208` (cell-core SentinelCell with HGTConsumer wired)
