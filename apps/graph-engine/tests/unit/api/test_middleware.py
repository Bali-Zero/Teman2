"""Tests for API middleware — auth and rate limiting."""

import pytest
from unittest.mock import MagicMock

from nuzantara_graph.api.middleware import (
    _RateLimitStore,
    get_current_user,
)


class TestRateLimiter:
    def test_allows_within_limit(self):
        store = _RateLimitStore()
        for _ in range(5):
            assert store.check("user1", max_rpm=10) is True

    def test_blocks_over_limit(self):
        store = _RateLimitStore()
        for _ in range(10):
            store.check("user1", max_rpm=10)
        assert store.check("user1", max_rpm=10) is False

    def test_different_users_independent(self):
        store = _RateLimitStore()
        for _ in range(10):
            store.check("user1", max_rpm=10)
        # user2 should still be allowed
        assert store.check("user2", max_rpm=10) is True

    def test_remaining_calculation(self):
        store = _RateLimitStore()
        for _ in range(3):
            store.check("user1", max_rpm=10)
        assert store.remaining("user1", max_rpm=10) == 7

    def test_remaining_zero_when_full(self):
        store = _RateLimitStore()
        for _ in range(10):
            store.check("user1", max_rpm=10)
        assert store.remaining("user1", max_rpm=10) == 0


class TestAuth:
    @pytest.mark.asyncio
    async def test_no_auth_header_returns_anonymous(self):
        request = MagicMock()
        request.headers = {}
        user = await get_current_user(request)
        assert user["user_id"] == "anonymous"
        assert user["authenticated"] is False

    @pytest.mark.asyncio
    async def test_empty_bearer_returns_anonymous(self):
        request = MagicMock()
        request.headers = {"authorization": "Bearer "}
        user = await get_current_user(request)
        assert user["user_id"] == "anonymous"
        assert user["authenticated"] is False

    @pytest.mark.asyncio
    async def test_non_bearer_returns_anonymous(self):
        request = MagicMock()
        request.headers = {"authorization": "Basic dXNlcjpwYXNz"}
        user = await get_current_user(request)
        assert user["user_id"] == "anonymous"
        assert user["authenticated"] is False
