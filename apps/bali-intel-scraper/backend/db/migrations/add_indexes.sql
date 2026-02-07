-- Database Indexing Strategy for Bali Intel Scraper

-- Articles table indexes
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);

-- Composite indexes
CREATE INDEX IF NOT EXISTS idx_articles_source_published ON articles(source_id, published_at DESC);

-- Sources table
CREATE INDEX IF NOT EXISTS idx_sources_url ON sources(url);
CREATE INDEX IF NOT EXISTS idx_sources_is_active ON sources(is_active) WHERE is_active = true;

-- Scraping jobs
CREATE INDEX IF NOT EXISTS idx_jobs_status ON scraping_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON scraping_jobs(created_at DESC);

ANALYZE articles;
ANALYZE sources;
