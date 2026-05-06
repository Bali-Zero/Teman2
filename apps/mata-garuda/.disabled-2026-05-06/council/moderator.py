"""
Consiglio v1 — Moderator LLM.

The moderator is architecturally distinct from the deliberating agents.
Uses Ollama gemma4:26b (local, diverse from Claude/Gemini/DeepSeek).

Produces structured JSON synthesis with action items and escalation decision.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from typing import Optional

from mata_garuda.council.models import (
    AgentVote,
    ConsensusResult,
    Dissent,
)
from mata_garuda.council.prompts import COUNCIL_MODERATOR_PROMPT

logger = logging.getLogger("mata_garuda.council.moderator")


class ModeratorLLM:
    """Ollama-based moderator for council synthesis."""

    def __init__(
        self,
        model: str = "gemma4:26b",
        timeout: int = 120,
    ):
        self._model = model
        self._timeout = timeout

    async def synthesize(
        self,
        topic_title: str,
        topic_description: str,
        votes: list[AgentVote],
        consensus: ConsensusResult,
        dissents: list[Dissent],
    ) -> dict:
        """Synthesize agent votes into a moderator decision.

        Returns dict with: synthesis, action_items, confidence,
        requires_zero_approval, escalation_reason.
        """
        # Format agent responses
        agent_responses = ""
        for v in votes:
            agent_responses += f"\n--- {v.agent_name} ({v.runtime}) ---\n"
            agent_responses += f"Position: {v.position}\n"
            agent_responses += f"Confidence: {v.confidence}\n"
            agent_responses += f"Arguments: {', '.join(v.key_arguments)}\n"
            agent_responses += f"Risks: {', '.join(v.risks_identified)}\n"

        # Format dissent section
        dissent_section = ""
        if dissents:
            dissent_section = "DISSENTING POSITIONS:\n"
            for d in dissents:
                dissent_section += f"- {d.agent_name} (divergence {d.divergence_score:.2f}): {d.position}\n"

        prompt = COUNCIL_MODERATOR_PROMPT.format(
            agent_count=len(votes),
            topic_title=topic_title,
            topic_description=topic_description,
            agent_responses=agent_responses,
            consensus_score=f"{consensus.score:.2f}",
            consensus_method=consensus.method,
            groupthink_status="YES" if consensus.groupthink_detected else "No",
            dissent_section=dissent_section,
        )

        try:
            raw = await asyncio.to_thread(self._invoke_ollama, prompt)
            parsed = self._parse_synthesis(raw)
            return parsed
        except Exception as e:
            logger.error(f"[moderator] synthesis failed: {e}")
            return self._fallback_synthesis(votes, consensus, dissents)

    def _invoke_ollama(self, prompt: str) -> str:
        """Run ollama subprocess."""
        result = subprocess.run(
            ["ollama", "run", self._model, prompt],
            capture_output=True, text=True,
            timeout=self._timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ollama moderator failed: {result.stderr[:200]}")
        return result.stdout.strip()

    def _parse_synthesis(self, raw: str) -> dict:
        """Parse structured JSON from moderator output."""
        # Try direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown fences
        match = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding first JSON object
        match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Return raw text as synthesis
        return {
            "synthesis": raw[:500],
            "action_items": [],
            "confidence": 5,
            "requires_zero_approval": True,
            "escalation_reason": "moderator output could not be parsed as JSON",
        }

    def _fallback_synthesis(
        self,
        votes: list[AgentVote],
        consensus: ConsensusResult,
        dissents: list[Dissent],
    ) -> dict:
        """Deterministic fallback when Ollama is unavailable."""
        positions = [v.position for v in votes if v.position]
        summary = "; ".join(positions[:3]) if positions else "No positions available"

        return {
            "synthesis": f"[FALLBACK] Agents responded: {summary}",
            "action_items": ["Review agent positions manually"],
            "confidence": 3,
            "requires_zero_approval": True,
            "escalation_reason": "moderator LLM unavailable, fallback synthesis used",
        }
