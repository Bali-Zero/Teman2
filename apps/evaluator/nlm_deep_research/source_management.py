"""Source management for the NLM Deep Research Pipeline.

Implements:
- SVS (Source Value Score): multi-factor scoring to rank source utility
- NHS (Notebook Health Score): aggregate notebook quality metric
- Pre-import filtering (6-gate should_import)
- Lifecycle transitions (promote, archive, emergency_prune)

All scoring formulas use only Python stdlib + math.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Constants — Tier value mapping
# ---------------------------------------------------------------------------

TIER_VALUES: Dict[str, float] = {
    "T0": 1.00,
    "T1": 0.90,
    "T2": 0.80,
    "T3": 0.65,
    "T4": 0.60,
    "T5": 0.50,
    "T6": 0.30,
    "MD": 0.50,
}

# ---------------------------------------------------------------------------
# Constants — SVS weights
# ---------------------------------------------------------------------------

W_TIER: float = 0.25
W_CLAIMS: float = 0.20
W_FRESH: float = 0.20
W_CITE: float = 0.15
W_UNIQUE: float = 0.10
W_BONUS: float = 0.10

# ---------------------------------------------------------------------------
# Constants — SVS classification thresholds
# ---------------------------------------------------------------------------


class SVSClassification(str, Enum):
    """Source Value Score classification bands."""

    ESSENTIAL = "ESSENTIAL"
    VALUABLE = "VALUABLE"
    MARGINAL = "MARGINAL"
    EXPENDABLE = "EXPENDABLE"


SVS_THRESHOLDS: List[Tuple[float, SVSClassification]] = [
    (0.70, SVSClassification.ESSENTIAL),
    (0.45, SVSClassification.VALUABLE),
    (0.25, SVSClassification.MARGINAL),
    (0.00, SVSClassification.EXPENDABLE),
]

# ---------------------------------------------------------------------------
# Constants — NHS classification thresholds
# ---------------------------------------------------------------------------


class NHSClassification(str, Enum):
    """Notebook Health Score classification bands."""

    EXCELLENT = "EXCELLENT"
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


NHS_THRESHOLDS: List[Tuple[float, NHSClassification]] = [
    (0.80, NHSClassification.EXCELLENT),
    (0.60, NHSClassification.NORMAL),
    (0.40, NHSClassification.DEGRADED),
    (0.00, NHSClassification.CRITICAL),
]

# ---------------------------------------------------------------------------
# Constants — Staleness half-lives (days) by source type
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    """Recognised source types for staleness decay calculation."""

    LAW_IN_FORCE = "LAW_IN_FORCE"
    REGULATION = "REGULATION"
    OPERATIONAL = "OPERATIONAL"
    NEWS = "NEWS"
    KNOWLEDGE_DOC = "KNOWLEDGE_DOC"


HALF_LIFE_DAYS: Dict[SourceType, float] = {
    SourceType.LAW_IN_FORCE: 99999.0,
    SourceType.REGULATION: 365.0,
    SourceType.OPERATIONAL: 90.0,
    SourceType.NEWS: 15.0,
    SourceType.KNOWLEDGE_DOC: 180.0,
}

# ---------------------------------------------------------------------------
# Constants — Lifecycle stages
# ---------------------------------------------------------------------------


class LifecycleStage(str, Enum):
    """Source lifecycle stages."""

    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    ARCHIVE = "ARCHIVE"


# ---------------------------------------------------------------------------
# Constants — Pre-import filter
# ---------------------------------------------------------------------------

DOMAIN_DENYLIST: List[str] = [
    "tripadvisor.com",
    "expat.com/forum",
    "kaskus.co.id",
    "nomadicmatt.com",
    "reddit.com",
    "quora.com",
    "medium.com/@",
    "youtube.com",
    "tiktok.com",
    "pinterest.com",
    "booking.com",
    "agoda.com",
    "skyscanner.com",
    "lonelyplanet.com",
    "thepointsguy.com",
    "balizero.com",
]

VALID_SOURCE_TYPES: Set[str] = {
    "news",
    "regulation",
    "guide",
    "institutional_announcement",
    "knowledge_doc",
}

ALLOWED_LANGUAGES: Set[str] = {"id", "en"}

MAX_AGE_DAYS_DEFAULT: int = 60

CANONICAL_TIERS: Set[str] = {"T0", "T1"}

DEFAULT_WEEKLY_BUDGET: int = 20

# ---------------------------------------------------------------------------
# NHS weights
# ---------------------------------------------------------------------------

NHS_W_CAPACITY: float = 0.20
NHS_W_FRESHNESS: float = 0.25
NHS_W_QUALITY: float = 0.25
NHS_W_COVERAGE: float = 0.15
NHS_W_DEDUP: float = 0.15


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SourceDates:
    """Temporal metadata for a source."""

    published: Optional[datetime] = None
    ingested: Optional[datetime] = None
    promoted: Optional[datetime] = None
    last_reviewed: Optional[datetime] = None
    last_confirmed_valid: Optional[datetime] = None


@dataclass
class SourceScores:
    """Computed score breakdown for a source."""

    svs_total: float = 0.0
    svs_classification: SVSClassification = SVSClassification.EXPENDABLE
    times_cited: int = 0
    svs_breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class SourceFlags:
    """Operational flags for a source."""

    pinned: bool = False
    enforcement_divergence: bool = False
    manual_review_needed: bool = False


@dataclass
class SourceDedup:
    """Deduplication metadata."""

    url_hash: Optional[str] = None
    title_normalized: str = ""
    known_duplicates: List[str] = field(default_factory=list)


@dataclass
class Source:
    """A single source tracked by the NLM Deep Research Pipeline."""

    nlm_source_id: str
    stage: LifecycleStage
    category: str
    source_type: SourceType
    title: str
    url: Optional[str]
    language: str
    tier: int
    tier_label: str
    dates: SourceDates
    scores: SourceScores
    claims: List[str] = field(default_factory=list)
    dedup: SourceDedup = field(default_factory=SourceDedup)
    flags: SourceFlags = field(default_factory=SourceFlags)


@dataclass
class NotebookHealthInput:
    """Aggregated inputs for computing Notebook Health Score."""

    active_count: int
    sources: List[Source]
    clusters_with_claims: int
    categories_with_claims: int
    duplicates_found_this_week: int
    sources_evaluated_this_week: int


@dataclass
class NotebookHealthResult:
    """Result of NHS computation."""

    nhs_total: float
    nhs_classification: NHSClassification
    h_capacity: float
    h_freshness: float
    h_quality: float
    h_coverage: float
    h_dedup: float


# ---------------------------------------------------------------------------
# SVS — Source Value Score
# ---------------------------------------------------------------------------


def _resolve_tier_label(tier: int, tier_label: str) -> str:
    """Resolve the tier label to a key in TIER_VALUES.

    Falls back to tier_label prefix (e.g. 'T2_REGIONAL' -> 'T2'),
    then to 'T{tier}', then 'MD'.
    """
    # Direct match
    if tier_label in TIER_VALUES:
        return tier_label

    # Try prefix (e.g. 'T2_REGIONAL' -> 'T2')
    prefix = tier_label.split("_")[0] if "_" in tier_label else tier_label
    if prefix in TIER_VALUES:
        return prefix

    # Try numeric tier
    key = f"T{tier}"
    if key in TIER_VALUES:
        return key

    return "MD"


def compute_staleness(
    source_type: SourceType,
    days_since_published: Optional[float],
    days_since_confirmed: Optional[float],
) -> float:
    """Compute the staleness score using exponential decay.

    staleness = 1 - exp(-t_effective / half_life)

    Args:
        source_type: Determines the half-life for decay.
        days_since_published: Days since the source was published.
        days_since_confirmed: Days since the source was last confirmed valid.

    Returns:
        Staleness score in [0, 1]. 0 = perfectly fresh, 1 = fully stale.
    """
    half_life = HALF_LIFE_DAYS.get(source_type, 180.0)

    candidates: List[float] = []
    if days_since_published is not None and days_since_published >= 0:
        candidates.append(days_since_published)
    if days_since_confirmed is not None and days_since_confirmed >= 0:
        candidates.append(days_since_confirmed)

    if not candidates:
        # No temporal data — assume moderately stale
        return 0.5

    t_effective = min(candidates)
    return 1.0 - math.exp(-t_effective / half_life)


def _days_between(earlier: Optional[datetime], later: datetime) -> Optional[float]:
    """Return days between two datetimes, or None if earlier is None."""
    if earlier is None:
        return None
    delta = later - earlier
    return max(0.0, delta.total_seconds() / 86400.0)


def compute_svs(
    source: Source,
    now: Optional[datetime] = None,
) -> SourceScores:
    """Compute the Source Value Score for a single source.

    SVS = w_tier * V_tier
        + w_claims * V_claims
        + w_fresh * (1 - staleness)
        + w_cite * V_citations
        + w_unique * V_uniqueness
        + w_bonus * bonus

    Args:
        source: The source to score.
        now: Reference time for freshness calculation. Defaults to UTC now.

    Returns:
        Updated SourceScores with total, classification, and full breakdown.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # V_tier
    tier_key = _resolve_tier_label(source.tier, source.tier_label)
    v_tier = TIER_VALUES.get(tier_key, 0.50)

    # V_claims
    claims_count = len(source.claims)
    v_claims = min(1.0, claims_count / 3.0)

    # Staleness
    days_pub = _days_between(source.dates.published, now)
    days_conf = _days_between(source.dates.last_confirmed_valid, now)
    staleness = compute_staleness(source.source_type, days_pub, days_conf)

    # V_citations
    times_cited = source.scores.times_cited
    v_citations = min(1.0, times_cited / 5.0)

    # V_uniqueness — requires at least one unique claim
    unique_claims = _count_unique_claims(source)
    v_uniqueness = 1.0 if unique_claims > 0 else 0.5

    # Bonus — pinned or enforcement_divergence flagged sources get the bonus
    bonus = 0.0
    if source.flags.pinned:
        bonus = 1.0
    elif source.flags.enforcement_divergence:
        bonus = 0.5

    # Composite SVS
    svs_total = (
        W_TIER * v_tier
        + W_CLAIMS * v_claims
        + W_FRESH * (1.0 - staleness)
        + W_CITE * v_citations
        + W_UNIQUE * v_uniqueness
        + W_BONUS * bonus
    )

    # Clamp to [0, 1]
    svs_total = max(0.0, min(1.0, svs_total))

    classification = classify_svs(svs_total)

    t_effective_val = None
    if days_pub is not None or days_conf is not None:
        candidates = [d for d in [days_pub, days_conf] if d is not None]
        t_effective_val = min(candidates) if candidates else None

    breakdown: Dict[str, Any] = {
        "v_tier": round(v_tier, 3),
        "v_claims": round(v_claims, 3),
        "staleness": round(staleness, 3),
        "v_citations": round(v_citations, 3),
        "v_uniqueness": round(v_uniqueness, 3),
        "bonus": round(bonus, 3),
        "days_old": round(days_pub, 1) if days_pub is not None else None,
        "claims_count": claims_count,
        "unique_claims": unique_claims,
        "times_cited": times_cited,
        "t_effective": round(t_effective_val, 1) if t_effective_val is not None else None,
    }

    return SourceScores(
        svs_total=round(svs_total, 3),
        svs_classification=classification,
        times_cited=times_cited,
        svs_breakdown=breakdown,
    )


