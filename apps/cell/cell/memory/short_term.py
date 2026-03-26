"""Short-Term Memory — Redis with 24h TTL.
Key pattern: cell:stm:{timestamp}:{event_type}"""
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

@dataclass
class Observation:
    event_type: str
    data: dict[str, Any]
    timestamp: str = ""
    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

class ShortTermMemory:
    def __init__(self, redis: Any, ttl_seconds: int = 86400, max_bytes: int = 5_000_000) -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._max_bytes = max_bytes

    async def store(self, obs: Observation) -> None:
        key = f"cell:stm:{int(time.time())}:{obs.event_type}"
        value = json.dumps(asdict(obs))
        await self._redis.set(key, value, ex=self._ttl)

    async def recent(self, event_type: str = "", limit: int = 10) -> list[dict[str, Any]]:
        pattern = f"cell:stm:*:{event_type}" if event_type else "cell:stm:*"
        keys = await self._redis.keys(pattern)
        keys = sorted(keys, reverse=True)[:limit]
        results = []
        for key in keys:
            raw = await self._redis.get(key)
            if raw:
                data = raw if isinstance(raw, str) else raw.decode()
                results.append(json.loads(data))
        return results

    async def within_budget(self) -> bool:
        info = await self._redis.info()
        used = info.get("used_memory", 0)
        return used < self._max_bytes
