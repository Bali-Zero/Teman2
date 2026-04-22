import pytest
import fakeredis.aioredis


@pytest.fixture
async def fake_redis():
    """Async fake Redis for testing."""
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.aclose()


@pytest.fixture
def fake_claude_cli(monkeypatch):
    """Replace claude CLI shell-out with deterministic stub."""
    async def _fake_invoke(template, slots):
        return {"decision": "restart_agent", "params": slots, "confidence": 0.9}
    monkeypatch.setattr("organism.supervisor.claude_brain.invoke_claude", _fake_invoke)
