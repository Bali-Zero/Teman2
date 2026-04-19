"""Unit tests for OpenRouterClient cost tracking (Task 3).

Verifies that complete() emits a record_llm_call event with the dynamically
selected model from OpenRouter's server-side fallback response, and that
failures are also recorded.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.llm_clients.openrouter_client import (
    ModelTier,
    OpenRouterClient,
)


@pytest.mark.asyncio
async def test_complete_records_cost_with_dynamic_model():
    client = OpenRouterClient(api_key="test-key", default_tier=ModelTier.RAG)
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "model": "google/gemini-2.0-flash-exp:free",
        "usage": {"prompt_tokens": 120, "completion_tokens": 30},
    }
    fake_resp.raise_for_status = MagicMock()
    fake_http = AsyncMock()
    fake_http.post = AsyncMock(return_value=fake_resp)

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        with patch.object(client, "_get_client", return_value=fake_http):
            await client.complete(messages=[{"role": "user", "content": "hi"}])

    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openrouter"
    assert kwargs["model"] == "google/gemini-2.0-flash-exp:free"
    assert kwargs["input_tokens"] == 120
    assert kwargs["output_tokens"] == 30
    assert kwargs["success"] is True


@pytest.mark.asyncio
async def test_complete_records_on_failure():
    client = OpenRouterClient(api_key="test-key")
    fake_http = AsyncMock()
    fake_http.post = AsyncMock(side_effect=RuntimeError("rate limit"))

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        with patch.object(client, "_get_client", return_value=fake_http):
            with pytest.raises(RuntimeError):
                await client.complete(messages=[{"role": "user", "content": "hi"}])

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["success"] is False
    assert kwargs["error_class"] == "RuntimeError"
