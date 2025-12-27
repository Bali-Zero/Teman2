"""Ingestion services module."""

from .ingestion_service import IngestionService
from .collection_manager import CollectionManager
from .collection_health_service import (
    CollectionHealthService,
    HealthStatus,
    StalenessSeverity,
    CollectionMetrics,
)
from .collection_warmup_service import CollectionWarmupService
from .legal_ingestion_service import LegalIngestionService
from .auto_ingestion_orchestrator import (
    AutoIngestionOrchestrator,
    SourceType,
    UpdateType,
    IngestionStatus,
    MonitoredSource,
    ScrapedContent,
    IngestionJob,
)
from .politics_ingestion import PoliticsIngestionService

__all__ = [
    "IngestionService",
    "CollectionManager",
    "CollectionHealthService",
    "HealthStatus",
    "StalenessSeverity",
    "CollectionMetrics",
    "CollectionWarmupService",
    "LegalIngestionService",
    "AutoIngestionOrchestrator",
    "SourceType",
    "UpdateType",
    "IngestionStatus",
    "MonitoredSource",
    "ScrapedContent",
    "IngestionJob",
    "PoliticsIngestionService",
]
