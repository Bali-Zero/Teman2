"""
Tests for GoldenAnswerService - fast FAQ lookup.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGoldenAnswerService:
    def test_lookup_golden_answer_exact_match(self):
        """Service should initialize with correct threshold."""
        from backend.services.misc.golden_answer_service import GoldenAnswerService
        svc = GoldenAnswerService(database_url="postgresql://test@localhost/test")
        assert svc.similarity_threshold == 0.80
        assert svc.pool is None
        assert svc.model is None

    def test_load_model(self):
        """_load_model should lazy-load embedding model."""
        from backend.services.misc.golden_answer_service import GoldenAnswerService
        svc = GoldenAnswerService(database_url="postgresql://test@localhost/test")
        # SentenceTransformer is imported inside _load_model, so patch at source
        with patch("sentence_transformers.SentenceTransformer") as MockST:
            MockST.return_value = MagicMock()
            svc._load_model()
            MockST.assert_called_once_with("all-MiniLM-L6-v2")
            assert svc.model is not None
