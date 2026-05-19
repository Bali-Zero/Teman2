"""Ingestion services module."""

from .auto_ingestion_orchestrator import (
    AutoIngestionOrchestrator,
    IngestionJob,
    IngestionStatus,
    MonitoredSource,
    ScrapedContent,
    SourceType,
    UpdateType,
)
from .collection_health_service import (
    CollectionHealthService,
    CollectionMetrics,
    HealthStatus,
    StalenessSeverity,
)
from .collection_manager import CollectionManager
from .collection_warmup_service import CollectionWarmupService
from .ingestion_service import IngestionService
from .legal_ingestion_service import LegalIngestionService
from .politics_ingestion import PoliticsIngestionService

__all__ = [
    "AutoIngestionOrchestrator",
    "CollectionHealthService",
    "CollectionManager",
    "CollectionMetrics",
    "CollectionWarmupService",
    "HealthStatus",
    "IngestionJob",
    "IngestionService",
    "IngestionStatus",
    "LegalIngestionService",
    "MonitoredSource",
    "PoliticsIngestionService",
    "ScrapedContent",
    "SourceType",
    "StalenessSeverity",
    "UpdateType",
]
