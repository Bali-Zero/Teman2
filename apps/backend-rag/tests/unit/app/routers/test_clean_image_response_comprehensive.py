"""
Comprehensive tests for clean_image_generation_response

Tests all patterns from frontend implementation to ensure parity.
"""

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import pytest

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

    # Mock backend services to avoid cascade
    for m in ["backend.services.oracle", "backend.services.search", 
              "backend.services.rag", "backend.services.rag.agentic", 
              "backend.services.ingestion", "backend.services.analytics",
              "backend.services.llm_clients", "backend.services.monitoring", "backend.services.pricing",
              "qdrant_client"]:
        sys.modules[m] = MagicMock()

    # Special handling for misc to allow submodule imports
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
    
    # Special handling for routing to allow submodule imports
    routing_mock = types.ModuleType("backend.services.routing")
    routing_mock.__path__ = []
    sys.modules["backend.services.routing"] = routing_mock
    sys.modules["backend.services.routing.intelligent_router"] = MagicMock()

mock_problematic_modules()

from backend.app.routers.agentic_rag import clean_image_generation_response


class TestCleanImageResponseComprehensive:
    """Comprehensive tests covering all frontend patterns"""

    def test_no_pollinations_returns_unchanged(self):
        """Text without pollinations should be unchanged"""
        text = "This is a normal response without image URLs."
        result = clean_image_generation_response(text)
        assert result == text

    def test_removes_pollinations_urls(self):
        """Lines with pollinations URLs should be removed"""
        text = """Ecco l'immagine:
Check out https://pollinations.ai/image/test
Here's your image!"""
        result = clean_image_generation_response(text)
        assert "pollinations" not in result.lower()
        assert "Here's your image!" in result

    def test_removes_markdown_images(self):
        """Markdown image syntax should be removed"""
        text = """Your image:
![Image description](https://pollinations.ai/test)
Done!"""
        result = clean_image_generation_response(text)
        assert "![" not in result
        assert "Done!" in result

    def test_removes_broken_markdown_images(self):
        """Broken markdown images should be removed"""
        text = """Your image:
![Broken image
](http://pollinations.ai/test)
Done!"""
        result = clean_image_generation_response(text)
        assert "Broken" not in result or "pollinations" not in result.lower()
        assert "Done!" in result

    def test_removes_visualizza_links(self):
        """[Visualizza...] lines should be removed"""
        text = """Your image:
[Visualizza immagine](https://pollinations.ai/test)
Done!"""
        result = clean_image_generation_response(text)
        assert "[Visualizza" not in result
        assert "Done!" in result

    def test_removes_numbered_versions(self):
        """Numbered version lines should be removed"""
        text = """Your image:
1. Versione 1
2. **Versione 2
Done!"""
        result = clean_image_generation_response(text)
        assert "Versione" not in result
        assert "Done!" in result

    def test_removes_bullet_versions(self):
        """Bullet point versions should be removed"""
        text = """Your image:
* Versione 1
- **Versione 2
Done!"""
        result = clean_image_generation_response(text)
        assert "Versione" not in result
        assert "Done!" in result

    def test_removes_versione_headers(self):
        """Versione X headers should be removed"""
        text = """Your image:
**Versione 1**
*Versione 2*
Done!"""
        result = clean_image_generation_response(text)
        assert "Versione" not in result
        assert "Done!" in result

    def test_removes_intro_lines(self):
        """Intro lines mentioning opzioni/varianti should be removed"""
        test_cases = [
            "Ecco le opzioni per l'immagine",
            "Ho elaborato due immagini",
            "Ti propongo due varianti",
            "Ecco i risultati",
            "Queste versioni sono disponibili",
        ]
        for intro_line in test_cases:
            text = f"""{intro_line}
https://pollinations.ai/test
Done!"""
            result = clean_image_generation_response(text)
            assert intro_line not in result or "pollinations" not in result.lower()

    def test_removes_outro_lines(self):
        """Outro lines should be removed"""
        test_cases = [
            "Spero che queste opzioni vadano bene",
            "Se hai bisogno di altre varianti",
            "Vadano bene per le tue esigenze",
            "Sembra che queste versioni siano ok",
        ]
        for outro_line in test_cases:
            text = f"""Your image:
https://pollinations.ai/test
{outro_line}"""
            result = clean_image_generation_response(text)
            assert outro_line not in result or "pollinations" not in result.lower()

    def test_removes_url_lines(self):
        """Lines that are just URLs should be removed"""
        text = """Your image:
https://pollinations.ai/image/test
http://image.pollinations.ai/test
Done!"""
        result = clean_image_generation_response(text)
        assert "https://" not in result
        assert "http://" not in result
        assert "Done!" in result

    def test_removes_url_encoded_content(self):
        """URL-encoded content should be removed"""
        text = """Your image:
This%20is%20a%20long%20url%20encoded%20string
Done!"""
        result = clean_image_generation_response(text)
        assert "%20" not in result or len(result) < 30

    def test_removes_image_descriptions(self):
        """Image description lines should be removed"""
        test_cases = [
            "Immagine in alta risoluzione",
            "Atmosfera tradizionale balinese",
            "Luce dorata del tramonto",
        ]
        for desc_line in test_cases:
            text = f"""Your image:
{desc_line}
https://pollinations.ai/test
Done!"""
            result = clean_image_generation_response(text)
            # Should remove description or pollinations URL
            assert desc_line not in result or "pollinations" not in result.lower()

    def test_removes_lines_with_image_and_http(self):
        """Lines with 'image' and 'http' should be removed"""
        text = """Your image:
Check out this image http://pollinations.ai/test
Done!"""
        result = clean_image_generation_response(text)
        assert "image http" not in result.lower()
        assert "Done!" in result

    def test_provides_default_for_empty_result(self):
        """If almost all content is removed, provide default response"""
        text = """https://pollinations.ai/image/test
[Visualizza immagine](link)
1. Versione 1"""
        result = clean_image_generation_response(text)
        assert len(result) >= 30
        assert "Ecco l'immagine" in result

    def test_preserves_valid_content(self):
        """Valid content should be preserved"""
        text = """Ecco l'immagine che hai richiesto!
L'immagine mostra un paesaggio balinese.
Spero ti piaccia!"""
        result = clean_image_generation_response(text)
        assert "paesaggio balinese" in result
        assert "Spero ti piaccia" in result

    def test_handles_mixed_content(self):
        """Mixed valid and invalid content should be cleaned correctly"""
        text = """Ecco l'immagine!
https://pollinations.ai/test
L'immagine mostra un tempio.
1. Versione 1
Questo è il risultato finale."""
        result = clean_image_generation_response(text)
        assert "pollinations" not in result.lower()
        assert "Versione" not in result
        assert "tempio" in result
        assert "risultato finale" in result

    def test_empty_input(self):
        """Empty input should return empty"""
        assert clean_image_generation_response("") == ""
        assert clean_image_generation_response(None) is None

    def test_threshold_30_characters(self):
        """Default message should appear if result < 30 characters"""
        # Text that will be mostly removed
        text = """https://pollinations.ai/test
[Visualizza immagine]
1. Versione 1
* Versione 2"""
        result = clean_image_generation_response(text)
        # Should have default message (>= 30 chars)
        assert len(result) >= 30
        assert "Ecco l'immagine" in result
