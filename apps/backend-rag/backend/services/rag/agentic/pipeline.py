"""
Response Processing Pipeline

A clean pipeline pattern for processing LLM responses through multiple stages.
Each stage is independent and can be tested/configured separately.

Architecture:
- PipelineStage: Base class for all processing stages
- VerificationStage: Verify response quality and accuracy
- PostProcessingStage: Clean and format response text
- CitationStage: Extract and normalize citations
- FormatStage: Final formatting for output
- ResponsePipeline: Main orchestrator that runs data through stages

Benefits:
- Single Responsibility: Each stage has one job
- Testability: Test stages independently
- Reusability: Stages can be reused in different pipelines
- Configurability: Easy to add/remove stages
- No Duplication: Post-processing logic in one place
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from services.rag.verification_service import verification_service

from .response_processor import post_process_response

logger = logging.getLogger(__name__)


class PipelineStage(ABC):
    """
    Base class for pipeline stages.

    Each stage processes data and returns modified data.
    Stages should be stateless and idempotent where possible.
    """

    @abstractmethod
    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Process data and return modified data.

        Args:
            data: Dictionary containing processing data

        Returns:
            Modified data dictionary
        """
        pass

    @property
    def name(self) -> str:
        """Return stage name for logging"""
        return self.__class__.__name__


class VerificationStage(PipelineStage):
    """
    Verify response quality and accuracy.

    Uses the verification service to check if the response
    is supported by the retrieved context.

    Only verifies substantial responses (>50 chars) with context.
    """

    def __init__(self, min_response_length: int = 50):
        """
        Initialize verification stage.

        Args:
            min_response_length: Minimum response length to trigger verification
        """
        self.min_response_length = min_response_length

    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Verify response and add verification metadata.

        Adds:
        - verification: Full verification result
        - verification_score: Score (0-1)
        - verification_status: Status string
        """
        response = data.get("response", "")
        query = data.get("query", "")
        context_chunks = data.get("context_chunks", [])

        # Skip verification for short responses or no context
        if len(response) < self.min_response_length or not context_chunks:
            logger.debug(f"[{self.name}] Skipping verification (response too short or no context)")
            data["verification_score"] = 1.0
            data["verification_status"] = "skipped"
            return data

        try:
            verification = await verification_service.verify_response(
                query=query,
                draft_answer=response,
                context_chunks=context_chunks,
            )

            data["verification"] = {
                "is_valid": verification.is_valid,
                "status": verification.status.value,
                "score": verification.score,
                "reasoning": verification.reasoning,
                "missing_citations": verification.missing_citations,
            }
            data["verification_score"] = verification.score
            data["verification_status"] = verification.status.value

            logger.info(
                f"[{self.name}] Verification complete: "
                f"status={verification.status.value}, score={verification.score:.2f}"
            )

        except (ValueError, RuntimeError, KeyError) as e:
            logger.warning(f"[{self.name}] Verification failed: {e}", exc_info=True)
            data["verification_score"] = 0.5
            data["verification_status"] = "error"

        return data


class PostProcessingStage(PipelineStage):
    """
    Clean and format response text.

    Applies:
    - Internal reasoning pattern removal (THOUGHT:, ACTION:, etc.)
    - Language detection and enforcement
    - Procedural question formatting
    - Emotional acknowledgment
    """

    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Apply text cleaning and formatting.

        Uses the existing post_process_response function
        which handles all communication rules.
        """
        response = data.get("response", "")
        query = data.get("query", "")

        if not response:
            logger.debug(f"[{self.name}] Skipping (empty response)")
            return data

        try:
            # Apply all post-processing rules
            cleaned = post_process_response(response, query)

            # Update response
            original_length = len(response)
            data["response"] = cleaned

            logger.info(
                f"[{self.name}] Post-processing complete: "
                f"{original_length} -> {len(cleaned)} chars"
            )

        except (ValueError, RuntimeError) as e:
            logger.warning(f"[{self.name}] Post-processing failed: {e}", exc_info=True)
            # Keep original response on error

        return data


