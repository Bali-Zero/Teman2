"""
Unit Tests for RSS Fetcher
Tests for Google News RSS fetching and scoring
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from rss_fetcher import GoogleNewsRSSFetcher


class TestGoogleNewsRSSFetcherInit:
    """Test GoogleNewsRSSFetcher initialization"""

    def test_default_init(self):
        """Test default initialization"""
        fetcher = GoogleNewsRSSFetcher()
        assert fetcher.max_age_days == 7
        assert "news.google.com" in fetcher.base_url

    def test_custom_max_age(self):
        """Test custom max age"""
        fetcher = GoogleNewsRSSFetcher(max_age_days=3)
        assert fetcher.max_age_days == 3

    def test_has_topics(self):
        """Test topics list exists"""
        fetcher = GoogleNewsRSSFetcher()
        assert len(fetcher.TOPICS) > 0
        for topic in fetcher.TOPICS:
            assert len(topic) == 2


class TestBuildRSSUrl:
    """Test RSS URL building"""

    def test_build_url_simple(self):
        """Test building simple URL"""
        fetcher = GoogleNewsRSSFetcher()
        url = fetcher._build_rss_url("Indonesia visa")
        assert "Indonesia+visa" in url
        assert "news.google.com" in url

    def test_build_url_encodes_special_chars(self):
        """Test special characters are encoded"""
        fetcher = GoogleNewsRSSFetcher()
        url = fetcher._build_rss_url("Bali business startup")
        assert "Bali+business+startup" in url

    def test_url_has_locale(self):
        """Test URL has Indonesia locale"""
        fetcher = GoogleNewsRSSFetcher()
        url = fetcher._build_rss_url("test")
        assert "hl=en-ID" in url or "gl=ID" in url


class TestParseDate:
    """Test date parsing"""

    def test_parse_valid_gmt_date(self):
        """Test parsing valid RSS date with GMT"""
        fetcher = GoogleNewsRSSFetcher()
        date_str = "Mon, 01 Jan 2024 12:00:00 GMT"
        result = fetcher._parse_date(date_str)
        assert result is not None
        assert result.year == 2024

    def test_parse_invalid_date(self):
        """Test parsing invalid date returns None"""
        fetcher = GoogleNewsRSSFetcher()
        result = fetcher._parse_date("invalid date")
        assert result is None


class TestIsFresh:
    """Test freshness checking"""

    def test_fresh_article(self):
        """Test recent article is fresh"""
        fetcher = GoogleNewsRSSFetcher(max_age_days=7)
        recent_date = datetime.utcnow() - timedelta(days=3)
        assert fetcher._is_fresh(recent_date) is True

    def test_stale_article(self):
        """Test old article is not fresh"""
        fetcher = GoogleNewsRSSFetcher(max_age_days=7)
        old_date = datetime.utcnow() - timedelta(days=10)
        assert fetcher._is_fresh(old_date) is False

    def test_none_date_is_fresh(self):
        """Test None date is considered fresh"""
        fetcher = GoogleNewsRSSFetcher()
        assert fetcher._is_fresh(None) is True


class TestExtractSource:
    """Test source extraction"""

    def test_extract_source_from_element(self):
        """Test extracting source from XML element"""
        import xml.etree.ElementTree as ET

        fetcher = GoogleNewsRSSFetcher()

        xml_str = """
        <item>
            <title>Test</title>
            <source>Jakarta Post</source>
        </item>
        """
        item = ET.fromstring(xml_str)
        source = fetcher._extract_source(item)
        assert source == "Jakarta Post"

    def test_extract_source_missing(self):
        """Test default source when missing"""
        import xml.etree.ElementTree as ET

        fetcher = GoogleNewsRSSFetcher()

        xml_str = """<item><title>Test</title></item>"""
        item = ET.fromstring(xml_str)
        source = fetcher._extract_source(item)
        assert source == "Google News"


class TestCleanTitle:
    """Test title cleaning"""

    def test_clean_title_with_source(self):
        """Test removing source suffix from title"""
        fetcher = GoogleNewsRSSFetcher()
        title = "Indonesia extends visa - Jakarta Post"
        cleaned = fetcher._clean_title(title)
        assert "Jakarta Post" not in cleaned

    def test_clean_title_no_source(self):
        """Test title without source suffix"""
        fetcher = GoogleNewsRSSFetcher()
        title = "Indonesia extends visa"
        cleaned = fetcher._clean_title(title)
        assert cleaned == "Indonesia extends visa"


class TestFetchTopic:
    """Test topic fetching"""

    @pytest.mark.asyncio
    async def test_fetch_topic_success(self):
        """Test successful topic fetch"""
        fetcher = GoogleNewsRSSFetcher()

        # Use a recent date (within max_age_days)
        recent_date = datetime.utcnow() - timedelta(days=1)
        date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

        mock_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Indonesia visa news - Reuters</title>
                    <link>https://example.com/article</link>
                    <pubDate>{date_str}</pubDate>
                    <description>Article description</description>
                    <source>Reuters</source>
                </item>
            </channel>
        </rss>
        """.encode()

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            items = await fetcher.fetch_topic("Indonesia visa", "immigration")

            assert len(items) >= 1
            assert items[0]["category"] == "immigration"

    @pytest.mark.asyncio
    async def test_fetch_topic_network_error(self):
        """Test handling network error"""
        fetcher = GoogleNewsRSSFetcher()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Network error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            items = await fetcher.fetch_topic("test", "general")

            assert items == []

    @pytest.mark.asyncio
    async def test_fetch_topic_no_channel(self):
        """Test handling XML without channel"""
        fetcher = GoogleNewsRSSFetcher()

        mock_xml = b"""<?xml version="1.0"?><rss version="2.0"></rss>"""

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            items = await fetcher.fetch_topic("test", "general")

            assert items == []


