"""Backward-compat shim — all symbols moved to client_core.py."""
from backend.services.crm.client_core import (  # noqa: F401
    ClientValidator,
    InteractionValidator,
    PracticeValidator,
    extract_entities_from_text,
    normalize_phone_e164,
    sanitize_input,
    validate_uuid,
)
