"""
Unit tests for media router - targeting 90% coverage

Tests cover:
1. Image generation endpoint (success, various failures, edge cases)
2. File upload endpoint (success, failures, edge cases)
3. Error handling and logging
"""

import sys
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def app():
    """Create test FastAPI app with media router"""
    app = FastAPI()
    from app.routers.media import router
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_image_service():
    """Mock ImageGenerationService"""
    service = AsyncMock()
    service.generate_image = AsyncMock()
    return service


# ============================================================================
# TESTS FOR /media/generate-image ENDPOINT
# ============================================================================


class TestGenerateImageEndpoint:
    """Tests for POST /media/generate-image"""

    @pytest.mark.asyncio
    async def test_generate_image_success(self, client, mock_image_service):
        """Test successful image generation"""
        mock_image_service.generate_image.return_value = {
            "success": True,
            "url": "https://image.pollinations.ai/prompt/sunset",
            "prompt": "a beautiful sunset",
            "service": "pollinations_fallback",
        }

        with patch("app.routers.media.ImageGenerationService", return_value=mock_image_service):
            response = client.post(
                "/media/generate-image",
                json={"prompt": "a beautiful sunset"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["url"] == "https://image.pollinations.ai/prompt/sunset"
        assert data["prompt"] == "a beautiful sunset"
        assert data["service"] == "pollinations_fallback"
        mock_image_service.generate_image.assert_called_once_with("a beautiful sunset")

    @pytest.mark.asyncio
    async def test_generate_image_service_not_configured(self, client, mock_image_service):
        """Test image generation when service is not configured"""
        mock_image_service.generate_image.return_value = {
            "success": False,
            "error": "Image generation service not configured",
            "details": "GOOGLE_API_KEY environment variable required",
        }

        with patch("app.routers.media.ImageGenerationService", return_value=mock_image_service):
            response = client.post(
                "/media/generate-image",
                json={"prompt": "test prompt"}
            )

        assert response.status_code == 503
        data = response.json()
        assert "not configured" in data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_generate_image_invalid_prompt(self, client, mock_image_service):
        """Test image generation with invalid prompt"""
        mock_image_service.generate_image.return_value = {
            "success": False,
            "error": "Invalid prompt",
            "details": "Prompt cannot be empty",
        }

        with patch("app.routers.media.ImageGenerationService", return_value=mock_image_service):
            response = client.post(
                "/media/generate-image",
                json={"prompt": ""}
            )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid prompt" in data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_generate_image_generic_error(self, client, mock_image_service):
        """Test image generation with generic service error"""
        mock_image_service.generate_image.return_value = {
            "success": False,
            "error": "Image generation failed",
            "details": "Network timeout",
        }

        with patch("app.routers.media.ImageGenerationService", return_value=mock_image_service):
            response = client.post(
                "/media/generate-image",
                json={"prompt": "test prompt"}
            )

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["success"] is False
        assert "Image generation failed" in data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_generate_image_exception_handling(self, client, mock_image_service):
        """Test exception handling during image generation"""
        mock_image_service.generate_image.side_effect = RuntimeError("Unexpected error")

        with patch("app.routers.media.ImageGenerationService", return_value=mock_image_service):
            response = client.post(
                "/media/generate-image",
                json={"prompt": "test prompt"}
            )

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["success"] is False
        assert data["detail"]["error"] == "Internal server error"
        assert "Unexpected error" in data["detail"]["details"]

    @pytest.mark.asyncio
    async def test_generate_image_missing_optional_fields(self, client, mock_image_service):
        """Test response when optional fields are missing"""
        mock_image_service.generate_image.return_value = {
            "success": True,
            "url": "https://example.com/image.png",
            # prompt and service fields missing
        }

        with patch("app.routers.media.ImageGenerationService", return_value=mock_image_service):
            response = client.post(
                "/media/generate-image",
                json={"prompt": "test"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["url"] == "https://example.com/image.png"
        assert data["prompt"] is None  # Uses .get() with no default
        assert data["service"] == "unknown"  # Has default value

    @pytest.mark.asyncio
    async def test_generate_image_long_prompt(self, client, mock_image_service):
        """Test image generation with a very long prompt"""
        long_prompt = "a " * 1000  # Very long prompt
        mock_image_service.generate_image.return_value = {
            "success": True,
            "url": "https://image.pollinations.ai/prompt/test",
            "prompt": long_prompt,
            "service": "pollinations_fallback",
        }

        with patch("app.routers.media.ImageGenerationService", return_value=mock_image_service):
            response = client.post(
                "/media/generate-image",
                json={"prompt": long_prompt}
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_generate_image_special_characters(self, client, mock_image_service):
        """Test image generation with special characters in prompt"""
        special_prompt = "a sunset 🌅 with émojis & spëcial çharacters!"
        mock_image_service.generate_image.return_value = {
            "success": True,
            "url": "https://image.pollinations.ai/prompt/test",
            "prompt": special_prompt,
            "service": "pollinations_fallback",
        }

        with patch("app.routers.media.ImageGenerationService", return_value=mock_image_service):
            response = client.post(
                "/media/generate-image",
                json={"prompt": special_prompt}
            )

        assert response.status_code == 200
        mock_image_service.generate_image.assert_called_once_with(special_prompt)

    @pytest.mark.asyncio
    async def test_generate_image_invalid_request_body(self, client):
        """Test with invalid request body"""
        response = client.post(
            "/media/generate-image",
            json={"wrong_field": "value"}
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_generate_image_empty_request_body(self, client):
        """Test with empty request body"""
        response = client.post(
            "/media/generate-image",
            json={}
        )

        assert response.status_code == 422  # Validation error


# ============================================================================
# TESTS FOR /media/upload ENDPOINT
# ============================================================================


class TestUploadFileEndpoint:
    """Tests for POST /media/upload"""

    def test_upload_file_success(self, client):
        """Test successful file upload"""
        # Create a temporary file
        file_content = b"test image content"
        files = {"file": ("test_image.jpg", BytesIO(file_content), "image/jpeg")}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock Path class to return proper extension
            mock_path_instance = MagicMock()
            mock_path_instance.suffix = ".jpg"
            mock_path_instance.mkdir = MagicMock()
            mock_file_path = MagicMock()

            with patch("app.routers.media.Path") as mock_path_class:
                # Mock the Path("static/uploads") call
                mock_path_class.return_value = mock_path_instance
                mock_path_instance.__truediv__ = MagicMock(return_value=mock_file_path)

                # Mock Path(file.filename) call for suffix extraction
                def path_side_effect(arg):
                    if arg == "test_image.jpg":
                        mock = MagicMock()
                        mock.suffix = ".jpg"
                        return mock
                    return mock_path_instance

                mock_path_class.side_effect = path_side_effect

                with patch("app.routers.media.uuid.uuid4") as mock_uuid:
                    mock_uuid.return_value = "test-uuid"
                    with patch("builtins.open", create=True) as mock_open:
                        with patch("app.routers.media.shutil.copyfileobj") as mock_copy:
                            mock_file = MagicMock()
                            mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
                            mock_open.return_value.__exit__ = MagicMock(return_value=False)

                            response = client.post("/media/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["filename"] == "test_image.jpg"
        assert data["url"] == "/static/uploads/test-uuid.jpg"
        assert data["type"] == "image/jpeg"

    def test_upload_file_png(self, client):
        """Test uploading PNG file"""
        file_content = b"fake png content"
        files = {"file": ("image.png", BytesIO(file_content), "image/png")}

        mock_path_instance = MagicMock()
        mock_path_instance.mkdir = MagicMock()
        mock_file_path = MagicMock()

        with patch("app.routers.media.Path") as mock_path_class:
            def path_side_effect(arg):
                if arg == "image.png":
                    mock = MagicMock()
                    mock.suffix = ".png"
                    return mock
                return mock_path_instance

            mock_path_class.side_effect = path_side_effect
            mock_path_instance.__truediv__ = MagicMock(return_value=mock_file_path)

            with patch("app.routers.media.uuid.uuid4") as mock_uuid:
                mock_uuid.return_value = "test-uuid-2"
                with patch("builtins.open", create=True) as mock_open:
                    with patch("app.routers.media.shutil.copyfileobj"):
                        mock_file = MagicMock()
                        mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
                        mock_open.return_value.__exit__ = MagicMock(return_value=False)

                        response = client.post("/media/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "/static/uploads/test-uuid-2.png"
        assert data["type"] == "image/png"

    def test_upload_file_no_extension(self, client):
        """Test uploading file without extension"""
        file_content = b"file content"
        files = {"file": ("filename_no_ext", BytesIO(file_content), "application/octet-stream")}

        mock_path_instance = MagicMock()
        mock_path_instance.mkdir = MagicMock()
        mock_file_path = MagicMock()

        with patch("app.routers.media.Path") as mock_path_class:
            def path_side_effect(arg):
                if arg == "filename_no_ext":
                    mock = MagicMock()
                    mock.suffix = ""
                    return mock
                return mock_path_instance

            mock_path_class.side_effect = path_side_effect
            mock_path_instance.__truediv__ = MagicMock(return_value=mock_file_path)

            with patch("app.routers.media.uuid.uuid4") as mock_uuid:
                mock_uuid.return_value = "test-uuid-3"
                with patch("builtins.open", create=True) as mock_open:
                    with patch("app.routers.media.shutil.copyfileobj"):
                        mock_file = MagicMock()
                        mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
                        mock_open.return_value.__exit__ = MagicMock(return_value=False)

                        response = client.post("/media/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "/static/uploads/test-uuid-3"  # No extension

    def test_upload_file_pdf(self, client):
        """Test uploading PDF document"""
        file_content = b"fake pdf content"
        files = {"file": ("document.pdf", BytesIO(file_content), "application/pdf")}

        mock_path_instance = MagicMock()
        mock_path_instance.mkdir = MagicMock()
        mock_file_path = MagicMock()

        with patch("app.routers.media.Path") as mock_path_class:
            def path_side_effect(arg):
                if arg == "document.pdf":
                    mock = MagicMock()
                    mock.suffix = ".pdf"
                    return mock
                return mock_path_instance

            mock_path_class.side_effect = path_side_effect
            mock_path_instance.__truediv__ = MagicMock(return_value=mock_file_path)

            with patch("app.routers.media.uuid.uuid4") as mock_uuid:
                mock_uuid.return_value = "test-uuid-pdf"
                with patch("builtins.open", create=True) as mock_open:
                    with patch("app.routers.media.shutil.copyfileobj"):
                        mock_file = MagicMock()
                        mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
                        mock_open.return_value.__exit__ = MagicMock(return_value=False)

                        response = client.post("/media/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "/static/uploads/test-uuid-pdf.pdf"
        assert data["type"] == "application/pdf"

    def test_upload_file_audio(self, client):
        """Test uploading audio file"""
        file_content = b"fake audio content"
        files = {"file": ("audio.mp3", BytesIO(file_content), "audio/mpeg")}

        mock_path_instance = MagicMock()
        mock_path_instance.mkdir = MagicMock()
        mock_file_path = MagicMock()

        with patch("app.routers.media.Path") as mock_path_class:
            def path_side_effect(arg):
                if arg == "audio.mp3":
                    mock = MagicMock()
                    mock.suffix = ".mp3"
                    return mock
                return mock_path_instance

            mock_path_class.side_effect = path_side_effect
            mock_path_instance.__truediv__ = MagicMock(return_value=mock_file_path)

            with patch("app.routers.media.uuid.uuid4") as mock_uuid:
                mock_uuid.return_value = "test-uuid-audio"
                with patch("builtins.open", create=True) as mock_open:
                    with patch("app.routers.media.shutil.copyfileobj"):
                        mock_file = MagicMock()
                        mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
                        mock_open.return_value.__exit__ = MagicMock(return_value=False)

                        response = client.post("/media/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "/static/uploads/test-uuid-audio.mp3"
        assert data["type"] == "audio/mpeg"

    def test_upload_file_creates_directory(self, client):
        """Test that upload creates directory if it doesn't exist"""
        file_content = b"test content"
        files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}

        with patch("app.routers.media.Path") as mock_path_class:
            mock_upload_dir = MagicMock()
            mock_path_class.return_value = mock_upload_dir
            mock_file_path = MagicMock()
            mock_upload_dir.__truediv__ = MagicMock(return_value=mock_file_path)

            with patch("app.routers.media.uuid.uuid4", return_value="test-uuid"):
                with patch("builtins.open", create=True) as mock_open:
                    with patch("app.routers.media.shutil.copyfileobj"):
                        mock_file = MagicMock()
                        mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
                        mock_open.return_value.__exit__ = MagicMock(return_value=False)

                        response = client.post("/media/upload", files=files)

        # Verify directory creation was called
        mock_upload_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        assert response.status_code == 200

    def test_upload_file_io_error(self, client):
        """Test handling of IO error during file upload"""
        file_content = b"test content"
        files = {"file": ("test.jpg", BytesIO(file_content), "image/jpeg")}

        with patch("app.routers.media.Path") as mock_path:
            mock_upload_dir = MagicMock()
            mock_upload_dir.mkdir = MagicMock()
            mock_file_path = MagicMock()

            mock_path.return_value = mock_upload_dir
            mock_upload_dir.__truediv__ = MagicMock(return_value=mock_file_path)

            with patch("builtins.open", side_effect=IOError("Disk full")):
                response = client.post("/media/upload", files=files)

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["success"] is False
        assert data["detail"]["error"] == "Upload failed"
        assert "Disk full" in data["detail"]["details"]

    def test_upload_file_permission_error(self, client):
        """Test handling of permission error during file upload"""
        file_content = b"test content"
        files = {"file": ("test.jpg", BytesIO(file_content), "image/jpeg")}

        with patch("app.routers.media.Path") as mock_path:
            mock_upload_dir = MagicMock()
            mock_upload_dir.mkdir.side_effect = PermissionError("Access denied")
            mock_path.return_value = mock_upload_dir

            response = client.post("/media/upload", files=files)

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["success"] is False
        assert "Access denied" in data["detail"]["details"]

    def test_upload_file_copyfileobj_error(self, client):
        """Test handling of error during file copy operation"""
        file_content = b"test content"
        files = {"file": ("test.jpg", BytesIO(file_content), "image/jpeg")}

        with patch("app.routers.media.Path") as mock_path:
            mock_upload_dir = MagicMock()
            mock_upload_dir.mkdir = MagicMock()
            mock_file_path = MagicMock()

            mock_path.return_value = mock_upload_dir
            mock_upload_dir.__truediv__ = MagicMock(return_value=mock_file_path)

            with patch("builtins.open", create=True) as mock_open:
                with patch("app.routers.media.shutil.copyfileobj", side_effect=OSError("Copy failed")):
                    mock_file = MagicMock()
                    mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
                    mock_open.return_value.__exit__ = MagicMock(return_value=False)

                    response = client.post("/media/upload", files=files)

        assert response.status_code == 500
        data = response.json()
        assert "Copy failed" in data["detail"]["details"]

    def test_upload_file_no_file_provided(self, client):
        """Test upload endpoint with no file"""
        response = client.post("/media/upload")
        assert response.status_code == 422  # Validation error

    def test_upload_file_large_file(self, client):
        """Test uploading a large file"""
        # Simulate a large file (10MB)
        file_content = b"x" * (10 * 1024 * 1024)
        files = {"file": ("large_file.bin", BytesIO(file_content), "application/octet-stream")}

        with patch("app.routers.media.Path") as mock_path:
            mock_upload_dir = MagicMock()
            mock_upload_dir.mkdir = MagicMock()
            mock_file_path = MagicMock()

            mock_path.return_value = mock_upload_dir
            mock_upload_dir.__truediv__ = MagicMock(return_value=mock_file_path)

            with patch("app.routers.media.uuid.uuid4", return_value="large-uuid"):
                with patch("builtins.open", create=True) as mock_open:
                    with patch("app.routers.media.shutil.copyfileobj"):
                        mock_file = MagicMock()
                        mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
                        mock_open.return_value.__exit__ = MagicMock(return_value=False)

                        response = client.post("/media/upload", files=files)

        assert response.status_code == 200


# ============================================================================
# TESTS FOR MODEL VALIDATION
# ============================================================================


class TestImagePromptModel:
    """Tests for ImagePrompt Pydantic model"""

    def test_image_prompt_valid(self):
        """Test valid ImagePrompt creation"""
        from app.routers.media import ImagePrompt

        prompt = ImagePrompt(prompt="test prompt")
        assert prompt.prompt == "test prompt"

    def test_image_prompt_empty_string(self):
        """Test ImagePrompt with empty string (valid for Pydantic)"""
        from app.routers.media import ImagePrompt

        prompt = ImagePrompt(prompt="")
        assert prompt.prompt == ""

    def test_image_prompt_missing_field(self):
        """Test ImagePrompt with missing field"""
        from app.routers.media import ImagePrompt
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ImagePrompt()

    def test_image_prompt_extra_field(self):
        """Test ImagePrompt ignores extra fields by default"""
        from app.routers.media import ImagePrompt

        # Pydantic v2 allows extra fields by default unless forbidden
        prompt = ImagePrompt(prompt="test", extra_field="ignored")
        assert prompt.prompt == "test"


# ============================================================================
# TESTS FOR LOGGING
# ============================================================================


class TestLogging:
    """Tests for logging behavior"""

    @pytest.mark.asyncio
    async def test_generate_image_logs_error_on_exception(self, client, mock_image_service):
        """Test that errors are logged during image generation"""
        mock_image_service.generate_image.side_effect = RuntimeError("Test error")

        with patch("app.routers.media.ImageGenerationService", return_value=mock_image_service):
            with patch("app.routers.media.logger") as mock_logger:
                response = client.post(
                    "/media/generate-image",
                    json={"prompt": "test"}
                )

        assert response.status_code == 500
        # Verify logger.error was called
        assert mock_logger.error.called
        call_args = str(mock_logger.error.call_args)
        assert "Image generation error" in call_args

    def test_upload_file_logs_error_on_exception(self, client):
        """Test that errors are logged during file upload"""
        file_content = b"test"
        files = {"file": ("test.jpg", BytesIO(file_content), "image/jpeg")}

        with patch("app.routers.media.Path") as mock_path:
            mock_upload_dir = MagicMock()
            mock_upload_dir.mkdir.side_effect = RuntimeError("Test error")
            mock_path.return_value = mock_upload_dir

            with patch("app.routers.media.logger") as mock_logger:
                response = client.post("/media/upload", files=files)

        assert response.status_code == 500
        # Verify logger.error was called
        assert mock_logger.error.called
        call_args = str(mock_logger.error.call_args)
        assert "File upload error" in call_args


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestRouterIntegration:
    """Integration tests for the media router"""

    def test_router_prefix_and_tags(self):
        """Test that router has correct prefix and tags"""
        from app.routers.media import router

        assert router.prefix == "/media"
        assert "media" in router.tags

    def test_router_has_required_endpoints(self):
        """Test that router has all required endpoints"""
        from app.routers.media import router

        routes = [route.path for route in router.routes]
        # Routes include the prefix
        assert "/media/generate-image" in routes
        assert "/media/upload" in routes

    def test_generate_image_endpoint_method(self):
        """Test that generate-image endpoint accepts POST"""
        from app.routers.media import router

        route = next(r for r in router.routes if r.path == "/media/generate-image")
        assert "POST" in route.methods

    def test_upload_endpoint_method(self):
        """Test that upload endpoint accepts POST"""
        from app.routers.media import router

        route = next(r for r in router.routes if r.path == "/media/upload")
        assert "POST" in route.methods
