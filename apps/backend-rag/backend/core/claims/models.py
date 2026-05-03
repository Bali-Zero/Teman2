"""Claim data structures and ontology constants.

This file defines the canonical claim schema shared across Naga and
NLM pipelines. Any change here propagates to all consumers.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Claim categories — 15 canonical types per spec section 3
# ---------------------------------------------------------------------------

CLAIM_CATEGORIES: list[str] = [
    "LEGAL_CHANGE",
    "OPERATIONAL_CHANGE",
    "ENFORCEMENT_ACTION",
    "ENFORCEMENT_PATTERN",
    "POLICY_SIGNAL",
    "PROCEDURAL_STEP",
    "LOCAL_REGULATION",
    "DOCUMENT_REQUIREMENT",
    "FEE_CHANGE",
    "SOURCE_GAP",
    "SOURCE_REGISTRATION",
    "BASELINE_EXISTING",
    "SYSTEM_STATUS",
    "PROCESSING_TIME",
    "ELIGIBILITY_RULE",
]


# ---------------------------------------------------------------------------
# Verification levels — confidence thresholds
# ---------------------------------------------------------------------------


class VerificationLevel:
    """Confidence score thresholds for claim verification status.

    VERIFIED:     score >= 0.75  — high-authority, corroborated, citable
    PROVISIONAL:  0.55 <= score < 0.75 — needs additional confirmation
    LOW:          score < 0.55  — insufficient backing, flag for review
    """

    VERIFIED: float = 0.75
    PROVISIONAL: float = 0.55
    LOW: float = 0.55  # boundary value (anything below PROVISIONAL)


# ---------------------------------------------------------------------------
# ClaimRecord dataclass
# ---------------------------------------------------------------------------


@dataclass
class ClaimRecord:
    """Atomic verifiable claim extracted from a research response.

    Fields mirror the NLM claim registry schema. The ``to_dict`` method
    serialises for JSONL output, omitting falsy values to keep payloads lean.
    """

    claim_id: str
    claim_text: str
    category: str
    confidence_class: str
    confidence_score: float
    source_ids: list[str]
    extracted: str
    status: str = "active"
    geographic_scope: str = "NATIONAL"
    affected_visa_types: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict, omitting falsy values."""
        return {k: v for k, v in asdict(self).items() if v}
