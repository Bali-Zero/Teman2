"""
Brute force detection for login endpoint (S03 Sprint 3).

Uses IP+email pair to avoid NAT/coworking collateral blocking.
5 failures in 5 minutes per IP+email → 429 for 5 minutes.
Fail-open: Redis down = no blocking.

Fail-open means the login endpoint keeps serving with NO rate limiting at all,
so the one thing that must never be silent is the transition into that state.
It used to be: `RedisManager.get_async_client()` RETURNS None when Redis is
unavailable — it does not raise — so the detector constructed fine, every method
returned early on `if not self._redis`, and nothing was logged at any level. The
router's `except Exception: logger.debug(...)` never even ran, and prod sits at
`LOG_LEVEL=INFO` where a debug line is discarded anyway. `report_armed_state()`
below is the cure: it makes the disarmed state say so, out loud, exactly once
per transition. Family #2 (esiste ≠ armato) and W104 (a None/refusal that is not
an exception is still a refusal — judge the reply, not the absence of a raise).
"""

import logging
from typing import Any

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

DEFAULT_MAX_FAILURES = 5
DEFAULT_WINDOW_SECONDS = 300
DEFAULT_BLOCK_SECONDS = 300

# Process-wide last-reported state. None = nothing reported yet, so the first
# call always logs. Logging on TRANSITION (not per request) keeps an outage to
# two lines instead of one per login — which matters precisely because an
# unauthenticated endpoint is the one an attacker can drive at high volume.
_armed_state_reported: bool | None = None


def report_armed_state(armed: bool, *, reason: str = "") -> None:
    """Announce whether login rate limiting is actually armed, on change only.

    Call this at every login with the honest answer to "did I get a usable Redis
    client?". Silence here is the bug this function exists to prevent.
    """
    global _armed_state_reported
    first_report = _armed_state_reported is None
    if _armed_state_reported is armed:
        return
    _armed_state_reported = armed
    if armed:
        # "again" is only true after an outage. On the first report of a process
        # there was no outage to recover from, and a log line that misstates the
        # history is worse than no line at all when someone reads it mid-incident.
        logger.warning(
            "S03: login rate limiter ARMED %s",
            "at startup" if first_report else "again (Redis reachable)",
        )
    else:
        # Deliberately NOT "unlimited": /api/auth/login is ALSO covered by
        # RateLimitMiddleware's "/api/" prefix bucket at 120 req/min per client
        # IP (verified live on prod via the x-ratelimit-limit response header),
        # and that limiter keeps working through a Redis outage on its in-memory
        # fallback. What is lost here is the tight per-(ip+email) failure budget,
        # so state the real degradation — an incident-time line that overstates
        # the damage sends whoever reads it after the wrong thing.
        logger.error(
            "S03: login rate limiter NOT ARMED — per-(ip+email) failure budget "
            "is gone; /api/auth/login falls back to the generic 120/min per-IP "
            "bucket until Redis returns (%s)",
            reason or "no usable Redis client",
        )


def _reset_armed_state_for_tests() -> None:
    """Clear the process-wide transition memory. Tests only."""
    global _armed_state_reported
    _armed_state_reported = None


class BruteForceDetector:
    def __init__(
        self,
        redis_client: Any | None = None,
        max_failures: int = DEFAULT_MAX_FAILURES,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        block_seconds: int = DEFAULT_BLOCK_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._block_seconds = block_seconds

    def _fail_key(self, ip: str, email: str) -> str:
        return f"auth_fail:{ip}:{email.lower()}"

    def _block_key(self, ip: str, email: str) -> str:
        return f"auth_block:{ip}:{email.lower()}"

    async def is_blocked(self, ip: str, email: str) -> bool:
        if not self._redis:
            return False
        try:
            return bool(await self._redis.exists(self._block_key(ip, email)))
        except (RedisError, OSError) as e:
            logger.warning("S03: Brute force check failed (fail-open): %s", e)
            return False
        except Exception:
            logger.exception("S03: Brute force check unexpected error (fail-open)")
            return False

    async def record_failure(self, ip: str, email: str) -> None:
        if not self._redis:
            return
        try:
            key = self._fail_key(ip, email)
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, self._window_seconds)
            if count > self._max_failures:
                await self._redis.setex(
                    self._block_key(ip, email),
                    self._block_seconds,
                    f"brute_force:{count}_attempts",
                )
                logger.warning(
                    "S03: Brute force block ip=%s email=%s attempts=%s", ip, email, count
                )
        except (RedisError, OSError) as e:
            logger.warning("S03: Brute force record failed: %s", e)
        except Exception:
            logger.exception("S03: Brute force record unexpected error")

    async def clear_on_success(self, ip: str, email: str) -> None:
        if not self._redis:
            return
        try:
            await self._redis.delete(self._fail_key(ip, email), self._block_key(ip, email))
        except (RedisError, OSError) as e:
            logger.warning("S03: Brute force clear failed: %s", e)
        except Exception:
            logger.exception("S03: Brute force clear unexpected error")
