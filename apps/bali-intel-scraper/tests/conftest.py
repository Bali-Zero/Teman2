"""
BALI INTEL SCRAPER - Test Configuration
Shared fixtures and configuration for all tests
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================


@pytest.fixture
def sample_articles():
    """Sample articles for testing"""
    return [
        {
            "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
            "summary": "The Indonesian government announced a new policy extending the digital nomad visa.",
            "content": "The Indonesian government through BKPM announced new golden visa regulations for foreign investors.",
            "url": "https://jakartapost.com/article/visa",
            "source": "Jakarta Post",
            "source_url": "https://jakartapost.com/article/visa",
            "published_at": datetime.utcnow() - timedelta(days=1),
            "category": "immigration",
        },
        {
            "title": "New Tax Rules for Foreign Workers PPh 21",
            "summary": "Tax authority issues new NPWP guidelines for expats",
            "content": "The DJP has issued new regulations regarding PPh 21 withholding for foreign workers.",
            "url": "https://pajak.go.id/news/tax",
            "source": "DJP",
            "source_url": "https://pajak.go.id/news/tax",
            "published_at": datetime.utcnow() - timedelta(hours=6),
            "category": "tax",
        },
        {
            "title": "Taylor Swift Announces World Tour",
            "summary": "Pop star announces concert dates",
            "content": "Famous singer announces tour dates for 2026.",
            "url": "https://entertainment.com/taylor",
            "source": "Entertainment Weekly",
            "source_url": "https://entertainment.com/taylor",
            "published_at": datetime.utcnow() - timedelta(days=5),
            "category": "general",
        },
        {
            "title": "Bali Governor Announces New KITAS Requirements",
            "summary": "New izin tinggal terbatas requirements for digital nomads in Bali",
            "content": "Gubernur Bali menyatakan peraturan baru untuk KITAS.",
            "url": "https://bali.tribunnews.com/kitas",
            "source": "Tribun Bali",
            "source_url": "https://bali.tribunnews.com/kitas",
            "published_at": datetime.utcnow() - timedelta(hours=2),
            "category": "immigration",
        },
    ]


@pytest.fixture
def high_relevance_article():
    """Article with high relevance score"""
    return {
        "title": "Indonesia Launches New Golden Visa Program for Foreign Investors",
        "summary": "BKPM announces golden visa for investors",
        "content": "The Indonesian government through BKPM announced new golden visa regulations.",
        "url": "https://bkpm.go.id/golden-visa",
        "source": "BKPM",
        "source_url": "https://bkpm.go.id/golden-visa",
        "published_at": datetime.utcnow(),
    }


@pytest.fixture
def low_relevance_article():
    """Article with low relevance score"""
    return {
        "title": "Celebrity Wedding Goes Viral",
        "summary": "Famous actor gets married",
        "content": "A celebrity wedding happened somewhere.",
        "url": "https://gossip.com/wedding",
        "source": "Gossip Blog",
        "source_url": "https://gossip.com/wedding",
        "published_at": datetime.utcnow() - timedelta(days=30),
    }


@pytest.fixture
def medium_relevance_article():
    """Article with medium relevance score (40-75) - needs validation"""
    return {
        "title": "Indonesia Tourism Numbers Increase",
        "summary": "Tourist arrivals up 20%",
        "content": "Tourism in Indonesia has seen growth this year.",
        "url": "https://news.com/tourism",
        "source": "Local News",
        "source_url": "https://news.com/tourism",
        "published_at": datetime.utcnow() - timedelta(days=3),
    }


# =============================================================================
# MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_httpx_client():
    """Mock httpx async client"""
    with patch("httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = client_instance
        yield client_instance


@pytest.fixture
def mock_ollama_response():
    """Mock Ollama API response"""
    return {
        "response": '{"score": 75, "reason": "visa policy relevant"}',
        "done": True,
    }


@pytest.fixture
def mock_claude_cli():
    """Mock Claude CLI subprocess"""
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(
            returncode=0,
            stdout='{"approved": true, "confidence": 85, "reason": "Relevant for expats"}',
            stderr="",
        )
        yield mock


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client"""
    with patch("qdrant_client.QdrantClient") as mock:
        client = MagicMock()
        client.get_collections.return_value = MagicMock(collections=[])
        client.search.return_value = []
        mock.return_value = client
        yield client


# =============================================================================
# RSS/SCRAPER FIXTURES
# =============================================================================


