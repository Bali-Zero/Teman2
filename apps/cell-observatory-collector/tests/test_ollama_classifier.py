from __future__ import annotations
import json
import pytest

from cell_observatory.classifier import OllamaClassifier
from cell_observatory.models import ClassificationLabel, PulseEventV1


def _event(**over) -> PulseEventV1:
    base = dict(
        _outbox_id=1,
        event_version="v1",
        cell_id="seo_cell",
        cell_kind="seo",
        pulse_id="p1",
        pulse_timestamp=1717000000000,
        phase="observe",
        sensors=[{"name": "latency_ms", "value": 120}],
        pulse_result={"classifier_self": "green", "trend_label": "stable"},
        homeostatic_state={"energy_pct": 80, "load_factor": 0.3},
    )
    base.update(over)
    return PulseEventV1.model_validate(base)


class _FakeResponse:
    def __init__(self, payload: dict): self._payload = payload
    def raise_for_status(self): pass
    def json(self): return self._payload


class _FakeAsyncClient:
    def __init__(self, content: str): self._content = content; self.calls = []
    async def post(self, url, **kw):
        self.calls.append((url, kw))
        return _FakeResponse({"message": {"content": self._content},
                              "prompt_eval_count": 100, "eval_count": 20})
    async def aclose(self): pass


@pytest.mark.asyncio
async def test_classify_normal_label_maps_and_costs_zero():
    fake = _FakeAsyncClient(json.dumps({"label": "normal", "confidence": 0.92,
                                        "reasoning": "sensors within band"}))
    clf = OllamaClassifier(client=fake)
    res = await clf.classify(_event(pulse_result={"classifier_self": "green"}))
    assert res.label == ClassificationLabel.NORMAL
    assert res.confidence == pytest.approx(0.92)
    assert res.cost_usd == 0.0
    assert res.label_diff == "agree"
    assert res.error is None
    assert "qwen" in res.model.lower()


@pytest.mark.asyncio
async def test_classify_uses_chat_endpoint_with_json_format_and_think_false():
    fake = _FakeAsyncClient(json.dumps({"label": "anomaly", "confidence": 0.5, "reasoning": "x"}))
    clf = OllamaClassifier(client=fake)
    await clf.classify(_event())
    url, kw = fake.calls[0]
    assert url.endswith("/api/chat")
    body = kw["json"]
    assert body["format"] == "json"
    assert body["think"] is False
    assert body["stream"] is False


@pytest.mark.asyncio
async def test_classify_invalid_json_returns_uncertain_error_row():
    fake = _FakeAsyncClient("not json at all")
    clf = OllamaClassifier(client=fake)
    res = await clf.classify(_event())
    assert res.label == ClassificationLabel.UNCERTAIN
    assert res.confidence == 0.0
    assert res.error is not None
    assert res.cost_usd == 0.0


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold_transport_failures():
    class _FailingClient:
        async def post(self, url, **kw):
            raise RuntimeError("connection refused")
        async def aclose(self): pass

    clf = OllamaClassifier(client=_FailingClient(), circuit_threshold=3)
    # First 3 calls return error-rows (not raise) and accumulate failures
    for _ in range(3):
        res = await clf.classify(_event())
        assert res.error is not None
        assert res.label == ClassificationLabel.UNCERTAIN
    # 4th call: circuit is now open -> _check_circuit raises before any HTTP
    import pytest as _pytest
    from cell_observatory.classifier import CircuitOpenError
    with _pytest.raises(CircuitOpenError):
        await clf.classify(_event())
