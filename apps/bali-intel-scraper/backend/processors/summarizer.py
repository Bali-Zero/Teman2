"""
Text summarization processor.

Generates concise summaries of articles using AI and extractive methods.
"""

from dataclasses import dataclass
import re

from backend.services.ai_engine import ai_engine, AIProvider
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="summarizer")


@dataclass
class Summary:
    """Generated summary."""

    text: str
    method: str  # 'extractive' or 'abstractive'
    compression_ratio: float
    original_length: int
    summary_length: int


class Summarizer:
    """Generate text summaries."""

    def __init__(self, use_ai: bool = True):
        self.use_ai = use_ai

    async def summarize(
        self, text: str, max_length: int = 200, method: str = "auto"
    ) -> Summary:
        """
        Summarize text.

        Args:
            text: Text to summarize
            max_length: Maximum summary length in words
            method: 'extractive', 'abstractive', or 'auto'

        Returns:
            Summary object
        """
        original_length = len(text.split())

        # Use extractive for short texts
        if method == "auto":
            if original_length < 200 or not self.use_ai:
                method = "extractive"
            else:
                method = "abstractive"

        if method == "abstractive" and self.use_ai:
            try:
                summary = await self._summarize_abstractive(text, max_length)
            except Exception as e:
                logger.warning(
                    "Abstractive summarization failed, using extractive",
                    action=LogAction.ERROR,
                    metadata={"error": str(e)},
                )
                summary = self._summarize_extractive(text, max_length)
        else:
            summary = self._summarize_extractive(text, max_length)

        summary_length = len(summary.text.split())
        compression = 1 - (summary_length / max(original_length, 1))

        return Summary(
            text=summary.text,
            method=method,
            compression_ratio=compression,
            original_length=original_length,
            summary_length=summary_length,
        )

    async def _summarize_abstractive(self, text: str, max_length: int) -> Summary:
        """Generate abstractive summary using AI."""
        prompt = f"""Summarize this article in {max_length} words or less:

{text[:5000]}

Summary:"""

        response = await ai_engine.process(
            prompt,
            task_type="summarize",
            provider=AIProvider.OPENAI,
            temperature=0.3,
            max_tokens=max_length * 2,
        )

        return Summary(
            text=response.content.strip(),
            method="abstractive",
            compression_ratio=0,
            original_length=len(text.split()),
            summary_length=0,
        )

    def _summarize_extractive(self, text: str, max_length: int) -> Summary:
        """Generate extractive summary using sentence scoring."""
        # Split into sentences
        sentences = self._split_sentences(text)

        if len(sentences) <= 3:
            return Summary(
                text=" ".join(sentences),
                method="extractive",
                compression_ratio=0,
                original_length=len(text.split()),
                summary_length=0,
            )

        # Score sentences
        word_freq = self._calculate_word_frequency(text)
        scores = []

        for i, sentence in enumerate(sentences):
            score = self._score_sentence(sentence, word_freq, i, len(sentences))
            scores.append((score, i, sentence))

        # Select top sentences
        scores.sort(reverse=True)
        num_sentences = max(1, min(5, max_length // 20))

        selected = sorted(scores[:num_sentences], key=lambda x: x[1])
        summary_text = " ".join(s[2] for s in selected)

        return Summary(
            text=summary_text,
            method="extractive",
            compression_ratio=0,
            original_length=len(text.split()),
            summary_length=0,
        )

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _calculate_word_frequency(self, text: str) -> dict:
        """Calculate word frequency (excluding stopwords)."""
        stopwords = {
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
            "shall",
            "can",
            "need",
            "dare",
            "ought",
            "used",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "and",
            "but",
            "or",
            "yet",
            "so",
            "if",
            "because",
            "although",
            "though",
            "while",
            "where",
            "when",
            "that",
            "which",
            "who",
            "whom",
            "whose",
            "what",
            "this",
            "these",
            "those",
            "i",
            "me",
            "my",
            "myself",
            "we",
            "our",
            "ours",
            "ourselves",
            "you",
            "your",
            "yours",
            "yourself",
            "yourselves",
            "he",
            "him",
            "his",
            "himself",
            "she",
            "her",
            "hers",
            "herself",
            "it",
            "its",
            "itself",
            "they",
            "them",
            "their",
            "theirs",
            "themselves",
        }

        words = text.lower().split()
        freq = {}

        for word in words:
            word = re.sub(r"[^\w]", "", word)
            if word and word not in stopwords and len(word) > 2:
                freq[word] = freq.get(word, 0) + 1

        return freq

    def _score_sentence(
        self, sentence: str, word_freq: dict, position: int, total: int
    ) -> float:
        """Score a sentence for importance."""
        words = sentence.lower().split()

        # Word frequency score
        freq_score = sum(word_freq.get(re.sub(r"[^\w]", "", w), 0) for w in words)
        freq_score /= max(len(words), 1)

        # Position score (earlier sentences often more important)
        position_score = 1.0 if position < total * 0.2 else 0.5

        # Length score (prefer medium-length sentences)
        length_score = 1.0 if 10 <= len(words) <= 30 else 0.5

        return freq_score * position_score * length_score

    async def summarize_article(
        self, title: str, content: str, max_sentences: int = 3
    ) -> str:
        """Generate article summary."""
        # Include title in summary consideration
        full_text = f"{title}. {content}"

        summary = await self.summarize(
            full_text, max_length=max_sentences * 25, method="auto"
        )

        return summary.text


summarizer = Summarizer()


async def summarize_text(text: str, max_length: int = 200) -> Summary:
    """Quick function to summarize text."""
    return await summarizer.summarize(text, max_length)


__all__ = [
    "Summarizer",
    "Summary",
    "summarizer",
    "summarize_text",
]
