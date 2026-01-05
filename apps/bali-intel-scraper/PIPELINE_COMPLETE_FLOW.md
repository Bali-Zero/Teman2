# BALI INTEL PIPELINE - Complete Flow Documentation

## 🎯 Overview

Pipeline completo da 790+ fonti web → Articolo pubblicato su balizero.com con anti-duplicate detection.

**Architettura:** Esecuzione locale su Mac (costo $0/mese)
**Tools:** Ollama (LLAMA scoring), Claude CLI (validation/enrichment), Chrome (Gemini images)

---

## 📊 Diagramma Architettura

```
┌───────────────────────────────────────────────────────────────────┐
│                    MASSIVE MODE PIPELINE                           │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│  1️⃣ SCRAPING (unified_scraper.py)                                │
│     └─> 790+ sources (T1/T2/T3)                                   │
│         ├─> SmartExtractor (newspaper3k + BeautifulSoup)          │
│         ├─> SemanticDeduplicator (embeddings)                     │
│         └─> OllamaScorer (local LLAMA 40+ min score)              │
│                                                                    │
│  2️⃣ VALIDATION (claude_validator.py) - DUPLICATE CHECK!           │
│     └─> Claude Desktop CLI (subprocess)                           │
│         ├─> Carica ultimi 50 articoli pubblicati                  │
│         ├─> Quick check: 60% keyword overlap                      │
│         ├─> Semantic check: Claude confronta titoli               │
│         └─> REJECT se duplicato, APPROVE se nuovo                 │
│                                                                    │
│  3️⃣ ENRICHMENT (article_deep_enricher.py)                         │
│     └─> Claude Max (expensive - solo dopo validation)             │
│         ├─> Executive brief (200 words)                           │
│         ├─> Key facts extraction                                  │
│         ├─> Actionable insights                                   │
│         └─> Legal analysis                                        │
│                                                                    │
│  4️⃣ IMAGE GENERATION (gemini_image.py)                            │
│     └─> Chrome browser automation                                 │
│         ├─> Gemini Imagen 3 (FREE)                                │
│         ├─> Professional 16:9 1536x768px                          │
│         └─> Download to data/images/                              │
│                                                                    │
│  5️⃣ SEO OPTIMIZATION (seo_aeo_optimizer.py)                       │
│     └─> Claude generates:                                         │
│         ├─> Meta tags (title 60 chars, description 155 chars)     │
│         ├─> Schema.org JSON-LD (Article, BreadcrumbList)          │
│         ├─> FAQ schema                                            │
│         └─> Full HTML with Open Graph                             │
│                                                                    │
│  6️⃣ SUBMISSION FOR APPROVAL (parallel)                            │
│     ├─> 6a. News Room UI (intel_pipeline.py)                      │
│     │    └─> POST /api/intel/scraper/submit                       │
│     │        └─> Saves to data/staging/news/{id}.json             │
│     │            └─> Team reviews at zantara.balizero.com         │
│     │                                                              │
│     └─> 6b. Telegram Voting (telegram_approval.py)                │
│          └─> Message con preview HTML + buttons                   │
│              └─> Majority vote: 2/3 required                       │
│                  ├─> ✅ APPROVE: Queued for publish                │
│                  └─> ❌ REJECT: Archived                           │
│                                                                    │
│  7️⃣ PUBLISHING (⏳ TO BE IMPLEMENTED)                             │
│     └─> After approval → Publish to website                       │
│         ├─> Sanity CMS / balizero.com                             │
│         └─> ClaudeValidator.add_published_article()               │
│             └─> Updates data/published_articles.json              │
│                 └─> Loop closes! (feed duplicate detection)       │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Usage

### Run Massive Mode (Full Pipeline)

```bash
cd apps/bali-intel-scraper/scripts

# Full run: scrape + process
python run_intel_feed.py \
  --mode massive \
  --categories immigration,tax-legal \
  --tiers T1,T2 \
  --limit-per-source 5 \
  --min-score 40 \
  --generate-images \
  --require-approval

# Dry run (test without Claude enrichment)
python run_intel_feed.py \
  --mode massive \
  --dry-run \
  --limit-per-source 2
