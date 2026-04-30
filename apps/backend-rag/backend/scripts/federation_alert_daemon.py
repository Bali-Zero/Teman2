"""Entry point for the Federation Alert Dispatcher daemon.

Run via:
    python -m backend.scripts.federation_alert_daemon

The LaunchAgent plist at
``infra/launchagents/com.nuzantara.federation-alert-dispatcher.plist``
invokes this module on Pro at startup.

Configuration is read from environment variables (see
``backend/services/federation_alerts/config.py``). Defaults are safe:
mode=observe, dispatch unavailable → no actions, replay on boot.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

from backend.services.federation_alerts import FADConfig, FederationAlertDaemon


def _configure_logging() -> None:
    level = os.environ.get("FEDERATION_ALERT_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


async def _main() -> int:
    _configure_logging()
    config = FADConfig.from_env()
    config.assert_required()
    daemon = FederationAlertDaemon(config)
    await daemon.start()
    return 0


def main() -> int:
    try:
        return asyncio.run(_main())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
