"""
ZANTARA MEDIA - Content Repository
Database operations for content management
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
import asyncpg

from app.models import ContentStatus, ContentType, ContentCategory
from app.db.connection import get_db_pool

logger = logging.getLogger(__name__)


class ContentRepository:
    """Repository for content database operations."""

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        """Get database pool."""
        if self._pool is None:
            self._pool = await get_db_pool()
        return self._pool

    # ============================================================================
    # CREATE OPERATIONS
    # ============================================================================

    async def create_content(
        self,
        title: str,
        slug: str,
        body: Optional[str],
        summary: Optional[str],
        content_type: ContentType,
        category: ContentCategory,
        tags: List[str],
        author_id: Optional[str] = None,
        author_name: Optional[str] = None,
        word_count: int = 0,
        reading_time_minutes: int = 0,
        ai_generated: bool = False,
        ai_model: Optional[str] = None,
        source_signal_id: Optional[str] = None,
        seo_title: Optional[str] = None,
        seo_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new content record."""
        pool = await self._get_pool()

        query = """
            INSERT INTO zantara_content (
                title, slug, body, summary, type, category, tags,
                author_id, author_name, word_count, reading_time_minutes,
                ai_generated, ai_model, source_signal_id,
                seo_title, seo_description, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            RETURNING *
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                title,
                slug,
                body,
                summary,
                content_type.value,
                category.value,
                tags,
                author_id,
                author_name,
                word_count,
                reading_time_minutes,
                ai_generated,
                ai_model,
                source_signal_id,
                seo_title,
                seo_description,
                ContentStatus.DRAFT.value,
            )

            return dict(row)

    async def create_intel_signal(
        self,
        title: str,
        summary: str,
        category: ContentCategory,
        source_name: str,
        source_url: Optional[str] = None,
        source_tier: Optional[int] = None,
        confidence_score: Optional[float] = None,
        priority: int = 5,
        tags: Optional[List[str]] = None,
        raw_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a new intel signal."""
        pool = await self._get_pool()

        query = """
            INSERT INTO intel_signals (
                title, summary, category, source_name, source_url,
                source_tier, confidence_score, priority, tags, raw_data
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                title,
                summary,
                category.value,
                source_name,
                source_url,
                source_tier,
                confidence_score,
                priority,
                tags or [],
                raw_data,
            )

            return dict(row)

    async def create_media_asset(
        self,
        content_id: Optional[UUID],
        asset_type: str,
        storage_url: str,
        file_name: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        mime_type: Optional[str] = None,
        generated_by: Optional[str] = None,
        generation_prompt: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a media asset record."""
        pool = await self._get_pool()

        query = """
            INSERT INTO media_assets (
                content_id, asset_type, storage_url, file_name,
                file_size_bytes, mime_type, generated_by,
                generation_prompt, width, height
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                content_id,
                asset_type,
                storage_url,
                file_name,
                file_size_bytes,
                mime_type,
                generated_by,
                generation_prompt,
                width,
                height,
            )

            return dict(row)

    # ============================================================================
    # READ OPERATIONS
    # ============================================================================

    async def get_content_by_id(self, content_id: UUID) -> Optional[Dict[str, Any]]:
        """Get content by ID."""
        pool = await self._get_pool()

        query = "SELECT * FROM zantara_content WHERE id = $1"

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, content_id)
            return dict(row) if row else None

    async def get_content_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get content by slug."""
        pool = await self._get_pool()

        query = "SELECT * FROM zantara_content WHERE slug = $1"

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, slug)
            return dict(row) if row else None

    async def list_content(
        self,
        status: Optional[ContentStatus] = None,
        category: Optional[ContentCategory] = None,
        content_type: Optional[ContentType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List content with optional filters."""
        pool = await self._get_pool()

        conditions = []
        params = []
        param_count = 0

        if status:
            param_count += 1
            conditions.append(f"status = ${param_count}")
            params.append(status.value)

        if category:
            param_count += 1
            conditions.append(f"category = ${param_count}")
            params.append(category.value)

        if content_type:
            param_count += 1
            conditions.append(f"type = ${param_count}")
            params.append(content_type.value)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        param_count += 1
        limit_param = f"${param_count}"
        params.append(limit)

        param_count += 1
        offset_param = f"${param_count}"
        params.append(offset)

        query = f"""
            SELECT * FROM zantara_content
            {where_clause}
            ORDER BY created_at DESC
            LIMIT {limit_param} OFFSET {offset_param}
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_scheduled_content(self) -> List[Dict[str, Any]]:
        """Get content scheduled for publication."""
        pool = await self._get_pool()

        query = """
            SELECT * FROM zantara_content
            WHERE status = 'SCHEDULED'
                AND scheduled_at <= NOW()
            ORDER BY scheduled_at ASC
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]

    async def get_pending_intel_signals(
        self, limit: int = 20, min_priority: int = 5
    ) -> List[Dict[str, Any]]:
        """Get unprocessed intel signals."""
        pool = await self._get_pool()

        query = """
            SELECT * FROM intel_signals
            WHERE processed = FALSE
                AND priority >= $1
            ORDER BY priority DESC, signal_date DESC
            LIMIT $2
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, min_priority, limit)
            return [dict(row) for row in rows]

    # ============================================================================
    # UPDATE OPERATIONS
    # ============================================================================

    async def update_content_status(
        self,
        content_id: UUID,
        status: ContentStatus,
        approved_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update content status."""
        pool = await self._get_pool()

        if status == ContentStatus.APPROVED and approved_by:
            query = """
                UPDATE zantara_content
                SET status = $1, approved_by = $2, approved_at = NOW()
                WHERE id = $3
                RETURNING *
            """
            params = [status.value, approved_by, content_id]
        elif status == ContentStatus.PUBLISHED:
            query = """
                UPDATE zantara_content
                SET status = $1, published_at = NOW()
                WHERE id = $2
                RETURNING *
            """
            params = [status.value, content_id]
        else:
            query = """
                UPDATE zantara_content
                SET status = $1
                WHERE id = $2
                RETURNING *
            """
            params = [status.value, content_id]

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            if not row:
                raise ValueError(f"Content not found: {content_id}")
            return dict(row)

    async def schedule_content(
        self,
        content_id: UUID,
        scheduled_at: datetime,
    ) -> Dict[str, Any]:
        """Schedule content for future publication."""
        pool = await self._get_pool()

        query = """
            UPDATE zantara_content
            SET status = 'SCHEDULED', scheduled_at = $1
            WHERE id = $2
            RETURNING *
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, scheduled_at, content_id)
            if not row:
                raise ValueError(f"Content not found: {content_id}")
            return dict(row)

    async def update_content_body(
        self,
        content_id: UUID,
        title: Optional[str] = None,
        body: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update content text fields."""
        pool = await self._get_pool()

        updates = []
        params = []
        param_count = 0

        if title is not None:
            param_count += 1
            updates.append(f"title = ${param_count}")
            params.append(title)

        if body is not None:
            param_count += 1
            updates.append(f"body = ${param_count}")
            params.append(body)
            # Recalculate word count
            word_count = len(body.split())
            param_count += 1
            updates.append(f"word_count = ${param_count}")
            params.append(word_count)
            param_count += 1
            updates.append(f"reading_time_minutes = ${param_count}")
            params.append(max(1, word_count // 200))

        if summary is not None:
            param_count += 1
            updates.append(f"summary = ${param_count}")
            params.append(summary)

        if not updates:
            raise ValueError("No fields to update")

        param_count += 1
        params.append(content_id)

        query = f"""
            UPDATE zantara_content
            SET {", ".join(updates)}
            WHERE id = ${param_count}
            RETURNING *
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            if not row:
                raise ValueError(f"Content not found: {content_id}")
            return dict(row)

    async def mark_intel_signal_processed(
        self,
        signal_id: UUID,
        action: str,
        content_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Mark intel signal as processed."""
        pool = await self._get_pool()

        query = """
            UPDATE intel_signals
            SET processed = TRUE, processed_at = NOW(), action_taken = $1, content_id = $2
            WHERE id = $3
            RETURNING *
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, action, content_id, signal_id)
            if not row:
                raise ValueError(f"Intel signal not found: {signal_id}")
            return dict(row)

    # ============================================================================
    # DELETE OPERATIONS
    # ============================================================================

    async def delete_content(self, content_id: UUID) -> bool:
        """Delete content permanently."""
        pool = await self._get_pool()

        query = "DELETE FROM zantara_content WHERE id = $1"

        async with pool.acquire() as conn:
            result = await conn.execute(query, content_id)
            return result == "DELETE 1"

    # ============================================================================
    # ANALYTICS
    # ============================================================================

    async def get_content_stats(self) -> Dict[str, Any]:
        """Get overall content statistics."""
        pool = await self._get_pool()

        query = """
            SELECT
                COUNT(*) as total_content,
                COUNT(*) FILTER (WHERE status = 'PUBLISHED') as published_count,
                COUNT(*) FILTER (WHERE status = 'DRAFT') as draft_count,
                COUNT(*) FILTER (WHERE status = 'REVIEW') as review_count,
                COUNT(*) FILTER (WHERE status = 'SCHEDULED') as scheduled_count,
                COUNT(*) FILTER (WHERE ai_generated = TRUE) as ai_generated_count,
                SUM(view_count) as total_views,
                AVG(engagement_score) as avg_engagement
            FROM zantara_content
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query)
            return dict(row) if row else {}


# Singleton instance
content_repository = ContentRepository()
