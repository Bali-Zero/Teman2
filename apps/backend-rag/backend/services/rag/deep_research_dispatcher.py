"""Deep Research Dispatcher — background research for novel/low-confidence queries.

When the CRAG router determines that retrieval confidence is too low for a
reliable answer, dispatches a background research job. The user gets an immediate
best-effort response with a disclaimer, and the full research result is available
via polling endpoint.

# Organo: backend-rag/rag → produce research job → consuma da worker + API
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Redis keys
QUEUE_KEY = "zantara:deep_research:queue"
RESULT_PREFIX = "zantara:deep_research:result:"
RESULT_TTL = 86400  # 24 hours


@dataclass
class ResearchJob:
    """A deep research job queued for background processing."""

    job_id: str = ""
    query: str = ""
    domain: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | processing | completed | failed
    result: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if not self.job_id:
            self.job_id = str(uuid.uuid4())


class DeepResearchDispatcher:
    """Dispatches and tracks background deep research jobs.

    Uses Redis as a lightweight job queue. Jobs are processed by a separate
    worker (cron or long-running process) that calls NLM deep research.

    Graceful degradation: if Redis is unavailable, dispatch silently fails
    and the user still gets their best-effort answer.
    """

    def __init__(self, redis_client: Any = None) -> None:
        self._redis = redis_client

    async def dispatch(
        self,
        query: str,
        domain: str = "",
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """Dispatch a deep research job. Returns job_id or None on failure.

        Args:
            query: The user query requiring deep research.
            domain: Query domain for routing.
            context: Additional context (entities, user info).

        Returns:
            job_id string for tracking, or None if dispatch fails.
        """
        if self._redis is None:
            logger.debug("Deep research: no Redis client, skipping dispatch")
            return None

        job = ResearchJob(
            query=query,
            domain=domain,
            context=context or {},
        )

        try:
            payload = json.dumps(asdict(job))
            await self._redis.rpush(QUEUE_KEY, payload)

            # Store initial job status
            result_key = f"{RESULT_PREFIX}{job.job_id}"
            await self._redis.set(
                result_key,
                json.dumps({"status": "pending", "job_id": job.job_id}),
                ex=RESULT_TTL,
            )

            logger.info(
                "Deep research: dispatched job %s for query: %s",
                job.job_id,
                query[:50],
            )
            return job.job_id

        except Exception as exc:
            logger.warning("Deep research: dispatch failed (%s)", exc)
            return None

    async def check_result(self, job_id: str) -> dict[str, Any] | None:
        """Check if a deep research result is available.

        Args:
            job_id: The job ID returned by dispatch().

        Returns:
            Dict with status and result, or None if not found.
        """
        if self._redis is None:
            return None

        try:
            result_key = f"{RESULT_PREFIX}{job_id}"
            data = await self._redis.get(result_key)
            if data:
                return json.loads(data)
        except Exception as exc:
            logger.debug("Deep research: check_result failed (%s)", exc)

        return None

    async def complete_job(
        self,
        job_id: str,
        result: str,
        status: str = "completed",
    ) -> bool:
        """Mark a job as completed with its result.

        Called by the worker process after finishing research.

        Args:
            job_id: The job ID.
            result: The research result text.
            status: "completed" or "failed".

        Returns:
            True if stored successfully.
        """
        if self._redis is None:
            return False

        try:
            result_key = f"{RESULT_PREFIX}{job_id}"
            await self._redis.set(
                result_key,
                json.dumps({
                    "status": status,
                    "job_id": job_id,
                    "result": result,
                }),
                ex=RESULT_TTL,
            )
            return True
        except Exception as exc:
            logger.warning("Deep research: complete_job failed (%s)", exc)
            return False

    async def pending_count(self) -> int:
        """Get the number of pending jobs in the queue."""
        if self._redis is None:
            return 0
        try:
            return await self._redis.llen(QUEUE_KEY)
        except Exception:
            return 0
