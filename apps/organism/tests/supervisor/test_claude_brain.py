import json
import pytest
from unittest.mock import AsyncMock, patch

from organism.schemas import Event, Severity, ActionDecision
from organism.supervisor.claude_brain import (
    ClaudeBrain,
    CACHE_KEY_PREFIX,
    RATE_LIMIT_PER_MINUTE,
    CACHE_TTL,
)


def _event(kind="disk_fill", source="guardian.system_doctor", payload=None):
    return Event(
        severity=Severity.ERROR,
        source=source,
        kind=kind,
        payload=payload or {"percent": 90},
        correlation_id="c-test",
        host="Pro",
    )


class _MockProc:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, self._stderr

    def kill(self):
        pass

    async def wait(self):
        return


class _HangingProc:
    returncode = None

    async def communicate(self):
        import asyncio
        await asyncio.sleep(3600)

    def kill(self):
        pass

    async def wait(self):
        return


_VALID_RESPONSE = json.dumps({
    "actuator": "cleanup_log",
    "params": {"min_age_days": 30},
    "confidence": 0.85,
    "reasoning": "disk fill, oldest logs expendable",
})


@pytest.mark.asyncio
async def test_returns_cached_decision_on_hit(fake_redis):
    brain = ClaudeBrain(redis=fake_redis)
    decision = ActionDecision(
        actuator="cleanup_log", params={"min_age_days": 30},
        confidence=0.85, tier="L2_claude", reasoning="cached",
    )
    key = brain._cache_key(_event())
    await fake_redis.set(key, decision.model_dump_json(), ex=CACHE_TTL)

    with patch("asyncio.create_subprocess_exec") as mock_spawn:
        result = await brain.decide(
            _event(), ollama_bucket="data", recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    mock_spawn.assert_not_called()
    assert result.actuator == "cleanup_log"


@pytest.mark.asyncio
async def test_shells_out_and_parses_json(fake_redis):
    brain = ClaudeBrain(redis=fake_redis)
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(stdout=_VALID_RESPONSE.encode())),
    ):
        result = await brain.decide(
            _event(), ollama_bucket="data", recent_events_count=1,
            available_actuators=["cleanup_log", "quarantine"],
        )
    assert result.tier == "L2_claude"
    assert result.actuator == "cleanup_log"
    assert result.params == {"min_age_days": 30}
    assert result.confidence == 0.85


@pytest.mark.asyncio
async def test_caches_successful_decision(fake_redis):
    brain = ClaudeBrain(redis=fake_redis)
    ev = _event()
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(stdout=_VALID_RESPONSE.encode())),
    ):
        await brain.decide(ev, ollama_bucket="x", recent_events_count=1,
                           available_actuators=["cleanup_log"])
    key = brain._cache_key(ev)
    cached = await fake_redis.get(key)
    assert cached is not None
    assert await fake_redis.ttl(key) > 590


@pytest.mark.asyncio
async def test_rate_limit_defers_fourth_call_in_same_minute(fake_redis):
    brain = ClaudeBrain(redis=fake_redis)
    # Exhaust rate limit by calling _allow_this_call directly 3 times
    for _ in range(RATE_LIMIT_PER_MINUTE):
        assert brain._allow_this_call() is True
    assert brain._allow_this_call() is False

    with patch("asyncio.create_subprocess_exec") as mock_spawn:
        result = await brain.decide(
            _event(kind="new_kind"), ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    mock_spawn.assert_not_called()
    assert result.actuator == "defer_to_human"
    assert "rate_limit" in result.params["reason"]


@pytest.mark.asyncio
async def test_timeout_returns_defer(fake_redis):
    brain = ClaudeBrain(redis=fake_redis)
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_HangingProc()),
    ):
        with patch("asyncio.wait_for", side_effect=__import__("asyncio").TimeoutError):
            result = await brain.decide(
                _event(kind="novel"), ollama_bucket=None, recent_events_count=1,
                available_actuators=["cleanup_log"],
            )
    assert result.actuator == "defer_to_human"
    assert "timeout" in result.params["reason"]


