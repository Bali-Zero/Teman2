-- Migration 017: ZANTARA MEDIA Content Management System
-- Provides persistent storage for content pipeline, editorial workflow, and distribution tracking
-- Replaces in-memory storage in zantara-media app

-- ============================================================================
-- CONTENT MANAGEMENT
-- ============================================================================

-- Content statuses: INTAKE → DRAFT → REVIEW → APPROVED → SCHEDULED → PUBLISHED → ARCHIVED
CREATE TYPE content_status AS ENUM (
    'INTAKE',      -- Initial signal ingestion
    'DRAFT',       -- Being written/edited
    'REVIEW',      -- Submitted for review
    'APPROVED',    -- Approved for publication
    'SCHEDULED',   -- Scheduled for future publication
    'PUBLISHED',   -- Live on platforms
    'ARCHIVED'     -- Removed from circulation
);

-- Content types
CREATE TYPE content_type AS ENUM (
    'ARTICLE',
    'SOCIAL_POST',
    'NEWSLETTER',
    'PODCAST_SCRIPT',
    'VIDEO_SCRIPT',
    'THREAD'
);

-- Content categories (aligned with NUZANTARA's categories)
CREATE TYPE content_category AS ENUM (
    'IMMIGRATION',
    'TAX',
    'BUSINESS',
    'PROPERTY',
    'LEGAL',
    'BALI_NEWS',
    'LIFESTYLE',
    'GENERAL'
);

-- Main content table
CREATE TABLE IF NOT EXISTS zantara_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Basic info
    title TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    body TEXT,
    summary TEXT,

    -- Classification
    type content_type NOT NULL,
    category content_category NOT NULL,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- Workflow
    status content_status NOT NULL DEFAULT 'DRAFT',

    -- Authorship
    author_id TEXT,
    author_name TEXT,

    -- SEO
    seo_title TEXT,
    seo_description TEXT,
    seo_keywords TEXT[],

    -- Media
    cover_image_url TEXT,
    cover_image_alt TEXT,

    -- Metadata
    word_count INTEGER DEFAULT 0,
    reading_time_minutes INTEGER DEFAULT 0,
    language TEXT DEFAULT 'en',

    -- AI tracking
    ai_generated BOOLEAN DEFAULT FALSE,
    ai_model TEXT,
    source_signal_id TEXT,

    -- Approval tracking
    approved_by TEXT,
    approved_at TIMESTAMPTZ,

    -- Publishing
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,

    -- Analytics (populated by distribution system)
    view_count INTEGER DEFAULT 0,
    engagement_score DECIMAL(5,2) DEFAULT 0.0,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Indexes
    CHECK (word_count >= 0),
    CHECK (reading_time_minutes >= 0),
    CHECK (view_count >= 0),
    CHECK (engagement_score >= 0)
);

-- Indexes for common queries
CREATE INDEX idx_zantara_content_status ON zantara_content(status);
CREATE INDEX idx_zantara_content_category ON zantara_content(category);
CREATE INDEX idx_zantara_content_type ON zantara_content(type);
CREATE INDEX idx_zantara_content_published_at ON zantara_content(published_at DESC);
CREATE INDEX idx_zantara_content_scheduled_at ON zantara_content(scheduled_at);
CREATE INDEX idx_zantara_content_tags ON zantara_content USING GIN(tags);
CREATE INDEX idx_zantara_content_created_at ON zantara_content(created_at DESC);

-- Full-text search index
CREATE INDEX idx_zantara_content_search ON zantara_content
    USING GIN(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body, '') || ' ' || coalesce(summary, '')));

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_zantara_content_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_zantara_content_updated_at
    BEFORE UPDATE ON zantara_content
    FOR EACH ROW
    EXECUTE FUNCTION update_zantara_content_updated_at();


-- ============================================================================
-- INTEL SIGNALS
-- ============================================================================

-- Track intel signals that feed the content pipeline
CREATE TABLE IF NOT EXISTS intel_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal data
    title TEXT NOT NULL,
    summary TEXT,
    category content_category NOT NULL,

    -- Source tracking
    source_name TEXT NOT NULL,
    source_url TEXT,
    source_tier INTEGER CHECK (source_tier IN (1, 2, 3)),  -- T1=Official, T2=Media, T3=Community

    -- Confidence & priority
    confidence_score DECIMAL(3,2) CHECK (confidence_score BETWEEN 0 AND 1),
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),

    -- Processing status
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    action_taken TEXT,  -- 'content_created', 'merged', 'dismissed'
    content_id UUID REFERENCES zantara_content(id) ON DELETE SET NULL,

    -- Metadata
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    raw_data JSONB,

    -- Timestamps
    signal_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_intel_signals_category ON intel_signals(category);