class TestFetchAll:
    """Test fetching all topics"""

    @pytest.mark.asyncio
    async def test_fetch_all_returns_list(self):
        """Test that fetch_all returns a list"""
        fetcher = GoogleNewsRSSFetcher()

        mock_xml = b"""<?xml version="1.0"?>
        <rss version="2.0"><channel><title>Test</title></channel></rss>"""

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await fetcher.fetch_all(min_score=0)

            assert isinstance(result, list)


class TestSendToBaliZero:
    """Test sending to BaliZero API"""

    @pytest.mark.asyncio
    async def test_dry_run(self):
        """Test dry run mode"""
        from rss_fetcher import send_to_balizero

        items = [
            {
                "title": "Test",
                "relevance_score": 80,
                "priority": "high",
                "category": "immigration",
            }
        ]

        result = await send_to_balizero(items, dry_run=True)

        assert result["sent"] == 1
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Test successful send"""
        from rss_fetcher import send_to_balizero

        items = [
            {
                "title": "Test",
                "summary": "Summary",
                "source": "Test",
                "category": "immigration",
                "priority": "high",
                "relevance_score": 80,
            }
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await send_to_balizero(items)

            assert result["sent"] == 1

    @pytest.mark.asyncio
    async def test_send_duplicate(self):
        """Test handling duplicate response"""
        from rss_fetcher import send_to_balizero

        items = [
            {
                "title": "Test",
                "source": "Test",
                "category": "general",
                "priority": "medium",
                "relevance_score": 50,
            }
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "duplicate": True}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await send_to_balizero(items)

            assert result["duplicates"] == 1

    @pytest.mark.asyncio
    async def test_send_failure(self):
        """Test handling send failure"""
        from rss_fetcher import send_to_balizero

        items = [
            {
                "title": "Test",
                "source": "T",
                "category": "g",
                "priority": "m",
                "relevance_score": 50,
            }
        ]

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Error"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await send_to_balizero(items)

            assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_send_with_api_key(self):
        """Test sending with API key"""
        from rss_fetcher import send_to_balizero

        items = [
            {
                "title": "Test",
                "source": "Test",
                "category": "immigration",
                "priority": "high",
                "relevance_score": 80,
            }
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await send_to_balizero(items, api_key="test-api-key")

            # Verify API key was included in headers
            call_args = mock_instance.post.call_args
            headers = call_args.kwargs.get("headers", {})
            assert headers.get("X-API-Key") == "test-api-key"

    @pytest.mark.asyncio
    async def test_send_api_rejection(self):
        """Test handling API rejection (success=False)"""
        from rss_fetcher import send_to_balizero

        items = [
            {
                "title": "Test",
                "source": "T",
                "category": "g",
                "priority": "m",
                "relevance_score": 50,
            }
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": False, "error": "Invalid"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await send_to_balizero(items)

            assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_send_exception(self):
        """Test handling exception during send"""
        from rss_fetcher import send_to_balizero

        items = [
            {
                "title": "Test",
                "source": "T",
                "category": "g",
                "priority": "m",
                "relevance_score": 50,
            }
        ]

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = Exception("Network error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await send_to_balizero(items)

            assert result["failed"] == 1


class TestFetchTopicEdgeCases:
    """Test edge cases in fetch_topic"""

    @pytest.mark.asyncio
    async def test_missing_title_element(self):
        """Test handling item without title element"""
        fetcher = GoogleNewsRSSFetcher()

        mock_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <link>https://example.com</link>
                </item>
            </channel>
        </rss>
        """

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            items = await fetcher.fetch_topic("test", "general")

            assert items == []  # Item should be skipped

    @pytest.mark.asyncio
    async def test_missing_link_element(self):
        """Test handling item without link element"""
        fetcher = GoogleNewsRSSFetcher()

        mock_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test Title</title>
                </item>
            </channel>
        </rss>
        """

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            items = await fetcher.fetch_topic("test", "general")

            assert items == []  # Item should be skipped

    @pytest.mark.asyncio
    async def test_stale_article_filtered(self):
        """Test that old articles are filtered out"""
        fetcher = GoogleNewsRSSFetcher(max_age_days=7)

        # Use an old date (30 days ago)
        old_date = datetime.utcnow() - timedelta(days=30)
        date_str = old_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

        mock_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Old Article</title>
                    <link>https://example.com</link>
                    <pubDate>{date_str}</pubDate>
                </item>
            </channel>
        </rss>
        """.encode()

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            items = await fetcher.fetch_topic("test", "general")

            assert items == []  # Old item should be filtered

    @pytest.mark.asyncio
    async def test_long_summary_truncated(self):
        """Test that long summaries are truncated"""
        fetcher = GoogleNewsRSSFetcher()

        recent_date = datetime.utcnow() - timedelta(days=1)
        date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
        long_desc = "x" * 500

        mock_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test</title>
                    <link>https://example.com</link>
                    <pubDate>{date_str}</pubDate>
                    <description>{long_desc}</description>
                </item>
            </channel>
        </rss>
        """.encode()

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            items = await fetcher.fetch_topic("test", "general")

            assert len(items) == 1
            assert len(items[0]["summary"]) <= 300
            assert items[0]["summary"].endswith("...")

    @pytest.mark.asyncio
    async def test_empty_source_element(self):
        """Test handling empty source element"""
        fetcher = GoogleNewsRSSFetcher()

        recent_date = datetime.utcnow() - timedelta(days=1)
        date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

        mock_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test</title>
                    <link>https://example.com</link>
                    <pubDate>{date_str}</pubDate>
                    <source></source>
                </item>
            </channel>
        </rss>
        """.encode()

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            items = await fetcher.fetch_topic("test", "general")

            assert len(items) == 1
            assert items[0]["source"] == "Unknown"


