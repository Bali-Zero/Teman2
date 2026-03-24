# Bali Intel Scraper

Intelligence pipeline for Bali Zero news and regulatory updates.

**Runs locally on Pro** via OpenClaw cron (03:00 WITA daily). NOT deployed to Fly.io.

## What It Does

- Scrapes Indonesian news, immigration, tax, and business regulation sources
- Enriches articles with AI summaries and categorization
- Publishes to BaliZero News (balizero_news Qdrant collection)

## Setup

```bash
# Requires Pro machine (OpenClaw + Chrome)
cd apps/bali-intel-scraper
pip install -r requirements.txt
```

## Key Files

- `scraper/` — Source scrapers (immigration, tax, business news)
- `enricher/` — AI enrichment pipeline
- `publisher/` — Qdrant + GitHub publisher
- `CLAUDE.md` — Scraper-specific AI rules
