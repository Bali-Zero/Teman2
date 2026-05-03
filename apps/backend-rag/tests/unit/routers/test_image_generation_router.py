"""
Unit tests for image_generation router - Pollinations.ai (free, no API key)

UPDATED 2026-04-10: Rewritten to match current Pollinations-only implementation.
Old tests targeted Google Imagen API which was removed on 2026-04-08.
"""

from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def app():
    """Create FastAPI app with image generation router"""
    from backend.app.routers.image_generation import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def valid_image_request():
    """Valid image generation request payload"""
    return {
        "prompt": "A beautiful sunset over mountains",
        "number_of_images": 1,
        "aspect_ratio": "1:1",
    }


# ============================================================================
# TEST REQUEST MODEL
# ============================================================================


class TestImageGenerationRequest:
    """Tests for ImageGenerationRequest model"""

    def test_request_model_with_defaults(self):
        """Test request model creation with default values"""
        from backend.app.routers.image_generation import ImageGenerationRequest

        request = ImageGenerationRequest(prompt="Test prompt")

        assert request.prompt == "Test prompt"
        assert request.number_of_images == 1
        assert request.aspect_ratio == "1:1"

    def test_request_model_with_custom_values(self):
        """Test request model creation with custom values"""
        from backend.app.routers.image_generation import ImageGenerationRequest

        request = ImageGenerationRequest(
            prompt="Custom prompt",
            number_of_images=3,
            aspect_ratio="16:9",
        )

        assert request.prompt == "Custom prompt"
        assert request.number_of_images == 3
        assert request.aspect_ratio == "16:9"

    def test_request_model_validation_missing_prompt(self):
        """Test request model validation with missing prompt"""
        from pydantic import ValidationError

        from backend.app.routers.image_generation import ImageGenerationRequest

        with pytest.raises(ValidationError):
            ImageGenerationRequest()


# ============================================================================
# TEST RESPONSE MODEL
# ============================================================================


class TestImageGenerationResponse:
    """Tests for ImageGenerationResponse model"""

    def test_response_model_success(self):
        """Test response model for successful generation"""
        from backend.app.routers.image_generation import ImageGenerationResponse

        response = ImageGenerationResponse(
            images=["https://image.pollinations.ai/prompt/test"],
            success=True,
        )

        assert response.images == ["https://image.pollinations.ai/prompt/test"]
        assert response.success is True
        assert response.error is None

    def test_response_model_with_error(self):
        """Test response model with error"""
        from backend.app.routers.image_generation import ImageGenerationResponse

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
        from backend.app.routers.image_generation import ImageGenerationResponse

        images = [
            "https://image.pollinations.ai/prompt/test?seed=0",
            "https://image.pollinations.ai/prompt/test?seed=1",
            "https://image.pollinations.ai/prompt/test?seed=2",
        ]
        response = ImageGenerationResponse(images=images, success=True)

        assert len(response.images) == 3
        assert response.success is True


# ============================================================================
# TEST GENERATE IMAGE ENDPOINT - SUCCESS CASES
# ============================================================================


