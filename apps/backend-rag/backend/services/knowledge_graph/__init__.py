"""
Knowledge Graph Services
LLM-powered entity and relation extraction for Indonesian legal documents
"""

from .ontology import EntityType, RelationType, ENTITY_SCHEMAS, RELATION_SCHEMAS
from .extractor import KGExtractor
from .coreference import CoreferenceResolver
from .pipeline import KGPipeline

__all__ = [
    "EntityType",
    "RelationType",
    "ENTITY_SCHEMAS",
    "RELATION_SCHEMAS",
    "KGExtractor",
    "CoreferenceResolver",
    "KGPipeline",
]
