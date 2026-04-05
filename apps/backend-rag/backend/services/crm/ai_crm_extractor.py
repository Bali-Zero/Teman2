"""Backward-compat shim — all symbols moved to enrichment.py."""
from backend.services.crm.enrichment import (  # noqa: F401
    AICRMExtractor,
    AsyncpgJSONEncoder,
    get_extractor,
)
