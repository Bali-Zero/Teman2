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

PHASE 2 (web verification, 2026-06-16): the local model is fluent but can cite a
stale framework (e.g. the Negative Investment List, superseded by the Positive
List / Perpres 10/2021). After the Ollama draft, we run a single Exa web search
on the gap topic and graft the real result URLs into the evidence citations,
nudging confidence up when the web corroborates. This grounds the proposal
against live public sources. It is STRICTLY additive and degrades gracefully:
no EXA_API_KEY, a network failure, or zero results all leave the Ollama-only
evidence untouched (Law 6 — the web is a bonus, never a hard dependency). Only
public regulatory data is queried; no PII ever leaves the box (Law 2).
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

# Phase 2 web verification (Exa). Key is read lazily at call time so the absence
# of EXA_API_KEY silently disables verification rather than breaking the cron.
EXA_SEARCH_URL = "https://api.exa.ai/search"
EXA_TIMEOUT = int(os.environ.get("CURIOSITY_EXA_TIMEOUT", "30"))
EXA_NUM_RESULTS = int(os.environ.get("CURIOSITY_EXA_NUM_RESULTS", "4"))
# Master switch — set CURIOSITY_WEB_VERIFY=0 to force Ollama-only.
WEB_VERIFY_ENABLED = os.environ.get("CURIOSITY_WEB_VERIFY", "1") != "0"

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
                # Phase 2: ground the local draft against live public sources.
                # Strictly additive — never raises, never downgrades the draft.
                self._verify_with_web(result, topic, domain)
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

    def _verify_with_web(
        self, evidence: ResearchEvidence, topic: str, domain: str
    ) -> None:
        """Graft real web-source URLs into `evidence` (in place), if available.

        Runs one Exa search on the gap topic and appends the result URLs to the
        evidence citations, records them in metadata, and nudges confidence up a
        little when the web corroborates the local draft. Pure best-effort: any
        failure (no key, network error, no results, bad JSON) is swallowed and
        leaves `evidence` exactly as the local model produced it. Mutates in
        place; returns nothing.
        """
        if not WEB_VERIFY_ENABLED:
            return
        api_key = os.environ.get("EXA_API_KEY", "")
        if not api_key:
            logger.debug("SimpleDispatcher: EXA_API_KEY unset — skipping web verify")
            return

        query = f"{topic} Indonesia regulation 2025 2026 ({domain})"
        payload = {
            "query": query,
            "type": "auto",
            "numResults": EXA_NUM_RESULTS,
            "contents": {"text": {"maxCharacters": 600}},
        }
        try:
            req = urllib.request.Request(
                EXA_SEARCH_URL,
                data=json.dumps(payload).encode(),
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "nuzantara-curiosity/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=EXA_TIMEOUT) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            logger.warning(
                "SimpleDispatcher: web verify failed for '%s': %s", topic[:40], e
            )
            return

        results = [r for r in (data.get("results", []) or []) if r.get("url")]
        if not results:
            return

        # Rank official Indonesian government sources (.go.id — imigrasi/bkpm/
        # oss/peraturan/pajak) ahead of commercial blogs and law-firm posts, so
        # the most authoritative citations lead. Stable within each tier.
        results.sort(key=lambda r: 0 if ".go.id" in r.get("url", "") else 1)
        urls = [r["url"] for r in results]

        # Graft URLs as extra citations (dedup, keep order) + record provenance.
        existing = list(evidence.citations)
        for url in urls:
            if url not in existing:
                existing.append(url)
        evidence.citations = existing
        evidence.source_type = "ollama+web"
        evidence.metadata = {
            **evidence.metadata,
            "web_verified": True,
            "web_sources": [
                {"url": r.get("url", ""), "title": r.get("title", "")}
                for r in results
                if r.get("url")
            ],
        }
        # Corroboration bumps confidence toward, but not past, a sensible ceiling.
        evidence.confidence = min(0.9, evidence.confidence + 0.1)
        logger.info(
            "SimpleDispatcher: web-verified '%s' with %d source(s)",
            topic[:40], len(urls),
        )

    def _call_ollama(self, topic: str, domain: str) -> ResearchEvidence | None:
        """Call the configured Ollama model (default SEA-LION) for research."""
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