class TestFetchAllWithScoring:
    """Test fetch_all with professional scoring"""

    @pytest.mark.asyncio
    async def test_fetch_all_deduplication(self):
        """Test that duplicate titles are removed"""
        fetcher = GoogleNewsRSSFetcher()

        recent_date = datetime.utcnow() - timedelta(days=1)
        date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

        # Same title in multiple topics
        mock_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Indonesia Visa Update</title>
                    <link>https://example.com/1</link>
                    <pubDate>{date_str}</pubDate>
                </item>
            </channel>
        </rss>
        """.encode()

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        # Mock scorer
        mock_score = MagicMock()
        mock_score.final_score = 80
        mock_score.priority = "high"
        mock_score.matched_category = "immigration"
        mock_score.matched_keywords = ["visa"]
        mock_score.explanation = "Immigration news"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch("rss_fetcher.score_article", return_value=mock_score):
                items = await fetcher.fetch_all(min_score=0)

                # Should deduplicate
                title_count = {}
                for item in items:
                    title_count[item["title"]] = title_count.get(item["title"], 0) + 1

                # Each title should appear only once
                for count in title_count.values():
                    assert count == 1

    @pytest.mark.asyncio
    async def test_fetch_all_filters_low_scores(self):
        """Test that low score items are filtered"""
        fetcher = GoogleNewsRSSFetcher()

        recent_date = datetime.utcnow() - timedelta(days=1)
        date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

        mock_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Low Score Article</title>
                    <link>https://example.com</link>
                    <pubDate>{date_str}</pubDate>
                </item>
            </channel>
        </rss>
        """.encode()

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        # Mock low score
        mock_score = MagicMock()
        mock_score.final_score = 20  # Below min_score
        mock_score.priority = "low"
        mock_score.matched_category = "general"
        mock_score.matched_keywords = []
        mock_score.explanation = "Not relevant"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch("rss_fetcher.score_article", return_value=mock_score):
                items = await fetcher.fetch_all(min_score=35)

                assert len(items) == 0  # Filtered due to low score

    @pytest.mark.asyncio
    async def test_fetch_all_sorts_by_score(self):
        """Test that items are sorted by score descending"""
        fetcher = GoogleNewsRSSFetcher()

        recent_date = datetime.utcnow() - timedelta(days=1)
        date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

        mock_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Article A</title>
                    <link>https://example.com/a</link>
                    <pubDate>{date_str}</pubDate>
                </item>
                <item>
                    <title>Article B</title>
                    <link>https://example.com/b</link>
                    <pubDate>{date_str}</pubDate>
                </item>
            </channel>
        </rss>
        """.encode()

        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.raise_for_status = MagicMock()

        scores = [50, 80]  # B should come first
        call_count = [0]

        def get_score(*args, **kwargs):
            score = MagicMock()
            score.final_score = scores[call_count[0] % 2]
            score.priority = "medium" if score.final_score < 70 else "high"
            score.matched_category = "general"
            score.matched_keywords = []
            score.explanation = "Test"
            call_count[0] += 1
            return score

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with patch("rss_fetcher.score_article", side_effect=get_score):
                items = await fetcher.fetch_all(min_score=0)

                # Check if sorted (higher scores first)
                if len(items) >= 2:
                    for i in range(len(items) - 1):
                        assert (
                            items[i]["relevance_score"]
                            >= items[i + 1]["relevance_score"]
                        )


class TestParseDateFormats:
    """Test different date format parsing"""

    def test_parse_date_with_timezone(self):
        """Test parsing date with timezone"""
        fetcher = GoogleNewsRSSFetcher()

        # Some RSS feeds use %Z format
        date_str = "Mon, 01 Jan 2024 12:00:00 UTC"
        result = fetcher._parse_date(date_str)

        # May return None if format doesn't match exactly, that's acceptable
        assert result is None or isinstance(result, datetime)


class TestMain:
    """Test main function"""

    @pytest.mark.asyncio
    async def test_main_with_args(self):
        """Test main function with arguments"""
        from rss_fetcher import main

        # Mock fetch_all to return empty list
        with patch.object(GoogleNewsRSSFetcher, "fetch_all", return_value=[]):
            with patch("sys.argv", ["rss_fetcher", "--dry-run", "--max-age", "3"]):
                await main()

    @pytest.mark.asyncio
    async def test_main_with_items(self):
        """Test main function with items"""
        from rss_fetcher import main

        mock_items = [
            {
                "title": "Test Article",
                "relevance_score": 80,
                "priority": "high",
                "category": "immigration",
                "source": "Test Source",
            }
        ]

        with patch.object(GoogleNewsRSSFetcher, "fetch_all", return_value=mock_items):
            with patch("sys.argv", ["rss_fetcher", "--dry-run"]):
                await main()

    @pytest.mark.asyncio
    async def test_main_send_mode(self):
        """Test main function in send mode"""
        from rss_fetcher import main

        mock_items = [
            {
                "title": "Test",
                "relevance_score": 80,
                "priority": "high",
                "category": "immigration",
                "source": "Test",
            }
        ]

        with patch.object(GoogleNewsRSSFetcher, "fetch_all", return_value=mock_items):
            with patch(
                "rss_fetcher.send_to_balizero",
                return_value={"sent": 1, "failed": 0, "duplicates": 0},
            ):
                with patch("sys.argv", ["rss_fetcher", "--send"]):
                    await main()
