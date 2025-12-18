"""
ZANTARA RAG - Tier Classification
Classify books into knowledge tiers (S, A, B, C, D)
"""

import logging
import re

from app.models import TierLevel

logger = logging.getLogger(__name__)


class TierClassifier:
    """
    Classify books into ZANTARA knowledge tiers based on title/author/content.

    Tier S (Supreme): Quantum physics, consciousness, advanced metaphysics
    Tier A (Advanced): Philosophy, psychology, spiritual teachings
    Tier B (Intermediate): History, culture, practical wisdom
    Tier C (Basic): Self-help, business, general knowledge
    Tier D (Public): Popular science, introductory texts
    """

    # Keyword patterns for tier classification
    TIER_PATTERNS = {
        TierLevel.S: [
            # Quantum & Physics
            r"\bquantum\b",
            r"\brelativity\b",
            r"\bstring theory\b",
            r"\bcosmology\b",
            r"\bmultiverse\b",
            r"\bspacetime\b",
            # Consciousness & Metaphysics
            r"\bconsciousness\b",
            r"\bawareness\b",
            r"\bnonduality\b",
            r"\badvaita\b",
            r"\benlightenment\b",
            r"\bawakening\b",
            # Advanced spiritual
            r"\bkundalini\b",
            r"\bchakra\b",
            r"\bnirvana\b",
            r"\bsatori\b",
            r"\bsamadhi\b",
        ],
        TierLevel.A: [
            # Philosophy
            r"\bphilosophy\b",
            r"\bmetaphysics\b",
            r"\bepistemology\b",
            r"\bontology\b",
            r"\bexistentialism\b",
            r"\bphenomenology\b",
            # Psychology
            r"\bjung\b",
            r"\barchetype\b",
            r"\bcollective unconscious\b",
            r"\btranspersonal\b",
            r"\bpsychology\b",
            # Spiritual teachings
            r"\bbuddhism\b",
            r"\btaoism\b",
            r"\bvedanta\b",
            r"\bsufism\b",
            r"\bkabbalah\b",
            r"\bhermeticism\b",
        ],
        TierLevel.B: [
            # History & Culture
            r"\bhistory\b",
            r"\bcivilization\b",
            r"\banthropology\b",
            r"\bmythology\b",
            r"\barcheology\b",
            # Practical wisdom
            r"\bstrategy\b",
            r"\bwisdom\b",
            r"\bart of\b",
            # Specific traditions
            r"\bsamurai\b",
            r"\bzen\b",
            r"\byoga\b",
            r"\bmeditation\b",
            r"\bmindfulness\b",
        ],
        TierLevel.C: [
            # Business & Self-help
            r"\bbusiness\b",
            r"\bleadership\b",
            r"\bmanagement\b",
            r"\bproductivity\b",
            r"\bself-help\b",
            r"\bself improvement\b",
            r"\bsuccess\b",
            r"\bhabits\b",
            r"\bmotivation\b",
        ],
        TierLevel.D: [
            # Popular science
            r"\bintroduction\b",
            r"\bbeginners?\b",
            r"\bfor dummies\b",
            r"\bmade simple\b",
            r"\bguide to\b",
            r"\bbasics?\b",
        ],
    }

    # Author-based classification (high-tier authors)
    TIER_S_AUTHORS = [
        "david bohm",
        "niels bohr",
        "werner heisenberg",
        "ramana maharshi",
        "nisargadatta",
        "jiddu krishnamurti",
        "adi shankaracharya",
        "nagarjuna",
    ]

    TIER_A_AUTHORS = [
        "carl jung",
        "alan watts",
        "joseph campbell",
        "mircea eliade",
        "aldous huxley",
        "rudolf steiner",
        "ram dass",
        "thich nhat hanh",
        "pema chödrön",
    ]

    def __init__(self):
        """Initialize classifier with compiled regex patterns"""
        self.tier_patterns_compiled = {
            tier: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for tier, patterns in self.TIER_PATTERNS.items()
        }

        logger.info("TierClassifier initialized")

    def classify_book_tier(
        self, book_title: str, book_author: str = "", book_content_sample: str = ""
    ) -> TierLevel:
        """
        Classify a book into a tier based on title, author, and content.

        Args:
            book_title: Book title
            book_author: Book author (optional)
            book_content_sample: Sample of book content (optional, for better classification)

        Returns:
            TierLevel enum (S, A, B, C, or D)
        """
        # Combine all text for analysis
        text = f"{book_title} {book_author} {book_content_sample}".lower()

        # Check author-based classification first (most reliable)
        author_lower = book_author.lower()
        if any(author in author_lower for author in self.TIER_S_AUTHORS):
            logger.info(f"Classified as Tier S based on author: {book_author}")
            return TierLevel.S

        if any(author in author_lower for author in self.TIER_A_AUTHORS):
            logger.info(f"Classified as Tier A based on author: {book_author}")
            return TierLevel.A

        # Score each tier based on keyword matches
        tier_scores = {}
        for tier, patterns in self.tier_patterns_compiled.items():
            score = sum(1 for pattern in patterns if pattern.search(text))
            tier_scores[tier] = score

        # Find tier with highest score
        if max(tier_scores.values()) > 0:
            best_tier = max(tier_scores, key=tier_scores.get)
            logger.info(
                f"Classified '{book_title}' as Tier {best_tier.value} (scores: {tier_scores})"
            )
            return best_tier

        # Default to Tier C if no clear match
        logger.info(f"No clear match for '{book_title}', defaulting to Tier C")
        return TierLevel.C

    def get_min_access_level(self, tier: TierLevel) -> int:
        """
        Get minimum user access level required for a tier.

        Args:
            tier: Book tier

        Returns:
            Minimum access level (0-3)
        """
        tier_to_level = {
            TierLevel.S: 0,  # Level 0 can only access Tier S
            TierLevel.A: 1,  # Level 1 can access S + A
            TierLevel.B: 2,  # Level 2 can access S + A + B + C
            TierLevel.C: 2,  # Level 2 can access S + A + B + C
            TierLevel.D: 3,  # Level 3 can access all
        }
        return tier_to_level.get(tier, 3)


# Convenience function
def classify_book_tier(book_title: str, book_author: str = "", content_sample: str = "") -> str:
    """
    Quick function to classify a book without instantiating class.

    Args:
        book_title: Book title
        book_author: Book author
        content_sample: Sample content

    Returns:
        Tier as string (S, A, B, C, or D)
    """
    classifier = TierClassifier()
    tier = classifier.classify_book_tier(book_title, book_author, content_sample)
    return tier.value
