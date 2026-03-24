"""
Query Expander Service - Multi-Query LLM Expansion

Generates 2-3 alternative search queries using Gemini Flash to improve
recall on complex/comparative queries. Uses RRF fusion downstream.

Two expansion modes:
1. expand() — single expanded query (original + translations), backward compatible
2. expand_multi() — list of 2-3 alternative queries for RRF fusion (NEW)

Architecture:
- Gemini Flash (fast, cheap ~$0.0001/call) with 3s timeout
- Redis cache (1h TTL) to avoid repeat LLM calls
- Graceful fallback to KeywordTranslator if Gemini unavailable
- Feature flag: ENABLE_QUERY_EXPANSION

Author: RIRI (original), refactored 2026-03-24
"""

import asyncio
import json
import logging
from typing import Any

from backend.app.core.config import settings
from backend.core.cache import cached

logger = logging.getLogger(__name__)

# Prompt for multi-query expansion
_MULTI_QUERY_PROMPT = """You are a search query optimizer for an Indonesian business services platform (visa, company setup, tax, KBLI codes).

Given this user query, generate 2-3 alternative search queries that:
1. Cover different aspects or phrasings of the same intent
2. Include Indonesian legal/business terms (KITAS, PT PMA, NIB, NPWP, etc.)
3. Translate key concepts to Bahasa Indonesia (the document language)
4. Are concise and search-optimized (no full sentences)

User query: "{query}"

Return ONLY a JSON array of 2-3 strings. No explanation, no markdown:
["alternative query 1 in English/Indonesian mix", "alternative query 2", "alternative query 3"]"""

# Prompt for single translation expansion (backward compat)
_TRANSLATION_PROMPT = """Analyze this query and provide translations for search optimization.

Query: "{query}"

Respond in this EXACT JSON format only (no markdown, no code blocks):
{{"detected_lang": "xx", "english": "translation here", "indonesian": "translation here"}}

Rules:
- If query is already in English, copy it to "english" field
- If query is already in Indonesian, copy it to "indonesian" field
- Keep translations concise and search-optimized
- Preserve key terms and codes (like E25B, KITAS, etc.)"""


class QueryExpander:
    """
    Multi-query LLM expansion service.

    Expands user queries into multiple alternative search queries
    using Gemini Flash, with graceful fallback to KeywordTranslator.
    """

    def __init__(self) -> None:
        self._gemini: Any = None

    async def _get_gemini(self) -> Any:
        """Lazy init Gemini client."""
        if self._gemini is None:
            from backend.services.llm_clients.gemini_service import GeminiService

            self._gemini = GeminiService()
        return self._gemini

    async def _call_gemini(self, prompt: str, timeout_s: float = 3.0) -> str | None:
        """Call Gemini with timeout. Returns None on any failure."""
        try:
            client = await self._get_gemini()
            result = await asyncio.wait_for(
                client.generate_response(prompt=prompt),
                timeout=timeout_s,
            )
            return result if result and result.strip() else None
        except asyncio.TimeoutError:
            logger.warning("Gemini query expansion timed out (%.1fs)", timeout_s)
            return None
        except Exception as e:
            logger.warning("Gemini query expansion failed: %s", e)
            return None

    @staticmethod
    def _clean_json(response: str) -> str:
        """Extract JSON from potentially markdown-wrapped response."""
        clean = response.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean = "\n".join(lines)
        # Find JSON array or object
        for start_char, end_char in [("[", "]"), ("{", "}")]:
            start = clean.find(start_char)
            end = clean.rfind(end_char)
            if start != -1 and end > start:
                return clean[start : end + 1]
        return clean.strip()

    @cached(ttl=3600, prefix="qexp_multi")
    async def expand_multi(self, query: str) -> list[str]:
        """
        Generate 2-3 alternative search queries using Gemini Flash.

        Returns a list of queries including the original.
        Falls back to keyword-translated original on any failure.

        Args:
            query: Original user query (any language)

        Returns:
            List of 2-4 query strings (always includes original first)
        """
        # Always start with keyword-translated original
        from backend.services.search.keyword_translator import get_keyword_translator

        translator = get_keyword_translator()
        base_query = translator.translate(query)
        result_queries = [base_query]

        # Skip LLM expansion for short/simple queries
        word_count = len(query.split())
        if word_count <= 4:
            logger.debug("Query too short for LLM expansion (%d words): %s", word_count, query[:50])
            return result_queries

        # Call Gemini for multi-query expansion
        prompt = _MULTI_QUERY_PROMPT.format(query=query)
        response = await self._call_gemini(prompt, timeout_s=3.0)

        if response is None:
            logger.debug("Gemini unavailable, using keyword-only expansion")
            return result_queries

        # Parse JSON array response
        try:
            cleaned = self._clean_json(response)
            alternatives = json.loads(cleaned)
            if isinstance(alternatives, list):
                for alt in alternatives[:3]:
                    alt_str = str(alt).strip()
                    if alt_str and alt_str.lower() != query.lower():
                        result_queries.append(alt_str)
                logger.info(
                    "Multi-query expansion: '%s' → %d queries",
                    query[:40],
                    len(result_queries),
                )
            else:
                logger.warning("Gemini returned non-array: %s", type(alternatives).__name__)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse expansion JSON: %s | response: %s", e, response[:100])

        return result_queries

    @cached(ttl=3600, prefix="query_expand")
    async def expand(self, query: str) -> str:
        """
        Expand query to multiple languages (backward compatible).

        Returns a single expanded string: "{original} {english} {indonesian}".
        Falls back to keyword-translated query on any error.

        Args:
            query: Original user query in any language

        Returns:
            Expanded query string
        """
        # Keyword translation first (always works)
        from backend.services.search.keyword_translator import get_keyword_translator

        translator = get_keyword_translator()
        base = translator.translate(query)

        # Skip LLM for very short queries
        if not query or len(query.strip()) < 3:
            return base

        # Try Gemini for translation
        prompt = _TRANSLATION_PROMPT.format(query=query)
        response = await self._call_gemini(prompt, timeout_s=3.0)

        if response is None:
            return base

        try:
            cleaned = self._clean_json(response)
            result = json.loads(cleaned)
            english = result.get("english", "").strip()
            indonesian = result.get("indonesian", "").strip()

            parts = [base]
            if english and english.lower() != query.lower():
                parts.append(english)
            if indonesian and indonesian.lower() not in (query.lower(), english.lower()):
                parts.append(indonesian)

            expanded = " ".join(parts)
            logger.info("Query translated: '%s' → %d chars", query[:30], len(expanded))
            return expanded
        except json.JSONDecodeError:
            return base

    async def expand_with_details(self, query: str) -> dict[str, Any]:
        """Expand query and return detailed breakdown."""
        multi = await self.expand_multi(query)
        single = await self.expand(query)
        return {
            "original": query,
            "expanded_single": single,
            "expanded_multi": multi,
            "num_alternatives": len(multi),
        }


# Module singleton
_expander: QueryExpander | None = None


def get_query_expander() -> QueryExpander:
    """Get or create singleton QueryExpander."""
    global _expander
    if _expander is None:
        _expander = QueryExpander()
    return _expander
