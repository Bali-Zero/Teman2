import pytest
from unittest.mock import AsyncMock, patch
from cell_observatory.classifier import MinimaxClassifier, CircuitOpenError
from cell_observatory.models import PulseEventV1


def event_factory():
    return PulseEventV1(
        _outbox_id=1, event_version="v1", cell_id="x", cell_kind="x",
        pulse_id="x", pulse_timestamp="2026-05-01T00:00:00.000Z",
        phase="x", sensors=[], pulse_result={"classifier_self": "green"},
        homeostatic_state={}, scar_signals=[], metadata={},
    )


@pytest.mark.asyncio
async def test_classify_returns_structured():
    event = event_factory()
    clf = MinimaxClassifier(api_key="sk-fake")
    fake_response = {
        "choices": [{"message": {"content": '{"reasoning": "all good", "label": "normal", "confidence": 0.9}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
    }
    with patch.object(clf, "_call_api", AsyncMock(return_value=fake_response)):
        result = await clf.classify(event)
    assert result.label.value == "normal"
    assert result.confidence == 0.9
    # cost_usd >= 0 (zero on free OpenRouter tier minimax-m2.5:free, positive on paid models)
    assert result.cost_usd >= 0
    await clf.aclose()


@pytest.mark.asyncio
async def test_classify_label_diff_disagree():
    """Cell self=green, LLM=anomaly → label_diff='disagree'."""
    event = event_factory()
    clf = MinimaxClassifier(api_key="sk-fake")
    fake_response = {
        "choices": [{"message": {"content": '{"reasoning": "subtle issue", "label": "anomaly", "confidence": 0.7}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
    }
    with patch.object(clf, "_call_api", AsyncMock(return_value=fake_response)):
        result = await clf.classify(event)
    assert result.label_diff == "disagree"
    await clf.aclose()


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_n_failures():
    """M3 fix: 5 consecutive failures → circuit opens, raises CircuitOpenError on 6th call."""
    clf = MinimaxClassifier(api_key="sk-fake", circuit_threshold=5)
    failing = AsyncMock(side_effect=Exception("500"))
    with patch.object(clf, "_call_api", failing):
        # 5 failures will increment _consecutive_failures
        for _ in range(5):
            with pytest.raises(Exception):
                await clf.classify(event_factory())
    # 6th call: circuit should be OPEN
    with pytest.raises(CircuitOpenError):
        await clf.classify(event_factory())
    await clf.aclose()
