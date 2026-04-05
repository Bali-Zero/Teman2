"""Backward-compat shim — all symbols moved to client_core.py."""
from backend.services.crm.client_core import (  # noqa: F401
    CREATE_AUDIT_TABLE_SQL,
    AuditAction,
    CRMAuditor,
    init_audit_table,
)
