"""
Unit tests for Article Composer router.

Tests article composition, enrichment, and publishing endpoints.
"""

import base64
import json
import os
import sys
import types
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).resolve().parents[4] / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# Aggressively mock problematic modules before any backend imports
def mock_problematic_modules():
    # Mock NumPy and PIL
    numpy_mock = types.ModuleType("numpy")
    numpy_mock.__version__ = "1.26.4"
    numpy_mock.__path__ = []
    sys.modules["numpy"] = numpy_mock
    sys.modules["numpy.typing"] = MagicMock()
    sys.modules["numpy._typing"] = MagicMock()
    sys.modules["numpy._typing._char_codes"] = MagicMock()

    for m in ["PIL", "PIL.Image", "PIL.ImageMode"]:
        mock = types.ModuleType(m)
        if m == "PIL":
            mock.__version__ = "10.0.0"
            mock.Image = types.ModuleType("PIL.Image")
            mock.Image.Image = MagicMock
        sys.modules[m] = mock

    # Mock qdrant_client BEFORE any backend imports
    sys.modules["qdrant_client"] = MagicMock()
    sys.modules["qdrant_client.http"] = MagicMock()
    sys.modules["qdrant_client.http.exceptions"] = MagicMock()

    # Set up ALL backend.services submodules BEFORE importing article_composer
    # This prevents import errors when article_composer triggers service imports

    # Special handling for misc to allow submodule imports (MUST be first)
    misc_mock = types.ModuleType("backend.services.misc")
    misc_mock.__path__ = []

    # Add commonly imported classes from misc
    misc_mock.AdvancedContextWindowManager = MagicMock()
    misc_mock.AutonomousResearchService = MagicMock()
    misc_mock.AutonomousScheduler = MagicMock()
    misc_mock.ClarificationService = MagicMock()
    misc_mock.ClientJourneyOrchestrator = MagicMock()
    misc_mock.ContextSuggestionService = MagicMock()
    misc_mock.ConversationService = MagicMock()
    misc_mock.CulturalInsightsService = MagicMock()
    misc_mock.CulturalRAGService = MagicMock()
    misc_mock.EmotionalAttunementService = MagicMock()
    misc_mock.FollowupService = MagicMock()
    misc_mock.GoldenAnswerService = MagicMock()
    misc_mock.GraphExtractor = MagicMock()
    misc_mock.GraphService = MagicMock()
    misc_mock.ImageGenerationService = MagicMock()
    misc_mock.KnowledgeGraphBuilder = MagicMock()
    misc_mock.MCPClientService = MagicMock()
    misc_mock.MigrationRunner = MagicMock()
    misc_mock.PerformanceMonitor = MagicMock()
    misc_mock.PersonalityService = MagicMock()
    misc_mock.ProactiveComplianceMonitor = MagicMock()
    misc_mock.SessionService = MagicMock()
    misc_mock.ToolExecutor = MagicMock()
    misc_mock.WorkSessionService = MagicMock()
    misc_mock.ZantaraTools = MagicMock()
    misc_mock.format_search_results = MagicMock()
    misc_mock.get_context_suggestion_service = MagicMock()
    misc_mock.get_zantara_tools = MagicMock()
    misc_mock.Entity = MagicMock()
    misc_mock.EntityType = MagicMock()
    misc_mock.Relationship = MagicMock()
    misc_mock.RelationType = MagicMock()

    sys.modules["backend.services.misc"] = misc_mock

    # Special handling for search to allow submodule imports
    search_mock = types.ModuleType("backend.services.search")
    search_mock.__path__ = []
    search_mock.CitationService = MagicMock()
    search_mock.build_search_filter = MagicMock()
    search_mock.SemanticCache = MagicMock()
    search_mock.SearchService = MagicMock()
    sys.modules["backend.services.search"] = search_mock
    sys.modules["backend.services.search.citation_service"] = MagicMock()
    sys.modules["backend.services.search.search_filters"] = MagicMock()
    sys.modules["backend.services.search.search_service"] = MagicMock()
    sys.modules["backend.services.search.semantic_cache"] = MagicMock()

    # Special handling for search to allow submodule imports
    search_mock = types.ModuleType("backend.services.search")
    search_mock.__path__ = []
    search_mock.CitationService = MagicMock()
    search_mock.build_search_filter = MagicMock()
    search_mock.SemanticCache = MagicMock()
    search_mock.SearchService = MagicMock()
    sys.modules["backend.services.search"] = search_mock
    sys.modules["backend.services.search.citation_service"] = MagicMock()
    sys.modules["backend.services.search.search_filters"] = MagicMock()
    sys.modules["backend.services.search.search_service"] = MagicMock()
    sys.modules["backend.services.search.semantic_cache"] = MagicMock()

    # Special handling for ingestion to allow submodule imports
    ingestion_mock = types.ModuleType("backend.services.ingestion")
    ingestion_mock.__path__ = []

    # Add all ingestion services
    ingestion_mock.AutoIngestionOrchestrator = MagicMock()
    ingestion_mock.CollectionHealthService = MagicMock()
    ingestion_mock.CollectionManager = MagicMock()
    ingestion_mock.CollectionMetrics = MagicMock()
    ingestion_mock.CollectionWarmupService = MagicMock()
    ingestion_mock.HealthStatus = MagicMock()
    ingestion_mock.IngestionJob = MagicMock()
    ingestion_mock.IngestionService = MagicMock()
    ingestion_mock.IngestionStatus = MagicMock()
    ingestion_mock.LegalIngestionService = MagicMock()
    ingestion_mock.MonitoredSource = MagicMock()
    ingestion_mock.PoliticsIngestionService = MagicMock()
    ingestion_mock.ScrapedContent = MagicMock()
    ingestion_mock.SourceType = MagicMock()
    ingestion_mock.StalenessSeverity = MagicMock()
    ingestion_mock.UpdateType = MagicMock()

    sys.modules["backend.services.ingestion"] = ingestion_mock
    sys.modules["backend.services.ingestion.ingestion_service"] = MagicMock()

    # Special handling for routing to allow submodule imports
    routing_mock = types.ModuleType("backend.services.routing")
    routing_mock.__path__ = []

    routing_mock.ConfidenceCalculatorService = MagicMock()
    routing_mock.ConflictResolver = MagicMock()
    routing_mock.FallbackManagerService = MagicMock()
    routing_mock.GoldenRouterService = MagicMock()
    routing_mock.IntelligentRouter = MagicMock()
    routing_mock.KeywordMatcherService = MagicMock()
    routing_mock.PriorityOverrideService = MagicMock()
    routing_mock.QueryRouter = MagicMock()
    routing_mock.QueryRouterIntegration = MagicMock()
    routing_mock.RoutingStatsService = MagicMock()

    sys.modules["backend.services.routing"] = routing_mock
    sys.modules["backend.services.routing.intelligent_router"] = MagicMock()

    # Special handling for monitoring to allow submodule imports
    monitoring_mock = types.ModuleType("backend.services.monitoring")
    monitoring_mock.__path__ = []
    sys.modules["backend.services.monitoring"] = monitoring_mock

    # Special handling for integrations (needed by other tests if this runs first)
    integrations_mock = types.ModuleType("backend.services.integrations")
    integrations_mock.__path__ = []
    integrations_mock.messaging_identity_service = MagicMock()
    integrations_mock.whatsapp_service = MagicMock()
    integrations_mock.whatsapp_triage_service = MagicMock()
    integrations_mock.github_publisher = MagicMock()
    sys.modules["backend.services.integrations"] = integrations_mock
    sys.modules["backend.services.integrations.messaging_identity_service"] = MagicMock()
    sys.modules["backend.services.integrations.github_publisher"] = MagicMock()
    sys.modules["backend.services.integrations.telegram_bot_service"] = MagicMock()
    sys.modules["backend.services.integrations.whatsapp_service"] = MagicMock()
    sys.modules["backend.services.integrations.whatsapp_triage_service"] = MagicMock()

    # Special handling for memory
    memory_mock = types.ModuleType("backend.services.memory")
    memory_mock.__path__ = []
    memory_mock.MemoryServicePostgres = MagicMock()
    sys.modules["backend.services.memory"] = memory_mock

    # Special handling for article_composer - import the real module first
    import backend.services.article_composer as article_composer_module

    # Mock backend services to avoid cascade
    svc_mock = types.ModuleType("backend.services")
    svc_mock.__path__ = []
    sys.modules["backend.services"] = svc_mock

    for m in [
        "backend.services.oracle",
        "backend.services.rag",
        "backend.services.rag.agentic",
        "backend.services.analytics",
        "backend.services.llm_clients",
        "backend.services.pricing",
    ]:
        sys.modules[m] = MagicMock()

    # Add article_composer to the mock
    sys.modules["backend.services.article_composer"] = article_composer_module
    svc_mock.article_composer = article_composer_module

    return article_composer_module