@pytest.fixture
def sample_rss_feed():
    """Sample RSS feed XML"""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Google News - Bali Visa</title>
            <item>
                <title>New Visa Rules for Bali</title>
                <link>https://example.com/visa-news</link>
                <description>Indonesia announces new visa policies.</description>
                <pubDate>Sat, 04 Jan 2026 10:00:00 GMT</pubDate>
                <source url="https://jakartapost.com">Jakarta Post</source>
            </item>
            <item>
                <title>Tax Changes for Expats</title>
                <link>https://example.com/tax-news</link>
                <description>New tax regulations for foreign workers.</description>
                <pubDate>Fri, 03 Jan 2026 15:00:00 GMT</pubDate>
                <source url="https://bisnis.com">Bisnis</source>
            </item>
        </channel>
    </rss>"""


@pytest.fixture
def sample_html_article():
    """Sample HTML article content"""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>New Visa Rules</title></head>
    <body>
        <article>
            <h1>Indonesia Announces New Digital Nomad Visa</h1>
            <p class="author">By John Doe</p>
            <div class="content">
                <p>The Indonesian government has announced new visa regulations
                for digital nomads. The new KITAS will be valid for 5 years.</p>
                <p>According to the Ministry of Immigration, applications will
                open next month. The visa costs $500 and allows remote work.</p>
            </div>
        </article>
    </body>
    </html>
    """


# =============================================================================
# ENRICHED ARTICLE FIXTURES
# =============================================================================


@pytest.fixture
def enriched_article_response():
    """Sample enriched article from Claude Max"""
    return {
        "headline": "Indonesia Extends Digital Nomad Visa: 5-Year Stay Now Possible",
        "category": "immigration",
        "priority": "high",
        "relevance_score": 92,
        "ai_summary": "Indonesia has extended digital nomad visa validity to 5 years.",
        "ai_tags": ["visa", "digital nomad", "immigration", "policy"],
        "full_article": "# Indonesia Extends Digital Nomad Visa\n\nThe Indonesian government...",
        "key_points": [
            "Visa validity extended to 5 years",
            "Cost: $500",
            "Applications open next month",
        ],
        "action_required": False,
        "affected_groups": ["digital nomads", "remote workers", "expats"],
    }


# =============================================================================
# CONFIGURATION FIXTURES
# =============================================================================


@pytest.fixture
def sample_config():
    """Sample categories.json config"""
    return {
        "total_categories": 2,
        "categories": {
            "immigration": {
                "id": 1,
                "key": "immigration",
                "name": "Immigration & Visa",
                "priority": "high",
                "sources": [
                    {
                        "name": "Imigrasi Indonesia",
                        "url": "https://www.imigrasi.go.id/",
                        "tier": "T1",
                        "selectors": ["div.content", "article"],
                    }
                ],
            },
            "tax": {
                "id": 2,
                "key": "tax",
                "name": "Tax & BKPM",
                "priority": "high",
                "sources": [
                    {
                        "name": "DJP",
                        "url": "https://www.pajak.go.id/",
                        "tier": "T1",
                        "selectors": ["article"],
                    }
                ],
            },
        },
    }


# =============================================================================
# VALIDATION FIXTURES
# =============================================================================


@pytest.fixture
def validation_approved():
    """Approved validation result"""
    return {
        "approved": True,
        "confidence": 85,
        "reason": "Directly affects expat visa requirements",
        "category_override": None,
        "priority_override": "high",
        "enrichment_hints": ["Focus on timeline", "Include application process"],
    }


@pytest.fixture
def validation_rejected():
    """Rejected validation result"""
    return {
        "approved": False,
        "confidence": 90,
        "reason": "General entertainment news, no expat relevance",
        "category_override": None,
        "priority_override": None,
        "enrichment_hints": None,
    }


# =============================================================================
# IMAGE GENERATION FIXTURES
# =============================================================================


@pytest.fixture
def image_context():
    """Sample article context for image generation"""
    return {
        "title": "Coretax System Causing NPWP Registration Issues",
        "summary": "New tax system experiencing errors",
        "full_content": "The new Coretax system launched by DJP is causing delays...",
        "category": "tax",
        "tone": "problem",
    }


@pytest.fixture
def expected_image_prompt():
    """Expected structure for image prompts"""
    return {
        "must_contain": ["ultra-realistic", "8K", "Bali", "16:9"],
        "must_not_contain": ["cartoon", "illustration", "stock photo"],
    }
