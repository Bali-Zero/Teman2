"""Tier 1 Simple Dispatcher — local Ollama research for specific regulatory gaps.

# Organo: graph-engine/curiosity/dispatchers → produce ResearchEvidence

Uses a local SEA-trained Ollama model to generate evidence for well-defined
regulatory gaps. Falls back to template-based evidence summary when Ollama is
unavailable. Graceful degradation: returns empty evidence list on any failure.

Model + timeout chosen from a live benchmark on the Pro (2026-06-16). The
previous default (qwen3.5:9b, 60s timeout) timed out on EVERY gap — the
regulatory-research + JSON task takes ~100-120s on the Pro (a loaded H24
workhorse), so the 60s cap meant the cron ran for 10 days producing only
template placeholders, never real research. Three locally-present models on
the real prompt:
  - qwen3.5:9b   104s, cites a stale framework (Negative Investment List,
                 superseded by the Positive List / Perpres 10/2021)
  - gemma3:27b   194s, hallucinated a non-existent "Law 6/2023" for PT PMA
  - SEA-LION-32B 121s, correct Indonesian terminology (BKPM, MoJ, UU 11/2020) —
                 AI Singapore's model is trained on Southeast-Asian context,
                 best accuracy for the Indonesian regulatory domain.
SEA-LION wins on accuracy at +17s vs qwen — irrelevant for a once-nightly cron.
Timeout 180s gives headroom over the measured 121s incl. cold-start variance.
Model/URL/timeout are env-overridable so the Pro and Mini can diverge without
a code change (the Mini only has <=9B models).
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any

from nuzantara_graph.curiosity.models import ResearchEvidence

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("CURIOSITY_OLLAMA_URL", "http://localhost:11434/api/chat")
# SEA-LION v4 32B (AI Singapore) — best Indonesian-regulatory accuracy in the
# 2026-06-16 Pro benchmark. Override per host via CURIOSITY_OLLAMA_MODEL.
OLLAMA_MODEL = os.environ.get(
    "CURIOSITY_OLLAMA_MODEL", "aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m"
)
# Live E2E on the Pro measured 103s and 170s on two real gaps — the second
# brushed a 180s cap, so 240s gives genuine cold-start headroom. A once-nightly
# cron can well afford it. Override via env.
OLLAMA_TIMEOUT = int(os.environ.get("CURIOSITY_OLLAMA_TIMEOUT", "240"))

RESEARCH_PROMPT = """You are a regulatory research assistant for Indonesian business services.

Domain: {domain}
Gap topic: {topic}

Research this specific gap and provide:
1. Key facts and current regulations (2025-2026)
2. Official references (law numbers, government decrees)
3. Practical requirements (fees, timelines, documents needed)

Be specific and factual. Include law numbers (PP, PMK, Perpres) where applicable.
Focus on Indonesia and Bali specifically.

Return your response as JSON:
{{
  "summary": "concise factual summary (200 words max)",
  "citations": ["citation 1", "citation 2"],
  "key_facts": ["fact 1", "fact 2", "fact 3"],
  "confidence": 0.0-1.0
}}
"""


class SimpleDispatcher:
    """Tier 1: Local Ollama research for specific regulatory gaps."""

    async def dispatch(
        self,
        topic: str,
        domain: str,
        follow_up_queries: list[str] | None = None,
    ) -> list[ResearchEvidence]:
        """Research a gap topic using Ollama.

        Args:
            topic: The gap topic to research.
            domain: Domain (immigration, tax, etc.).
            follow_up_queries: Optional specific queries from gap detector.

        Returns:
            List of ResearchEvidence (1 item for simple tier).
        """
        try:
            result = self._call_ollama(topic, domain)
            if result:
                return [result]
        except Exception as e:
            logger.warning("SimpleDispatcher: Ollama failed for '%s': %s", topic[:40], e)

        # Fallback: return minimal evidence indicating research needed
        return [
            ResearchEvidence(
                content=f"Gap identified: {topic} in {domain}. Requires external research.",
                source_type="template",
                confidence=0.1,
            )
        ]

    def _call_ollama(self, topic: str, domain: str) -> ResearchEvidence | None:
        """Call Ollama qwen3.5:9b for regulatory research."""
        prompt = RESEARCH_PROMPT.format(domain=domain, topic=topic)

        payload = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"think": False, "temperature": 0.3},
        }

        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read())

        content = data.get("message", {}).get("content", "").strip()
        if not content:
            return None

        # Parse JSON response
        parsed = self._parse_response(content)
        if not parsed:
            # Treat raw text as evidence
            return ResearchEvidence(
                content=content[:2000],
                source_type="ollama",
                confidence=0.4,
            )

        return ResearchEvidence(
            content=parsed.get("summary", content[:2000]),
            source_type="ollama",
            citations=parsed.get("citations", []),
            confidence=min(1.0, max(0.0, parsed.get("confidence", 0.5))),
            metadata={"key_facts": parsed.get("key_facts", [])},
        )

    def _parse_response(self, content: str) -> dict[str, Any] | None:
        """Try to parse JSON from Ollama response."""
        # Find JSON block
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass
        return None