```

### Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `full` | `massive` = unified_scraper + pipeline |
| `--categories` | `all` | Filter: `immigration,tax-legal,business,property` |
| `--tiers` | `all` | Source priority: `T1,T2,T3` |
| `--limit-per-source` | `5` | Articles per source (max) |
| `--min-score` | `40` | LLAMA score threshold (0-100) |
| `--generate-images` | `False` | Enable Gemini image generation |
| `--require-approval` | `True` | Send to Telegram for voting |
| `--dry-run` | `False` | Skip Claude enrichment (fast test) |

---

## 📁 File Structure

```
apps/bali-intel-scraper/scripts/
├── run_intel_feed.py           # Main runner (--mode massive)
├── unified_scraper.py          # BaliZeroScraperV2 (790+ sources)
├── intel_pipeline.py           # 7-step processing pipeline
├── claude_validator.py         # 🔴 Anti-duplicate + validation
├── article_deep_enricher.py    # Claude Max enrichment
├── gemini_image.py             # Browser automation for images
├── seo_aeo_optimizer.py        # SEO + schema generation
├── telegram_approval.py        # Voting system (2/3 majority)
│
├── config/
│   └── unified_sources.json    # 790+ source definitions
│
└── data/
    ├── scraped_articles.json   # Raw scraper output
    ├── images/                 # Generated cover images
    ├── previews/               # HTML previews for Telegram
    ├── pending_articles/       # Waiting for approval
    └── published_articles.json # 🔴 Anti-duplicate registry
```

---

## 🔍 Anti-Duplicate System (NEW)

### How it Works

1. **Registry File:** `data/published_articles.json`
   - Stores last 500 published articles
   - Auto-created on first run
   - Updates on each publish

2. **Two-Layer Detection:**

   **Layer 1: Quick Keyword Check** (60% threshold)
   ```python
   # Fast local check before calling Claude
   title_words = {"indonesia", "extends", "digital", "nomad", "visa"}
   published_words = {"indonesian", "extended", "digital", "nomad", "visa"}
   overlap = 4/5 = 80% → DUPLICATE!
   ```

   **Layer 2: Claude Semantic Analysis**
   ```
   Claude receives list of last 50 published articles:
   - [immigration] Indonesia Extends Digital Nomad Visa to 5 Years
   - [tax-legal] New Coretax System Causing NPWP Delays

   Task #1: DUPLICATE CHECK (CRITICAL!)
   Compare this article against ALREADY PUBLISHED list above.
   If SUBSTANTIALLY SIMILAR → REJECT
   ```

3. **Validation Output:**
   ```json
   {
     "approved": false,
     "confidence": 85,
     "reason": "Duplicate of already published article",
     "is_duplicate": true,
     "similar_to": "Indonesia Extends Digital Nomad Visa to 5 Years"
   }
   ```

4. **Auto-Approve Override:**
   - Even articles with LLAMA score ≥75 get duplicate check
   - Prevents auto-approving duplicates from different sources

### Integration Point (⏳ To Be Implemented)

After publishing to website:

```python
from claude_validator import ClaudeValidator

# In publish endpoint/script
ClaudeValidator.add_published_article(
    title="Indonesia's 0% Tax on Foreign Income",
    url="https://balizero.com/tax/zero-tax-foreign-income",
    category="tax-legal",
    published_at="2026-01-05T10:00:00"
)
```

See: `ANTI_DUPLICATE_INTEGRATION.md` for detailed integration guide.

---

## 📊 Stats & Monitoring

### Pipeline Stats (example output)

```
═══════════════════════════════════════════════════════════════════
📊 PIPELINE SUMMARY
═══════════════════════════════════════════════════════════════════
   Total input:      47
   LLAMA scored:     47
   LLAMA filtered:   12  (low score < 40)
   Claude validated: 35
   Claude approved:  28
   Claude rejected:  7   (includes duplicates!)
   Duplicate reject: 3   🔴 NEW!
   Enriched:         28
   Images generated: 28
   SEO optimized:    28
   Pending approval: 28
   Published:        0   (after team approves)
   Errors:           0
   Duration:         847.3s
