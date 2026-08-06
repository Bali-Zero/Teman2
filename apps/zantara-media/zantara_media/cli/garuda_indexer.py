#!/usr/bin/env python3
"""
garuda-indexer — GARUDA daily incremental indexer CLI
Usage: garuda-indexer [--worker WORKER_NAME] [--dry-run]
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path


# Load .env from apps/backend-rag/.env (sibling app)
def load_env() -> None:
    """Load environment variables from apps/backend-rag/.env if not already set."""
    # Structure: apps/zantara-media/zantara_media/cli/garuda_indexer.py
    # parents[0] = cli/, parents[1] = zantara_media/, parents[2] = zantara-media/,
    # parents[3] = apps/, parents[4] = nuzantara/
    candidates = [
        Path(__file__).parents[2] / ".env",                           # apps/zantara-media/.env
        Path(__file__).parents[3] / "backend-rag" / ".env",           # apps/backend-rag/.env
        Path.home() / "Desktop" / "nuzantara" / "apps" / "backend-rag" / ".env",
    ]
    for env_path in candidates:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        if key.strip() not in os.environ:
                            os.environ[key.strip()] = value.strip()
            break


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def async_main(worker_name: str, dry_run: bool) -> int:
    from zantara_media.alerts import send_critical_alert
    from zantara_media.indexer.orchestrator import run_indexer

    logger = logging.getLogger("garuda-indexer")
    logger.info("Starting GARUDA indexer (worker=%s, dry_run=%s)", worker_name, dry_run)

    if dry_run:
        logger.info("DRY RUN — not connecting to any real services")
        return 0

    try:
        result = await run_indexer(worker_name=worker_name)
        logger.info("Indexer completed: %s", result)

        # Alert if too many consecutive failures
        consecutive = result.get("errors", 0)
        if consecutive >= 3:
            await send_critical_alert(
                f"⚠️ GARUDA indexer: {consecutive} errors in last run (worker={worker_name})",
                condition="indexer-errors",
            )

        # The OAuth expiry check that used to live here is DELETED, 2026-08-06.
        #
        # It read `SELECT expires_at ... ORDER BY created_at DESC LIMIT 1` and
        # alerted when `(expires_at - now).days < 7`. But `expires_at` is the
        # **one-hour access token**, not a 90-day credential clock
        # (google_drive_service.py:163 — `now + expires_in (3600)`; measured
        # live, `expires_at - updated_at == 1h` on every row). So `days_left`
        # was 0 at best and negative the rest of the time: the condition was
        # **always true**, and the only reason this did not fire nightly is
        # that the indexer crashes upstream before reaching it.
        #
        # It is not replaced here, for two reasons.
        #
        # 1. This check cannot see the failure it was written for. A REVOKED
        #    refresh token still sits in the column: on 2026-08-05 Google
        #    answered `invalid_grant: Token has been expired or revoked` while
        #    the row looked perfectly populated. No query against this table
        #    can tell a live credential from a dead one — only an attempt can,
        #    and this indexer already makes one every night.
        # 2. One owner per condition. `scripts/drive_token_watchdog.py` owns
        #    the credential's health; a second organ guessing at it in
        #    parallel, on the wrong scale, is noise that trains the reader to
        #    ignore the real thing.
        #
        # What DOES report the credential here is the crash path below — the
        # RefreshError propagates and `send_critical_alert` names it.

        return 0
    except Exception as e:
        logger.exception("Fatal error in indexer: %s", e)
        await send_critical_alert(
            f"💥 GARUDA indexer CRASHED: {e}", condition="indexer-crash"
        )
        return 1


def main() -> None:
    load_env()

    parser = argparse.ArgumentParser(description="GARUDA daily incremental indexer")
    parser.add_argument("--worker", default="default", help="Worker name for advisory lock")
    parser.add_argument("--dry-run", action="store_true", help="Skip all real operations")
    parser.add_argument("--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    setup_logging(args.verbose)
    sys.exit(asyncio.run(async_main(args.worker, args.dry_run)))


if __name__ == "__main__":
    main()
