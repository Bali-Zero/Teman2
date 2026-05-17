"""
Topic classification processor.

Classifies articles into categories like:
- News topics (politics, business, sports, etc.)
- Sentiment categories
- Geographic relevance
"""

from dataclasses import dataclass
from enum import Enum
import json

from backend.services.ai_engine import ai_engine, AIProvider
from backend.core.logger import get_logger, LogAction
from backend.core.cache import cached, CacheStrategy

logger = get_logger(__name__, component="classifier")


class NewsCategory(Enum):
    """News topic categories."""

    POLITICS = "politics"
    BUSINESS = "business"
    ECONOMY = "economy"
    TECHNOLOGY = "technology"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    HEALTH = "health"
    SCIENCE = "science"
    ENVIRONMENT = "environment"
    TRAVEL = "travel"
    CULTURE = "culture"
    CRIME = "crime"
    EDUCATION = "education"
    LIFESTYLE = "lifestyle"
    OTHER = "other"


@dataclass
class ClassificationResult:
    """Classification result."""

    primary_category: NewsCategory
    confidence: float
    all_scores: dict[str, float]
    keywords: list[str]


class TopicClassifier:
    """Classify content into topics."""

    # Keywords for rule-based classification
    CATEGORY_KEYWORDS = {
        NewsCategory.POLITICS: [
            "government",
            "election",
            "minister",
            "president",
            "policy",
            "political",
            "parliament",
            "vote",
        ],
        NewsCategory.BUSINESS: [
            "company",
            "market",
            "stock",
            "investment",
            "profit",
            "revenue",
            "corporate",
            "trade",
        ],
        NewsCategory.ECONOMY: [
            "economy",
            "economic",
            "inflation",
            "gdp",
            "finance",
            "financial",
            "growth",
        ],
        NewsCategory.TECHNOLOGY: [
            "technology",
            "tech",
            "digital",
            "software",
            "app",
            "internet",
            "ai",
            "data",
        ],
        NewsCategory.SPORTS: [
            "sport",
            "game",
            "match",
            "player",
            "team",
            "championship",
            "tournament",
            "score",
        ],
        NewsCategory.ENTERTAINMENT: [
            "movie",
            "music",
            "celebrity",
            "film",
            "actor",
            "concert",
            "show",
            "entertainment",
        ],
        NewsCategory.HEALTH: [
            "health",
            "medical",
            "hospital",
            "disease",
            "treatment",
            "doctor",
            "medicine",
        ],
        NewsCategory.SCIENCE: [
            "science",
            "research",
            "study",
            "discovery",
            "scientist",
            "space",
            "physics",
        ],
        NewsCategory.ENVIRONMENT: [
            "environment",
            "climate",
            "green",
            "pollution",
            "sustainability",
            "nature",
        ],
        NewsCategory.TRAVEL: [
            "travel",
            "tourism",
            "tourist",
            "hotel",
            "destination",
            "flight",
            "vacation",
        ],
        NewsCategory.CULTURE: [
            "culture",
            "art",
            "heritage",
            "tradition",
            "festival",
            "museum",
            "history",
        ],
        NewsCategory.CRIME: [
            "crime",
            "police",
            "court",
            "arrest",
            "criminal",
            "investigation",
            "law",
        ],
        NewsCategory.EDUCATION: [
            "education",
            "school",
            "university",
            "student",
            "teacher",
            "learning",
            "academic",
        ],
        NewsCategory.LIFESTYLE: [
            "lifestyle",
            "fashion",
            "food",
            "recipe",
            "home",
            "decor",
            "wellness",
        ],
    }

    # Bali-specific keywords
    BALI_KEYWORDS = [
        "bali",
        "denpasar",
        "kuta",
        "seminyak",
        "ubud",
        "nusa dua",
        "canggu",
        "sanur",
    ]
    INDONESIA_KEYWORDS = [
        "indonesia",
        "jakarta",
        "indonesian",
        "archipelago",
        "nusantara",
    ]

    def __init__(self, use_ai: bool = True):
        self.use_ai = use_ai

    async def classify(self, title: str, content: str) -> ClassificationResult:
        """Classify article content."""
        if self.use_ai:
            try:
                return await self._classify_with_ai(title, content)
            except Exception as e:
                logger.warning(
                    "AI classification failed, using fallback",
                    action=LogAction.ERROR,
                    metadata={"error": str(e)},
                )

        return self._classify_basic(title, content)

    async def _classify_with_ai(self, title: str, content: str) -> ClassificationResult:
        """Classify using AI."""
        prompt = f"""Classify this news article into ONE category. Return JSON:
{{
    "category": "<one of: politics, business, economy, technology, sports, entertainment, health, science, environment, travel, culture, crime, education, lifestyle, other>",
    "confidence": <0-1>,
    "keywords": ["keyword1", "keyword2", "keyword3"]
}}

Title: {title}
Content: {content[:2000]}"""

        response = await ai_engine.process(
            prompt,
            task_type="classify",
            provider=AIProvider.OPENAI,
            temperature=0.0,
            max_tokens=200,
        )

        try:
            result = json.loads(response.content)

            category_str = result.get("category", "other")
            try:
                category = NewsCategory(category_str.lower())
            except ValueError:
                category = NewsCategory.OTHER

            return ClassificationResult(
                primary_category=category,
                confidence=result.get("confidence", 0.5),
                all_scores={category_str: result.get("confidence", 0.5)},
                keywords=result.get("keywords", []),
            )

        except json.JSONDecodeError:
            return self._classify_basic(title, content)

    def _classify_basic(self, title: str, content: str) -> ClassificationResult:
        """Basic keyword-based classification."""
        text = (title + " " + content).lower()
        words = set(text.split())

        scores = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            # Normalize by keyword count
            scores[category] = score / len(keywords)

        # Get best category
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]

        # Calculate confidence
        total_score = sum(scores.values())
        confidence = best_score / total_score if total_score > 0 else 0.5

        # Extract keywords
        keywords = list(words & set().union(*self.CATEGORY_KEYWORDS.values()))[:10]

        return ClassificationResult(
            primary_category=best_category,
            confidence=min(1.0, confidence),
            all_scores={k.value: v for k, v in scores.items()},
            keywords=keywords,
        )

    def classify_geography(self, text: str) -> dict[str, float]:
        """Classify geographic relevance."""
        text_lower = text.lower()

        bali_score = sum(1 for kw in self.BALI_KEYWORDS if kw in text_lower)
        indonesia_score = sum(1 for kw in self.INDONESIA_KEYWORDS if kw in text_lower)

        # Normalize
        total_words = len(text_lower.split())

        return {
            "bali_relevance": min(1.0, bali_score / 5),
            "indonesia_relevance": min(1.0, indonesia_score / 5),
            "is_bali_news": bali_score > 0,
            "is_indonesia_news": indonesia_score > 0,
        }

    async def classify_full(self, title: str, content: str) -> dict:
        """Full classification with all metadata."""
        topic_result = await self.classify(title, content)
        geo_result = self.classify_geography(title + " " + content)

        return {
            "topic": {
                "category": topic_result.primary_category.value,
                "confidence": topic_result.confidence,
                "all_scores": topic_result.all_scores,
            },
            "geography": geo_result,
            "keywords": topic_result.keywords,
        }


classifier = TopicClassifier()


@cached(strategy=CacheStrategy.TTL_LONG)
async def classify_content(title: str, content: str) -> ClassificationResult:
    """Quick function to classify content."""
    return await classifier.classify(title, content)


__all__ = [
    "TopicClassifier",
    "ClassificationResult",
    "NewsCategory",
    "classifier",
    "classify_content",
]
