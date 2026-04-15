"""Vertical Feedback — child→parent skill improvement proposals via Redis Stream.

# Organo: cell-core L0 → produces cell:feedback events → consumed by parent cells
# If fails: child keeps improved skill locally, parent doesn't get update (no harm)

Merge policy: conditional overwrite (not fork).
If child.confidence > parent.confidence + IMPROVEMENT_THRESHOLD AND child.uses >= MIN_USES
→ propose improvement to parent.

Anti-loop: rejected proposals not re-proposed for COOLDOWN_DAYS.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from cell_core.genome import Genome

logger = logging.getLogger("cell_core.hgt.feedback")

STREAM_FEEDBACK = "cell:feedback"


class VerticalFeedback:
    """Manages child→parent skill improvement proposals.

    Usage::

        feedback = VerticalFeedback(redis_client, genome, cell_name="kontrak_parser")

        # Child proposes improvement
        await feedback.propose_improvement(improved_skill_dict)

        # Parent processes proposals
        count = await feedback.process_proposals()
    """

    IMPROVEMENT_THRESHOLD: float = 0.15
    MIN_USES: int = 3
    COOLDOWN_DAYS: int = 7

    def __init__(
        self,
        redis_client: Any,
        genome: Genome,
        cell_name: str,
    ) -> None:
        self._redis = redis_client
        self._genome = genome
        self._cell_name = cell_name
        # In-memory cooldown: {(from_cell, skill_id): rejection_timestamp}
        # Clears on restart — intentional (allows fresh attempts after deploy)
        self._cooldown: dict[tuple[str, str], float] = {}

    async def ensure_group(self) -> None:
        """Create consumer group for feedback stream. Idempotent."""
        if not self._redis:
            return
        try:
            await self._redis.xgroup_create(
                STREAM_FEEDBACK, f"feedback_{self._cell_name}",
                id="0", mkstream=True,
            )
        except Exception:
            pass

    async def propose_improvement(self, skill: dict) -> bool:
        """If we improved an inherited skill significantly, propose back to parent.

        Conditions (ALL must be true):
        1. skill has inherited_from (it was inherited)
        2. skill.uses >= MIN_USES (proven in practice)
        3. skill.confidence > parent.confidence + IMPROVEMENT_THRESHOLD
        4. Not in cooldown from recent rejection

        Returns True if proposal was published.
        """
        if not self._redis:
            return False

        inherited_from = skill.get("inherited_from")
        if not inherited_from:
            return False

        uses = skill.get("uses", 0)
        if uses < self.MIN_USES:
            return False

        # Check cooldown
        key = (self._cell_name, skill.get("id", ""))
        if key in self._cooldown:
            if time.time() - self._cooldown[key] < self.COOLDOWN_DAYS * 86400:
                return False

        # Find parent skill to compare confidence
        parent_skills = self._genome.search(inherited_from)
        if not parent_skills:
            # Try direct lookup by id
            conn = self._genome._get_conn()
            row = conn.execute(
                "SELECT confidence, cell_origin FROM genome WHERE id = ? AND valid_to IS NULL",
                (inherited_from,),
            ).fetchone()
            if not row:
                return False
            parent_conf = row["confidence"]
            parent_cell = row["cell_origin"]
        else:
            parent_conf = parent_skills[0].get("confidence", 0)
            parent_cell = parent_skills[0].get("cell_origin", "")

        child_conf = skill.get("confidence", 0)
        if child_conf <= parent_conf + self.IMPROVEMENT_THRESHOLD:
            return False

        try:
            await self._redis.xadd(
                STREAM_FEEDBACK,
                {
                    "skill_id": skill.get("id", ""),
                    "from_cell": self._cell_name,
                    "to_cell": parent_cell,
                    "original_inherited_from": inherited_from,
                    "new_confidence": str(child_conf),
                    "procedure_updated": skill.get("procedure", ""),
                    "uses": str(uses),
                },
                maxlen=500,
            )
            logger.info(
                f"[feedback] '{self._cell_name}' proposed improvement for "
                f"'{inherited_from}' (conf {parent_conf:.2f}→{child_conf:.2f})"
            )
            return True
        except Exception as e:
            logger.warning(f"[feedback] propose failed: {e}")
            return False

    async def process_proposals(self, count: int = 10) -> dict[str, int]:
        """Process improvement proposals from child cells.

        Merge policy: conditional overwrite.
        If proposal.confidence > own.confidence + IMPROVEMENT_THRESHOLD
        AND child.uses >= MIN_USES → update own procedure and confidence.

        Returns ``{"accepted": N, "rejected": M}``.
        """
        if not self._redis:
            return {"accepted": 0, "rejected": 0}

        result = {"accepted": 0, "rejected": 0}
        group = f"feedback_{self._cell_name}"

        try:
            entries = await self._redis.xreadgroup(
                groupname=group,
                consumername=self._cell_name,
                streams={STREAM_FEEDBACK: ">"},
                count=count,
                block=5000,
            )
        except Exception as e:
            logger.warning(f"[feedback] process failed: {e}")
            return result

        for _stream_name, messages in entries:
            for msg_id, data in messages:
                to_cell = data.get("to_cell", "")
                if to_cell != self._cell_name:
                    # Not for us — ACK and skip
                    await self._safe_ack(msg_id)
                    continue

                accepted = self._merge_proposal(data)
                if accepted:
                    result["accepted"] += 1
                else:
                    # Record cooldown for rejected proposals
                    from_cell = data.get("from_cell", "")
                    skill_id = data.get("skill_id", "")
                    self._cooldown[(from_cell, skill_id)] = time.time()
                    result["rejected"] += 1

                await self._safe_ack(msg_id)

        if result["accepted"] or result["rejected"]:
            logger.info(
                f"[feedback] '{self._cell_name}' processed: "
                f"{result['accepted']} accepted, {result['rejected']} rejected"
            )
        return result

    def _merge_proposal(self, data: dict) -> bool:
        """Apply conditional overwrite merge policy."""
        original_id = data.get("original_inherited_from", "")
        if not original_id:
            return False

        # Find our version of the skill
        conn = self._genome._get_conn()
        row = conn.execute(
            "SELECT confidence, procedure FROM genome WHERE id = ? AND valid_to IS NULL",
            (original_id,),
        ).fetchone()
        if not row:
            return False

        our_conf = row["confidence"]
        new_conf = float(data.get("new_confidence", "0"))
        child_uses = int(data.get("uses", "0"))

        # Merge conditions
        if new_conf <= our_conf + self.IMPROVEMENT_THRESHOLD:
            return False
        if child_uses < self.MIN_USES:
            return False

        # Apply: overwrite procedure and update confidence (with inherit decay)
        merged_conf = round(new_conf * 0.9, 4)  # decay from child
        new_procedure = data.get("procedure_updated", "")
        if not new_procedure:
            return False

        with self._genome._write_lock:
            conn = self._genome._get_conn()
            conn.execute(
                """UPDATE genome SET
                   procedure = ?,
                   confidence = ?,
                   last_used = datetime('now')
                   WHERE id = ? AND valid_to IS NULL""",
                (new_procedure, merged_conf, original_id),
            )
            conn.commit()

        logger.info(
            f"[feedback] merged improvement for '{original_id}' "
            f"(conf {our_conf:.2f}→{merged_conf:.2f} from '{data.get('from_cell')}')"
        )
        return True

    async def _safe_ack(self, msg_id: str) -> None:
        """ACK message, ignoring errors."""
        try:
            await self._redis.xack(
                STREAM_FEEDBACK, f"feedback_{self._cell_name}", msg_id
            )
        except Exception:
            pass
