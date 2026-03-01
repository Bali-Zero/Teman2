"""
Knowledge Graph Services
LLM-powered entity and relation extraction for Indonesian legal documents
"""

from .coreference import CoreferenceResolver
from .extractor import KGExtractor
from .ontology import ENTITY_SCHEMAS, RELATION_SCHEMAS, EntityType, RelationType
from .pipeline import KGPipeline, PipelineConfig
from .quality_filter import KGQualityFilter, apply_quality_filter_to_batch


# Lazy import for Gemini (requires vertexai SDK)
def get_gemini_extractor() -> Any:
    """Get GeminiKGExtractor (lazy import)"""
    from .extractor_gemini import GeminiKGExtractor

    return GeminiKGExtractor


__all__ = [
    "EntityType",
    "RelationType",
    "ENTITY_SCHEMAS",
    "RELATION_SCHEMAS",
    "KGExtractor",
    "get_gemini_extractor",
    "CoreferenceResolver",
    "KGPipeline",
    "PipelineConfig",
    "KGQualityFilter",
    "apply_quality_filter_to_batch",
]
