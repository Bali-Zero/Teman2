-- Migration 139: intel_radar_findings — canonical handoff between intel-radar (Pro cron)
-- and intel-scraper pipeline.
--
-- Purpose: replace JSON-file handoff (`~/.intel_scraper/incoming/`) with a single
-- DB table. intel-radar INSERTs hourly findings (5 results × query × 24h = ~120/day);
-- intel_radar_daily_digest.py (cron 18:00 WITA) reads the day's findings, clusters
-- preliminary by topic, sends one Telegram digest, marks `processed=true`, emits
-- `NOTIFY intel_radar_batch_ready`. intel-scraper consumes processed/unpicked rows.
--
-- Schema decisions (3/3 reviewer convergence — Codex/Gemini/DeepSeek 2026-04-26):
--   - canonical_url UNIQUE: hard dedup (Codex: prevents SEO rewrite/syndicated flood)
--   - content_hash sha256: near-dup detection across slightly varied URLs
--   - query_tier enum (L1/L2/L3): rotation by hour-of-day, audit which tier produced hit
--   - published_at nullable: search engines return it ~30% of the time
--   - observed_at default NOW(): when WE saw it (radar run time)
--   - processed/processed_at: digest watermark; scraper_picked/picked_at: scraper watermark
--   - source: 'brave' | 'ddg' | 'exa' (text not enum, easier to extend)
--
-- Indices: query patterns are (a) digest reads unprocessed last 24h,
-- (b) scraper reads processed but not picked, (c) dedup lookup by canonical_url.

CREATE TABLE IF NOT EXISTS intel_radar_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    query_tier TEXT NOT NULL CHECK (query_tier IN ('L1', 'L2', 'L3')),
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    content_hash TEXT,
    title TEXT,
    description TEXT,
    source_domain TEXT,
    published_at TIMESTAMPTZ,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    scraper_picked BOOLEAN NOT NULL DEFAULT FALSE,
    scraper_picked_at TIMESTAMPTZ,
    CONSTRAINT intel_radar_findings_canonical_url_uniq UNIQUE (canonical_url)
);

CREATE INDEX IF NOT EXISTS idx_intel_radar_findings_unprocessed
    ON intel_radar_findings (observed_at DESC)
    WHERE processed = FALSE;

CREATE INDEX IF NOT EXISTS idx_intel_radar_findings_pickable
    ON intel_radar_findings (observed_at DESC)
    WHERE processed = TRUE AND scraper_picked = FALSE;

CREATE INDEX IF NOT EXISTS idx_intel_radar_findings_content_hash
    ON intel_radar_findings (content_hash)
    WHERE content_hash IS NOT NULL;

COMMENT ON TABLE intel_radar_findings IS
    'Canonical handoff: intel-radar (Pro cron) INSERTs findings, intel_radar_daily_digest reads unprocessed and marks processed=true, intel-scraper reads processed AND NOT scraper_picked. UNIQUE(canonical_url) hard dedup. See plan: intel-radar-fa-domande-flickering-boot.md section A.';

COMMENT ON COLUMN intel_radar_findings.canonical_url IS
    'URL normalized: lowercase host, no utm_*/fbclid params, no fragment. Computed at INSERT. Hard UNIQUE.';

COMMENT ON COLUMN intel_radar_findings.content_hash IS
    'sha256(title + " " + description), 64 hex chars. Used for near-dup detection across slightly varied URLs (e.g. /amp/ vs canonical).';

COMMENT ON COLUMN intel_radar_findings.query_tier IS
    'L1=core (visa/kitas/KBLI/OSS), L2=adjacent (banking/fintech/property), L3=lateral (rupiah/ASEAN/G20). Rotation by hour-of-day WITA: 0-7=L1, 8-15=L2, 16-23=L3.';

-- === ROLLBACK ===
-- Drops the table. Rolling back loses all collected findings (no soft-delete by design —
-- raw signals are reconstructible from search APIs). Indexes/comments are dropped
-- with the table via CASCADE-equivalent semantics.
DROP TABLE IF EXISTS intel_radar_findings;
