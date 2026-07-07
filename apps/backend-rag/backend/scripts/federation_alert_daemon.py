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
import importlib.util
import logging
import os
import sys
import threading
import time
from pathlib import Path

from backend.services.federation_alerts import FADConfig, FederationAlertDaemon

ORGAN_ID = "pro.federation_alert_dispatcher"


def _load_organism_heartbeat():
    """Load scripts/lib/heartbeat.py (repo-root sidecar SSOT) if present.

    The daemon runs on Pro from the repo checkout; on Fly or in tests the
    lib may be absent — heartbeat degrades to a no-op, never a crash.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "scripts" / "lib" / "heartbeat.py"
        if not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location("nuzantara_heartbeat", candidate)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.organism_heartbeat

    def _noop(*_args, **_kwargs) -> bool:
        return False

    return _noop


organism_heartbeat = _load_organism_heartbeat()


def _configure_logging() -> None:
    level = os.environ.get("FEDERATION_ALERT_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _start_heartbeat_thread(interval_s: int = 60) -> None:
    def _loop() -> None:
        while True:
            organism_heartbeat(ORGAN_ID, "ok", "federation alert dispatcher running")
            time.sleep(interval_s)

    thread = threading.Thread(target=_loop, name="federation-alert-heartbeat", daemon=True)
    thread.start()


async def _main() -> int:
    _configure_logging()
    config = FADConfig.from_env()
    config.assert_required()
    daemon = FederationAlertDaemon(config)
    organism_heartbeat(ORGAN_ID, "starting", "daemon configured")
    _start_heartbeat_thread()
    await daemon.start()
    organism_heartbeat(ORGAN_ID, "ok", "daemon stopped cleanly")
    return 0


def main() -> int:
    try:
        return asyncio.run(_main())
    except KeyboardInterrupt:
        organism_heartbeat(ORGAN_ID, "ok", "keyboard interrupt")
        return 0
    except Exception as exc:
        organism_heartbeat(ORGAN_ID, "error", f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
