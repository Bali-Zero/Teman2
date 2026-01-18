# BaliZero Intel Scraper - Pipeline Documentation

> Last Updated: 2026-01-11
> Author: Claude Code Session

## Overview

The BaliZero Intel Pipeline is a complete news processing system that:

1. Fetches articles from RSS feeds
2. Scores and validates relevance
3. Enriches content with AI
4. Generates cover images
5. Optimizes for SEO/AEO (AI search engines)
6. Sends for manual approval via Telegram
7. Publishes to BaliZero website

---

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. RSS FETCHER                                                 │
│     Raw article: {title, summary, url}                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. LLAMA SCORER (fast, local, free)                            │
│     - Keyword matching + heuristics                             │
│     - Score 0-100, category, priority                           │
│     - Filters obvious noise (score < 40)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. CLAUDE VALIDATOR (intelligent gate)                         │
│     - For ambiguous scores (40-75)                              │
│     - Quick research/validation                                 │
│     - Decides: "Worth enriching?"                               │
│     - Can override LLAMA's category/priority                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (only approved)
┌─────────────────────────────────────────────────────────────────┐
│  4. CLAUDE MAX ENRICHMENT                                       │
│     - Fetches full article content                              │
│     - Writes complete Executive Brief                           │
│     - BaliZero style, actionable insights                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  5. CLAUDE IMAGE REASONING                                      │
│     - Reads the enriched article                                │
│     - Reasons: What scene captures this?                        │
│     - Creates unique Gemini prompt                              │
│     - Browser automation generates image                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  5.5 SEO/AEO OPTIMIZATION (NEW)                                 │
│     - Schema.org JSON-LD structured data                        │
│     - Meta tags (OG, Twitter, canonical)                        │
│     - TL;DR summary for AI citation                             │
│     - FAQ generation for featured snippets                      │
│     - Entity extraction for LLM knowledge                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  6. TELEGRAM APPROVAL (NEW)                                     │
│     - Generate HTML preview                                     │
│     - Send notification to Telegram                             │
│     - Wait for manual approval/rejection                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (only approved)
┌─────────────────────────────────────────────────────────────────┐
│  7. PUBLISH TO API                                              │
│     - Article + cover image + SEO metadata → BaliZero API       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Cost Breakdown

| Step                  | Cost           | Provider              |
| --------------------- | -------------- | --------------------- |
| LLAMA scoring         | $0             | Local Ollama          |
| Claude validation     | ~$0.01/article | Anthropic             |
| Claude Max enrichment | ~$0.05/article | Anthropic             |
| Gemini image          | $0             | Google One AI Premium |
| SEO/AEO optimization  | $0             | Local processing      |
| Telegram notification | $0             | Telegram Bot API      |

**Total cost per article: ~$0.06**

---

## New Components (Added 2026-01-04)

### 1. SEO/AEO Optimizer (`seo_aeo_optimizer.py`)

Optimizes articles for both traditional search engines (Google, Bing) and AI search engines (ChatGPT, Claude, Perplexity, Gemini).

#### Features

| Feature                 | For Google        | For AI Search           |
| ----------------------- | ----------------- | ----------------------- |
| Schema.org JSON-LD      | Rich snippets     | Entity understanding    |
| Meta tags (OG, Twitter) | Social shares     | Context signals         |
| TL;DR summary           | -                 | Direct citation         |
| FAQ generation          | Featured snippets | Q&A format for LLMs     |
| Entity extraction       | Topic signals     | Knowledge graph linking |
| Canonical URL           | Dedup             | Source attribution      |

#### Usage

```python
from seo_aeo_optimizer import optimize_article

article = {
    "title": "Indonesia Extends Digital Nomad Visa",
    "content": "The Indonesian government...",
    "category": "immigration",
    "source_url": "https://example.com/article",
    "image_url": "https://example.com/image.jpg",
}

# Returns article with added 'seo' key
optimized = optimize_article(article)

print(optimized["seo"]["title"])  # SEO-optimized title
print(optimized["seo"]["keywords"])  # Extracted keywords
print(optimized["seo"]["schema_json_ld"])  # Full JSON-LD
```

