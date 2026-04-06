"""
Knowledge Graph Data Models

Dataclass definitions for KG extraction pipeline.
Used by extractor_gemini.py (production), pipeline.py, quality_filter.py, coreference.py.

NOTE: The deprecated KGExtractor class (Anthropic/Claude) was removed in S05 solidification.
Production extractor: extractor_gemini.py (GeminiKGExtractor)
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.services.knowledge_graph.ontology import (
    EntityType,
    RelationType,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """Extracted entity from text"""

    id: str
    type: EntityType
    name: str
    mention: str  # Original text mention
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8
    start_pos: int | None = None
    end_pos: int | None = None


@dataclass
class ExtractedRelation:
    """Extracted relation between entities"""

    source_id: str
    target_id: str
    type: RelationType
    evidence: str  # Text evidence for relation
    confidence: float = 0.7
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result of extraction from a chunk"""

    chunk_id: str
    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)
    raw_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
