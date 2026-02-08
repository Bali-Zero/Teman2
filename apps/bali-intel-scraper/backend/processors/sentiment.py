"""
Sentiment analysis processor.

Analyzes text sentiment using AI and traditional NLP methods.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict
import json

from backend.services.ai_engine import ai_engine, AIProvider
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="sentiment")


class SentimentLabel(Enum):
    """Sentiment classification labels."""

    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    SLIGHTLY_NEGATIVE = "slightly_negative"
    NEUTRAL = "neutral"
    SLIGHTLY_POSITIVE = "slightly_positive"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


@dataclass
class SentimentResult:
    """Sentiment analysis result."""

    score: float  # -1.0 to 1.0
    label: SentimentLabel
    confidence: float
    aspects: Dict[str, float]  # Aspect-based sentiment
    emotions: Dict[str, float]  # Emotion detection


class SentimentAnalyzer:
    """Analyze sentiment of text content."""

    # Keywords for basic sentiment
    POSITIVE_WORDS = {
        "good",
        "great",
        "excellent",
        "amazing",
        "wonderful",
        "fantastic",
        "love",
        "like",
        "enjoy",
        "happy",
        "pleased",
        "satisfied",
        "best",
        "awesome",
        "perfect",
        "brilliant",
        "outstanding",
        "success",
        "win",
        "victory",
        "growth",
        "improvement",
        "progress",
        "beautiful",
        "nice",
        "pleasant",
        "delightful",
        "positive",
    }

    NEGATIVE_WORDS = {
        "bad",
        "terrible",
        "awful",
        "horrible",
        "hate",
        "dislike",
        "angry",
        "sad",
        "disappointed",
        "frustrated",
        "annoyed",
        "worst",
        "fail",
        "failure",
        "loss",
        "decline",
        "crisis",
        "problem",
        "issue",
        "concern",
        "worry",
        "fear",
        "negative",
        "difficult",
        "hard",
        "struggle",
        "challenge",
        "risk",
    }

    EMOTION_WORDS = {
        "joy": ["happy", "joyful", "excited", "delighted", "cheerful"],
        "anger": ["angry", "furious", "mad", "irritated", "annoyed"],
        "sadness": ["sad", "depressed", "melancholy", "gloomy", "sorrowful"],
        "fear": ["afraid", "scared", "terrified", "anxious", "worried"],
        "surprise": ["surprised", "amazed", "astonished", "shocked"],
        "disgust": ["disgusted", "repulsed", "revolted", "appalled"],
    }

    def __init__(self, use_ai: bool = True):
        self.use_ai = use_ai

    async def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of text."""
        if self.use_ai and len(text) > 50:
            try:
                return await self._analyze_with_ai(text)
            except Exception as e:
                logger.warning(
                    "AI sentiment analysis failed, falling back",
                    action=LogAction.ERROR,
                    metadata={"error": str(e)},
                )

        return self._analyze_basic(text)

    async def _analyze_with_ai(self, text: str) -> SentimentResult:
        """Analyze sentiment using AI."""
        prompt = f"""Analyze the sentiment of this text. Return ONLY a JSON object with this structure:
{{
    "score": <float between -1 and 1>,
    "confidence": <float between 0 and 1>,
    "label": <one of: very_negative, negative, slightly_negative, neutral, slightly_positive, positive, very_positive>,
    "aspects": {{"topic1": score, "topic2": score}},
    "emotions": {{"joy": 0.0-1.0, "anger": 0.0-1.0, "sadness": 0.0-1.0, "fear": 0.0-1.0, "surprise": 0.0-1.0}}
}}

Text: {text[:2000]}"""

        response = await ai_engine.process(
            prompt, task_type="analyze", provider=AIProvider.OPENAI, temperature=0.0
        )

        try:
            result = json.loads(response.content)

            return SentimentResult(
                score=result.get("score", 0.0),
                label=SentimentLabel(result.get("label", "neutral")),
                confidence=result.get("confidence", 0.5),
                aspects=result.get("aspects", {}),
                emotions=result.get("emotions", {}),
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(
                f"Failed to parse AI sentiment response: {e}", action=LogAction.ERROR
            )
            return self._analyze_basic(text)

    def _analyze_basic(self, text: str) -> SentimentResult:
        """Basic keyword-based sentiment analysis."""
        text_lower = text.lower()
        words = text_lower.split()

        # Count sentiment words
        positive_count = sum(1 for word in words if word in self.POSITIVE_WORDS)
        negative_count = sum(1 for word in words if word in self.NEGATIVE_WORDS)

        total = positive_count + negative_count
        if total == 0:
            score = 0.0
        else:
            score = (positive_count - negative_count) / max(len(words), 1)
            score = max(-1.0, min(1.0, score * 5))

        label = self._score_to_label(score)

        # Detect emotions
        emotions = {}
        for emotion, keywords in self.EMOTION_WORDS.items():
            count = sum(1 for word in words if word in keywords)
            emotions[emotion] = min(1.0, count / max(len(words) * 0.1, 1))

        confidence = min(1.0, len(words) / 50)

        return SentimentResult(
            score=score,
            label=label,
            confidence=confidence,
            aspects={},
            emotions=emotions,
        )

    def _score_to_label(self, score: float) -> SentimentLabel:
        """Convert score to sentiment label."""
        if score <= -0.75:
            return SentimentLabel.VERY_NEGATIVE
        elif score <= -0.5:
            return SentimentLabel.NEGATIVE
        elif score <= -0.25:
            return SentimentLabel.SLIGHTLY_NEGATIVE
        elif score <= 0.25:
            return SentimentLabel.NEUTRAL
        elif score <= 0.5:
            return SentimentLabel.SLIGHTLY_POSITIVE
        elif score <= 0.75:
            return SentimentLabel.POSITIVE
        else:
            return SentimentLabel.VERY_POSITIVE

    async def analyze_article(self, title: str, content: str) -> Dict:
        """Analyze sentiment of full article."""
        title_sentiment = await self.analyze(title)
        content_sentiment = await self.analyze(content[:5000])

        combined_score = (title_sentiment.score * 0.4) + (content_sentiment.score * 0.6)

        return {
            "overall": {
                "score": combined_score,
                "label": self._score_to_label(combined_score).value,
                "confidence": (
                    title_sentiment.confidence + content_sentiment.confidence
                )
                / 2,
            },
            "title": {
                "score": title_sentiment.score,
                "label": title_sentiment.label.value,
            },
            "content": {
                "score": content_sentiment.score,
                "label": content_sentiment.label.value,
                "emotions": content_sentiment.emotions,
            },
        }


sentiment_analyzer = SentimentAnalyzer()


async def analyze_sentiment(text: str) -> SentimentResult:
    """Quick function to analyze sentiment."""
    return await sentiment_analyzer.analyze(text)


__all__ = [
    "SentimentAnalyzer",
    "SentimentResult",
    "SentimentLabel",
    "sentiment_analyzer",
    "analyze_sentiment",
]
