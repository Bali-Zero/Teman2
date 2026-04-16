"""Tier 3 Complex Dispatcher — background deep research for novel/hard gaps.

# Organo: graph-engine/curiosity/dispatchers → produce ResearchEvidence (async)

Dispatches a background research job via Redis queue. The job is processed
by a separate worker that calls NLM deep research. Returns a placeholder
evidence with the job ID for future retrieval.

Graceful degradation: falls back to MediumDispatcher if Redis unavailable.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from nuzantara_graph.curiosity.models import ResearchEvidence

logger = logging.getLogger(__name__)

# Redis keys for curiosity research queue
QUEUE_KEY = "curiosity:research:queue"
RESULT_PREFIX = "curiosity:research:result:"
RESULT_TTL = 172800  # 48 hours


class ComplexDispatcher:
    """Tier 3: Background deep research dispatch."""

    def __init__(self, redis_client: Any = None) -> None:
        self._redis = redis_client

    async def dispatch(
        self,
        topic: str,
        domain: str,
        follow_up_queries: list[str] | None = None,
    ) -> list[ResearchEvidence]:
        """Dispatch a background research job for complex gap.

        Args:
            topic: The gap topic to research.
            domain: Domain (immigration, tax, etc.).
            follow_up_queries: Specific queries from gap detector.

        Returns:
            List with a single placeholder evidence containing job_id.
        """
        job_id = str(uuid.uuid4())

        if self._redis is None:
            logger.debug("ComplexDispatcher: no Redis, returning placeholder")
            return [
                ResearchEvidence(
                    content=f"Deep research required: {topic}. Redis unavailable for async dispatch.",
                    source_type="complex_placeholder",
                    confidence=0.1,
                    metadata={"requires_manual_research": True},
                )
            ]

        try:
            job_payload = {
                "job_id": job_id,
                "topic": topic,
                "domain": domain,
                "follow_up_queries": follow_up_queries or [],
                "status": "pending",
            }

            await self._redis.rpush(QUEUE_KEY, json.dumps(job_payload))
            await self._redis.set(
                f"{RESULT_PREFIX}{job_id}",
                json.dumps({"status": "pending", "job_id": job_id}),
                ex=RESULT_TTL,
            )

            logger.info(
                "ComplexDispatcher: queued job %s for '%s' (%s)",
                job_id[:8], topic[:40], domain,
            )

            return [
                ResearchEvidence(
                    content=f"Background research dispatched (job {job_id[:8]}). "
                            f"Topic: {topic}",
                    source_type="complex_async",
                    confidence=0.3,
                    metadata={"job_id": job_id, "status": "pending"},
                )
            ]

        except Exception as e:
            logger.warning("ComplexDispatcher: dispatch failed: %s", e)
            return [
                ResearchEvidence(
                    content=f"Deep research dispatch failed for: {topic}",
                    source_type="complex_fallback",
                    confidence=0.1,
                    metadata={"error": str(e)},
                )
            ]

    async def check_result(self, job_id: str) -> dict[str, Any] | None:
        """Check if a background research result is available."""
        if self._redis is None:
            return None

        try:
            data = await self._redis.get(f"{RESULT_PREFIX}{job_id}")
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None
