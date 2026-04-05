"""CRM services module — Production Ready.

Consolidated modules (as of 2026-04-05):
  cache_query.py   ← cache_manager + query_optimizer
  documents.py     ← document_categorizer + document_upload_service
  notifiers.py     ← birthday_notifier_service + stale_practice_notifier
  enrichment.py    ← birthplace_enrichment_service + conversation_title_generator
                      + ai_crm_extractor
  assignment.py    ← client_identity_resolver + lead_assignment_agent
  automation.py    ← process_automation_service + completed_process_service
                      + waiting_documents_service
  client_core.py   ← validators + audit_trail + enhanced_crm_service

Standalone (unchanged):
  client_service.py, collaborator_service.py, drive_poll_service.py,
  practice_status_listener.py
"""

# ── cache_query ──────────────────────────────────────────────────────────────
# ── assignment ───────────────────────────────────────────────────────────────
from .assignment import (
    ASSIGNABLE_ROLES,
    PRACTICE_DEPARTMENT_MAP,
    ClientIdentityResolver,
    LeadAssignmentState,
    create_lead_assignment_workflow,
    normalize_phone,
    trigger_lead_assignment,
)

# ── automation ───────────────────────────────────────────────────────────────
from .automation import (
    CompletedProcessService,
    ProcessAutomationService,
    WaitingDocumentsService,
)
from .cache_query import (
    CRMCache,
    CRMQueryOptimizer,
    QueryCache,
    cache_crm_result,
    crm_cache,
    health_check_crm_tables,
    invalidate_client_cache,
    invalidate_practice_cache,
    query_cache,
)

# ── client_core (validators + audit_trail + enhanced_crm_service) ────────────
from .client_core import (
    AuditAction,
    ClientValidator,
    CRMAuditor,
    EnhancedCRMService,
    InteractionValidator,
    PracticeValidator,
    extract_entities_from_text,
    get_enhanced_crm_service,
    init_audit_table,
    normalize_phone_e164,
    sanitize_input,
    validate_uuid,
)

# ── standalone ───────────────────────────────────────────────────────────────
from .collaborator_service import CollaboratorProfile, CollaboratorService

# ── documents ────────────────────────────────────────────────────────────────
from .documents import (
    CATEGORIZATION_RULES,
    CATEGORY_TO_FOLDER,
    DocumentUploadService,
    auto_categorize_document,
    auto_categorize_documents_batch,
    get_categorization_stats,
)

# ── enrichment ───────────────────────────────────────────────────────────────
from .enrichment import (
    AICRMExtractor,
    AsyncpgJSONEncoder,
    BirthplaceEnrichmentService,
    generate_conversation_title,
    get_extractor,
    run_birthplace_enrichment_task,
)

# ── notifiers ────────────────────────────────────────────────────────────────
from .notifiers import (
    BIRTHDAY_TEMPLATES,
    NATIONALITY_LANGUAGE_MAP,
    BirthdayNotifierService,
    StalePracticeNotifier,
    run_birthday_notifier_task,
    run_stale_practice_notifier_task,
)

__all__ = [
    # cache_query
    "CRMCache",
    "CRMQueryOptimizer",
    "QueryCache",
    "cache_crm_result",
    "crm_cache",
    "health_check_crm_tables",
    "invalidate_client_cache",
    "invalidate_practice_cache",
    "query_cache",
    # client_core
    "AuditAction",
    "CRMAuditor",
    "ClientValidator",
    "EnhancedCRMService",
    "InteractionValidator",
    "PracticeValidator",
    "extract_entities_from_text",
    "get_enhanced_crm_service",
    "init_audit_table",
    "normalize_phone_e164",
    "sanitize_input",
    "validate_uuid",
    # enrichment
    "AICRMExtractor",
    "AsyncpgJSONEncoder",
    "BirthplaceEnrichmentService",
    "generate_conversation_title",
    "get_extractor",
    "run_birthplace_enrichment_task",
    # notifiers
    "BIRTHDAY_TEMPLATES",
    "NATIONALITY_LANGUAGE_MAP",
    "BirthdayNotifierService",
    "StalePracticeNotifier",
    "run_birthday_notifier_task",
    "run_stale_practice_notifier_task",
    # assignment
    "ASSIGNABLE_ROLES",
    "PRACTICE_DEPARTMENT_MAP",
    "ClientIdentityResolver",
    "LeadAssignmentState",
    "create_lead_assignment_workflow",
    "normalize_phone",
    "trigger_lead_assignment",
    # automation
    "CompletedProcessService",
    "ProcessAutomationService",
    "WaitingDocumentsService",
    # documents
    "CATEGORIZATION_RULES",
    "CATEGORY_TO_FOLDER",
    "DocumentUploadService",
    "auto_categorize_document",
    "auto_categorize_documents_batch",
    "get_categorization_stats",
    # standalone
    "CollaboratorProfile",
    "CollaboratorService",
]