═══════════════════════════════════════════════════════════════════
```

### Validator Stats

```python
validator.stats = {
    "auto_approved": 15,        # LLAMA ≥75, no duplicates
    "auto_rejected": 8,         # LLAMA <40
    "validated_approved": 13,   # Claude approved
    "validated_rejected": 4,    # Claude rejected (quality)
    "duplicate_rejected": 3,    # 🔴 Duplicates detected
    "validation_errors": 0
}
```

---

## 🎯 Source Configuration

### Source Tiers

**T1 (Official):** 127 sources
- Government sites (imigrasi.go.id, kemenkeu.go.id)
- Embassies, official portals

**T2 (Professional):** 361 sources
- Jakarta Post, Antara News
- Legal firms, consulting agencies

**T3 (Community):** 302 sources
- Facebook groups, Reddit
- Expat blogs, forums

### Example Source Entry

```json
{
  "name": "Imigrasi Indonesia",
  "url": "https://www.imigrasi.go.id",
  "category": "immigration",
  "tier": "T1",
  "method": "smart_extraction",
  "selectors": [".article", ".news-item"],
  "freshness_days": 30,
  "enabled": true
}
```

---

## 🔧 Technical Details

### Cost Breakdown (Local Execution)

| Component | Provider | Cost |
|-----------|----------|------|
| LLAMA Scoring | Ollama (local) | **$0** |
| Claude Validation | Claude Desktop CLI (Max subscription) | **$0** |
| Claude Enrichment | Claude Desktop CLI | **$0** |
| Image Generation | Gemini Imagen 3 (browser automation) | **$0** |
| **TOTAL** | | **$0/month** |

### Performance

- **Scraping:** ~790 sources in 15-20 min (parallel)
- **LLAMA Scoring:** ~2-3 sec/article (local Ollama)
- **Claude Validation:** ~5-8 sec/article (duplicate check included)
- **Claude Enrichment:** ~25-35 sec/article (executive brief + analysis)
- **Image Generation:** ~12-15 sec/image (Chrome + Gemini)
- **SEO Optimization:** ~8-12 sec/article

**Total:** ~60-80 sec/article (full pipeline)

### Rate Limits

- Ollama: No limit (local)
- Claude Desktop: ~50 requests/min (soft limit)
- Gemini browser: ~10 images/min (avoid detection)

---

## 🚧 Known Issues & Fixes

### Issue 1: FileNotFoundError for config
**Fixed:** Use absolute path `Path(__file__).parent.parent / "config"`

### Issue 2: KeyError 'selectors'
**Fixed:** Add default selectors when source doesn't have selectors field

### Issue 3: timeout command not found (Mac)
**Fixed:** Removed GNU timeout, use subprocess timeout parameter

### Issue 4: Duplicates being published
**Fixed:** ✅ Anti-duplicate system implemented (validation + registry)

---

## 🎬 Workflow Example

### Scenario: Indonesia extends Digital Nomad Visa to 5 years

```
Step 1: SCRAPING
  Source: Jakarta Post (T2)
  Title: "Indonesia's Digital Nomad Visa Extended to Five Years"
  LLAMA Score: 87/100 ✅

Step 2: VALIDATION (with duplicate check)
  Quick check: No match in last 100 published titles ✅
  Claude check: "This is new policy, not a duplicate" ✅
  → APPROVED

Step 3: ENRICHMENT
  Executive Brief: "The Indonesian government has announced..."
  Key Facts: ["Validity: 5 years", "Eligible: remote workers", ...]
  → Enriched ✅

Step 4: IMAGE
  Prompt: "Digital nomad working on laptop in Bali rice terrace..."
  → Generated: data/images/digital-nomad-visa-extension.jpg ✅

Step 5: SEO
  Meta title: "Indonesia Digital Nomad Visa: Now 5 Years | Bali Zero"
  Meta desc: "Indonesia extends digital nomad visa validity from 1..."
  Schema: Article + FAQ
  → SEO ready ✅

Step 6: SUBMISSION
  6a. News Room: ✅ Sent to zantara.balizero.com/intelligence/news-room
  6b. Telegram: 📱 Vote message sent to team channel
      Votes: ✅ Zero, ✅ Dea → APPROVED (2/3)

Step 7: PUBLISHING (⏳ manual for now)
  Team clicks "Publish" in News Room UI
  → Article published to balizero.com
  → ClaudeValidator.add_published_article() called
  → Registry updated with new article
  → Future duplicates will be detected! 🎉
```

---

## 📋 Next Steps

### To Complete Full Loop

1. **Implement Publish Endpoint**
   - Create `/api/intel/staging/{item_id}/publish` in backend
   - Integrate Sanity CMS or direct website publish
   - Call `ClaudeValidator.add_published_article()` after success

2. **Add Publish Button in News Room UI**
   - Update `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`
   - Add "Publish" button for approved articles
   - Call backend publish endpoint

3. **Automate Telegram → Publish**
   - Option: Auto-publish after 2/3 approval
   - Or: Keep manual for quality control

See: `ANTI_DUPLICATE_INTEGRATION.md` for detailed implementation guide.

---

## 🎓 Best Practices

1. **Always run with `--dry-run` first** to test scraper + validator
2. **Monitor duplicate_rejected stats** to tune thresholds
3. **Review registry file** periodically (keep last 500 articles)
4. **Use categories filter** to focus on specific topics
5. **Limit sources in dev** (`--limit-per-source 2`) for faster iteration

---

## 📞 Support

- **Integration Guide:** `ANTI_DUPLICATE_INTEGRATION.md`
- **Source Config:** `config/unified_sources.json`
- **Pipeline Code:** `intel_pipeline.py` (lines 1-600)
- **Validator Code:** `claude_validator.py` (lines 74-390)

---

**Last Updated:** 2026-01-05
**Status:** ✅ Duplicate detection complete, ⏳ Publish integration pending
