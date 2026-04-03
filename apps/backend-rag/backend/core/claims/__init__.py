"""Shared claims library — canonical ontology for claim extraction and scoring.

This module is the single source of truth for claim data structures,
confidence scoring, and extraction logic. Both the Naga research engine
and the NLM Deep Research pipeline consume this library to prevent
split-brain divergence in confidence scoring.

Public API:
    ClaimRecord         — Atomic verifiable claim dataclass
    CLAIM_CATEGORIES    — 15 canonical claim categories
    VerificationLevel   — Confidence threshold constants
    compute_confidence  — 6-factor weighted confidence formula
    classify_confidence — Map score to VERIFIED/PROVISIONAL/LOW
    extract_claims_from_response — Paragraph-based claim extraction
"""

from backend.core.claims.confidence import classify_confidence, compute_confidence
from backend.core.claims.extractor import extract_claims_from_response
from backend.core.claims.models import CLAIM_CATEGORIES, ClaimRecord, VerificationLevel

__all__ = [
    "CLAIM_CATEGORIES",
    "ClaimRecord",
    "VerificationLevel",
    "classify_confidence",
    "compute_confidence",
    "extract_claims_from_response",
]
