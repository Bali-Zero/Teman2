-- Migration 038: News Items Table for Intel Feed
-- Created: 2026-01-03
-- Purpose: Store scraped news from RSS and other sources

-- News items table
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

    -- Metadata for AI enrichment
    ai_summary TEXT,
    ai_tags TEXT[],
    ai_sentiment TEXT CHECK (ai_sentiment IN ('positive', 'neutral', 'negative')),

    -- Source tracking
    source_feed TEXT,  -- e.g., 'google_news', 'rss_direct', 'manual'
    external_id TEXT   -- Original ID from source for deduplication
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_news_items_category ON news_items(category);
CREATE INDEX IF NOT EXISTS idx_news_items_status ON news_items(status);
CREATE INDEX IF NOT EXISTS idx_news_items_published_at ON news_items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_items_slug ON news_items(slug);
CREATE INDEX IF NOT EXISTS idx_news_items_source_feed ON news_items(source_feed);
CREATE INDEX IF NOT EXISTS idx_news_items_external_id ON news_items(external_id);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_news_items_fts ON news_items
    USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(content, '')));

-- User saved/bookmarked news
CREATE TABLE IF NOT EXISTS user_saved_news (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    news_id UUID NOT NULL REFERENCES news_items(id) ON DELETE CASCADE,
    saved_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, news_id)
);

CREATE INDEX IF NOT EXISTS idx_user_saved_news_user ON user_saved_news(user_id);

-- News category subscriptions for alerts
CREATE TABLE IF NOT EXISTS news_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    categories TEXT[] NOT NULL DEFAULT '{}',
    frequency TEXT NOT NULL DEFAULT 'daily' CHECK (frequency IN ('instant', 'daily', 'weekly')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    unsubscribed_at TIMESTAMPTZ,
    UNIQUE(email)
);

CREATE INDEX IF NOT EXISTS idx_news_subscriptions_email ON news_subscriptions(email);
CREATE INDEX IF NOT EXISTS idx_news_subscriptions_active ON news_subscriptions(is_active) WHERE is_active = true;

-- Function to generate slug from title
CREATE OR REPLACE FUNCTION generate_news_slug(title TEXT) RETURNS TEXT AS $$
BEGIN
    RETURN lower(regexp_replace(
        regexp_replace(title, '[^a-zA-Z0-9\s-]', '', 'g'),
        '\s+', '-', 'g'
    )) || '-' || substring(md5(random()::text) from 1 for 6);
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-generate slug
CREATE OR REPLACE FUNCTION news_items_before_insert() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.slug IS NULL OR NEW.slug = '' THEN
        NEW.slug := generate_news_slug(NEW.title);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_news_items_before_insert ON news_items;
CREATE TRIGGER trg_news_items_before_insert
    BEFORE INSERT ON news_items
    FOR EACH ROW
    EXECUTE FUNCTION news_items_before_insert();

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION news_items_update_timestamp() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_news_items_update ON news_items;
CREATE TRIGGER trg_news_items_update
    BEFORE UPDATE ON news_items
    FOR EACH ROW
    EXECUTE FUNCTION news_items_update_timestamp();

-- Note: Ingesting initial data removed to prevent ON CONFLICT issues during automated migrations.
-- Data should be added via scrapers or manual scripts.