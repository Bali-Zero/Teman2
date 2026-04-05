"""Backward-compat shim — all symbols moved to cache_query.py."""
from backend.services.crm.cache_query import (  # noqa: F401
    CRMCache,
    QueryCache,
    cache_crm_result,
    crm_cache,
    invalidate_client_cache,
    invalidate_practice_cache,
    query_cache,
)
