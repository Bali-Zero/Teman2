"""
Query Expansion Service for Nuzantara RAG System

Improves retrieval recall by generating query variants before retrieval.
Uses multiple expansion strategies including:
- Synonym expansion (Indonesian ↔ English business terms)
- LLM-based query rephrasing (lightweight)
- Filter relaxation

Author: Nuzantara Team
Date: 2026-02-16
"""

import hashlib
import json
import logging
import re
import time
from typing import Any

from backend.core.cache import CacheService, get_cache_service
from backend.llm.genai_client import GENAI_AVAILABLE, get_genai_client

logger = logging.getLogger(__name__)

# Indonesian business terms dictionary for synonym expansion
INDONESIAN_BUSINESS_TERMS: dict[str, list[str]] = {
    # Company types
    "pt pma": ["foreign investment company", "penanaman modal asing", "foreign owned company"],
    "penanaman modal asing": ["foreign investment company", "pt pma"],
    "pt": ["perseroan terbatas", "limited liability company"],
    "perseroan terbatas": ["limited liability company", "pt"],
    "cv": ["commanditaire vennootschap", "partnership"],
    "commanditaire vennootschap": ["cv", "partnership"],
    "firma": ["partnership", "firm"],
    # Permits and licenses
    "kitas": ["residence permit", "kartu izin tinggal terbatas", "stay permit"],
    "kartu izin tinggal terbatas": ["residence permit", "kitas"],
    "kitap": ["permanent residence permit", "kartu izin tinggal tetap"],
    "kartu izin tinggal tetap": ["permanent residence permit", "kitap"],
    "nib": ["business identification number", "nomor induk berusaha"],
    "nomor induk berusaha": ["business identification number", "nib"],
    "oss": ["online single submission", "sistem oss"],
    "sistem oss": ["online single submission", "oss"],
    "siup": ["business license", "surat izin usaha perdagangan"],
    "surat izin usaha perdagangan": ["business license", "siup"],
    "tdp": ["company registration", "tanda daftar perusahaan"],
    "tanda daftar perusahaan": ["company registration", "tdp"],
    "npwp": ["tax identification number", "nomor pokok wajib pajak"],
    "nomor pokok wajib pajak": ["tax identification number", "npwp"],
    "imb": ["building permit", "izin mendirikan bangunan"],
    "izin mendirikan bangunan": ["building permit", "imb"],
    "slf": ["certificate of building worthiness", "sertifikat laik fungsi"],
    "sertifikat laik fungsi": ["certificate of building worthiness", "slf"],
    # Visas
    "visa kunjungan": ["visit visa", "tourist visa"],
    "visit visa": ["visa kunjungan", "tourist visa"],
    "visa tinggal terbatas": ["limited stay visa", "kitas visa"],
    "limited stay visa": ["visa tinggal terbatas", "kitas visa"],
    "visa on arrival": ["voa", "visa on arrival indonesia"],
    "voa": ["visa on arrival", "visa on arrival indonesia"],
    # Land and property
    "hak milik": ["freehold", "ownership right"],
    "freehold": ["hak milik", "ownership right"],
    "hak guna bangunan": ["hgb", "building use right"],
    "hgb": ["hak guna bangunan", "building use right"],
    "hak pakai": ["right of use", "usage right"],
    "hak sewa": ["leasehold", "lease right"],
    "leasehold": ["hak sewa", "lease right"],
    # Investment
    "modal": ["capital", "investment", "fund"],
    "capital": ["modal", "investment", "fund"],
    "penanaman modal": ["investment", "capital investment"],
    "investment": ["penanaman modal", "modal"],
    "saham": ["shares", "stock", "equity"],
    "shares": ["saham", "stock", "equity"],
    "direksi": ["board of directors", "directors"],
    "board of directors": ["direksi", "directors"],
    "komisaris": ["commissioners", "board of commissioners"],
    "board of commissioners": ["komisaris", "commissioners"],
    # Common business terms
    "pajak": ["tax", "taxation"],
    "tax": ["pajak", "taxation"],
    "perpajakan": ["taxation", "tax system"],
    "taxation": ["perpajakan", "pajak"],
    "karyawan": ["employee", "staff", "worker"],
    "employee": ["karyawan", "staff", "worker"],
    "tenaga kerja": ["workforce", "labor", "manpower"],
    "workforce": ["tenaga kerja", "labor"],
    "bpjs": ["social security", "health insurance", "ketenagakerjaan"],
    "social security": ["bpjs", "jamsostek"],
    "laporan keuangan": ["financial report", "financial statement"],
    "financial report": ["laporan keuangan", "financial statement"],
    "audit": ["auditing", "financial audit"],
    "pembukuan": ["bookkeeping", "accounting records"],
    "bookkeeping": ["pembukuan", "accounting records"],
}

