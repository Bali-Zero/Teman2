"""Test that the OpenAI embeddings batch call records cost via @llm_cost_tracked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.embeddings import EmbeddingsGenerator


@pytest.mark.asyncio
async def test_embed_batch_records_cost():
    gen = EmbeddingsGenerator(api_key="test", model="text-embedding-3-small", provider="openai")
    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=[0.1] * 1536)]
    fake_response.usage = MagicMock(prompt_tokens=42, total_tokens=42)
    gen.client = MagicMock()
    gen.client.embeddings.create = AsyncMock(return_value=fake_response)

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        await gen._embed_batch(["hello world"])

    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openai_embeddings"
    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["input_tokens"] == 42
    assert kwargs["output_tokens"] == 0
    assert kwargs["success"] is True


@pytest.mark.asyncio
async def test_embed_batch_records_cost_via_generate_embeddings():
    """Verify cost tracking fires when called through the public generate_embeddings API."""
    gen = EmbeddingsGenerator(api_key="test", model="text-embedding-3-small", provider="openai")
    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=[0.1] * 1536)]
    fake_response.usage = MagicMock(prompt_tokens=10, total_tokens=10)
    gen.client = MagicMock()
    gen.client.embeddings.create = AsyncMock(return_value=fake_response)

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        result = await gen.generate_embeddings(["hello"])

    assert result == [[0.1] * 1536]
    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openai_embeddings"
    assert kwargs["input_tokens"] == 10
    assert kwargs["success"] is True
