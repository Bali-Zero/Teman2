"""
Query Expander Service - Multilingue Query Expansion

Migliora la ricerca RAG espandendo le query in più lingue:
- Rileva la lingua della query
- Traduce in inglese (lingua ponte)
- Traduce in indonesiano (lingua documenti)
- Combina per massimizzare il match semantico

Author: RIRI
Date: 2026-01-28
"""

import json
import logging
from typing import Optional

from backend.app.core.config import settings
from backend.core.cache import cached
from backend.services.llm_clients.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class QueryExpander:
    """
    Multilingue Query Expansion Service.
    
    Espande le query utente in multiple lingue per migliorare
    il matching semantico con i documenti (principalmente in indonesiano).
    
    Flow:
    1. Detect lingua query
    2. Se non EN → traduci in EN  
    3. Traduci EN → ID (indonesiano)
    4. Return: "{original} {english} {indonesian}"
    
    Usa Gemini Flash per velocità e costo ridotto.
    """
    
    EXPANSION_PROMPT = """Analyze this query and provide translations for search optimization.

Query: "{query}"

Instructions:
1. Detect the language of the query (use ISO 639-1 code)
2. If NOT English, translate to English
3. Translate to Indonesian (Bahasa Indonesia)

Respond in this EXACT JSON format only (no markdown, no code blocks, no explanation):
{{"detected_lang": "xx", "english": "translation here", "indonesian": "translation here"}}

Rules:
- If query is already in English, copy it to "english" field
- If query is already in Indonesian, copy it to "indonesian" field
- Keep translations concise and search-optimized
- Preserve key terms and codes (like E25B, KITAS, etc.)"""

    def __init__(self, gemini_service: Optional[GeminiService] = None):
        """Initialize QueryExpander with optional Gemini service."""
        self._gemini = gemini_service
        self._initialized = False
    
    async def _ensure_client(self) -> GeminiService:
        """Lazy initialization of Gemini client."""
        if self._gemini is None:
            self._gemini = GeminiService()
        return self._gemini
    
    @cached(ttl=3600, prefix="query_expand")
    async def expand(self, query: str) -> str:
        """
        Expand query to multiple languages for better RAG matching.
        
        Args:
            query: Original user query in any language
            
        Returns:
            Expanded query combining original + English + Indonesian
            Falls back to original query on any error
        """
        # Check if feature is enabled
        if not getattr(settings, 'query_expansion_enabled', True):
            logger.debug("Query expansion disabled via settings")
            return query
            
        # Skip very short queries
        if not query or len(query.strip()) < 3:
            return query
        
        # Skip if query looks like a code/ID only
        if query.strip().upper() == query.strip() and len(query.strip()) < 10:
            logger.debug(f"Skipping expansion for code-like query: {query}")
            return query
        
        try:
            client = await self._ensure_client()
            
            prompt = self.EXPANSION_PROMPT.format(query=query)
            
            response = await client.generate_response(prompt=prompt)
            
            if not response or not response.strip():
                logger.warning(
                    "Empty response from Gemini for query expansion",
                    extra={"query": query[:50]}
                )
                return query
            
            # Parse JSON response
            try:
                clean_response = self._clean_json_response(response)
                result = json.loads(clean_response)
                
                english = result.get("english", "").strip()
                indonesian = result.get("indonesian", "").strip()
                detected = result.get("detected_lang", "unknown")
                
                # Build expanded query
                parts = [query]  # Always include original
                
                # Add English if different from original
                if english and english.lower() != query.lower():
                    parts.append(english)
                
                # Add Indonesian if different from both
                if indonesian and indonesian.lower() != query.lower():
                    if indonesian.lower() != english.lower():
                        parts.append(indonesian)
                
                expanded = " ".join(parts)
                
                logger.info(
                    f"Query expanded: '{query[:30]}...' ({detected}) → {len(expanded)} chars",
                    extra={
                        "original_query": query[:50],
                        "detected_lang": detected,
                        "original_len": len(query),
                        "expanded_len": len(expanded),
                        "expansion_ratio": len(expanded) / len(query) if query else 1,
                    }
                )
                
                return expanded
                
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse Gemini response as JSON: {e}",
                    extra={"response": response[:200], "query": query[:50]}
                )
                return query
                
        except Exception as e:
            logger.warning(
                f"Query expansion failed, using original: {e}",
                extra={"query": query[:50], "error": str(e)}
            )
            return query
    
    def _clean_json_response(self, response: str) -> str:
        """Clean potential markdown or extra text from JSON response."""
        clean = response.strip()
        
        # Remove markdown code blocks
        if clean.startswith("```"):
            lines = clean.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean = "\n".join(lines)
        
        # Try to find JSON object
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start != -1 and end > start:
            clean = clean[start:end]
        
        return clean.strip()
    
    async def expand_with_details(self, query: str) -> dict:
        """
        Expand query and return detailed breakdown.
        
        Useful for debugging and analytics.
        
        Args:
            query: Original user query
            
        Returns:
            Dict with original, expanded, and metadata
        """
        expanded = await self.expand(query)
        
        return {
            "original": query,
            "expanded": expanded,
            "expansion_applied": expanded != query,
            "original_length": len(query),
            "expanded_length": len(expanded),
        }
