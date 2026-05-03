"""Tests for CoverImageGenerator — focus on the persistent client (S09)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.article_composer.cover_image_generator import CoverImageGenerator


@pytest.fixture
def gen(monkeypatch: pytest.MonkeyPatch) -> CoverImageGenerator:
    monkeypatch.setenv("FIREWORKS_API_KEY", "fake-key")
    return CoverImageGenerator()


class TestClientLifecycle:
    def test_client_is_lazy(self, gen: CoverImageGenerator) -> None:
        assert gen._client is None

    @pytest.mark.asyncio
    async def test_client_reused_across_calls(self, gen: CoverImageGenerator) -> None:
        first = gen._get_client()
        second = gen._get_client()
        assert first is second
        await gen.aclose()

    @pytest.mark.asyncio
    async def test_aclose_is_idempotent(self, gen: CoverImageGenerator) -> None:
        _ = gen._get_client()
        await gen.aclose()
        await gen.aclose()  # must not raise

    @pytest.mark.asyncio
    async def test_aclose_allows_new_client_creation(self, gen: CoverImageGenerator) -> None:
        client_a = gen._get_client()
        await gen.aclose()
        client_b = gen._get_client()
        assert client_a is not client_b
        await gen.aclose()


class TestFireworksErrorHandling:
    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self, gen: CoverImageGenerator) -> None:
        fake_client = MagicMock()
        fake_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        fake_client.is_closed = False
        gen._client = fake_client

        result = await gen._fireworks("prompt")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_bytes_on_success(self, gen: CoverImageGenerator) -> None:
        fake_resp = MagicMock()
        fake_resp.content = b"X" * 6000  # > 5000 threshold
        fake_resp.raise_for_status = MagicMock()
        fake_client = MagicMock()
        fake_client.post = AsyncMock(return_value=fake_resp)
        fake_client.is_closed = False
        gen._client = fake_client

        result = await gen._fireworks("prompt")
        assert result == b"X" * 6000

    @pytest.mark.asyncio
    async def test_returns_none_for_undersized_response(self, gen: CoverImageGenerator) -> None:
        fake_resp = MagicMock()
        fake_resp.content = b"X" * 100  # < 5000 threshold
        fake_resp.raise_for_status = MagicMock()
        fake_client = MagicMock()
        fake_client.post = AsyncMock(return_value=fake_resp)
        fake_client.is_closed = False
        gen._client = fake_client

        result = await gen._fireworks("prompt")
        assert result is None


class TestPollinationsFallback:
    @pytest.mark.asyncio
    async def test_tries_both_models_on_failure(self, gen: CoverImageGenerator) -> None:
        fake_resp = MagicMock()
        fake_resp.status_code = 500
        fake_resp.content = b""
        fake_client = MagicMock()
        fake_client.get = AsyncMock(return_value=fake_resp)
        fake_client.is_closed = False
        gen._client = fake_client

        result = await gen._pollinations("prompt")
        assert result is None
        # Called twice: once for "sana", once for "turbo"
        assert fake_client.get.await_count == 2

    @pytest.mark.asyncio
    async def test_returns_bytes_on_first_model_success(self, gen: CoverImageGenerator) -> None:
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.content = b"X" * 6000
        fake_client = MagicMock()
        fake_client.get = AsyncMock(return_value=fake_resp)
        fake_client.is_closed = False
        gen._client = fake_client

        result = await gen._pollinations("prompt")
        assert result == b"X" * 6000
        assert fake_client.get.await_count == 1  # sana succeeded, no turbo retry
