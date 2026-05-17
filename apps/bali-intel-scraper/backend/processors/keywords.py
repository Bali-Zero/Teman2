"""
Keyword extraction processor.

Extracts relevant keywords and key phrases from content.
"""

import re
from collections import Counter
from dataclasses import dataclass
import json

from backend.services.ai_engine import ai_engine, AIProvider
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="keywords")


@dataclass
class Keyword:
    """Extracted keyword."""

    text: str
    score: float
    frequency: int
    is_phrase: bool = False


class KeywordExtractor:
    """Extract keywords from text."""

    # Common stopwords
    STOPWORDS = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "can",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "what",
        "which",
        "who",
        "when",
        "where",
        "why",
        "how",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "and",
        "but",
        "if",
        "or",
        "because",
        "as",
        "until",
        "while",
        "of",
        "at",
        "by",
        "for",
        "with",
        "about",
        "against",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "to",
        "from",
        "up",
        "down",
        "in",
        "out",
        "on",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
    }

    # Domain-specific keywords for Bali/Indonesia
    DOMAIN_KEYWORDS = {
        "bali",
        "indonesia",
        "tourism",
        "temple",
        "beach",
        "culture",
        "traditional",
        "ceremony",
        "island",
        "travel",
        "destination",
        "hospitality",
        "resort",
        "hotel",
        "villa",
        "restaurant",
        "local",
        "community",
        "village",
        "ubud",
        "kuta",
        "seminyak",
    }

    def __init__(self, use_ai: bool = True):
        self.use_ai = use_ai

    async def extract(
        self, text: str, max_keywords: int = 10, max_phrases: int = 5
    ) -> list[Keyword]:
        """Extract keywords from text."""
        keywords = []

        # Extract single keywords
        word_keywords = self._extract_words(text, max_keywords)
        keywords.extend(word_keywords)

        # Extract phrases
        phrase_keywords = self._extract_phrases(text, max_phrases)
        keywords.extend(phrase_keywords)

        # AI enhancement
        if self.use_ai and len(text) > 100:
            try:
                ai_keywords = await self._extract_with_ai(text)
                keywords.extend(ai_keywords)
            except Exception as e:
                logger.warning(
                    "AI keyword extraction failed",
                    action=LogAction.ERROR,
                    metadata={"error": str(e)},
                )

        # Remove duplicates and sort by score
        seen = set()
        unique = []
        for kw in sorted(keywords, key=lambda x: x.score, reverse=True):
            key = kw.text.lower()
            if key not in seen:
                seen.add(key)
                unique.append(kw)

        return unique[: max_keywords + max_phrases]

    def _extract_words(self, text: str, max_keywords: int) -> list[Keyword]:
        """Extract single-word keywords."""
        # Clean and tokenize
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

        # Filter stopwords
        words = [w for w in words if w not in self.STOPWORDS]

        # Count frequency
        freq = Counter(words)

        # Score keywords
        keywords = []
        for word, count in freq.most_common(max_keywords * 2):
            # Calculate score based on frequency and domain relevance
            domain_bonus = 1.5 if word in self.DOMAIN_KEYWORDS else 1.0
            score = (count / len(words)) * 100 * domain_bonus

            keywords.append(
                Keyword(text=word, score=score, frequency=count, is_phrase=False)
            )

        return keywords[:max_keywords]

    def _extract_phrases(self, text: str, max_phrases: int) -> list[Keyword]:
        """Extract multi-word phrases."""
        # Extract noun phrases (simplified)
        # Look for capitalized word sequences
        phrases = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)

        # Also look for quoted phrases
        quoted = re.findall(r'"([^"]{3,50})"', text)
        phrases.extend(quoted)

        # Count frequency
        freq = Counter(p.lower() for p in phrases)

        keywords = []
        for phrase, count in freq.most_common(max_phrases):
            score = count * 2  # Phrases get higher base score

            # Bonus for domain keywords
            words = phrase.split()
            domain_words = sum(1 for w in words if w in self.DOMAIN_KEYWORDS)
            score *= 1 + domain_words * 0.3

            keywords.append(
                Keyword(text=phrase, score=score, frequency=count, is_phrase=True)
            )

        return keywords[:max_phrases]

    async def _extract_with_ai(self, text: str) -> list[Keyword]:
        """Extract keywords using AI."""
        prompt = f"""Extract the 5 most important keywords or key phrases from this text. Return JSON array:
["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]

Text: {text[:2000]}"""

        response = await ai_engine.process(
            prompt,
            task_type="analyze",
            provider=AIProvider.OPENAI,
            temperature=0.0,
            max_tokens=200,
        )

        try:
            keywords_data = json.loads(response.content)
            keywords = []

            for i, kw in enumerate(keywords_data):
                keywords.append(
                    Keyword(
                        text=kw,
                        score=10 - i,  # Descending score
                        frequency=1,
                        is_phrase=" " in kw,
                    )
                )

            return keywords

        except json.JSONDecodeError:
            return []

    def get_key_topics(self, text: str, num_topics: int = 3) -> list[str]:
        """Get main topics from text."""
        import asyncio

        # Run extraction synchronously
        keywords = asyncio.run(self.extract(text, max_keywords=num_topics))
        return [kw.text for kw in keywords if kw.is_phrase][:num_topics]


extractor = KeywordExtractor()


async def extract_keywords(text: str, max_keywords: int = 10) -> list[Keyword]:
    """Quick function to extract keywords."""
    return await extractor.extract(text, max_keywords)


__all__ = [
    "KeywordExtractor",
    "Keyword",
    "extractor",
    "extract_keywords",
]
