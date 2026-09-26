"""Tests for SLOW reasoner + DNA interpreter."""
from unittest.mock import AsyncMock, patch

import httpx

import pytest
from cell.core.dna_interpreter import DNAInterpreter
from cell.slow.reasoner import SlowReasoner, _tier0_busy

# --- Reasoner ---

def test_reasoner_parse_valid_json():
    reasoner = SlowReasoner()
    result = reasoner._parse_response(
        '{"action": "alert_human", "reason": "Backend is down", "confidence": 0.9}',
        tier=0, cost=0.0,
    )
    assert result.action == "alert_human"
    assert result.confidence == 0.9
    assert result.reason == "Backend is down"


def test_reasoner_parse_json_in_markdown():
    reasoner = SlowReasoner()
    result = reasoner._parse_response(
        'Here is my analysis:\n```json\n{"action": "none", "reason": "all good", "confidence": 1.0}\n```',
        tier=0, cost=0.0,
    )
    assert result.action == "none"
    assert result.confidence == 1.0


def test_reasoner_parse_invalid_action():
    reasoner = SlowReasoner()
    result = reasoner._parse_response(
        '{"action": "hack_pentagon", "reason": "test", "confidence": 0.9}',
        tier=0, cost=0.0,
    )
    assert result.action == "none"  # Invalid action rejected
    assert "not in allowlist" in result.reason


def test_reasoner_parse_garbage():
    reasoner = SlowReasoner()
    result = reasoner._parse_response(
        "I don't know what to do, sorry!",
        tier=0, cost=0.0,
    )
    assert result.action == "alert_human"  # Fallback to human
    assert "unparseable" in result.reason.lower()


def test_reasoner_clamps_confidence():
    reasoner = SlowReasoner()
    result = reasoner._parse_response(
        '{"action": "none", "reason": "test", "confidence": 5.0}',
        tier=0, cost=0.0,
    )
    assert result.confidence == 1.0  # Clamped


# --- DNA Interpreter ---

def test_interpreter_approves_valid_action():
    interp = DNAInterpreter()
    result = interp.validate("check_health", budget_spent=1.0, budget_limit=10.0)
    assert result.approved is True


def test_interpreter_rejects_unknown_action():
    interp = DNAInterpreter()
    result = interp.validate("hack_pentagon", budget_spent=1.0, budget_limit=10.0)
    assert result.approved is False
    assert result.rule_violated == 1


def test_interpreter_blocks_over_budget():
    interp = DNAInterpreter()
    result = interp.validate("restart_service", budget_spent=9.5, budget_limit=10.0, confidence=0.9)
    assert result.approved is False
    assert result.rule_violated == 3


def test_interpreter_allows_alert_over_budget():
    """alert_human is cost-immune — works even at 95% budget."""
    interp = DNAInterpreter()
    result = interp.validate("alert_human", budget_spent=9.5, budget_limit=10.0)
    assert result.approved is True


def test_interpreter_blocks_low_confidence_restart():
    interp = DNAInterpreter()
    result = interp.validate("restart_service", budget_spent=1.0, budget_limit=10.0, confidence=0.3)
    assert result.approved is False
    assert "confidence" in result.reason.lower()


def test_interpreter_approves_high_confidence_restart():
    interp = DNAInterpreter()
    result = interp.validate("restart_service", budget_spent=1.0, budget_limit=10.0, confidence=0.8)
    assert result.approved is True


def test_interpreter_cooldown_blocks_repeat():
    interp = DNAInterpreter()
    interp.record_action("restart_service")
    result = interp.validate("restart_service", budget_spent=1.0, budget_limit=10.0, confidence=0.9)
    assert result.approved is False
    assert "cooldown" in result.reason.lower()


def test_interpreter_daily_limit():
    interp = DNAInterpreter()
    for _ in range(3):
        interp.record_action("restart_service")
    # Force past cooldown by clearing history timestamps
    for entry in interp._action_history:
        entry["timestamp"] = 0  # Long ago
    result = interp.validate("restart_service", budget_spent=1.0, budget_limit=10.0, confidence=0.9)
    assert result.approved is False
    assert "daily limit" in result.reason.lower()


def test_interpreter_none_always_approved():
    interp = DNAInterpreter()
    result = interp.validate("none", budget_spent=9.9, budget_limit=10.0)
    assert result.approved is True


