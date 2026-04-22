import pytest
from unittest.mock import AsyncMock

from organism.schemas import ActionDecision, Event, Severity
from organism.supervisor.consiglio_gate import (
    ConsiglioGate,
    IRREVERSIBLE_ACTUATORS,
    REQUIRED_AGREE_VOTES,
)


def _event(kind="deploy_failure"):
    return Event(
        severity=Severity.CRITICAL,
        source="guardian.deploy",
        kind=kind,
        payload={"version": "v1.2.3"},
        correlation_id="c-test",
        host="Pro",
    )


def _irreversible_proposed(actuator="rollback_deploy", params=None):
    return ActionDecision(
        actuator=actuator,
        params=params or {"version": "v1.2.2"},
        confidence=0.85,
        tier="L2_claude",
        reasoning="prior stable version",
    )


def _reversible_proposed():
    return ActionDecision(
        actuator="cleanup_log",
        params={"min_age_days": 30},
        confidence=0.9,
        tier="L0_yaml",
        reasoning="disk fill rule",
    )


def _mock_runner(votes):
    runner = AsyncMock()
    runner.deliberate = AsyncMock(return_value={"votes": votes, "consensus": False})
    return runner


@pytest.mark.asyncio
async def test_is_irreversible_detects_rollback_deploy():
    assert ConsiglioGate.is_irreversible(_irreversible_proposed(actuator="rollback_deploy"))


@pytest.mark.asyncio
async def test_is_irreversible_detects_propose_yaml_rule():
    assert ConsiglioGate.is_irreversible(_irreversible_proposed(actuator="propose_yaml_rule"))


@pytest.mark.asyncio
async def test_is_not_irreversible_for_cleanup_log():
    assert not ConsiglioGate.is_irreversible(_reversible_proposed())


@pytest.mark.asyncio
async def test_approve_passthrough_for_reversible_decision():
    runner = AsyncMock()
    runner.deliberate = AsyncMock()  # should NOT be called
    gate = ConsiglioGate(runner=runner)
    result = await gate.approve(_event(), _reversible_proposed())
    assert result.actuator == "cleanup_log"
    runner.deliberate.assert_not_called()


@pytest.mark.asyncio
async def test_approve_3of4_agree_proceeds_with_proposed():
    votes = [
        {"agree": True, "rationale": "sound", "llm": "claude"},
        {"agree": True, "rationale": "safe", "llm": "gemini"},
        {"agree": True, "rationale": "ok", "llm": "deepseek"},
        {"agree": False, "rationale": "risky", "llm": "ollama"},
    ]
    gate = ConsiglioGate(runner=_mock_runner(votes))
    result = await gate.approve(_event(), _irreversible_proposed())
    assert result.actuator == "rollback_deploy"
    assert result.tier == "L3_consiglio"
    assert "3/4" in result.reasoning


@pytest.mark.asyncio
async def test_approve_4of4_agree_proceeds():
    votes = [{"agree": True, "rationale": "r", "llm": f"m{i}"} for i in range(4)]
    gate = ConsiglioGate(runner=_mock_runner(votes))
    result = await gate.approve(_event(), _irreversible_proposed())
    assert result.actuator == "rollback_deploy"
    assert result.tier == "L3_consiglio"


@pytest.mark.asyncio
async def test_approve_2of4_dissent_defers():
    votes = [
        {"agree": True, "rationale": "a", "llm": "claude"},
        {"agree": True, "rationale": "b", "llm": "gemini"},
        {"agree": False, "rationale": "c", "llm": "deepseek"},
        {"agree": False, "rationale": "d", "llm": "ollama"},
    ]
    gate = ConsiglioGate(runner=_mock_runner(votes))
    result = await gate.approve(_event(), _irreversible_proposed())
    assert result.actuator == "defer_to_human"
    assert result.tier == "L3_consiglio"
    assert "consiglio_dissent" in result.params["reason"]
    assert "2/4" in result.reasoning


@pytest.mark.asyncio
async def test_approve_zero_agree_defers():
    votes = [{"agree": False, "rationale": "x", "llm": f"m{i}"} for i in range(4)]
    gate = ConsiglioGate(runner=_mock_runner(votes))
    result = await gate.approve(_event(), _irreversible_proposed())
    assert result.actuator == "defer_to_human"
    assert "0/4" in result.reasoning


@pytest.mark.asyncio
async def test_runner_exception_defers_gracefully():
    runner = AsyncMock()
    runner.deliberate = AsyncMock(side_effect=RuntimeError("consiglio offline"))
    gate = ConsiglioGate(runner=runner)
    result = await gate.approve(_event(), _irreversible_proposed())
    assert result.actuator == "defer_to_human"
    assert result.params["reason"] == "consiglio_runner_error"
    assert "consiglio offline" in result.params["error"]


@pytest.mark.asyncio
async def test_prompt_includes_proposed_params_and_reasoning():
    runner = AsyncMock()
    # Capture the prompt
    runner.deliberate = AsyncMock(
        return_value={"votes": [{"agree": True, "rationale": "r", "llm": "m"} for _ in range(4)]},
    )
    gate = ConsiglioGate(runner=runner)
    proposed = _irreversible_proposed(
        actuator="propose_yaml_rule",
        params={"rule_id": "disk_fill_custom", "confidence": 0.9},
    )
    await gate.approve(_event(kind="new_pattern"), proposed)
    call_args = runner.deliberate.await_args
    prompt = call_args.args[0]
    assert "new_pattern" in prompt
    assert "propose_yaml_rule" in prompt
    assert "rule_id" in prompt
    assert "disk_fill_custom" in prompt


@pytest.mark.asyncio
async def test_approve_empty_votes_defers():
    """Runner returns {} or {'votes': []} — must defer, not silently accept."""
    runner = _mock_runner([])  # empty votes list
    gate = ConsiglioGate(runner=runner)
    result = await gate.approve(_event(), _irreversible_proposed())
    assert result.actuator == "defer_to_human"
    assert result.params["reason"] == "consiglio_dissent"
    assert "0/0" in result.reasoning or "0/" in result.reasoning


@pytest.mark.asyncio
async def test_approve_runner_returns_none_defers():
    """Runner returns None (malformed) — must defer, not crash."""
    from unittest.mock import AsyncMock
    runner = AsyncMock()
    runner.deliberate = AsyncMock(return_value=None)
    gate = ConsiglioGate(runner=runner)
    result = await gate.approve(_event(), _irreversible_proposed())
    assert result.actuator == "defer_to_human"


@pytest.mark.asyncio
async def test_approve_params_with_datetime_serializes_cleanly():
    """Regression for I1: proposed.params with datetime must serialize via mode='json'."""
    from datetime import datetime, timezone
    import json
    runner = _mock_runner([
        {"agree": False, "rationale": "x", "llm": "m"} for _ in range(4)
    ])
    gate = ConsiglioGate(runner=runner)
    proposed = ActionDecision(
        actuator="rollback_deploy",
        params={"version": "v1.2.3", "committed_at": datetime(2026, 4, 22, tzinfo=timezone.utc)},
        confidence=0.85,
        tier="L2_claude",
        reasoning="datetime test",
    )
    result = await gate.approve(_event(), proposed)
    # The key property: the result.params["proposed"] must be JSON-serializable end-to-end
    json.dumps(result.params["proposed"])  # must not raise TypeError
    # Verify datetime was converted to ISO string
    assert isinstance(result.params["proposed"]["params"]["committed_at"], str)
