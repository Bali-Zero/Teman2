"""Scenario 6: Redis is unreachable for 5 minutes during an incident.
EventBus emit() must fall back to JSONL-only so events are not lost —
they can be replayed when Redis returns.
"""
import pytest
from organism.schemas import Event, Severity
from organism.redis_bus import EventBus


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_06_redis_down(tmp_path):
    """Bypasses staging_organism to swap in BrokenRedis directly."""
    class BrokenRedis:
        async def xadd(self, *a, **kw):
            raise ConnectionError("redis unreachable")

    jsonl = tmp_path / "events.jsonl"
    bus = EventBus(redis=BrokenRedis(), jsonl_path=jsonl)

    e = Event(
        severity=Severity.CRITICAL,
        source="guardian.test",
        kind="cron_agent_failure",
        payload={"agent": "x"},
        correlation_id="c",
        host="Pro",
    )
    await bus.emit(e)  # must NOT raise

    # JSONL mirror captured the event
    lines = jsonl.read_text().strip().splitlines()
    assert len(lines) == 1, "event lost during Redis-down simulation"
