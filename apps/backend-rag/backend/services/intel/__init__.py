"""
Intel Services Module

Services for Intel News management and processing.

Extended with dossier system (migration 113):
- dossier_models: Pydantic schemas for TrendSignal + ResearchDossier
- dossier_repository: asyncpg CRUD for trend_signals, research_dossiers, reuses
"""

from backend.services.intel.dossier_compiler import (
    CompileSummary,
    DossierCompiler,
)
from backend.services.intel.dossier_models import (
    ConsumerType,
    DossierCitation,
    DossierEntity,
    DossierFact,
    DossierNumber,
    DossierPrecedent,
    IntelEventPayload,
    RefreshReason,
    ResearchDossier,
    ResearchDossierCreate,
    TopicCategory,
    TrendSignal,
    TrendSignalCreate,
    TrendSource,
)
from backend.services.intel.dossier_repository import IntelRepository
from backend.services.intel.dossier_slug import (
    build_dossier_slug,
    categorize_topic,
)
from backend.services.intel.intel_analytics_service import IntelAnalyticsService
from backend.services.intel.intel_approval_service import IntelApprovalService
from backend.services.intel.intel_classification_service import IntelClassificationService
from backend.services.intel.intel_staging_service import IntelStagingService

__all__ = [
    "CompileSummary",
    "ConsumerType",
    "DossierCitation",
    "DossierCompiler",
    "DossierEntity",
    "DossierFact",
    "DossierNumber",
    "DossierPrecedent",
    "IntelAnalyticsService",
    "IntelApprovalService",
    "IntelClassificationService",
    "IntelEventPayload",
    "IntelRepository",
    "IntelStagingService",
    "RefreshReason",
    "ResearchDossier",
    "ResearchDossierCreate",
    "TopicCategory",
    "TrendSignal",
    "TrendSignalCreate",
    "TrendSource",
    "build_dossier_slug",
    "categorize_topic",
]
