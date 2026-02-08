#!/usr/bin/env python3
"""
Run The Generals Multi-Agent System

Starts Coding General, Intelligence General, and Antigravity General in background loops.
"""

import asyncio
import logging
import signal
import sys

from backend.generals.antigravity_general import AntigravityGeneral
from backend.generals.coding_general import CodingGeneral
from backend.generals.intelligence_general import IntelligenceGeneral

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class GeneralsRunner:
    """Manages running all three Generals."""

    def __init__(self):
        self.coding_general = CodingGeneral(poll_interval=5)
        self.intelligence_general = IntelligenceGeneral(poll_interval=5)
        self.antigravity_general = AntigravityGeneral(poll_interval=10)
        self.running = False

    async def start(self):
        """Initialize and start all Generals."""
        try:
            logger.info("🚀 Starting The Generals Multi-Agent System...")

            await self.coding_general.initialize()
            await self.intelligence_general.initialize()
            await self.antigravity_general.initialize()

            logger.info("✅ All three Generals initialized")

            # Start polling loops
            self.running = True
            await asyncio.gather(
                self.coding_general.run_loop(),
                self.intelligence_general.run_loop(),
                self.antigravity_general.run(),
                return_exceptions=True,
            )

        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested")
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
        finally:
            await self.stop()

    async def stop(self):
        """Stop all Generals."""
        logger.info("🛑 Stopping Generals...")
        self.running = False

        self.coding_general.stop()
        self.intelligence_general.stop()
        await self.antigravity_general.stop()

        await self.coding_general.close()
        await self.intelligence_general.close()

        logger.info("✅ Generals stopped")


def main():
    """Main entry point."""
    runner = GeneralsRunner()

    # Handle SIGINT (Ctrl+C) gracefully
    def signal_handler(sig, frame):
        logger.info("Received SIGINT, shutting down...")
        runner.running = False
        runner.coding_general.stop()
        runner.intelligence_general.stop()
        asyncio.create_task(runner.antigravity_general.stop())

    signal.signal(signal.SIGINT, signal_handler)

    try:
        asyncio.run(runner.start())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
        sys.exit(0)


if __name__ == "__main__":
    main()
