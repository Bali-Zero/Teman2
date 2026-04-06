"""
Knowledge Graph Services
LLM-powered entity and relation extraction for Indonesian legal documents
"""

from .coreference import CoreferenceResolver
from .extractor import ExtractedEntity, ExtractedRelation, ExtractionResult
from .extractor_gemini import GeminiKGExtractor
from .ontology import ENTITY_SCHEMAS, RELATION_SCHEMAS, EntityType, RelationType
from .pipeline import KGPipeline, PipelineConfig
from .quality_filter import KGQualityFilter, apply_quality_filter_to_batch

__all__ = [
    "EntityType",
    "RelationType",
    "ENTITY_SCHEMAS",
    "RELATION_SCHEMAS",
    "ExtractedEntity",
    "ExtractedRelation",
    "ExtractionResult",
    "GeminiKGExtractor",
    "CoreferenceResolver",
    "KGPipeline",
    "PipelineConfig",
    "KGQualityFilter",
    "apply_quality_filter_to_batch",
]
