"""python -m cell_observatory — entrypoint for LaunchAgent."""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import structlog

from cell_observatory.collector import run_collector
from cell_observatory.api import run_api

structlog.configure(processors=[
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.JSONRenderer(),
])

log = structlog.get_logger()


def _hb(status: str, note: str = "") -> None:
    """Best-effort heartbeat for the Innervation Genoma sentinel.

    Writes ~/.organism/last_seen/cell.observatory.json. Never raises.
    """
    try:
        directory = Path.home() / ".organism" / "last_seen"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "cell.observatory.json"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {"ts": ts, "status": status, "note": str(note)[:500]}
        tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


async def _heartbeat_loop(interval_s: int = 60) -> None:
    """Periodic heartbeat tick for sentinel-aggregate."""
    while True:
        _hb("ok", "tick")
        try:
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            return


async def main():
    log.info("cell-observatory-collector starting", version="0.1.0")
    _hb("starting", "version=0.1.0")
    try:
        await asyncio.gather(run_collector(), run_api(), _heartbeat_loop())
    except Exception as exc:  # noqa: BLE001
        _hb("fail", f"exc={type(exc).__name__}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
