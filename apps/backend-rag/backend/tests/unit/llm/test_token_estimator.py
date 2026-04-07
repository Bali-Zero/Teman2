"""
Unit tests for TokenEstimator
Target: >95% coverage

The TokenEstimator was simplified in S04 Solidification to use word-based
approximation only (removed tiktoken dependency since it uses cl100k_base/BPE
which is wrong for Gemini's SentencePiece tokenizer).
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.token_estimator import TokenEstimator


class TestTokenEstimator:
    """Tests for TokenEstimator"""

    def test_init_default_model(self):
        """Test initialization with default model"""
        estimator = TokenEstimator()
        assert estimator.model == "gemini-3-flash-preview"

    def test_init_custom_model(self):
        """Test initialization with custom model"""
        estimator = TokenEstimator("gpt-4")
        assert estimator.model == "gpt-4"

    def test_init_with_gemini_model(self):
        """Test initialization with Gemini model"""
        estimator = TokenEstimator("gemini-pro")
        assert estimator.model == "gemini-pro"

    def test_estimate_tokens_basic(self):
        """Test basic token estimation (word-based approximation)"""
        estimator = TokenEstimator("gpt-4")
        count = estimator.estimate_tokens("test text")
        # "test text" = 2 words * 1.3 = 2.6 -> int(2.6) = 2
        assert count == 2

    def test_estimate_tokens_longer_text(self):
        """Test token estimation with longer text"""
        estimator = TokenEstimator("gpt-4")
        count = estimator.estimate_tokens("the quick brown fox jumps over the lazy dog")
        # 9 words * 1.3 = 11.7 -> int(11.7) = 11
        assert count == 11

    def test_estimate_tokens_single_word(self):
        """Test token estimation with single word"""
        estimator = TokenEstimator("gpt-4")
        count = estimator.estimate_tokens("hello")
        # 1 word * 1.3 = 1.3 -> int(1.3) = 1
        assert count == 1

    def test_estimate_tokens_empty_string(self):
        """Test token estimation with empty string"""
        estimator = TokenEstimator("gpt-4")
        count = estimator.estimate_tokens("")
        assert count == 0

    def test_estimate_tokens_returns_positive(self):
        """Test that estimation returns positive value for non-empty text"""
        estimator = TokenEstimator("gpt-4")
        count = estimator.estimate_tokens("test text with some words")
        assert count > 0

    def test_estimate_messages_tokens(self):
        """Test estimating tokens for messages"""
        estimator = TokenEstimator("gpt-4")
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        count = estimator.estimate_messages_tokens(messages)
        assert count > 0  # Should include overhead (4 tokens per message)

    def test_estimate_messages_tokens_empty(self):
        """Test estimating tokens for empty messages"""
        estimator = TokenEstimator("gpt-4")
        count = estimator.estimate_messages_tokens([])
        assert count == 0

    def test_estimate_messages_tokens_missing_fields(self):
        """Test estimating tokens for messages with missing fields"""
        estimator = TokenEstimator("gpt-4")
        messages = [
            {"role": "user"},  # Missing content
            {"content": "Hello"},  # Missing role
        ]
        count = estimator.estimate_messages_tokens(messages)
        assert count >= 0

    def test_estimate_messages_tokens_non_dict(self):
        """Test estimating tokens for messages with non-dict items"""
        estimator = TokenEstimator("gpt-4")
        messages = [
            {"role": "user", "content": "Hello"},
            "not a dict",  # Should be skipped
        ]
        count = estimator.estimate_messages_tokens(messages)
        assert count > 0  # Only the valid dict message counts