#### Output Structure

```python
article["seo"] = {
    "title": "Indonesia Extends Digital Nomad Visa | BaliZero",
    "meta_description": "Indonesia extends E33G visa from 1 to 5 years...",
    "keywords": ["digital nomad visa", "E33G", "Indonesia", ...],
    "canonical_url": "https://balizero.com/news/immigration/...",
    "tldr_summary": "Indonesia has extended the Digital Nomad Visa...",
    "key_entities": ["Indonesia", "Bali", "Ministry of Law", ...],
    "faq_items": [
        {"question": "How long is the visa valid?", "answer": "..."},
        ...
    ],
    "reading_time_minutes": 4,
    "og": {"title": "...", "description": "...", "image": "..."},
    "twitter": {"card": "summary_large_image", ...},
    "schema_json_ld": "{...}",  # Full JSON-LD string
    "dates": {"published": "...", "modified": "..."}
}
```

---

### 2. Telegram Approval System (`telegram_approval.py`)

Sends article previews to Telegram for manual approval before publishing.

#### Features

- HTML preview generation (looks like final published article)
- Telegram notification with inline buttons
- Support for multiple recipients (team notifications)
- Approve/Reject/Request Changes workflow
- Article tracking (pending, approved, rejected, changes_requested)

#### Configuration

Set environment variables:

```bash
# In .env or Fly.io secrets
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_APPROVAL_CHAT_ID=123456789  # Comma-separated for multiple
```

#### Telegram Message Format

```
📰 New Article Ready for Review

Title: Indonesia Extends Digital Nomad Visa to 5 Years

Category: IMMIGRATION
Source: Jakarta Post

🔑 Keywords: visa, E33G, digital nomad, Indonesia, Bali
🏷️ Entities: Indonesia, Bali, Ministry of Law, E33G
❓ FAQs: 3 items generated

📄 View Full HTML Preview

Article ID: 65708874ed4d

[✅ Approve] [❌ Reject]
[✏️ Request Changes]
[📄 View Full Article]
```

#### Approval Actions

| Button               | Action                                           |
| -------------------- | ------------------------------------------------ |
| ✅ Approve           | Marks article as approved, queues for publishing |
| ❌ Reject            | Marks article as rejected, discards              |
| ✏️ Request Changes   | Prompts user to reply with feedback              |
| 📄 View Full Article | Opens HTML preview in browser                    |

#### HTML Preview

The HTML preview looks like the final published article:

- Light background (white/gray)
- BaliZero header with logo
- Category badge
- Article title and meta (date, reading time, source)
- Cover image
- Formatted content with headers, lists, bold text
- FAQ section
- Source attribution
- Tags
- Footer
- Orange "PREVIEW - Pending Approval" banner at top

#### Usage

```python
from telegram_approval import TelegramApproval

approval = TelegramApproval()

# Submit article for approval
pending = await approval.submit_for_approval(
    article=article_dict,
    seo_metadata=seo_metadata,
    enriched_content=content
)

print(pending.article_id)  # Unique article ID
print(pending.preview_html)  # Path to HTML file
print(pending.telegram_message_id)  # Telegram message ID

# Check status
article = approval.get_pending_article(article_id)
print(article.status)  # pending, approved, rejected, changes_requested

# List pending articles
pending_list = approval.list_pending()

# List approved articles ready for publishing
approved_list = approval.list_approved()
```

---

## File Structure

