"""
Unit tests for TokenEstimator - Word-based token approximation.
"""

import pytest

from backend.llm.token_estimator import TokenEstimator, _TOKEN_WORD_RATIO


class TestTokenEstimator:
    """Test suite for TokenEstimator class"""

    def test_default_model(self):
        estimator = TokenEstimator()
        assert estimator.model == "gemini-3-flash-preview"

    def test_custom_model(self):
        estimator = TokenEstimator(model="claude-3")
        assert estimator.model == "claude-3"

    def test_estimate_tokens_simple(self):
        estimator = TokenEstimator()
        # "Hello world" = 2 words → int(2 * 1.3) = 2
        assert estimator.estimate_tokens("Hello world") == 2

    def test_estimate_tokens_empty(self):
        estimator = TokenEstimator()
        assert estimator.estimate_tokens("") == 0

    def test_estimate_tokens_long_text(self):
        estimator = TokenEstimator()
        text = " ".join(["word"] * 100)
        assert estimator.estimate_tokens(text) == int(100 * _TOKEN_WORD_RATIO)

    def test_estimate_tokens_whitespace(self):
        estimator = TokenEstimator()
        assert estimator.estimate_tokens("Hello\n\nworld  \n  test") == int(3 * _TOKEN_WORD_RATIO)

    def test_estimate_messages_single(self):
        estimator = TokenEstimator()
        messages = [{"role": "user", "content": "Hello world"}]
        result = estimator.estimate_messages_tokens(messages)
        # "user: Hello world" = 3 words → int(3*1.3) + 4 = 3 + 4 = 7
        assert result == 7

    def test_estimate_messages_multiple(self):
        estimator = TokenEstimator()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = estimator.estimate_messages_tokens(messages)
        # msg1: "user: Hello" = 2 words → 2 + 4 = 6
        # msg2: "assistant: Hi there" = 3 words → 3 + 4 = 7
        assert result == 13

    def test_estimate_messages_empty(self):
        estimator = TokenEstimator()
        assert estimator.estimate_messages_tokens([]) == 0

    def test_estimate_messages_missing_content(self):
        estimator = TokenEstimator()
        messages = [{"role": "user"}]
        result = estimator.estimate_messages_tokens(messages)
        # "user: " = 1 word → 1 + 4 = 5
        assert result == 5

    def test_estimate_messages_non_dict_skipped(self):
        estimator = TokenEstimator()
        messages = ["not a dict", {"role": "user", "content": "Hi"}]
        result = estimator.estimate_messages_tokens(messages)
        # Only dict is counted: "user: Hi" = 2 words → 2 + 4 = 6
        assert result == 6

    def test_token_word_ratio(self):
        assert _TOKEN_WORD_RATIO == 1.3
