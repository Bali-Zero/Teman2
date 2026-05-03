#!/usr/bin/env python3
"""
garuda-gc — Tombstone garbage collector (runs Sunday 05:00 WITA)
Sweeps garuda_index for files no longer on Drive, marks them archived.
Usage: garuda-gc [--dry-run] [--batch-size 100]
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path


def load_env() -> None:
    """Load environment variables from apps/backend-rag/.env if not already set."""
    candidates = [
        Path(__file__).parents[2] / ".env",
        Path(__file__).parents[3] / "backend-rag" / ".env",
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


async def async_main(dry_run: bool, batch_size: int) -> int:
    from zantara_media.maintenance.gc import run_gc
    from zantara_media.alerts import send_critical_alert

    logger = logging.getLogger("garuda-gc")
    logger.info("Starting GARUDA GC (dry_run=%s, batch_size=%d)", dry_run, batch_size)

    try:
        result = await run_gc(dry_run=dry_run, batch_size=batch_size)
        logger.info("GC completed: %s", result)
        return 0
    except Exception as e:
        logger.exception("GC failed: %s", e)
        await send_critical_alert(f"💥 GARUDA GC FAILED: {e}")
        return 1


def main() -> None:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="GARUDA tombstone garbage collector")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    sys.exit(asyncio.run(async_main(args.dry_run, args.batch_size)))


if __name__ == "__main__":
    main()