CREATE INDEX idx_intel_signals_processed ON intel_signals(processed, signal_date DESC);
CREATE INDEX idx_intel_signals_priority ON intel_signals(priority DESC, signal_date DESC);
CREATE INDEX idx_intel_signals_content_id ON intel_signals(content_id);


-- ============================================================================
-- DISTRIBUTION TRACKING
-- ============================================================================

-- Distribution platforms
CREATE TYPE distribution_platform AS ENUM (
    'TWITTER',
    'LINKEDIN',
    'INSTAGRAM',
    'TIKTOK',
    'TELEGRAM',
    'NEWSLETTER',
    'WEBSITE',
    'YOUTUBE'
);

-- Distribution status
CREATE TYPE distribution_status AS ENUM (
    'PENDING',
    'SCHEDULED',
    'IN_PROGRESS',
    'PUBLISHED',
    'FAILED',
    'CANCELLED'
);

-- Track content distribution across platforms
CREATE TABLE IF NOT EXISTS content_distributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL REFERENCES zantara_content(id) ON DELETE CASCADE,

    -- Platform
    platform distribution_platform NOT NULL,
    platform_post_id TEXT,  -- ID from the platform (tweet ID, post ID, etc.)
    platform_url TEXT,      -- Direct URL to the post

    -- Status
    status distribution_status NOT NULL DEFAULT 'PENDING',

    -- Scheduling
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,

    -- Platform-specific config
    config JSONB,  -- Platform-specific settings (hashtags, mentions, etc.)

    -- Results
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Analytics (populated post-publication)
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    engagement_rate DECIMAL(5,2),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE(content_id, platform),
    CHECK (retry_count >= 0)
);

CREATE INDEX idx_content_distributions_content_id ON content_distributions(content_id);
CREATE INDEX idx_content_distributions_platform ON content_distributions(platform);
CREATE INDEX idx_content_distributions_status ON content_distributions(status);
CREATE INDEX idx_content_distributions_scheduled_at ON content_distributions(scheduled_at);
CREATE INDEX idx_content_distributions_published_at ON content_distributions(published_at DESC);

-- Auto-update updated_at
CREATE TRIGGER trigger_update_content_distributions_updated_at
    BEFORE UPDATE ON content_distributions
    FOR EACH ROW
    EXECUTE FUNCTION update_zantara_content_updated_at();


-- ============================================================================
-- MEDIA ASSETS
-- ============================================================================

-- Track generated images, videos, and other media
CREATE TABLE IF NOT EXISTS media_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES zantara_content(id) ON DELETE SET NULL,

    -- Asset info
    asset_type TEXT NOT NULL CHECK (asset_type IN ('image', 'video', 'audio', 'document')),
    file_name TEXT,
    file_size_bytes BIGINT,
    mime_type TEXT,

    -- Storage
    storage_url TEXT NOT NULL,  -- Full URL to the asset
    storage_bucket TEXT,
    storage_path TEXT,

    -- Generation metadata
    generated_by TEXT,  -- 'google_imagen', 'imagineart', 'manual_upload'
    generation_prompt TEXT,
    generation_config JSONB,

    -- Dimensions (for images/videos)
    width INTEGER,
    height INTEGER,
    duration_seconds INTEGER,

    -- Usage tracking
    usage_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (file_size_bytes >= 0),
    CHECK (usage_count >= 0)
);

CREATE INDEX idx_media_assets_content_id ON media_assets(content_id);
CREATE INDEX idx_media_assets_type ON media_assets(asset_type);
CREATE INDEX idx_media_assets_created_at ON media_assets(created_at DESC);


-- ============================================================================
-- CONTENT VERSIONS (Track editing history)
-- ============================================================================

CREATE TABLE IF NOT EXISTS content_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL REFERENCES zantara_content(id) ON DELETE CASCADE,

    -- Version snapshot
    version_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    summary TEXT,

    -- Change tracking
    changed_by TEXT,
    change_description TEXT,

    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(content_id, version_number)
);

