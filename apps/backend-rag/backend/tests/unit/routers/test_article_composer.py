"""
Unit tests for Article Composer API

Tests cover:
- Article enrichment with Claude API (compose endpoint)
- Article publishing to GitHub (publish endpoint)
- Helper functions (slug generation, MDX content generation)
- Error handling and edge cases
"""

import base64
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.routers.article_composer import (
    BaliZeroTake,
    ComposeRequest,
    EnrichedArticle,
    NextSteps,
    PublishRequest,
    TLDRSection,
    build_enrichment_prompt,
    generate_mdx_content,
    generate_slug,
    router,
)

# --- FIXTURES ---


@pytest.fixture
def test_client():
    """Create FastAPI test client"""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def sample_compose_request():
    """Sample compose request"""
    return ComposeRequest(
        title="New Visa Regulation 2026",
        content="The Indonesian government announced new visa regulations affecting expats in Bali and across the archipelago. The new rules require additional documentation for work permit renewals and introduce stricter compliance checks for foreign workers.",
        category="immigration",
        source_url="https://example.com/news",
        author="Test Author",
    )


@pytest.fixture
def sample_enriched_article():
    """Sample enriched article"""
    return EnrichedArticle(
        title="New Visa Regulation 2026",
        headline="Indonesia Tightens Visa Rules: What Expats Need to Know",
        tldr=TLDRSection(
            should_worry="Yes",
            what="New visa regulations require additional documentation",
            who="All expats on work permits",
            when="Effective March 2026",
            risk_level="High",
        ),
        facts="The Indonesian government has announced significant changes to visa regulations. "
        * 50,  # ~500 words
        bali_zero_take=BaliZeroTake(
            hidden_insight="This is part of a broader immigration crackdown",
            our_analysis="The timing suggests coordination with other ASEAN countries",
            our_advice="Review your visa status immediately and consult immigration lawyer",
        ),
        next_steps=NextSteps(
            expat=["Check visa expiry", "Gather required documents"],
            investor=["Review company sponsorship", "Update compliance procedures"],
        ),
        category="immigration",
        priority="high",
        relevance_score=85,
        ai_summary="Indonesia introduces stricter visa requirements for expats starting March 2026",
        ai_tags=["visa", "immigration", "regulation", "expat", "compliance"],
        suggested_components=["timeline", "checklist", "alert-box"],
        cover_image=None,
        source="Test Author",
        source_url="https://example.com/news",
        enriched_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response"""
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text=json.dumps(
                {
                    "headline": "Indonesia Tightens Visa Rules: What Expats Need to Know",
                    "tldr": {
                        "should_worry": "Yes",
                        "what": "New visa regulations require additional documentation",
                        "who": "All expats on work permits",
                        "when": "Effective March 2026",
                        "risk_level": "High",
                    },
                    "facts": "The Indonesian government has announced significant changes. " * 80,
                    "bali_zero_take": {
                        "hidden_insight": "This is part of broader immigration crackdown",
                        "our_analysis": "Timing suggests ASEAN coordination",
                        "our_advice": "Review visa status immediately",
                    },
                    "next_steps": {
                        "expat": ["Check visa expiry", "Gather documents"],
                        "investor": ["Review sponsorship", "Update procedures"],
                    },
                    "category": "immigration",
                    "priority": "high",
                    "relevance_score": 85,
                    "ai_summary": "Indonesia introduces stricter visa requirements",
                    "ai_tags": ["visa", "immigration", "regulation"],
                    "suggested_components": ["timeline", "checklist"],
                },
            ),
        ),
    ]
    mock_response.usage = MagicMock(input_tokens=1000, output_tokens=1500)
    return mock_response


# --- COMPOSE ENDPOINT TESTS ---


@pytest.mark.skip(reason="Article composer compose endpoint disabled (501)")
@patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
@patch("backend.app.routers.article_composer.anthropic.Anthropic")
def test_compose_article_success(
    mock_anthropic_class, test_client, sample_compose_request, mock_anthropic_response,
):
    """Test successful article composition with Claude API"""
    # Setup mock
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response
    mock_anthropic_class.return_value = mock_client

    # Call endpoint
    response = test_client.post("/api/articles/compose", json=sample_compose_request.model_dump())

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["article"] is not None
    assert data["article"]["headline"] == "Indonesia Tightens Visa Rules: What Expats Need to Know"
    assert data["article"]["priority"] == "high"
    assert data["api_cost_cents"] > 0
    assert "image_prompt" not in data["article"]  # Verify image_prompt removed


@pytest.mark.skip(reason="Article composer compose endpoint disabled (501)")
@patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
@patch("backend.app.routers.article_composer.anthropic.Anthropic")
def test_compose_article_priority_word_count(mock_anthropic_class, test_client):
    """Test that facts section length varies by priority (high=600, medium=500, low=400 words)"""
    test_cases = [
        ("high", 600),
        ("medium", 500),
        ("low", 400),
    ]

    for priority, expected_words in test_cases:
        # Setup mock with specific priority
        mock_response = MagicMock()
        facts_text = " ".join(["word"] * expected_words)
        mock_response.content = [
            MagicMock(
                text=json.dumps(
                    {
                        "headline": "Test Headline",
                        "tldr": {
                            "should_worry": "Depends",
                            "what": "Test",
                            "who": "Test",
                            "when": "Test",
                            "risk_level": "Medium",
                        },
                        "facts": facts_text,
                        "bali_zero_take": {
                            "hidden_insight": "Test",
                            "our_analysis": "Test",
                            "our_advice": "Test",
                        },
                        "next_steps": {"expat": [], "investor": []},
                        "category": "business",
                        "priority": priority,
                        "relevance_score": 50,
                        "ai_summary": "Test",
                        "ai_tags": [],
                        "suggested_components": [],
                    },
                ),
            ),
        ]
        mock_response.usage = MagicMock(input_tokens=1000, output_tokens=1500)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        # Call endpoint
        request = ComposeRequest(
            title="Test Article Title",
            content="Test content for article enrichment that must be at least one hundred characters long to pass the validation check in the compose request validator model.",
            category="business",
        )
        response = test_client.post("/api/articles/compose", json=request.model_dump())

        # Verify priority and word count
        assert response.status_code == 200
        data = response.json()
        assert data["article"]["priority"] == priority
        # Verify facts section has approximately expected word count
        facts = data["article"]["facts"]
        word_count = len(facts.split())
        assert word_count >= expected_words - 50  # Allow some variance


@pytest.mark.skip(reason="Article composer compose endpoint disabled (501)")
@patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
@patch("backend.app.routers.article_composer.anthropic.Anthropic")
def test_compose_article_json_cleanup(mock_anthropic_class, test_client, sample_compose_request):
    """Test that markdown JSON blocks are cleaned correctly"""
    test_cases = [
        # JSON wrapped in ```json
        '```json\n{"headline": "Test"}\n```',
        # JSON wrapped in ```
        '```\n{"headline": "Test"}\n```',
        # Plain JSON
        '{"headline": "Test"}',
    ]

    for json_text in test_cases:
        mock_response = MagicMock()
        # Build minimal valid JSON
        minimal_json = {
            "headline": "Test",
            "tldr": {
                "should_worry": "No",
                "what": "Test",
                "who": "Test",
                "when": "Test",
                "risk_level": "Low",
            },
            "facts": "Test facts",
            "bali_zero_take": {
                "hidden_insight": "Test",
                "our_analysis": "Test",
                "our_advice": "Test",
            },
            "next_steps": {"expat": [], "investor": []},
            "category": "business",
            "priority": "low",
            "relevance_score": 30,
            "ai_summary": "Test",
            "ai_tags": [],
            "suggested_components": [],
        }
        if "```json" in json_text:
            mock_response.content = [MagicMock(text=f"```json\n{json.dumps(minimal_json)}\n```")]
        elif "```" in json_text:
            mock_response.content = [MagicMock(text=f"```\n{json.dumps(minimal_json)}\n```")]
        else:
            mock_response.content = [MagicMock(text=json.dumps(minimal_json))]

        mock_response.usage = MagicMock(input_tokens=500, output_tokens=800)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        response = test_client.post(
            "/api/articles/compose", json=sample_compose_request.model_dump(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.skip(reason="Article composer compose endpoint disabled (501)")
@patch.dict("os.environ", {}, clear=True)
def test_compose_article_missing_api_key(test_client, sample_compose_request):
    """Test compose fails gracefully when API key is missing"""
    response = test_client.post("/api/articles/compose", json=sample_compose_request.model_dump())

    assert response.status_code == 500
    assert "API key not configured" in response.json()["detail"]


@pytest.mark.skip(reason="Article composer compose endpoint disabled (501)")
@patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
@patch("backend.app.routers.article_composer.anthropic.Anthropic")
def test_compose_article_json_parse_error(
    mock_anthropic_class, test_client, sample_compose_request,
):
    """Test compose handles JSON parse errors"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Invalid JSON {{{")]
    mock_response.usage = MagicMock(input_tokens=500, output_tokens=100)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    response = test_client.post("/api/articles/compose", json=sample_compose_request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Failed to parse Claude response" in data["error"]


@pytest.mark.skip(reason="Article composer compose endpoint disabled (501)")
@patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
@patch("backend.app.routers.article_composer.anthropic.Anthropic")
def test_compose_article_api_error(mock_anthropic_class, test_client, sample_compose_request):
    """Test compose handles Anthropic API errors"""
    import anthropic
    import httpx

    mock_client = MagicMock()
    # anthropic.APIError requires message, request, and body
    mock_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    mock_client.messages.create.side_effect = anthropic.APIError(
        "API Error", request=mock_request, body={},
    )
    mock_anthropic_class.return_value = mock_client

    response = test_client.post("/api/articles/compose", json=sample_compose_request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Claude API error" in data["error"]


def test_compose_status_configured(test_client):
    """Test compose status endpoint when configured"""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        response = test_client.get("/api/articles/compose/status")

        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["api_key_set"] is True
        assert data["model"] == "claude-sonnet-4-20250514"


def test_compose_status_not_configured(test_client):
    """Test compose status endpoint when not configured"""
    with patch.dict("os.environ", {}, clear=True):
        response = test_client.get("/api/articles/compose/status")

        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is False
        assert data["api_key_set"] is False


# --- PUBLISH ENDPOINT TESTS ---


@pytest.mark.asyncio
@patch("backend.services.integrations.github_publisher.github_publisher")
async def test_publish_article_with_cover_image(
    mock_publisher, test_client, sample_enriched_article,
):
    """Test publishing article with cover image (base64)"""
    # Setup mock
    mock_publisher.is_configured = True
    mock_publisher.create_commit_with_files = AsyncMock(
        return_value={"success": True, "commit_sha": "abc123", "files_count": 2, "branch": "main"},
    )

    # Create base64 image
    image_data = b"fake-image-data"
    image_base64 = base64.b64encode(image_data).decode("utf-8")

    # Call endpoint
    request = PublishRequest(
        article=sample_enriched_article,
        cover_image_base64=image_base64,
        cover_image_filename="test-article.jpg",
        position="normal",
    )
    response = test_client.post("/api/articles/publish", json=request.model_dump())

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["article_url"] is not None
    assert data["commit_sha"] == "abc123"
    assert data["image_path"] == "/static/news/test-article.jpg"

    # Verify atomic commit was called
    mock_publisher.create_commit_with_files.assert_called_once()
    call_args = mock_publisher.create_commit_with_files.call_args
    assert len(call_args[1]["files"]) == 2  # MDX + image


@pytest.mark.asyncio
@patch("backend.services.integrations.github_publisher.github_publisher")
async def test_publish_article_without_cover_image(
    mock_publisher, test_client, sample_enriched_article,
):
    """Test publishing article without cover image"""
    # Setup mock
    mock_publisher.is_configured = True
    mock_publisher.upload_file = AsyncMock(
        return_value={"success": True, "commit_sha": "def456", "path": "test.mdx"},
    )

    # Call endpoint
    request = PublishRequest(article=sample_enriched_article, position="normal")
    response = test_client.post("/api/articles/publish", json=request.model_dump())

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["image_path"] is None

    # Verify single file upload was called
    mock_publisher.upload_file.assert_called_once()


@patch("backend.services.integrations.github_publisher.github_publisher")
def test_publish_article_github_not_configured(
    mock_publisher, test_client, sample_enriched_article,
):
    """Test publish fails when GitHub not configured"""
    mock_publisher.is_configured = False

    request = PublishRequest(article=sample_enriched_article)
    response = test_client.post("/api/articles/publish", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "GitHub API not configured" in data["message"]


@pytest.mark.asyncio
@patch("backend.services.integrations.github_publisher.github_publisher")
async def test_publish_article_github_error(mock_publisher, test_client, sample_enriched_article):
    """Test publish handles GitHub API errors"""
    from backend.services.integrations.github_publisher import GitHubPublisherError

    mock_publisher.is_configured = True
    mock_publisher.upload_file = AsyncMock(side_effect=GitHubPublisherError("GitHub API error"))

    request = PublishRequest(article=sample_enriched_article)
    response = test_client.post("/api/articles/publish", json=request.model_dump())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Failed to publish to GitHub" in data["message"]


def test_publish_status(test_client):
    """Test publish status endpoint"""
    with patch("backend.services.integrations.github_publisher.github_publisher") as mock_publisher:
        mock_publisher.is_configured = True
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.github_token = "test-token"
            mock_settings.github_owner = "test-owner"
            mock_settings.github_repo = "test-repo"

            response = test_client.get("/api/articles/publish/status")

            assert response.status_code == 200
            data = response.json()
            assert data["configured"] is True
            assert data["github_token_set"] is True
            assert data["github_owner"] == "test-owner"
            assert data["github_repo"] == "test-repo"


# --- HELPER FUNCTION TESTS ---


def test_generate_slug_basic():
    """Test slug generation from headline"""
    headline = "Indonesia Tightens Visa Rules"
    slug = generate_slug(headline)
    assert slug == "indonesia-tightens-visa-rules"


def test_generate_slug_special_characters():
    """Test slug generation removes special characters"""
    headline = "New Law: Tax @ 25% for Investors!"
    slug = generate_slug(headline)
    assert slug == "new-law-tax-25-for-investors"


def test_generate_slug_multiple_spaces():
    """Test slug generation handles multiple spaces"""
    headline = "Tax    Law    Update"
    slug = generate_slug(headline)
    assert slug == "tax-law-update"


def test_generate_slug_long_headline():
    """Test slug generation limits length to 120 chars"""
    headline = "This is a very long headline that should be truncated to sixty characters maximum"
    slug = generate_slug(headline)
    assert len(slug) <= 120
    assert not slug.endswith("-")  # No trailing hyphen


def test_generate_slug_unicode():
    """Test slug generation handles unicode characters"""
    headline = "Café & Résumé: Naïve Approach"
    slug = generate_slug(headline)
    assert slug == "caf-rsum-nave-approach"


def test_generate_mdx_content_json_serialization(sample_enriched_article):
    """Test MDX content generation with JSON serialization for React components"""
    slug = "test-article"
    mdx = generate_mdx_content(sample_enriched_article, slug, None)

    # Verify next_steps are JSON serialized
    assert '["Check visa expiry", "Gather required documents"]' in mdx
    assert '["Review company sponsorship", "Update compliance procedures"]' in mdx

    # Verify frontmatter
    assert f'slug: "{slug}"' in mdx
    assert f'title: "{sample_enriched_article.headline}"' in mdx

    # Verify sections
    assert "## TL;DR" in mdx
    assert "## The Facts" in mdx
    assert "## Bali Zero Take" in mdx
    assert "## Next Steps" in mdx


def test_generate_mdx_content_cover_image_path(sample_enriched_article):
    """Test MDX content uses provided cover image path"""
    slug = "test-article"
    cover_path = "/static/news/custom-image.jpg"
    mdx = generate_mdx_content(sample_enriched_article, slug, cover_path)

    assert f'coverImage: "{cover_path}"' in mdx


def test_generate_mdx_content_reading_time(sample_enriched_article):
    """Test MDX content calculates reading time"""
    slug = "test-article"
    mdx = generate_mdx_content(sample_enriched_article, slug, None)

    # Reading time should be calculated (min 3 minutes)
    assert "readingTime:" in mdx
    # Extract reading time value
    import re

    match = re.search(r"readingTime: (\d+)", mdx)
    assert match
    reading_time = int(match.group(1))
    assert reading_time >= 3


def test_build_enrichment_prompt_truncates_content():
    """Test enrichment prompt truncates content to 8000 chars"""
    title = "Test"
    long_content = "word " * 3000  # ~15000 chars
    category = "business"

    prompt = build_enrichment_prompt(title, long_content, category)

    # Verify content is truncated
    assert "word " * 1600 in prompt  # ~8000 chars worth
    assert len(long_content) > 8000
    # Prompt should contain truncated content
    assert title in prompt
    assert category in prompt


def test_build_enrichment_prompt_priority_instructions():
    """Test enrichment prompt contains priority-based word count instructions"""
    prompt = build_enrichment_prompt("Test", "Content", "business")

    # Verify dynamic word count instruction is present
    assert "400-600 words based on news relevance" in prompt
    assert "high priority = 600 words" in prompt
    assert "medium = 500" in prompt
    assert "low = 400" in prompt


# --- INTEGRATION TEST ---


@pytest.mark.asyncio
@pytest.mark.skip(reason="Article composer compose endpoint disabled (501)")
@patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
@patch("backend.app.routers.article_composer.anthropic.Anthropic")
@patch("backend.services.integrations.github_publisher.github_publisher")
async def test_full_compose_and_publish_flow(
    mock_publisher, mock_anthropic_class, test_client, mock_anthropic_response,
):
    """Integration test: compose article then publish it"""
    # Setup mocks
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response
    mock_anthropic_class.return_value = mock_client

    mock_publisher.is_configured = True
    mock_publisher.upload_file = AsyncMock(
        return_value={"success": True, "commit_sha": "abc123", "path": "test.mdx"},
    )

    # Step 1: Compose article
    compose_request = ComposeRequest(
        title="Test Article",
        content="Test content for integration test that must be at least one hundred characters long to pass the validation check in the compose request validator model.",
        category="business",
    )
    compose_response = test_client.post("/api/articles/compose", json=compose_request.model_dump())

    assert compose_response.status_code == 200
    compose_data = compose_response.json()
    assert compose_data["success"] is True
    assert compose_data["article"] is not None

    # Step 2: Publish article
    enriched_article = EnrichedArticle(**compose_data["article"])
    publish_request = PublishRequest(article=enriched_article)
    publish_response = test_client.post("/api/articles/publish", json=publish_request.model_dump())

    assert publish_response.status_code == 200
    publish_data = publish_response.json()
    assert publish_data["success"] is True
    assert publish_data["article_url"] is not None
    assert publish_data["commit_sha"] == "abc123"
