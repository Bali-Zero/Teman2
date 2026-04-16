"""
Consiglio v1 — Council Orchestrator.

The main entry point for multi-LLM deliberation sessions.

Flow:
1. Validate agents (min 2)
2. Parallel dispatch via asyncio.gather
3. Filter failed votes
4. Score consensus (LLM-as-judge or Jaccard)
5. Detect groupthink → devil's advocate if triggered
6. Identify dissents
7. Moderator synthesis
8. Determine escalation
9. Persist to SQLite
10. Return CouncilDecision

Pattern: cell/actor.py asyncio.to_thread() for sync→async wrapping.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from statistics import mean
from typing import Optional

from mata_garuda.council.agents import (
    CouncilAgent,
    OllamaAdapter,
    _format_agent_prompt,
    _parse_vote_json,
    get_default_agents,
)
from mata_garuda.council.consensus import score_consensus
from mata_garuda.council.models import (
    AgentVote,
    ConsensusResult,
    CouncilDecision,
    Dissent,
    Topic,
)
from mata_garuda.council.moderator import ModeratorLLM
from mata_garuda.council.prompts import DEVILS_ADVOCATE_PROMPT
from mata_garuda.council.store import CouncilStore

logger = logging.getLogger("mata_garuda.council.orchestrator")

# Total council run budget
TOTAL_TIMEOUT_S = 600  # 10 minutes max


class CouncilOrchestrator:
    """Multi-LLM deliberation orchestrator with groupthink detection."""

    def __init__(
        self,
        agents: Optional[list[CouncilAgent]] = None,
        moderator: Optional[ModeratorLLM] = None,
        store: Optional[CouncilStore] = None,
        min_agents: int = 2,
        total_timeout: int = TOTAL_TIMEOUT_S,
    ):
        self.agents = agents or get_default_agents()
        self.moderator = moderator or ModeratorLLM()
        self.store = store or CouncilStore()
        self.min_agents = min_agents
        self.total_timeout = total_timeout

    async def deliberate(self, topic: Topic) -> CouncilDecision:
        """Run a full council deliberation on a topic."""
        decision_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()

        try:
            return await asyncio.wait_for(
                self._deliberate_inner(topic, decision_id, now),
                timeout=self.total_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(f"[council] total timeout ({self.total_timeout}s) exceeded")
            return CouncilDecision(
                id=decision_id,
                topic=topic,
                status="abstain",
                synthesis="Council timed out",
                escalation_reason=f"total timeout {self.total_timeout}s exceeded",
                requires_zero_approval=True,
                decided_at=now,
            )

    async def _deliberate_inner(
        self, topic: Topic, decision_id: str, now: str,
    ) -> CouncilDecision:
        """Inner deliberation logic (without total timeout wrapper)."""

        # 1. Validate agents
        if len(self.agents) < self.min_agents:
            return CouncilDecision(
                id=decision_id, topic=topic, status="abstain",
                synthesis=f"Insufficient agents: {len(self.agents)} < {self.min_agents}",
                requires_zero_approval=True,
                escalation_reason="insufficient agents",
                decided_at=now,
            )

        # 2. Parallel dispatch
        logger.info(f"[council] dispatching to {len(self.agents)} agents")
        raw_results = await asyncio.gather(
            *[agent.deliberate(topic) for agent in self.agents],
            return_exceptions=True,
        )

        # 3. Filter failed votes
        votes: list[AgentVote] = []
        for i, result in enumerate(raw_results):
            if isinstance(result, Exception):
                agent_name = self.agents[i].name if i < len(self.agents) else f"agent_{i}"
                logger.warning(f"[council] {agent_name} raised: {result}")
                votes.append(AgentVote(
                    agent_name=agent_name, success=False,
                    error=str(result)[:200],
                ))
            else:
                votes.append(result)

        successful = [v for v in votes if v.success]
        logger.info(f"[council] {len(successful)}/{len(votes)} agents responded successfully")

        if len(successful) < self.min_agents:
            return CouncilDecision(
                id=decision_id, topic=topic, votes=votes,
                status="abstain",
                synthesis=f"Only {len(successful)} agents responded (min: {self.min_agents})",
                requires_zero_approval=True,
                escalation_reason=f"insufficient responses: {len(successful)}/{self.min_agents}",
                decided_at=now,
            )

        # 4. Score consensus
        consensus = await score_consensus(successful)
        logger.info(
            f"[council] consensus={consensus.score:.2f} method={consensus.method} "
            f"groupthink={consensus.groupthink_detected}"
        )

        # 5. Groupthink → devil's advocate
        if consensus.groupthink_detected:
            logger.warning(f"[council] GROUPTHINK detected: {consensus.groupthink_reason}")
            devils_vote = await self._devils_advocate(topic, successful, consensus)
            if devils_vote and devils_vote.success:
                votes.append(devils_vote)
                # Re-score with devil's advocate included
                all_successful = [v for v in votes if v.success]
                consensus = await score_consensus(all_successful)
                logger.info(f"[council] post-advocate consensus={consensus.score:.2f}")

        # 6. Identify dissents
        dissents = self._identify_dissents(successful, consensus)

        # 7. Moderator synthesis
        mod_result = await self.moderator.synthesize(
            topic_title=topic.title,
            topic_description=topic.description,
            votes=successful,
            consensus=consensus,
            dissents=dissents,
        )

        synthesis = mod_result.get("synthesis", "")
        action_items = mod_result.get("action_items", [])
        mod_confidence = mod_result.get("confidence", 5)

        # 8. Determine escalation
        requires_zero, esc_reason = self._check_escalation(
            topic, consensus, mod_confidence, mod_result,
        )

        # 9. Build decision
        decision = CouncilDecision(
            id=decision_id,
            topic=topic,
            votes=votes,
            consensus=consensus,
            dissents=dissents,
            synthesis=synthesis,
            action_items=action_items,
            requires_zero_approval=requires_zero,
            escalation_reason=esc_reason,
            status="pending" if requires_zero else "auto_approved",
            decided_at=now,
        )

        # 10. Persist
        try:
            self.store.save_decision(decision)
        except Exception as e:
            logger.error(f"[council] store failed: {e}")

        return decision

    async def _devils_advocate(
        self,
        topic: Topic,
        votes: list[AgentVote],
        consensus: ConsensusResult,
    ) -> Optional[AgentVote]:
        """Invoke devil's advocate using the fastest-responding agent."""
        if not votes:
            return None

        # Find majority position
        majority = max(votes, key=lambda v: v.confidence)

        prompt = DEVILS_ADVOCATE_PROMPT.format(
            topic_title=topic.title,
            topic_description=topic.description,
            majority_position=majority.position,
            avg_time=consensus.avg_response_time,
            consensus_score=consensus.score,
        )

        # Use Ollama for devil's advocate (distinct from original agents)
        adapter = OllamaAdapter(model="gemma4:26b", timeout=60)
        try:
            vote = await adapter.deliberate(
                Topic(
                    id=topic.id,
                    title=f"[DEVIL'S ADVOCATE] {topic.title}",
                    description=prompt,
                    category=topic.category,
                )
            )
            vote.agent_name = "devils_advocate"
            vote.runtime = "ollama_local"
            return vote
        except Exception as e:
            logger.warning(f"[council] devil's advocate failed: {e}")
            return None

    def _identify_dissents(
        self,
        votes: list[AgentVote],
        consensus: ConsensusResult,
    ) -> list[Dissent]:
        """Identify minority positions diverging from the majority."""
        if len(votes) < 2 or not consensus.pairwise_scores:
            return []

        dissents: list[Dissent] = []

        for vote in votes:
            # Calculate average pairwise score for this agent
            agent_scores = []
            for key, score in consensus.pairwise_scores.items():
                if vote.agent_name in key:
                    agent_scores.append(score)

            if not agent_scores:
                continue

            avg_agreement = mean(agent_scores)
            # Dissent threshold: agent agrees less than 0.50 with others
            if avg_agreement < 0.50:
                dissents.append(Dissent(
                    agent_name=vote.agent_name,
                    position=vote.position,
                    divergence_score=round(1.0 - avg_agreement, 3),
                ))

        return dissents

    def _check_escalation(
        self,
        topic: Topic,
        consensus: ConsensusResult,
        mod_confidence: int,
        mod_result: dict,
    ) -> tuple[bool, str]:
        """Determine if decision requires Zero approval."""
        reasons: list[str] = []

        # Low consensus → fundamental disagreement
        if consensus.score < 0.50:
            reasons.append(f"consensus={consensus.score:.2f} < 0.50")

        # Low moderator confidence
        if mod_confidence < 5:
            reasons.append(f"moderator confidence={mod_confidence}/10 < 5")

        # Structural/architecture topics always escalate
        if topic.category in ("architecture", "escalation"):
            reasons.append(f"topic category={topic.category}")

        # Groupthink detected (still present after devil's advocate)
        if consensus.groupthink_detected:
            reasons.append("groupthink detected")

        # Moderator explicitly requested escalation
        if mod_result.get("requires_zero_approval"):
            mod_reason = mod_result.get("escalation_reason", "")
            if mod_reason:
                reasons.append(f"moderator: {mod_reason}")

        if reasons:
            return True, "; ".join(reasons)

        return False, ""
