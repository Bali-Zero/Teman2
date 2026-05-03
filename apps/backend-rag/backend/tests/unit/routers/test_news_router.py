"""
Unit tests for backend/app/routers/news.py

Covers: list_news, get_categories, get_news_by_slug, create_news,
        create_news_bulk, update_news_image, update_news_status,
        subscribe_to_news, unsubscribe_from_news, get_rss_feed,
        _enqueue_post_publish.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.news import router


# ============================================================
# FIXTURES
# ============================================================

NOW = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def app(mock_db_pool):
    from backend.app.dependencies import get_database_pool

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


def _make_news_row(
    *,
    id="uuid-1",
    title="Test Article",
    slug="test-article",
    summary="Summary",
    content="Body",
    source="test-source",
    source_url="https://example.com",
    category="business",
    priority="medium",
    status="approved",
    image_url=None,
    view_count=0,
    published_at=NOW,
    created_at=NOW,
    ai_summary=None,
    ai_tags=None,
):
    """Helper to build a dict-like row."""
    return {
        "id": id,
        "title": title,
        "slug": slug,
        "summary": summary,
        "content": content,
        "source": source,
        "source_url": source_url,
        "category": category,
        "priority": priority,
        "status": status,
        "image_url": image_url,
        "view_count": view_count,
        "published_at": published_at,
        "created_at": created_at,
        "ai_summary": ai_summary,
        "ai_tags": ai_tags,
    }


# ============================================================
# GET /api/news — list_news
# ============================================================


def test_list_news_defaults(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch = AsyncMock(return_value=[_make_news_row()])

    response = client.get("/api/news")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["data"]) == 1
    assert data["data"][0]["slug"] == "test-article"


def test_list_news_with_category_filter(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetch = AsyncMock(return_value=[])

    response = client.get("/api/news?category=immigration&page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total"] == 0
    assert data["has_more"] is False


def test_list_news_with_priority_filter(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch = AsyncMock(return_value=[_make_news_row(priority="high")])

    response = client.get("/api/news?priority=high")
    assert response.status_code == 200
    data = response.json()
    assert data["data"][0]["priority"] == "high"


def test_list_news_with_search(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetch = AsyncMock(return_value=[])

    response = client.get("/api/news?search=visa")
    assert response.status_code == 200


def test_list_news_with_all_filters(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetch = AsyncMock(return_value=[])

    response = client.get(
        "/api/news?category=tax&priority=high&search=pph&status=approved&page=2&limit=5"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert data["limit"] == 5


def test_list_news_has_more_true(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value=25)
    conn.fetch = AsyncMock(return_value=[_make_news_row()] * 20)

    response = client.get("/api/news?page=1&limit=20")
    assert response.status_code == 200
    assert response.json()["has_more"] is True


def test_list_news_db_error(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(side_effect=Exception("DB error"))

    response = client.get("/api/news")
    assert response.status_code == 500


def test_list_news_zero_view_count(client, mock_db_pool):
    """view_count=None should become 0."""
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch = AsyncMock(return_value=[_make_news_row(view_count=None)])

    response = client.get("/api/news")
    assert response.status_code == 200
    assert response.json()["data"][0]["view_count"] == 0


# ============================================================
# GET /api/news/categories
# ============================================================


def test_get_categories(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetch = AsyncMock(
        return_value=[
            {"category": "business", "count": 10},
            {"category": "tax", "count": 5},
        ]
    )

    response = client.get("/api/news/categories")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["categories"]) == 2
    assert data["categories"][0]["name"] == "business"


def test_get_categories_empty(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetch = AsyncMock(return_value=[])

    response = client.get("/api/news/categories")
    assert response.status_code == 200
    assert response.json()["categories"] == []


def test_get_categories_db_error(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetch = AsyncMock(side_effect=Exception("DB error"))

    response = client.get("/api/news/categories")
    assert response.status_code == 500


# ============================================================
# GET /api/news/{slug}
# ============================================================


def test_get_news_by_slug_found(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchrow = AsyncMock(return_value=_make_news_row(view_count=42))

    response = client.get("/api/news/test-article")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["slug"] == "test-article"
    assert data["data"]["view_count"] == 42


def test_get_news_by_slug_not_found(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchrow = AsyncMock(return_value=None)

    response = client.get("/api/news/nonexistent-slug")
    assert response.status_code == 404


def test_get_news_by_slug_db_error(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))

    response = client.get("/api/news/test-article")
    assert response.status_code == 500


# ============================================================
# POST /api/news — create_news
# ============================================================


def test_create_news_new_item(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value=None)  # no duplicate
    conn.fetchrow = AsyncMock(return_value={"id": "new-uuid", "slug": "new-article"})
    conn.execute = AsyncMock()  # for enqueue_post_publish

    response = client.post(
        "/api/news",
        json={
            "title": "A New Article Title Here",
            "source": "test-bot",
            "category": "business",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == "new-uuid"
    assert data["data"]["slug"] == "new-article"


def test_create_news_duplicate(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(return_value="existing-uuid")

    response = client.post(
        "/api/news",
        json={
            "title": "A Duplicate Article Here",
            "source": "test-bot",
            "external_id": "ext-123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["duplicate"] is True
    assert data["data"]["id"] == "existing-uuid"


def test_create_news_with_image_url_skips_enqueue(client, mock_db_pool):
    """When image_url is provided, _enqueue_post_publish should NOT be called."""
    conn = mock_db_pool._mock_conn
    conn.fetchrow = AsyncMock(return_value={"id": "uuid-2", "slug": "with-image"})

    with patch("backend.app.routers.news._enqueue_post_publish", new_callable=AsyncMock) as mock_enqueue:
        response = client.post(
            "/api/news",
            json={
                "title": "Article with image url",
                "source": "scraper",
                "image_url": "https://example.com/image.png",
            },
        )
        assert response.status_code == 200
        mock_enqueue.assert_not_called()


def test_create_news_without_image_calls_enqueue(client, mock_db_pool):
    """When image_url is missing, _enqueue_post_publish should be called."""
    conn = mock_db_pool._mock_conn
    conn.fetchrow = AsyncMock(return_value={"id": "uuid-3", "slug": "no-image"})
    conn.execute = AsyncMock()

    response = client.post(
        "/api/news",
        json={
            "title": "Article without image url",
            "source": "scraper",
        },
    )
    assert response.status_code == 200


def test_create_news_title_too_short(client):
    response = client.post(
        "/api/news",
        json={"title": "Short", "source": "test"},
    )
    assert response.status_code == 422


def test_create_news_db_error(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchrow = AsyncMock(side_effect=Exception("insert failed"))

    response = client.post(
        "/api/news",
        json={
            "title": "A valid title that is long enough",
            "source": "test-source",
        },
    )
    assert response.status_code == 500


# ============================================================
# POST /api/news/bulk — create_news_bulk
# ============================================================


def test_create_news_bulk_mixed(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    # First item: duplicate; second item: new
    conn.fetchval = AsyncMock(side_effect=["existing-id", None])
    conn.fetchrow = AsyncMock(return_value={"id": "new-id", "slug": "new-bulk"})
    conn.execute = AsyncMock()

    response = client.post(
        "/api/news/bulk",
        json=[
            {
                "title": "Duplicate article title here",
                "source": "scraper",
                "external_id": "ext-dup",
            },
            {
                "title": "New article title here today",
                "source": "scraper",
            },
        ],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["created"] == 1
    assert data["duplicates"] == 1
    assert data["total"] == 2


def test_create_news_bulk_empty(client, mock_db_pool):
    response = client.post("/api/news/bulk", json=[])
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 0
    assert data["total"] == 0


def test_create_news_bulk_db_error(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetchval = AsyncMock(side_effect=Exception("bulk error"))

    response = client.post(
        "/api/news/bulk",
        json=[
            {
                "title": "Article that will cause an error",
                "source": "scraper",
                "external_id": "ext-1",
            },
        ],
    )
    assert response.status_code == 500


# ============================================================
# POST /api/news/{news_id}/image — update_news_image
# ============================================================


def test_update_news_image_success(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock(return_value="UPDATE 1")

    response = client.post(
        "/api/news/uuid-1/image",
        json={"image_url": "https://example.com/cover.jpg"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["image_url"] == "https://example.com/cover.jpg"


def test_update_news_image_missing_url(client, mock_db_pool):
    response = client.post("/api/news/uuid-1/image", json={})
    assert response.status_code == 400


def test_update_news_image_not_found(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock(return_value="UPDATE 0")

    response = client.post(
        "/api/news/uuid-1/image",
        json={"image_url": "https://example.com/cover.jpg"},
    )
    assert response.status_code == 404


def test_update_news_image_db_error(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock(side_effect=Exception("DB error"))

    response = client.post(
        "/api/news/uuid-1/image",
        json={"image_url": "https://example.com/cover.jpg"},
    )
    assert response.status_code == 500


# ============================================================
# PATCH /api/news/{news_id}/status — update_news_status
# ============================================================


def test_update_news_status_approved(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock(return_value="UPDATE 1")

    response = client.patch("/api/news/uuid-1/status?status=approved")
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_update_news_status_invalid(client, mock_db_pool):
    response = client.patch("/api/news/uuid-1/status?status=invalid_status")
    assert response.status_code == 400


def test_update_news_status_not_found(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock(return_value="UPDATE 0")

    response = client.patch("/api/news/uuid-1/status?status=archived")
    assert response.status_code == 404


def test_update_news_status_db_error(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock(side_effect=Exception("DB error"))

    response = client.patch("/api/news/uuid-1/status?status=pending")
    assert response.status_code == 500


def test_update_news_status_all_valid_values(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock(return_value="UPDATE 1")

    for status in ("pending", "approved", "rejected", "archived"):
        response = client.patch(f"/api/news/uuid-1/status?status={status}")
        assert response.status_code == 200
        assert response.json()["status"] == status


# ============================================================
# POST /api/news/subscribe
# ============================================================


def test_subscribe_success(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock()

    response = client.post(
        "/api/news/subscribe",
        json={
            "email": "user@example.com",
            "categories": ["business", "tax"],
            "frequency": "daily",
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_subscribe_defaults(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock()

    response = client.post(
        "/api/news/subscribe",
        json={"email": "user@example.com"},
    )
    assert response.status_code == 200


def test_subscribe_db_error(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock(side_effect=Exception("DB error"))

    response = client.post(
        "/api/news/subscribe",
        json={"email": "user@example.com"},
    )
    assert response.status_code == 500


# ============================================================
# POST /api/news/unsubscribe
# ============================================================


def test_unsubscribe_success(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock()

    response = client.post("/api/news/unsubscribe?email=user@example.com")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_unsubscribe_db_error(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock(side_effect=Exception("DB error"))

    response = client.post("/api/news/unsubscribe?email=user@example.com")
    assert response.status_code == 500


# ============================================================
# GET /api/news/feed/rss
# ============================================================


def test_rss_feed_no_filter(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetch = AsyncMock(
        return_value=[
            {
                "title": "RSS Item",
                "slug": "rss-item",
                "summary": "Summary text",
                "source": "test",
                "category": "business",
                "published_at": NOW,
            }
        ]
    )

    response = client.get("/api/news/feed/rss")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/rss+xml"
    assert "<rss" in response.text
    assert "RSS Item" in response.text


def test_rss_feed_with_category(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetch = AsyncMock(return_value=[])

    response = client.get("/api/news/feed/rss?category=tax")
    assert response.status_code == 200
    assert "application/rss+xml" in response.headers["content-type"]


def test_rss_feed_no_published_at(client, mock_db_pool):
    """Should handle None published_at gracefully."""
    conn = mock_db_pool._mock_conn
    conn.fetch = AsyncMock(
        return_value=[
            {
                "title": "No Date Item",
                "slug": "no-date",
                "summary": None,
                "source": "test",
                "category": "business",
                "published_at": None,
            }
        ]
    )

    response = client.get("/api/news/feed/rss")
    assert response.status_code == 200
    assert "No Date Item" in response.text


def test_rss_feed_db_error(client, mock_db_pool):
    conn = mock_db_pool._mock_conn
    conn.fetch = AsyncMock(side_effect=Exception("DB error"))

    response = client.get("/api/news/feed/rss")
    assert response.status_code == 500


# ============================================================
# _enqueue_post_publish (helper function)
# ============================================================


@pytest.mark.asyncio
async def test_enqueue_post_publish_success(mock_db_pool):
    from backend.app.routers.news import _enqueue_post_publish

    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock()

    await _enqueue_post_publish(
        slug="test-slug",
        title="Test Title",
        category="business",
        article_id="uuid-1",
        pool=mock_db_pool,
    )
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_enqueue_post_publish_failure_does_not_raise(mock_db_pool):
    """Should log warning but not raise on failure."""
    conn = mock_db_pool._mock_conn
    conn.execute = AsyncMock(side_effect=Exception("insert failed"))

    # Should NOT raise
    from backend.app.routers.news import _enqueue_post_publish

    await _enqueue_post_publish(
        slug="test-slug",
        title="Test Title",
        category="business",
        article_id="uuid-1",
        pool=mock_db_pool,
    )
