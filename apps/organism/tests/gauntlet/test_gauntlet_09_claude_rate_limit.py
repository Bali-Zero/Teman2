"""Scenario 9: Claude CLI rate limit hit. ClaudeBrain defers to human
instead of crashing. This is tested in test_claude_brain.py — we
reproduce the boundary here at gauntlet granularity."""
import pytest
from unittest.mock import AsyncMock, patch
from organism.supervisor.claude_brain import ClaudeBrain, RATE_LIMIT_PER_MINUTE
from organism.schemas import Event, Severity


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_09_claude_rate_limit(staging_organism):
    brain = ClaudeBrain(redis=staging_organism.redis)
    # Exhaust rate limit
    for _ in range(RATE_LIMIT_PER_MINUTE):
        assert brain._allow_this_call() is True
    # Fourth call should be blocked at the counter level
    assert brain._allow_this_call() is False

    event = Event(
        severity=Severity.ERROR,
        source="guardian.test",
        kind="novel_kind_unmatched",
        payload={"x": 1},
        correlation_id="c-rl",
        host="Pro",
    )
    with patch("asyncio.create_subprocess_exec") as mock_spawn:
        decision = await brain.decide(
            event, ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    mock_spawn.assert_not_called()
    assert decision.actuator == "defer_to_human"
    assert "rate_limit" in decision.params.get("reason", "")
