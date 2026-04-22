import pytest
import fakeredis
import fakeredis.aioredis


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


@pytest.fixture
def fake_claude_cli(monkeypatch):
    """Replace claude CLI shell-out with deterministic stub.

    Yields the stub callable so tests can assert on its invocations or
    override behavior per-test.
    """
    async def _fake_invoke(template, slots):
        return {"decision": "restart_agent", "params": slots, "confidence": 0.9}
    monkeypatch.setattr("organism.supervisor.claude_brain.invoke_claude", _fake_invoke)
    yield _fake_invoke
