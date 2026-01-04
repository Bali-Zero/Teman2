"""
Migration 038: News Items for Intel Feed

Creates tables for news items, user saved news, and subscriptions.
Supports the BaliZero Intel Feed feature.

Created: 2026-01-03
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply the migration - create news items tables."""

    logger.info("Applying migration 038: News Items for Intel Feed")

    # Create news_items table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS news_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            summary TEXT,
            content TEXT,
            source TEXT NOT NULL,
            source_url TEXT,
            category TEXT NOT NULL CHECK (category IN ('immigration', 'business', 'tax', 'property', 'lifestyle', 'tech', 'legal')),
            priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'archived')),
            image_url TEXT,
            view_count INTEGER DEFAULT 0,
            published_at TIMESTAMPTZ,
            scraped_at TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            ai_summary TEXT,
            ai_tags TEXT[],
            ai_sentiment TEXT CHECK (ai_sentiment IN ('positive', 'neutral', 'negative')),
            source_feed TEXT,
            external_id TEXT
        );
    """)

    # Create indexes
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_items_category ON news_items(category);"
    )
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_news_items_status ON news_items(status);")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_items_published_at ON news_items(published_at DESC);"
    )
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_news_items_slug ON news_items(slug);")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_items_source_feed ON news_items(source_feed);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_items_external_id ON news_items(external_id);"
    )

    # Full-text search index
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_items_fts ON news_items
        USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(content, '')));
    """)

    # Create user_saved_news table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_saved_news (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            news_id UUID NOT NULL REFERENCES news_items(id) ON DELETE CASCADE,
            saved_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, news_id)
        );
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_saved_news_user ON user_saved_news(user_id);"
    )

    # Create news_subscriptions table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS news_subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL UNIQUE,
            categories TEXT[] NOT NULL DEFAULT '{}',
            frequency TEXT NOT NULL DEFAULT 'daily' CHECK (frequency IN ('instant', 'daily', 'weekly')),
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            unsubscribed_at TIMESTAMPTZ
        );
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_subscriptions_email ON news_subscriptions(email);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_news_subscriptions_active ON news_subscriptions(is_active) WHERE is_active = true;"
    )

    # Create slug generation function
    await conn.execute("""
        CREATE OR REPLACE FUNCTION generate_news_slug(title TEXT) RETURNS TEXT AS $$
        BEGIN
            RETURN lower(regexp_replace(
                regexp_replace(title, '[^a-zA-Z0-9\\s-]', '', 'g'),
                '\\s+', '-', 'g'
            )) || '-' || substring(md5(random()::text) from 1 for 6);
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger to auto-generate slug
    await conn.execute("""
        CREATE OR REPLACE FUNCTION news_items_before_insert() RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.slug IS NULL OR NEW.slug = '' THEN
                NEW.slug := generate_news_slug(NEW.title);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    await conn.execute("DROP TRIGGER IF EXISTS trg_news_items_before_insert ON news_items;")
    await conn.execute("""
        CREATE TRIGGER trg_news_items_before_insert
            BEFORE INSERT ON news_items
            FOR EACH ROW
            EXECUTE FUNCTION news_items_before_insert();
    """)

    # Create trigger for updated_at
    await conn.execute("""
        CREATE OR REPLACE FUNCTION news_items_update_timestamp() RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    await conn.execute("DROP TRIGGER IF EXISTS trg_news_items_update ON news_items;")
    await conn.execute("""
        CREATE TRIGGER trg_news_items_update
            BEFORE UPDATE ON news_items
            FOR EACH ROW
            EXECUTE FUNCTION news_items_update_timestamp();
    """)

    logger.info("Migration 038 applied successfully")


async def rollback(conn: Any) -> None:
    """Rollback the migration - drop news tables."""

    logger.info("Rolling back migration 038: News Items")

    await conn.execute("DROP TRIGGER IF EXISTS trg_news_items_update ON news_items;")
    await conn.execute("DROP TRIGGER IF EXISTS trg_news_items_before_insert ON news_items;")
    await conn.execute("DROP FUNCTION IF EXISTS news_items_update_timestamp();")
    await conn.execute("DROP FUNCTION IF EXISTS news_items_before_insert();")
    await conn.execute("DROP FUNCTION IF EXISTS generate_news_slug(TEXT);")
    await conn.execute("DROP TABLE IF EXISTS news_subscriptions;")
    await conn.execute("DROP TABLE IF EXISTS user_saved_news;")
    await conn.execute("DROP TABLE IF EXISTS news_items;")

    logger.info("Migration 038 rolled back successfully")
