"""
Unit tests for Intelligence Center scraper submission endpoint.

Tests the /api/intel/scraper/submit endpoint that receives articles from:
- unified_scraper.py (general news scraper)
- intelligent_visa_agent.py (official immigration scraper)

Coverage:
- Successful submission (visa/news)
- Duplicate detection
- Classification algorithm
- Payload validation
"""

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_staging_dir(tmp_path):
    """Create temporary staging directories"""
    visa_dir = tmp_path / "staging" / "visa"
    news_dir = tmp_path / "staging" / "news"
    visa_dir.mkdir(parents=True)
    news_dir.mkdir(parents=True)
    return tmp_path / "staging"


@pytest.fixture
def client(mock_staging_dir):
    """Create FastAPI test client with mocked staging directories"""
    import sys

    # Remove cached module if it exists
    if "app.routers.intel" in sys.modules:
        del sys.modules["app.routers.intel"]

    with (
        patch("app.routers.intel.VISA_STAGING_DIR", mock_staging_dir / "visa"),
        patch("app.routers.intel.NEWS_STAGING_DIR", mock_staging_dir / "news"),
        patch("app.routers.intel.BASE_STAGING_DIR", mock_staging_dir),
    ):
        # Import router after patches are applied
        # Manually update the module's global variables
        import app.routers.intel as intel_module
        from app.routers.intel import router

        intel_module.VISA_STAGING_DIR = mock_staging_dir / "visa"
        intel_module.NEWS_STAGING_DIR = mock_staging_dir / "news"

        app = FastAPI()
        app.include_router(router)
        yield TestClient(app)

        # Cleanup: remove module again so next test gets fresh import
        if "app.routers.intel" in sys.modules:
            del sys.modules["app.routers.intel"]


# --- SUCCESSFUL SUBMISSION TESTS ---