```
apps/bali-intel-scraper/
├── scripts/
│   ├── intel_pipeline.py       # Main orchestrator
│   ├── rss_fetcher.py          # Step 1: RSS fetching
│   ├── professional_scorer.py   # Step 2: Keyword scoring
│   ├── ollama_scorer.py        # Step 2: Ollama enhancement
│   ├── claude_validator.py     # Step 3: Claude validation
│   ├── article_deep_enricher.py # Step 4: Content enrichment
│   ├── gemini_image_generator.py # Step 5: Image generation
│   ├── seo_aeo_optimizer.py    # Step 5.5: SEO/AEO
│   ├── telegram_approval.py    # Step 6: Approval
│   ├── preview_generator.py    # E-E-A-T HTML previews
│   ├── logging_config.py       # Centralized logging
│   ├── metrics.py              # Prometheus metrics
│   └── data/
│       ├── pending_articles/   # JSON files for pending articles
│       └── previews/           # HTML preview files
├── tests/
│   └── unit/
│       ├── test_intel_pipeline.py
│       ├── test_logging_config.py  # 47 tests
│       ├── test_metrics.py
│       ├── test_preview_generator.py
│       └── ...
├── docs/
│   ├── PIPELINE_DOCUMENTATION.md  # This file
│   └── BALIZERO_STYLE_GUIDE.md
├── CLAUDE.md                   # AI session memory
├── .env                        # Environment variables
└── .env.example                # Template
```

---

## Environment Variables

```bash
# Telegram Approval System
TELEGRAM_BOT_TOKEN=your_bot_token        # From @BotFather
TELEGRAM_APPROVAL_CHAT_ID=123456789      # Your chat ID (comma-separated for multiple)

# Claude API
ANTHROPIC_API_KEY=your_anthropic_key

# BaliZero API
BALIZERO_API_URL=https://balizero.com/api
BALIZERO_API_KEY=your_api_key

# Preview URL Base
# Note: Preview URLs can be served by backend (nuzantara-rag.fly.dev/preview)
# or frontend (nuzantara-mouth.vercel.app/preview)
PREVIEW_BASE_URL=https://nuzantara-rag.fly.dev/preview
```

---

## Running the Pipeline

### Full Pipeline

```python
from intel_pipeline import IntelPipeline

pipeline = IntelPipeline(
    min_llama_score=40,
    auto_approve_threshold=75,
    generate_images=True,
    require_approval=True,  # Enable Telegram approval
    dry_run=False
)

articles = [
    {"title": "...", "summary": "...", "url": "...", "source": "..."},
    # ...
]

results, stats = await pipeline.process_batch(articles)

print(f"Processed: {stats.total_input}")
print(f"Enriched: {stats.enriched}")
print(f"SEO optimized: {stats.seo_optimized}")
print(f"Pending approval: {stats.pending_approval}")
```

### Test SEO Optimizer

```bash
cd apps/bali-intel-scraper/scripts
python seo_aeo_optimizer.py
```

### Test Telegram Approval

```bash
cd apps/bali-intel-scraper/scripts
python telegram_approval.py
```

---

## Fly.io Secrets

The following secrets are configured on `nuzantara-rag`:

```bash
# View secrets
fly secrets list -a nuzantara-rag

# Set Telegram approval chat ID
fly secrets set TELEGRAM_APPROVAL_CHAT_ID=8290313965 -a nuzantara-rag

# Add multiple recipients (comma-separated)
fly secrets set TELEGRAM_APPROVAL_CHAT_ID="8290313965,ANOTHER_CHAT_ID" -a nuzantara-rag
```

---

## Current Configuration

| Setting          | Value                                                   |
| ---------------- | ------------------------------------------------------- |
| Telegram Bot     | @zantara_bot                                            |
| Approvers        | Zero (8290313965), Dea (6217157548), Damar (1813875994) |
| Bot Token Secret | TELEGRAM_BOT_TOKEN                                      |
| Chat ID Secret   | TELEGRAM_APPROVAL_CHAT_ID                               |

---

## Changelog

### 2026-01-04

