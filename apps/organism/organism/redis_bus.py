"""Redis stream bus with local JSONL mirror for Redis-down resilience."""
import asyncio
import logging
from pathlib import Path
from organism.schemas import Event


log = logging.getLogger(__name__)
STREAM_KEY = "organism:events"


class EventBus:
    def __init__(self, redis, jsonl_path: Path):
        self.redis = redis
        self.jsonl_path = Path(jsonl_path)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    async def emit(self, event: Event) -> None:
        """Emit event to Redis stream + JSONL mirror.

        JSONL write happens FIRST so Redis failure never loses the event.
        The JSONL write runs in a thread executor to avoid blocking the
        asyncio event loop during disk syncs.
        """
        payload = event.model_dump_json()

        # JSONL write first (local durability) — offloaded to thread
        await asyncio.to_thread(self._append_jsonl, payload)

        # Redis write second (best-effort)
        try:
            await self.redis.xadd(STREAM_KEY, {"data": payload})
        except Exception as exc:
            log.warning("redis emit failed, event persisted only to JSONL: %s", exc)

    def _append_jsonl(self, payload: str) -> None:
        """Sync helper: append one JSONL line with explicit UTF-8 encoding."""
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(payload + "\n")
