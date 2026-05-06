#!/usr/bin/env python3
"""
Consiglio v1 — Weekly cron script.

Runs via LaunchAgent: com.matagaruda.council.weekly.plist
Schedule: Sunday 10:00 WITA (Air)

Flow:
1. Auto-select topic from escalations/MOS
2. Run council deliberation
3. Send report to Zero via Telegram
4. Exit
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ensure mata_garuda package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.council.delivery import format_telegram_report, send_to_zero
from mata_garuda.council.orchestrator import CouncilOrchestrator
from mata_garuda.council.topics import TopicSelector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("council_weekly")


async def main() -> int:
    logger.info("Council weekly run starting")

    selector = TopicSelector()
    topic = selector.auto_select()

    if not topic:
        logger.info("No pending topics. Skipping.")
        return 0

    logger.info(f"Topic: {topic.title} (source: {topic.source})")

    orchestrator = CouncilOrchestrator()
    decision = await orchestrator.deliberate(topic)

    report = format_telegram_report(decision)
    logger.info(f"Decision:\n{report}")

    sent = send_to_zero(decision)
    logger.info(f"Telegram: {'sent' if sent else 'FAILED'}")

    orchestrator.store.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
