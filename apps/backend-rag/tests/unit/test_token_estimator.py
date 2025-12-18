"""
Unit tests for TokenEstimator
"""

import sys
from pathlib import Path

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from llm.token_estimator import TokenEstimator  # noqa: E402


def test_token_estimator_init():
    """Test TokenEstimator initialization"""
    estimator = TokenEstimator(model="gpt-4")
    assert estimator.model == "gpt-4"
    assert estimator.TOKEN_CHAR_RATIO == 4
    assert estimator.TOKEN_WORD_RATIO == 1.3


def test_token_estimator_init_gemini():
    """Test TokenEstimator initialization with Gemini model"""
    estimator = TokenEstimator(model="gemini-2.5-pro")
    assert estimator.model == "gemini-2.5-pro"


def test_estimate_tokens_approximate():
    """Test token estimation with approximation (no tiktoken)"""
    estimator = TokenEstimator(model="test-model")
    estimator._encoding = None  # Force approximation

    text = "Hello world this is a test"
    tokens = estimator.estimate_tokens(text)

    # Should use word-based approximation: 5 words * 1.3 = 6.5 -> 6
    assert tokens > 0
    assert isinstance(tokens, int)


def test_estimate_tokens_with_tiktoken():
    """Test token estimation with tiktoken when available"""
    try:
        import tiktoken  # noqa: F401

        estimator = TokenEstimator(model="gpt-4")

        # If tiktoken is available, encoding should be set
        if estimator._encoding:
            text = "Hello world"
            tokens = estimator.estimate_tokens(text)
            assert tokens > 0
            assert isinstance(tokens, int)
    except ImportError:
        pytest.skip("tiktoken not available")


def test_estimate_messages_tokens():
    """Test estimating tokens for multiple messages"""
    estimator = TokenEstimator(model="test-model")
    estimator._encoding = None  # Force approximation

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]

    tokens = estimator.estimate_messages_tokens(messages)

    # Should estimate tokens for both messages plus overhead
    assert tokens > 0
    assert isinstance(tokens, int)


def test_estimate_messages_tokens_empty():
    """Test estimating tokens for empty messages"""
    estimator = TokenEstimator(model="test-model")
    messages = []

    tokens = estimator.estimate_messages_tokens(messages)

    # Should return 0 or small overhead
    assert tokens >= 0
    assert isinstance(tokens, int)


def test_estimate_tokens_empty_text():
    """Test estimating tokens for empty text"""
    estimator = TokenEstimator(model="test-model")
    estimator._encoding = None

    tokens = estimator.estimate_tokens("")

    assert tokens == 0


def test_estimate_approximate_method():
    """Test the _estimate_approximate method directly"""
    estimator = TokenEstimator(model="test-model")

    text = "This is a test"
    tokens = estimator._estimate_approximate(text)

    # 4 words * 1.3 = 5.2 -> 5
    assert tokens == 5


def test_token_estimator_gemini_fallback():
    """Test TokenEstimator handles Gemini models correctly"""
    estimator = TokenEstimator(model="gemini-2.5-pro")

    # Should not raise error even if tiktoken doesn't recognize Gemini
    text = "Hello world"
    tokens = estimator.estimate_tokens(text)

    assert tokens > 0
    assert isinstance(tokens, int)
