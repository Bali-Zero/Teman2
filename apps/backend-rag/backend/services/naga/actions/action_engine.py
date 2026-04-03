"""Action Engine — deterministic trigger detection from research claims.

Scans verified/contested claims and knowledge gaps to propose concrete
actions (CRM alerts, article drafts, escalations, follow-ups).  No LLM
calls — every rule is a simple keyword/threshold check.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from backend.core.claims.models import ClaimRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ActionItem dataclass
# ---------------------------------------------------------------------------


@dataclass
class ActionItem:
    """A proposed action triggered by a research claim or gap."""

    action_type: str  # notify / crm_alert / draft_article / publish / escalation / followup
    description: str
    payload: dict = field(default_factory=dict)
    rationale: str = ""
    auto_execute: bool = False
    priority: str = "medium"  # low / medium / high / critical

    # Valid action types — kept as class-level constant for validation.
    VALID_TYPES: frozenset[str] = frozenset(
        {
            "notify",
            "crm_alert",
            "draft_article",
            "publish",
            "escalation",
            "followup",
        }
    )

    def __post_init__(self) -> None:
        if self.action_type not in self.VALID_TYPES:
            raise ValueError(
                f"Invalid action_type '{self.action_type}'. "
                f"Must be one of {sorted(self.VALID_TYPES)}"
            )


# ---------------------------------------------------------------------------
# Keyword sets (compiled once at module level)
# ---------------------------------------------------------------------------

_IMPACT_KEYWORDS: frozenset[str] = frozenset(
    {
        "fee",
        "tarif",
        "biaya",
        "cost",
        "deadline",
        "expiry",
        "new requirement",
        "increased",
        "decreased",
        "changed",
        "effective",
        "berlaku",
    }
)

_NEWS_KEYWORDS: frozenset[str] = frozenset(
    {
        "new regulation",
        "new policy",
        "peraturan baru",
        "golden visa",
        "launched",
        "announced",
    }
)

# Pre-compiled pattern for efficient multi-keyword matching.
_IMPACT_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in _IMPACT_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

_NEWS_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in _NEWS_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Indonesia-related keywords for fallback when geographic_scope is absent.
_INDONESIA_KEYWORDS: frozenset[str] = frozenset(
    {"indonesia", "bali", "kitas", "kitap", "pma", "imigrasi", "kemenag"}
)

_INDONESIA_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in _INDONESIA_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Gap keywords that trigger follow-up actions.
_GAP_REGULATION_KEYWORDS: frozenset[str] = frozenset(
    {"regulation", "normativa"}
)


# ---------------------------------------------------------------------------
# Helper predicates
# ---------------------------------------------------------------------------


def _is_indonesia_domain(claim: ClaimRecord) -> bool:
    """Return True if the claim relates to Indonesia."""
    scope = getattr(claim, "geographic_scope", None) or ""
    if scope.upper() in ("NATIONAL", "LOCAL_BALI"):
        return True
    # Fallback: scan claim text for Indonesia keywords.
    return bool(_INDONESIA_PATTERN.search(claim.claim_text))


def _is_verified(claim: ClaimRecord) -> bool:
    return claim.confidence_class.upper() == "VERIFIED"


def _is_low_confidence(claim: ClaimRecord) -> bool:
    return claim.confidence_class.upper() == "LOW"


def _has_impact_keywords(text: str) -> bool:
    return bool(_IMPACT_PATTERN.search(text))


def _has_news_keywords(text: str) -> bool:
    return bool(_NEWS_PATTERN.search(text))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_actions(
    claims: list[ClaimRecord],
    trusted_mode: bool = False,
    gaps: list[str] | None = None,
) -> list[ActionItem]:
    """Detect actionable triggers from a list of research claims.

    Args:
        claims: Verified/provisional/low-confidence claim records.
        trusted_mode: When *True*, ``draft_article`` and ``followup``
            actions are marked ``auto_execute=True``.
        gaps: Optional list of knowledge-gap descriptions.

    Returns:
        Deduplicated list of :class:`ActionItem` objects, ordered by
        priority (critical > high > medium > low).
    """
    actions: list[ActionItem] = []

    for claim in claims:
        # --- Rule 1: Client impact (VERIFIED + indonesia + impact keyword) ---
        if (
            _is_verified(claim)
            and _is_indonesia_domain(claim)
            and _has_impact_keywords(claim.claim_text)
        ):
            actions.append(
                ActionItem(
                    action_type="crm_alert",
                    description=f"Client-impacting change detected: {claim.claim_text[:120]}",
                    payload={"claim_id": claim.claim_id, "category": claim.category},
                    rationale="VERIFIED claim with client-impact keywords in Indonesia domain",
                    auto_execute=False,  # crm_alert: always manual
                    priority="high",
                )
            )
            actions.append(
                ActionItem(
                    action_type="notify",
                    description=f"Notify team of client-impacting change: {claim.claim_text[:120]}",
                    payload={"claim_id": claim.claim_id, "category": claim.category},
                    rationale="VERIFIED claim with client-impact keywords in Indonesia domain",
                    auto_execute=True,  # notify: always auto
                    priority="high",
                )
            )

        # --- Rule 2: Newsworthy (VERIFIED + news keyword) ---
        if _is_verified(claim) and _has_news_keywords(claim.claim_text):
            actions.append(
                ActionItem(
                    action_type="draft_article",
                    description=f"Newsworthy claim for article draft: {claim.claim_text[:120]}",
                    payload={"claim_id": claim.claim_id, "category": claim.category},
                    rationale="VERIFIED claim containing news-trigger keywords",
                    auto_execute=trusted_mode,  # draft_article: trusted_mode
                    priority="medium",
                )
            )

        # --- Rule 3: Contested regulation (LOW + indonesia) ---
        if _is_low_confidence(claim) and _is_indonesia_domain(claim):
            actions.append(
                ActionItem(
                    action_type="escalation",
                    description=f"Low-confidence Indonesia claim needs review: {claim.claim_text[:120]}",
                    payload={"claim_id": claim.claim_id, "confidence_score": claim.confidence_score},
                    rationale="LOW confidence claim in Indonesia domain — requires human review",
                    auto_execute=True,  # escalation: always auto
                    priority="high",
                )
            )

    # --- Rule 4: Critical gap (regulation / normativa in gaps) ---
    for gap in gaps or []:
        gap_lower = gap.lower()
        if any(kw in gap_lower for kw in _GAP_REGULATION_KEYWORDS):
            actions.append(
                ActionItem(
                    action_type="followup",
                    description=f"Knowledge gap requires follow-up research: {gap[:120]}",
                    payload={"gap": gap},
                    rationale="Gap contains regulation/normativa keywords",
                    auto_execute=trusted_mode,  # followup: trusted_mode
                    priority="medium",
                )
            )

    # Sort by priority: critical > high > medium > low
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    actions.sort(key=lambda a: priority_order.get(a.priority, 99))

    logger.info("Action engine detected %d actions from %d claims", len(actions), len(claims))
    return actions
