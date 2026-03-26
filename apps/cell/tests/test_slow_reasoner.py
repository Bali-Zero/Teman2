"""Tests for SLOW reasoner + DNA interpreter."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cell.slow.reasoner import SlowReasoner, ReasonerProposal
from cell.core.dna_interpreter import DNAInterpreter, ValidationResult


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
async def test_reasoner_qwen_success():
    """Mock Qwen returning a valid action."""
    reasoner = SlowReasoner()
    with patch.object(reasoner, "_call_qwen", new_callable=AsyncMock) as mock_qwen:
        mock_qwen.return_value = ('{"action": "alert_human", "reason": "Backend unreachable for 3 pulses", "confidence": 0.85}', 0.0)
        proposal = await reasoner.think(
            health_status="red",
            response_time_ms=0,
            error_message="Connection refused",
        )
        assert proposal.action == "alert_human"
        assert proposal.tier_used == 0
        assert proposal.cost_usd == 0.0


@pytest.mark.asyncio
async def test_reasoner_escalates_low_confidence():
    """Qwen low confidence → escalates to Gemini."""
    reasoner = SlowReasoner(gemini_api_key="test")
    with patch.object(reasoner, "_call_qwen", new_callable=AsyncMock) as mock_qwen, \
         patch.object(reasoner, "_call_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_qwen.return_value = ('{"action": "restart_service", "reason": "maybe", "confidence": 0.3}', 0.0)
        mock_gemini.return_value = ('{"action": "alert_human", "reason": "better to alert", "confidence": 0.9}', 0.00004)
        proposal = await reasoner.think(
            health_status="red",
            response_time_ms=0,
            error_message="Connection refused",
        )
        assert proposal.tier_used == 1  # Escalated to Gemini
        assert proposal.action == "alert_human"


@pytest.mark.asyncio
async def test_reasoner_qwen_failure_escalates():
    """Qwen fails → escalates to Gemini."""
    reasoner = SlowReasoner(gemini_api_key="test")
    with patch.object(reasoner, "_call_qwen", new_callable=AsyncMock) as mock_qwen, \
         patch.object(reasoner, "_call_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_qwen.side_effect = Exception("Ollama not running")
        mock_gemini.return_value = ('{"action": "alert_human", "reason": "qwen down", "confidence": 0.8}', 0.00004)
        proposal = await reasoner.think(
            health_status="yellow",
            response_time_ms=8000,
        )
        assert proposal.tier_used == 1
