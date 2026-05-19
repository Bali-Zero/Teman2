"""
KG Monitoring Service - Phase 8

Automated monitoring and ingestion service for Knowledge Graph data sources.
Monitors legal websites for changes, detects updates, and auto-ingests new content.

Components:
- scraper.py: Website monitoring and content extraction
- change_detector.py: Diff detection and hash storage
- auto_ingestion.py: LLM-based content extraction and ingestion
- quality_check.py: Content validation and quality assurance
"""

from .auto_ingestion import (
    AutoIngestionService,
    DocumentType,
    ExtractedDocument,
    IngestionResult,
    IngestionStatus,
)
from .change_detector import (
    ChangeDetector,
    ChangeEvent,
    ChangeType,
    DocumentState,
)
from .quality_check import (
    DimensionScore,
    QualityCheckService,
    QualityDimension,
    QualityLevel,
    QualityReport,
)
from .scraper import LegalScraper, ScrapedDocument, SourceConfig, SourceType

__all__ = [
    # Auto Ingestion
    "AutoIngestionService",
    # Change Detector
    "ChangeDetector",
    "ChangeEvent",
    "ChangeType",
    "DimensionScore",
    "DocumentState",
    "DocumentType",
    "ExtractedDocument",
    "IngestionResult",
    "IngestionStatus",
    # Scraper
    "LegalScraper",
    # Quality Check
    "QualityCheckService",
    "QualityDimension",
    "QualityLevel",
    "QualityReport",
    "ScrapedDocument",
    "SourceConfig",
    "SourceType",
]