@pytest.mark.asyncio
async def test_malformed_json_returns_defer(fake_redis):
    brain = ClaudeBrain(redis=fake_redis)
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(stdout=b"this is not JSON")),
    ):
        result = await brain.decide(
            _event(kind="novel2"), ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    assert result.actuator == "defer_to_human"
    assert "parse_error" in result.params["reason"]


@pytest.mark.asyncio
async def test_missing_required_field_returns_defer(fake_redis):
    """Claude returns JSON but no actuator key."""
    brain = ClaudeBrain(redis=fake_redis)
    bad_resp = json.dumps({"params": {}, "confidence": 0.5})
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(stdout=bad_resp.encode())),
    ):
        result = await brain.decide(
            _event(kind="novel3"), ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    assert result.actuator == "defer_to_human"


@pytest.mark.asyncio
async def test_cli_not_found_returns_defer(fake_redis):
    brain = ClaudeBrain(redis=fake_redis, claude_binary="/nonexistent/claude")
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        result = await brain.decide(
            _event(kind="novel4"), ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    assert result.actuator == "defer_to_human"
    assert "not_found" in result.params["reason"]


@pytest.mark.asyncio
async def test_strips_anthropic_api_key_from_env(fake_redis, monkeypatch):
    """Golden Rule #13: ANTHROPIC_API_KEY must NOT reach the spawned CLI."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-LEAKED-DO-NOT-PASS")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-token-ok")
    brain = ClaudeBrain(redis=fake_redis)
    mock_spawn = AsyncMock(return_value=_MockProc(stdout=_VALID_RESPONSE.encode()))
    with patch("asyncio.create_subprocess_exec", mock_spawn):
        await brain.decide(
            _event(kind="env_test"), ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    call_kwargs = mock_spawn.call_args.kwargs
    passed_env = call_kwargs["env"]
    assert "ANTHROPIC_API_KEY" not in passed_env
    assert "CLAUDE_CODE_OAUTH_TOKEN" in passed_env


@pytest.mark.asyncio
async def test_cache_key_stable_for_same_input(fake_redis):
    brain = ClaudeBrain(redis=fake_redis)
    k1 = brain._cache_key(_event(kind="k", payload={"a": 1, "b": 2}))
    k2 = brain._cache_key(_event(kind="k", payload={"b": 2, "a": 1}))
    assert k1 == k2


@pytest.mark.asyncio
async def test_cache_key_differs_for_different_kind(fake_redis):
    brain = ClaudeBrain(redis=fake_redis)
    k1 = brain._cache_key(_event(kind="k1"))
    k2 = brain._cache_key(_event(kind="k2"))
    assert k1 != k2


@pytest.mark.asyncio
async def test_prompt_uses_structured_slots(fake_redis):
    """Slot-only template prevents prompt injection via log content."""
    brain = ClaudeBrain(redis=fake_redis)
    mock_spawn = AsyncMock(return_value=_MockProc(stdout=_VALID_RESPONSE.encode()))
    with patch("asyncio.create_subprocess_exec", mock_spawn):
        await brain.decide(
            _event(kind="probe", payload={"path": "/tmp/log"}),
            ollama_bucket="hardware", recent_events_count=3,
            available_actuators=["cleanup_log", "notify_telegram"],
        )
    prompt_arg = mock_spawn.call_args.args[2]  # `-p <prompt>` is positional arg index 2
    assert "Event kind: probe" in prompt_arg
    assert "Ollama classifier bucket: hardware" in prompt_arg
    assert "Recent events in same correlation: 3" in prompt_arg
    assert "cleanup_log, notify_telegram" in prompt_arg


@pytest.mark.asyncio
async def test_malformed_cache_entry_triggers_recompute(fake_redis):
    """If Redis has garbage under the cache key, brain recomputes instead of crashing."""
    brain = ClaudeBrain(redis=fake_redis)
    ev = _event(kind="cache_garbage")
    key = brain._cache_key(ev)
    await fake_redis.set(key, b"{this is : not} valid JSON", ex=CACHE_TTL)
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(stdout=_VALID_RESPONSE.encode())),
    ):
        result = await brain.decide(
            ev, ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    assert result.actuator == "cleanup_log"


@pytest.mark.asyncio
async def test_confidence_clamped_to_valid_range(fake_redis):
    """Claude might return confidence > 1.0 — pydantic catches it."""
    brain = ClaudeBrain(redis=fake_redis)
    bad_resp = json.dumps({
        "actuator": "cleanup_log", "params": {}, "confidence": 1.5,
        "reasoning": "r",
    })
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(stdout=bad_resp.encode())),
    ):
        result = await brain.decide(
            _event(kind="bad_conf"), ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    assert result.actuator == "defer_to_human"


@pytest.mark.asyncio
async def test_rate_limit_window_resets_after_60s(fake_redis, monkeypatch):
    brain = ClaudeBrain(redis=fake_redis)
    for _ in range(RATE_LIMIT_PER_MINUTE):
        brain._allow_this_call()
    # Force window roll: simulate 61s elapsed
    brain._minute_start -= 61
    assert brain._allow_this_call() is True  # window rolled, counter reset


@pytest.mark.asyncio
async def test_empty_payload_cache_key_valid(fake_redis):
    brain = ClaudeBrain(redis=fake_redis)
    key = brain._cache_key(_event(payload={}))
    assert key.startswith(CACHE_KEY_PREFIX)


@pytest.mark.asyncio
async def test_decide_tier_always_l2_claude(fake_redis):
    """Every path — cache hit, rate limit, timeout, parse error, success —
    must return tier='L2_claude' so audit logs are consistent."""
    brain = ClaudeBrain(redis=fake_redis)
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(stdout=_VALID_RESPONSE.encode())),
    ):
        d = await brain.decide(
            _event(kind="tier_test"), ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    assert d.tier == "L2_claude"


@pytest.mark.asyncio
async def test_stdout_unicode_handled(fake_redis):
    """Claude may return UTF-8 reasoning with accented chars."""
    brain = ClaudeBrain(redis=fake_redis)
    resp = json.dumps({
        "actuator": "cleanup_log",
        "params": {},
        "confidence": 0.8,
        "reasoning": "Pulizia necessària — 日本語",
    })
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(stdout=resp.encode("utf-8"))),
    ):
        result = await brain.decide(
            _event(kind="utf_test"), ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    assert result.actuator == "cleanup_log"
    assert "日本語" in result.reasoning


@pytest.mark.asyncio
async def test_payload_with_path_objects_in_cache_key(fake_redis):
    """Cache key generation must handle non-JSON-native types (sort uses repr)."""
    from pathlib import Path
    brain = ClaudeBrain(redis=fake_redis)
    ev = _event(payload={"log_path": Path("/tmp/a.log"), "count": 5})
    key = brain._cache_key(ev)  # must NOT raise
    assert key.startswith(CACHE_KEY_PREFIX)


@pytest.mark.asyncio
async def test_stderr_noise_does_not_break_stdout_parse(fake_redis):
    """CLI may write progress/debug to stderr; stdout alone is authoritative."""
    brain = ClaudeBrain(redis=fake_redis)
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_MockProc(
            stdout=_VALID_RESPONSE.encode(),
            stderr=b"warning: slow path taken\ninfo: thinking\n",
        )),
    ):
        result = await brain.decide(
            _event(kind="stderr_test"), ollama_bucket=None, recent_events_count=1,
            available_actuators=["cleanup_log"],
        )
    assert result.tier == "L2_claude"
    assert result.actuator == "cleanup_log"