# Filter keywords that might limit results
FILTER_KEYWORDS: list[str] = [
    "only",
    "just",
    "specifically",
    "exclusively",
    "must be",
    "has to be",
    "hanya",
    "hanya",
    "khusus",
    "eksklusif",
    "harus",
    "wajib",
]


class QueryExpander:
    """
    Query Expansion Service for RAG retrieval improvement.

    Generates multiple query variants to improve recall by:
    1. Synonym expansion using Indonesian business terms dictionary
    2. LLM-based query rephrasing (fast, lightweight)
    3. Filter removal/relaxation

    Attributes:
        cache_service: CacheService instance for caching expansions
        max_variants: Maximum number of variants to generate
        llm_timeout_ms: Timeout for LLM calls in milliseconds

    Example:
        >>> expander = QueryExpander()
        >>> variants = await expander.expand("How to apply for KITAS?", num_variants=3)
        >>> print(variants)
        ['How to apply for KITAS?', 'How to apply for residence permit?',
         'Cara mengajukan KITAS?']
    """

    # Prompt for LLM-based query rephrasing
    REPHRASE_PROMPT = """Generate {num_variants} alternative phrasings of this query for semantic search.
Keep the same meaning but use different words or sentence structure.

Query: "{query}"

Requirements:
- Each variant should be concise (max 20 words)
- Preserve key terms (KITAS, NIB, PT PMA, etc.)
- Make them search-friendly
- Return ONLY a JSON array of strings, no markdown, no explanation

Example output: ["variant 1", "variant 2"]"""

    def __init__(
        self,
        cache_service: CacheService | None = None,
        max_variants: int = 5,
        llm_timeout_ms: int = 100,
    ) -> None:
        """
        Initialize QueryExpander.

        Args:
            cache_service: Optional CacheService for caching expansions
            max_variants: Maximum number of variants to generate per query
            llm_timeout_ms: Timeout for LLM calls in milliseconds
        """
        self.cache_service = cache_service or get_cache_service()
        self.max_variants = max_variants
        self.llm_timeout_ms = llm_timeout_ms
        self._genai_client = None

        # Compile synonym patterns for faster matching
        self._synonym_patterns: dict[re.Pattern, list[str]] = {}
        for term, synonyms in INDONESIAN_BUSINESS_TERMS.items():
            # Create word boundary pattern for whole word matching
            pattern = re.compile(r"\b" + re.escape(term.lower()) + r"\b", re.IGNORECASE)
            self._synonym_patterns[pattern] = synonyms

        logger.info(f"✅ QueryExpander initialized (max_variants={max_variants})")

    def _get_genai_client(self) -> Any | None:
        """Lazy load GenAI client."""
        if self._genai_client is None and GENAI_AVAILABLE:
            try:
                client = get_genai_client()
                if client.is_available:
                    self._genai_client = client
            except Exception as e:
                logger.warning(f"Failed to initialize GenAI client: {e}")
        return self._genai_client

    def _generate_cache_key(self, query: str, method: str) -> str:
        """Generate cache key for query expansion."""
        key_data = f"{method}:{query.lower().strip()}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
        return f"zantara:query_expand:{method}:{key_hash}"

    async def expand(self, query: str, num_variants: int = 3) -> list[str]:
        """
        Expand query into multiple variants using all strategies.

        Combines synonym expansion, LLM rephrasing, and filter relaxation
        to generate diverse query variants for improved recall.

        Args:
            query: Original user query
            num_variants: Number of variants to generate (default: 3)

        Returns:
            List of query variants including the original query

        Example:
            >>> variants = await expander.expand("How to get KITAS?")
            >>> print(variants)
            ['How to get KITAS?', 'How to get residence permit?', ...]
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to expand()")
            return [query]

        start_time = time.time()

        try:
            query_clean = query.strip()

            # Strategy 1: Synonym expansion
            variants: set[str] = set(self.generate_synonyms(query_clean))

            # Strategy 2: Translation variants
            translation_variants = await self.translate_variants(query_clean)
            variants.update(translation_variants)

            # Strategy 3: LLM-based rephrasing (if we need more variants)
            if len(variants) < num_variants:
                llm_variants = await self._llm_rephrase(query_clean, num_variants=num_variants)
                variants.update(llm_variants)

            # Strategy 4: Filter relaxation
            relaxed = self._relax_filters(query_clean)
            if relaxed != query_clean:
                variants.add(relaxed)

            # Convert to list, ensuring original query is FIRST, then limit to max_variants
            result = [query_clean] + [v for v in variants if v != query_clean]
            result = result[: self.max_variants]

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Query expanded: '{query[:40]}...' → {len(result)} variants in {elapsed_ms:.1f}ms",
                extra={
                    "original_query": query[:50],
                    "num_variants": len(result),
                    "elapsed_ms": elapsed_ms,
                },
            )

            return result

        except Exception as e:
            logger.warning(
                f"Query expansion failed, returning original: {e}",
                extra={"query": query[:50], "error": str(e)},
            )
            return [query]

    def generate_synonyms(self, query: str) -> list[str]:
        """
        Generate query variants by replacing terms with synonyms.

        Uses the Indonesian business terms dictionary to find
        equivalent terms in English and Indonesian.

        Args:
            query: Original user query

        Returns:
            List of query variants with synonyms replaced

        Example:
            >>> expander.generate_synonyms("How to apply for KITAS?")
            ['How to apply for residence permit?', 'How to apply for kartu izin tinggal terbatas?']
        """
        if not query or not query.strip():
            return []

        variants: set[str] = set()
        query_lower = query.lower()

        # Find matching terms and generate variants
        for pattern, synonyms in self._synonym_patterns.items():
            if pattern.search(query_lower):
                # Generate variant with each synonym
                for synonym in synonyms:
                    variant = pattern.sub(synonym, query, count=0)
                    if variant != query:
                        variants.add(variant)

        return list(variants)

    async def translate_variants(self, query: str, languages: list[str] | None = None) -> list[str]:
        """
        Generate translation variants of the query.

        Uses lightweight dictionary-based translation for common terms.
        For full translation, uses LLM (cached).

        Args:
            query: Original user query
            languages: Target languages (default: ["id", "en"])

        Returns:
            List of translated query variants

        Example:
            >>> variants = await expander.translate_variants("How to get KITAS?", ["id"])
            >>> print(variants)
            ['Cara mendapatkan KITAS?']
        """
        if not query or not query.strip():
            return []

        languages = languages or ["id", "en"]
        variants: set[str] = set()

        # Check cache first
        cache_key = self._generate_cache_key(query, "translate")
        cached_result = await self.cache_service.get(cache_key)
        if cached_result:
            logger.debug(f"Cache HIT for translation: {query[:30]}...")
            return cached_result

        try:
            # Try dictionary-based translation first (fast)
            dict_variants = self._dictionary_translate(query, languages)
            variants.update(dict_variants)

            # If no dictionary matches, try LLM translation
            if not variants and len(query.split()) <= 10:  # Only for short queries
                llm_variants = await self._llm_translate(query, languages)
                variants.update(llm_variants)

            result = list(variants)

            # Cache the result
            await self.cache_service.set(cache_key, result, ttl=3600)

            return result

        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return []

    def _dictionary_translate(self, query: str, languages: list[str]) -> set[str]:
        """Translate using dictionary lookups (fast, no LLM)."""
        variants: set[str] = set()
        query_lower = query.lower()

        # Simple phrase mappings for common queries
        phrase_mappings: dict[str, dict[str, str]] = {
            "how to": {"id": "cara", "en": "how to"},
            "what is": {"id": "apa itu", "en": "what is"},
            "cara": {"id": "cara", "en": "how to"},
            "apa itu": {"id": "apa itu", "en": "what is"},
            "apply for": {"id": "mengajukan", "en": "apply for"},
            "get": {"id": "mendapatkan", "en": "get"},
            "mengajukan": {"id": "mengajukan", "en": "apply for"},
            "mendapatkan": {"id": "mendapatkan", "en": "get"},
            "requirements": {"id": "persyaratan", "en": "requirements"},
            "persyaratan": {"id": "persyaratan", "en": "requirements"},
            "process": {"id": "proses", "en": "process"},
            "proses": {"id": "proses", "en": "process"},
        }

        for phrase, translations in phrase_mappings.items():
            if phrase in query_lower:
                for lang in languages:
                    if lang in translations:
                        translation = translations[lang]
                        if translation != phrase:
                            variant = query_lower.replace(phrase, translation)
                            # Capitalize first letter
                            variant = variant[0].upper() + variant[1:]
                            variants.add(variant)

        return variants

    async def _llm_translate(self, query: str, languages: list[str]) -> set[str]:
        """Translate using LLM (slower but more accurate)."""
        variants: set[str] = set()

        client = self._get_genai_client()
        if not client:
            return variants

        target_langs = ", ".join(
            [{"id": "Indonesian", "en": "English"}.get(lang, lang) for lang in languages],
        )

        prompt = f"""Translate this query to {target_langs}.
