"""
Citation Service - Add inline citations and source references to AI responses
Enhances credibility and transparency by showing where information comes from

This service enables AI to cite sources using inline references [1], [2] and
provide full source details at the end of responses, building user trust.

Author: ZANTARA Development Team
Date: 2025-10-16
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class CitationService:
    """
    Manages citation formatting and source references for AI responses

    Features:
    - Inline citation markers [1], [2], etc.
    - Full source details with titles, URLs, dates
    - Automatic citation numbering
    - Support for multiple source types (RAG docs, memory, web)
    """

    def __init__(self, search_service=None):
        """
        Initialize citation service

        Args:
            search_service: Optional SearchService instance (for test compatibility)
        """
        self.search_service = search_service
        logger.info("✅ CitationService initialized")

    async def generate_citations(
        self, search_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Generate citations from search results (for test compatibility).

        Args:
            search_results: List of search result dictionaries

        Returns:
            List of citation dictionaries
        """
        return self.extract_sources_from_rag(search_results)

    def create_citation_instructions(self, sources_available: bool = False) -> str:
        """
        Generate citation instructions for AI system prompt

        Args:
            sources_available: Whether RAG sources are available

        Returns:
            Citation instructions to add to system prompt
        """
        if not sources_available:
            return ""

        instructions = """
## Citation Guidelines

When using information from provided sources, include inline citations:

- Add [1], [2], [3] etc. after statements from specific sources
- Use citations for factual claims, statistics, regulations, or specific details
- At the end of your response, include a "Sources:" section with full references
- Format: [N] Title - URL (if available) - Date (if available)

Example:
"Indonesia requires a KITAS visa for business activities [1]. The minimum investment
for foreign companies is IDR 10 billion [2]."

Sources:
[1] Immigration Regulations 2024 - Ministry of Law and Human Rights
[2] Investment Requirements - BKPM Official Guidelines - 2024
"""
        return instructions

    def extract_sources_from_rag(self, rag_results: list[dict]) -> list[dict[str, Any]]:
        """
        Extract source metadata from RAG results

        Args:
            rag_results: List of RAG document results

        Returns:
            List of source dictionaries:
            [
                {
                    "id": 1,
                    "title": "Document title",
                    "url": "https://...",
                    "date": "2024-01-15",
                    "type": "rag",
                    "score": 0.85
                },
                ...
            ]
        """
        sources = []

        for idx, doc in enumerate(rag_results, start=1):
            metadata = doc.get("metadata", {})

            source = {
                "id": idx,
                "title": metadata.get("title", f"Document {idx}"),
                "url": metadata.get("url", metadata.get("source_url", "")),
                "date": metadata.get("date", metadata.get("scraped_at", "")),
                "type": "rag",
                "score": doc.get("score", 0.0),
                "category": metadata.get("category", "general"),
            }

            sources.append(source)

        logger.info(f"📚 [Citations] Extracted {len(sources)} sources from RAG")
        return sources

    def format_sources_section(self, sources: list[dict[str, Any]]) -> str:
        """
        Format sources into a readable "Sources:" section

        Args:
            sources: List of source dictionaries

        Returns:
            Formatted sources section:

            Sources:
            [1] Immigration Regulations 2024 - https://... - 2024-01-15
            [2] BKPM Investment Guidelines - https://... - 2024-02-20
            [3] Tax Law Overview - Ministry of Finance - 2024-03-10
        """
        if not sources:
            return ""

        lines = ["\n\n---\n**Sources:**"]

        for source in sources:
            source_id = source["id"]
            title = source["title"]
            url = source.get("url", "")
            date = source.get("date", "")

            # Format each source line
            parts = [f"[{source_id}] {title}"]

            if url:
                parts.append(url)

            if date:
                # Try to format date nicely
                try:
                    if isinstance(date, str) and len(date) >= 10:
                        date = date[:10]  # Take YYYY-MM-DD part
                    parts.append(date)
                except Exception:
                    pass

            line = " - ".join(parts)
            lines.append(line)

        return "\n".join(lines)

    def inject_citation_context_into_prompt(
        self, system_prompt: str, sources: list[dict[str, Any]]
    ) -> str:
        """
        Inject citation instructions and source context into system prompt

        Args:
            system_prompt: Original system prompt
            sources: Available sources

        Returns:
            Enhanced system prompt with citation instructions
        """
        if not sources:
            return system_prompt

        # Add citation instructions
        citation_instructions = self.create_citation_instructions(sources_available=True)

        # Add source listing for AI reference
        source_context = "\n\n## Available Sources\n\n"
        for source in sources:
            source_context += f"[{source['id']}] {source['title']}"
            if source.get("category"):
                source_context += f" (Category: {source['category']})"
            source_context += "\n"

        enhanced_prompt = system_prompt + citation_instructions + source_context

        logger.info(f"📝 [Citations] Injected {len(sources)} sources into prompt")
        return enhanced_prompt

    def validate_citations_in_response(
        self, response_text: str, sources: list[dict]
    ) -> dict[str, Any]:
        """
        Validate that citations in response match available sources

        Args:
            response_text: AI response text
            sources: Available sources

        Returns:
            Validation result:
            {
                "valid": bool,
                "citations_found": [1, 2, 3],
                "invalid_citations": [5],  # Citations referenced but not in sources
                "unused_sources": [4],      # Sources provided but not cited
                "stats": {...}
            }
        """
        # Extract citation numbers from response [1], [2], etc.
        citation_pattern = r"\[(\d+)\]"
        found_citations = re.findall(citation_pattern, response_text)
        found_citations = [int(c) for c in found_citations]
        found_citations = list(set(found_citations))  # Remove duplicates

        # Get available source IDs
        available_source_ids = [s["id"] for s in sources]

        # Find invalid citations (referenced but not available)
        invalid_citations = [c for c in found_citations if c not in available_source_ids]

        # Find unused sources (provided but not cited)
        unused_sources = [s for s in available_source_ids if s not in found_citations]

        valid = len(invalid_citations) == 0

        result = {
            "valid": valid,
            "citations_found": sorted(found_citations),
            "invalid_citations": invalid_citations,
            "unused_sources": unused_sources,
            "stats": {
                "total_citations": len(found_citations),
                "total_sources": len(sources),
                "citation_rate": len(found_citations) / len(sources) if sources else 0,
            },
        }

        if invalid_citations:
            logger.warning(f"⚠️ [Citations] Invalid citations found: {invalid_citations}")
        else:
            logger.info(
                f"✅ [Citations] Valid - {len(found_citations)} citations, "
                f"{len(unused_sources)} unused sources"
            )

        return result

    def append_sources_to_response(
        self,
        response_text: str,
        sources: list[dict[str, Any]],
        validation_result: dict | None = None,
    ) -> str:
        """
        Append formatted sources section to AI response

        Args:
            response_text: Original AI response
            sources: Available sources
            validation_result: Optional validation result to filter unused sources

        Returns:
            Response with sources section appended
        """
        if not sources:
            return response_text

        # If validation result provided, only include cited sources
        if validation_result and validation_result.get("citations_found"):
            cited_source_ids = validation_result["citations_found"]
            sources = [s for s in sources if s["id"] in cited_source_ids]

        # Format sources section
        sources_section = self.format_sources_section(sources)

        # Append to response
        enhanced_response = response_text + sources_section

        logger.info(f"📚 [Citations] Appended {len(sources)} sources to response")
        return enhanced_response

    def process_response_with_citations(
        self, response_text: str, rag_results: list[dict] | None = None, auto_append: bool = True
    ) -> dict[str, Any]:
        """
        Complete citation processing workflow

        Args:
            response_text: AI response text
            rag_results: RAG results (if available)
            auto_append: Automatically append sources section

        Returns:
            {
                "response": str,           # Response with sources appended
                "sources": List[Dict],     # Source metadata
                "validation": Dict,        # Citation validation result
                "has_citations": bool
            }
        """
        # Extract sources from RAG
        sources = []
        if rag_results:
            sources = self.extract_sources_from_rag(rag_results)

        # Validate citations in response
        validation = self.validate_citations_in_response(response_text, sources)

        # Append sources if requested
        final_response = response_text
        if auto_append and sources and validation["citations_found"]:
            final_response = self.append_sources_to_response(response_text, sources, validation)

        return {
            "response": final_response,
            "sources": sources,
            "validation": validation,
            "has_citations": len(validation["citations_found"]) > 0,
        }

    def create_source_metadata_for_frontend(self, sources: list[dict]) -> list[dict]:
        """
        Format source metadata for frontend display

        Args:
            sources: Source dictionaries

        Returns:
            Frontend-friendly source metadata:
            [
                {
                    "id": 1,
                    "title": "...",
                    "url": "...",
                    "date": "...",
                    "type": "rag" | "memory" | "web",
                    "category": "immigration" | "tax" | ...
                },
                ...
            ]
        """
        frontend_sources = []

        for source in sources:
            frontend_sources.append(
                {
                    "id": source["id"],
                    "title": source.get("title", "Unknown Source"),
                    "url": source.get("url", ""),
                    "date": source.get("date", ""),
                    "type": source.get("type", "rag"),
                    "category": source.get("category", "general"),
                }
            )

        return frontend_sources

    async def health_check(self) -> dict[str, Any]:
        """
        Health check for citation service

        Returns:
            {
                "status": "healthy",
                "features": {...}
            }
        """
        return {
            "status": "healthy",
            "features": {
                "inline_citations": True,
                "source_formatting": True,
                "citation_validation": True,
                "rag_integration": True,
                "frontend_metadata": True,
            },
        }
