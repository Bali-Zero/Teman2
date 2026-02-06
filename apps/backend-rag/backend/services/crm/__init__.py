"""CRM services module - Production Ready."""

# Core services
from .ai_crm_extractor import AICRMExtractor, get_extractor
from .auto_crm_service import AutoCRMService, get_auto_crm_service
from .collaborator_service import CollaboratorProfile, CollaboratorService

# New optimized modules
from .validators import ClientValidator, PracticeValidator, normalize_phone_e164
from .cache_manager import crm_cache, query_cache, invalidate_client_cache
from .query_optimizer import CRMQueryOptimizer
from .audit_trail import CRMAuditor, AuditAction
from .enhanced_crm_service import EnhancedCRMService, get_enhanced_crm_service

__all__ = [
    # Legacy
    "AutoCRMService",
    "get_auto_crm_service",
    "AICRMExtractor",
    "get_extractor",
    "CollaboratorService",
    "CollaboratorProfile",
    # New
    "EnhancedCRMService",
    "get_enhanced_crm_service",
    "ClientValidator",
    "PracticeValidator",
    "normalize_phone_e164",
    "crm_cache",
    "query_cache",
    "invalidate_client_cache",
    "CRMQueryOptimizer",
    "CRMAuditor",
    "AuditAction",
]
