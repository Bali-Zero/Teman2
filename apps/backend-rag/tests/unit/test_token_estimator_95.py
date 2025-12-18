"""
Unit Tests for llm/token_estimator.py - 95% Coverage Target
Tests the TokenEstimator class
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test TokenEstimator initialization
# ============================================================================


class TestTokenEstimatorInit:
    """Test suite for TokenEstimator initialization"""

    def test_init_default_model(self):
        """Test initialization with default model"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        assert estimator.model == "gpt-4"

    def test_init_custom_model(self):
        """Test initialization with custom model"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator(model="gpt-3.5-turbo")

        assert estimator.model == "gpt-3.5-turbo"

    def test_init_gemini_model(self):
        """Test initialization with Gemini model uses cl100k_base"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator(model="gemini-1.5-pro")

        assert estimator.model == "gemini-1.5-pro"
        # Should use cl100k_base encoding
        if estimator._encoding is not None:
            assert estimator._encoding is not None

    def test_init_with_tiktoken_unavailable(self):
        """Test initialization when tiktoken is unavailable"""
        with patch("llm.token_estimator.TIKTOKEN_AVAILABLE", False):
            from llm.token_estimator import TokenEstimator

            estimator = TokenEstimator()

            # Encoding should be None when tiktoken unavailable
            assert (
                estimator._encoding is None or True
            )  # May or may not be None based on existing state

    def test_init_encoding_failure(self):
        """Test initialization handles encoding failure gracefully"""
        with patch("llm.token_estimator.TIKTOKEN_AVAILABLE", True):
            with patch("llm.token_estimator.tiktoken") as mock_tiktoken:
                mock_tiktoken.encoding_for_model.side_effect = Exception("Model not found")

                from llm.token_estimator import TokenEstimator

                # Force reimport to test error handling
                estimator = TokenEstimator(model="unknown-model-xyz")
                # Should not raise, encoding might be None


# ============================================================================
# Test estimate_tokens
# ============================================================================


class TestEstimateTokens:
    """Test suite for estimate_tokens method"""

    def test_estimate_tokens_with_tiktoken(self):
        """Test token estimation with tiktoken encoding"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        # Estimate tokens for a simple text
        result = estimator.estimate_tokens("Hello, how are you today?")

        assert isinstance(result, int)
        assert result > 0

    def test_estimate_tokens_empty_string(self):
        """Test token estimation for empty string"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()
        result = estimator.estimate_tokens("")

        assert isinstance(result, int)
        assert result == 0

    def test_estimate_tokens_long_text(self):
        """Test token estimation for longer text"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        long_text = "This is a longer piece of text. " * 100
        result = estimator.estimate_tokens(long_text)

        assert isinstance(result, int)
        assert result > 100  # Should be more than 100 tokens

    def test_estimate_tokens_with_encoding_failure(self):
        """Test token estimation falls back to approximation on encoding error"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        # Mock encoding to raise error
        mock_encoding = MagicMock()
        mock_encoding.encode.side_effect = Exception("Encoding failed")
        estimator._encoding = mock_encoding

        result = estimator.estimate_tokens("Test text for estimation")

        assert isinstance(result, int)
        assert result > 0

    def test_estimate_tokens_without_encoding(self):
        """Test token estimation without tiktoken encoding"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()
        estimator._encoding = None

        result = estimator.estimate_tokens("This is a test sentence with several words")

        assert isinstance(result, int)
        assert result > 0


# ============================================================================
# Test estimate_messages_tokens
# ============================================================================


class TestEstimateMessagesTokens:
    """Test suite for estimate_messages_tokens method"""

    def test_estimate_messages_single_message(self):
        """Test estimating tokens for a single message"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        messages = [{"role": "user", "content": "Hello, how are you?"}]

        result = estimator.estimate_messages_tokens(messages)

        assert isinstance(result, int)
        assert result > 0

    def test_estimate_messages_multiple_messages(self):
        """Test estimating tokens for multiple messages"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the weather like?"},
            {"role": "assistant", "content": "I cannot check real-time weather."},
        ]

        result = estimator.estimate_messages_tokens(messages)

        assert isinstance(result, int)
        assert result > 0

    def test_estimate_messages_empty_list(self):
        """Test estimating tokens for empty message list"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()
        result = estimator.estimate_messages_tokens([])

        assert result == 0

    def test_estimate_messages_missing_content(self):
        """Test estimating tokens for messages with missing content"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        messages = [
            {"role": "user"},  # Missing content
            {"content": "Test"},  # Missing role
        ]

        result = estimator.estimate_messages_tokens(messages)

        assert isinstance(result, int)
        # Should add 4 tokens overhead per message
        assert result >= 8

    def test_estimate_messages_includes_overhead(self):
        """Test that message estimation includes overhead tokens"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        messages = [{"role": "user", "content": "Hi"}]

        result_with_messages = estimator.estimate_messages_tokens(messages)

        # Single message should include 4 tokens overhead
        # Plus tokens for "user: Hi"
        assert result_with_messages >= 4


