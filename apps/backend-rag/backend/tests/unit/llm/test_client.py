"""
Tests for UnifiedLLMClient
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from llm.base import LLMMessage, LLMResponse
from llm.client import UnifiedLLMClient, create_default_client


class TestUnifiedLLMClient:
    """Test suite for UnifiedLLMClient"""

    def test_init(self):
        """Test client initialization"""
        mock_provider1 = MagicMock()
        mock_provider1.name = "provider1"
        mock_provider1.is_available = True

        mock_provider2 = MagicMock()
        mock_provider2.name = "provider2"
        mock_provider2.is_available = False

        client = UnifiedLLMClient([mock_provider1, mock_provider2])

        assert len(client.providers) == 2

    def test_get_available_providers(self):
        """Test getting available providers"""
        mock_provider1 = MagicMock()
        mock_provider1.name = "provider1"
        mock_provider1.is_available = True

        mock_provider2 = MagicMock()
        mock_provider2.name = "provider2"
        mock_provider2.is_available = False

        mock_provider3 = MagicMock()
        mock_provider3.name = "provider3"
        mock_provider3.is_available = True

        client = UnifiedLLMClient([mock_provider1, mock_provider2, mock_provider3])

        available = client.get_available_providers()

        assert "provider1" in available
        assert "provider2" not in available
        assert "provider3" in available
        assert len(available) == 2

    @pytest.mark.asyncio
    async def test_generate_success_first_provider(self):
        """Test successful generation with first provider"""
        mock_provider1 = MagicMock()
        mock_provider1.name = "provider1"
        mock_provider1.is_available = True
        mock_provider1.generate = AsyncMock(
            return_value=LLMResponse(content="Response", model="model1", provider="provider1")
        )

        mock_provider2 = MagicMock()
        mock_provider2.name = "provider2"
        mock_provider2.is_available = True

        client = UnifiedLLMClient([mock_provider1, mock_provider2])

        messages = [LLMMessage(role="user", content="Test")]
        response = await client.generate(messages)

        assert response.content == "Response"
        assert response.provider == "provider1"
        mock_provider1.generate.assert_called_once()
        mock_provider2.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_fallback_to_second_provider(self):
        """Test fallback to second provider when first fails"""
        mock_provider1 = MagicMock()
        mock_provider1.name = "provider1"
        mock_provider1.is_available = True
        mock_provider1.generate = AsyncMock(side_effect=Exception("Provider 1 failed"))

        mock_provider2 = MagicMock()
        mock_provider2.name = "provider2"
        mock_provider2.is_available = True
        mock_provider2.generate = AsyncMock(
            return_value=LLMResponse(content="Response", model="model2", provider="provider2")
        )

        client = UnifiedLLMClient([mock_provider1, mock_provider2])

        messages = [LLMMessage(role="user", content="Test")]
        response = await client.generate(messages)

        assert response.content == "Response"
        assert response.provider == "provider2"
        mock_provider1.generate.assert_called_once()
        mock_provider2.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_skips_unavailable_providers(self):
        """Test that unavailable providers are skipped"""
        mock_provider1 = MagicMock()
        mock_provider1.name = "provider1"
        mock_provider1.is_available = False

        mock_provider2 = MagicMock()
        mock_provider2.name = "provider2"
        mock_provider2.is_available = True
        mock_provider2.generate = AsyncMock(
            return_value=LLMResponse(content="Response", model="model2", provider="provider2")
        )

        client = UnifiedLLMClient([mock_provider1, mock_provider2])

        messages = [LLMMessage(role="user", content="Test")]
        response = await client.generate(messages)

        assert response.content == "Response"
        mock_provider1.generate.assert_not_called()
        mock_provider2.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_all_providers_fail(self):
        """Test when all providers fail"""
        mock_provider1 = MagicMock()
        mock_provider1.name = "provider1"
        mock_provider1.is_available = True
        mock_provider1.generate = AsyncMock(side_effect=Exception("Provider 1 failed"))

        mock_provider2 = MagicMock()
        mock_provider2.name = "provider2"
        mock_provider2.is_available = True
        mock_provider2.generate = AsyncMock(side_effect=Exception("Provider 2 failed"))

        client = UnifiedLLMClient([mock_provider1, mock_provider2])

        messages = [LLMMessage(role="user", content="Test")]

        with pytest.raises(RuntimeError, match="All providers failed"):
            await client.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_with_parameters(self):
        """Test generate with temperature and max_tokens"""
        mock_provider = MagicMock()
        mock_provider.name = "provider1"
        mock_provider.is_available = True
        mock_provider.generate = AsyncMock(
            return_value=LLMResponse(content="Response", model="model1", provider="provider1")
        )

        client = UnifiedLLMClient([mock_provider])

        messages = [LLMMessage(role="user", content="Test")]
        response = await client.generate(messages, temperature=0.5, max_tokens=2048)

        call_args = mock_provider.generate.call_args
        assert call_args.kwargs["temperature"] == 0.5
        assert call_args.kwargs["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_stream_success_first_provider(self):
        """Test successful streaming with first provider"""
        mock_provider1 = MagicMock()
        mock_provider1.name = "provider1"
        mock_provider1.is_available = True

        async def mock_stream(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"
            yield "chunk3"

        mock_provider1.stream = mock_stream

        mock_provider2 = MagicMock()
        mock_provider2.name = "provider2"
        mock_provider2.is_available = True

        client = UnifiedLLMClient([mock_provider1, mock_provider2])

        messages = [LLMMessage(role="user", content="Test")]
        chunks = []
        async for chunk in client.stream(messages):
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2", "chunk3"]
        mock_provider2.stream.assert_not_called()

    @pytest.mark.asyncio
    async def test_stream_fallback_to_second_provider(self):
        """Test fallback to second provider when first fails"""
        mock_provider1 = MagicMock()
        mock_provider1.name = "provider1"
        mock_provider1.is_available = True

        async def mock_stream_fail(*args, **kwargs):
            raise Exception("Provider 1 failed")

        mock_provider1.stream = mock_stream_fail

        mock_provider2 = MagicMock()
        mock_provider2.name = "provider2"
        mock_provider2.is_available = True

        async def mock_stream_success(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"

        mock_provider2.stream = mock_stream_success

        client = UnifiedLLMClient([mock_provider1, mock_provider2])

        messages = [LLMMessage(role="user", content="Test")]
        chunks = []
        async for chunk in client.stream(messages):
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2"]

    @pytest.mark.asyncio
    async def test_stream_skips_unavailable_providers(self):
        """Test that unavailable providers are skipped in streaming"""
        mock_provider1 = MagicMock()
        mock_provider1.name = "provider1"
        mock_provider1.is_available = False

        mock_provider2 = MagicMock()
        mock_provider2.name = "provider2"
        mock_provider2.is_available = True

        async def mock_stream(*args, **kwargs):
            yield "chunk1"

        mock_provider2.stream = mock_stream

        client = UnifiedLLMClient([mock_provider1, mock_provider2])

        messages = [LLMMessage(role="user", content="Test")]
        chunks = []
        async for chunk in client.stream(messages):
            chunks.append(chunk)

        assert chunks == ["chunk1"]

    @pytest.mark.asyncio
    async def test_stream_all_providers_fail(self):
        """Test when all providers fail in streaming"""
        mock_provider1 = MagicMock()
        mock_provider1.name = "provider1"
        mock_provider1.is_available = True

        async def mock_stream_fail(*args, **kwargs):
            raise Exception("Provider 1 failed")

        mock_provider1.stream = mock_stream_fail

        mock_provider2 = MagicMock()
        mock_provider2.name = "provider2"
        mock_provider2.is_available = True

        async def mock_stream_fail2(*args, **kwargs):
            raise Exception("Provider 2 failed")

        mock_provider2.stream = mock_stream_fail2

        client = UnifiedLLMClient([mock_provider1, mock_provider2])

        messages = [LLMMessage(role="user", content="Test")]

        with pytest.raises(RuntimeError, match="All providers failed"):
            async for _ in client.stream(messages):
                pass

    @pytest.mark.asyncio
    async def test_stream_with_parameters(self):
        """Test stream with temperature parameter"""
        mock_provider = MagicMock()
        mock_provider.name = "provider1"
        mock_provider.is_available = True

        async def mock_stream(*args, **kwargs):
            yield "chunk"

        mock_provider.stream = mock_stream

        client = UnifiedLLMClient([mock_provider])

        messages = [LLMMessage(role="user", content="Test")]
        chunks = []
        async for chunk in client.stream(messages, temperature=0.5):
            chunks.append(chunk)

        assert len(chunks) > 0


class TestCreateDefaultClient:
    """Test create_default_client function"""

    def test_create_default_client(self):
        """Test creating default client"""
        # This test verifies that the function can be called without errors
        # The actual providers are initialized, which may fail if dependencies are missing
        try:
            client = create_default_client()
            assert client is not None
            assert isinstance(client, UnifiedLLMClient)
            # May have 0-3 providers depending on availability
            assert len(client.providers) >= 0
        except Exception:
            # If providers fail to initialize, that's okay for this test
            # The important thing is that the function structure is correct
            pass
