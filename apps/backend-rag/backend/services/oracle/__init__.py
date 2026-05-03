"""
Oracle Module
Specialized services extracted from OracleService
"""

# Import sub-services FIRST to avoid circular imports
from .analytics import OracleAnalyticsService

# Import main services AFTER sub-services
from .cross_oracle_synthesis_service import (
    CrossOracleSynthesisService,
    OracleQuery,
    SynthesisResult,
)
from .document_retrieval import DocumentRetrievalService
from .language_detector import LanguageDetectionService
from .oracle_config import OracleConfiguration, oracle_config
from .oracle_database import DatabaseManager, db_manager
from .oracle_google_services import GoogleServices, google_services
from .oracle_service import OracleService, detect_query_language, generate_query_hash
from .reasoning_engine import ReasoningEngineService
from .smart_oracle import (
    download_pdf_from_drive,
    get_drive_service,
    smart_oracle,
    test_drive_connection,
)
from .user_context import UserContextService

__all__ = [
    "LanguageDetectionService",
    "UserContextService",
    "ReasoningEngineService",
    "DocumentRetrievalService",
    "OracleAnalyticsService",
    "OracleConfiguration",
    "oracle_config",
    "DatabaseManager",
    "db_manager",
    "GoogleServices",
    "google_services",
    "OracleService",
    "detect_query_language",
    "generate_query_hash",
    "smart_oracle",
    "download_pdf_from_drive",
    "get_drive_service",
    "test_drive_connection",
    "CrossOracleSynthesisService",
    "OracleQuery",
    "SynthesisResult",
]
