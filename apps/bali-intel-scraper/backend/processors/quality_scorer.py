"""
Content quality scoring processor.

Scores articles based on:
- Readability
- Information density
- Credibility indicators
- Spam detection
"""

import re
from dataclasses import dataclass
from typing import List

from backend.core.logger import get_logger

logger = get_logger(__name__, component="quality_scorer")


@dataclass
class QualityScore:
    """Content quality score."""

    overall: float  # 0-100
    readability: float
    information_density: float
    credibility: float
    uniqueness: float
    is_spam: bool
    issues: List[str]


class QualityScorer:
    """Score content quality."""

    # Spam indicators
    SPAM_PATTERNS = [
        r"\b(?:click here|click below|act now|limited time|order now)\b",
        r"[!?]{3,}",  # Excessive punctuation
        r"\b(?:FREE|URGENT|WINNER|CONGRATULATIONS)\b",
        r"\$\d+\s*(?:million|billion|thousand)",
        r"(?:http[s]?://){3,}",  # Too many links
    ]

    # Credibility indicators
    CREDIBILITY_POSITIVE = [
        "according to",
        "study",
        "research",
        "data",
        "statistics",
        "expert",
        "official",
        "report",
        "survey",
        "analysis",
    ]

    CREDIBILITY_NEGATIVE = [
        "rumor",
        "allegedly",
        "unnamed source",
        "some say",
        "many believe",
        "it is said",
        "speculation",
    ]

    def score(self, title: str, content: str) -> QualityScore:
        """
        Score article quality.

        Returns QualityScore with overall score 0-100.
        """
        issues = []

        # Check spam
        is_spam, spam_score = self._check_spam(title + " " + content)
        if is_spam:
            issues.append("Potential spam content detected")

        # Readability
        readability = self._score_readability(content)
        if readability < 30:
            issues.append("Low readability")

        # Information density
        density = self._score_information_density(content)
        if density < 20:
            issues.append("Low information density")

        # Credibility
        credibility = self._score_credibility(content)
        if credibility < 30:
            issues.append("Low credibility indicators")

        # Uniqueness (based on repetitive content)
        uniqueness = self._score_uniqueness(content)
        if uniqueness < 50:
            issues.append("High repetition detected")

        # Calculate overall score
        if is_spam:
            overall = max(0, 100 - spam_score * 10)
        else:
            overall = (
                readability * 0.25
                + density * 0.25
                + credibility * 0.25
                + uniqueness * 0.25
            )

        return QualityScore(
            overall=round(overall, 1),
            readability=round(readability, 1),
            information_density=round(density, 1),
            credibility=round(credibility, 1),
            uniqueness=round(uniqueness, 1),
            is_spam=is_spam,
            issues=issues,
        )

    def _check_spam(self, text: str) -> tuple[bool, float]:
        """Check for spam indicators."""
        text_lower = text.lower()
        spam_score = 0

        for pattern in self.SPAM_PATTERNS:
            matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
            spam_score += matches

        # Check all caps ratio
        words = text.split()
        caps_words = sum(1 for w in words if w.isupper() and len(w) > 2)
        caps_ratio = caps_words / max(len(words), 1)

        if caps_ratio > 0.1:
            spam_score += caps_ratio * 10

        # Check link density
        links = len(re.findall(r"http[s]?://", text))
        link_density = links / max(len(words) / 100, 1)

        if link_density > 2:
            spam_score += link_density * 2

        is_spam = spam_score > 3
        return is_spam, spam_score

    def _score_readability(self, text: str) -> float:
        """Score readability using simplified Flesch."""
        sentences = max(1, len(re.split(r"[.!?]+", text)))
        words = len(text.split())
        syllables = self._count_syllables(text)

        if words == 0:
            return 0

        # Simplified Flesch Reading Ease
        avg_sentence_length = words / sentences
        avg_syllables_per_word = syllables / words

        # Score 0-100, higher is more readable
        score = (
            206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
        )

        # Normalize to 0-100
        return max(0, min(100, score))

    def _count_syllables(self, text: str) -> int:
        """Estimate syllable count."""
        words = text.lower().split()
        count = 0

        for word in words:
            word = re.sub(r"[^a-z]", "", word)
            if not word:
                continue

            # Count vowel groups
            vowels = re.findall(r"[aeiouy]+", word)
            count += max(1, len(vowels))

        return count

    def _score_information_density(self, text: str) -> float:
        """Score information density."""
        words = text.split()
        if not words:
            return 0

        # Unique words ratio
        unique_words = len(set(w.lower() for w in words))
        unique_ratio = unique_words / len(words)

        # Named entities (capitalized words) ratio
        entities = len(re.findall(r"\b[A-Z][a-z]+\b", text))
        entity_ratio = min(1.0, entities / max(len(words) / 50, 10))

        # Numbers ratio (facts/data)
        numbers = len(re.findall(r"\b\d+(?:\.\d+)?\b", text))
        number_ratio = min(1.0, numbers / max(len(words) / 100, 5))

        # Combine scores
        score = (unique_ratio * 40) + (entity_ratio * 30) + (number_ratio * 30)

        return min(100, score)

    def _score_credibility(self, text: str) -> float:
        """Score credibility indicators."""
        text_lower = text.lower()

        positive_count = sum(1 for p in self.CREDIBILITY_POSITIVE if p in text_lower)
        negative_count = sum(1 for n in self.CREDIBILITY_NEGATIVE if n in text_lower)

        # Quote ratio
        quotes = text.count('"') // 2
        quote_ratio = min(1.0, quotes / max(len(text.split()) / 200, 1))

        # Source attribution
        has_attribution = any(
            phrase in text_lower for phrase in ["said", "told", "according to"]
        )

        # Calculate score
        score = 50  # Base score
        score += positive_count * 5
        score -= negative_count * 10
        score += quote_ratio * 20
        score += 10 if has_attribution else 0

        return max(0, min(100, score))

    def _score_uniqueness(self, text: str) -> float:
        """Score content uniqueness (lower repetition = higher score)."""
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        if len(paragraphs) < 2:
            return 100

        # Check for repeated phrases
        phrases = re.findall(r"\b\w+\s+\w+\s+\w+\b", text.lower())
        phrase_counts = {}
        for phrase in phrases:
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

        # Count highly repeated phrases
        repeated = sum(1 for count in phrase_counts.values() if count > 3)

        # Score inversely to repetition
        uniqueness = max(0, 100 - (repeated * 5))

        return uniqueness

    def should_filter(self, score: QualityScore, min_quality: float = 30.0) -> bool:
        """Determine if content should be filtered."""
        if score.is_spam:
            return True
        if score.overall < min_quality:
            return True
        return False


scorer = QualityScorer()


def score_quality(title: str, content: str) -> QualityScore:
    """Quick function to score content quality."""
    return scorer.score(title, content)


__all__ = [
    "QualityScorer",
    "QualityScore",
    "scorer",
    "score_quality",
]
