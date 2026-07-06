from __future__ import annotations

import backend.services.knowledge_graph as kg
from backend.services.knowledge_graph.coreference import CoreferenceResolver
from backend.services.knowledge_graph.extractor import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from backend.services.knowledge_graph.extractor_gemini import GeminiKGExtractor
from backend.services.knowledge_graph.ontology import EntityType, RelationType


def test_package_exports_public_knowledge_graph_symbols() -> None:
    assert set(kg.__all__) >= {
        "CoreferenceResolver",
        "EntityType",
        "ExtractedEntity",
        "ExtractedRelation",
        "ExtractionResult",
        "GeminiKGExtractor",
        "KGPipeline",
        "KGQualityFilter",
        "PipelineConfig",
        "RelationType",
    }


def test_exported_symbols_point_to_expected_implementations() -> None:
    assert kg.CoreferenceResolver is CoreferenceResolver
    assert kg.ExtractedEntity is ExtractedEntity
    assert kg.ExtractedRelation is ExtractedRelation
    assert kg.ExtractionResult is ExtractionResult
    assert kg.GeminiKGExtractor is GeminiKGExtractor
    assert kg.EntityType is EntityType
    assert kg.RelationType is RelationType


def test_schema_exports_are_populated() -> None:
    assert kg.ENTITY_SCHEMAS[EntityType.KITAS].description
    assert kg.RELATION_SCHEMAS[RelationType.REQUIRES].trigger_words
