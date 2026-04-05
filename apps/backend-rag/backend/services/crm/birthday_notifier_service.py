"""Backward-compat shim — all symbols moved to notifiers.py."""
from backend.services.crm.notifiers import (  # noqa: F401
    BIRTHDAY_TEMPLATES,
    NATIONALITY_LANGUAGE_MAP,
    SYSTEM_SENDER_USER_ID,
    BirthdayNotifierService,
    run_birthday_notifier_task,
)
