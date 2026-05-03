"""
LLM Metrics Emitter — S12 R5

Emits structured LLM call metrics to Redis Stream `llm:metrics`.
Graceful degradation: if Redis is unavailable, metrics are dropped (no exception propagated).

Stream key: llm:metrics
Fields per entry: provider, model, latency_ms, prompt_tokens, completion_tokens, status
MAXLEN: 10,000 (sliding window ~7 days at 1K calls/day)

Consumer: any future cost dashboard or alerting pipeline can XREAD from llm:metrics.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_STREAM_KEY = "llm:metrics"
_STREAM_MAXLEN = 10_000


def _get_redis() -> Any | None:
    """Return the async Redis client from RedisManager, or None if unavailable."""
    try:
        from backend.core.redis_manager import RedisManager

        mgr = RedisManager.get_instance()
        return mgr.async_client if mgr.is_available else None
    except Exception:
        return None


async def emit_llm_metric(
    *,
    provider: str,
    model: str,
    latency_ms: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    status: str = "ok",
    extra: dict[str, str] | None = None,
) -> None:
    """
    Emit a single LLM call metric to Redis Stream.

    Args:
        provider: 'ollama' | 'gemini' | 'claude' | 'openrouter'
        model: model identifier
        latency_ms: wall-clock time for the call
        prompt_tokens: input tokens (0 if unknown)
        completion_tokens: output tokens (0 if unknown)
        status: 'ok' | 'error' | 'timeout'
        extra: optional additional fields (string values only)
    """
    redis = _get_redis()
    if redis is None:
        return

    fields: dict[str, str] = {
        "provider": provider,
        "model": model,
        "latency_ms": str(latency_ms),
        "prompt_tokens": str(prompt_tokens),
        "completion_tokens": str(completion_tokens),
        "status": status,
        "ts": str(int(time.time())),
    }
    if extra:
        fields.update(extra)

    try:
        await redis.xadd(_STREAM_KEY, fields, maxlen=_STREAM_MAXLEN, approximate=True)
    except Exception as e:
        logger.debug(f"LLM metrics emit failed (non-critical): {e}")