class CitationStage(PipelineStage):
    """
    Extract and normalize citations.

    Processes sources from vector search and other tools:
    - Deduplicates by (title, url)
    - Normalizes field names
    - Filters out invalid entries
    - Sorts by relevance score
    """

    def __init__(self, max_citations: int = 10):
        """
        Initialize citation stage.

        Args:
            max_citations: Maximum number of citations to include
        """
        self.max_citations = max_citations

    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract citations from sources.

        Adds:
        - citations: List of normalized citation objects
        - citation_count: Number of citations
        """
        sources = data.get("sources", [])

        if not sources:
            logger.debug(f"[{self.name}] No sources to process")
            data["citations"] = []
            data["citation_count"] = 0
            return data

        try:
            # Normalize and deduplicate
            normalized = self._normalize_citations(sources)

            # Limit citations
            if len(normalized) > self.max_citations:
                normalized = normalized[: self.max_citations]

            data["citations"] = normalized
            data["citation_count"] = len(normalized)

            logger.info(
                f"[{self.name}] Processed {len(sources)} sources -> "
                f"{len(normalized)} unique citations"
            )

        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"[{self.name}] Citation processing failed: {e}", exc_info=True)
            data["citations"] = []
            data["citation_count"] = 0

        return data

    def _normalize_citations(self, sources: list) -> list[dict[str, Any]]:
        """
        Normalize and deduplicate citations.

        Args:
            sources: Raw source objects from tools

        Returns:
            List of normalized citation objects
        """
        seen = set()
        normalized = []

        for src in sources:
            if not isinstance(src, dict):
                continue

            # Extract fields with fallbacks
            title = src.get("title", "")
            url = src.get("url", src.get("source_url", ""))

            # Skip if missing essential fields
            if not title:
                continue

            # Deduplicate by (title, url)
            key = (title, url)
            if key in seen:
                continue

            seen.add(key)

            # Build normalized citation
            normalized.append(
                {
                    "title": title,
                    "url": url,
                    "collection": src.get("collection", ""),
                    "score": float(src.get("score", 0)),
                    "snippet": src.get("snippet", ""),
                    "metadata": src.get("metadata", {}),
                }
            )

        # Sort by relevance score (descending)
        normalized.sort(key=lambda x: x["score"], reverse=True)

        return normalized


class FormatStage(PipelineStage):
    """
    Final formatting for output.

    Ensures consistent output structure and adds
    any final metadata or formatting.
    """

    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Format final output structure.

        Ensures all expected fields are present and
        properly formatted for API response.
        """
        # Ensure response is stripped
        if "response" in data:
            data["response"] = data["response"].strip()

        # Ensure citations list exists
        if "citations" not in data:
            data["citations"] = []

        # Add processing metadata
        data["pipeline_version"] = "1.0"
        data["stages_completed"] = data.get("stages_completed", []) + [self.name]

        logger.debug(f"[{self.name}] Final formatting complete")

        return data


class ResponsePipeline:
    """
    Main pipeline orchestrator.

    Runs data through a sequence of processing stages.
    Each stage can modify the data and pass it to the next stage.

    Example:
        pipeline = ResponsePipeline([
            VerificationStage(),
            PostProcessingStage(),
            CitationStage(),
            FormatStage(),
        ])

        result = await pipeline.process({
            "response": "...",
            "query": "...",
            "sources": [...],
        })
    """

    def __init__(self, stages: list[PipelineStage]):
        """
        Initialize pipeline with stages.

        Args:
            stages: List of pipeline stages to execute in order
        """
        self.stages = stages
        logger.info(
            f"[ResponsePipeline] Initialized with {len(stages)} stages: "
            f"{', '.join(s.name for s in stages)}"
        )

    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Run data through all pipeline stages.

        Args:
            data: Input data dictionary

        Returns:
            Processed data dictionary

        Raises:
            ValueError: If data is None or stages fail
        """
        if data is None:
            raise ValueError("Pipeline data cannot be None")

        # Track stages completed
        data["stages_completed"] = []

        for stage in self.stages:
            try:
                logger.debug(f"[ResponsePipeline] Executing stage: {stage.name}")
                data = await stage.process(data)
                data["stages_completed"].append(stage.name)

            except (ValueError, RuntimeError, KeyError, TypeError) as e:
                logger.error(f"[ResponsePipeline] Stage {stage.name} failed: {e}", exc_info=True)
                # Continue pipeline even if one stage fails
                # This ensures we always get some output
                data["stages_completed"].append(f"{stage.name} (failed)")

        logger.info(
            f"[ResponsePipeline] Processing complete: "
            f"{len(data['stages_completed'])} stages executed"
        )

        return data


def create_default_pipeline() -> ResponsePipeline:
    """
    Create the default response processing pipeline.

    Default stages:
    1. VerificationStage: Verify against context
    2. PostProcessingStage: Clean and format
    3. CitationStage: Normalize citations
    4. FormatStage: Final formatting

    Returns:
        Configured ResponsePipeline instance
    """
    return ResponsePipeline(
        [
            VerificationStage(min_response_length=50),
            PostProcessingStage(),
            CitationStage(max_citations=10),
            FormatStage(),
        ]
    )
