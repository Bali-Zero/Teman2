"""Sentinel Cell hourly runner — single-pulse driver for cron / LaunchAgent.

Phase 3 TICKET C — switches sentinel cron entry from legacy
``run_sentinel_py.py`` (bypass) to ``PulseLoop.single_pulse()`` invocation
via ``create_sentinel_cell()``. Activates HGTConsumer reflect phase
(``sentinel_cell.py:167-170``) which consumes from ``cell:skills`` via
sentinel-1 consumer group.

This is a CLONE of ``apps/evaluator/seo_cell/run_seo_cell.py`` canonical
pattern (NB-1 ground-truth signal from 4-panel brainstorm 2026-05-13).
Boilerplate replicated verbatim for:

- KeyboardInterrupt handling (exit 130)
- structured logging stdout/stderr merge for LaunchAgent
- Gap 1 Layer 2 fix: ``asyncio.all_tasks()`` blanket wait with 10s timeout
  after ``single_pulse()`` so fire-and-forget observatory emit task
  completes before ``asyncio.run()`` destroys the event loop

The Gap 1 Layer 2 fix OVERRIDES Phase 3 spec v2 CORR-9 (which forbade
``asyncio.all_tasks``) per empirical evidence from the seo_cell
precedent. ``cell_core.pulse:265`` schedules observatory emit as
fire-and-forget ``asyncio.create_task``; without the blanket wait the
task gets cancelled before sqlite/PG write completes →
``observatory.db`` row LOST.

Layer A (plist target) and Layer B (script bypass) are BOTH fixed by
switching the plist ``ProgramArguments`` to invoke this file. The
legacy ``run_sentinel_py.py`` is preserved for manual debug
invocation.

Reference:
- Spec v2: ``research/symbiosis/2026-05-13-ticket-c-narrow-spec.md``
- Canonical pattern: ``apps/evaluator/seo_cell/run_seo_cell.py``
- Gap 1 Layer 2: ``research/symbiosis/2026-05-12-cell-silenti-root-cause-and-fix.md``
- Parent Phase 3 spec v2: ``docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md``
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add apps/mata-garuda to sys.path so imports resolve from cron context.
# Necessary because plist invokes the script directly (not via python -m).
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
    """Drive one PulseLoop.single_pulse() and exit with health-based code.

    Returns:
        0 if pulse health != 'red' (or single_pulse returned cleanly)
        1 on single_pulse exception or health == 'red'
    """
    # Local import — keeps argparse/logging imports cheap when --help.
    from mata_garuda.cells.sentinel_cell import create_sentinel_cell

    cell = create_sentinel_cell()
    try:
        result = await cell.single_pulse()
    except Exception as e:  # noqa: BLE001
        logger.exception("[sentinel] single_pulse raised: %r", e)
        return 1

    logger.info(
        "[sentinel] pulse #%s done health=%s action=%s halted=%s",
        result.pulse_number,
        result.health_status,
        result.action_taken,
        result.halted,
    )

    # Gap 1 Layer 2 fix 2026-05-12 (cloned from seo_cell run_seo_cell.py):
    # cell_core.pulse:265 schedules the observatory emit as fire-and-forget
    # asyncio.create_task. Without this cleanup wait, asyncio.run() exits
    # before the emit task can finish its PG INSERT + NOTIFY, leaving
    # observatory.db without the sentinel row.
    # OVERRIDES Phase 3 spec v2 CORR-9 (forbidding asyncio.all_tasks()
    # blanket wait) per empirical evidence from seo_cell precedent.
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        logger.info(
            "[sentinel] awaiting %d fire-and-forget tasks (observatory emit)",
            len(pending),
        )
        try:
            await asyncio.wait(pending, timeout=10.0)
        except Exception as e:  # noqa: BLE001
            logger.warning("[sentinel] pending-task wait raised: %r", e)

    # 'red' health is a soft failure — the cell is still running but a
    # sensor is having connectivity issues. cron exits 0 = healthy enough
    # to keep running. cron alerts (via shell wrapper) on non-zero exit.
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
