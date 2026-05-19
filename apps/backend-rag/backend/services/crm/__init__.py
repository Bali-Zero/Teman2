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
    # assignment
    "ASSIGNABLE_ROLES",
    # notifiers
    "BIRTHDAY_TEMPLATES",
    # documents
    "CATEGORIZATION_RULES",
    "CATEGORY_TO_FOLDER",
    "NATIONALITY_LANGUAGE_MAP",
    "PRACTICE_DEPARTMENT_MAP",
    # enrichment
    "AICRMExtractor",
    "AsyncpgJSONEncoder",
    # client_core
    "AuditAction",
    "BirthdayNotifierService",
    "BirthplaceEnrichmentService",
    "CRMAuditor",
    # cache_query
    "CRMCache",
    "CRMQueryOptimizer",
    "ClientIdentityResolver",
    "ClientValidator",
    # standalone
    "CollaboratorProfile",
    "CollaboratorService",
    # automation
    "CompletedProcessService",
    "DocumentUploadService",
    "EnhancedCRMService",
    "InteractionValidator",
    "LeadAssignmentState",
    "PracticeValidator",
    "ProcessAutomationService",
    "QueryCache",
    "StalePracticeNotifier",
    "WaitingDocumentsService",
    "auto_categorize_document",
    "auto_categorize_documents_batch",
    "cache_crm_result",
    "create_lead_assignment_workflow",
    "crm_cache",
    "extract_entities_from_text",
    "generate_conversation_title",
    "get_categorization_stats",
    "get_enhanced_crm_service",
    "get_extractor",
    "health_check_crm_tables",
    "init_audit_table",
    "invalidate_client_cache",
    "invalidate_practice_cache",
    "normalize_phone",
    "normalize_phone_e164",
    "query_cache",
    "run_birthday_notifier_task",
    "run_birthplace_enrichment_task",
    "run_stale_practice_notifier_task",
    "sanitize_input",
    "trigger_lead_assignment",
    "validate_uuid",
]