def _count_unique_claims(source: Source) -> int:
    """Count claims that are unique to this source.

    A claim is considered unique if the source has claims listed.
    The actual cross-source dedup happens at the pipeline level;
    here we use the claim list length as a proxy — sources with
    claims have contributed unique verifiable facts.
    """
    return len(source.claims)


def classify_svs(svs_total: float) -> SVSClassification:
    """Classify a raw SVS score into a named band.

    Args:
        svs_total: The computed SVS score in [0, 1].

    Returns:
        The classification band.
    """
    for threshold, classification in SVS_THRESHOLDS:
        if svs_total >= threshold:
            return classification
    return SVSClassification.EXPENDABLE


# ---------------------------------------------------------------------------
# NHS — Notebook Health Score
# ---------------------------------------------------------------------------


def compute_nhs(
    health_input: NotebookHealthInput,
    now: Optional[datetime] = None,
) -> NotebookHealthResult:
    """Compute the Notebook Health Score.

    NHS = 0.20*H_capacity + 0.25*H_freshness + 0.25*H_quality
        + 0.15*H_coverage + 0.15*H_dedup

    Args:
        health_input: Aggregated notebook metrics.
        now: Reference time for freshness. Defaults to UTC now.

    Returns:
        NotebookHealthResult with total, classification, and component scores.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    h_capacity = _compute_h_capacity(health_input.active_count)
    h_freshness = _compute_h_freshness(health_input.sources, now)
    h_quality = _compute_h_quality(health_input.sources, now)
    h_coverage = _compute_h_coverage(
        health_input.clusters_with_claims,
        health_input.categories_with_claims,
    )
    h_dedup = _compute_h_dedup(
        health_input.duplicates_found_this_week,
        health_input.sources_evaluated_this_week,
    )

    nhs_total = (
        NHS_W_CAPACITY * h_capacity
        + NHS_W_FRESHNESS * h_freshness
        + NHS_W_QUALITY * h_quality
        + NHS_W_COVERAGE * h_coverage
        + NHS_W_DEDUP * h_dedup
    )
    nhs_total = max(0.0, min(1.0, nhs_total))

    classification = classify_nhs(nhs_total)

    return NotebookHealthResult(
        nhs_total=round(nhs_total, 3),
        nhs_classification=classification,
        h_capacity=round(h_capacity, 3),
        h_freshness=round(h_freshness, 3),
        h_quality=round(h_quality, 3),
        h_coverage=round(h_coverage, 3),
        h_dedup=round(h_dedup, 3),
    )


def _compute_h_capacity(active_count: int) -> float:
    """Capacity health: peaks at 55 sources, degrades above 70.

    H_capacity = min(1.0, active_count / 55) if active_count <= 70
                 else max(0, 1.0 - (active_count - 70) / 30)
    """
    if active_count <= 70:
        return min(1.0, active_count / 55.0)
    return max(0.0, 1.0 - (active_count - 70) / 30.0)


def _compute_h_freshness(
    sources: List[Source],
    now: datetime,
) -> float:
    """Average freshness (1 - staleness) across all active sources."""
    active = [s for s in sources if s.stage == LifecycleStage.ACTIVE]
    if not active:
        return 0.0

    total_freshness = 0.0
    for src in active:
        days_pub = _days_between(src.dates.published, now)
        days_conf = _days_between(src.dates.last_confirmed_valid, now)
        staleness = compute_staleness(src.source_type, days_pub, days_conf)
        total_freshness += 1.0 - staleness
    return total_freshness / len(active)


def _compute_h_quality(
    sources: List[Source],
    now: datetime,
) -> float:
    """Average SVS across all active sources."""
    active = [s for s in sources if s.stage == LifecycleStage.ACTIVE]
    if not active:
        return 0.0

    total_svs = 0.0
    for src in active:
        scores = compute_svs(src, now=now)
        total_svs += scores.svs_total
    return total_svs / len(active)


def _compute_h_coverage(
    clusters_with_claims: int,
    categories_with_claims: int,
) -> float:
    """Coverage across topic clusters and categories.

    H_coverage = (clusters_with_claims/5 + categories_with_claims/10) / 2
    """
    cluster_ratio = min(1.0, clusters_with_claims / 5.0)
    category_ratio = min(1.0, categories_with_claims / 10.0)
    return (cluster_ratio + category_ratio) / 2.0


def _compute_h_dedup(
    duplicates_found_this_week: int,
    sources_evaluated_this_week: int,
) -> float:
    """Deduplication health.

    H_dedup = 1.0 - (duplicates_found_this_week / max(1, sources_evaluated_this_week))
    """
    denominator = max(1, sources_evaluated_this_week)
    return 1.0 - (duplicates_found_this_week / denominator)


def classify_nhs(nhs_total: float) -> NHSClassification:
    """Classify a raw NHS score into a named band.

    Args:
        nhs_total: The computed NHS score in [0, 1].

    Returns:
        The classification band.
    """
    for threshold, classification in NHS_THRESHOLDS:
        if nhs_total >= threshold:
            return classification
    return NHSClassification.CRITICAL


# ---------------------------------------------------------------------------
# Pre-import filter — should_import
# ---------------------------------------------------------------------------


def _normalize_url(url: str) -> str:
    """Normalize a URL for dedup comparison.

    Strips scheme, www prefix, trailing slashes, and query parameters.
    """
    cleaned = re.sub(r"^https?://", "", url)
    cleaned = re.sub(r"^www\.", "", cleaned)
    cleaned = cleaned.split("?")[0].split("#")[0]
    return cleaned.rstrip("/").lower()


def _url_hash(url: str) -> str:
    """Compute a SHA-256 hash of the normalized URL."""
    normalized = _normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _is_domain_denied(url: str) -> bool:
    """Check if a URL matches any entry in the domain denylist."""
    normalized = _normalize_url(url)
    for domain in DOMAIN_DENYLIST:
        if domain in normalized:
            return True
    return False


def _is_url_duplicate(
    url: str,
    existing_sources: List[Source],
) -> bool:
    """Check if a URL already exists among tracked sources."""
    candidate_hash = _url_hash(url)
    for src in existing_sources:
        if src.url is not None:
            if src.dedup.url_hash == candidate_hash:
                return True
            if _url_hash(src.url) == candidate_hash:
                return True
    return False


def should_import(
    url: Optional[str],
    source_type: str,
    language: str,
    publication_date: Optional[datetime],
    tier_label: str,
    existing_sources: List[Source],
    weekly_imports_used: int = 0,
    weekly_budget: int = DEFAULT_WEEKLY_BUDGET,
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """Six-gate pre-import filter. ALL gates must pass.

    Gates:
        1. Domain denylist check (URL not on blocked domains)
        2. URL dedup (not already tracked)
        3. Source type valid
        4. Publication date within 60 days (or any date for T0-T1 canonical)
        5. Language: id or en only
        6. Budget pressure: not at weekly budget limit

    Args:
        url: The candidate source URL. May be None for file-based sources.
        source_type: Type string (e.g. 'news', 'regulation').
        language: ISO language code.
        publication_date: When the source was published.
        tier_label: The tier label (e.g. 'T0', 'T1', 'T2_REGIONAL').
        existing_sources: Currently tracked sources for dedup.
        weekly_imports_used: How many imports have been done this week.
        weekly_budget: Maximum weekly import budget.
        now: Reference time. Defaults to UTC now.

    Returns:
        Tuple of (pass: bool, reason: str). If pass is True, reason is 'OK'.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Gate 1: Domain denylist
    if url is not None and _is_domain_denied(url):
        return False, f"DENIED: URL matches domain denylist"

    # Gate 2: URL dedup
    if url is not None and _is_url_duplicate(url, existing_sources):
        return False, "DENIED: URL already tracked (duplicate)"

    # Gate 3: Source type valid
    if source_type not in VALID_SOURCE_TYPES:
        return False, f"DENIED: Invalid source type '{source_type}'. Valid: {sorted(VALID_SOURCE_TYPES)}"

    # Gate 4: Publication date within MAX_AGE_DAYS_DEFAULT days
    # Exception: T0 and T1 canonical sources bypass the date gate
    tier_prefix = tier_label.split("_")[0] if "_" in tier_label else tier_label
    is_canonical_tier = tier_prefix in CANONICAL_TIERS

    if not is_canonical_tier:
        if publication_date is None:
            return False, "DENIED: No publication date provided (required for non-canonical tiers)"
        days_old = (now - publication_date).total_seconds() / 86400.0
        if days_old > MAX_AGE_DAYS_DEFAULT:
            return False, (
                f"DENIED: Publication date is {days_old:.0f} days old "
                f"(max {MAX_AGE_DAYS_DEFAULT} for non-canonical sources)"
            )

    # Gate 5: Language
    if language not in ALLOWED_LANGUAGES:
        return False, f"DENIED: Language '{language}' not allowed. Allowed: {sorted(ALLOWED_LANGUAGES)}"

    # Gate 6: Budget pressure
    if weekly_imports_used >= weekly_budget:
        return False, (
            f"DENIED: Weekly import budget exhausted "
            f"({weekly_imports_used}/{weekly_budget})"
        )

    return True, "OK"


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


