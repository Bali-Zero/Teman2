"""Backward-compat shim — all symbols moved to assignment.py."""
from backend.services.crm.assignment import (  # noqa: F401
    ClientIdentityResolver,
    normalize_phone,
)
