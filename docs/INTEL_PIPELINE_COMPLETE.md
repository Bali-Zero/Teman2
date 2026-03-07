# Intel Pipeline - Complete System Documentation

**Version:** 2.0
**Last Updated:** 2026-03-07
**Status:** Production - 100% Operational

---

## Architecture Overview

```
                        INTEL PIPELINE (End-to-End)

 [1] SCRAPING            [2] ENRICHMENT           [3] STAGING
 +-----------------+     +-----------------+      +------------------+
 | RSS Fetcher     |     | LLAMA Scoring   |      | Backend Submit   |
 | Reddit Scraper  | --> | Claude Enricher | -->  | + Drive Upload   |
 | Telegram Scraper|     | Dedup Filter    |      | + Classification |
 | Kaskus Scraper  |     | Image Generator |      | + Dedup Check    |
 | Exa Search      |     |                 |      |                  |
 +-----------------+     +-----------------+      +------------------+
                                                         |
                                                         v
 [6] LIVE ON SITE        [5] PUBLISH               [4] APPROVAL
 +------------------+    +------------------+      +------------------+
 | Vercel CDN       |    | Download img     |      | Telegram Voting  |
 | ISR (60s)        | <--| from Drive       | <--  | News Room UI     |
 | homepage-layout  |    | Generate MDX     |      | Position Select  |
 | /news route      |    | Git commit+push  |      | (hero/insight)   |
 +------------------+    | Update layout    |      +------------------+
                         +------------------+
```

---

## Components

### 1. Scraper (`apps/bali-intel-scraper/`)

**Entry point:** `scripts/run_intel_pipeline.py`

**Sources:**

| Source    | Method     | Script                | Notes                               |
| --------- | ---------- | --------------------- | ----------------------------------- |
| RSS feeds | feedparser | `rss_fetcher.py`      | 30+ Indonesian news feeds           |
| Reddit    | PRAW API   | `reddit_scraper.py`   | r/bali, r/indonesia, r/digitalnomad |
| Telegram  | Telethon   | `telegram_scraper.py` | Public channels                     |
| Kaskus    | Playwright | `kaskus_scraper.py`   | JS-rendered forum                   |
| Exa       | Exa API    | `exa_scraper.py`      | AI-powered web search               |

**Pipeline stages:**

1. **Fetch** - Collect articles from all sources
2. **Dedup** - Filter duplicates via URL + title similarity
3. **LLAMA Score** - Relevance scoring (0-100)
4. **Claude Validate** - E-E-A-T enrichment, fact-checking
5. **Image Generate** - Cover image via Gemini (`gemini_image_generator.py`)
6. **Push to Backend** - Submit enriched articles + base64 cover image

**Config:** `config/unified_sources.json`

**Output:** Each article pushed to `POST /api/intel/scraper/submit`

---

### 2. Cover Image Pipeline

**Generator:** `scripts/gemini_image_generator.py` (606 lines)

Uses Playwright browser automation to generate images via gemini.google.com:

- Category-specific visual prompts (Bali Zero editorial style)
- Saves to `data/images/{article_id}.png`

**Flow:**

```
Scraper generates image locally
    |
    v
Read image as base64 (in run_intel_pipeline.py _push())
    |
    v
Send as cover_image_base64 in POST payload
    |
    v
Backend uploads to Google Drive (Intel_Images folder)
    |
    v
Stores image_drive_file_id in staging JSON
    |
    v
At publish: download from Drive -> commit to GitHub
```

**Google Drive folder:** `Intel_Images` (ID: `12UhfVLsNJgHSqXQP3vFbWk3THpDeU-2-`)

**Fly.io secret:** `INTEL_IMAGES_DRIVE_FOLDER_ID`

**Why Drive (not direct commit)?**

- Avoids storing 1MB base64 per article in staging JSON
- No orphan images from rejected articles
- Images only committed to GitHub at publish time

---

### 3. Backend Intel Router (`backend/app/routers/intel.py`)

**Base URL:** `https://nuzantara-rag.fly.dev/api/intel`

#### Key Endpoints

