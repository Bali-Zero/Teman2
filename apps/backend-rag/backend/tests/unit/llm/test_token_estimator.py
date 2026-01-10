"""
Unit tests for TokenEstimator
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.token_estimator import TokenEstimator


class TestTokenEstimator:
    """Tests for TokenEstimator"""

    def test_init_with_tiktoken(self):
        """Test initialization with tiktoken available"""
        with patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", True):
            with patch("backend.llm.token_estimator.tiktoken") as mock_tiktoken:
                mock_encoding = MagicMock()
                mock_tiktoken.encoding_for_model.return_value = mock_encoding

                estimator = TokenEstimator("gpt-4")
                assert estimator.model == "gpt-4"
                assert estimator._encoding == mock_encoding

    def test_init_with_gemini_model(self):
        """Test initialization with Gemini model"""
        with patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", True):
            with patch("backend.llm.token_estimator.tiktoken") as mock_tiktoken:
                mock_encoding = MagicMock()
                mock_tiktoken.get_encoding.return_value = mock_encoding

                estimator = TokenEstimator("gemini-pro")
                mock_tiktoken.get_encoding.assert_called_with("cl100k_base")

    def test_init_without_tiktoken(self):
        """Test initialization without tiktoken"""
        with patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", False):
            estimator = TokenEstimator("gpt-4")
            assert estimator._encoding is None

    def test_init_tiktoken_error(self):
        """Test initialization with tiktoken error"""
        with patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", True):
            with patch("backend.llm.token_estimator.tiktoken") as mock_tiktoken:
                mock_tiktoken.encoding_for_model.side_effect = Exception("Error")

                estimator = TokenEstimator("gpt-4")
                assert estimator._encoding is None

    def test_estimate_tokens_with_encoding(self):
        """Test estimating tokens with encoding"""
        with patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", True):
            with patch("backend.llm.token_estimator.tiktoken") as mock_tiktoken:
                mock_encoding = MagicMock()
                # Mock encode to return a list with 5 elements
                tokens_list = [1, 2, 3, 4, 5]
                mock_encoding.encode = MagicMock(return_value=tokens_list)
                mock_tiktoken.encoding_for_model.return_value = mock_encoding

                estimator = TokenEstimator("gpt-4")
                count = estimator.estimate_tokens("test text")
                # len([1,2,3,4,5]) = 5
                assert count == 5
                mock_encoding.encode.assert_called_once_with("test text")

    def test_estimate_tokens_encoding_error(self):
        """Test estimating tokens with encoding error"""
        with patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", True):
            with patch("backend.llm.token_estimator.tiktoken") as mock_tiktoken:
                mock_encoding = MagicMock()
                mock_encoding.encode.side_effect = Exception("Encoding error")
                mock_tiktoken.encoding_for_model.return_value = mock_encoding

                estimator = TokenEstimator("gpt-4")
                count = estimator.estimate_tokens("test text")
                # Should fallback to approximation: "test text" has 2 words, * 1.3 = 2
                assert count >= 2

    def test_estimate_tokens_approximation(self):
        """Test estimating tokens with approximation"""
        with patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", False):
            estimator = TokenEstimator("gpt-4")
            count = estimator.estimate_tokens("test text")
            # Approximation: len(text) / TOKEN_CHAR_RATIO
            assert count > 0

    def test_estimate_messages_tokens(self):
        """Test estimating tokens for messages"""
        with patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", False):
            estimator = TokenEstimator("gpt-4")
            messages = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
            count = estimator.estimate_messages_tokens(messages)
            assert count > 0  # Should include overhead

    def test_estimate_messages_tokens_empty(self):
        """Test estimating tokens for empty messages"""
        with patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", False):
            estimator = TokenEstimator("gpt-4")
            count = estimator.estimate_messages_tokens([])
            assert count == 0

    def test_estimate_messages_tokens_missing_fields(self):
        """Test estimating tokens for messages with missing fields"""
        with patch("backend.llm.token_estimator.TIKTOKEN_AVAILABLE", False):
            estimator = TokenEstimator("gpt-4")
            messages = [
                {"role": "user"},  # Missing content
                {"content": "Hello"},  # Missing role
            ]
            count = estimator.estimate_messages_tokens(messages)
            assert count >= 0
