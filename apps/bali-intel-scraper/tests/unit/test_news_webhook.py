"""
Unit Tests for News Webhook
Tests for BaliZero API integration
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from news_webhook import BaliZeroNewsWebhook


class TestNewsWebhookInit:
    """Test BaliZeroNewsWebhook initialization"""

    def test_default_init(self):
        """Test default initialization"""
        webhook = BaliZeroNewsWebhook()
        assert webhook is not None
        assert hasattr(webhook, "api_base_url")
        assert hasattr(webhook, "news_endpoint")

    def test_custom_url(self):
        """Test custom API URL"""
        webhook = BaliZeroNewsWebhook(api_base_url="https://custom.api.com")
        assert webhook.api_base_url == "https://custom.api.com"

    def test_has_tier_mapping(self):
        """Test tier to priority mapping exists"""
        webhook = BaliZeroNewsWebhook()
        assert "T1" in webhook.tier_priority_map
        assert "T2" in webhook.tier_priority_map

    def test_has_category_mapping(self):
        """Test category mapping exists"""
        webhook = BaliZeroNewsWebhook()
        assert "immigration" in webhook.category_map
        assert "tax" in webhook.category_map

    def test_stats_initialized(self):
        """Test stats are initialized"""
        webhook = BaliZeroNewsWebhook()
        assert "sent" in webhook.stats
        assert "failed" in webhook.stats


class TestCategoryMapping:
    """Test category mapping"""

    def test_map_immigration(self):
        """Test immigration category mapping"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("immigration") == "immigration"

    def test_map_business(self):
        """Test business category mapping"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("business") == "business"

    def test_map_unknown(self):
        """Test unknown category defaults to business"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("unknown") == "business"


class TestPriorityMapping:
    """Test tier to priority mapping"""

    def test_map_t1(self):
        """Test T1 maps to high"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_priority("T1") == "high"

    def test_map_t2(self):
        """Test T2 maps to medium"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_priority("T2") == "medium"

    def test_map_unknown(self):
        """Test unknown tier defaults to medium"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_priority("unknown") == "medium"


class TestGenerateSummary:
    """Test summary generation"""

    def test_short_content(self):
        """Test summary of short content"""
        webhook = BaliZeroNewsWebhook()
        summary = webhook._generate_summary("Short paragraph.")
        assert summary == "Short paragraph."

    def test_long_content_truncated(self):
        """Test long content is truncated"""
        webhook = BaliZeroNewsWebhook()
        long_content = "x" * 500
        summary = webhook._generate_summary(long_content, max_length=100)
        assert len(summary) <= 100


class TestSendNewsItem:
    """Test sending news items"""

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Test successful send"""
        webhook = BaliZeroNewsWebhook()

        item = {
            "title": "Test Article",
            "summary": "Test summary",
            "content": "Content",
            "source": "Test Source",
            "category": "immigration",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await webhook.send_news_item(item)

            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self):
        """Test failed send"""
        webhook = BaliZeroNewsWebhook()

        item = {"title": "Test"}

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await webhook.send_news_item(item)

            assert result is False

    @pytest.mark.asyncio
    async def test_dry_run(self):
        """Test dry run mode"""
        webhook = BaliZeroNewsWebhook()

        item = {"title": "Test", "content": "Content"}

        result = await webhook.send_news_item(item, dry_run=True)

        assert result is True


class TestExtractMetadata:
    """Test metadata extraction"""

    def test_extract_from_frontmatter(self):
        """Test extracting metadata from markdown frontmatter"""
        webhook = BaliZeroNewsWebhook()

        content = """---
title: Test Article
source: Jakarta Post
---

Article content here.
"""

        metadata = webhook._extract_metadata_from_markdown(content)

        assert metadata.get("title") == "Test Article"
        assert metadata.get("source") == "Jakarta Post"

    def test_no_frontmatter(self):
        """Test with no frontmatter"""
        webhook = BaliZeroNewsWebhook()

        content = "Just plain content without frontmatter."

        metadata = webhook._extract_metadata_from_markdown(content)

        assert metadata == {}