class TestGenerateImageSuccess:
    """Tests for successful image generation scenarios"""

    def test_generate_single_image_success(self, client, valid_image_request):
        """Test successful generation of a single image"""
        response = client.post("/api/v1/image/generate", json=valid_image_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["images"]) == 1
        assert data["images"][0].startswith("https://image.pollinations.ai/prompt/")
        assert data["error"] is None

    def test_generate_multiple_images_success(self, client):
        """Test successful generation of multiple images"""
        request_data = {
            "prompt": "Test prompt",
            "number_of_images": 3,
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["images"]) == 3
        # Each image should have a different seed
        for i, img_url in enumerate(data["images"]):
            assert f"seed={i}" in img_url

    def test_generate_image_with_default_aspect_ratio(self, client):
        """Test image generation uses 1:1 default aspect ratio"""
        request_data = {"prompt": "Test prompt"}

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "width=1024&height=1024" in data["images"][0]

    def test_generate_image_with_16_9_aspect_ratio(self, client):
        """Test image generation with 16:9 aspect ratio"""
        request_data = {
            "prompt": "Landscape view",
            "aspect_ratio": "16:9",
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "width=1024&height=576" in data["images"][0]

    def test_generate_image_with_9_16_aspect_ratio(self, client):
        """Test image generation with 9:16 aspect ratio"""
        request_data = {
            "prompt": "Portrait view",
            "aspect_ratio": "9:16",
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "width=576&height=1024" in data["images"][0]

    def test_generate_image_with_4_3_aspect_ratio(self, client):
        """Test image generation with 4:3 aspect ratio"""
        request_data = {
            "prompt": "Classic photo",
            "aspect_ratio": "4:3",
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "width=1024&height=768" in data["images"][0]

    def test_generate_image_with_3_4_aspect_ratio(self, client):
        """Test image generation with 3:4 aspect ratio"""
        request_data = {
            "prompt": "Portrait photo",
            "aspect_ratio": "3:4",
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "width=768&height=1024" in data["images"][0]

    def test_generate_image_unknown_aspect_ratio_defaults(self, client):
        """Test that unknown aspect ratio falls back to 1:1"""
        request_data = {
            "prompt": "Test",
            "aspect_ratio": "99:99",
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "width=1024&height=1024" in data["images"][0]

    def test_generate_image_url_format(self, client):
        """Test that generated URLs have correct format"""
        request_data = {
            "prompt": "A test image",
            "number_of_images": 1,
            "aspect_ratio": "1:1",
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        url = data["images"][0]
        encoded_prompt = quote("A test image")
        assert f"https://image.pollinations.ai/prompt/{encoded_prompt}" in url
        assert "nologo=true" in url

    def test_generate_image_prompt_is_url_encoded(self, client):
        """Test that prompt is properly URL-encoded in the image URL"""
        prompt = "A cat & a dog in a café"
        request_data = {"prompt": prompt}

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        # Verify URL encoding of special characters
        assert quote(prompt) in data["images"][0]


# ============================================================================
# TEST GENERATE IMAGE ENDPOINT - ERROR CASES
# ============================================================================


class TestGenerateImageErrors:
    """Tests for error scenarios in image generation"""

    def test_generate_image_empty_prompt(self, client):
        """Test image generation with empty prompt returns error"""
        request_data = {
            "prompt": "",
            "number_of_images": 1,
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Prompt cannot be empty"
        assert data["images"] == []

    def test_generate_image_whitespace_prompt(self, client):
        """Test image generation with whitespace-only prompt returns error"""
        request_data = {
            "prompt": "   ",
            "number_of_images": 1,
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Prompt cannot be empty"
        assert data["images"] == []

    def test_generate_image_invalid_request_missing_prompt(self, client):
        """Test validation error when prompt is missing"""
        request_data = {
            "number_of_images": 1,
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_generate_image_invalid_request_invalid_type(self, client):
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

    def test_generate_image_very_long_prompt(self, client):
        """Test image generation with very long prompt"""
        long_prompt = "A" * 5000
        request_data = {
            "prompt": long_prompt,
            "number_of_images": 1,
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["images"]) == 1

    def test_generate_image_special_characters_in_prompt(self, client):
        """Test image generation with special characters in prompt"""
        special_prompt = "Test symbols @#$% and more"
        request_data = {
            "prompt": special_prompt,
            "number_of_images": 1,
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Prompt should be URL-encoded in the URL
        assert quote(special_prompt) in data["images"][0]

    def test_generate_image_unicode_prompt(self, client):
        """Test image generation with unicode characters"""
        request_data = {
            "prompt": "Pemandangan gunung Bali",
            "number_of_images": 1,
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_generate_zero_images(self, client):
        """Test image generation requesting zero images"""
        request_data = {
            "prompt": "Test prompt",
            "number_of_images": 0,
        }

        response = client.post("/api/v1/image/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["images"]) == 0

    def test_no_api_key_required(self, client, valid_image_request):
        """Test that Pollinations.ai works without any API key"""
        # Pollinations is free and requires no API key
        response = client.post("/api/v1/image/generate", json=valid_image_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["images"]) >= 1
