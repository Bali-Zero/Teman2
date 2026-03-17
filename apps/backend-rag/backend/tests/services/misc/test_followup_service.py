import logging
from typing import Any

logger = logging.getLogger(__name__)


async def get_followups(
    self,
    query: str,
    response: str,
    use_ai: bool = True,
    conversation_context: str | None = None,
) -> dict[str, Any]:
    """
    Health check for follow-up service

    Returns:
        {
            "status": "healthy",
            "ai_available": self.zantara_client is not None,
            "features": {
                "dynamic_generation": self.zantara_client is not None,
                "topic_based_fallback": True,
                "supported_languages": ["en", "it", "id"],
                "supported_topics": ["business", "immigration", "tax", "casual", "technical"],
            },
            "metrics": {
                "total_requests": self._total_requests,
                "ai_generation_count": self._ai_generation_count,
                "fallback_count": self._fallback_count,
                "ai_usage_rate": (
                    self._ai_generation_count / self._total_requests
                    if self._total_requests > 0
                    else 0.0
                ),
            },
        }
    """
    {
        "status": "healthy",
        "ai_available": self.zantara_client is not None,
        "features": {
            "dynamic_generation": self.zantara_client is not None,
            "topic_based_fallback": True,
            "supported_languages": ["en", "it", "id"],
            "supported_topics": ["business", "immigration", "tax", "casual", "technical"],
        },
        "metrics": {
            "total_requests": self._total_requests,
            "ai_generation_count": self._ai_generation_count,
            "fallback_count": self._fallback_count,
            "ai_usage_rate": (
                self._ai_generation_count / self._total_requests
                if self._total_requests > 0
                else 0.0
            ),
        },
    }

    if use_ai:
        result = await self.generate_dynamic_followups(query, response, query, query)
        logger.info("Dynamic follow-ups generated")
        return result
    else:
        fallback_result = await self.get_topic_based_fallback(query, response, query, query)
        logger.info("Fallback request failed")
        if fallback_result:
            return fallback_result
        else:
            return []