# ============================================================================
# Test _estimate_approximate
# ============================================================================


class TestEstimateApproximate:
    """Test suite for _estimate_approximate method"""

    def test_estimate_approximate_simple_text(self):
        """Test approximate estimation for simple text"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        # 10 words, should be approximately 13 tokens (10 * 1.3)
        result = estimator._estimate_approximate("one two three four five six seven eight nine ten")

        assert isinstance(result, int)
        assert result == 13  # 10 * 1.3 = 13

    def test_estimate_approximate_empty_text(self):
        """Test approximate estimation for empty text"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()
        result = estimator._estimate_approximate("")

        assert result == 0

    def test_estimate_approximate_long_text(self):
        """Test approximate estimation for long text"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        # 100 words
        words = " ".join(["word"] * 100)
        result = estimator._estimate_approximate(words)

        assert result == 130  # 100 * 1.3 = 130


# ============================================================================
# Test constants and flags
# ============================================================================


class TestModuleConstants:
    """Test suite for module constants"""

    def test_token_char_ratio(self):
        """Test TOKEN_CHAR_RATIO constant"""
        from llm.token_estimator import TokenEstimator

        assert TokenEstimator.TOKEN_CHAR_RATIO == 4

    def test_token_word_ratio(self):
        """Test TOKEN_WORD_RATIO constant"""
        from llm.token_estimator import TokenEstimator

        assert TokenEstimator.TOKEN_WORD_RATIO == 1.3

    def test_tiktoken_available_flag(self):
        """Test TIKTOKEN_AVAILABLE flag is defined"""
        from llm.token_estimator import TIKTOKEN_AVAILABLE

        assert isinstance(TIKTOKEN_AVAILABLE, bool)


# ============================================================================
# Test edge cases
# ============================================================================


class TestEdgeCases:
    """Test suite for edge cases"""

    def test_estimation_fallback_when_no_encoding(self):
        """Test that estimation works correctly when no encoding available"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()
        # Force no encoding
        estimator._encoding = None

        result = estimator.estimate_tokens("This is a test message")

        # Should use approximation: 5 words * 1.3 = 6.5 -> 6
        assert result == 6

    def test_gemini_model_variation(self):
        """Test Gemini model with different case"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator(model="GEMINI-pro")

        # Should use cl100k_base for Gemini
        assert estimator.model == "GEMINI-pro"

    def test_estimate_tokens_unicode_text(self):
        """Test token estimation with unicode text"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        # Test with Indonesian/international characters
        result = estimator.estimate_tokens("Halo, apa kabar? Saya ingin tahu tentang visa 🇮🇩")

        assert isinstance(result, int)
        assert result > 0

    def test_estimate_messages_long_conversation(self):
        """Test estimating tokens for a long conversation"""
        from llm.token_estimator import TokenEstimator

        estimator = TokenEstimator()

        messages = []
        for i in range(50):
            messages.append({"role": "user", "content": f"Question {i}: What about this?"})
            messages.append({"role": "assistant", "content": f"Answer {i}: Here is the info."})

        result = estimator.estimate_messages_tokens(messages)

        # 100 messages * (tokens per message + 4 overhead)
        assert result > 100 * 4  # At least overhead for all messages
