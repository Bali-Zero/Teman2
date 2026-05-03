"""
Autonomous Agents package for Nuzantara RAG.

Provides autonomous agent capabilities for knowledge extraction and graph building.

Exports:
    KnowledgeGraphBuilder: Agent for building knowledge graphs from documents.
    Entity: Data class representing a knowledge graph entity.
    Relationship: Data class representing relationships between entities.
"""

from .knowledge_graph_builder import Entity, KnowledgeGraphBuilder, Relationship

__all__ = ["KnowledgeGraphBuilder", "Entity", "Relationship"]
