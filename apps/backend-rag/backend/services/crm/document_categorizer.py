"""Backward-compat shim — all symbols moved to documents.py."""
from backend.services.crm.documents import (  # noqa: F401
    CATEGORIZATION_RULES,
    CATEGORY_TO_FOLDER,
    FAMILY_MEMBER_KEYWORDS,
    auto_categorize_document,
    auto_categorize_documents_batch,
    extract_expiry_date,
    extract_person_name,
    get_categorization_stats,
)
