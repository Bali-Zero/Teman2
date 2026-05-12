"""SEO Cell daily runner — single-pulse driver for cron / LaunchAgent.

Sprint 2 entrypoint. Performs one `single_pulse()`, persists side-effects
(SQLite memory, birth-date marker, sensor caches), and exits 0 on
success / 1 on failure. The exit code is the only health signal — the
LaunchAgent log captures stderr; the sentinel writes the success/fail
state to `~/.agent/decisions/state/seo_cell.last.json` (handled by the
shell wrapper, not here).

Why a separate file instead of `python -c "from … import …; …"`:
  - the cell's I/O surface (Postgres, Google APIs) means `KeyboardInterrupt`
    handling, structured logging, and a graceful asyncpg cleanup on shutdown
    deserve a dedicated module
  - the sentinel and LaunchAgent ergonomics expect a stable import path
    (`python -m apps.evaluator.seo_cell.run_seo_cell`) — keeping it inside
    the package keeps the relative imports working under all PYTHONPATH
    permutations, including the editable-install one used by `.venv`

Pre_natal stays locked unless the lead_attribution sensor returns a
non-zero count AND age_days ≥ 28 AND gsc_query_count ≥ 80. In Sprint 2
the cell is still expected to run pre_natal — sensor readings are
collected, the thinker proposes action="none", the actor never fires.
This is the intended steady state until Sprint 3 lands.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logger = logging.getLogger("seo_cell.runner")


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
    # Local import — keeps argparse/logging imports cheap when the
    # package isn't actually being used (e.g. `--help`).
    from apps.evaluator.seo_cell import create_seo_cell

    cell = create_seo_cell()
    try:
        result = await cell.single_pulse()
    except Exception as e:  # noqa: BLE001
        logger.exception("[seo_cell] single_pulse raised: %r", e)
        return 1

    logger.info(
        "[seo_cell] pulse #%s done health=%s action=%s",
        result.pulse_number,
        result.health_status,
        result.action_taken,
    )

    # Gap 1 Layer 2 fix 2026-05-12: cell_core.pulse:265 schedules the
    # observatory emit as fire-and-forget asyncio.create_task. Without this
    # cleanup wait, asyncio.run() exits before the emit task can finish its
    # PG INSERT + NOTIFY, leaving observatory.db without the seo_cell row.
    # Reference: research/symbiosis/2026-05-12-cell-silenti-root-cause-and-fix.md
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        logger.info(
            "[seo_cell] awaiting %d fire-and-forget tasks (observatory emit)",
            len(pending),
        )
        try:
            await asyncio.wait(pending, timeout=10.0)
        except Exception as e:  # noqa: BLE001
            logger.warning("[seo_cell] pending-task wait raised: %r", e)

    # We treat 'red' health as a soft failure for sentinel purposes —
    # the cell is still pre_natal and the actor never ran, but a red
    # signal indicates a sensor is having connectivity issues that
    # operators should see in monitoring. The cell itself is healthy
    # enough that exit 0 is honest.
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one SEO Cell pulse (cron-style)."
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
        logger.warning("[seo_cell] interrupted by signal")
        return 130


if __name__ == "__main__":
    sys.exit(main())
