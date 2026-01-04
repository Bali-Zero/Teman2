"""
Unit tests for DeepSeek Provider - 99% Coverage
Tests all methods, error cases, and edge cases
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the classes we need to test
from llm.base import LLMMessage, LLMResponse


@pytest.mark.unit
class TestDeepSeekProvider:
    """Comprehensive unit tests for DeepSeek provider targeting 99% coverage"""

    def test_init_default_model(self):
        """Test DeepSeekProvider initialization with default model"""
        with patch("llm.providers.deepseek.logger") as mock_logger:
            # Mock the DeepSeekClient from the correct import path
            with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.is_available = True
                mock_client_class.return_value = mock_client

                from llm.providers.deepseek import DeepSeekProvider

                provider = DeepSeekProvider()

                assert provider._model == "deepseek-chat"
                assert provider._client == mock_client
                assert provider._available is True
                mock_client_class.assert_called_once()
                mock_logger.info.assert_called_once()

    def test_init_custom_model(self):
        """Test DeepSeekProvider initialization with custom model"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider(model="deepseek-coder")

            assert provider._model == "deepseek-coder"
            assert provider._available is True

    def test_init_client_import_failure(self):
        """Test initialization failure when DeepSeekClient cannot be imported"""
        with patch("llm.providers.deepseek.logger") as mock_logger:
            # Force import error by patching the import inside the _init_client method
            with patch.object(__import__, "__import__", side_effect=ImportError("No module")):
                from llm.providers.deepseek import DeepSeekProvider

                provider = DeepSeekProvider()

                assert provider._client is None
                assert provider._available is False
                mock_logger.warning.assert_called_once()

    def test_init_client_initialization_failure(self):
        """Test initialization failure when DeepSeekClient raises exception"""
        with patch("llm.providers.deepseek.logger") as mock_logger:
            with patch(
                "services.llm_clients.deepseek_client.DeepSeekClient",
                side_effect=Exception("Client init failed"),
            ):
                from llm.providers.deepseek import DeepSeekProvider

                provider = DeepSeekProvider()

                assert provider._client is None
                assert provider._available is False
                mock_logger.warning.assert_called_once()

    def test_init_client_not_available(self):
        """Test initialization when DeepSeekClient.is_available is False"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = False
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()

            assert provider._client == mock_client
            assert provider._available is False

    def test_name_property(self):
        """Test provider name property"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()
            assert provider.name == "deepseek"

    def test_is_available_property_true(self):
        """Test is_available property when client is available"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()
            assert provider.is_available is True

    def test_is_available_property_false(self):
        """Test is_available property when client is not available"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = False
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()
            assert provider.is_available is False

    def test_is_available_property_no_client(self):
        """Test is_available property when client is None"""
        with patch("llm.providers.deepseek.logger"):
            with patch(
                "services.llm_clients.deepseek_client.DeepSeekClient",
                side_effect=Exception("Init failed"),
            ):
                from llm.providers.deepseek import DeepSeekProvider

                provider = DeepSeekProvider()
                assert provider.is_available is False

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful response generation"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            # Setup mock client
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_result = MagicMock()
            mock_result.content = "Generated response"
            mock_result.model_name = "deepseek-chat"
            mock_result.input_tokens = 10
            mock_result.output_tokens = 20
            mock_result.finish_reason = "stop"
            mock_client.complete = AsyncMock(return_value=mock_result)
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()

            # Test messages
            messages = [
                LLMMessage(role="user", content="Hello"),
                LLMMessage(role="system", content="You are helpful"),
            ]

            response = await provider.generate(messages=messages, temperature=0.5, max_tokens=1000)

            assert isinstance(response, LLMResponse)
            assert response.content == "Generated response"
            assert response.model == "deepseek-chat"
            assert response.tokens_used == 30  # 10 + 20
            assert response.provider == "deepseek"
            assert response.finish_reason == "stop"

            # Verify client was called correctly
            mock_client.complete.assert_called_once_with(
                messages=[
                    {"role": "user", "content": "Hello"},
                    {"role": "system", "content": "You are helpful"},
                ],
                model="deepseek-chat",
                temperature=0.5,
                max_tokens=1000,
            )

    @pytest.mark.asyncio
    async def test_generate_not_available(self):
        """Test generate when provider is not available"""
        with patch("llm.providers.deepseek.logger"):
            with patch(
                "services.llm_clients.deepseek_client.DeepSeekClient",
                side_effect=Exception("Init failed"),
            ):
                from llm.providers.deepseek import DeepSeekProvider

                provider = DeepSeekProvider()

                messages = [LLMMessage(role="user", content="Hello")]

                with pytest.raises(RuntimeError, match="DeepSeek provider not available"):
                    await provider.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_with_default_parameters(self):
        """Test generate with default temperature and max_tokens"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_result = MagicMock()
            mock_result.content = "Response"
            mock_result.model_name = "deepseek-chat"
            mock_result.input_tokens = 5
            mock_result.output_tokens = 10
            mock_result.finish_reason = "stop"
            mock_client.complete = AsyncMock(return_value=mock_result)
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()
            messages = [LLMMessage(role="user", content="Hello")]

            response = await provider.generate(messages)

            assert response.content == "Response"
            mock_client.complete.assert_called_once_with(
                messages=[{"role": "user", "content": "Hello"}],
                model="deepseek-chat",
                temperature=0.7,  # Default
                max_tokens=4096,  # Default
            )

    @pytest.mark.asyncio
    async def test_stream_success(self):
        """Test successful streaming response"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = True

            # Create async iterator mock
            async def mock_stream():
                chunks = ["Hello", " world", "!"]
                for chunk in chunks:
                    yield chunk

            mock_client.complete_stream = AsyncMock()
            mock_client.complete_stream.return_value = mock_stream()
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()
            messages = [LLMMessage(role="user", content="Say hello")]

            # Collect streamed chunks
            chunks = []
            async for chunk in provider.stream(messages, temperature=0.3, max_tokens=100):
                chunks.append(chunk)

            assert chunks == ["Hello", " world", "!"]

            # Verify client was called correctly
            mock_client.complete_stream.assert_called_once_with(
                messages=[{"role": "user", "content": "Say hello"}],
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=100,
            )

    @pytest.mark.asyncio
    async def test_stream_not_available(self):
        """Test stream when provider is not available"""
        with patch("llm.providers.deepseek.logger"):
            with patch(
                "services.llm_clients.deepseek_client.DeepSeekClient",
                side_effect=Exception("Init failed"),
            ):
                from llm.providers.deepseek import DeepSeekProvider

                provider = DeepSeekProvider()
                messages = [LLMMessage(role="user", content="Hello")]

                with pytest.raises(RuntimeError, match="DeepSeek provider not available"):
                    async for chunk in provider.stream(messages):
                        pass

    @pytest.mark.asyncio
    async def test_stream_with_default_parameters(self):
        """Test stream with default parameters"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = True

            async def mock_stream():
                yield "test"

            mock_client.complete_stream = AsyncMock()
            mock_client.complete_stream.return_value = mock_stream()
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()
            messages = [LLMMessage(role="user", content="Test")]

            chunks = []
            async for chunk in provider.stream(messages):
                chunks.append(chunk)

            assert chunks == ["test"]
            mock_client.complete_stream.assert_called_once_with(
                messages=[{"role": "user", "content": "Test"}],
                model="deepseek-chat",
                temperature=0.7,  # Default
                max_tokens=8192,  # Default from kwargs.get
            )

    @pytest.mark.asyncio
    async def test_stream_with_kwargs(self):
        """Test stream with additional kwargs"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = True

            async def mock_stream():
                yield "test"

            mock_client.complete_stream = AsyncMock()
            mock_client.complete_stream.return_value = mock_stream()
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()
            messages = [LLMMessage(role="user", content="Test")]

            chunks = []
            async for chunk in provider.stream(messages, temperature=0.5, max_tokens="value"):
                chunks.append(chunk)

            assert chunks == ["test"]
            mock_client.complete_stream.assert_called_once_with(
                messages=[{"role": "user", "content": "Test"}],
                model="deepseek-chat",
                temperature=0.5,
                max_tokens="value",  # From kwargs.get
            )

    @pytest.mark.asyncio
    async def test_generate_with_kwargs(self):
        """Test generate with additional kwargs"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_result = MagicMock()
            mock_result.content = "Response"
            mock_result.model_name = "deepseek-chat"
            mock_result.input_tokens = 5
            mock_result.output_tokens = 10
            mock_result.finish_reason = "stop"
            mock_client.complete = AsyncMock(return_value=mock_result)
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()
            messages = [LLMMessage(role="user", content="Test")]

            response = await provider.generate(
                messages, temperature=0.5, max_tokens=1000, custom_param="value"
            )

            assert response.content == "Response"
            # Verify kwargs are passed through
            call_kwargs = mock_client.complete.call_args[1]
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 1000
            assert "custom_param" in call_kwargs

    def test_message_conversion(self):
        """Test that LLMMessage objects are correctly converted to OpenAI format"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_result = MagicMock()
            mock_result.content = "Test response"
            mock_result.model_name = "deepseek-chat"
            mock_result.input_tokens = 5
            mock_result.output_tokens = 5
            mock_result.finish_reason = "stop"
            mock_client.complete = AsyncMock(return_value=mock_result)
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()

            # Test different message roles
            messages = [
                LLMMessage(role="system", content="System prompt"),
                LLMMessage(role="user", content="User message"),
                LLMMessage(role="assistant", content="Assistant response"),
                LLMMessage(role="developer", content="Developer instruction"),
            ]

            # We'll call generate and check the call args
            import asyncio

            asyncio.run(provider.generate(messages))

            # Verify message conversion
            call_args = mock_client.complete.call_args
            expected_messages = [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "User message"},
                {"role": "assistant", "content": "Assistant response"},
                {"role": "developer", "content": "Developer instruction"},
            ]
            assert call_args[0]["messages"] == expected_messages

    @pytest.mark.asyncio
    async def test_response_token_calculation(self):
        """Test token calculation in LLMResponse"""
        with patch("services.llm_clients.deepseek_client.DeepSeekClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.is_available = True
            mock_result = MagicMock()
            mock_result.content = "Response"
            mock_result.model_name = "deepseek-chat"
            mock_result.input_tokens = 100
            mock_result.output_tokens = 50
            mock_result.finish_reason = "length"
            mock_client.complete = AsyncMock(return_value=mock_result)
            mock_client_class.return_value = mock_client

            from llm.providers.deepseek import DeepSeekProvider

            provider = DeepSeekProvider()
            messages = [LLMMessage(role="user", content="Test")]

            response = await provider.generate(messages)

            # Verify token calculation
            assert response.tokens_used == 150  # 100 + 50
            assert response.finish_reason == "length"
