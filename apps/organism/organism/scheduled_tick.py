"""Cron entrypoint — emits `scheduled_tick` event hourly.

Wire via crontab:
    0 * * * * PYTHONPATH=~/Desktop/nuzantara/apps/organism python3 -m organism.scheduled_tick

Supervisor L0 rules match {kind: scheduled_tick, payload.hour: N} or
{kind: scheduled_tick, payload.day_of_week: N} to trigger time-based
cleanup actuators.
"""
import asyncio
from datetime import datetime, timezone
from organism.emit import emit_event
from organism.schemas import Severity


async def main() -> None:
    now = datetime.now(timezone.utc)
    await emit_event(
        severity=Severity.INFO,
        source="cron.scheduled_tick",
        kind="scheduled_tick",
        payload={
            "hour": now.hour,
            "day_of_week": now.weekday(),  # Monday=0
            "ts_utc": now.isoformat(),
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