- **Added SEO/AEO Optimizer** (`seo_aeo_optimizer.py`)
  - Schema.org JSON-LD generation (Article, FAQ, Organization, Breadcrumb)
  - Meta tags optimization (OG, Twitter, canonical)
  - TL;DR summary for AI citation
  - Entity extraction for LLM knowledge graphs
  - FAQ generation for featured snippets
  - Keyword extraction

- **Added Telegram Approval System** (`telegram_approval.py`)
  - HTML preview generation (article-style layout)
  - Telegram notifications with inline buttons
  - Multi-recipient support
  - Approve/Reject/Request Changes workflow
  - Article status tracking

- **Updated Pipeline** (`intel_pipeline.py`)
  - Added Step 5.5: SEO/AEO Optimization
  - Added Step 6: Telegram Approval
  - Added `require_approval` parameter
  - Added `seo_optimized` and `pending_approval` stats

- **Configuration**
  - Added `TELEGRAM_APPROVAL_CHAT_ID` to Fly.io secrets
  - Created `.env.example` template

### 2026-01-11

- **Added Centralized Logging** (`logging_config.py`)
  - Environment-based log levels (DEBUG in dev, INFO in prod)
  - JSON structured logging for production (machine-parseable)
  - Log rotation (100MB) and retention (7 days)
  - Context managers: `log_context()`, `correlation_context()`
  - Decorators: `@log_operation()`, `@log_errors()`
  - PerformanceLogger class for timing operations

- **Added Metrics Module** (`metrics.py`)
  - Prometheus-compatible metrics export
  - Thread-safe MetricsCollector with counters, gauges, latencies
  - Pipeline-specific metrics (articles_input, processed, rejected, etc.)
  - Latency tracking with `track_latency()` context manager
  - StructuredLogger for component-scoped logging

- **Added E-E-A-T Preview Generator** (`preview_generator.py`)
  - BaliZero branded HTML previews for human review
  - E-E-A-T compliance indicators
  - FAQ accordion display
  - Responsive mobile layout
  - Source citations and SEO metadata preview

- **Updated Pipeline** (`intel_pipeline.py`)
  - Integrated MetricsCollector for observability
  - Integrated StructuredLogger for consistent logging
  - Added `get_metrics()` and `get_prometheus_metrics()` methods
  - Images now mandatory (E-E-A-T compliance)

- **Test Coverage**
  - Fixed 11 failing tests across 6 test files
  - Added 47 new tests for logging_config.py
  - All 563 tests passing

---

## Observability

### Logging Configuration

```python
from logging_config import setup_logging, get_logger, log_context

# At application startup
setup_logging(environment="production", app_name="intel_pipeline")

# In modules
logger = get_logger("enricher")
logger.info("Processing article", title="Example", score=85)

# With context (all logs in block include these fields)
with log_context(batch_id="abc123", user="admin"):
    logger.info("Starting enrichment")
    # ... processing ...
    logger.info("Enrichment complete")
```

### Metrics Collection

```python
from metrics import MetricsCollector, track_latency

metrics = MetricsCollector(app_name="intel_pipeline")
metrics.start_pipeline()

# Track latency
with track_latency(metrics, "claude_validation"):
    result = await validate_article(article)

# Increment counters
metrics.increment("articles_processed")
metrics.increment("claude_approved")

# End pipeline and save
metrics.end_pipeline()
metrics.save_to_file("metrics_20260111.json")

# Export for Prometheus
print(metrics.export_prometheus())
```

### Prometheus Metrics Format

```
# TYPE intel_pipeline_articles_input counter
intel_pipeline_articles_input 100

# TYPE intel_pipeline_articles_processed counter
intel_pipeline_articles_processed 85

# TYPE intel_pipeline_claude_validation_duration_ms summary
intel_pipeline_claude_validation_duration_ms_count 85
intel_pipeline_claude_validation_duration_ms_avg 1250.45
intel_pipeline_claude_validation_duration_ms_p95 2100.00
```