# --- Integration: Reasoner + Interpreter ---

@pytest.mark.asyncio
async def test_reasoner_qwen9b_success():
    """Mock Qwen 9B returning a valid action."""
    reasoner = SlowReasoner()
    with patch.object(reasoner, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = ('{"action": "alert_human", "reason": "Backend unreachable for 3 pulses", "confidence": 0.85}', 0.0)
        proposal = await reasoner.think(
            health_status="red",
            response_time_ms=0,
            error_message="Connection refused",
        )
        assert proposal.action == "alert_human"
        assert proposal.tier_used == 0
        assert proposal.cost_usd == 0.0
        # Should have called with the fast model
        mock_ollama.assert_called_once()
        assert mock_ollama.call_args[0][0] == "qwen3.5:9b"


@pytest.mark.asyncio
async def test_reasoner_escalates_low_confidence():
    """Qwen 9B low confidence → escalates to Qwen 27B."""
    reasoner = SlowReasoner()
    call_count = 0

    async def mock_ollama(model: str, system: str, user: str, timeout: float = 30.0, **_kw) -> tuple[str, float]:
        nonlocal call_count
        call_count += 1
        if model == "qwen3.5:9b":
            return '{"action": "restart_service", "reason": "maybe", "confidence": 0.3}', 0.0
        else:
            return '{"action": "alert_human", "reason": "better to alert", "confidence": 0.9}', 0.0

    with patch.object(reasoner, "_call_ollama", side_effect=mock_ollama), \
            patch.object(reasoner, "_unload_model", new_callable=AsyncMock):
        proposal = await reasoner.think(
            health_status="red",
            response_time_ms=0,
            error_message="Connection refused",
        )
        assert proposal.tier_used == 1  # Escalated to 27B
        assert proposal.action == "alert_human"
        assert call_count == 2


@pytest.mark.asyncio
async def test_reasoner_9b_failure_escalates_to_27b():
    """Qwen 9B fails → escalates to Qwen 27B."""
    reasoner = SlowReasoner()

    async def mock_ollama(model: str, system: str, user: str, timeout: float = 30.0, **_kw) -> tuple[str, float]:
        if model == "qwen3.5:9b":
            raise Exception("Ollama not running")
        return '{"action": "alert_human", "reason": "9b down", "confidence": 0.8}', 0.0

    with patch.object(reasoner, "_call_ollama", side_effect=mock_ollama), \
            patch.object(reasoner, "_unload_model", new_callable=AsyncMock):
        proposal = await reasoner.think(
            health_status="yellow",
            response_time_ms=8000,
        )
        assert proposal.tier_used == 1



def _timeout():
    return httpx.ReadTimeout("")


def _record(reasoner, events, fast_outcomes, heavy_reply='{"action": "alert_human", "reason": "deep", "confidence": 0.9}'):
    """Wire mocks that append ('call', model, keep_alive) / ('unload', model) to events."""
    outcomes = list(fast_outcomes)

    async def mock_ollama(model, system, user, timeout=30.0, keep_alive=None):
        events.append(("call", model, keep_alive))
        if model == reasoner._model_fast:
            nxt = outcomes.pop(0)
            if isinstance(nxt, BaseException):
                raise nxt
            return nxt, 0.0
        return heavy_reply, 0.0

    async def mock_unload(model):
        events.append(("unload", model))

    reasoner._busy_retry_s = 0
    return (patch.object(reasoner, "_call_ollama", side_effect=mock_ollama),
            patch.object(reasoner, "_unload_model", side_effect=mock_unload))


LOW = '{"action": "restart_service", "reason": "maybe", "confidence": 0.3}'


@pytest.mark.asyncio
async def test_low_confidence_unloads_9b_then_calls_27b_without_keeping_it():
    reasoner, events = SlowReasoner(), []
    p1, p2 = _record(reasoner, events, [LOW])
    with p1, p2:
        proposal = await reasoner.think(health_status="red", response_time_ms=0)
    assert proposal.tier_used == 1
    assert events == [("call", "qwen3.5:9b", None), ("unload", "qwen3.5:9b"), ("call", "qwen3.8:27b-mlx", 0)]


@pytest.mark.asyncio
async def test_busy_9b_twice_never_loads_the_27b():
    """Pro 2026-09-26 20:50: a 9b held by the translator is busy, not broken."""
    reasoner, events = SlowReasoner(), []
    p1, p2 = _record(reasoner, events, [_timeout(), _timeout()])
    with p1, p2:
        proposal = await reasoner.think(health_status="red", response_time_ms=0)
    assert events == [("call", "qwen3.5:9b", None), ("call", "qwen3.5:9b", None)]
    assert proposal.action == "alert_human" and proposal.tier_used == 0


@pytest.mark.asyncio
async def test_busy_9b_on_green_returns_none_without_27b():
    reasoner, events = SlowReasoner(), []
    busy = httpx.HTTPStatusError("busy", request=httpx.Request("POST", "http://x"), response=httpx.Response(503))
    p1, p2 = _record(reasoner, events, [busy, busy])
    with p1, p2:
        proposal = await reasoner.think(health_status="green", response_time_ms=100)
    assert proposal.action == "none"
    assert all(e[1] == "qwen3.5:9b" for e in events)


@pytest.mark.asyncio
async def test_busy_9b_answering_on_retry_is_used():
    reasoner, events = SlowReasoner(), []
    ok = '{"action": "alert_human", "reason": "down", "confidence": 0.8}'
    p1, p2 = _record(reasoner, events, [_timeout(), ok])
    with p1, p2:
        proposal = await reasoner.think(health_status="red", response_time_ms=0)
    assert proposal.tier_used == 0 and proposal.action == "alert_human"
    assert len(events) == 2


@pytest.mark.asyncio
async def test_real_9b_error_escalates_with_keep_alive_0():
    reasoner, events = SlowReasoner(), []
    p1, p2 = _record(reasoner, events, [httpx.ConnectError("refused")])
    with p1, p2:
        proposal = await reasoner.think(health_status="red", response_time_ms=0)
    assert proposal.tier_used == 1
    assert events == [("call", "qwen3.5:9b", None), ("unload", "qwen3.5:9b"), ("call", "qwen3.8:27b-mlx", 0)]


@pytest.mark.asyncio
async def test_failed_unload_still_reaches_tier1(caplog):
    """Memory hygiene must never block the alert path."""
    import logging

    reasoner = SlowReasoner()
    calls = []

    async def mock_ollama(model, system, user, timeout=30.0, keep_alive=None):
        calls.append((model, keep_alive))
        return (LOW if model == "qwen3.5:9b" else '{"action": "alert_human", "reason": "d", "confidence": 0.9}'), 0.0

    class _Down:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            raise httpx.ConnectError("refused")

        async def __aexit__(self, *a):
            return False

    with patch.object(reasoner, "_call_ollama", side_effect=mock_ollama), \
            patch("cell.slow.reasoner.httpx.AsyncClient", _Down), \
            caplog.at_level(logging.WARNING, logger="cell.slow"):
        proposal = await reasoner.think(health_status="red", response_time_ms=0)
    assert proposal.tier_used == 1
    assert calls[-1] == ("qwen3.8:27b-mlx", 0)
    assert any("Unload of qwen3.5:9b before Tier 1 failed" in r.message for r in caplog.records)


def test_tier0_busy_classification():
    req = httpx.Request("POST", "http://x")
    assert _tier0_busy(httpx.ReadTimeout(""))
    assert _tier0_busy(httpx.HTTPStatusError("q", request=req, response=httpx.Response(503)))
    assert not _tier0_busy(httpx.HTTPStatusError("e", request=req, response=httpx.Response(500)))
    assert not _tier0_busy(httpx.ConnectError("refused"))
    assert not _tier0_busy(ValueError("bad json"))


@pytest.mark.asyncio
async def test_call_ollama_sends_keep_alive_only_when_asked():
    reasoner = SlowReasoner()
    sent = []

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "{}"}}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json):
            sent.append(json)
            return _Resp()

    with patch("cell.slow.reasoner.httpx.AsyncClient", _Client):
        await reasoner._call_ollama("m", "s", "u")
        await reasoner._call_ollama("m", "s", "u", keep_alive=0)
        await reasoner._unload_model("m")
    assert "keep_alive" not in sent[0]
    assert sent[1]["keep_alive"] == 0
    assert sent[2] == {"model": "m", "keep_alive": 0}
