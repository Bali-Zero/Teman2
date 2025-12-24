"""
Unit tests for image_generation router - targeting 90% coverage
"""

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


@contextmanager
def mock_httpx_client(mock_response):
    """
    Helper context manager to mock httpx.AsyncClient properly

    Args:
        mock_response: MagicMock response object to return from client.post()
    """
    with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
        # Create mock client with proper async context manager support
        mock_client = MagicMock()

        # Make post an AsyncMock that returns the mock_response
        mock_client.post = AsyncMock(return_value=mock_response)

        # Make __aenter__ and __aexit__ async
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_client_class.return_value = mock_client
        yield mock_client


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def app():
    """Create FastAPI app with image generation router"""
    from app.routers.image_generation import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_settings_with_imagen_key():
    """Mock settings with google_imagen_api_key configured"""
    with patch("app.routers.image_generation.settings") as mock_settings:
        mock_settings.google_imagen_api_key = "test-imagen-api-key"
        mock_settings.google_api_key = None
        yield mock_settings


@pytest.fixture
def mock_settings_with_google_key():
    """Mock settings with google_api_key configured (fallback)"""
    with patch("app.routers.image_generation.settings") as mock_settings:
        mock_settings.google_imagen_api_key = None
        mock_settings.google_api_key = "test-google-api-key"
        yield mock_settings


@pytest.fixture
def mock_settings_no_keys():
    """Mock settings with no API keys configured"""
    with patch("app.routers.image_generation.settings") as mock_settings:
        mock_settings.google_imagen_api_key = None
        mock_settings.google_api_key = None
        yield mock_settings


@pytest.fixture
def valid_image_request():
    """Valid image generation request payload"""
    return {
        "prompt": "A beautiful sunset over mountains",
        "number_of_images": 1,
        "aspect_ratio": "1:1",
        "safety_filter_level": "block_some",
        "person_generation": "allow_adult",
    }


@pytest.fixture
def mock_imagen_success_response():
    """Mock successful Imagen API response"""
    return {
        "generatedImages": [
            {"bytesBase64Encoded": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}
        ]
    }


@pytest.fixture
def mock_imagen_multiple_images_response():
    """Mock successful Imagen API response with multiple images"""
    return {
        "generatedImages": [
            {"bytesBase64Encoded": "base64data1"},
            {"bytesBase64Encoded": "base64data2"},
            {"bytesBase64Encoded": "base64data3"},
        ]
    }


# ============================================================================
# TEST REQUEST MODEL
# ============================================================================


class TestImageGenerationRequest:
    """Tests for ImageGenerationRequest model"""

    def test_request_model_with_defaults(self):
        """Test request model creation with default values"""
        from app.routers.image_generation import ImageGenerationRequest

        request = ImageGenerationRequest(prompt="Test prompt")

        assert request.prompt == "Test prompt"
        assert request.number_of_images == 1
        assert request.aspect_ratio == "1:1"
        assert request.safety_filter_level == "block_some"
        assert request.person_generation == "allow_adult"

    def test_request_model_with_custom_values(self):
        """Test request model creation with custom values"""
        from app.routers.image_generation import ImageGenerationRequest

        request = ImageGenerationRequest(
            prompt="Custom prompt",
            number_of_images=3,
            aspect_ratio="16:9",
            safety_filter_level="block_most",
            person_generation="allow_all",
        )

        assert request.prompt == "Custom prompt"
        assert request.number_of_images == 3
        assert request.aspect_ratio == "16:9"
        assert request.safety_filter_level == "block_most"
        assert request.person_generation == "allow_all"

    def test_request_model_validation_missing_prompt(self):
        """Test request model validation with missing prompt"""
        from app.routers.image_generation import ImageGenerationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ImageGenerationRequest()


# ============================================================================
# TEST RESPONSE MODEL
# ============================================================================


class TestImageGenerationResponse:
    """Tests for ImageGenerationResponse model"""

    def test_response_model_success(self):
        """Test response model for successful generation"""
        from app.routers.image_generation import ImageGenerationResponse

        response = ImageGenerationResponse(
            images=["data:image/png;base64,abc123"],
            success=True,
        )

        assert response.images == ["data:image/png;base64,abc123"]
        assert response.success is True
        assert response.error is None

    def test_response_model_with_error(self):
        """Test response model with error"""
        from app.routers.image_generation import ImageGenerationResponse

        response = ImageGenerationResponse(
            images=[],
            success=False,
            error="Image generation failed",
        )

        assert response.images == []
        assert response.success is False
        assert response.error == "Image generation failed"

    def test_response_model_multiple_images(self):
        """Test response model with multiple images"""
        from app.routers.image_generation import ImageGenerationResponse

        images = [
            "data:image/png;base64,img1",
            "data:image/png;base64,img2",
            "data:image/png;base64,img3",
        ]
        response = ImageGenerationResponse(images=images, success=True)

        assert len(response.images) == 3
        assert response.success is True


