from unittest.mock import AsyncMock, patch

import pytest

from backend.services.observability.tracking_decorator import (
    llm_cost_tracked,
    set_usage,
)


@pytest.mark.asyncio
async def test_decorator_records_on_success():
    @llm_cost_tracked(provider="openai_embeddings", static_model="text-embedding-3-small")
    async def fake_call():
        set_usage(input_tokens=100, output_tokens=0)
        return "ok"

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        result = await fake_call()

    assert result == "ok"
    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openai_embeddings"
    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["input_tokens"] == 100
    assert kwargs["success"] is True
    assert kwargs["error_class"] is None
    assert kwargs["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_decorator_records_on_failure():
    @llm_cost_tracked(provider="openrouter", static_model="llama-3")
    async def fake_call():
        set_usage(input_tokens=50, output_tokens=0)
        raise RuntimeError("boom")

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        with pytest.raises(RuntimeError):
            await fake_call()

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["success"] is False
    assert kwargs["error_class"] == "RuntimeError"


@pytest.mark.asyncio
async def test_decorator_never_raises_on_recorder_error():
    @llm_cost_tracked(provider="gemini", static_model="flash")
    async def fake_call():
        set_usage(input_tokens=1, output_tokens=1)
        return "ok"

    async def blowup(**_):
        raise OSError("disk full")

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=blowup):
        result = await fake_call()  # must not raise

    assert result == "ok"


@pytest.mark.asyncio
async def test_decorator_uses_model_attr_from_self():
    class Client:
        model = "dynamic-model-v2"

        @llm_cost_tracked(provider="gemini", model_attr="model")
        async def call(self):
            set_usage(input_tokens=10, output_tokens=20)
            return "ok"

    c = Client()
    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        await c.call()

    assert mock_rec.await_args.kwargs["model"] == "dynamic-model-v2"


@pytest.mark.asyncio
async def test_decorator_falls_back_to_zero_cost_on_unknown_model():
    @llm_cost_tracked(provider="mystery", static_model="who-knows")
    async def fake_call():
        set_usage(input_tokens=1, output_tokens=1)
        return "ok"

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        await fake_call()

    assert mock_rec.await_args.kwargs["cost_usd"] == 0.0
