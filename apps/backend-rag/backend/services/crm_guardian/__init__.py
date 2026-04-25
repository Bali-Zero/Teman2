"""CRM Guardian — autonomous custodian for BALI ZERO/CRM Google Drive.

Maintains invariants over the CRM folder structure (Individual_CRM + Companies_CRM):
    I1  canonical_folder        — every active client has exactly one canonical folder
    I2  template_structure      — every canonical folder has the 14-subfolder template
    I3  satellite_consolidation — files from satellite folders moved to canonical/99_Misc
    I4  orphan_folders          — CRM folders with no DB link get auto-linked or queued
    I5  dead_links              — DB rows pointing to trashed folders are unlinked + reprovisioned
    I6  missing_ocr             — NULL passport_expiry with a passport PDF triggers OCR
    I7  db_duplicates           — report-only (no auto-fix)
    I8  permission_audit        — external/public shares alerted
    I10 summary_l1              — Gemini 3 Pro generates clients.ai_summary JSONB
    I11 summary_l2_markdown     — _AI_BRIEF.md inside canonical folder
    I12 summary_l3_notebooklm   — per-client NotebookLM sync (VIP only)

Invariants are opt-in (default enabled=false, dry_run=true). State lives in
crm_guardian_state. Audit trail lives in crm_guardian_events (append-only).
Global kill switch: system_settings.crm_guardian_enabled.
"""
from .base import (
    GuardianAction,
    GuardianConfig,
    GuardianEvent,
    GuardianRunContext,
    build_drive_service,
    compute_rule,
    Rule,
    record_event,
)

__all__ = [
    "GuardianAction",
    "GuardianConfig",
    "GuardianEvent",
    "GuardianRunContext",
    "Rule",
    "build_drive_service",
    "compute_rule",
    "record_event",
]