class TestParseRawFile:
    """Test parsing raw markdown files"""

    def test_parse_valid_file(self, tmp_path):
        """Test parsing a valid markdown file"""
        webhook = BaliZeroNewsWebhook()

        test_file = tmp_path / "test.md"
        test_file.write_text("""---
title: Test Article
source: Jakarta Post
category: immigration
tier: T1
---

This is the article content.
""")

        result = webhook.parse_raw_file(test_file)

        assert result is not None
        assert result["title"] == "Test Article"
        assert result["source"] == "Jakarta Post"

    def test_parse_missing_title(self, tmp_path):
        """Test parsing file without title returns None"""
        webhook = BaliZeroNewsWebhook()

        test_file = tmp_path / "test.md"
        test_file.write_text("""---
source: Test
---
""")

        result = webhook.parse_raw_file(test_file)

        assert result is None

    def test_parse_file_exception(self, tmp_path):
        """Test parse_raw_file handles file read errors"""
        webhook = BaliZeroNewsWebhook()

        # Non-existent file
        nonexistent = tmp_path / "nonexistent.md"

        result = webhook.parse_raw_file(nonexistent)

        assert result is None

    def test_parse_with_all_metadata(self, tmp_path):
        """Test parsing file with all metadata fields"""
        webhook = BaliZeroNewsWebhook()

        test_file = tmp_path / "test.md"
        test_file.write_text("""---
title: Full Test Article
source: Jakarta Post
url: https://example.com/article
category: visa
tier: T1
published_at: 2025-01-01
scraped_at: 2025-01-02
---

This is comprehensive article content with multiple paragraphs.

Another paragraph here.
""")

        result = webhook.parse_raw_file(test_file)

        assert result is not None
        assert result["title"] == "Full Test Article"
        assert result["sourceUrl"] == "https://example.com/article"
        assert result["category"] == "immigration"  # visa maps to immigration
        assert result["priority"] == "high"  # T1 maps to high
        assert result["publishedAt"] == "2025-01-01"


class TestExtractContentBody:
    """Test content body extraction"""

    def test_extract_with_headers(self):
        """Test extraction removes markdown headers"""
        webhook = BaliZeroNewsWebhook()

        content = """---
title: Test
---

# Main Header

Regular content here.

## Sub Header

More content.
"""
        body = webhook._extract_content_body(content)

        assert "# Main Header" not in body
        assert "## Sub Header" not in body
        assert "Regular content here." in body
        assert "More content." in body

    def test_extract_with_metadata_lines(self):
        """Test extraction removes metadata lines"""
        webhook = BaliZeroNewsWebhook()

        content = """---
title: Test
---

**Source:** Jakarta Post
**URL:** https://example.com
**Published:** 2025-01-01
**Scraped:** 2025-01-02

Actual content here.

---

More content after separator.
"""
        body = webhook._extract_content_body(content)

        assert "**Source:**" not in body
        assert "**URL:**" not in body
        assert "**Published:**" not in body
        assert "**Scraped:**" not in body
        assert "Actual content here." in body


class TestGenerateSummaryEdgeCases:
    """Test summary generation edge cases"""

    def test_no_paragraphs(self):
        """Test summary generation with no paragraph breaks"""
        webhook = BaliZeroNewsWebhook()

        # Content with no paragraph breaks
        content = ""
        summary = webhook._generate_summary(content, max_length=100)

        assert len(summary) <= 100

    def test_multiple_paragraphs(self):
        """Test takes first paragraph only"""
        webhook = BaliZeroNewsWebhook()

        content = """First paragraph here.

Second paragraph here.

Third paragraph."""

        summary = webhook._generate_summary(content)

        assert summary == "First paragraph here."


