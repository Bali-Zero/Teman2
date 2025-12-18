"""
Token Estimator - Accurate token counting for cost tracking

Uses tiktoken for accurate token estimation instead of approximations.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Try to import tiktoken, fallback to approximation if not available
try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("⚠️ tiktoken not available, using approximation for token estimation")


class TokenEstimator:
    """
    Estimates token counts for cost tracking.

    Uses tiktoken for accurate estimation when available,
    falls back to approximation otherwise.
    """

    # Approximation constants (fallback)
    TOKEN_CHAR_RATIO = 4  # Average characters per token
    TOKEN_WORD_RATIO = 1.3  # Average words per token

    def __init__(self, model: str = "gpt-4"):
        """
        Initialize TokenEstimator.

        Args:
            model: Model name for tokenizer selection
        """
        self.model = model
        self._encoding: Any = None

        if TIKTOKEN_AVAILABLE:
            try:
                # Try to get encoding for model
                # For Gemini models, use cl100k_base (GPT-4) as approximation
                if "gemini" in model.lower():
                    self._encoding = tiktoken.get_encoding("cl100k_base")
                    logger.debug(
                        f"✅ TokenEstimator initialized with tiktoken cl100k_base for Gemini model {model}"
                    )
                else:
                    self._encoding = tiktoken.encoding_for_model(model)
                    logger.debug(f"✅ TokenEstimator initialized with tiktoken for {model}")
            except Exception as e:
                logger.debug(
                    f"⚠️ Failed to load tiktoken encoding for {model}: {e}, using approximation"
                )
                self._encoding = None

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if self._encoding:
            try:
                return len(self._encoding.encode(text))
            except Exception as e:
                logger.warning(f"⚠️ tiktoken encoding failed: {e}, using approximation")
                return self._estimate_approximate(text)

        return self._estimate_approximate(text)

    def estimate_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        """
        Estimate total tokens for a list of messages.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Total estimated token count
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")
            # Add tokens for role and content
            total += self.estimate_tokens(f"{role}: {content}")
            # Add overhead for message structure (~4 tokens per message)
            total += 4
        return total

    def _estimate_approximate(self, text: str) -> int:
        """
        Fallback approximation method.

        Args:
            text: Text to estimate

        Returns:
            Approximate token count
        """
        # Use word-based estimation (more accurate than char-based)
        words = len(text.split())
        return int(words * self.TOKEN_WORD_RATIO)
