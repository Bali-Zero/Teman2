"""
Knowledge Graph Services
LLM-powered entity and relation extraction for Indonesian legal documents
"""

from .ontology import EntityType, RelationType, ENTITY_SCHEMAS, RELATION_SCHEMAS
from .extractor import KGExtractor
from .coreference import CoreferenceResolver
from .pipeline import KGPipeline, PipelineConfig

# Lazy import for Gemini (requires vertexai SDK)
def get_gemini_extractor():
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
]
