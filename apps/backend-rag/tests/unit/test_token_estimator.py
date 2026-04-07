"""
Unit tests for TokenEstimator

The TokenEstimator was simplified in S04 Solidification to use word-based
approximation only (removed tiktoken dependency).
"""

from backend.llm.token_estimator import TokenEstimator  # noqa: E402


def test_token_estimator_init():
    """Test TokenEstimator initialization"""
    estimator = TokenEstimator(model="gpt-4")
    assert estimator.model == "gpt-4"


def test_token_estimator_init_gemini():
    """Test TokenEstimator initialization with Gemini model"""
    estimator = TokenEstimator(model="gemini-3-flash-preview")
    assert estimator.model == "gemini-3-flash-preview"


def test_estimate_tokens_approximate():
    """Test token estimation with word-based approximation"""
    estimator = TokenEstimator(model="test-model")

    text = "Hello world this is a test"
    tokens = estimator.estimate_tokens(text)

    # Should use word-based approximation: 6 words * 1.3 = 7.8 -> 7
    assert tokens > 0
    assert isinstance(tokens, int)


def test_estimate_messages_tokens():
    """Test estimating tokens for multiple messages"""
    estimator = TokenEstimator(model="test-model")

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

    # Should return 0
    assert tokens == 0
    assert isinstance(tokens, int)


def test_estimate_tokens_empty_text():
    """Test estimating tokens for empty text"""
    estimator = TokenEstimator(model="test-model")

    tokens = estimator.estimate_tokens("")

    assert tokens == 0


def test_token_estimator_word_count():
    """Test word-count based estimation"""
    estimator = TokenEstimator(model="test-model")

    text = "This is a test"
    tokens = estimator.estimate_tokens(text)

    # 4 words * 1.3 = 5.2 -> 5
    assert tokens == 5


def test_token_estimator_gemini_fallback():
    """Test TokenEstimator handles Gemini models correctly"""
    estimator = TokenEstimator(model="gemini-3-flash-preview")

    text = "Hello world"
    tokens = estimator.estimate_tokens(text)

    assert tokens > 0
    assert isinstance(tokens, int)