CREATE INDEX idx_content_versions_content_id ON content_versions(content_id, version_number DESC);


-- ============================================================================
-- AUTOMATION LOGS
-- ============================================================================

-- Track automated pipeline runs
CREATE TABLE IF NOT EXISTS automation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run info
    run_type TEXT NOT NULL,  -- 'daily_scrape', 'scheduled_publish', 'distribution_batch'
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),

    -- Results
    items_processed INTEGER DEFAULT 0,
    items_succeeded INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,

    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,

    -- Details
    error_message TEXT,
    logs JSONB,  -- Detailed logs

    CHECK (items_processed >= 0),
    CHECK (items_succeeded >= 0),
    CHECK (items_failed >= 0)
);

CREATE INDEX idx_automation_runs_type ON automation_runs(run_type, started_at DESC);
CREATE INDEX idx_automation_runs_status ON automation_runs(status);


-- ============================================================================
-- ANALYTICS AGGREGATIONS
-- ============================================================================

-- Daily content performance metrics
CREATE TABLE IF NOT EXISTS content_analytics_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL REFERENCES zantara_content(id) ON DELETE CASCADE,
    date DATE NOT NULL,

    -- Metrics
    views INTEGER DEFAULT 0,
    unique_views INTEGER DEFAULT 0,
    engagement_events INTEGER DEFAULT 0,  -- likes, shares, comments combined
    conversion_events INTEGER DEFAULT 0,   -- newsletter signups, clicks to services

    -- Platform breakdown
    platform_metrics JSONB,  -- { "twitter": { "views": 100, "likes": 10 }, ... }

    -- Calculated
    engagement_rate DECIMAL(5,2),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(content_id, date),
    CHECK (views >= 0),
    CHECK (unique_views >= 0)
);

CREATE INDEX idx_content_analytics_daily_content_id ON content_analytics_daily(content_id, date DESC);
CREATE INDEX idx_content_analytics_daily_date ON content_analytics_daily(date DESC);


-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Get content with full distribution status
CREATE OR REPLACE FUNCTION get_content_with_distribution_status(p_content_id UUID)
RETURNS TABLE(
    content_json JSONB,
    distributions_json JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        to_jsonb(c.*) as content_json,
        COALESCE(
            jsonb_agg(to_jsonb(cd.*)) FILTER (WHERE cd.id IS NOT NULL),
            '[]'::jsonb
        ) as distributions_json
    FROM zantara_content c
    LEFT JOIN content_distributions cd ON cd.content_id = c.id
    WHERE c.id = p_content_id
    GROUP BY c.id;
END;
$$ LANGUAGE plpgsql;

-- Get pending scheduled content
CREATE OR REPLACE FUNCTION get_pending_scheduled_content()
RETURNS TABLE(
    id UUID,
    title TEXT,
    scheduled_at TIMESTAMPTZ,
    category content_category
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.title,
        c.scheduled_at,
        c.category
    FROM zantara_content c
    WHERE c.status = 'SCHEDULED'
        AND c.scheduled_at <= NOW()
    ORDER BY c.scheduled_at ASC;
END;
$$ LANGUAGE plpgsql;

-- Get scheduled distributions
CREATE OR REPLACE FUNCTION get_pending_distributions()
RETURNS TABLE(
    id UUID,
    content_id UUID,
    platform distribution_platform,
    scheduled_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cd.id,
        cd.content_id,
        cd.platform,
        cd.scheduled_at
    FROM content_distributions cd
    WHERE cd.status IN ('SCHEDULED', 'PENDING')
        AND cd.scheduled_at <= NOW()
    ORDER BY cd.scheduled_at ASC;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- No initial data needed; content will be created through the pipeline

COMMENT ON TABLE zantara_content IS 'Main content storage for ZANTARA MEDIA editorial pipeline';
COMMENT ON TABLE intel_signals IS 'Intel signals from scraping that feed content generation';
COMMENT ON TABLE content_distributions IS 'Track multi-platform content distribution';
COMMENT ON TABLE media_assets IS 'Generated and uploaded media assets (images, videos)';
COMMENT ON TABLE content_versions IS 'Content editing history and version control';
COMMENT ON TABLE automation_runs IS 'Automated pipeline execution logs';
COMMENT ON TABLE content_analytics_daily IS 'Daily aggregated content performance metrics';