Keep it concise and natural for search queries.

Query: "{query}"

Return ONLY a JSON object with language codes as keys:
{{"id": "indonesian translation", "en": "english translation"}}"""

        try:
            import asyncio

            result = await asyncio.wait_for(
                client.generate_content(
                    contents=prompt,
                    model="gemini-2.0-flash-lite",
                    max_output_tokens=256,
                ),
                timeout=self.llm_timeout_ms / 1000,
            )

            if result and result.get("text"):
                text = result["text"]
                # Extract JSON
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    try:
                        translations = json.loads(text[start:end])
                        for lang in languages:
                            if lang in translations:
                                variants.add(translations[lang])
                    except json.JSONDecodeError as e:
                        logger.debug(f"Translation JSON parse skipped: {e}")

        except asyncio.TimeoutError:
            logger.debug("LLM translation timeout, using dictionary only")
        except Exception as e:
            logger.debug(f"LLM translation failed: {e}")

        return variants

    async def hybrid_expansion(self, query: str) -> list[str]:
        """
        Perform hybrid expansion combining all strategies.

        This is an alias for expand() with default num_variants,
        designed for easy integration with RAG pipelines.

        Args:
            query: Original user query

        Returns:
            List of expanded query variants

        Example:
            >>> variants = await expander.hybrid_expansion("KITAS requirements")
            >>> print(variants)
            ['KITAS requirements', 'residence permit requirements', ...]
        """
        return await self.expand(query, num_variants=self.max_variants)

    async def _llm_rephrase(self, query: str, num_variants: int = 2) -> list[str]:
        """
        Generate rephrased variants using LLM.

        Lightweight rephrasing for semantic search optimization.
        Uses Gemini Flash for speed (< 100ms).

        Args:
            query: Original query
            num_variants: Number of variants to generate

        Returns:
            List of rephrased variants
        """
        variants: list[str] = []

        # Check cache
        cache_key = self._generate_cache_key(query, "rephrase")
        cached_result = await self.cache_service.get(cache_key)
        if cached_result:
            return cached_result[:num_variants]

        client = self._get_genai_client()
        if not client:
            return variants

        prompt = self.REPHRASE_PROMPT.format(
            query=query,
            num_variants=num_variants,
        )

        try:
            import asyncio

            start_time = time.time()

            result = await asyncio.wait_for(
                client.generate_content(
                    contents=prompt,
                    model="gemini-2.0-flash-lite",
                    max_output_tokens=256,
                ),
                timeout=self.llm_timeout_ms / 1000,
            )

            elapsed_ms = (time.time() - start_time) * 1000

            if result and result.get("text"):
                text = result["text"]
                # Extract JSON array
                start = text.find("[")
                end = text.rfind("]") + 1
                if start != -1 and end > start:
                    try:
                        parsed = json.loads(text[start:end])
                        if isinstance(parsed, list):
                            variants = [v for v in parsed if isinstance(v, str)]
                            logger.debug(
                                f"LLM rephrasing completed in {elapsed_ms:.1f}ms: {len(variants)} variants",
                            )

                            # Cache the result
                            await self.cache_service.set(cache_key, variants, ttl=3600)
                    except json.JSONDecodeError as e:
                        logger.debug(f"Query rephrase JSON parse skipped: {e}")

        except asyncio.TimeoutError:
            logger.debug("LLM rephrasing timeout")
        except Exception as e:
            logger.debug(f"LLM rephrasing failed: {e}")

        return variants[:num_variants]

    def _relax_filters(self, query: str) -> str:
        """
        Remove or relax restrictive filters from query.

        Removes words like "only", "specifically", "must be" that
        might limit retrieval results unnecessarily.

        Args:
            query: Original query

        Returns:
            Query with relaxed filters

        Example:
            >>> expander._relax_filters("I only want PT PMA companies")
            'I want PT PMA companies'
        """
        if not query:
            return query

        relaxed = query
        query.lower()

        # Remove filter keywords
        for keyword in FILTER_KEYWORDS:
            # Match whole words only
            pattern = r"\b" + re.escape(keyword) + r"\b"
            relaxed = re.sub(pattern, "", relaxed, flags=re.IGNORECASE)

        # Clean up extra whitespace
        relaxed = " ".join(relaxed.split())

        return relaxed.strip()

    async def get_expansion_details(self, query: str) -> dict[str, Any]:
        """
        Get detailed expansion breakdown for debugging.

        Returns a dictionary with all expansion strategies and their results.

        Args:
            query: Original user query

        Returns:
            Dictionary with expansion details

        Example:
            >>> details = await expander.get_expansion_details("How to get KITAS?")
            >>> print(details["synonym_variants"])
            ['How to get residence permit?', 'How to get kartu izin tinggal terbatas?']
        """
        start_time = time.time()

        synonym_variants = self.generate_synonyms(query)
        translation_variants = await self.translate_variants(query)
        llm_variants = await self._llm_rephrase(query, num_variants=2)
        relaxed_query = self._relax_filters(query)

        elapsed_ms = (time.time() - start_time) * 1000

        # Combine all unique variants
        all_variants = {query}
        all_variants.update(synonym_variants)
        all_variants.update(translation_variants)
        all_variants.update(llm_variants)
        if relaxed_query != query:
            all_variants.add(relaxed_query)

        return {
            "original": query,
            "final_variants": list(all_variants),
            "synonym_variants": synonym_variants,
            "translation_variants": translation_variants,
            "llm_variants": llm_variants,
            "relaxed_query": relaxed_query if relaxed_query != query else None,
            "total_variants": len(all_variants),
            "elapsed_ms": elapsed_ms,
        }

    async def clear_cache(self, query: str | None = None) -> int:
        """
        Clear expansion cache.

        Args:
            query: Optional specific query to clear, or None to clear all

        Returns:
            Number of cache entries cleared
        """
        if query:
            # Clear specific query
            keys_to_clear = [
                self._generate_cache_key(query, "translate"),
                self._generate_cache_key(query, "rephrase"),
            ]
            count = 0
            for key in keys_to_clear:
                if await self.cache_service.delete(key):
                    count += 1
            return count
        # Clear all query expansion cache
        return await self.cache_service.clear_pattern("zantara:query_expand:*")


# Singleton instance for easy access
_query_expander_instance: QueryExpander | None = None


def get_query_expander() -> QueryExpander:
    """
    Get singleton QueryExpander instance.

    Returns:
        QueryExpander instance

    Example:
        >>> expander = get_query_expander()
        >>> variants = await expander.expand("KITAS application")
    """
    global _query_expander_instance
    if _query_expander_instance is None:
        _query_expander_instance = QueryExpander()
    return _query_expander_instance
