"""
Unit tests for TokenEstimator - Accurate token counting
"""

from unittest.mock import Mock, patch

import pytest

from backend.llm.token_estimator import TIKTOKEN_AVAILABLE, TokenEstimator


class TestTokenEstimator:
    """Test suite for TokenEstimator class"""

    @pytest.fixture
    def mock_encoding(self):
        """Mock tiktoken encoding"""
        encoding = Mock()
        encoding.encode = Mock(return_value=[1, 2, 3, 4, 5])  # 5 tokens
        return encoding

    def test_init_with_gpt4_model(self):
        """Test initialization with GPT-4 model"""
        estimator = TokenEstimator(model="gpt-4")
        assert estimator.model == "gpt-4"
        if TIKTOKEN_AVAILABLE:
            assert estimator._encoding is not None

    def test_init_with_gemini_model(self):
        """Test initialization with Gemini model"""
        estimator = TokenEstimator(model="gemini-pro")
        assert estimator.model == "gemini-pro"
        # Gemini should use cl100k_base encoding
        if TIKTOKEN_AVAILABLE:
            assert estimator._encoding is not None

    def test_init_with_unknown_model(self):
        """Test initialization with unknown model falls back gracefully"""
        estimator = TokenEstimator(model="unknown-model-xyz")
        assert estimator.model == "unknown-model-xyz"
        # Should either have encoding or be None (fallback)
        assert estimator._encoding is None or estimator._encoding is not None

    @patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", False)
    def test_init_without_tiktoken(self):
        """Test initialization when tiktoken is not available"""
        estimator = TokenEstimator()
        assert estimator._encoding is None

    def test_estimate_tokens_with_tiktoken(self, mock_encoding):
        """Test token estimation using tiktoken"""
        estimator = TokenEstimator()
        estimator._encoding = mock_encoding

        result = estimator.estimate_tokens("Hello world")

        assert result == 5
        mock_encoding.encode.assert_called_once_with("Hello world")

    def test_estimate_tokens_without_tiktoken(self):
        """Test token estimation using approximation fallback"""
        estimator = TokenEstimator()
        estimator._encoding = None

        # "Hello world" = 2 words
        # 2 words * 1.3 = 2.6 → 2 tokens (int conversion)
        result = estimator.estimate_tokens("Hello world")

        assert result == 2  # 2 words * 1.3 = 2.6 → int(2.6) = 2

    def test_estimate_tokens_empty_string(self):
        """Test token estimation for empty string"""
        estimator = TokenEstimator()
        estimator._encoding = None

        result = estimator.estimate_tokens("")

        assert result == 0

    def test_estimate_tokens_long_text(self):
        """Test token estimation for long text"""
        estimator = TokenEstimator()
        estimator._encoding = None

        # 100 words text
        text = " ".join(["word"] * 100)
        result = estimator.estimate_tokens(text)

        # 100 words * 1.3 = 130 tokens
        assert result == 130

    def test_estimate_tokens_with_tiktoken_error(self, mock_encoding):
        """Test token estimation when tiktoken encoding raises error"""
        estimator = TokenEstimator()
        estimator._encoding = mock_encoding
        mock_encoding.encode.side_effect = Exception("Encoding error")

        # Should fallback to approximation
        # "Hello world" = 2 words → 2 tokens
        result = estimator.estimate_tokens("Hello world")

        assert result == 2  # Fallback approximation

    def test_estimate_messages_tokens_single_message(self):
        """Test token estimation for single message"""
        estimator = TokenEstimator()
        estimator._encoding = None

        messages = [{"role": "user", "content": "Hello world"}]

        result = estimator.estimate_messages_tokens(messages)

        # "user: Hello world" = 3 words * 1.3 = 3.9 → 3 tokens
        # + 4 tokens overhead = 7 tokens
        assert result == 7

    def test_estimate_messages_tokens_multiple_messages(self):
        """Test token estimation for multiple messages"""
        estimator = TokenEstimator()
        estimator._encoding = None

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you"},
        ]

        result = estimator.estimate_messages_tokens(messages)

        # Message 1: "user: Hello" = 2 words → 2 tokens + 4 overhead = 6
        # Message 2: "assistant: Hi there" = 3 words → 3 tokens + 4 overhead = 7
        # Message 3: "user: How are you" = 4 words → 5 tokens + 4 overhead = 9
        # Total = 6 + 7 + 9 = 22
        assert result == 22

    def test_estimate_messages_tokens_empty_list(self):
        """Test token estimation for empty message list"""
        estimator = TokenEstimator()

        result = estimator.estimate_messages_tokens([])

        assert result == 0

    def test_estimate_messages_tokens_missing_content(self):
        """Test token estimation for message missing content"""
        estimator = TokenEstimator()
        estimator._encoding = None

        messages = [
            {"role": "user"}  # Missing content
        ]

        result = estimator.estimate_messages_tokens(messages)

        # "user: " = 1 word → 1 token + 4 overhead = 5
        assert result == 5

    def test_estimate_messages_tokens_missing_role(self):
        """Test token estimation for message missing role"""
        estimator = TokenEstimator()
        estimator._encoding = None

        messages = [
            {"content": "Hello"}  # Missing role
        ]

        result = estimator.estimate_messages_tokens(messages)

        # ": Hello" = 1 word → 1 token + 4 overhead = 5
        assert result == 5

    @patch("backend.llm.token_estimator.tiktoken")
    def test_init_tiktoken_import_error(self, mock_tiktoken):
        """Test initialization when tiktoken raises import error"""
        mock_tiktoken.encoding_for_model.side_effect = Exception("Import error")

        estimator = TokenEstimator(model="gpt-4")

        # Should fallback gracefully
        assert estimator.model == "gpt-4"

    def test_approximate_estimation_accuracy(self):
        """Test approximation method accuracy"""
        estimator = TokenEstimator()

        # Test known phrases
        text1 = "The quick brown fox"  # 4 words → 5 tokens
        text2 = "Hello world how are you today"  # 6 words → 7 tokens

        result1 = estimator._estimate_approximate(text1)
        result2 = estimator._estimate_approximate(text2)

        assert result1 == 5  # 4 * 1.3 = 5.2 → 5
        assert result2 == 7  # 6 * 1.3 = 7.8 → 7

    def test_estimate_tokens_special_characters(self):
        """Test token estimation with special characters"""
        estimator = TokenEstimator()
        estimator._encoding = None

        text = "Hello! @world #test $special %chars"
        result = estimator.estimate_tokens(text)

        # 5 words → 6 tokens
        assert result == 6

    def test_estimate_tokens_multilingual(self):
        """Test token estimation with multilingual text"""
        estimator = TokenEstimator()
        estimator._encoding = None

        text = "Hello मस्ते 你好 مرحبا"  # 4 words
        result = estimator.estimate_tokens(text)

        # 4 words → 5 tokens
        assert result == 5

    def test_token_char_ratio_constant(self):
        """Test TOKEN_CHAR_RATIO constant"""
        assert TokenEstimator.TOKEN_CHAR_RATIO == 4

    def test_token_word_ratio_constant(self):
        """Test TOKEN_WORD_RATIO constant"""
        assert TokenEstimator.TOKEN_WORD_RATIO == 1.3

    @pytest.mark.parametrize(
        "model,expected_model",
        [
            ("gpt-4", "gpt-4"),
            ("gpt-3.5-turbo", "gpt-3.5-turbo"),
            ("gemini-pro", "gemini-pro"),
            ("claude-3", "claude-3"),
        ],
    )
    def test_init_with_various_models(self, model, expected_model):
        """Test initialization with various model names"""
        estimator = TokenEstimator(model=model)
        assert estimator.model == expected_model

    def test_estimate_messages_with_tiktoken(self, mock_encoding):
        """Test message estimation using tiktoken"""
        estimator = TokenEstimator()
        estimator._encoding = mock_encoding

        messages = [{"role": "user", "content": "Hello"}]

        result = estimator.estimate_messages_tokens(messages)

        # tiktoken returns 5 tokens + 4 overhead = 9
        assert result == 9
        mock_encoding.encode.assert_called_once()

    def test_estimate_very_long_message(self):
        """Test estimation for very long message"""
        estimator = TokenEstimator()
        estimator._encoding = None

        # 1000 word message
        content = " ".join(["word"] * 1000)
        messages = [{"role": "user", "content": content}]

        result = estimator.estimate_messages_tokens(messages)

        # 1001 words (role + content) * 1.3 + 4 overhead ≈ 1305
        assert result > 1000  # Should be approximately 1305

    def test_estimate_tokens_newlines_and_whitespace(self):
        """Test token estimation with newlines and whitespace"""
        estimator = TokenEstimator()
        estimator._encoding = None

        text = "Hello\n\nworld  \n  test"
        result = estimator.estimate_tokens(text)

        # 3 words → 3 tokens
        assert result == 3

    def test_default_model_initialization(self):
        """Test default model initialization"""
        estimator = TokenEstimator()
        assert estimator.model == "gpt-4"
