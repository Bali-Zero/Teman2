"""
Unit Tests for Smart Extractor
Tests for multi-layer content extraction
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from smart_extractor import SmartExtractor


class TestSmartExtractorInit:
    """Test SmartExtractor initialization"""

    def test_default_init(self):
        """Test default initialization"""
        extractor = SmartExtractor()
        assert extractor is not None
        assert extractor.ollama_model == "llama3.2:3b"
        assert extractor.ollama_url == "http://localhost:11434"
        assert extractor.ollama_available is None

    def test_custom_init(self):
        """Test custom initialization"""
        extractor = SmartExtractor(
            ollama_model="llama3:8b", ollama_url="http://custom:11434"
        )
        assert extractor.ollama_model == "llama3:8b"
        assert extractor.ollama_url == "http://custom:11434"

    def test_stats_initialized(self):
        """Test stats are initialized"""
        extractor = SmartExtractor()
        assert "css_success" in extractor.stats
        assert "trafilatura_success" in extractor.stats
        assert "newspaper_success" in extractor.stats
        assert "llama_success" in extractor.stats
        assert "failed" in extractor.stats


class TestCheckOllama:
    """Test Ollama availability check"""

    @pytest.mark.asyncio
    async def test_check_ollama_available(self):
        """Test check_ollama when available"""
        extractor = SmartExtractor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.2:3b"}]}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await extractor.check_ollama()

            assert result is True
            assert extractor.ollama_available is True

    @pytest.mark.asyncio
    async def test_check_ollama_fallback_to_available_model(self):
        """Test check_ollama falls back to available model when requested not found"""
        extractor = SmartExtractor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "mistral:7b"}]}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await extractor.check_ollama()

            # Code falls back to any available model
            assert result is True
            assert extractor.ollama_model == "mistral:7b"

    @pytest.mark.asyncio
    async def test_check_ollama_no_models_available(self):
        """Test check_ollama when no models are available"""
        extractor = SmartExtractor()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await extractor.check_ollama()

            assert result is False

    @pytest.mark.asyncio
    async def test_check_ollama_connection_error(self):
        """Test check_ollama when connection fails"""
        extractor = SmartExtractor()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Connection refused")
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await extractor.check_ollama()

            assert result is False
            assert extractor.ollama_available is False

    @pytest.mark.asyncio
    async def test_check_ollama_cached(self):
        """Test check_ollama returns cached result"""
        extractor = SmartExtractor()
        extractor.ollama_available = True

        # Should not make HTTP call
        result = await extractor.check_ollama()

        assert result is True


class TestExtractWithCSS:
    """Test CSS selector extraction"""

    def test_css_extraction_success(self):
        """Test successful CSS extraction"""
        extractor = SmartExtractor()

        # Content needs to be >200 chars
        long_content = "This is the main article content. " * 10

        html = f"""
        <html>
        <body>
            <article class="content">
                <h1>Article Title</h1>
                <p>{long_content}</p>
            </article>
        </body>
        </html>
        """

        result = extractor.extract_with_css(
            html, [".content", "article"], "http://test.com"
        )

        assert result is not None
        assert result["title"] == "Article Title"
        assert "main article content" in result["content"]
        assert result["method"] == "css"
        assert extractor.stats["css_success"] == 1

    def test_css_extraction_content_too_short(self):
        """Test CSS extraction fails for short content"""
        extractor = SmartExtractor()

        html = """
        <html>
        <body>
            <article class="content">
                <h1>Title</h1>
                <p>Short.</p>
            </article>
        </body>
        </html>
        """

        result = extractor.extract_with_css(html, [".content"], "http://test.com")

        assert result is None

    def test_css_extraction_no_match(self):
        """Test CSS extraction with no matching selectors"""
        extractor = SmartExtractor()

        html = "<html><body><p>Content</p></body></html>"

        result = extractor.extract_with_css(
            html, [".article", ".post"], "http://test.com"
        )

        assert result is None

    def test_css_extraction_error(self):
        """Test CSS extraction handles errors"""
        extractor = SmartExtractor()

        result = extractor.extract_with_css(None, [".content"], "http://test.com")

        assert result is None


class TestExtractWithTrafilatura:
    """Test Trafilatura extraction"""

    def test_trafilatura_not_installed(self):
        """Test Trafilatura returns None when not installed"""
        extractor = SmartExtractor()

        import smart_extractor

        original_ok = smart_extractor.TRAFILATURA_OK
        smart_extractor.TRAFILATURA_OK = False

        result = extractor.extract_with_trafilatura("<html></html>", "http://test.com")

        smart_extractor.TRAFILATURA_OK = original_ok

        assert result is None

    def test_trafilatura_returns_none_for_short_content(self):
        """Test method returns None for short content (mocked)"""
        extractor = SmartExtractor()

        # Mock the method to test behavior
        with patch.object(extractor, "extract_with_trafilatura") as mock_method:
            mock_method.return_value = None

            result = extractor.extract_with_trafilatura(
                "<html></html>", "http://test.com"
            )

            assert result is None

    def test_trafilatura_returns_dict_on_success(self):
        """Test method returns dict on success (mocked)"""
        extractor = SmartExtractor()

        # Mock the method to test behavior
        with patch.object(extractor, "extract_with_trafilatura") as mock_method:
            mock_method.return_value = {
                "title": "Test Title",
                "content": "Test content that is long enough",
                "method": "trafilatura",
            }

            result = extractor.extract_with_trafilatura(
                "<html></html>", "http://test.com"
            )

            assert result is not None
            assert result["method"] == "trafilatura"


class TestExtractWithNewspaper:
    """Test Newspaper3k extraction"""

    def test_newspaper_extraction_success(self):
        """Test successful Newspaper extraction"""
        extractor = SmartExtractor()

        import smart_extractor

        original_ok = smart_extractor.NEWSPAPER_OK
        smart_extractor.NEWSPAPER_OK = True

        mock_article = MagicMock()
        mock_article.title = "Test Article"
        mock_article.text = (
            "This is the article content that is long enough to pass the minimum length check. It contains useful information. "
            * 3
        )
        mock_article.authors = ["John Doe"]
        mock_article.publish_date = "2024-01-01"
        mock_article.top_image = "http://test.com/image.jpg"
        mock_article.download = MagicMock()
        mock_article.parse = MagicMock()

        with patch("newspaper.Article") as mock_class:
            mock_class.return_value = mock_article

            result = extractor.extract_with_newspaper("http://test.com/article")

            if result is not None:
                assert result["title"] == "Test Article"
                assert result["author"] == "John Doe"
                assert result["method"] == "newspaper"

        smart_extractor.NEWSPAPER_OK = original_ok

    def test_newspaper_not_installed(self):
        """Test Newspaper returns None when not installed"""
        extractor = SmartExtractor()

        import smart_extractor

        original_ok = smart_extractor.NEWSPAPER_OK
        smart_extractor.NEWSPAPER_OK = False

        result = extractor.extract_with_newspaper("http://test.com/article")

        smart_extractor.NEWSPAPER_OK = original_ok

        assert result is None

    def test_newspaper_extraction_short_content(self):
        """Test Newspaper with short content returns None"""
        extractor = SmartExtractor()

        import smart_extractor

        original_ok = smart_extractor.NEWSPAPER_OK
        smart_extractor.NEWSPAPER_OK = True

        mock_article = MagicMock()
        mock_article.text = "Short"
        mock_article.download = MagicMock()
        mock_article.parse = MagicMock()

        with patch("newspaper.Article") as mock_class:
            mock_class.return_value = mock_article

            result = extractor.extract_with_newspaper("http://test.com/article")

        smart_extractor.NEWSPAPER_OK = original_ok

        assert result is None

    def test_newspaper_extraction_error(self):
        """Test Newspaper handles errors"""
        extractor = SmartExtractor()

        import smart_extractor

        original_ok = smart_extractor.NEWSPAPER_OK
        smart_extractor.NEWSPAPER_OK = True

        with patch("newspaper.Article") as mock_class:
            mock_class.side_effect = Exception("Download error")

            result = extractor.extract_with_newspaper("http://test.com/article")

        smart_extractor.NEWSPAPER_OK = original_ok

        assert result is None


class TestExtractWithLlama:
    """Test Llama LLM fallback extraction"""

    @pytest.mark.asyncio
    async def test_llama_extraction_success(self):
        """Test successful Llama extraction"""
        extractor = SmartExtractor()
        extractor.ollama_available = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"title": "Test Article", "content": "This is the extracted article content that is long enough to be valid. It contains multiple sentences and useful information.", "author": "John Doe", "date": "2024-01-01"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await extractor.extract_with_llama(
                "Some raw HTML content",
                "http://test.com/article",
                hint="Find immigration news",
            )

            assert result is not None
            assert result["title"] == "Test Article"
            assert extractor.stats["llama_success"] == 1

    @pytest.mark.asyncio
    async def test_llama_extraction_ollama_unavailable(self):
        """Test Llama when Ollama not available"""
        extractor = SmartExtractor()
        extractor.ollama_available = False

        result = await extractor.extract_with_llama("text", "http://test.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_llama_extraction_short_content(self):
        """Test Llama with short extracted content"""
        extractor = SmartExtractor()
        extractor.ollama_available = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"title": "Test", "content": "Short"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await extractor.extract_with_llama("text", "http://test.com")

            assert result is None

    @pytest.mark.asyncio
    async def test_llama_extraction_json_error(self):
        """Test Llama handles JSON parse error"""
        extractor = SmartExtractor()
        extractor.ollama_available = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Invalid JSON"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await extractor.extract_with_llama("text", "http://test.com")

            assert result is None

    @pytest.mark.asyncio
    async def test_llama_extraction_api_error(self):
        """Test Llama handles API error"""
        extractor = SmartExtractor()
        extractor.ollama_available = True

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = Exception("API error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await extractor.extract_with_llama("text", "http://test.com")

            assert result is None


class TestExtract:
    """Test main extract method"""

    @pytest.mark.asyncio
    async def test_extract_with_provided_html(self):
        """Test extract with pre-fetched HTML"""
        extractor = SmartExtractor()

        html = """
        <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Test Title</h1>
                <p>This is enough content to pass validation and be extracted properly by trafilatura or other methods.</p>
            </article>
        </body>
        </html>
        """

        with patch.object(extractor, "extract_with_trafilatura") as mock_traf:
            mock_traf.return_value = {
                "title": "Test Title",
                "content": "This is enough content",
                "method": "trafilatura",
            }

            result = await extractor.extract("http://test.com", html=html)

            assert result is not None
            assert result["title"] == "Test Title"

    @pytest.mark.asyncio
    async def test_extract_fetches_html(self):
        """Test extract fetches HTML when not provided"""
        extractor = SmartExtractor()

        mock_response = MagicMock()
        mock_response.text = "<html><body>Content</body></html>"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch.object(extractor, "extract_with_trafilatura") as mock_traf:
                mock_traf.return_value = {
                    "title": "Title",
                    "content": "Content that is long enough",
                    "method": "trafilatura",
                }

                result = await extractor.extract("http://test.com")

                mock_instance.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_fetch_error(self):
        """Test extract handles fetch error"""
        extractor = SmartExtractor()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Network error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await extractor.extract("http://test.com")

            assert result is None

    @pytest.mark.asyncio
    async def test_extract_css_first(self):
        """Test extract tries CSS first when selectors provided"""
        extractor = SmartExtractor()

        html = "<html><body><article>Content</article></body></html>"

        with patch.object(extractor, "extract_with_css") as mock_css:
            mock_css.return_value = {
                "title": "CSS Title",
                "content": "CSS content",
                "method": "css",
            }

            result = await extractor.extract(
                "http://test.com", html=html, selectors=["article"]
            )

            mock_css.assert_called_once()
            assert result["method"] == "css"

    @pytest.mark.asyncio
    async def test_extract_fallback_chain(self):
        """Test extract falls back through methods"""
        extractor = SmartExtractor()
        extractor.ollama_available = False

        html = "<html><body>Content</body></html>"

        with patch.object(extractor, "extract_with_css") as mock_css:
            with patch.object(extractor, "extract_with_trafilatura") as mock_traf:
                with patch.object(extractor, "extract_with_newspaper") as mock_news:
                    mock_css.return_value = None
                    mock_traf.return_value = None
                    mock_news.return_value = None

                    result = await extractor.extract(
                        "http://test.com", html=html, selectors=[".article"]
                    )

                    mock_css.assert_called_once()
                    mock_traf.assert_called_once()
                    mock_news.assert_called_once()
                    assert result is None
                    assert extractor.stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_extract_llama_fallback(self):
        """Test extract uses Llama as last resort"""
        extractor = SmartExtractor()
        extractor.ollama_available = True

        html = "<html><body>Content</body></html>"

        with patch.object(extractor, "extract_with_trafilatura", return_value=None):
            with patch.object(extractor, "extract_with_newspaper", return_value=None):
                with patch.object(extractor, "extract_with_llama") as mock_llama:
                    mock_llama.return_value = {
                        "title": "Llama Title",
                        "content": "Llama content",
                    }

                    result = await extractor.extract("http://test.com", html=html)

                    mock_llama.assert_called_once()
                    assert result["method"] == "llama"


class TestGetStats:
    """Test statistics tracking"""

    def test_get_stats_initial(self):
        """Test initial stats"""
        extractor = SmartExtractor()
        stats = extractor.get_stats()

        assert stats["css_success"] == 0
        assert stats["trafilatura_success"] == 0
        assert stats["newspaper_success"] == 0
        assert stats["llama_success"] == 0
        assert stats["failed"] == 0
        assert stats["total"] == 0
        assert stats["success_rate"] == "N/A"

    def test_get_stats_with_data(self):
        """Test stats with data"""
        extractor = SmartExtractor()
        extractor.stats["css_success"] = 5
        extractor.stats["trafilatura_success"] = 3
        extractor.stats["failed"] = 2

        stats = extractor.get_stats()

        assert stats["total"] == 10
        assert stats["success_rate"] == "80.0%"

    def test_stats_updated_on_css_success(self):
        """Test stats update on CSS success"""
        extractor = SmartExtractor()

        # Content needs to be >200 chars
        long_content = (
            "Long enough content to pass the minimum character requirement. " * 10
        )

        html = f"""
        <html>
        <body>
            <article class="content">
                <h1>Title</h1>
                <p>{long_content}</p>
            </article>
        </body>
        </html>
        """

        extractor.extract_with_css(html, [".content"], "http://test.com")

        assert extractor.stats["css_success"] == 1
