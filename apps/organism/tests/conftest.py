import pytest
import fakeredis
import fakeredis.aioredis


@pytest.fixture(autouse=True)
def _reset_organism_bus():
    """Reset organism emit singleton between tests to prevent cross-test contamination."""
    yield
    from organism import emit
    emit._reset_bus_for_tests()


@pytest.fixture(scope="function")
async def fake_redis():
    """Async fake Redis for testing.

    Uses explicit FakeServer per test to avoid event-loop binding issues
    (fakeredis-py #292) when multiple async tests share a session.
    """
    server = fakeredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server)
    yield client
    await client.aclose()


