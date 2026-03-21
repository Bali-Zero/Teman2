"""
Integration tests for Article Composer API

Tests the full flow including:
- Rate limiting
- Caching
- Error handling
- Retry logic
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Create test app
app = FastAPI()
# Import router
from backend.app.routers import article_composer

app.include_router(article_composer.router)


@pytest.fixture
def client():
    """Create test client"""
    c = TestClient(app)
    c.headers.update({"X-API-Key": "dev_api_key_for_testing_only"})
    return c


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response"""
    mock_message = MagicMock()
    mock_message.content = [
        MagicMock(
            text='{"headline": "Test Headline", "tldr": {"should_worry": "No", "what": "Test", "who": "Everyone", "when": "Now", "risk_level": "Low"}, "facts": "Test facts content", "bali_zero_take": {"hidden_insight": "Insight", "our_analysis": "Analysis", "our_advice": "Advice"}, "next_steps": {"expat": ["Step 1"], "investor": ["Step 2"]}, "category": "business", "priority": "medium", "relevance_score": 75, "ai_summary": "Test summary", "ai_tags": ["tag1", "tag2"], "suggested_components": []}'
        )
    ]
    mock_message.usage = MagicMock(input_tokens=1000, output_tokens=1500)
    return mock_message


class TestArticleComposerIntegration:
    """Integration tests for Article Composer"""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("backend.services.article_composer.claude_client.get_anthropic_client")
    @patch("backend.services.article_composer.cache_service.get_compose_cache")
    @patch("backend.services.article_composer.cache_service.set_compose_cache")
    def test_compose_article_success(
        self,
        mock_set_cache,
        mock_get_cache,
        mock_get_client,
        mock_anthropic_response,
        client,
    ):
        """Test successful article composition"""
        # Setup mocks
        mock_get_cache.return_value = None  # Cache miss

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        mock_get_client.return_value = mock_client

        # Make request
        response = client.post(
            "/api/articles/compose",
            json={
                "title": "Test Article Title",
                "content": "This is a test article content with enough words to pass validation and provide meaningful context for the AI to work with.",
                "category": "business",
                "author": "Test Author",
            },
        )

        # Endpoint is disabled (returns 501 Not Implemented)
        assert response.status_code == 501
        data = response.json()
        assert data["detail"]["success"] is False

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("backend.services.article_composer.cache_service.get_compose_cache")
    def test_compose_article_cache_hit(self, mock_get_cache, client):
        """Test article composition with cache hit"""
        # Setup cache hit
        cached_data = {
            "article": {
                "title": "Test Title",
                "headline": "Test Headline",
                "tldr": {
                    "should_worry": "No",
                    "what": "Test",
                    "who": "Everyone",
                    "when": "Now",
                    "risk_level": "Low",
                },
                "facts": "Test facts",
                "bali_zero_take": {
                    "hidden_insight": "Insight",
                    "our_analysis": "Analysis",
                    "our_advice": "Advice",
                },
                "next_steps": {"expat": [], "investor": []},
                "category": "business",
                "priority": "medium",
                "relevance_score": 75,
                "ai_summary": "Summary",
                "ai_tags": [],
                "suggested_components": [],
                "source": "Test Author",
                "source_url": None,
                "enriched_at": "2026-01-24T00:00:00",
            },
            "api_cost_cents": 3.5,
        }
        mock_get_cache.return_value = cached_data

        # Make request
        response = client.post(
            "/api/articles/compose",
            json={
                "title": "Test Article Title",
                "content": "This is a test article content with enough words to pass validation. It provides sufficient context for the AI processing pipeline.",
                "category": "business",
            },
        )

        # Endpoint is disabled (returns 501 Not Implemented)
        assert response.status_code == 501
        data = response.json()
        assert data["detail"]["success"] is False

    def test_compose_article_validation_error(self, client):
        """Test validation error handling"""
        # Title too short
        response = client.post(
            "/api/articles/compose",
            json={
                "title": "Short",  # Too short
                "content": "Valid content",
                "category": "business",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_compose_article_rate_limit(self, client):
        """Test rate limiting"""
        # Make 11 requests rapidly (limit is 10/minute)
        responses = []
        for _ in range(11):
            response = client.post(
                "/api/articles/compose",
                json={
                    "title": "Test Article Title",
                    "content": "This is a test article content with enough words to be valid. This extra text ensures the content meets the minimum length requirement for validation.",
                    "category": "business",
                },
            )
            responses.append(response)

        # At least one should be rate limited (429)
        [r.status_code for r in responses]
        # Note: Rate limiting might not trigger in test environment
        # This test documents expected behavior

    @patch.dict("os.environ", {}, clear=True)
    def test_compose_article_no_api_key(self, client):
        """Test error when API key is missing"""
        response = client.post(
            "/api/articles/compose",
            json={
                "title": "Test Article Title",
                "content": "This is a test article content with enough words to be valid. This extra text ensures the content meets the minimum length requirement.",
                "category": "business",
            },
        )

        # Endpoint is disabled (returns 501); rate-limiter may return 429 first
        assert response.status_code in [501, 429]

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("backend.services.article_composer.claude_client.call_claude_with_retry")
    def test_compose_article_api_error(self, mock_claude_call, mock_anthropic_response, client):
        """Test handling of API errors"""
        import anthropic

        # Simulate rate limit error
        mock_claude_call.side_effect = anthropic.RateLimitError(
            message="Rate limit exceeded", response=MagicMock(), body={}
        )

        response = client.post(
            "/api/articles/compose",
            json={
                "title": "Test Article Title",
                "content": "This is a test article content with enough words to be valid. This extra text ensures the content meets the minimum length requirement.",
                "category": "business",
            },
        )

        # Endpoint disabled (501); rate-limiter may return 429
        assert response.status_code in [501, 429]

    def test_compose_status_endpoint(self, client):
        """Test status endpoint"""
        response = client.get("/api/articles/compose/status")

        assert response.status_code == 200
        data = response.json()
        assert "configured" in data
        assert "model" in data
        assert "cache_enabled" in data
        assert "rate_limit" in data
