"""Backward-compat shim — all symbols moved to enrichment.py."""
from backend.services.crm.enrichment import (  # noqa: F401
    BATCH_SIZE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    BirthplaceEnrichmentService,
    run_birthplace_enrichment_task,
)
