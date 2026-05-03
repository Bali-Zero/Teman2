"""HGT Publisher — broadcasts high-confidence skills to Redis Stream.

# Organo: cell-core L0 → produces cell:skills events → consumed by HGT consumers
# If fails: skill still recorded in local genome, just not shared (graceful degradation)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cell_core.hgt.publisher")

# Stream name for horizontal gene transfer
STREAM_SKILLS = "cell:skills"


class HGTPublisher:
    """Publishes eligible skills to Redis Stream ``cell:skills``.

    A skill is eligible if:
    - confidence >= CONFIDENCE_THRESHOLD (0.7)
    - scope == 'Project' (germline, not somatic)
    - type != 'scar' (scars are Personal by definition)

    Usage::

        publisher = HGTPublisher(redis_client, cell_name="mata-garuda")
        published = await publisher.publish(skill_dict)
    """

    CONFIDENCE_THRESHOLD: float = 0.7

    def __init__(self, redis_client: Any, cell_name: str, maxlen: int = 1000) -> None:
        self._redis = redis_client
        self._cell_name = cell_name
        self._maxlen = maxlen

    async def publish(self, skill: dict) -> bool:
        """Publish skill to HGT stream if eligible.

        Returns True if published, False if filtered out or failed.
        """
        if not self._redis:
            return False

        conf = skill.get("confidence", 0)
        if conf < self.CONFIDENCE_THRESHOLD:
            return False
        if skill.get("scope") != "Project":
            return False
        if skill.get("type") == "scar":
            return False

        try:
            await self._redis.xadd(
                STREAM_SKILLS,
                {
                    "skill_id": skill.get("id", ""),
                    "cell_origin": self._cell_name,
                    "procedure": skill.get("procedure", ""),
                    "precondition": skill.get("precondition", ""),
                    "success_criterion": skill.get("success_criterion", ""),
                    "confidence": str(conf),
                    "type": skill.get("type", "skill"),
                    "scope": "Project",
                    "domain": skill.get("domain", "generic"),
                },
                maxlen=self._maxlen,
            )
            logger.info(
                f"[hgt] published '{skill.get('id')}' from '{self._cell_name}' "
                f"(conf={conf:.0%}, domain={skill.get('domain', 'generic')})"
            )
            return True
        except Exception as e:
            logger.warning(f"[hgt] publish failed (Redis down?): {e}")
            return False
