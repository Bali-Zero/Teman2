"""Re-establish the Redis connection after a cache-ping failure."""

from __future__ import annotations

import redis

from backend.self_healing.actions.base import ActionResult


class ReconnectCacheAction:
    name = "reconnect_cache"
    target_check = "cache"

    def __init__(self, redis_url: str | None) -> None:
        self.redis_url = redis_url
        self.redis_client: redis.Redis | None = None

    async def run(self) -> ActionResult:
        if not self.redis_url:
            return ActionResult(success=False, error="redis_url not configured")
        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.redis_client.ping()
            return ActionResult(success=True, detail="reconnected")
        except Exception as exc:  # noqa: BLE001
            return ActionResult(success=False, error=f"{type(exc).__name__}: {exc}")
