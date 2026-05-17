"""
Fake news and misinformation detection.

Basic credibility assessment based on:
- Source reliability
- Content patterns
- Fact-check indicators
"""

import re
from dataclasses import dataclass
from enum import Enum

from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="fake_news")


class CredibilityRating(Enum):
    """Credibility rating levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


@dataclass
class CredibilityResult:
    """Credibility assessment result."""

    rating: CredibilityRating
    score: float  # 0-100
    confidence: float
    factors: list[str]
    warnings: list[str]


class FakeNewsDetector:
    """Detect potential fake news and misinformation."""

    # Known reliable sources (examples)
    RELIABLE_SOURCES = {
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "npr.org",
        "wsj.com",
        "economist.com",
        "ft.com",
        "bloomberg.com",
        "theguardian.com",
        "nytimes.com",
        "washingtonpost.com",
        "antaranews.com",
        "kompas.com",
        "detik.com",
        "liputan6.com",
        "jakartapost.com",
        "balipost.com",
        "radarbali.co.id",
    }

    # Known unreliable patterns
    UNRELIABLE_PATTERNS = [
        r"\b(?:shocking|mind blowing|you won\'t believe)\b",
        r"\b(?:doctors hate this|one weird trick)\b",
        r"\b(?:mainstream media won\'t tell you)\b",
        r"\b(?:what they don\'t want you to know)\b",
        r"\b(?:this changes everything)\b",
    ]

    # Sensationalism indicators
    SENSATIONAL_WORDS = {
        "shocking",
        "unbelievable",
        "incredible",
        "astonishing",
        "outrageous",
        "devastating",
        "terrifying",
        "miracle",
        "secret",
        "conspiracy",
        "cover-up",
        "censored",
    }

    # Emotional manipulation indicators
    EMOTIONAL_MANIPULATION = {
        "everyone is talking about",
        "people are outraged",
        "the truth about",
        "wake up",
        "sheep",
        "brainwashed",
    }

    def assess(
        self,
        title: str,
        content: str,
        source_url: str | None = None,
        author: str | None = None,
    ) -> CredibilityResult:
        """
        Assess credibility of article.

        Returns CredibilityResult with rating and factors.
        """
        factors = []
        warnings = []
        score = 50  # Start neutral

        # Source reliability
        source_score = self._assess_source(source_url)
        score += source_score
        if source_score > 10:
            factors.append("Reliable source")
        elif source_score < -10:
            factors.append("Unknown/unreliable source")
            warnings.append("Source credibility uncertain")

        # Check for clickbait patterns
        clickbait_score = self._check_clickbait(title)
        score -= clickbait_score * 5
        if clickbait_score > 0:
            factors.append(f"{clickbait_score} clickbait indicators")
            warnings.append("Potential clickbait detected")

        # Check for sensationalism
        sensational_score = self._check_sensationalism(title + " " + content)
        score -= sensational_score * 3
        if sensational_score > 2:
            factors.append("Sensational language detected")

        # Check for emotional manipulation
        manipulation_score = self._check_emotional_manipulation(title + " " + content)
        score -= manipulation_score * 4
        if manipulation_score > 0:
            factors.append("Emotional manipulation patterns")
            warnings.append("Potential emotional manipulation")

        # Check for all caps shouting
        caps_ratio = self._check_caps_ratio(title)
        if caps_ratio > 0.3:
            score -= 15
            factors.append("Excessive capitalization")

        # Check for source citations
        citation_score = self._check_citations(content)
        score += citation_score * 10
        if citation_score > 0:
            factors.append("Contains source citations")

        # Author check
        if author and len(author) > 2:
            score += 5
            factors.append("Author attribution present")
        else:
            warnings.append("No author attribution")

        # Normalize score
        score = max(0, min(100, score))

        # Determine rating
        rating = self._score_to_rating(score)

        # Calculate confidence based on available data
        confidence = self._calculate_confidence(title, content, source_url)

        logger.info(
            "Credibility assessment complete",
            action=LogAction.ANALYZE,
            metadata={
                "rating": rating.value,
                "score": score,
                "warnings": len(warnings),
            },
        )

        return CredibilityResult(
            rating=rating,
            score=round(score, 1),
            confidence=round(confidence, 2),
            factors=factors,
            warnings=warnings,
        )

    def _assess_source(self, url: str | None) -> float:
        """Assess source reliability."""
        if not url:
            return 0

        url_lower = url.lower()

        for reliable in self.RELIABLE_SOURCES:
            if reliable in url_lower:
                return 20

        # Check for suspicious TLDs
        suspicious_tlds = [".xyz", ".click", ".link", ".work"]
        if any(tld in url_lower for tld in suspicious_tlds):
            return -15

        return -5  # Unknown source

    def _check_clickbait(self, title: str) -> int:
        """Count clickbait patterns."""
        title_lower = title.lower()
        count = 0

        for pattern in self.UNRELIABLE_PATTERNS:
            if re.search(pattern, title_lower):
                count += 1

        # Numbered lists often clickbait
        if re.search(r"^\d+\s+", title):
            count += 0.5

        # Question marks
        if title.count("?") > 1:
            count += 1

        return int(count)

    def _check_sensationalism(self, text: str) -> int:
        """Count sensational words."""
        words = text.lower().split()
        count = sum(1 for word in words if word in self.SENSATIONAL_WORDS)
        return count

    def _check_emotional_manipulation(self, text: str) -> int:
        """Check for emotional manipulation phrases."""
        text_lower = text.lower()
        count = sum(1 for phrase in self.EMOTIONAL_MANIPULATION if phrase in text_lower)
        return count

    def _check_caps_ratio(self, text: str) -> float:
        """Calculate ratio of capital letters."""
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return 0
        caps = sum(1 for c in letters if c.isupper())
        return caps / len(letters)

    def _check_citations(self, content: str) -> int:
        """Count source citations."""
        citations = len(re.findall(r'"[^"]{10,200}"', content))
        citations += len(re.findall(r"according to [A-Z]", content))
        citations += len(re.findall(r"said [A-Z][a-z]+", content))
        return min(3, citations)

    def _score_to_rating(self, score: float) -> CredibilityRating:
        """Convert score to rating."""
        if score >= 70:
            return CredibilityRating.HIGH
        elif score >= 50:
            return CredibilityRating.MEDIUM
        elif score >= 30:
            return CredibilityRating.LOW
        else:
            return CredibilityRating.VERY_LOW

    def _calculate_confidence(
        self, title: str, content: str, source: str | None
    ) -> float:
        """Calculate confidence in assessment."""
        confidence = 0.5

        # More content = higher confidence
        if len(content) > 500:
            confidence += 0.2

        # Known source = higher confidence
        if source:
            confidence += 0.15

        # Title present
        if title:
            confidence += 0.1

        return min(0.95, confidence)

    def should_flag(self, result: CredibilityResult) -> bool:
        """Determine if article should be flagged for review."""
        if result.rating == CredibilityRating.VERY_LOW:
            return True
        if result.score < 30:
            return True
        return len(result.warnings) >= 3


detector = FakeNewsDetector()


def assess_credibility(
    title: str,
    content: str,
    source_url: str | None = None,
    author: str | None = None,
) -> CredibilityResult:
    """Quick function to assess credibility."""
    return detector.assess(title, content, source_url, author)


__all__ = [
    "FakeNewsDetector",
    "CredibilityResult",
    "CredibilityRating",
    "detector",
    "assess_credibility",
]