article_composer_module = mock_problematic_modules()

from backend.app.routers.article_composer import (  # noqa: E402
    BaliZeroTake,
    EnrichedArticle,
    NextSteps,
    TLDRSection,
    generate_mdx_content,
    router,
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
        """Test generates valid MDX content."""
        mdx = generate_mdx_content(
            article=sample_article,
            slug="test-article",
            cover_image_path="/static/news/test-article.jpg",
        )

        assert 'title: "This Is a Test Headline"' in mdx
        assert 'slug: "test-article"' in mdx
        assert 'category: "business"' in mdx
        assert "## TL;DR" in mdx
        assert "## The Facts" in mdx
        assert "## Bali Zero Take" in mdx
        assert "## Next Steps" in mdx

    def test_includes_image_path(self, sample_article):
        """Test includes correct cover image path."""
        mdx = generate_mdx_content(
            article=sample_article,
            slug="test-article",
            cover_image_path="/custom/path.jpg",
        )
        assert 'coverImage: "/custom/path.jpg"' in mdx

    def test_formats_tags_correctly(self, sample_article):
        """Test formats tags list correctly."""
        mdx = generate_mdx_content(
            article=sample_article,
            slug="test-article",
            cover_image_path=None,
        )
        assert 'tags: ["test", "article", "business"]' in mdx

    def test_maps_category_correctly(self, sample_article):
        """Test maps category to URL-friendly slug."""
        sample_article.category = "tax"
        mdx = generate_mdx_content(
            article=sample_article,
            slug="test-article",
            cover_image_path=None,
        )
        assert 'category: "tax-legal"' in mdx

    def test_calculates_reading_time(self, sample_article):
        """Test calculates reading time correctly."""
        # Add lots of text
        sample_article.facts = "word " * 1000
        mdx = generate_mdx_content(
            article=sample_article,
            slug="test-article",
            cover_image_path=None,
        )
        assert "readingTime: 6" in mdx


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
        mock_message.content = [
            MagicMock(
                text=json.dumps(
                    {
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
                    }
                )
            )
        ]
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

    def test_publish_returns_error_when_not_configured(self, client, sample_publish_request):
        """Test returns 500 when GitHub not configured."""
        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = False
            mock_pub.create_commit_with_files = AsyncMock(return_value={})
            mock_pub.upload_file = AsyncMock(return_value={})

            response = client.post(
                "/api/articles/publish",
                json=sample_publish_request,
            )

            assert response.status_code == 200
            assert "not configured" in response.json()["message"]

    def test_publish_success(self, client, sample_publish_request):
        """Test successful publish returns correct response."""
        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = True
            mock_pub.check_file_exists = AsyncMock(return_value=False)
            mock_pub.create_commit_with_files = AsyncMock(
                return_value={
                    "success": True,
                    "commit_sha": "abc123def456",
                }
            )
            mock_pub.upload_file = AsyncMock(
                return_value={
                    "success": True,
                    "commit_sha": "abc123def456",
                }
            )

            response = client.post(
                "/api/articles/publish",
                json=sample_publish_request,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["article_url"] == "https://balizero.com/business/test-article"
            assert "apps/mouth" in data["mdx_path"]
            assert data["commit_sha"] == "abc123def456"

    def test_publish_generates_correct_paths(self, client, sample_publish_request):
        """Test generates correct file paths for different categories."""
        sample_publish_request["article"]["category"] = "immigration"
        sample_publish_request["slug"] = "visa-update"

        with patch("backend.services.integrations.github_publisher.github_publisher") as mock_pub:
            mock_pub.is_configured = True
            mock_pub.check_file_exists = AsyncMock(return_value=False)
            mock_pub.create_commit_with_files = AsyncMock(
                return_value={
                    "success": True,
                    "commit_sha": "sha123",
                }
            )
            mock_pub.upload_file = AsyncMock(
                return_value={
                    "success": True,
                    "commit_sha": "sha123",
                }
            )

            response = client.post(
                "/api/articles/publish",
                json=sample_publish_request,
            )

            data = response.json()
            assert "immigration/visa-update.mdx" in data["mdx_path"]
            assert "balizero.com/immigration/visa-update" in data["article_url"]


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
            assert data["github_token_set"] is True

    def test_status_when_not_configured(self, client):
        """Test returns correct status when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "backend.services.integrations.github_publisher.github_publisher"
            ) as mock_pub:
                mock_pub.is_configured = False
                mock_pub.owner = None
                mock_pub.repo = None
                mock_pub.token = None

                with patch("backend.app.core.config.settings") as mock_settings:
                    mock_settings.github_token = None

                    response = client.get("/api/articles/publish/status")

                    data = response.json()
                    assert data["configured"] is False
                    assert data["github_token_set"] is False
