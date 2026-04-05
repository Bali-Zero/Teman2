"""Backward-compat shim — all symbols moved to notifiers.py."""
from backend.services.crm.notifiers import (  # noqa: F401
    ACTIVE_STATUSES,
    ADMIN_EMAIL,
    CRM_PRACTICE_URL,
    STALE_DAYS,
    StalePracticeNotifier,
    run_stale_practice_notifier_task,
)
