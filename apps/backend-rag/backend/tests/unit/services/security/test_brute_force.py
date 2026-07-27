"""Tests for brute force detection — S03 Sprint 3."""

import logging
from unittest.mock import AsyncMock

import pytest

BF_LOGGER = "backend.services.security.brute_force"


class TestBruteForceDetection:
    @pytest.mark.asyncio
    async def test_record_failure_increments_counter(self):
        from backend.services.security.brute_force import BruteForceDetector

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        detector = BruteForceDetector(redis_client=mock_redis)
        await detector.record_failure("1.2.3.4", "user@test.com")
        mock_redis.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_blocked_false_under_threshold(self):
        from backend.services.security.brute_force import BruteForceDetector

        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        detector = BruteForceDetector(redis_client=mock_redis)
        assert await detector.is_blocked("1.2.3.4", "u@t.com") is False

    @pytest.mark.asyncio
    async def test_is_blocked_true_when_blocked(self):
        from backend.services.security.brute_force import BruteForceDetector

        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        detector = BruteForceDetector(redis_client=mock_redis)
        assert await detector.is_blocked("1.2.3.4", "u@t.com") is True

    @pytest.mark.asyncio
    async def test_blocks_after_threshold(self):
        from backend.services.security.brute_force import BruteForceDetector

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=6)
        mock_redis.expire = AsyncMock()
        mock_redis.setex = AsyncMock()
        detector = BruteForceDetector(redis_client=mock_redis, max_failures=5)
        await detector.record_failure("1.2.3.4", "u@t.com")
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_graceful_redis_unavailable(self):
        from backend.services.security.brute_force import BruteForceDetector

        detector = BruteForceDetector(redis_client=None)
        assert await detector.is_blocked("1.2.3.4", "u@t.com") is False

    @pytest.mark.asyncio
    async def test_clear_on_success(self):
        from backend.services.security.brute_force import BruteForceDetector

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        detector = BruteForceDetector(redis_client=mock_redis)
        await detector.clear_on_success("1.2.3.4", "u@t.com")
        mock_redis.delete.assert_called()


class TestArmedStateIsAudible:
    """The login rate limiter may fail open, but it may not fail SILENT.

    `test_graceful_redis_unavailable` above pins the silence as correct
    behaviour for the detector itself — and it is: fail-open is deliberate.
    What was missing is anyone SAYING so. These are the guilt/innocence pair
    for that announcement.
    """

    @pytest.fixture(autouse=True)
    def _reset_transition_memory(self):
        from backend.services.security.brute_force import _reset_armed_state_for_tests

        _reset_armed_state_for_tests()
        yield
        _reset_armed_state_for_tests()

    @staticmethod
    def _errors(caplog):
        return [r for r in caplog.records if r.levelno >= logging.ERROR]

    def test_guilt_disarmed_is_reported_at_error(self, caplog):
        from backend.services.security.brute_force import report_armed_state

        with caplog.at_level(logging.DEBUG, logger=BF_LOGGER):
            report_armed_state(False, reason="no usable Redis client")

        errors = self._errors(caplog)
        assert len(errors) == 1, "a disarmed rate limiter must produce exactly one ERROR"
        assert "NOT ARMED" in errors[0].getMessage()

    def test_innocence_armed_never_logs_an_error(self, caplog):
        from backend.services.security.brute_force import report_armed_state

        with caplog.at_level(logging.DEBUG, logger=BF_LOGGER):
            report_armed_state(True)

        assert self._errors(caplog) == [], "a healthy limiter must not cry wolf"

    def test_a_flood_of_logins_cannot_flood_the_log(self, caplog):
        """An unauthenticated endpoint is exactly the one an attacker can drive
        at volume — reporting per request would turn the alarm into the DoS."""
        from backend.services.security.brute_force import report_armed_state

        with caplog.at_level(logging.DEBUG, logger=BF_LOGGER):
            for _ in range(50):
                report_armed_state(False)

        assert len(self._errors(caplog)) == 1

    def test_recovery_is_announced_too(self, caplog):
        from backend.services.security.brute_force import report_armed_state

        with caplog.at_level(logging.DEBUG, logger=BF_LOGGER):
            report_armed_state(False)
            report_armed_state(True)

        messages = [r.getMessage() for r in caplog.records]
        assert any("NOT ARMED" in m for m in messages)
        assert any("ARMED (Redis reachable again)" in m for m in messages), (
            "an outage that ends without a line looks identical to one that never ended"
        )

    def test_a_none_client_is_the_disarmed_case(self, caplog):
        """The realistic failure: get_async_client() RETURNS None, never raises."""
        from backend.services.security.brute_force import (
            BruteForceDetector,
            report_armed_state,
        )

        redis_client = None  # what RedisManager hands back when Redis is down
        with caplog.at_level(logging.DEBUG, logger=BF_LOGGER):
            report_armed_state(redis_client is not None)
            BruteForceDetector(redis_client=redis_client)

        assert len(self._errors(caplog)) == 1