def test_submit_visa_article_success(client, mock_staging_dir):
    """Test successful submission of visa article from intelligent_visa_agent"""
    payload = {
        "title": "🆕 NEW: E33E Retirement Visa Requirements Updated",
        "content": "The immigration office has updated E33E visa requirements...",
        "source_url": "https://www.imigrasi.go.id/wna/e33e-visa-pensiun",
        "source_name": "intelligent_visa_agent",
        "category": "visa",
        "relevance_score": 100,
        "published_at": "2026-01-05T10:00:00Z",
        "extraction_method": "playwright+gemini",
        "tier": "T1",
    }

    response = client.post("/api/intel/scraper/submit", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["intel_type"] == "visa"
    assert data["duplicate"] is False
    assert "item_id" in data
    assert data["item_id"].startswith("visa_")

    # Verify file created
    visa_dir = mock_staging_dir / "visa"
    files = list(visa_dir.glob("*.json"))
    assert len(files) == 1

    # Verify file content
    saved_data = json.loads(files[0].read_text())
    assert saved_data["title"] == payload["title"]
    assert saved_data["intel_type"] == "visa"
    assert saved_data["tier"] == "T1"
    assert saved_data["status"] == "pending"


def test_submit_news_article_success(client, mock_staging_dir):
    """Test successful submission of news article from unified_scraper"""
    payload = {
        "title": "Jakarta Post: New KITAS Rules Announced",
        "content": "The Indonesian government announced new digital nomad visa rules...",
        "source_url": "https://jakartaglobe.id/news/kitas-digital-nomad",
        "source_name": "unified_scraper",
        "category": "news",
        "relevance_score": 85,
        "published_at": "2026-01-05T09:30:00Z",
        "extraction_method": "css",
        "tier": "T2",
    }

    response = client.post("/api/intel/scraper/submit", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["intel_type"] == "news"
    assert data["duplicate"] is False
    assert "item_id" in data
    assert data["item_id"].startswith("news_")

    # Verify file created in news directory
    news_dir = mock_staging_dir / "news"
    files = list(news_dir.glob("*.json"))
    assert len(files) == 1


# --- DUPLICATE DETECTION TESTS ---


def test_submit_duplicate_article(client, mock_staging_dir):
    """Test duplicate detection by source_url"""
    payload = {
        "title": "Original Article",
        "content": "Original content",
        "source_url": "https://example.com/article-123",
        "source_name": "test_scraper",
        "category": "news",
        "relevance_score": 80,
        "tier": "T2",
    }

    # First submission - should succeed
    response1 = client.post("/api/intel/scraper/submit", json=payload)
    assert response1.status_code == 200
    assert response1.json()["duplicate"] is False

    # Second submission - should detect duplicate
    response2 = client.post("/api/intel/scraper/submit", json=payload)
    assert response2.status_code == 200
    data = response2.json()

    assert data["success"] is True
    assert data["duplicate"] is True
    assert data["message"] == "Article already exists in staging"

    # Verify only one file exists
    news_dir = mock_staging_dir / "news"
    files = list(news_dir.glob("*.json"))
    assert len(files) == 1


# --- CLASSIFICATION TESTS ---


def test_classification_visa_by_category(client):
    """Test classification: category='visa' → intel_type='visa'"""
    payload = {
        "title": "Test Article",
        "content": "Some content",
        "source_url": "https://example.com/1",
        "source_name": "test",
        "category": "visa",  # Direct category match
        "relevance_score": 90,
        "tier": "T2",
    }

    response = client.post("/api/intel/scraper/submit", json=payload)
    assert response.json()["intel_type"] == "visa"


def test_classification_visa_by_immigration_category(client):
    """Test classification: category='immigration' → intel_type='visa'"""
    payload = {
        "title": "Immigration Update",
        "content": "Content about immigration",
        "source_url": "https://example.com/2",
        "source_name": "test",
        "category": "immigration",  # Should map to visa
        "relevance_score": 90,
        "tier": "T1",
    }

    response = client.post("/api/intel/scraper/submit", json=payload)
    assert response.json()["intel_type"] == "visa"


def test_classification_visa_by_keywords(client):
    """Test classification: ≥3 visa keywords → intel_type='visa'"""
    payload = {
        "title": "KITAS B211 Visa Requirements for Investors",
        "content": "New permit regulations for residence in Indonesia...",
        "source_url": "https://example.com/3",
        "source_name": "test",
        "category": "business",  # Not visa category
        "relevance_score": 85,
        "tier": "T2",
    }

    # Title contains: KITAS, B211, visa, permit, residence = 5 keywords
    response = client.post("/api/intel/scraper/submit", json=payload)
    assert response.json()["intel_type"] == "visa"


def test_classification_news_default(client):
    """Test classification: no visa indicators → intel_type='news'"""
    payload = {
        "title": "Bali Tourism Numbers Rise in 2026",
        "content": "Tourist arrivals increased by 15% this quarter...",
        "source_url": "https://example.com/4",
        "source_name": "test",
        "category": "tourism",
        "relevance_score": 70,
        "tier": "T3",
    }

    # No visa keywords, generic category → should classify as news
    response = client.post("/api/intel/scraper/submit", json=payload)
    assert response.json()["intel_type"] == "news"


def test_classification_visa_by_content_keywords(client):
    """Test classification: visa keywords in content → intel_type='visa'"""
    payload = {
        "title": "Policy Update",
        "content": "The new KITAS regulations require KITAP holders to renew their stay permit before the VOA expires.",
        "source_url": "https://example.com/5",
        "source_name": "test",
        "category": "policy",
        "relevance_score": 90,
        "tier": "T2",
    }

    # Content contains: KITAS, KITAP, stay permit, VOA = 4 keywords
    response = client.post("/api/intel/scraper/submit", json=payload)
    assert response.json()["intel_type"] == "visa"


# --- PAYLOAD VALIDATION TESTS ---


def test_invalid_payload_missing_required_field(client):
    """Test validation: missing required field"""
    payload = {
        "title": "Test",
        # Missing 'content' field
        "source_url": "https://example.com/6",
        "source_name": "test",
        "category": "news",
        "relevance_score": 80,
        "tier": "T2",
    }

    response = client.post("/api/intel/scraper/submit", json=payload)
    assert response.status_code == 422  # Validation error


def test_invalid_payload_empty_title(client):
    """Test validation: empty title"""
    payload = {
        "title": "",  # Empty title
        "content": "Some content",
        "source_url": "https://example.com/7",
        "source_name": "test",
        "category": "news",
        "relevance_score": 80,
        "tier": "T2",
    }

    response = client.post("/api/intel/scraper/submit", json=payload)
    assert response.status_code == 422


def test_payload_with_optional_fields(client, mock_staging_dir):
    """Test submission with all optional fields"""
    payload = {
        "title": "Complete Article",
        "content": "Full content",
        "source_url": "https://example.com/8",
        "source_name": "test_scraper",
        "category": "visa",
        "relevance_score": 95,
        "published_at": "2026-01-05T12:00:00Z",
        "extraction_method": "playwright+gemini",
        "tier": "T1",
    }

    response = client.post("/api/intel/scraper/submit", json=payload)
    assert response.status_code == 200

    # Verify all fields saved
    visa_dir = mock_staging_dir / "visa"
    saved_file = list(visa_dir.glob("*.json"))[0]
    saved_data = json.loads(saved_file.read_text())

    assert saved_data["published_at"] == "2026-01-05T12:00:00Z"
    assert saved_data["extraction_method"] == "playwright+gemini"
    assert saved_data["tier"] == "T1"


# --- EDGE CASES ---


def test_classification_boundary_2_keywords(client):
    """Test classification: 2 visa keywords (below threshold) → news"""
    payload = {
        "title": "Visa Requirements",  # 2 keywords: visa, requirements
        "content": "General article about travel",
        "source_url": "https://example.com/9",
        "source_name": "test",
        "category": "travel",
        "relevance_score": 70,
        "tier": "T2",
    }

    # Only 2 keywords (threshold is 3) → should be news
    response = client.post("/api/intel/scraper/submit", json=payload)
    assert response.json()["intel_type"] == "news"


def test_classification_boundary_3_keywords_exact(client):
    """Test classification: exactly 3 visa keywords → visa"""
    payload = {
        "title": "KITAS and KITAP Updates",  # 3 keywords: KITAS, KITAP, visa
        "content": "No additional visa keywords here",
        "source_url": "https://example.com/10",
        "source_name": "test",
        "category": "policy",
        "relevance_score": 85,
        "tier": "T2",
    }

    # Exactly 3 keywords (threshold met) → should be visa
    response = client.post("/api/intel/scraper/submit", json=payload)
    assert response.json()["intel_type"] == "visa"


def test_item_id_uniqueness(client, mock_staging_dir):
    """Test that different articles get unique item_ids"""
    payload1 = {
        "title": "Article 1",
        "content": "Content 1",
        "source_url": "https://example.com/a1",
        "source_name": "test",
        "category": "news",
        "relevance_score": 80,
        "tier": "T2",
    }

    payload2 = {
        "title": "Article 2",
        "content": "Content 2",
        "source_url": "https://example.com/a2",
        "source_name": "test",
        "category": "news",
        "relevance_score": 80,
        "tier": "T2",
    }

    response1 = client.post("/api/intel/scraper/submit", json=payload1)
    response2 = client.post("/api/intel/scraper/submit", json=payload2)

    item_id1 = response1.json()["item_id"]
    item_id2 = response2.json()["item_id"]

    assert item_id1 != item_id2  # Must be unique

    # Verify both files exist
    news_dir = mock_staging_dir / "news"
    files = list(news_dir.glob("*.json"))
    assert len(files) == 2
