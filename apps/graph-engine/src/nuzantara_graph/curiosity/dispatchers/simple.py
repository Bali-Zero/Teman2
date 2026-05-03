"""Tier 1 Simple Dispatcher — local Ollama research for specific regulatory gaps.

# Organo: graph-engine/curiosity/dispatchers → produce ResearchEvidence

Uses Ollama qwen3.5:9b to generate evidence for well-defined regulatory gaps.
Falls back to template-based evidence summary when Ollama is unavailable.
Graceful degradation: returns empty evidence list on any failure.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

from nuzantara_graph.curiosity.models import ResearchEvidence

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_TIMEOUT = 60

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