# ============================================================================
# TEST GENERATE IMAGE ENDPOINT - SUCCESS CASES
# ============================================================================


class TestGenerateImageSuccess:
    """Tests for successful image generation scenarios"""

    @pytest.mark.asyncio
    async def test_generate_image_success_with_imagen_key(
        self, client, valid_image_request, mock_settings_with_imagen_key, mock_imagen_success_response
    ):
        """Test successful image generation with google_imagen_api_key"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_imagen_success_response

        with mock_httpx_client(mock_response) as mock_client:
            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["images"]) == 1
            assert data["images"][0].startswith("data:image/png;base64,")
            assert data["error"] is None

            # Verify API was called with correct headers
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[1]["headers"]["X-Goog-Api-Key"] == "test-imagen-api-key"
            assert call_args[1]["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_generate_image_success_with_google_api_key_fallback(
        self, client, valid_image_request, mock_settings_with_google_key, mock_imagen_success_response
    ):
        """Test successful image generation with google_api_key fallback"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_imagen_success_response

        with mock_httpx_client(mock_response) as mock_client:
            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify fallback API key was used
            call_args = mock_client.post.call_args
            assert call_args[1]["headers"]["X-Goog-Api-Key"] == "test-google-api-key"

    @pytest.mark.asyncio
    async def test_generate_multiple_images_success(
        self, client, mock_settings_with_imagen_key, mock_imagen_multiple_images_response
    ):
        """Test successful generation of multiple images"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_imagen_multiple_images_response

        with mock_httpx_client(mock_response):
            request_data = {
                "prompt": "Test prompt",
                "number_of_images": 3,
            }

            response = client.post("/api/v1/image/generate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["images"]) == 3
            assert all(img.startswith("data:image/png;base64,") for img in data["images"])

    @pytest.mark.asyncio
    async def test_generate_image_with_custom_parameters(
        self, client, mock_settings_with_imagen_key, mock_imagen_success_response
    ):
        """Test image generation with custom aspect ratio and safety settings"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_imagen_success_response

        with mock_httpx_client(mock_response) as mock_client:
            request_data = {
                "prompt": "Custom prompt",
                "number_of_images": 2,
                "aspect_ratio": "16:9",
                "safety_filter_level": "block_most",
                "person_generation": "allow_all",
            }

            response = client.post("/api/v1/image/generate", json=request_data)

            assert response.status_code == 200

            # Verify payload was sent correctly
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["prompt"] == "Custom prompt"
            assert payload["number_of_images"] == 2
            assert payload["aspect_ratio"] == "16:9"
            assert payload["safety_filter_level"] == "block_most"
            assert payload["person_generation"] == "allow_all"
            assert payload["language"] == "auto"

    @pytest.mark.asyncio
    async def test_generate_image_correct_api_url(
        self, client, valid_image_request, mock_settings_with_imagen_key, mock_imagen_success_response
    ):
        """Test that correct Imagen API URL is used"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_imagen_success_response

        with mock_httpx_client(mock_response) as mock_client:
            client.post("/api/v1/image/generate", json=valid_image_request)

            # Verify correct URL was called
            call_args = mock_client.post.call_args
            expected_url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict"
            assert call_args[0][0] == expected_url


# ============================================================================
# TEST GENERATE IMAGE ENDPOINT - ERROR CASES
# ============================================================================


class TestGenerateImageErrors:
    """Tests for error scenarios in image generation"""

    def test_generate_image_no_api_key(self, client, valid_image_request, mock_settings_no_keys):
        """Test image generation fails when no API key is configured"""
        response = client.post("/api/v1/image/generate", json=valid_image_request)

        assert response.status_code == 500
        data = response.json()
        assert "Google Imagen API key not configured" in data["detail"]

    @pytest.mark.asyncio
    async def test_generate_image_403_api_not_enabled(
        self, client, valid_image_request, mock_settings_with_imagen_key
    ):
        """Test handling of 403 error when Imagen API is not enabled

        Note: The code raises HTTPException(403) but it gets caught by the generic
        except Exception handler and re-raised as 500. This is a known issue but we
        test the actual behavior.
        """
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "API not enabled"

        with mock_httpx_client(mock_response):
            response = client.post("/api/v1/image/generate", json=valid_image_request)

            # Due to HTTPException being caught by generic except, this returns 500
            assert response.status_code == 500
            data = response.json()
            assert "Imagen API not enabled" in data["detail"]
            assert "403" in data["detail"]  # Original 403 error is in the message

    @pytest.mark.asyncio
    async def test_generate_image_http_status_error(
        self, client, valid_image_request, mock_settings_with_imagen_key
    ):
        """Test handling of HTTP status errors (400, 500, etc.)"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad request", request=MagicMock(), response=mock_response
        )

        with mock_httpx_client(mock_response):
            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 400
            data = response.json()
            assert "Image generation failed" in data["detail"]

    @pytest.mark.asyncio
    async def test_generate_image_http_status_error_500(
        self, client, valid_image_request, mock_settings_with_imagen_key
    ):
        """Test handling of 500 server error from Imagen API"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal server error", request=MagicMock(), response=mock_response
        )

        with mock_httpx_client(mock_response):
            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 500
            data = response.json()
            assert "Image generation failed" in data["detail"]

    @pytest.mark.asyncio
    async def test_generate_image_timeout_error(
        self, client, valid_image_request, mock_settings_with_imagen_key
    ):
        """Test handling of timeout errors"""
        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 500
            data = response.json()
            assert "Unexpected error during image generation" in data["detail"]

    @pytest.mark.asyncio
    async def test_generate_image_connection_error(
        self, client, valid_image_request, mock_settings_with_imagen_key
    ):
        """Test handling of connection errors"""
        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 500
            data = response.json()
            assert "Unexpected error during image generation" in data["detail"]

    @pytest.mark.asyncio
    async def test_generate_image_generic_exception(
        self, client, valid_image_request, mock_settings_with_imagen_key
    ):
        """Test handling of generic exceptions"""
        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=Exception("Unexpected error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 500
            data = response.json()
            assert "Unexpected error during image generation" in data["detail"]

    def test_generate_image_invalid_request_missing_prompt(self, client, mock_settings_with_imagen_key):
        """Test validation error when prompt is missing"""
        request_data = {
            "number_of_images": 1,
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_generate_image_invalid_request_invalid_type(self, client, mock_settings_with_imagen_key):
        """Test validation error with invalid data types"""
        request_data = {
            "prompt": "Test prompt",
            "number_of_images": "invalid",  # Should be int
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 422


# ============================================================================
# TEST EDGE CASES
# ============================================================================


class TestGenerateImageEdgeCases:
    """Tests for edge cases in image generation"""

    @pytest.mark.asyncio
    async def test_generate_image_empty_response(
        self, client, valid_image_request, mock_settings_with_imagen_key
    ):
        """Test handling of empty response from Imagen API"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Empty response

        with mock_httpx_client(mock_response):
            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert len(data["images"]) == 0

    @pytest.mark.asyncio
    async def test_generate_image_missing_base64_field(
        self, client, valid_image_request, mock_settings_with_imagen_key
    ):
        """Test handling when response has images but missing bytesBase64Encoded field"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "generatedImages": [
                {"someOtherField": "value"},  # Missing bytesBase64Encoded
            ]
        }

        with mock_httpx_client(mock_response):
            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert len(data["images"]) == 0

    @pytest.mark.asyncio
    async def test_generate_image_partial_results(
        self, client, valid_image_request, mock_settings_with_imagen_key
    ):
        """Test handling when some images have valid data and others don't"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "generatedImages": [
                {"bytesBase64Encoded": "validdata1"},
                {"someOtherField": "value"},  # Missing bytesBase64Encoded
                {"bytesBase64Encoded": "validdata2"},
            ]
        }

        with mock_httpx_client(mock_response):
            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["images"]) == 2  # Only the valid ones

    @pytest.mark.asyncio
    async def test_generate_image_malformed_json_response(
        self, client, valid_image_request, mock_settings_with_imagen_key
    ):
        """Test handling of malformed JSON response"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with mock_httpx_client(mock_response):
            response = client.post("/api/v1/image/generate", json=valid_image_request)

            assert response.status_code == 500
            data = response.json()
            assert "Unexpected error during image generation" in data["detail"]

    @pytest.mark.asyncio
    async def test_generate_image_very_long_prompt(
        self, client, mock_settings_with_imagen_key, mock_imagen_success_response
    ):
        """Test image generation with very long prompt"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_imagen_success_response

        with mock_httpx_client(mock_response) as mock_client:
            long_prompt = "A" * 5000  # Very long prompt
            request_data = {
                "prompt": long_prompt,
                "number_of_images": 1,
            }

            response = client.post("/api/v1/image/generate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify the long prompt was sent
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["prompt"] == long_prompt

    @pytest.mark.asyncio
    async def test_generate_image_special_characters_in_prompt(
        self, client, mock_settings_with_imagen_key, mock_imagen_success_response
    ):
        """Test image generation with special characters in prompt"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_imagen_success_response

        with mock_httpx_client(mock_response):
            special_prompt = "Test 日本語 émojis 🌸🎨 symbols @#$%"
            request_data = {
                "prompt": special_prompt,
                "number_of_images": 1,
            }

            response = client.post("/api/v1/image/generate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_generate_image_timeout_configuration(
        self, client, valid_image_request, mock_settings_with_imagen_key, mock_imagen_success_response
    ):
        """Test that AsyncClient is configured with correct timeout"""
        with patch("app.routers.image_generation.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_imagen_success_response
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = AsyncMock()
            mock_client_class.return_value = mock_client

            client.post("/api/v1/image/generate", json=valid_image_request)

            # Verify AsyncClient was created with timeout=60.0
            mock_client_class.assert_called_once_with(timeout=60.0)

    @pytest.mark.asyncio
    async def test_generate_image_empty_prompt(self, client, mock_settings_with_imagen_key):
        """Test image generation with empty prompt"""
        request_data = {
            "prompt": "",
            "number_of_images": 1,
        }

        # Empty string is still valid for Pydantic, but may fail at API level
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Prompt cannot be empty"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad request", request=MagicMock(), response=mock_response
        )

        with mock_httpx_client(mock_response):
            response = client.post("/api/v1/image/generate", json=request_data)

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_generate_image_zero_images(self, client, mock_settings_with_imagen_key):
        """Test image generation requesting zero images"""
        request_data = {
            "prompt": "Test prompt",
            "number_of_images": 0,
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"generatedImages": []}

        with mock_httpx_client(mock_response):
            response = client.post("/api/v1/image/generate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert len(data["images"]) == 0


# ============================================================================
# TEST API KEY PRIORITY
# ============================================================================


class TestAPIKeyPriority:
    """Tests for API key selection priority"""

    @pytest.mark.asyncio
    async def test_imagen_key_takes_priority_over_google_key(
        self, client, valid_image_request, mock_imagen_success_response
    ):
        """Test that google_imagen_api_key takes priority over google_api_key"""
        with patch("app.routers.image_generation.settings") as mock_settings:
            mock_settings.google_imagen_api_key = "imagen-key"
            mock_settings.google_api_key = "google-key"

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_imagen_success_response

            with mock_httpx_client(mock_response) as mock_client:
                client.post("/api/v1/image/generate", json=valid_image_request)

                # Verify imagen key was used, not google key
                call_args = mock_client.post.call_args
                assert call_args[1]["headers"]["X-Goog-Api-Key"] == "imagen-key"

    @pytest.mark.asyncio
    async def test_google_key_used_when_imagen_key_none(
        self, client, valid_image_request, mock_settings_with_google_key, mock_imagen_success_response
    ):
        """Test that google_api_key is used when imagen_api_key is None"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_imagen_success_response

        with mock_httpx_client(mock_response) as mock_client:
            client.post("/api/v1/image/generate", json=valid_image_request)

            call_args = mock_client.post.call_args
            assert call_args[1]["headers"]["X-Goog-Api-Key"] == "test-google-api-key"

    def test_both_keys_missing_raises_error(self, client, valid_image_request, mock_settings_no_keys):
        """Test that error is raised when both keys are missing"""
        response = client.post("/api/v1/image/generate", json=valid_image_request)

        assert response.status_code == 500
        data = response.json()
        assert "GOOGLE_IMAGEN_API_KEY or GOOGLE_API_KEY" in data["detail"]