| Endpoint                       | Method | Auth    | Purpose                       |
| ------------------------------ | ------ | ------- | ----------------------------- |
| `/scraper/submit`              | POST   | API Key | Receive articles from scraper |
| `/staging/pending`             | GET    | Public  | List pending items            |
| `/staging/preview/{type}/{id}` | GET    | Public  | Preview staging item          |
| `/staging/approve/{type}/{id}` | POST   | API Key | Initiate Telegram voting      |
| `/staging/reject/{type}/{id}`  | POST   | Public  | Reject item                   |
| `/staging/publish/{type}/{id}` | POST   | Public  | Publish to site               |
| `/search`                      | POST   | Public  | Semantic search               |
| `/metrics`                     | GET    | Public  | System metrics                |

#### Submit Endpoint (`POST /scraper/submit`)

**Model: `ScraperSubmission`**

```python
class ScraperSubmission(BaseModel):
    title: str                          # Required
    content: str                        # Required
    source_url: str                     # Required
    source_name: str                    # Required
    category: str                       # Required (visa, immigration, news, etc.)
    relevance_score: int                # Required (0-100)
    published_at: str | None = None
    extraction_method: str | None = "intel_pipeline"
    tier: str = "T2"                    # T1, T2, T3
    cover_image: str | None = None      # URL/path (legacy)
    cover_image_base64: str | None = None  # NEW: base64 for Drive upload
```

**Submit flow:**

1. Validate input
2. Classify article type (visa/news) based on category + keywords
3. Check for duplicates (URL + title similarity)
4. If `cover_image_base64` present:
   - Decode base64
   - Detect format (PNG/JPG)
   - Upload to Google Drive `Intel_Images` folder via `ServiceAccountDriveService`
   - Store `image_drive_file_id` and `image_drive_url` in staging data
5. Save to `/data/staging/{type}/{item_id}.json`
6. Return item_id

#### Publish Endpoint (`POST /staging/publish/{type}/{id}`)

**Publish flow:**

1. Read staging JSON
2. Generate MDX content from enriched data
3. If `image_drive_file_id` exists:
   - Download image from Google Drive
   - Encode as base64
   - Include in GitHub commit alongside MDX
4. If `position` specified (hero_main, hero_2-5, insight_1-3):
   - Read `homepage-layout.json` from GitHub
   - Update position with new article slug
5. Atomic Git commit: MDX + image + homepage-layout.json
6. Push to GitHub -> triggers Vercel auto-deploy
7. Archive staging file to `archived/approved/`
8. Ingest to Qdrant knowledge base

---

### 4. Approval System

#### Telegram Voting

**Service:** `backend/services/intel/intel_approval_service.py`

**Approvers:** Configured in `backend/app/core/intel_approvers.py`

**Flow:**

1. Article submitted to staging
2. Telegram notification sent with inline keyboard (Approve/Reject)
3. Team votes via Telegram buttons
4. Majority (2/3) triggers auto-publish
5. Or manual publish from News Room UI

#### News Room UI

**Route:** `/intelligence/news-room` (apps/mouth)

**Features:**

- List all pending staging items
- Preview full article content
- Position dropdown (Hero Main, Hero 2-5, Insight 1-3, Latest)
- Approve/Reject buttons
- Shows current position occupants

---

### 5. Homepage Position System

**Config file:** `apps/mouth/src/content/homepage-layout.json`

```json
{
  "hero_main": "slow-paralysis-kbli-2025",
  "hero_2": "constitutional-clash-bank-statements",
  "hero_3": "kbli-2025-bali-transformation",
  "hero_4": "art-of-strategic-patience",
  "hero_5": "ota-data-crackdown-bali-2026",
  "insight_1": "bkpm-regulation-5-2025-fdi",
  "insight_2": "indonesia-gives-tax-authority-power-to-override-your-interco",
  "insight_3": "kbli-2025-hospitality-accommodation"
}
```

**8 named positions:**

