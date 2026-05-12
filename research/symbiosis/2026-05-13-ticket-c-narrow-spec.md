---
date: 2026-05-13
domain: symbiosis
client_case: SYMBIOSIS Phase 3 — TICKET C narrow spec v2 (post 4-panel)
status: spec-v2-execution-ready
empirical_survey_wita: 2026-05-13 01:40
review_completed_wita: 2026-05-13 01:50
---

# TICKET C — sentinel cell-aware entry (narrow spec v2)

**Date**: 2026-05-13 01:40 WITA · **Revised**: 01:55 WITA post-review
**Predecessor**: TICKET B EXECUTION merged (PR #639 → main `ad09a0876` at 01:33 WITA)
**Author**: Claude Opus 4.7 max
**Mode**: Narrow spec — code autonomous + OPERATOR-GATED plist swap (chmod 0444 workflow)
**Estimated effort**: ~5.25h (~0.7 day) code + 0.5h operator window
**Review status**: APPROVED with 9 corrections — Claude self PROCEED + Gemini PROCEED + DeepSeek PROCEED + NB-1 PROCEED (clone seo_cell pattern signal)

## Goal

Switch `com.matagaruda.sentinel.hourly` cron from legacy `run_sentinel_py.py` (bypass) to new `run_sentinel_cell.py` shim cloning canonical `apps/evaluator/seo_cell/run_seo_cell.py` pattern. Activates `PulseLoop.single_pulse()` lifecycle which internally consumes from `cell:skills` via HGTConsumer (lines 167-170 of sentinel_cell.py).

After plist swap + first hourly tick:

- `~/.cell-observatory/observatory.db` shows `cell_id='sentinel'` pulse events (currently 0 in 24h — verified empirically)
- `redis-cli XINFO GROUPS cell:skills` sentinel-1 group transitions to active (entries-read > 0, consumers ≥ 1 during tick)
- Sentinel consumes patterns from 2 publishers (crm-cell A.2 + intel-scraper-cell B) — completes FASE 4 lift criteria pipeline

## CRITICAL discovery (changes architecture)

**`apps/evaluator/seo_cell/run_seo_cell.py` ALREADY EXISTS** (111 LOC, verified empirically at 01:50 WITA via `ls -la`). NB-1 ground-truth signal: **clone this canonical pattern verbatim**, do not write naive shim.

The seo_cell file contains:

- argparse `--verbose` flag
- `_configure_logging()` LaunchAgent-aware (stdout + stderr merge)
- `_run_one_pulse()` async function with structured try/except + logging
- `main()` wrapping `asyncio.run(_run_one_pulse())` with KeyboardInterrupt → return 130
- **GAP 1 Layer 2 fix (2026-05-12)**: explicit `asyncio.all_tasks()` blanket wait with 10s timeout AFTER single_pulse() because _"cell_core.pulse:265 schedules the observatory emit as fire-and-forget asyncio.create_task. Without this cleanup wait, asyncio.run() exits before the emit task can finish its PG INSERT + NOTIFY"_

## OVERRIDE Phase 3 spec v2 CORR-9

Phase 3 spec v2 CORR-9 says: _"NO `asyncio.all_tasks()` blanket wait"_.

**This CORR-9 is INCORRECT**. Empirical evidence (seo_cell Gap 1 Layer 2 fix):

- `cell_core.pulse:265` schedules observatory emit as fire-and-forget `asyncio.create_task()`
- `asyncio.run()` shutdown sequence CANCELS pending tasks (DeepSeek F1 + Q2.3 confirmed)
- Without blanket wait, observatory emit task gets cancelled before sqlite/PG write completes
- Acceptance criterion #5 (observatory.db row written) FAILS

**TICKET C spec v2 OVERRIDES CORR-9**. Use `asyncio.all_tasks()` blanket wait with 10s timeout, exactly as seo_cell does. Reference: "Gap 1 Layer 2 fix 2026-05-12 (cloned from seo_cell precedent)".

## 4-panel review convergences applied (9 corrections)

| #   | Original spec v1                            | 4-panel verdict              | Correction in v2                                                                    |
| --- | ------------------------------------------- | ---------------------------- | ----------------------------------------------------------------------------------- |
| 1   | Naive shim with `await asyncio.sleep(0.1)`  | ALL 4 + NB-1 critical        | **CLONE seo_cell run_seo_cell.py pattern** verbatim                                 |
| 2   | `await cell.tick()` (Phase 3 spec v2 error) | Gemini F2 + DeepSeek F2      | `await cell.single_pulse()` (verified pulse.py:82)                                  |
| 3   | sleep_hours gap acceptable                  | Claude F2 + DeepSeek F2 HIGH | Relax success criterion: ">2h gap except during configured sleep window 02-06 WITA" |
| 4   | 6-step plist workflow                       | DeepSeek F4                  | **7-step**: add post-bootstrap log verification                                     |
| 5   | Test stubs without mocks                    | DeepSeek F6                  | Concrete mock implementations                                                       |
| 6   | plist EnvironmentVariables replace risk     | DeepSeek F7                  | Modify ONLY ProgramArguments, untouched env                                         |
| 7   | HGTConsumer methods unverified              | DeepSeek F3                  | **EMPIRICALLY VERIFIED**: ensure_group consumer.py:50, consume_once consumer.py:61  |
| 8   | asyncio.run() flushes pending tasks         | DeepSeek F1 CRITICAL         | OVERRIDE Phase 3 CORR-9 — use asyncio.all_tasks() blanket wait (seo_cell precedent) |
| 9   | sys.path manipulation risk                  | DeepSeek F5                  | **REJECTED** — necessary for direct script invocation, kept                         |

## Empirical state (2026-05-13 01:55 WITA — re-verified)

| Item                                                                            | Status                                        |
| ------------------------------------------------------------------------------- | --------------------------------------------- |
| A.0 → B sequence (PR #626 → #639)                                               | ✅ all merged                                 |
| `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py:46` create_sentinel_cell() | ✅ exists                                     |
| sentinel_cell.py:91/95 HGTConsumer init                                         | ✅ confirmed                                  |
| sentinel_cell.py:167-170 reflect phase ensure_group + consume_once              | ✅ confirmed                                  |
| `packages/cell-core/cell_core/pulse.py:82` single_pulse()                       | ✅ exists (NOT tick())                        |
| `packages/cell-core/cell_core/hgt/consumer.py:50` ensure_group()                | ✅ verified                                   |
| `packages/cell-core/cell_core/hgt/consumer.py:61` consume_once(count=10)        | ✅ verified                                   |
| `apps/evaluator/seo_cell/run_seo_cell.py` canonical pattern                     | ✅ EXISTS (111 LOC, 2026-05-12 14:43)         |
| `apps/mata-garuda/scripts/run_sentinel_py.py:120-135` legacy bypass             | ✅ confirmed (preserved)                      |
| plist ProgramArguments                                                          | invokes legacy run_sentinel_py.py             |
| plist EnvironmentVariables CELL_OBSERVATORY_EMIT=true                           | ✅ set Phase 1                                |
| observatory.db cell_id='sentinel' 24h count                                     | **0 events** (confirms bypass)                |
| sentinel-1 consumer group                                                       | 0 consumers, 0 pending, last-delivered-id=0-0 |
| redis-cli XLEN cell:skills                                                      | 18 (Phase 2.5 seed)                           |

## Implementation (Option C.1 clone seo_cell)

### File 1: `apps/mata-garuda/scripts/run_sentinel_cell.py` (NEW, ~110 LOC mirroring seo_cell)

```python
"""Sentinel Cell hourly runner — single-pulse driver for cron / LaunchAgent.

Phase 3 TICKET C — switches sentinel cron entry from legacy
``run_sentinel_py.py`` (bypass) to PulseLoop.single_pulse() invocation
via ``create_sentinel_cell()``. Activates HGTConsumer reflect phase
(sentinel_cell.py:167-170) which consumes from cell:skills sentinel-1
consumer group.

CLONE of ``apps/evaluator/seo_cell/run_seo_cell.py`` canonical pattern
(NB-1 ground-truth signal from 4-panel brainstorm 2026-05-13 01:50 WITA).
Includes Gap 1 Layer 2 fix (asyncio.all_tasks blanket wait) which
OVERRIDES Phase 3 spec v2 CORR-9 per empirical seo_cell precedent.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add apps/mata-garuda to sys.path so imports resolve from cron context
_PACKAGE_PATH = Path(__file__).resolve().parents[1]
if str(_PACKAGE_PATH) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PATH))

logger = logging.getLogger("sentinel_cell.runner")


def _configure_logging(verbose: bool) -> None:
    """Stdout for INFO+, stderr for WARNING+. LaunchAgent merges them."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.handlers = [handler]


async def _run_one_pulse() -> int:
    """Drive one PulseLoop.single_pulse() and exit with health-based code."""
    from mata_garuda.cells.sentinel_cell import create_sentinel_cell

    cell = create_sentinel_cell()
    try:
        result = await cell.single_pulse()
    except Exception as e:
        logger.exception("[sentinel] single_pulse raised: %r", e)
        return 1

    logger.info(
        "[sentinel] pulse #%s done health=%s action=%s halted=%s",
        result.pulse_number,
        result.health_status,
        result.action_taken,
        result.halted,
    )

    # Gap 1 Layer 2 fix 2026-05-12 (cloned from seo_cell):
    # cell_core.pulse:265 schedules observatory emit as fire-and-forget
    # asyncio.create_task. Blanket wait ensures it completes before
    # asyncio.run() destroys the event loop.
    # OVERRIDES Phase 3 spec v2 CORR-9.
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        logger.info("[sentinel] awaiting %d fire-and-forget tasks", len(pending))
        try:
            await asyncio.wait(pending, timeout=10.0)
        except Exception as e:
            logger.warning("[sentinel] pending-task wait raised: %r", e)

    return 0 if result.health_status != "red" else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one Sentinel Cell pulse (cron-style)."
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="DEBUG logging (default INFO).",
    )
    args = parser.parse_args()
    _configure_logging(args.verbose)

    try:
        return asyncio.run(_run_one_pulse())
    except KeyboardInterrupt:
        logger.warning("[sentinel] interrupted by signal")
        return 130


if __name__ == "__main__":
    sys.exit(main())
```

### File 2: plist swap (OPERATOR 7-step workflow)

```bash
# Step 1: Unlock plist
chmod u+w ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# Step 2: Modify ONLY ProgramArguments — point to run_sentinel_cell.py
plutil -replace ProgramArguments -json '[
  "/bin/bash",
  "-lc",
  "source ~/.nuzantara-secrets.env 2>/dev/null; /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_sentinel_cell.py"
]' ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# Step 3: plutil-lint sanity
plutil -lint ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# Step 4: Verify swap + EnvironmentVariables preserved
plutil -extract ProgramArguments xml1 -o - ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist | grep run_sentinel
plutil -extract EnvironmentVariables xml1 -o - ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist | grep CELL_OBSERVATORY_EMIT

# Step 5: Re-lock plist (chmod 0444 antibody restore)
chmod 0444 ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# Step 6: Pre-check no active cron tick
launchctl print gui/$(id -u)/com.matagaruda.sentinel.hourly | grep -i "state ="

# Step 7: bootout + bootstrap + log verification
launchctl bootout gui/$(id -u)/com.matagaruda.sentinel.hourly
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
sleep 5
launchctl print gui/$(id -u)/com.matagaruda.sentinel.hourly | head -30
```

**Rollback** (if next hourly tick fails):

```bash
chmod u+w ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
plutil -replace ProgramArguments -json '[
  "/bin/bash",
  "-lc",
  "source ~/.nuzantara-secrets.env 2>/dev/null; /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_sentinel_py.py"
]' ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
plutil -lint ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
chmod 0444 ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
launchctl bootout gui/$(id -u)/com.matagaruda.sentinel.hourly
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
```

### File 3: `apps/mata-garuda/tests/test_run_sentinel_cell.py` (4 tests, concrete mocks)

```python
"""Phase 3 TICKET C — run_sentinel_cell shim tests."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_run_one_pulse_returns_0_on_green_health():
    from scripts.run_sentinel_cell import _run_one_pulse
    mock_cell = MagicMock()
    mock_result = MagicMock(pulse_number=1, health_status="green",
                            action_taken="none", halted=False)
    mock_cell.single_pulse = AsyncMock(return_value=mock_result)
    with patch("mata_garuda.cells.sentinel_cell.create_sentinel_cell",
               return_value=mock_cell):
        assert await _run_one_pulse() == 0


@pytest.mark.asyncio
async def test_run_one_pulse_returns_1_on_red_health():
    from scripts.run_sentinel_cell import _run_one_pulse
    mock_cell = MagicMock()
    mock_result = MagicMock(pulse_number=2, health_status="red",
                            action_taken=None, halted=False)
    mock_cell.single_pulse = AsyncMock(return_value=mock_result)
    with patch("mata_garuda.cells.sentinel_cell.create_sentinel_cell",
               return_value=mock_cell):
        assert await _run_one_pulse() == 1


@pytest.mark.asyncio
async def test_run_one_pulse_returns_0_on_yellow_health():
    from scripts.run_sentinel_cell import _run_one_pulse
    mock_cell = MagicMock()
    mock_result = MagicMock(pulse_number=3, health_status="yellow",
                            action_taken="none", halted=False)
    mock_cell.single_pulse = AsyncMock(return_value=mock_result)
    with patch("mata_garuda.cells.sentinel_cell.create_sentinel_cell",
               return_value=mock_cell):
        assert await _run_one_pulse() == 0


@pytest.mark.asyncio
async def test_run_one_pulse_returns_1_on_exception():
    from scripts.run_sentinel_cell import _run_one_pulse
    mock_cell = MagicMock()
    mock_cell.single_pulse = AsyncMock(side_effect=RuntimeError("test"))
    with patch("mata_garuda.cells.sentinel_cell.create_sentinel_cell",
               return_value=mock_cell):
        assert await _run_one_pulse() == 1
```

## Acceptance criteria (v2)

1. ✅ CI tests green: `pytest apps/mata-garuda/tests/test_run_sentinel_cell.py -v` → 4/4
2. ✅ Regression: `pytest apps/mata-garuda/tests/ -v` → existing all green
3. ✅ Manual smoke (operator): `python -u scripts/run_sentinel_cell.py --verbose` → exit 0 + observatory.db row gained within 30s
4. ✅ Plist swap (operator 7-step workflow)
5. ✅ After first hourly tick post-swap:
   - observatory.db cell_id='sentinel' ≥1 row in last 1h (OUTSIDE sleep_hours 02-06)
   - sentinel-1 entries-read > 0 IF B/A.2 publishers have emitted (XLEN > 18)
   - sentinel-1 pending=0 post-tick
6. ✅ No regression in legacy run_sentinel_py.py
7. ✅ Success criterion #3 relaxed: ">2h gap except sleep_hours 02-06 window"

## Refusals (Phase 3 spec v2 §14)

- ❌ NO autonomous `launchctl bootstrap` (refusal #1)
- ❌ NO edits to `packages/cell-core/cell_core/hgt/*` (refusal #9)
- ❌ NO edits to `apps/evaluator/seo_cell/` (refusal #13)
- ❌ NO edits to `run_sentinel_py.py` (legacy preserved)
- ❌ NO edits to `sentinel_cell.py` (HGTConsumer already wired)
- ❌ NO HGT kill-switch lift
- ❌ NO edits to plist EnvironmentVariables (CORR-C6)
- **Phase 3 spec v2 CORR-9 OVERRIDDEN** per empirical seo_cell precedent

## Effort estimate (revised)

| Component                           | Hours                 |
| ----------------------------------- | --------------------- |
| Spec v2 (this doc)                  | 1                     |
| run_sentinel_cell.py clone seo_cell | 1.5                   |
| 4 unit tests concrete mocks         | 2                     |
| Plist 7-step workflow doc           | 0.5                   |
| Empirical verification              | 0.25                  |
| **Total v2**                        | **~5.25h (~0.7 day)** |

## Sequencing

A.0 ✅ → A.1 ✅ → A.2 ✅ → B ✅ → **C v2 code merge** (autonomous) → **operator plist swap** → first hourly tick → 14d soak → FASE 4 lift.

## Risks

| Risk                                | Severity | Mitigation                                                                      |
| ----------------------------------- | -------- | ------------------------------------------------------------------------------- |
| Observatory emit task cancelled     | CRITICAL | **MITIGATED**: asyncio.all_tasks() blanket wait 10s timeout (Gap 1 Layer 2 fix) |
| Sleep_hours 4h gap                  | HIGH     | **MITIGATED**: success criterion relaxed                                        |
| plist swap during active cron tick  | MEDIUM   | Step 6 pre-check launchctl print state                                          |
| HGTConsumer Redis connection leak   | MEDIUM   | sentinel_cell lazy redis client; asyncio.run() shutdown closes loop             |
| First tick during sleep_hours 02-06 | LOW      | halted=True / skipped=True; cron exits 0; next non-sleep tick produces events   |
| sentinel-1 entries-read=0           | LOW      | A.2 + B publishers active; first publisher event triggers consumer activation   |

## Brainstorm artifacts

Archive `docs/audits/2026-05-13-ticket-c-spec-brainstorm/`:

- 00_briefing.md
- 01_claude.md (5 findings)
- 02_gemini.md (F1 CRITICAL telemetry loss + F3 missing teardown)
- 03_deepseek.md (7 findings F1 CRITICAL + F2 HIGH gap)
- 04_nb1.md (CRITICAL signal: clone seo_cell pattern)
- 05_synthesis.md (9 corrections + CORR-9 OVERRIDE)

## Sources

1. `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py:46,91,95,167-170`
2. `packages/cell-core/cell_core/pulse.py:73,82`
3. `packages/cell-core/cell_core/hgt/consumer.py:50,61`
4. `apps/evaluator/seo_cell/run_seo_cell.py:1-111` (CANONICAL CLONE TARGET)
5. `apps/mata-garuda/scripts/run_sentinel_py.py:120-135`
6. `~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist`
7. `~/.cell-observatory/observatory.db` 24h sentinel events = 0
8. `redis-cli XINFO GROUPS cell:skills` sentinel-1 idle
9. Phase 3 spec v2: `docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md` (CORR-9 OVERRIDDEN)
10. Gap 1 Layer 2: `research/symbiosis/2026-05-12-cell-silenti-root-cause-and-fix.md`
11. PR chain: #626 → #629 → #632 → #635 → #636 → #637 → #639
12. 4-panel: `docs/audits/2026-05-13-ticket-c-spec-brainstorm/`
