"""Backward-compat shim — all symbols moved to cache_query.py."""
from backend.services.crm.cache_query import (  # noqa: F401
    CRMQueryOptimizer,
    health_check_crm_tables,
)
