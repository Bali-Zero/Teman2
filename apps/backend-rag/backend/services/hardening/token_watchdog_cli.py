"""Cron entrypoint for TokenWatchdog — daily on Pro.

Probes configured token sources for expiry proximity. Alerts Zero when
tokens are within WARN (≤7d default) or CRITICAL (≤2d default) windows.

This CLI is intentionally minimal: it starts with an empty probe list so
the cron can run cleanly while probes are wired in incrementally. Add
probes for IG long-lived token, X bearer, LinkedIn, etc. here as they are
productionalised.

Usage:
    PYTHONPATH=. python -m backend.services.hardening.token_watchdog_cli

Env:
    TELEGRAM_BOT_TOKEN       (required)
    TELEGRAM_OWNER_CHAT_ID   (required)

Exit codes:
    0  sweep completed (including the "no probes configured" case — the
       cron loop still ran and logged)
    1  configuration error
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

from backend.services.hardening.token_watchdog import TokenProbe, TokenWatchdog
from backend.services.review.telegram_adapter import TelegramReviewAdapter

logger = logging.getLogger("hardening.token_watchdog.cli")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def _build_probes() -> list[tuple[str, TokenProbe]]:
    """Stub list; wire concrete probes (IG/X/LI) as they become available."""
    return []


async def run() -> int:
    _configure_logging()
    owner_chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
    if not owner_chat_id:
        logger.error("TELEGRAM_OWNER_CHAT_ID not set")
        return 1

    probes = _build_probes()
    telegram = TelegramReviewAdapter()
    watchdog = TokenWatchdog(
        probes=probes, telegram=telegram, owner_chat_id=owner_chat_id,
    )
    result = await watchdog.sweep_once()
    sys.stdout.write(
        json.dumps(
            {
                "ran_at": result.ran_at.isoformat(),
                "probes": len(probes),
                "reports_count": len(result.reports),
                "warnings_sent": result.warnings_sent,
                "errors_count": len(result.errors),
            },
            default=str,
        )
        + "\n"
    )
    return 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
