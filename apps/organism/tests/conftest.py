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


@pytest.fixture(autouse=True)
def _forbid_real_subprocess(request):
    """Defense-in-depth: prevent any real subprocess from spawning during tests.

    Post-incident (PR #206 accidental): a validation-bypass bug allowed a real
    git/gh chain to execute. This autouse fixture patches
    asyncio.create_subprocess_exec with RuntimeError so any test that forgets
    to mock subprocess calls fails loudly instead of creating branches/PRs.

    Tests that explicitly mock subprocess via `with patch("asyncio.create_subprocess_exec", ...)`
    override this autouse patch for the duration of their block — no existing
    test needs changes.

    To opt out (should never be needed): @pytest.mark.allow_real_subprocess.
    """
    if request.node.get_closest_marker("allow_real_subprocess"):
        yield
        return
    from unittest.mock import patch, AsyncMock
    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=RuntimeError("real subprocess forbidden in organism tests"),
    ):
        yield


