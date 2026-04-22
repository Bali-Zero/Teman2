"""Circuit breaker — per-target failure counter with TTL-based cooldown.

Prevents action loops: if the same actuator fails on the same target more
than max_tries times within cooldown_seconds, further attempts are blocked
until the counter naturally expires (quarantine the target).
"""


CB_KEY_PREFIX = "organism:cb:"
DEFAULT_MAX_TRIES = 2
DEFAULT_COOLDOWN_SECONDS = 15 * 60  # 15 min


class CircuitBreaker:
    def __init__(
        self,
        *,
        redis,
        max_tries: int = DEFAULT_MAX_TRIES,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ):
        self.redis = redis
        self.max_tries = max_tries
        self.cooldown_seconds = cooldown_seconds

    async def allow(self, target: str) -> bool:
        key = CB_KEY_PREFIX + target
        raw = await self.redis.get(key)
        if raw is None:
            return True
        try:
            count = int(raw)
        except (ValueError, TypeError):
            return True
        return count < self.max_tries

    async def record_failure(self, target: str) -> int:
        key = CB_KEY_PREFIX + target
        count = await self.redis.incr(key)
        await self.redis.expire(key, self.cooldown_seconds)
        return int(count)

    async def record_success(self, target: str) -> None:
        await self.redis.delete(CB_KEY_PREFIX + target)
