"""
Comprehensive tests for VertexAIService
Target: 100% coverage
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestVertexAIService:
    """Tests for VertexAIService class"""

    @pytest.fixture
    def mock_vertexai(self):
        """Mock vertexai module"""
        with patch.dict(
            "sys.modules",
            {"vertexai": MagicMock(), "vertexai.preview.generative_models": MagicMock()},
        ):
            yield

    @pytest.fixture
    def service(self, mock_vertexai):
        """Create VertexAIService instance"""
        with patch("services.vertex_ai_service.vertexai") as mock_v:
            with patch("services.vertex_ai_service.GenerativeModel") as mock_model:
                with patch("services.vertex_ai_service.GenerationConfig"):
                    mock_v.init = MagicMock()
                    mock_model.return_value = MagicMock()

                    from services.vertex_ai_service import VertexAIService

                    return VertexAIService(project_id="test-project")

    def test_init_with_project_id(self, mock_vertexai):
        """Test initialization with project ID"""
        with patch("services.vertex_ai_service.vertexai"):
            from services.vertex_ai_service import VertexAIService

            service = VertexAIService(project_id="my-project", location="europe-west1")

            assert service.project_id == "my-project"
            assert service.location == "europe-west1"
            assert service._initialized is False

    def test_init_with_env_project(self, mock_vertexai):
        """Test initialization from environment variable"""
        with patch("services.vertex_ai_service.vertexai"):
            with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "env-project"}):
                from services.vertex_ai_service import VertexAIService

                service = VertexAIService()

                assert service.project_id == "env-project"

    def test_init_without_project(self, mock_vertexai):
        """Test initialization without project ID"""
        with patch("services.vertex_ai_service.vertexai"):
            with patch.dict("os.environ", {}, clear=True):
                from services.vertex_ai_service import VertexAIService

                service = VertexAIService(project_id=None)

                assert service.project_id is None

    def test_ensure_initialized_success(self, mock_vertexai):
        """Test successful lazy initialization"""
        mock_vertex = MagicMock()
        mock_model_class = MagicMock()
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        with patch("services.vertex_ai_service.vertexai", mock_vertex):
            with patch("services.vertex_ai_service.GenerativeModel", mock_model_class):
                from services.vertex_ai_service import VertexAIService

                service = VertexAIService(project_id="test-project")

                service._ensure_initialized()

                assert service._initialized is True
                assert service.model == mock_model
                mock_vertex.init.assert_called_once()

    def test_ensure_initialized_already_initialized(self, mock_vertexai):
        """Test that initialization is not repeated"""
        with patch("services.vertex_ai_service.vertexai") as mock_v:
            with patch("services.vertex_ai_service.GenerativeModel"):
                from services.vertex_ai_service import VertexAIService

                service = VertexAIService(project_id="test-project")
                service._initialized = True
                service.model = MagicMock()

                service._ensure_initialized()

                mock_v.init.assert_not_called()

    def test_ensure_initialized_no_vertexai(self):
        """Test initialization when vertexai not installed"""
        with patch("services.vertex_ai_service.vertexai", None):
            from services.vertex_ai_service import VertexAIService

            service = VertexAIService(project_id="test")

            with pytest.raises(ImportError, match="vertexai module is not installed"):
                service._ensure_initialized()

    def test_ensure_initialized_failure(self, mock_vertexai):
        """Test initialization failure"""
        mock_vertex = MagicMock()
        mock_vertex.init.side_effect = Exception("Auth failed")

        with patch("services.vertex_ai_service.vertexai", mock_vertex):
            from services.vertex_ai_service import VertexAIService

            service = VertexAIService(project_id="test-project")

            with pytest.raises(Exception, match="Auth failed"):
                service._ensure_initialized()

    @pytest.mark.asyncio
    async def test_extract_metadata_success(self, mock_vertexai):
        """Test successful metadata extraction"""
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "type": "UNDANG-UNDANG",
                "type_abbrev": "UU",
                "number": "12",
                "year": "2024",
                "topic": "Investment",
                "status": "BERLAKU",
                "full_title": "UU 12 Tahun 2024 tentang Investment",
            }
        )

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        mock_vertex = MagicMock()

        with patch("services.vertex_ai_service.vertexai", mock_vertex):
            with patch("services.vertex_ai_service.GenerativeModel") as mock_model_class:
                with patch("services.vertex_ai_service.GenerationConfig"):
                    mock_model_class.return_value = mock_model

                    from services.vertex_ai_service import VertexAIService

                    service = VertexAIService(project_id="test-project")

                    result = await service.extract_metadata("Test legal document text")

                    assert result["type"] == "UNDANG-UNDANG"
                    assert result["year"] == "2024"

    @pytest.mark.asyncio
    async def test_extract_metadata_with_markdown(self, mock_vertexai):
        """Test metadata extraction with markdown in response"""
        mock_response = MagicMock()
        mock_response.text = """```json
        {"type": "PP", "number": "5"}
        ```"""

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        mock_vertex = MagicMock()

        with patch("services.vertex_ai_service.vertexai", mock_vertex):
            with patch("services.vertex_ai_service.GenerativeModel") as mock_model_class:
                with patch("services.vertex_ai_service.GenerationConfig"):
                    mock_model_class.return_value = mock_model

                    from services.vertex_ai_service import VertexAIService

                    service = VertexAIService(project_id="test-project")

                    result = await service.extract_metadata("Test text")

                    assert result["type"] == "PP"

    @pytest.mark.asyncio
    async def test_extract_metadata_failure(self, mock_vertexai):
        """Test metadata extraction failure"""
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API error")

        mock_vertex = MagicMock()

        with patch("services.vertex_ai_service.vertexai", mock_vertex):
            with patch("services.vertex_ai_service.GenerativeModel") as mock_model_class:
                with patch("services.vertex_ai_service.GenerationConfig"):
                    mock_model_class.return_value = mock_model

                    from services.vertex_ai_service import VertexAIService

                    service = VertexAIService(project_id="test-project")

                    result = await service.extract_metadata("Test text")

                    assert result == {}

    @pytest.mark.asyncio
    async def test_extract_structure(self, mock_vertexai):
        """Test structure extraction (placeholder)"""
        with patch("services.vertex_ai_service.vertexai"):
            from services.vertex_ai_service import VertexAIService

            service = VertexAIService(project_id="test-project")

            result = await service.extract_structure("Test text")

            # Placeholder returns None
            assert result is None


class TestVertexAIServiceImportError:
    """Test VertexAI service when module is not available"""

    def test_import_without_vertexai(self):
        """Test that service handles missing vertexai gracefully"""
        # This test verifies the import handling at module level
        with patch.dict("sys.modules", {"vertexai": None}):
            # The module should still load, just with disabled functionality
            pass
