"""
Migration 077: Persistent post-publish queue

Replaces the in-memory _post_publish_queue list in intel.py with a PostgreSQL table.
Survives deploys and server restarts. The poller reads pending items from this table.

Items are enqueued when:
- An intel scraper article is published (intel_scraper.py publish endpoint)
- A news item is created via POST /api/news (news.py)

The post_publish_poller processes each item: cover image, translations, SEO/GEO.
"""

import logging

logger = logging.getLogger(__name__)


async def apply(conn) -> None:
    """Create post_publish_queue table."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS post_publish_queue (
            id              SERIAL PRIMARY KEY,
            slug            TEXT NOT NULL,
            title           TEXT,
            category        TEXT NOT NULL DEFAULT 'business',
            source          TEXT NOT NULL DEFAULT 'intel',
            article_id      TEXT,
            status          TEXT NOT NULL DEFAULT 'pending',
            attempts        INT NOT NULL DEFAULT 0,
            error_message   TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at      TIMESTAMPTZ,
            completed_at    TIMESTAMPTZ,
            CONSTRAINT uq_ppq_slug UNIQUE (slug)
        );
    """)

    # Index for poller queries
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ppq_status
        ON post_publish_queue (status)
        WHERE status IN ('pending', 'processing');
    """)

    logger.info("Migration 077: post_publish_queue table created")


async def rollback(conn) -> None:
    """Drop post_publish_queue table."""
    await conn.execute("DROP TABLE IF EXISTS post_publish_queue;")
    logger.info("Migration 077: post_publish_queue table dropped")
