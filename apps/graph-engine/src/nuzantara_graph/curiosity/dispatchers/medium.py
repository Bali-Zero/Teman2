"""Tier 2 Medium Dispatcher — HyDE-style expansion + web search for cross-domain gaps.

# Organo: graph-engine/curiosity/dispatchers → produce ResearchEvidence

Generates hypothetical documents via Ollama, then uses them as expanded
search queries. Useful for cross-domain gaps where simple keyword search
is insufficient.

Graceful degradation: falls back to SimpleDispatcher on any failure.
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

HYDE_PROMPT = """You are a knowledge base about Indonesian business services in Bali.
Given the question below, write a short paragraph (3-5 sentences) that would be
a perfect answer. Focus on specific facts, regulations, requirements, and numbers.
Be concrete and authoritative. Do NOT ask clarifying questions.

Question: "{query}"

Answer:"""

SYNTHESIS_PROMPT = """You are a regulatory research analyst for Indonesian business services.

Domain: {domain}
Topic: {topic}

Below are {count} research fragments gathered about this topic:

{fragments}

Synthesize these fragments into a comprehensive evidence summary:
1. Identify consistent facts across fragments
2. Note any contradictions or uncertainties
3. List official references and citations

Return JSON:
{{
  "summary": "synthesized factual summary (300 words max)",
  "citations": ["citation 1", "citation 2"],
  "confidence": 0.0-1.0,
  "contradictions": ["any contradictions found"]
}}
"""


class MediumDispatcher:
    """Tier 2: HyDE expansion + multi-query synthesis."""

    async def dispatch(
        self,
        topic: str,
        domain: str,
        follow_up_queries: list[str] | None = None,
    ) -> list[ResearchEvidence]:
        """Research a gap topic using HyDE-style expansion.

        Args:
            topic: The gap topic to research.
            domain: Domain (immigration, tax, etc.).
            follow_up_queries: Specific queries from gap detector.

        Returns:
            List of ResearchEvidence (multiple fragments + synthesis).
        """
        queries = follow_up_queries or [topic]
        fragments: list[ResearchEvidence] = []

        # Step 1: Generate hypothetical docs (HyDE expansion)
        for query in queries[:3]:  # Max 3 queries per dispatch
            try:
                hyde_doc = self._generate_hyde(query)
                if hyde_doc:
                    fragments.append(hyde_doc)
            except Exception as e:
                logger.debug("MediumDispatcher: HyDE failed for '%s': %s", query[:30], e)

        if not fragments:
            logger.warning("MediumDispatcher: no HyDE fragments for '%s'", topic[:40])
            return [
                ResearchEvidence(
                    content=f"HyDE expansion failed for: {topic}",
                    source_type="hyde_fallback",
                    confidence=0.1,
                )
            ]

        # Step 2: Synthesize fragments
        try:
            synthesis = self._synthesize(topic, domain, fragments)
            if synthesis:
                fragments.append(synthesis)
        except Exception as e:
            logger.debug("MediumDispatcher: synthesis failed: %s", e)

        return fragments

    def _generate_hyde(self, query: str) -> ResearchEvidence | None:
        """Generate a hypothetical document for query expansion."""
        prompt = HYDE_PROMPT.format(query=query)

        payload = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"think": False, "temperature": 0.7},
        }

        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read())

        content = data.get("message", {}).get("content", "").strip()
        if not content or len(content) < 30:
            return None

        return ResearchEvidence(
            content=content[:2000],
            source_type="hyde",
            confidence=0.5,
            metadata={"query": query},
        )

    def _synthesize(
        self,
        topic: str,
        domain: str,
        fragments: list[ResearchEvidence],
    ) -> ResearchEvidence | None:
        """Synthesize multiple fragments into a single evidence summary."""
        fragment_texts = "\n\n---\n\n".join(
            f"Fragment {i+1} ({f.source_type}):\n{f.content}"
            for i, f in enumerate(fragments)
        )

        prompt = SYNTHESIS_PROMPT.format(
            domain=domain,
            topic=topic,
            count=len(fragments),
            fragments=fragment_texts,
        )

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

        # Try parsing JSON
        parsed = self._parse_json(content)
        if parsed:
            return ResearchEvidence(
                content=parsed.get("summary", content[:2000]),
                source_type="hyde_synthesis",
                citations=parsed.get("citations", []),
                confidence=min(1.0, max(0.0, parsed.get("confidence", 0.6))),
                metadata={
                    "contradictions": parsed.get("contradictions", []),
                    "fragment_count": len(fragments),
                },
            )

        return ResearchEvidence(
            content=content[:2000],
            source_type="hyde_synthesis",
            confidence=0.4,
            metadata={"fragment_count": len(fragments)},
        )

    def _parse_json(self, content: str) -> dict[str, Any] | None:
        """Try to parse JSON from response."""
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass
        return None
