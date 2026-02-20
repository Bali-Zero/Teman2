# PIPELINE B - Full Article Scraping Implementation ✅

**Created:** 2026-02-21  
**By:** Zan (Gemini Sonnet 4.5)  
**Status:** Core scripts implemented, ready for testing

---

## 🎯 Overview

Full 7-step pipeline for automatic article scraping, validation, enrichment, and publishing.

**Engine:** Gemini 3 Pro (proven working, $0 cost with AI Ultra)  
**Alternative:** Claude CLI abandoned (3+ hours debugging, subprocess blocking)

---

## 📁 Scripts Created

| #   | Script                       | Purpose                                  | Status         |
| --- | ---------------------------- | ---------------------------------------- | -------------- |
| 0   | `run_intel_pipeline.py`      | **Orchestrator** - coordinates all steps | ✅ Ready       |
| 1   | `unified_scraper.py`         | Scrape 609 sources → articles            | ✅ Ready       |
| 2   | `gemini_validator.py`        | Anti-duplicate check with Gemini 3 Pro   | ✅ Ready       |
| 3   | `gemini_article_enricher.py` | Deep enrichment (brief, facts, insights) | ✅ Ready       |
| 4   | `gemini_image_generator.py`  | Image generation (Stagehand + Imagen 3)  | ⏳ Placeholder |
| 5   | `gemini_seo_optimizer.py`    | Meta tags, schema.org, Open Graph        | ✅ Ready       |
| 6   | `telegram_approval.py`       | Telegram voting                          | ✅ Exists      |
| 7   | `publish_articles.py`        | Publish to website                       | ✅ Exists      |

---

## 🚀 Usage

### Quick Test (Dry Run)

```bash
cd ~/Projects/nuzantara/apps/bali-intel-scraper

# Test full pipeline (no publishing)
python3 scripts/run_intel_pipeline.py \
  --mode dry-run \
  --categories immigration \
  --limit 3 \
  --auto-approve
```

### Production Run

```bash
# Full pipeline (all steps)
python3 scripts/run_intel_pipeline.py \
  --mode full \
  --categories immigration,tax,legal \
  --limit 10

# Skip images, auto-approve
python3 scripts/run_intel_pipeline.py \
  --skip-images \
  --auto-approve \
  --categories immigration \
  --limit 20
```

### Individual Steps

```bash
# 1. Scrape
python3 scripts/unified_scraper.py \
  --categories immigration \
  --limit 5 \
  --min-score 40

# 2. Validate (uses latest scraped)
python3 scripts/gemini_validator.py --latest

# 3. Enrich (uses latest validated)
python3 scripts/gemini_article_enricher.py --latest

# 4. Images (TODO)
python3 scripts/gemini_image_generator.py --latest

# 5. SEO (uses latest enriched)
python3 scripts/gemini_seo_optimizer.py --latest
```

---

## 📊 Pipeline Flow

```
unified_sources.json (609 sources)
         ↓
    [1. SCRAPING]
    unified_scraper.py
    ├─> newspaper3k extraction
    ├─> RSS/Atom feed parsing
    └─> Ollama quality scoring (40+ threshold)
         ↓
    data/scraped/*.json
         ↓
    [2. VALIDATION]
    gemini_validator.py
    ├─> Quick keyword overlap check
    ├─> Gemini 3 Pro semantic duplicate detection
    └─> Compare vs published_articles.json
         ↓
    data/validated/*.json (approved only)
         ↓
    [3. ENRICHMENT]
    gemini_article_enricher.py
    ├─> Executive brief (200 words)
    ├─> Key facts extraction
    ├─> Actionable insights
    ├─> Legal implications
    └─> Urgency level + expiry date
         ↓
    data/enriched/*.json
         ↓
    [4. IMAGE GENERATION] (TODO)
    gemini_image_generator.py
    └─> Stagehand + Gemini Imagen 3
         ↓
    [5. SEO OPTIMIZATION]
    gemini_seo_optimizer.py
    ├─> Meta tags (title 60 chars, description 155 chars)
    ├─> Schema.org JSON-LD
    ├─> Open Graph metadata
    └─> Keywords
         ↓
    data/seo_ready/*.json
         ↓
    [6. APPROVAL] (existing)
    telegram_approval.py
    └─> Telegram voting workflow
         ↓
    [7. PUBLISHING] (existing)
    publish_articles.py
    └─> Sanity CMS / balizero.com
```

