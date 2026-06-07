"""Cron entrypoint — emits `scheduled_tick` event hourly.

Wire via crontab:
    0 * * * * PYTHONPATH=~/Desktop/nuzantara/apps/organism python3 -m organism.scheduled_tick

Supervisor L0 rules match {kind: scheduled_tick, payload.hour: N} or
{kind: scheduled_tick, payload.day_of_week: N} to trigger time-based
cleanup actuators.
"""
import asyncio
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

from organism.emit import emit_event
from organism.schemas import Severity


def _load_organism_heartbeat():
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "scripts" / "lib" / "heartbeat.py"
        if not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location("nuzantara_heartbeat", candidate)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.organism_heartbeat
    return None


def organism_heartbeat(organ_id: str, status: str = "ok", note: str = "") -> None:
    heartbeat = _load_organism_heartbeat()
    if heartbeat:
        heartbeat(organ_id, status, note)


async def main() -> None:
    now = datetime.now(timezone.utc)
    await emit_event(
        severity=Severity.INFO,
        source="cron.scheduled_tick",
        kind="scheduled_tick",
        payload={
            "hour": now.hour,
            "day_of_week": now.weekday(),  # Monday=0, Sunday=6
            "day_of_month": now.day,
            "ts_utc": now.isoformat(),
        },
    )


async def _run_with_heartbeat() -> None:
    organism_heartbeat("organism.scheduled_tick", "starting", "scheduled tick started")
    try:
        await main()
    except Exception as exc:
        organism_heartbeat(
            "organism.scheduled_tick",
            "error",
            f"{type(exc).__name__}: {exc}",
        )
        raise
    organism_heartbeat("organism.scheduled_tick", "ok", "scheduled tick emitted")


if __name__ == "__main__":
    asyncio.run(_run_with_heartbeat())
