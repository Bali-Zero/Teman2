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
    # parents[3] = apps/, parents[4] = Desktop/nuzantara/
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
    from zantara_media.indexer.orchestrator import run_indexer
    from zantara_media.alerts import send_critical_alert

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
                f"⚠️ GARUDA indexer: {consecutive} errors in last run (worker={worker_name})"
            )

        # Check OAuth token expiry
        try:
            import asyncpg
            pg = await asyncpg.connect(dsn=os.environ.get("DATABASE_URL", ""))
            row = await pg.fetchrow(
                "SELECT expires_at FROM google_drive_tokens ORDER BY created_at DESC LIMIT 1"
            )
            if row and row["expires_at"]:
                from datetime import datetime, timezone
                days_left = (row["expires_at"] - datetime.now(tz=timezone.utc)).days
                if days_left < 7:
                    await send_critical_alert(
                        f"⚠️ GARUDA: Google Drive OAuth token expires in {days_left} days!\n"
                        f"Re-auth: https://kita.balizero.com/settings/integrations"
                    )
            await pg.close()
        except Exception as e:
            logger.warning("Could not check OAuth expiry: %s", e)

        return 0
    except Exception as e:
        logger.exception("Fatal error in indexer: %s", e)
        await send_critical_alert(f"💥 GARUDA indexer CRASHED: {e}")
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
