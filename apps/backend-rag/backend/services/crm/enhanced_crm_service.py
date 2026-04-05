"""Backward-compat shim — all symbols moved to client_core.py."""
from backend.services.crm.client_core import (  # noqa: F401
    EnhancedCRMService,
    get_enhanced_crm_service,
)
