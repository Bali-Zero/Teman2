"""
ZANTARA RAG - Services

Service modules are imported directly from their subpackages:
    from backend.services.search.search_service import SearchService
    from backend.services.oracle import OracleService

The previous barrel re-export was removed (2026-03-08) because:
1. Zero consumers — all code imports from subpackages directly
2. It polluted sys.modules during test collection, causing ~150 import failures
3. It imported ALL service dependencies at module load time (slow startup)
"""
