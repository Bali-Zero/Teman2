"""
Token Estimator — Lightweight approximation for cost logging.

S04 Solidification: Removed tiktoken dependency (used cl100k_base/BPE
which is wrong for Gemini's SentencePiece tokenizer). Word-based
approximation is sufficient for cost logging. Actual token counts
come from API response usage_metadata in production paths.
"""

import logging

logger = logging.getLogger(__name__)

# Approximation: ~1.3 tokens per word for English/Indonesian mixed text
_TOKEN_WORD_RATIO = 1.3


class TokenEstimator:
    """Lightweight token estimator using word-count approximation."""

    def __init__(self, model: str = "gemini-3-flash-preview") -> None:
        self.model = model

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text (word-based approximation)."""
        return int(len(text.split()) * _TOKEN_WORD_RATIO)

    def estimate_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        """Estimate total tokens for a list of chat messages."""
        total = 0
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content", "")
            role = msg.get("role", "")
            total += self.estimate_tokens(f"{role}: {content}") + 4
        return total
