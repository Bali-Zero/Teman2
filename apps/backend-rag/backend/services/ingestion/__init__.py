"""Ingestion services module."""

from .ingestion_service import IngestionService
from .collection_manager import CollectionManager
from .collection_health_service import CollectionHealthService
from .collection_warmup_service import CollectionWarmupService
from .legal_ingestion_service import LegalIngestionService
from .auto_ingestion_orchestrator import AutoIngestionOrchestrator
from .politics_ingestion import PoliticsIngestion

__all__ = [
    "IngestionService",
    "CollectionManager",
    "CollectionHealthService",
    "CollectionWarmupService",
    "LegalIngestionService",
    "AutoIngestionOrchestrator",
    "PoliticsIngestion",
]