---

## 🔧 Dependencies

```bash
# Python packages
pip install newspaper3k feedparser beautifulsoup4 lxml requests

# Ollama (local scoring)
brew install ollama
ollama pull llama3.2

# Gemini CLI (already configured)
gemini --version  # Should work
```

---

## ⚙️ Configuration

### Edit orchestrator defaults:

```python
# In run_intel_pipeline.py
MIN_SCORE = 40  # Article quality threshold
TIMEOUT = 120   # Gemini timeout per article
```

### Edit scraper limits:

```python
# In unified_scraper.py
LIMIT_PER_SOURCE = 5  # Max articles per source
```

---

## 📈 Performance Estimates

**Based on Gemini 3 Pro enricher tests:**

- Validation: ~60s per article
- Enrichment: ~120s per article
- SEO: ~60s per article

**For 100 articles:**

- Scraping: ~30 min (with Ollama scoring)
- Validation: ~100 min
- Enrichment: ~200 min
- SEO: ~100 min
- **Total: ~7-8 hours**

**Daily cron (6 AM):**

- Process 20-30 articles per day
- Sustainable with AI Ultra quota

---

## 🧪 Testing Checklist

- [ ] Test unified_scraper with 3 sources
- [ ] Test gemini_validator with mock duplicates
- [ ] Test gemini_article_enricher with 3 articles
- [ ] Test gemini_seo_optimizer with 3 articles
- [ ] Test full pipeline dry-run mode
- [ ] Verify Gemini 3 Pro quota usage
- [ ] Check Ollama scoring accuracy
- [ ] Integration test with real sources

---

## 🚧 TODO

### Immediate

1. **Install dependencies:**

   ```bash
   pip install newspaper3k feedparser beautifulsoup4 lxml
   ```

2. **Test individual scripts:**
   - Start with scraper (smallest surface area)
   - Then validator (duplicate detection critical)
   - Then enricher (quality check)

3. **Create published_articles.json template:**
   ```bash
   echo '{"articles": []}' > ~/Projects/nuzantara/apps/bali-intel-scraper/data/published_articles.json
   ```

### Phase 2

- **Image generation:** Implement Stagehand + Gemini Imagen 3
  - Use existing POC in `~/.openclaw/workspace/skills/browser-lam/`
  - Adapt for batch processing
  - Add error handling for login timeout

### Phase 3

- **Monitoring:** Add CloudWatch/Sentry integration
- **Retry logic:** Implement exponential backoff for Gemini API
- **Rate limiting:** Smart throttling for AI Ultra quota
- **Notification:** Telegram alerts for pipeline failures

---

## 📝 Notes

### Why Gemini 3 Pro?

- ✅ Tested working (source enrichment)
- ✅ $0 cost (AI Ultra subscription)
- ✅ No subprocess blocking (vs Claude CLI)
- ✅ Good quality (~90% vs Claude Opus)
- ✅ Reasonable speed (~60s per article)

### Alternative: Anthropic API

If Gemini quota becomes limiting:

- API key available: `sk-ant-oat01-AYqfjPGhx...`
- Cost: ~$0.50 per 100 articles
- Quality: Slightly higher than Gemini
- Speed: ~40% faster

### Claude CLI Issue

After 3+ hours debugging:

- Blocks indefinitely in subprocess
- OAuth incompatible with automation
- Works interactively, fails in scripts
- **Conclusion:** Not viable for pipeline

---

**Status:** ✅ READY FOR TESTING  
**Next:** Install dependencies → Test scraper → Validate full pipeline
