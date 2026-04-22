import pytest
from organism.schemas import Event, Severity, IncidentContext
from organism.supervisor.incident_context import IncidentStore, INCIDENT_KEY_PREFIX, INCIDENT_TTL


@pytest.mark.asyncio
async def test_hydrate_creates_new_context_if_absent(fake_redis):
    store = IncidentStore(redis=fake_redis)
    ctx = await store.hydrate("corr-1")
    assert ctx.correlation_id == "corr-1"
    assert ctx.events == []


@pytest.mark.asyncio
async def test_persist_sets_ttl_10min(fake_redis):
    store = IncidentStore(redis=fake_redis)
    ctx = IncidentContext(correlation_id="c", events=[])
    await store.persist(ctx)
    ttl = await fake_redis.ttl(INCIDENT_KEY_PREFIX + "c")
    assert 590 <= ttl <= 600


@pytest.mark.asyncio
async def test_append_event_roundtrip(fake_redis):
    store = IncidentStore(redis=fake_redis)
    e = Event(severity=Severity.ERROR, source="s", kind="k", payload={}, correlation_id="c", host="Pro")
    ctx = await store.hydrate("c")
    ctx.events.append(e)
    await store.persist(ctx)
    hydrated = await store.hydrate("c")
    assert len(hydrated.events) == 1