| Position    | UI Label           | Location               |
| ----------- | ------------------ | ---------------------- |
| `hero_main` | Hero Main (Large)  | Main collage, top-left |
| `hero_2`    | Hero 2             | Top-right              |
| `hero_3`    | Hero 3             | Bottom-left            |
| `hero_4`    | Hero 4             | Bottom-center          |
| `hero_5`    | Hero 5             | Bottom-right           |
| `insight_1` | Featured Insight 1 | Below hero, left       |
| `insight_2` | Featured Insight 2 | Below hero, center     |
| `insight_3` | Featured Insight 3 | Below hero, right      |
| `latest`    | Latest (default)   | Chronological feed     |

**Auto-demotion:** When a position is taken, previous occupant drops to chronological.

**Frontend reads:** Both `/` and `/news` routes use `getAllArticles()` + `homepage-layout.json`.

---

### 6. MDX Generation

**Template produces:**

```markdown
---
title: "Article Title"
slug: "article-slug"
category: "business"
excerpt: "Article summary..."
coverImage: "/static/insights/business/article-slug.jpg"
publishedAt: "2026-03-07T10:00:00Z"
tags: ["regulation", "kbli"]
featured: true
aiGenerated: true
author:
  name: "Zantara AI"
  avatar: "/static/zantara-avatar.png"
  role: "AI Research Assistant"
  isAI: true
readingTime: 5
---

## The Facts

{factual content}

---

## Bali Zero Take

### The Hidden Insight

{hidden insight - omitted if empty}

### Our Analysis

{analysis - omitted if empty}

### Our Advice

{advice - omitted if empty}

---

<Checklist items={[...]} />
```

**Conditional sections:** Bali Zero Take and Next Steps are fully omitted if all sub-fields are empty.

**JSON serialization:** Lists use `json.dumps()` for valid JSX/React rendering.

---

## Environment Variables

### Backend (Fly.io)

| Variable                       | Purpose                              |
| ------------------------------ | ------------------------------------ |
| `INTEL_IMAGES_DRIVE_FOLDER_ID` | Google Drive folder for cover images |
| `GITHUB_TOKEN`                 | GitHub API for commit/push           |
| `GITHUB_OWNER`                 | GitHub repository owner              |
| `GITHUB_REPO`                  | GitHub repository name               |
| `OPENAI_API_KEY`               | Embeddings for search/dedup          |
| `QDRANT_URL`                   | Vector DB for knowledge base         |
| `QDRANT_API_KEY`               | Qdrant authentication                |
| `API_KEYS`                     | Comma-separated valid API keys       |
| `TELEGRAM_BOT_TOKEN`           | Telegram approval notifications      |

### Scraper (`apps/bali-intel-scraper/.env`)

| Variable             | Purpose                                                |
| -------------------- | ------------------------------------------------------ |
| `SCRAPER_API_KEY`    | Auth for backend submit endpoint                       |
| `BACKEND_URL`        | Backend URL (default: `https://nuzantara-rag.fly.dev`) |
| `ANTHROPIC_API_KEY`  | Claude for E-E-A-T enrichment                          |
| `TELEGRAM_BOT_TOKEN` | Telegram notifications                                 |

---

## Staging Data Schema

**Path:** `/data/staging/{type}/{item_id}.json` (on Fly.io)

```json
{
  "item_id": "news_20260307_102402_1cd19823",
  "title": "Article Title",
  "content": "Full article content...",
  "source_url": "https://example.com/article",
  "source_name": "Jakarta Post",
  "category": "regulation",
  "relevance_score": 85,
  "intel_type": "news",
  "status": "pending",
  "detection_type": "scraper_auto",
  "detected_at": "2026-03-07T10:24:02Z",
  "cover_image": "https://example.com/image.jpg",
  "image_drive_file_id": "1y-OjFLkXEIIr336Z9v4thKOkyncVBy_r",
  "image_drive_url": "https://drive.google.com/file/d/.../view",
  "seo_metadata": {
    "title": "...",
    "keywords": ["..."],
    "faq_items": [{ "q": "...", "a": "..." }]
  },
  "enriched_data": {
    "headline": "...",
    "facts": "...",
    "bali_zero_take": {
      "hidden_insight": "...",
      "our_analysis": "...",
      "our_advice": "..."
    },
    "next_steps": {
      "expat": ["..."],
      "investor": ["..."]
    }
  }
}
```

---

## File Map

### Backend (`apps/backend-rag/`)

