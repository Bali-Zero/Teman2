"""
Intel Quality Gate — 4-dimension scoring for intel pipeline.

Evaluates articles on:
  1. Relevance  — how relevant to Bali Zero clients (visa, tax, company, property)
  2. Urgency    — breaking news vs background info, time-decay
  3. Reliability — source tier + SVS + cross-reference signals
  4. Business Impact — estimated client overlap from CRM service categories

Pure scoring functions: input → score (0.0–1.0), zero side effects.
Config loaded from config/quality_gate.yaml.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "quality_gate.yaml"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityGateConfig:
    """Loaded from quality_gate.yaml. All weights and thresholds."""

    # Dimension weights (must sum to 1.0)
    w_relevance: float = 0.35
    w_urgency: float = 0.20
    w_reliability: float = 0.20
    w_business_impact: float = 0.25

    # Thresholds
    threshold_auto_publish: float = 0.70
    threshold_review: float = 0.40
    # Below threshold_review → archive

    # Relevance config
    topic_keywords: dict[str, list[str]] = field(default_factory=dict)
    topic_weights: dict[str, float] = field(default_factory=dict)

    # Urgency config
    urgency_keywords: list[str] = field(default_factory=list)
    freshness_half_life_hours: float = 48.0

    # Reliability config
    source_tiers: dict[str, str] = field(default_factory=dict)  # domain → T1/T2/T3
    tier_scores: dict[str, float] = field(default_factory=lambda: {
        "T1": 1.0, "T2": 0.70, "T3": 0.40
    })

    # Business Impact config
    service_category_map: dict[str, list[str]] = field(default_factory=dict)
    # Maps topic → CRM service categories that overlap
    # e.g. "visa" → ["KITAS", "KITAP", "B211", "C31"]

    @classmethod
    def load(cls, path: Path | None = None) -> QualityGateConfig:
        """Load config from YAML. Falls back to defaults if file missing."""
        p = path or CONFIG_PATH
        if not p.exists():
            logger.warning("quality_gate.yaml not found at %s — using defaults", p)
            return cls()

        raw = yaml.safe_load(p.read_text()) or {}

        weights = raw.get("weights", {})
        thresholds = raw.get("thresholds", {})
        relevance = raw.get("relevance", {})
        urgency_cfg = raw.get("urgency", {})
        reliability = raw.get("reliability", {})
        impact = raw.get("business_impact", {})

        return cls(
            w_relevance=weights.get("relevance", 0.35),
            w_urgency=weights.get("urgency", 0.20),
            w_reliability=weights.get("reliability", 0.20),
            w_business_impact=weights.get("business_impact", 0.25),
            threshold_auto_publish=thresholds.get("auto_publish", 0.70),
            threshold_review=thresholds.get("review", 0.40),
            topic_keywords=relevance.get("topic_keywords", {}),
            topic_weights=relevance.get("topic_weights", {}),
            urgency_keywords=urgency_cfg.get("keywords", []),
            freshness_half_life_hours=urgency_cfg.get("freshness_half_life_hours", 48.0),
            source_tiers=reliability.get("source_tiers", {}),
            tier_scores=reliability.get("tier_scores", {"T1": 1.0, "T2": 0.70, "T3": 0.40}),
            service_category_map=impact.get("service_category_map", {}),
        )


# ---------------------------------------------------------------------------
# Routing enum
# ---------------------------------------------------------------------------


class GateDecision(str, Enum):
    AUTO_PUBLISH = "auto_publish"  # ≥ threshold_auto_publish
    REVIEW = "review"              # ≥ threshold_review
    ARCHIVE = "archive"            # below threshold_review


# ---------------------------------------------------------------------------
# Score result
# ---------------------------------------------------------------------------


@dataclass
class QualityGateResult:
    """Result of quality gate evaluation."""

    relevance: float        # 0.0–1.0
    urgency: float          # 0.0–1.0
    reliability: float      # 0.0–1.0
    business_impact: float  # 0.0–1.0
    composite: float        # weighted average 0.0–1.0
    decision: GateDecision
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relevance": round(self.relevance, 3),
            "urgency": round(self.urgency, 3),
            "reliability": round(self.reliability, 3),
            "business_impact": round(self.business_impact, 3),
            "composite": round(self.composite, 3),
            "decision": self.decision.value,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Dimension 1 — Relevance (0.0–1.0)
# ---------------------------------------------------------------------------


def _keyword_in_text(keyword: str, text: str) -> bool:
    """Match keyword in text. Short keywords (≤4 chars) use word boundaries to avoid
    false positives like 'oss' matching 'gossip'. Longer keywords use substring match."""
    if len(keyword) <= 4:
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))
    return keyword in text


def score_relevance(
    title: str,
    content: str,
    category: str,
    config: QualityGateConfig,
) -> tuple[float, dict[str, Any]]:
    """Score how relevant the article is for Bali Zero clients.

    Combines topic keyword matching + keyword density + category alignment.
    Pure function: (text, config) → (score, details).
    """
    text = (title + " " + content).lower()
    word_count = max(len(text.split()), 1)

    topic_scores: dict[str, float] = {}
    total_hits = 0

    for topic, keywords in config.topic_keywords.items():
        hits = sum(1 for kw in keywords if _keyword_in_text(kw.lower(), text))
        topic_weight = config.topic_weights.get(topic, 1.0)
        # Normalize: cap at 5 hits per topic for diminishing returns
        normalized = min(hits / 5.0, 1.0) * topic_weight
        topic_scores[topic] = round(normalized, 3)
        total_hits += hits

    # Keyword density bonus (more hits in shorter text = more focused)
    density = min(total_hits / (word_count / 100), 1.0) if word_count > 0 else 0.0

    # Category alignment: if article category matches a known high-value topic
    category_bonus = 0.0
    cat_lower = category.lower()
    if cat_lower in config.topic_keywords:
        category_bonus = 0.15

    # Aggregate: best topic score (60%) + density (25%) + category bonus (15%)
    best_topic = max(topic_scores.values()) if topic_scores else 0.0
    raw = best_topic * 0.60 + density * 0.25 + category_bonus

    score = max(0.0, min(1.0, raw))
    details = {
        "topic_scores": topic_scores,
        "keyword_hits": total_hits,
        "density": round(density, 3),
        "category_bonus": category_bonus,
        "best_topic": max(topic_scores, key=topic_scores.get) if topic_scores else None,
    }
    return score, details


# ---------------------------------------------------------------------------
# Dimension 2 — Urgency (0.0–1.0)
# ---------------------------------------------------------------------------


def score_urgency(
    title: str,
    content: str,
    published_at: datetime | None,
    scraped_at: datetime | None,
    config: QualityGateConfig,
) -> tuple[float, dict[str, Any]]:
    """Score urgency based on time freshness + urgency keyword signals.

    Pure function: (text, timestamps, config) → (score, details).
    """
    text = (title + " " + content).lower()

    # Urgency keyword signals (0.0–1.0)
    urgency_hits = sum(1 for kw in config.urgency_keywords if kw.lower() in text)
    keyword_signal = min(urgency_hits / 3.0, 1.0)

    # Time freshness: exponential decay with configurable half-life
    ref_time = published_at or scraped_at or datetime.now(timezone.utc)
    if ref_time.tzinfo is None:
        ref_time = ref_time.replace(tzinfo=timezone.utc)

    age_hours = (datetime.now(timezone.utc) - ref_time).total_seconds() / 3600
    half_life = config.freshness_half_life_hours
    freshness = math.exp(-math.log(2) * age_hours / half_life) if half_life > 0 else 0.0

    # Breaking news detection: if title contains urgency keywords → boost
    title_lower = title.lower()
    title_urgency = any(kw.lower() in title_lower for kw in config.urgency_keywords)
    title_boost = 0.15 if title_urgency else 0.0

    # Composite: freshness (50%) + keyword signal (35%) + title boost (15%)
    raw = freshness * 0.50 + keyword_signal * 0.35 + title_boost

    score = max(0.0, min(1.0, raw))
    details = {
        "age_hours": round(age_hours, 1),
        "freshness": round(freshness, 3),
        "urgency_keyword_hits": urgency_hits,
        "keyword_signal": round(keyword_signal, 3),
        "title_urgency": title_urgency,
    }
    return score, details


# ---------------------------------------------------------------------------
# Dimension 3 — Reliability (0.0–1.0)
# ---------------------------------------------------------------------------


def score_reliability(
    source_name: str,
    source_url: str,
    tier: str,
    svs_score: float | None,
    config: QualityGateConfig,
) -> tuple[float, dict[str, Any]]:
    """Score reliability from source reputation + existing SVS.

    Pure function: (source metadata, config) → (score, details).
    """
    # Source tier score
    # Try exact domain match first, then tier field from article
    from urllib.parse import urlparse

    try:
        domain = urlparse(source_url).hostname or ""
    except Exception:
        domain = ""

    resolved_tier = config.source_tiers.get(domain, tier.upper() if tier else "T3")
    tier_score = config.tier_scores.get(resolved_tier, 0.40)

    # SVS integration: use existing SVS if available
    svs = svs_score if svs_score is not None else 0.50

    # Cross-reference signal: government domains get a boost
    gov_boost = 0.0
    if domain.endswith(".go.id") or domain.endswith(".gov.id"):
        gov_boost = 0.10

    # Composite: tier (45%) + SVS (40%) + gov_boost (15%)
    raw = tier_score * 0.45 + svs * 0.40 + gov_boost

    score = max(0.0, min(1.0, raw))
    details = {
        "domain": domain,
        "resolved_tier": resolved_tier,
        "tier_score": tier_score,
        "svs_score": svs,
        "gov_boost": gov_boost,
    }
    return score, details


# ---------------------------------------------------------------------------
# Dimension 4 — Business Impact (0.0–1.0)
# ---------------------------------------------------------------------------

# Default CRM service distribution for Bali Zero
# Estimated % of active clients per service category
# Updated periodically from CRM stats — see get_crm_service_distribution()
_DEFAULT_CLIENT_DISTRIBUTION: dict[str, float] = {
    "visa": 0.45,        # ~45% of clients have visa services
    "company": 0.30,     # ~30% company setup/maintenance
    "tax": 0.20,         # ~20% tax compliance
    "property": 0.10,    # ~10% property transactions
    "immigration": 0.45, # overlaps with visa
    "work_permit": 0.15, # subset of visa
    "investment": 0.12,  # subset of company
}


def score_business_impact(
    title: str,
    content: str,
    category: str,
    config: QualityGateConfig,
    client_distribution: dict[str, float] | None = None,
) -> tuple[float, dict[str, Any]]:
    """Score how many Bali Zero clients are impacted.

    Cross-references article topics with CRM service categories.
    Pure function: (text, config, distribution) → (score, details).
    """
    text = (title + " " + content).lower()
    dist = client_distribution or _DEFAULT_CLIENT_DISTRIBUTION

    # Find which service categories this article touches
    matched_services: dict[str, float] = {}

    for topic, service_keywords in config.service_category_map.items():
        # Check if article text mentions service-related keywords
        for svc_kw in service_keywords:
            if _keyword_in_text(svc_kw.lower(), text):
                # Map to client distribution
                overlap = dist.get(topic, 0.05)
                if topic not in matched_services or overlap > matched_services[topic]:
                    matched_services[topic] = overlap

    # Category direct match
    cat_lower = category.lower()
    if cat_lower in dist and cat_lower not in matched_services:
        matched_services[cat_lower] = dist[cat_lower]

    if not matched_services:
        # No match → minimal impact
        return 0.10, {"matched_services": {}, "client_overlap": 0.0, "severity": "low"}

    # Client overlap: max overlap across matched services (not sum, to avoid >1.0)
    client_overlap = max(matched_services.values())

    # Severity estimation from content signals
    severity_keywords = [
        "wajib", "mandatory", "harus", "required", "deadline", "denda", "penalty",
        "fine", "sanksi", "sanction", "dicabut", "revoked", "dibatalkan", "cancelled",
        "new regulation", "peraturan baru", "changes", "perubahan",
    ]
    severity_hits = sum(1 for kw in severity_keywords if kw in text)
    severity_score = min(severity_hits / 3.0, 1.0)
    severity_label = "high" if severity_score > 0.6 else "medium" if severity_score > 0.3 else "low"

    # Composite: overlap (60%) + severity (40%)
    raw = client_overlap * 0.60 + severity_score * 0.40

    score = max(0.0, min(1.0, raw))
    details = {
        "matched_services": {k: round(v, 3) for k, v in matched_services.items()},
        "client_overlap": round(client_overlap, 3),
        "severity": severity_label,
        "severity_hits": severity_hits,
    }
    return score, details


# ---------------------------------------------------------------------------
# Quality Gate — composite scorer
# ---------------------------------------------------------------------------


class QualityGate:
    """Main quality gate: runs all 4 dimensions, computes composite, returns decision."""

    def __init__(self, config: QualityGateConfig | None = None) -> None:
        self.config = config or QualityGateConfig.load()

    def evaluate(
        self,
        *,
        title: str,
        content: str,
        category: str = "general",
        source_name: str = "",
        source_url: str = "",
        tier: str = "T3",
        svs_score: float | None = None,
        published_at: datetime | None = None,
        scraped_at: datetime | None = None,
        client_distribution: dict[str, float] | None = None,
    ) -> QualityGateResult:
        """Evaluate an article through the 4-dimension quality gate.

        Returns QualityGateResult with per-dimension scores, composite, and decision.
        """
        rel_score, rel_details = score_relevance(title, content, category, self.config)
        urg_score, urg_details = score_urgency(title, content, published_at, scraped_at, self.config)
        rel_score_dim3, rel3_details = score_reliability(
            source_name, source_url, tier, svs_score, self.config
        )
        biz_score, biz_details = score_business_impact(
            title, content, category, self.config, client_distribution
        )

        composite = (
            self.config.w_relevance * rel_score
            + self.config.w_urgency * urg_score
            + self.config.w_reliability * rel_score_dim3
            + self.config.w_business_impact * biz_score
        )
        composite = max(0.0, min(1.0, composite))

        if composite >= self.config.threshold_auto_publish:
            decision = GateDecision.AUTO_PUBLISH
        elif composite >= self.config.threshold_review:
            decision = GateDecision.REVIEW
        else:
            decision = GateDecision.ARCHIVE

        return QualityGateResult(
            relevance=rel_score,
            urgency=urg_score,
            reliability=rel_score_dim3,
            business_impact=biz_score,
            composite=composite,
            decision=decision,
            details={
                "relevance": rel_details,
                "urgency": urg_details,
                "reliability": rel3_details,
                "business_impact": biz_details,
            },
        )


# ---------------------------------------------------------------------------
# Batch processing helper
# ---------------------------------------------------------------------------


def evaluate_batch(
    articles: list[dict[str, Any]],
    config: QualityGateConfig | None = None,
) -> list[tuple[dict[str, Any], QualityGateResult]]:
    """Evaluate a batch of article dicts through the quality gate.

    Each article dict should have keys: title, content/text/summary, category,
    source_name/source, source_url/url, tier, qwen_score (optional).

    Returns list of (article, result) tuples sorted by composite descending.
    """
    gate = QualityGate(config)
    results: list[tuple[dict[str, Any], QualityGateResult]] = []

    for art in articles:
        title = art.get("title", "")
        content = art.get("content", art.get("text", art.get("summary", "")))
        category = art.get("qwen_category", art.get("category", "general"))
        source_name = art.get("source_name", art.get("source", ""))
        source_url = art.get("source_url", art.get("url", ""))
        tier = art.get("tier", "T3")
        svs = art.get("svs_score")
        published_at = _parse_datetime(art.get("published_at"))
        scraped_at = _parse_datetime(art.get("scraped_at"))

        result = gate.evaluate(
            title=title,
            content=content,
            category=category,
            source_name=source_name,
            source_url=source_url,
            tier=tier,
            svs_score=svs,
            published_at=published_at,
            scraped_at=scraped_at,
        )
        results.append((art, result))

    results.sort(key=lambda x: x[1].composite, reverse=True)
    return results


def _parse_datetime(value: Any) -> datetime | None:
    """Parse datetime from string or return as-is if already datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
