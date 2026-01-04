"""
News Router - API endpoints for Intel Feed news system
Handles CRUD operations, search, and subscriptions
"""

import logging
from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dependencies import get_database_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/news", tags=["News"])


# ============================================================================
# MODELS
# ============================================================================


class NewsItemCreate(BaseModel):
    """Model for creating a news item"""

    title: str = Field(..., min_length=10)
    summary: str | None = None
    content: str | None = None
    source: str
    source_url: str | None = None
    category: str = Field(default="business")
    priority: str = Field(default="medium")
    image_url: str | None = None
    published_at: datetime | None = None
    source_feed: str | None = None
    external_id: str | None = None


class NewsItemResponse(BaseModel):
    """Model for news item response"""

    id: str
    title: str
    slug: str
    summary: str | None
    content: str | None
    source: str
    source_url: str | None
    category: str
    priority: str
    status: str
    image_url: str | None
    view_count: int
    published_at: datetime | None
    created_at: datetime
    ai_summary: str | None
    ai_tags: list[str] | None


class NewsListResponse(BaseModel):
    """Model for paginated news list"""

    success: bool
    data: list[NewsItemResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class SubscriptionCreate(BaseModel):
    """Model for creating news subscription"""

    email: str
    categories: list[str] = Field(default_factory=list)
    frequency: str = Field(default="daily")


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("", response_model=NewsListResponse)
async def list_news(
    category: str | None = Query(None, description="Filter by category"),
    status: str = Query("approved", description="Filter by status"),
    search: str | None = Query(None, description="Search in title/content"),
    priority: str | None = Query(None, description="Filter by priority"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    List news items with filtering, search, and pagination.
    """

    try:
        # Build query
        conditions = ["status = $1"]
        params = [status]
        param_idx = 2

        if category:
            conditions.append(f"category = ${param_idx}")
            params.append(category)
            param_idx += 1

        if priority:
            conditions.append(f"priority = ${param_idx}")
            params.append(priority)
            param_idx += 1

        if search:
            conditions.append(
                f"to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, '')) @@ plainto_tsquery('english', ${param_idx})"
            )
            params.append(search)
            param_idx += 1

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * limit

        # Get total count
        count_query = f"SELECT COUNT(*) FROM news_items WHERE {where_clause}"
        async with pool.acquire() as conn:
            total = await conn.fetchval(count_query, *params)

            # Get items
            query = f"""
                SELECT id, title, slug, summary, content, source, source_url,
                       category, priority, status, image_url, view_count,
                       published_at, created_at, ai_summary, ai_tags
                FROM news_items
                WHERE {where_clause}
                ORDER BY
                    CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    published_at DESC NULLS LAST
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            params.extend([limit, offset])
            rows = await conn.fetch(query, *params)

        items = [
            NewsItemResponse(
                id=str(row["id"]),
                title=row["title"],
                slug=row["slug"],
                summary=row["summary"],
                content=row["content"],
                source=row["source"],
                source_url=row["source_url"],
                category=row["category"],
                priority=row["priority"],
                status=row["status"],
                image_url=row["image_url"],
                view_count=row["view_count"] or 0,
                published_at=row["published_at"],
                created_at=row["created_at"],
                ai_summary=row["ai_summary"],
                ai_tags=row["ai_tags"],
            )
            for row in rows
        ]

        return NewsListResponse(
            success=True,
            data=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )

    except Exception as e:
        logger.error(f"Error listing news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_categories(
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get available news categories with counts"""

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT category, COUNT(*) as count
                FROM news_items
                WHERE status = 'approved'
                GROUP BY category
                ORDER BY count DESC
            """)

        return {
            "success": True,
            "categories": [{"name": row["category"], "count": row["count"]} for row in rows],
        }
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{slug}")
async def get_news_by_slug(
    slug: str,
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get a single news item by slug and increment view count"""

    try:
        async with pool.acquire() as conn:
            # Increment view count and return item
            row = await conn.fetchrow(
                """
                UPDATE news_items
                SET view_count = view_count + 1
                WHERE slug = $1
                RETURNING id, title, slug, summary, content, source, source_url,
                          category, priority, status, image_url, view_count,
                          published_at, created_at, ai_summary, ai_tags
            """,
                slug,
            )

            if not row:
                raise HTTPException(status_code=404, detail="News item not found")

            return {
                "success": True,
                "data": NewsItemResponse(
                    id=str(row["id"]),
                    title=row["title"],
                    slug=row["slug"],
                    summary=row["summary"],
                    content=row["content"],
                    source=row["source"],
                    source_url=row["source_url"],
                    category=row["category"],
                    priority=row["priority"],
                    status=row["status"],
                    image_url=row["image_url"],
                    view_count=row["view_count"] or 0,
                    published_at=row["published_at"],
                    created_at=row["created_at"],
                    ai_summary=row["ai_summary"],
                    ai_tags=row["ai_tags"],
                ),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting news by slug: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_news(
    item: NewsItemCreate,
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Create a new news item (from scraper or manual)"""

    try:
        async with pool.acquire() as conn:
            # Check for duplicate by external_id
            if item.external_id:
                existing = await conn.fetchval(
                    "SELECT id FROM news_items WHERE external_id = $1", item.external_id
                )
                if existing:
                    return {"success": True, "data": {"id": str(existing)}, "duplicate": True}

            row = await conn.fetchrow(
                """
                INSERT INTO news_items (
                    title, summary, content, source, source_url,
                    category, priority, image_url, published_at,
                    source_feed, external_id, status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'approved')
                RETURNING id, slug
            """,
                item.title,
                item.summary,
                item.content,
                item.source,
                item.source_url,
                item.category,
                item.priority,
                item.image_url,
                item.published_at or datetime.utcnow(),
                item.source_feed,
                item.external_id,
            )

            return {"success": True, "data": {"id": str(row["id"]), "slug": row["slug"]}}

    except Exception as e:
        logger.error(f"Error creating news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk")
async def create_news_bulk(
    items: list[NewsItemCreate],
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Create multiple news items at once (for scraper batch uploads)"""
    created = 0
    duplicates = 0

    try:
        async with pool.acquire() as conn:
            for item in items:
                # Check duplicate
                if item.external_id:
                    existing = await conn.fetchval(
                        "SELECT id FROM news_items WHERE external_id = $1", item.external_id
                    )
                    if existing:
                        duplicates += 1
                        continue

                await conn.execute(
                    """
                    INSERT INTO news_items (
                        title, summary, content, source, source_url,
                        category, priority, image_url, published_at,
                        source_feed, external_id, status
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'approved')
                """,
                    item.title,
                    item.summary,
                    item.content,
                    item.source,
                    item.source_url,
                    item.category,
                    item.priority,
                    item.image_url,
                    item.published_at or datetime.utcnow(),
                    item.source_feed,
                    item.external_id,
                )
                created += 1

        return {"success": True, "created": created, "duplicates": duplicates, "total": len(items)}

    except Exception as e:
        logger.error(f"Error bulk creating news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{news_id}/status")
async def update_news_status(
    news_id: str,
    status: str,
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Update news item status (approve/reject)"""
    if status not in ("pending", "approved", "rejected", "archived"):
        raise HTTPException(status_code=400, detail="Invalid status")

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE news_items SET status = $1 WHERE id = $2
            """,
                status,
                news_id,
            )

            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="News item not found")

            return {"success": True, "status": status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating news status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SUBSCRIPTIONS
# ============================================================================


@router.post("/subscribe")
async def subscribe_to_news(
    subscription: SubscriptionCreate,
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Subscribe to news alerts"""

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO news_subscriptions (email, categories, frequency)
                VALUES ($1, $2, $3)
                ON CONFLICT (email) DO UPDATE SET
                    categories = $2,
                    frequency = $3,
                    is_active = true,
                    unsubscribed_at = NULL
            """,
                subscription.email,
                subscription.categories,
                subscription.frequency,
            )

        return {"success": True, "message": "Subscribed successfully"}

    except Exception as e:
        logger.error(f"Error subscribing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unsubscribe")
async def unsubscribe_from_news(
    email: str,
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Unsubscribe from news alerts"""

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE news_subscriptions
                SET is_active = false, unsubscribed_at = NOW()
                WHERE email = $1
            """,
                email,
            )

        return {"success": True, "message": "Unsubscribed successfully"}

    except Exception as e:
        logger.error(f"Error unsubscribing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RSS FEED
# ============================================================================


@router.get("/feed/rss")
async def get_rss_feed(
    category: str | None = None,
    limit: int = 20,
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Generate RSS feed for news items"""

    try:
        conditions = ["status = 'approved'"]
        params = []

        if category:
            conditions.append("category = $1")
            params.append(category)

        where_clause = " AND ".join(conditions)

        async with pool.acquire() as conn:
            query = f"""
                SELECT title, slug, summary, source, category, published_at
                FROM news_items
                WHERE {where_clause}
                ORDER BY published_at DESC
                LIMIT {limit}
            """
            rows = await conn.fetch(query, *params) if params else await conn.fetch(query)

        # Build RSS XML
        items_xml = ""
        for row in rows:
            pub_date = (
                row["published_at"].strftime("%a, %d %b %Y %H:%M:%S +0000")
                if row["published_at"]
                else ""
            )
            items_xml += f"""
        <item>
            <title><![CDATA[{row["title"]}]]></title>
            <link>https://balizero.com/news/{row["slug"]}</link>
            <description><![CDATA[{row["summary"] or ""}]]></description>
            <category>{row["category"]}</category>
            <pubDate>{pub_date}</pubDate>
            <guid>https://balizero.com/news/{row["slug"]}</guid>
        </item>"""

        rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
    <channel>
        <title>Bali Zero Intel Feed</title>
        <link>https://balizero.com/news</link>
        <description>Latest Indonesia news on immigration, business, tax, and property</description>
        <language>en</language>
        <lastBuildDate>{datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>
        <atom:link href="https://balizero.com/api/v2/news/feed/rss" rel="self" type="application/rss+xml"/>
        {items_xml}
    </channel>
</rss>"""

        from fastapi.responses import Response

        return Response(content=rss, media_type="application/rss+xml")

    except Exception as e:
        logger.error(f"Error generating RSS feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