class TestSendNewsItemEdgeCases:
    """Test send_news_item edge cases"""

    @pytest.mark.asyncio
    async def test_send_non_success_response(self):
        """Test send with non-success response from API"""
        webhook = BaliZeroNewsWebhook()

        item = {"title": "Test Article"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": False, "error": "Duplicate"}
        mock_response.text = '{"success": false}'

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await webhook.send_news_item(item)

            assert result is False
            assert webhook.stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_send_exception_handling(self):
        """Test send handles httpx exceptions"""
        webhook = BaliZeroNewsWebhook()

        item = {"title": "Test Article"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = Exception("Connection error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await webhook.send_news_item(item)

            assert result is False
            assert webhook.stats["failed"] == 1


class TestSendAllRaw:
    """Test send_all_raw function"""

    @pytest.mark.asyncio
    async def test_send_all_raw_dry_run(self, tmp_path):
        """Test sending all raw items in dry run mode"""
        webhook = BaliZeroNewsWebhook()

        # Create a raw directory with files
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        test_file = raw_dir / "test_article.md"
        test_file.write_text("""---
title: Test Article
source: Test Source
category: immigration
tier: T2
---

This is test content for the article.
""")

        stats = await webhook.send_all_raw(raw_dir=raw_dir, limit=10, dry_run=True)

        assert stats["sent"] == 1
        assert stats["failed"] == 0

    @pytest.mark.asyncio
    async def test_send_all_raw_with_categories(self, tmp_path):
        """Test sending all raw with specific categories"""
        webhook = BaliZeroNewsWebhook()

        # Create category-specific directories
        raw_dir = tmp_path / "raw"
        immigration_dir = raw_dir / "immigration"
        immigration_dir.mkdir(parents=True)

        test_file = immigration_dir / "test.md"
        test_file.write_text("""---
title: Immigration Article
source: Jakarta Post
---

Immigration content.
""")

        stats = await webhook.send_all_raw(
            raw_dir=raw_dir, categories=["immigration"], dry_run=True
        )

        assert stats["sent"] == 1

    @pytest.mark.asyncio
    async def test_send_all_raw_with_limit(self, tmp_path):
        """Test send_all_raw respects limit"""
        webhook = BaliZeroNewsWebhook()

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Create multiple files
        for i in range(5):
            test_file = raw_dir / f"test_{i}.md"
            test_file.write_text(f"""---
title: Article {i}
source: Source {i}
---

Content {i}.
""")

        stats = await webhook.send_all_raw(raw_dir=raw_dir, limit=2, dry_run=True)

        # Should only send 2 items due to limit
        assert stats["sent"] == 2

    @pytest.mark.asyncio
    async def test_send_all_raw_skips_invalid(self, tmp_path):
        """Test send_all_raw skips files that fail to parse"""
        webhook = BaliZeroNewsWebhook()

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Valid file
        valid_file = raw_dir / "valid.md"
        valid_file.write_text("""---
title: Valid Article
source: Valid Source
---

Valid content.
""")

        # Invalid file (no title)
        invalid_file = raw_dir / "invalid.md"
        invalid_file.write_text("""---
source: Invalid
---

No title here.
""")

        stats = await webhook.send_all_raw(raw_dir=raw_dir, dry_run=True)

        assert stats["sent"] == 1
        assert stats["skipped"] == 1

    @pytest.mark.asyncio
    async def test_send_all_raw_empty_dir(self, tmp_path):
        """Test send_all_raw with empty directory"""
        webhook = BaliZeroNewsWebhook()

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        stats = await webhook.send_all_raw(raw_dir=raw_dir, dry_run=True)

        assert stats["sent"] == 0

    @pytest.mark.asyncio
    async def test_send_all_raw_nonexistent_category(self, tmp_path):
        """Test send_all_raw with nonexistent category directory"""
        webhook = BaliZeroNewsWebhook()

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        stats = await webhook.send_all_raw(
            raw_dir=raw_dir, categories=["nonexistent"], dry_run=True
        )

        assert stats["sent"] == 0


class TestSendSingle:
    """Test send_single method"""

    @pytest.mark.asyncio
    async def test_send_single(self):
        """Test send_single delegates to send_news_item"""
        webhook = BaliZeroNewsWebhook()

        item = {"title": "Test", "content": "Content"}

        result = await webhook.send_single(item, dry_run=True)

        assert result is True
        assert webhook.stats["sent"] == 1


class TestCategoryMappingEdgeCases:
    """Test all category mappings"""

    def test_map_visa(self):
        """Test visa maps to immigration"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("visa") == "immigration"

    def test_map_pt_pma(self):
        """Test pt_pma maps to business"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("pt_pma") == "business"

    def test_map_real_estate(self):
        """Test real_estate maps to property"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("real_estate") == "property"

    def test_map_legal(self):
        """Test legal maps to business"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("legal") == "business"

    def test_map_banking(self):
        """Test banking maps to business"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("banking") == "business"

    def test_map_employment(self):
        """Test employment maps to business"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("employment") == "business"

    def test_map_lifestyle(self):
        """Test lifestyle category"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("lifestyle") == "lifestyle"

    def test_map_tech(self):
        """Test tech category"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("tech") == "tech"

    def test_map_tax(self):
        """Test tax category"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("tax") == "tax"

    def test_map_property(self):
        """Test property category"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("property") == "property"

    def test_map_uppercase(self):
        """Test uppercase category mapping"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_category("IMMIGRATION") == "immigration"


class TestPriorityMappingEdgeCases:
    """Test priority mapping edge cases"""

    def test_map_t3(self):
        """Test T3 maps to low"""
        webhook = BaliZeroNewsWebhook()
        assert webhook._map_priority("T3") == "low"


class TestMain:
    """Test main function"""

    def test_main_no_args(self):
        """Test main with no arguments prints help"""
        from news_webhook import main

        with patch("sys.argv", ["news_webhook.py"]):
            with patch("argparse.ArgumentParser.print_help") as mock_help:
                main()
                mock_help.assert_called_once()

    def test_main_send_raw_dry_run(self, tmp_path):
        """Test main with --send-raw --dry-run"""
        from news_webhook import main

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        test_file = raw_dir / "test.md"
        test_file.write_text("""---
title: Test
source: Test
---

Content.
""")

        with patch("sys.argv", ["news_webhook.py", "--send-raw", "--dry-run"]):
            with patch("news_webhook.BaliZeroNewsWebhook.send_all_raw") as mock_send:
                mock_send.return_value = {"sent": 1, "failed": 0, "skipped": 0}
                main()

    def test_main_with_custom_url(self):
        """Test main with custom API URL"""
        from news_webhook import main

        with patch(
            "sys.argv",
            [
                "news_webhook.py",
                "--send-raw",
                "--dry-run",
                "--api-url",
                "https://custom.api.com",
            ],
        ):
            with patch("news_webhook.BaliZeroNewsWebhook.send_all_raw") as mock_send:
                mock_send.return_value = {"sent": 0, "failed": 0, "skipped": 0}
                main()

    def test_main_with_categories_and_limit(self):
        """Test main with categories and limit"""
        from news_webhook import main

        with patch(
            "sys.argv",
            [
                "news_webhook.py",
                "--send-raw",
                "--categories",
                "immigration",
                "business",
                "--limit",
                "10",
                "--dry-run",
            ],
        ):
            with patch("news_webhook.BaliZeroNewsWebhook.send_all_raw") as mock_send:
                mock_send.return_value = {"sent": 0, "failed": 0, "skipped": 0}
                main()


class TestEnvVarInit:
    """Test initialization with environment variables"""

    def test_init_with_env_var(self):
        """Test initialization uses BALIZERO_API_URL env var"""
        import os

        with patch.dict(os.environ, {"BALIZERO_API_URL": "https://env.api.com"}):
            webhook = BaliZeroNewsWebhook()
            assert webhook.api_base_url == "https://env.api.com"

    def test_custom_url_overrides_env(self):
        """Test custom URL overrides environment variable"""
        import os

        with patch.dict(os.environ, {"BALIZERO_API_URL": "https://env.api.com"}):
            webhook = BaliZeroNewsWebhook(api_base_url="https://custom.api.com")
            assert webhook.api_base_url == "https://custom.api.com"