def promote_to_active(
    source: Source,
    now: Optional[datetime] = None,
) -> Source:
    """Promote a source to the ACTIVE lifecycle stage.

    Sets stage to ACTIVE and records the promotion timestamp.

    Args:
        source: The source to promote.
        now: Timestamp for the promotion. Defaults to UTC now.

    Returns:
        The mutated source (same object, updated in place).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    source.stage = LifecycleStage.ACTIVE
    source.dates.promoted = now
    return source


def archive_source(
    source: Source,
    now: Optional[datetime] = None,
) -> Source:
    """Archive a source, removing it from the active set.

    Sets stage to ARCHIVE and records the review timestamp.

    Args:
        source: The source to archive.
        now: Timestamp for the archival. Defaults to UTC now.

    Returns:
        The mutated source (same object, updated in place).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    source.stage = LifecycleStage.ARCHIVE
    source.dates.last_reviewed = now
    return source


def emergency_prune(
    sources: List[Source],
    target_count: int,
    now: Optional[datetime] = None,
) -> Tuple[List[Source], List[Source]]:
    """Emergency prune to reduce active sources to target_count.

    Removes the lowest-SVS non-pinned active sources until the active
    count reaches target_count. Pinned sources are never pruned.

    Args:
        sources: The full list of sources (all stages).
        target_count: Desired maximum number of active sources.
        now: Reference time for SVS computation. Defaults to UTC now.

    Returns:
        Tuple of (kept: List[Source], pruned: List[Source]).
        Pruned sources have their stage set to ARCHIVE.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    active = [s for s in sources if s.stage == LifecycleStage.ACTIVE]
    non_active = [s for s in sources if s.stage != LifecycleStage.ACTIVE]

    if len(active) <= target_count:
        return sources, []

    # Separate pinned from prunable
    pinned: List[Source] = []
    prunable: List[Source] = []
    for src in active:
        if src.flags.pinned:
            pinned.append(src)
        else:
            prunable.append(src)

    # Sort prunable by SVS ascending (lowest first = pruned first)
    scored_prunable: List[Tuple[float, Source]] = []
    for src in prunable:
        scores = compute_svs(src, now=now)
        scored_prunable.append((scores.svs_total, src))
    scored_prunable.sort(key=lambda x: x[0])

    # How many do we need to remove?
    excess = len(active) - target_count
    to_prune_count = min(excess, len(scored_prunable))

    pruned_sources: List[Source] = []
    kept_prunable: List[Source] = []

    for i, (_, src) in enumerate(scored_prunable):
        if i < to_prune_count:
            archive_source(src, now=now)
            pruned_sources.append(src)
        else:
            kept_prunable.append(src)

    kept = non_active + pinned + kept_prunable
    return kept, pruned_sources


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------


def recompute_all_svs(
    sources: List[Source],
    now: Optional[datetime] = None,
) -> List[Source]:
    """Recompute SVS for all sources, updating their scores in place.

    Args:
        sources: List of sources to score.
        now: Reference time. Defaults to UTC now.

    Returns:
        The same list with updated scores.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    for src in sources:
        src.scores = compute_svs(src, now=now)
    return sources


def normalize_title(title: str) -> str:
    """Normalize a title for dedup comparison.

    Lowercases, strips non-alphanumeric characters, collapses whitespace.

    Args:
        title: Raw title string.

    Returns:
        Normalized title suitable for fuzzy dedup matching.
    """
    cleaned = title.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def find_title_duplicates(
    candidate_title: str,
    existing_sources: List[Source],
) -> List[Source]:
    """Find sources with matching normalized titles.

    Args:
        candidate_title: The title to check.
        existing_sources: Currently tracked sources.

    Returns:
        List of sources whose normalized title matches the candidate.
    """
    normalized = normalize_title(candidate_title)
    duplicates: List[Source] = []
    for src in existing_sources:
        existing_normalized = src.dedup.title_normalized or normalize_title(src.title)
        if existing_normalized == normalized:
            duplicates.append(src)
    return duplicates
