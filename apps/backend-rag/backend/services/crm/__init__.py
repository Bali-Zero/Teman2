"""CRM services module - Production Ready."""

# Core services
from .ai_crm_extractor import AICRMExtractor, get_extractor
from .audit_trail import AuditAction, CRMAuditor
from .cache_manager import crm_cache, invalidate_client_cache, query_cache
from .collaborator_service import CollaboratorProfile, CollaboratorService
from .enhanced_crm_service import EnhancedCRMService, get_enhanced_crm_service
from .query_optimizer import CRMQueryOptimizer

# New optimized modules
from .validators import ClientValidator, PracticeValidator, normalize_phone_e164

__all__ = [
    # Legacy
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
