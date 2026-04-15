"""HGT Consumer — subscribes to Redis Stream and integrates sibling skills.

# Organo: cell-core L0 → consumes cell:skills events → produces genome entries
# If fails: cell continues with local genome only (graceful degradation)
"""
from __future__ import annotations

import logging
from typing import Any

from cell_core.genome import Genome
from cell_core.hgt.publisher import STREAM_SKILLS

logger = logging.getLogger("cell_core.hgt.consumer")


class HGTConsumer:
    """Consumes skills from Redis Stream ``cell:skills`` with domain filtering.

    Each cell registers its own consumer group: ``hgt_{cell_name}``.
    Skills from the same cell are ignored (no self-consumption).
    Skills are integrated with confidence decay (default 0.9x).

    Usage::

        consumer = HGTConsumer(
            redis_client, genome, cell_name="kontrak_parser",
            interested_domains={"legal", "generic"},
        )
        await consumer.ensure_group()
        count = await consumer.consume_once()
    """

    INHERIT_DECAY: float = 0.9
    BLOCK_MS: int = 5000  # 5s block, not infinite

    def __init__(
        self,
        redis_client: Any,
        genome: Genome,
        cell_name: str,
        interested_domains: set[str],
    ) -> None:
        self._redis = redis_client
        self._genome = genome
        self._cell_name = cell_name
        self._domains = interested_domains
        self._group = f"hgt_{cell_name}"

    async def ensure_group(self) -> None:
        """Create consumer group if not exists. Idempotent."""
        if not self._redis:
            return
        try:
            await self._redis.xgroup_create(
                STREAM_SKILLS, self._group, id="0", mkstream=True
            )
        except Exception:
            pass  # group already exists

    async def consume_once(self, count: int = 10) -> int:
        """Read and process pending messages. Returns count of skills integrated.

        Non-blocking if Redis is unavailable.
        """
        if not self._redis:
            return 0

        try:
            entries = await self._redis.xreadgroup(
                groupname=self._group,
                consumername=self._cell_name,
                streams={STREAM_SKILLS: ">"},
                count=count,
                block=self.BLOCK_MS,
            )
        except Exception as e:
            logger.warning(f"[hgt] consume failed (Redis down?): {e}")
            return 0

        processed = 0
        for _stream_name, messages in entries:
            for msg_id, data in messages:
                if self._should_consume(data):
                    self._integrate(data)
                    processed += 1
                # Always XACK to prevent pending buildup
                try:
                    await self._redis.xack(STREAM_SKILLS, self._group, msg_id)
                except Exception:
                    pass

        if processed:
            logger.info(f"[hgt] '{self._cell_name}' consumed {processed} skills")
        return processed

    def _should_consume(self, data: dict) -> bool:
        """Filter: skip own skills and irrelevant domains."""
        origin = data.get("cell_origin", "")
        domain = data.get("domain", "generic")
        return (
            origin != self._cell_name
            and (domain in self._domains or domain == "generic")
        )

    def _integrate(self, data: dict) -> None:
        """Record inherited skill in local genome with decay."""
        inherited_conf = float(data.get("confidence", "0.5")) * self.INHERIT_DECAY
        self._genome.record_skill(
            cell=self._cell_name,
            skill_id=f"hgt_{data.get('skill_id', '')}",
            procedure=data.get("procedure", ""),
            precondition=data.get("precondition", ""),
            success_criterion=data.get("success_criterion", ""),
            confidence=round(inherited_conf, 4),
            scope="Project",
            inherited_from=data.get("skill_id", ""),
            entry_type=data.get("type", "skill"),
            domain=data.get("domain", "generic"),
        )