| File                                                             | Purpose                                         |
| ---------------------------------------------------------------- | ----------------------------------------------- |
| `backend/app/routers/intel.py`                                   | Main router: submit, staging, publish endpoints |
| `backend/app/routers/article_composer.py`                        | MDX generation and GitHub publishing            |
| `backend/services/intel/intel_staging_service.py`                | Staging CRUD operations                         |
| `backend/services/intel/intel_approval_service.py`               | Telegram voting logic                           |
| `backend/services/intel/intel_classification_service.py`         | Article type classification                     |
| `backend/app/core/intel_approvers.py`                            | Team approver configuration                     |
| `backend/services/integrations/service_account_drive_service.py` | Google Drive upload/download                    |
| `backend/services/integrations/telegram_bot_service.py`          | Telegram notifications                          |

### Scraper (`apps/bali-intel-scraper/`)

| File                                | Purpose                            |
| ----------------------------------- | ---------------------------------- |
| `scripts/run_intel_pipeline.py`     | Main pipeline orchestrator         |
| `scripts/rss_fetcher.py`            | RSS feed fetcher                   |
| `scripts/reddit_scraper.py`         | Reddit scraper                     |
| `scripts/telegram_scraper.py`       | Telegram channel scraper           |
| `scripts/kaskus_scraper.py`         | Kaskus forum scraper (Playwright)  |
| `scripts/exa_scraper.py`            | Exa AI web search                  |
| `scripts/gemini_image_generator.py` | Cover image generation via Gemini  |
| `scripts/claude_cli_enricher.py`    | Claude E-E-A-T enrichment          |
| `scripts/smart_extractor.py`        | Content extraction + LLAMA scoring |
| `config/unified_sources.json`       | Source configuration               |

### Frontend (`apps/mouth/`)

| File                                         | Purpose                             |
| -------------------------------------------- | ----------------------------------- |
| `src/content/homepage-layout.json`           | Position config (8 slots)           |
| `src/content/articles/{category}/{slug}.mdx` | Published articles                  |
| `src/app/(blog)/news/page.tsx`               | /news route (ISR, server component) |
| `src/app/(blog)/NewsPageClient.tsx`          | Shared layout for / and /news       |
| `src/lib/blog/articles.ts`                   | Article loader (getAllArticles)     |

---

## Operations

### Run the pipeline manually

```bash
cd apps/bali-intel-scraper
source venv/bin/activate
python scripts/run_intel_pipeline.py
```

### Check staging items

```bash
curl https://nuzantara-rag.fly.dev/api/intel/staging/pending
```

### Publish an article

```bash
curl -X POST https://nuzantara-rag.fly.dev/api/intel/staging/publish/news/{item_id} \
  -H "Content-Type: application/json" \
  -d '{"position": "hero_main"}'
```

### View Drive images

Google Drive folder: [Intel_Images](https://drive.google.com/drive/folders/12UhfVLsNJgHSqXQP3vFbWk3THpDeU-2-)

### Deploy backend

```bash
cd apps/backend-rag
fly deploy --strategy rolling
```

---

## Commits (This Implementation)

| Hash        | Description                                                       |
| ----------- | ----------------------------------------------------------------- |
| `341cb41d7` | fix(intel): copy-paste bug in our_advice extraction               |
| `e7e5b03`   | feat(intel): publish-to-MDX bridge with homepage position control |
| `742bd28e1` | feat(intel): cover image pipeline via Google Drive                |

---

## Testing

### End-to-end test (verified 2026-03-07)

```bash
# Submit with cover image
curl -X POST https://nuzantara-rag.fly.dev/api/intel/scraper/submit \
  -H "X-API-Key: internal-scraper-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Article",
    "content": "Test content",
    "source_url": "https://example.com/test",
    "source_name": "test",
    "category": "regulation",
    "relevance_score": 85,
    "cover_image_base64": "<base64-encoded-image>"
  }'

# Response: 200 OK with item_id
# Staging JSON contains image_drive_file_id
# Image visible in Intel_Images Drive folder
```

---

**Maintained by:** Bali Zero AI Team
**Last Verified:** 2026-03-07
