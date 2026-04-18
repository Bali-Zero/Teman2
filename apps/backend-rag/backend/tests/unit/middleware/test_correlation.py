"""
Unit tests for the correlation-ID contextvar and its integration with
RequestTracingMiddleware + downstream middlewares.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from backend.middleware.correlation import (
    UNKNOWN_CORRELATION_ID,
    get_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from backend.middleware.request_tracing import RequestTracingMiddleware


class TestCorrelationContextVar:
    def test_default_is_unknown(self):
        assert get_correlation_id() == UNKNOWN_CORRELATION_ID

    def test_set_and_get(self):
        token = set_correlation_id("abc-123")
        try:
            assert get_correlation_id() == "abc-123"
        finally:
            reset_correlation_id(token)
        assert get_correlation_id() == UNKNOWN_CORRELATION_ID

    @pytest.mark.asyncio
    async def test_isolated_across_tasks(self):
        """Each asyncio task sees its own copy of the contextvar."""

        results: dict[str, str] = {}

        async def worker(name: str) -> None:
            token = set_correlation_id(f"id-{name}")
            try:
                await asyncio.sleep(0)  # yield control
                results[name] = get_correlation_id()
            finally:
                reset_correlation_id(token)

        await asyncio.gather(worker("a"), worker("b"), worker("c"))
        assert results == {"a": "id-a", "b": "id-b", "c": "id-c"}


class TestRequestTracingContextVarIntegration:
    @pytest.fixture
    def middleware(self):
        return RequestTracingMiddleware(MagicMock())

    @pytest.mark.asyncio
    async def test_dispatch_sets_and_resets_contextvar(self, middleware):
        """During call_next the contextvar is populated; after dispatch it resets."""
        seen: dict[str, str] = {}

        mock_request = MagicMock()
        mock_request.headers.get.side_effect = lambda k, d=None: (
            "inbound-abc" if k == "X-Request-Id" else None
        )
        mock_request.state = MagicMock()
        mock_request.state.request_id = None
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.query_params = {}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def call_next(_request):
            seen["during"] = get_correlation_id()
            return mock_response

        before = get_correlation_id()
        await middleware.dispatch(mock_request, call_next)
        after = get_correlation_id()

        assert seen["during"] == "inbound-abc"
        assert before == after == UNKNOWN_CORRELATION_ID

    @pytest.mark.asyncio
    async def test_contextvar_reset_on_exception(self, middleware):
        """If call_next raises, the contextvar is still reset in finally."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.state = MagicMock()
        mock_request.state.request_id = None
        mock_request.method = "GET"
        mock_request.url.path = "/boom"
        mock_request.query_params = {}

        async def call_next(_request):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await middleware.dispatch(mock_request, call_next)

        assert get_correlation_id() == UNKNOWN_CORRELATION_ID

    @pytest.mark.asyncio
    async def test_prefers_x_request_id_over_x_correlation_id(self, middleware):
        """X-Request-Id takes precedence over legacy X-Correlation-ID when both present."""
        mock_request = MagicMock()
        mock_request.headers.get.side_effect = lambda k, d=None: {
            "X-Request-Id": "canonical-id",
            "X-Correlation-ID": "legacy-id",
        }.get(k)
        mock_request.state = MagicMock()
        mock_request.state.request_id = None
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.query_params = {}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def call_next(_request):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)
        assert result.headers["X-Correlation-ID"] == "canonical-id"
        assert result.headers["X-Request-ID"] == "canonical-id"
