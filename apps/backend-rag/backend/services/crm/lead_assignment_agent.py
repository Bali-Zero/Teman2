"""Backward-compat shim — all symbols moved to assignment.py."""
from backend.services.crm.assignment import (  # noqa: F401
    ASSIGNABLE_ROLES,
    PRACTICE_DEPARTMENT_MAP,
    LeadAssignmentState,
    assign_lead,
    check_duplicates,
    create_lead_assignment_workflow,
    send_telegram_notification,
    trigger_lead_assignment,
)
