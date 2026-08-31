"""
Unit tests for GenAIClient
Target: 100% coverage
Composer: 3
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.genai_client import GenAIClient, get_genai_client


@pytest.fixture
def genai_client():
    """Create GenAI client instance"""
    with (
        patch("backend.llm.genai_client.genai") as mock_genai,
        patch("backend.llm.genai_client.types"),
        patch("backend.llm.genai_client.GENAI_AVAILABLE", True),
    ):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        client = GenAIClient(api_key="test-key")
        client._client = mock_client
        client._available = True
        return client


class TestGenAIClient:
    """Tests for GenAIClient"""

    def test_init(self):
        """Test initialization"""
        with (
            patch("backend.llm.genai_client.genai") as mock_genai,
            patch("backend.llm.genai_client.GENAI_AVAILABLE", True),
        ):
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            client = GenAIClient(api_key="test-key")
            assert client is not None

    @pytest.mark.asyncio
    async def test_generate_content(self, genai_client):
        """Test content generation"""
        mock_response = MagicMock()
        mock_response.text = "test response"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20

        genai_client._client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await genai_client.generate_content("test prompt")
        assert result["text"] == "test response"
        assert result["model"] == genai_client.DEFAULT_MODEL
        assert "usage" in result

    @pytest.mark.asyncio
    async def test_generate_content_stream(self, genai_client):
        """Test streaming content generation"""
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "chunk1"
        mock_chunk2 = MagicMock()
        mock_chunk2.text = "chunk2"

        # CORRECTED 2026-08-26. This mock used to be an async GENERATOR function,
        # with a comment asserting the mock "must return async generator directly".
        # The real SDK has never had that shape: on both google-genai 1.75.0 (local
        # venv) and 2.18.1 (the version requirements.lock.txt and
        # requirements-prod.lock.txt pin, i.e. what CI and production actually run),
        # `AsyncModels.generate_content_stream` is a COROUTINE FUNCTION --
        # inspect.iscoroutinefunction() is True and isasyncgenfunction() is False.
        # So this test was green over a call path that raised TypeError on every
        # real invocation. The mock now matches the SDK: a coroutine that resolves
        # to the async iterator.
        async def mock_stream(*args, **kwargs):
            async def _chunks():
                yield mock_chunk1
                yield mock_chunk2

            return _chunks()

        genai_client._client.aio.models.generate_content_stream = mock_stream

        chunks = []
        async for chunk in genai_client.generate_content_stream("test"):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0] == "chunk1"
        assert chunks[1] == "chunk2"

    def test_get_genai_client_singleton(self):
        """Test singleton pattern"""
        import backend.llm.genai_client as genai_client_module

        with (
            patch("backend.llm.genai_client.genai") as mock_genai,
            patch("backend.llm.genai_client.GENAI_AVAILABLE", True),
        ):
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            genai_client_module._client_instance = None

            client1 = get_genai_client()
            client2 = get_genai_client()
            assert client1 is client2

    @pytest.mark.asyncio
    async def test_generate_content_failure_records_enriched_error_class(self, genai_client):
        """Wiring test: a real ClientError raised from the SDK call must
        reach `record_llm_call`'s `error_class` kwarg through the enriched
        label, not the bare `type(e).__name__` this replaced. The helper
        function is unit-tested in isolation in test_gemini_error_label.py;
        this proves the write site actually calls it."""
        from google.genai.errors import ClientError

        quota_exc = ClientError(429, {"status": "RESOURCE_EXHAUSTED", "message": "depleted"})
        genai_client._client.aio.models.generate_content = AsyncMock(side_effect=quota_exc)

        with patch(
            "backend.services.observability.record_llm_call", new=AsyncMock()
        ) as mock_record:
            with pytest.raises(ClientError):
                await genai_client.generate_content("test prompt")

        mock_record.assert_awaited_once()
        recorded_error_class = mock_record.await_args.kwargs["error_class"]
        assert recorded_error_class == "ClientError:429:RESOURCE_EXHAUSTED"

    @pytest.mark.asyncio
    async def test_generate_content_ordinary_400_is_not_recorded_as_quota(self, genai_client):
        """Innocence at the wiring level: a 400 must never land in the
        ledger under a label that names quota/RESOURCE_EXHAUSTED."""
        from google.genai.errors import ClientError

        bad_request_exc = ClientError(400, {"status": "INVALID_ARGUMENT", "message": "bad"})
        genai_client._client.aio.models.generate_content = AsyncMock(side_effect=bad_request_exc)

        with patch(
            "backend.services.observability.record_llm_call", new=AsyncMock()
        ) as mock_record:
            with pytest.raises(ClientError):
                await genai_client.generate_content("test prompt")

        recorded_error_class = mock_record.await_args.kwargs["error_class"]
        assert "RESOURCE_EXHAUSTED" not in recorded_error_class
        assert recorded_error_class == "ClientError:400:INVALID_ARGUMENT"

    @pytest.mark.asyncio
    async def test_generate_content_success_never_touched_by_error_labelling(self, genai_client):
        """Robustness at the wiring level: a successful call records
        `error_class=None` and is never put at risk by the labelling path."""
        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 5
        mock_response.usage_metadata.candidates_token_count = 5
        genai_client._client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch(
            "backend.services.observability.record_llm_call", new=AsyncMock()
        ) as mock_record:
            result = await genai_client.generate_content("test prompt")

        assert result["text"] == "ok"
        assert mock_record.await_args.kwargs["error_class"] is None
        assert mock_record.await_args.kwargs["success"] is True
