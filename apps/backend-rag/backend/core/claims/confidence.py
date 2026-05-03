"""Confidence scoring for extracted claims.

Implements the 6-factor weighted formula:
    AUTH=0.30, CORR=0.25, SPEC=0.15, TYPE=0.12, RECENCY=0.10, GEO=0.08

This module is intentionally stateless — pure functions only.
"""

from backend.core.claims.models import VerificationLevel

# ---------------------------------------------------------------------------
# Weights per spec section 3
# ---------------------------------------------------------------------------

W_AUTH: float = 0.30
W_CORR: float = 0.25
W_SPEC: float = 0.15
W_TYPE: float = 0.12
W_RECENCY: float = 0.10
W_GEO: float = 0.08

# ---------------------------------------------------------------------------
# Tier authority scores
# ---------------------------------------------------------------------------

TIER_AUTHORITY: dict[int, float] = {
    0: 1.00,
    1: 0.95,
    2: 0.90,
    3: 0.80,
    4: 0.75,
    5: 0.60,
    6: 0.30,
}


def compute_confidence(
    highest_tier: int,
    source_count: int,
    has_specific_pasal: bool,
    is_regulatory: bool,
    days_since_pub: int,
    is_bali_specific: bool,
) -> float:
    """Compute confidence score using the 6-factor weighted formula.

    Args:
        highest_tier: Best (lowest) tier among backing sources (0=T0, 6=T6).
        source_count: Number of distinct sources backing this claim.
        has_specific_pasal: Whether claim cites specific pasal/ayat.
        is_regulatory: Whether claim is about a regulation (vs operational).
        days_since_pub: Days since source publication.
        is_bali_specific: Whether claim is specific to Bali.

    Returns:
        Confidence score clamped to [0.0, 1.0], rounded to 3 decimals.
    """
    # S_auth: authority of best source
    s_auth = TIER_AUTHORITY.get(highest_tier, 0.50)

    # S_corr: corroboration from multiple sources (saturates at 3)
    s_corr = min(1.0, source_count / 3)

    # S_spec: specificity of claim
    s_spec = 1.0 if has_specific_pasal else 0.6

    # S_type: regulatory vs operational
    s_type = 1.0 if is_regulatory else 0.7

    # S_recency: temporal freshness
    if days_since_pub <= 30:
        s_recency = 1.0
    elif days_since_pub <= 180:
        s_recency = 0.8
    elif days_since_pub <= 365:
        s_recency = 0.6
    else:
        s_recency = 0.4

    # S_geo: geographic relevance
    s_geo = 0.9 if is_bali_specific else 1.0

    score = (
        W_AUTH * s_auth
        + W_CORR * s_corr
        + W_SPEC * s_spec
        + W_TYPE * s_type
        + W_RECENCY * s_recency
        + W_GEO * s_geo
    )
    return round(min(1.0, max(0.0, score)), 3)


def classify_confidence(score: float) -> str:
    """Classify a confidence score into a verification level label.

    Returns:
        "VERIFIED" if score >= 0.75,
        "PROVISIONAL" if score >= 0.55,
        "LOW" otherwise.
    """
    if score >= VerificationLevel.VERIFIED:
        return "VERIFIED"
    elif score >= VerificationLevel.PROVISIONAL:
        return "PROVISIONAL"
    else:
        return "LOW"
