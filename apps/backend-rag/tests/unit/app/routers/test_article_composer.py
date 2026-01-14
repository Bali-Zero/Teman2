"""
Unit tests for Article Composer router.

Tests article composition, enrichment, and publishing endpoints.
"""

import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.app.routers.article_composer import (
    router,
    validate_slug,
    slugify,
    generate_mdx_content,
    ComposeRequest,
    EnrichedArticle,
    TLDRSection,
    BaliZeroTake,
    NextSteps,
    PublishRequest,
)


# --- Test App Setup ---

@pytest.fixture
def app():
    """Create test FastAPI app with article composer router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# --- Slug Validation Tests ---

class TestValidateSlug:
    """Tests for validate_slug function."""

    def test_valid_slug(self):
        """Test valid slug passes validation."""
        is_valid, error = validate_slug("my-article-2026")
        assert is_valid is True
        assert error == ""

    def test_valid_slug_with_numbers(self):
        """Test slug with numbers is valid."""
        is_valid, error = validate_slug("article123")
        assert is_valid is True

    def test_empty_slug_invalid(self):
        """Test empty slug is invalid."""
        is_valid, error = validate_slug("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_uppercase_invalid(self):
        """Test uppercase letters are invalid."""
        is_valid, error = validate_slug("My-Article")
        assert is_valid is False
        assert "lowercase" in error.lower()

    def test_spaces_invalid(self):
        """Test spaces are invalid."""
        is_valid, error = validate_slug("my article")
        assert is_valid is False

    def test_special_chars_invalid(self):
        """Test special characters are invalid."""
        is_valid, error = validate_slug("my_article!")
        assert is_valid is False

    def test_too_short_invalid(self):
        """Test slug shorter than 3 chars is invalid."""
        is_valid, error = validate_slug("ab")
        assert is_valid is False
        assert "3 characters" in error

    def test_too_long_invalid(self):
        """Test slug longer than 100 chars is invalid."""
        is_valid, error = validate_slug("a" * 101)
        assert is_valid is False
        assert "100 characters" in error


class TestSlugify:
    """Tests for slugify function."""

    def test_converts_to_lowercase(self):
        """Test converts text to lowercase."""
        assert slugify("HELLO WORLD") == "hello-world"

    def test_replaces_spaces_with_hyphens(self):
        """Test spaces become hyphens."""
        assert slugify("hello world") == "hello-world"

    def test_replaces_underscores_with_hyphens(self):
        """Test underscores become hyphens."""
        assert slugify("hello_world") == "hello-world"

    def test_removes_special_characters(self):
        """Test special characters are removed."""
        assert slugify("hello@world!") == "helloworld"

    def test_removes_multiple_hyphens(self):
        """Test multiple consecutive hyphens become single."""
        assert slugify("hello---world") == "hello-world"

    def test_strips_leading_trailing_hyphens(self):
        """Test leading/trailing hyphens are removed."""
        assert slugify("-hello-world-") == "hello-world"


# --- MDX Generation Tests ---

class TestGenerateMdxContent:
    """Tests for generate_mdx_content function."""

    @pytest.fixture
    def sample_article(self):
        """Create sample enriched article."""
        return EnrichedArticle(
            title="Test Article",
            headline="This Is a Test Headline",
            tldr=TLDRSection(
                should_worry="No",
                what="Test event happened",
                who="Expats in Bali",
                when="January 2026",
                risk_level="Low",
            ),
            facts="These are the facts about the test event.",
            bali_zero_take=BaliZeroTake(
                hidden_insight="Hidden insight here.",
                our_analysis="Our analysis here.",
                our_advice="Our advice here.",
            ),
            next_steps=NextSteps(
                expat=["Step 1 for expats", "Step 2 for expats"],
                investor=["Step 1 for investors"],
            ),
            category="business",
            priority="medium",
            relevance_score=75,
            ai_summary="Test summary for SEO.",
            ai_tags=["test", "article", "business"],
            suggested_components=["timeline", "checklist"],
            source="Marketing Team",
            source_url="https://example.com",
            enriched_at=datetime.utcnow().isoformat(),
        )

    def test_generates_valid_mdx(self, sample_article):
        """Test generates valid MDX content with frontmatter."""
        mdx = generate_mdx_content(
            article=sample_article,
            slug="test-article",
            category="business",
            image_path="/static/news/test-article.jpg",
        )

        assert "---" in mdx  # Frontmatter delimiters
        assert 'title: "This Is a Test Headline"' in mdx
        assert 'slug: "test-article"' in mdx
        assert 'category: "business"' in mdx
        assert "## TL;DR" in mdx
        assert "## The Facts" in mdx
        assert "## Bali Zero Take" in mdx
        assert "## Next Steps" in mdx

    def test_includes_image_path(self, sample_article):
        """Test includes correct image path."""
        mdx = generate_mdx_content(
            article=sample_article,
            slug="test-article",
            category="business",
            image_path="/static/news/test-article.webp",
        )

        assert "/static/news/test-article.webp" in mdx

    def test_formats_tags_correctly(self, sample_article):
        """Test formats tags as YAML array."""
        mdx = generate_mdx_content(
            article=sample_article,
            slug="test-article",
            category="business",
            image_path="/static/news/test.jpg",
        )

        assert '  - "test"' in mdx
        assert '  - "article"' in mdx
        assert '  - "business"' in mdx

    def test_maps_category_correctly(self, sample_article):
        """Test maps category to correct folder name."""
        mdx = generate_mdx_content(
            article=sample_article,
            slug="test",
            category="tax-legal",
            image_path="/img.jpg",
        )
        # tax-legal should map to "tax"
        assert 'category: "tax"' in mdx

    def test_calculates_reading_time(self, sample_article):
        """Test calculates reading time based on word count."""
        # Add more content to facts
        sample_article.facts = " ".join(["word"] * 400)  # 400 words
        sample_article.bali_zero_take.our_analysis = " ".join(["word"] * 200)  # 200 words

        mdx = generate_mdx_content(
            article=sample_article,
            slug="test",
            category="business",
            image_path="/img.jpg",
        )

        # 600 words / 200 wpm = 3 min
        assert "readingTime: 3" in mdx


# --- Compose Endpoint Tests ---

class TestComposeEndpoint:
    """Tests for POST /api/articles/compose endpoint."""

    @pytest.mark.asyncio
    async def test_compose_returns_error_when_api_key_missing(self, client):
        """Test returns 500 when ANTHROPIC_API_KEY not set."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            response = client.post(
                "/api/articles/compose",
                json={
                    "title": "Test",
                    "content": "Test content",
                    "category": "business",
                    "author": "Test",
                },
            )
            assert response.status_code == 500
            assert "API key not configured" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_compose_calls_anthropic_api(self, client):
        """Test calls Anthropic API with correct parameters."""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps({
            "headline": "Test Headline",
            "tldr": {
                "should_worry": "No",
                "what": "Test",
                "who": "Everyone",
                "when": "Now",
                "risk_level": "Low",
            },
            "facts": "Facts here",
            "bali_zero_take": {
                "hidden_insight": "Insight",
                "our_analysis": "Analysis",
                "our_advice": "Advice",
            },
            "next_steps": {
                "expat": ["Step 1"],
                "investor": ["Step 2"],
            },
            "category": "business",
            "priority": "medium",
            "relevance_score": 50,
            "ai_summary": "Summary",
            "ai_tags": ["tag1"],
            "suggested_components": [],
        }))]
        mock_message.usage = MagicMock(input_tokens=100, output_tokens=200)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic") as mock_anthropic:
                mock_client = MagicMock()
                mock_client.messages.create.return_value = mock_message
                mock_anthropic.return_value = mock_client

                response = client.post(
                    "/api/articles/compose",
                    json={
                        "title": "Test Article",
                        "content": "Test content for enrichment",
                        "category": "business",
                        "author": "Test Author",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["article"]["headline"] == "Test Headline"

    @pytest.mark.asyncio
    async def test_compose_handles_json_parse_error(self, client):
        """Test handles invalid JSON from Claude gracefully."""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="This is not valid JSON")]
        mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic") as mock_anthropic:
                mock_client = MagicMock()
                mock_client.messages.create.return_value = mock_message
                mock_anthropic.return_value = mock_client

                response = client.post(
                    "/api/articles/compose",
                    json={
                        "title": "Test",
                        "content": "Content",
                        "category": "business",
                        "author": "Author",
                    },
                )

                data = response.json()
                assert data["success"] is False
                assert "parse" in data["error"].lower()


