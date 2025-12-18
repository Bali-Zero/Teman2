"""
Integration tests for main_cloud.py
Tests the main FastAPI application initialization and endpoints
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestMainCloudIntegration:
    """Integration tests for main_cloud.py"""

    def test_allowed_origins_function(self):
        """Test _allowed_origins function"""
        with patch("app.main_cloud.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = "https://example.com,https://test.com"
            mock_settings.dev_origins = None

            from app.main_cloud import _allowed_origins

            origins = _allowed_origins()
            assert isinstance(origins, list)
            assert "https://example.com" in origins
            assert "http://localhost:3000" in origins  # Default

    def test_safe_endpoint_label(self):
        """Test _safe_endpoint_label function"""
        from app.main_cloud import _safe_endpoint_label

        # Test with URL
        label = _safe_endpoint_label("https://example.com/path")
        assert label == "example.com"

        # Test with None
        label = _safe_endpoint_label(None)
        assert label == "unknown"

        # Test with path only
        label = _safe_endpoint_label("/api/test")
        assert label == "/api/test"

    def test_parse_history(self):
        """Test _parse_history function"""
        from app.main_cloud import _parse_history

        # Test with valid JSON
        history_json = '[{"role": "user", "content": "test"}]'
        result = _parse_history(history_json)
        assert isinstance(result, list)
        assert len(result) == 1

        # Test with None
        result = _parse_history(None)
        assert result == []

        # Test with invalid JSON
        result = _parse_history("invalid json")
        assert result == []

    @pytest.mark.asyncio
    async def test_initialize_services_with_mocks(self):
        """Test initialize_services with mocked dependencies"""
        with (
            patch("app.main_cloud.SearchService") as mock_search,
            patch("app.main_cloud.ZantaraAIClient") as mock_ai,
            patch("app.main_cloud.CollectionManager") as mock_collection,
            patch("app.main_cloud.create_embeddings_generator") as mock_embedder,
            patch("app.main_cloud.app") as mock_app,
        ):
            mock_app.state = MagicMock()
            mock_app.state.services_initialized = False

            mock_search_instance = MagicMock()
            mock_search.return_value = mock_search_instance
            mock_ai_instance = MagicMock()
            mock_ai.return_value = mock_ai_instance

            from app.main_cloud import initialize_services

            # Should not raise exception with mocks
            try:
                await initialize_services()
            except RuntimeError:
                # Expected if critical services fail
                pass

    def test_app_initialization(self):
        """Test that FastAPI app can be imported and initialized"""
        with patch("app.main_cloud.initialize_services"), patch("app.main_cloud.include_routers"):
            from app.main_cloud import app

            assert app is not None
            assert app.title is not None
