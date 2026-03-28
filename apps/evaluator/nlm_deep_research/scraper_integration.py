"""NLMEnricher adapter for intel scraper integration.

The scraper calls NLMEnricher.enrich() to get NLM context for articles.
This is the ONLY touch point between the NLM pipeline and the scraper.

Design: adapter pattern — scraper works identically with or without NLM.
"""

import json
import logging
import math
from pathlib import Path
from typing import Optional

from .handoff import HANDOFF_DIR, MODE_IGNORE, validate_handoff_schema

logger = logging.getLogger(__name__)

# Cross-validation boost/penalty
CONVERGENCE_BOOST_BASE = 0.30  # B(n) = 0.30 * ln(1+n) / ln(6)
CONTRADICTION_PENALTY_PER = 0.15  # P(m) = min(0.40, 0.15 * m)
MAX_CONTRADICTION_PENALTY = 0.40

# Provenance tracking — prevent feedback loops
BLOCKED_DOMAINS = ["balizero.com"]


class NLMEnricher:
    """Adapter that provides NLM enrichment to the intel scraper.

    Usage in scraper:
        enricher = NLMEnricher()
        context = enricher.enrich(article_topic, article_sources)
        # context is None if no handoff or irrelevant
        # context has .findings, .mode, .boost if relevant
    """

    def __init__(self, handoff_dir: Optional[str] = None):
        self._handoff_dir = Path(handoff_dir or HANDOFF_DIR)
        self._package: Optional[dict] = None
        self._loaded = False

    def _load_latest(self) -> bool:
        """Load latest.json handoff package. Returns True if valid."""
        latest = self._handoff_dir / "latest.json"
        if not latest.exists():
            logger.debug("No handoff file found at %s", latest)
            self._loaded = True
            return False

        try:
            with open(latest) as f:
                self._package = json.load(f)

            is_valid, errors = validate_handoff_schema(self._package)
            if not is_valid:
                logger.warning("Invalid handoff schema: %s", errors)
                self._package = None
                self._loaded = True
                return False

            if self._package.get("integration_mode") == MODE_IGNORE:
                logger.info("Handoff mode is IGNORE — no enrichment")
                self._loaded = True
                return False

            self._loaded = True
            return True
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load handoff: %s", e)
            self._loaded = True
            return False

    @property
    def is_available(self) -> bool:
        """Check if NLM enrichment is available."""
        if not self._loaded:
            self._load_latest()
        return self._package is not None

    @property
    def mode(self) -> str:
        """Current integration mode."""
        if not self.is_available:
            return MODE_IGNORE
        return self._package.get("integration_mode", MODE_IGNORE)

    def enrich(
        self,
        article_topic: str,
        article_sources: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """Get NLM enrichment context for a scraper article.

        Args:
            article_topic: Topic/headline of the article being processed
            article_sources: URLs of sources the scraper found

        Returns:
            Enrichment dict with findings, boost, mode — or None if not relevant
        """
        if not self.is_available:
            return None

        # Check for feedback loop: article_sources must not contain blocked domains
        if article_sources:
            for url in article_sources:
                if _is_feedback_loop(url):
                    logger.warning("Feedback loop detected: %s — skipping enrichment", url)
                    return None

        # Find relevant findings
        findings = self._package.get("key_findings", [])
        relevant = _find_relevant_findings(article_topic, findings)

        if not relevant:
            return None

        # Calculate cross-validation boost
        boost = _calculate_convergence_boost(len(relevant))

        return {
            "mode": self.mode,
            "findings": relevant,
            "boost": boost,
            "suggested_topics": self._package.get("suggested_topics", []),
            "avoid_urls": self._package.get("scraper_hints", {}).get("avoid_urls", []),
        }


def _is_feedback_loop(url: str) -> bool:
    """Check if URL would create a feedback loop."""
    if not url:
        return False
    for domain in BLOCKED_DOMAINS:
        if domain in url:
            return True
    return False


def _find_relevant_findings(topic: str, findings: list[dict]) -> list[dict]:
    """Find handoff findings relevant to the article topic.

    Simple keyword overlap — in production, this would use embeddings.
    """
    if not topic or not findings:
        return []

    topic_words = set(topic.lower().split())
    relevant = []

    for finding in findings:
        headline = finding.get("headline", "")
        headline_words = set(headline.lower().split())

        # Overlap score: Jaccard-like
        overlap = len(topic_words & headline_words)
        if overlap >= 2:  # At least 2 shared words
            relevant.append(finding)

    return relevant


def _calculate_convergence_boost(n_convergent: int) -> float:
    """Calculate logarithmic convergence boost.

    B(n) = 0.30 * ln(1+n) / ln(6)
    Capped at 0.30 (when n=5, B=1.0*0.30=0.30)
    """
    if n_convergent <= 0:
        return 0.0
    boost = CONVERGENCE_BOOST_BASE * math.log(1 + n_convergent) / math.log(6)
    return round(min(CONVERGENCE_BOOST_BASE, boost), 3)


def calculate_contradiction_penalty(n_contradictions: int) -> float:
    """Calculate proportional contradiction penalty.

    P(m) = min(0.40, 0.15 * m)
    """
    if n_contradictions <= 0:
        return 0.0
    penalty = CONTRADICTION_PENALTY_PER * n_contradictions
    return round(min(MAX_CONTRADICTION_PENALTY, penalty), 3)
