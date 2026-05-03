"""
Brute force detection for login endpoint (S03 Sprint 3).

Uses IP+email pair to avoid NAT/coworking collateral blocking.
5 failures in 5 minutes per IP+email → 429 for 5 minutes.
Fail-open: Redis down = no blocking.
"""

import logging
from typing import Any

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

DEFAULT_MAX_FAILURES = 5
DEFAULT_WINDOW_SECONDS = 300
DEFAULT_BLOCK_SECONDS = 300


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
            logger.warning(f"S03: Brute force check failed (fail-open): {e}")
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
                logger.warning(f"S03: Brute force block ip={ip} email={email} attempts={count}")
        except (RedisError, OSError) as e:
            logger.warning(f"S03: Brute force record failed: {e}")
        except Exception:
            logger.exception("S03: Brute force record unexpected error")

    async def clear_on_success(self, ip: str, email: str) -> None:
        if not self._redis:
            return
        try:
            await self._redis.delete(self._fail_key(ip, email), self._block_key(ip, email))
        except (RedisError, OSError) as e:
            logger.warning(f"S03: Brute force clear failed: {e}")
        except Exception:
            logger.exception("S03: Brute force clear unexpected error")