# --- Compose Status Endpoint Tests ---

class TestComposeStatusEndpoint:
    """Tests for GET /api/articles/compose/status endpoint."""

    def test_status_when_configured(self, client):
        """Test returns configured=True when API key is set."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            response = client.get("/api/articles/compose/status")

            assert response.status_code == 200
            data = response.json()
            assert data["configured"] is True
            assert data["api_key_set"] is True
            assert "claude" in data["model"].lower()

    def test_status_when_not_configured(self, client):
        """Test returns configured=False when API key not set."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            response = client.get("/api/articles/compose/status")

            data = response.json()
            assert data["configured"] is False


# --- Publish Endpoint Tests ---

class TestPublishEndpoint:
    """Tests for POST /api/articles/publish endpoint."""

    @pytest.fixture
    def sample_publish_request(self):
        """Create sample publish request."""
        return {
            "article": {
                "title": "Test",
                "headline": "Test Headline",
                "tldr": {
                    "should_worry": "No",
                    "what": "Test",
                    "who": "Everyone",
                    "when": "Now",
                    "risk_level": "Low",
                },
                "facts": "Facts",
                "bali_zero_take": {
                    "hidden_insight": "Insight",
                    "our_analysis": "Analysis",
                    "our_advice": "Advice",
                },
                "next_steps": {"expat": [], "investor": []},
                "category": "business",
                "priority": "medium",
                "relevance_score": 50,
                "ai_summary": "Summary",
                "ai_tags": ["tag"],
                "suggested_components": [],
                "source": "Test",
                "source_url": None,
                "enriched_at": datetime.utcnow().isoformat(),
            },
            "slug": "test-article",
            "cover_image_base64": base64.b64encode(b"fake-image-bytes").decode(),
            "cover_image_filename": "cover.jpg",
            "position": "mainNews1",
            "category": "business",
        }

    def test_publish_rejects_invalid_slug(self, client, sample_publish_request):
        """Test rejects invalid slug format."""
        sample_publish_request["slug"] = "Invalid Slug!"

        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = True

            response = client.post(
                "/api/articles/publish",
                json=sample_publish_request,
            )

            assert response.status_code == 400
            assert "Invalid slug" in response.json()["detail"]

    def test_publish_returns_error_when_not_configured(self, client, sample_publish_request):
        """Test returns 500 when GitHub not configured."""
        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = False

            response = client.post(
                "/api/articles/publish",
                json=sample_publish_request,
            )

            assert response.status_code == 500
            assert "not configured" in response.json()["detail"].lower()

    def test_publish_rejects_duplicate_slug(self, client, sample_publish_request):
        """Test returns 409 when slug already exists."""
        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = True
            mock_pub.check_file_exists = AsyncMock(return_value=True)

            response = client.post(
                "/api/articles/publish",
                json=sample_publish_request,
            )

            assert response.status_code == 409
            assert "already exists" in response.json()["detail"]

    def test_publish_rejects_large_image(self, client, sample_publish_request):
        """Test rejects images larger than 2MB."""
        # Create >2MB base64 string
        large_image = b"x" * (3 * 1024 * 1024)  # 3MB
        sample_publish_request["cover_image_base64"] = base64.b64encode(large_image).decode()

        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = True
            mock_pub.check_file_exists = AsyncMock(return_value=False)

            response = client.post(
                "/api/articles/publish",
                json=sample_publish_request,
            )

            assert response.status_code == 413
            assert "2MB" in response.json()["detail"]

    def test_publish_success(self, client, sample_publish_request):
        """Test successful publish returns correct response."""
        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = True
            mock_pub.check_file_exists = AsyncMock(return_value=False)
            mock_pub.create_commit_with_files = AsyncMock(return_value={
                "success": True,
                "commit_sha": "abc123def456",
            })

            response = client.post(
                "/api/articles/publish",
                json=sample_publish_request,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["published_url"] == "https://balizero.com/business/test-article"
            assert "apps/mouth" in data["mdx_path"]
            assert data["commit_sha"] == "abc123def456"
            assert "mainNews1" in data["position_snippet"]

    def test_publish_generates_correct_paths(self, client, sample_publish_request):
        """Test generates correct file paths for different categories."""
        sample_publish_request["category"] = "immigration"
        sample_publish_request["slug"] = "visa-update"

        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = True
            mock_pub.check_file_exists = AsyncMock(return_value=False)
            mock_pub.create_commit_with_files = AsyncMock(return_value={
                "success": True,
                "commit_sha": "sha123",
            })

            response = client.post(
                "/api/articles/publish",
                json=sample_publish_request,
            )

            data = response.json()
            assert "immigration/visa-update" in data["mdx_path"]
            assert "balizero.com/immigration/visa-update" in data["published_url"]


# --- Publish Status Endpoint Tests ---

class TestPublishStatusEndpoint:
    """Tests for GET /api/articles/publish/status endpoint."""

    def test_status_when_configured(self, client):
        """Test returns correct status when configured."""
        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = True
            mock_pub.owner = "Balizero1987"
            mock_pub.repo = "Teman2"
            mock_pub.token = "ghp_xxx"

            response = client.get("/api/articles/publish/status")

            data = response.json()
            assert data["configured"] is True
            assert data["github_owner"] == "Balizero1987"
            assert data["github_repo"] == "Teman2"
            assert data["token_set"] is True

    def test_status_when_not_configured(self, client):
        """Test returns correct status when not configured."""
        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = False
            mock_pub.owner = None
            mock_pub.repo = None
            mock_pub.token = None

            response = client.get("/api/articles/publish/status")

            data = response.json()
            assert data["configured"] is False
            assert data["token_set"] is False
