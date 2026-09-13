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
        # TWO counters since 2026-09-11 (authz F2): the (ip, email) pair AND
        # email alone. Rotating the source IP used to reset the only one.
        keys = [call.args[0] for call in mock_redis.incr.call_args_list]
        assert keys == [
            "auth_fail:1.2.3.4:user@test.com",
            "auth_fail_email:user@test.com",
        ]

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
        assert any("ARMED again" in m for m in messages), (
            "an outage that ends without a line looks identical to one that never ended"
        )

    def test_the_first_report_does_not_claim_a_recovery_that_never_happened(self, caplog):
        """A process's first login has no outage behind it — saying "again" there
        invents a history, and someone reading this line mid-incident will act on it."""
        from backend.services.security.brute_force import report_armed_state

        with caplog.at_level(logging.DEBUG, logger=BF_LOGGER):
            report_armed_state(True)

        messages = [r.getMessage() for r in caplog.records]
        assert any("ARMED at startup" in m for m in messages)
        assert not any("again" in m for m in messages)

    def test_the_alarm_does_not_overstate_the_damage(self, caplog):
        """`/api/auth/login` is ALSO behind RateLimitMiddleware's "/api/" bucket at
        120/min per IP — measured live on prod via `x-ratelimit-limit`, and it
        survives a Redis outage on its in-memory fallback. Losing the brute-force
        detector costs the per-(ip+email) failure budget, NOT all rate limiting.
        An incident-time line that says "unlimited" sends the reader after the
        wrong thing — the exact defect this whole module exists to prevent."""
        from backend.services.security.brute_force import report_armed_state

        with caplog.at_level(logging.DEBUG, logger=BF_LOGGER):
            report_armed_state(False)

        msg = self._errors(caplog)[0].getMessage()
        assert "unlimited" not in msg.lower(), "the generic 120/min bucket still applies"
        assert "120/min" in msg, "name the protection that REMAINS, not just the one lost"

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


# =============================================================================
# F2 (2026-09-11 portal authz audit) — the lockout key was
# `auth_fail:{ip}:{email}`, so an attacker rotating source IPs reset the
# counter on every new IP. Against a KNOWN email the only remaining backstop
# was the generic 120 req/min-per-IP bucket, and a PIN is 4-6 digits
# (minimum 4 = 10,000 combinations). A second counter, keyed by email alone,
# is what makes IP rotation stop paying.
# =============================================================================


class TestPerEmailCounter:
    @pytest.mark.asyncio
    async def test_ip_rotation_still_accumulates_on_the_email_key(self):
        """The exploit, reproduced: 6 failures from 6 DIFFERENT IPs.

        Each pair key stays at 1 — under the pair threshold, so the old code
        never blocked anything — while the email key reaches 6.
        """
        from backend.services.security.brute_force import BruteForceDetector

        counters: dict[str, int] = {}

        async def incr(key: str) -> int:
            counters[key] = counters.get(key, 0) + 1
            return counters[key]

        mock_redis = AsyncMock()
        mock_redis.incr = incr
        detector = BruteForceDetector(redis_client=mock_redis)

        for i in range(6):
            await detector.record_failure(f"10.0.0.{i}", "victim@test.com")

        assert all(v == 1 for k, v in counters.items() if k.startswith("auth_fail:"))
        assert counters["auth_fail_email:victim@test.com"] == 6

    @pytest.mark.asyncio
    async def test_blocks_on_the_email_key_alone(self):
        from backend.services.security.brute_force import BruteForceDetector

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=31)
        detector = BruteForceDetector(
            redis_client=mock_redis,
            max_failures=5,
            email_max_failures=30,
        )
        await detector.record_failure("1.2.3.4", "u@t.com")

        blocked = [call.args[0] for call in mock_redis.setex.call_args_list]
        assert "auth_block_email:u@t.com" in blocked

    @pytest.mark.asyncio
    async def test_is_blocked_reads_the_email_key_when_the_pair_is_clean(self):
        """Guilt-proof: check only the pair key and this fails.

        A rotating attacker always presents a FRESH ip, so the pair block key
        never exists for them — the email block key is the only one that can
        stop the request.
        """
        from backend.services.security.brute_force import BruteForceDetector

        async def exists(key: str) -> int:
            return 1 if key == "auth_block_email:u@t.com" else 0

        mock_redis = AsyncMock()
        mock_redis.exists = exists
        detector = BruteForceDetector(redis_client=mock_redis)

        assert await detector.is_blocked("203.0.113.9", "u@t.com") is True

    @pytest.mark.asyncio
    async def test_is_blocked_false_when_neither_key_is_set(self):
        """INNOCENCE half: without it, `return True` would satisfy the proof
        above and lock every login out."""
        from backend.services.security.brute_force import BruteForceDetector

        async def exists(_key: str) -> int:
            return 0

        mock_redis = AsyncMock()
        mock_redis.exists = exists
        detector = BruteForceDetector(redis_client=mock_redis)

        assert await detector.is_blocked("203.0.113.9", "u@t.com") is False

    @pytest.mark.asyncio
    async def test_email_counter_is_still_fail_open_without_redis(self):
        """The documented degradation is unchanged — no new failure mode."""
        from backend.services.security.brute_force import BruteForceDetector

        detector = BruteForceDetector(redis_client=None)
        await detector.record_failure("1.2.3.4", "u@t.com")
        assert await detector.is_blocked("1.2.3.4", "u@t.com") is False
