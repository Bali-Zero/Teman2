# Article Composer API Documentation

**Version:** 1.0
**Last Updated:** 2026-01-19
**Base URL:** `https://nuzantara-rag.fly.dev/api/articles`

---

## Overview

The Article Composer API enables the marketing team to create enriched articles for the Bali Zero website. The API:

1. **Enriches** raw article content using Claude AI (Anthropic API)
2. **Generates** SEO-optimized MDX files with structured sections
3. **Publishes** articles directly to GitHub, triggering Vercel auto-deploy

**Architecture:**

```
Frontend (Article Editor)
    ↓
Article Composer API (FastAPI)
    ↓
Claude AI (Enrichment) → GitHub API (Publishing) → Vercel (Deploy)
```

---

## Authentication

**Method:** JWT Bearer Token (inherited from backend authentication)

```http
Authorization: Bearer <your-jwt-token>
```

**Note:** For development, endpoints are currently accessible without auth. Production deployment will enforce JWT validation.

---

## Endpoints

### 1. Compose Article

**Endpoint:** `POST /api/articles/compose`

**Purpose:** Enrich raw article content with Claude AI, transforming it into a Bali Zero Executive Brief format.

**Request Body:**

```json
{
  "title": "New Visa Regulation 2026",
  "content": "The Indonesian government announced new visa regulations affecting expats...",
  "category": "immigration",
  "source_url": "https://example.com/news",
  "author": "Marketing Team"
}
```

**Parameters:**

| Field        | Type   | Required | Description                                                                                              |
| ------------ | ------ | -------- | -------------------------------------------------------------------------------------------------------- |
| `title`      | string | Yes      | Article title (max 200 chars recommended)                                                                |
| `content`    | string | Yes      | Raw article content (will be truncated to 8000 chars for Claude)                                         |
| `category`   | string | No       | One of: `immigration`, `business`, `tax`, `property`, `lifestyle`, `tech`, `legal` (default: `business`) |
| `source_url` | string | No       | Original source URL if any                                                                               |
| `author`     | string | No       | Author name (default: `Marketing Team`)                                                                  |

**Response (Success):**

```json
{
  "success": true,
  "article": {
    "title": "New Visa Regulation 2026",
    "headline": "Indonesia Tightens Visa Rules: What Expats Need to Know",
    "tldr": {
      "should_worry": "Yes",
      "what": "New visa regulations require additional documentation",
      "who": "All expats on work permits",
      "when": "Effective March 2026",
      "risk_level": "High"
    },
    "facts": "<400-600 word journalism section>",
    "bali_zero_take": {
      "hidden_insight": "This is part of a broader immigration crackdown",
      "our_analysis": "The timing suggests coordination with other ASEAN countries",
      "our_advice": "Review your visa status immediately and consult immigration lawyer"
    },
    "next_steps": {
      "expat": ["Check visa expiry", "Gather required documents"],
      "investor": ["Review company sponsorship", "Update compliance procedures"]
    },
    "category": "immigration",
    "priority": "high",
    "relevance_score": 85,
    "ai_summary": "Indonesia introduces stricter visa requirements for expats starting March 2026",
    "ai_tags": ["visa", "immigration", "regulation", "expat", "compliance"],
    "suggested_components": ["timeline", "checklist", "alert-box"],
    "cover_image": null,
    "source": "Marketing Team",
    "source_url": "https://example.com/news",
    "enriched_at": "2026-01-19T10:30:00Z"
  },
  "api_cost_cents": 3.45
}
```

**Response (Error):**

```json
{
  "success": false,
  "article": null,
  "error": "Failed to parse Claude response: Expecting value: line 1 column 1 (char 0)",
  "api_cost_cents": 0
}
```

**HTTP Status Codes:**

- `200 OK` - Request processed (check `success` field for actual result)
- `500 Internal Server Error` - API key not configured

**Enrichment Details:**

**Word Count by Priority:**

- **High priority:** 600 words in facts section
- **Medium priority:** 500 words
- **Low priority:** 400 words

**Cost Estimate:**

- Model: `claude-sonnet-4-20250514`
- Average cost: $0.02-0.05 per article
- Pricing: $3 / 1M input tokens, $15 / 1M output tokens

**Processing Time:**

- Average: 3-8 seconds
- Depends on content length and Claude API latency

---

### 2. Publish Article

**Endpoint:** `POST /api/articles/publish`

**Purpose:** Publish an enriched article to the Bali Zero website via GitHub, triggering Vercel auto-deploy.

**Request Body:**

```json
{
  "article": {
    // ... (EnrichedArticle object from compose response)
  },
  "cover_image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "cover_image_filename": "visa-regulation-2026.jpg",
  "position": "normal",
  "slug": "indonesia-tightens-visa-rules"
}
```

**Parameters:**

| Field                  | Type   | Required | Description                                                           |
| ---------------------- | ------ | -------- | --------------------------------------------------------------------- |
| `article`              | object | Yes      | EnrichedArticle object from `/compose` response                       |
| `cover_image_base64`   | string | No       | Cover image as base64-encoded string                                  |
| `cover_image_filename` | string | No       | Cover image filename (e.g., `article-cover.jpg`)                      |
| `position`             | string | No       | Article position: `main_featured`, `secondary`, or `normal` (default) |
| `slug`                 | string | No       | Custom URL slug (auto-generated from headline if not provided)        |

**Response (Success):**

```json
{
  "success": true,
  "message": "Article published successfully. Vercel will auto-deploy in ~1 minute.",
  "article_url": "https://balizero.com/immigration/indonesia-tightens-visa-rules",
  "mdx_path": "apps/mouth/src/content/articles/immigration/indonesia-tightens-visa-rules.mdx",
  "image_path": "/static/news/visa-regulation-2026.jpg",
  "commit_sha": "abc1234"
}
```

**Response (Error):**

```json
{
  "success": false,
  "message": "Failed to publish to GitHub",
  "article_url": null,
  "mdx_path": null,
  "image_path": null,
  "commit_sha": null,
  "error": "GitHub API error: Rate limit exceeded"
}
```

**HTTP Status Codes:**

- `200 OK` - Request processed (check `success` field for actual result)

**Publishing Details:**

**GitHub Commit Strategy:**

- **Single file:** Uses `upload_file()` if no cover image
- **Atomic commit:** Uses `create_commit_with_files()` if cover image provided
- **Branch:** `main` (triggers immediate Vercel deploy)

**File Locations:**

- **MDX file:** `apps/mouth/src/content/articles/{category}/{slug}.mdx`
- **Cover image:** `apps/mouth/public/static/news/{filename}`

**Category Mapping:**

```
immigration → immigration
business → business
tax → tax-legal
legal → tax-legal
property → property
lifestyle → lifestyle
tech → tech
```

**Vercel Deploy Time:**

- Typical: 30-90 seconds after GitHub commit
- Article visible at: `https://balizero.com/{category}/{slug}`

---

### 3. Compose Status

**Endpoint:** `GET /api/articles/compose/status`

**Purpose:** Check if Article Composer is properly configured.

**Request:** No body required

**Response:**

```json
{
  "configured": true,
  "api_key_set": true,
  "model": "claude-sonnet-4-20250514",
  "estimated_cost_per_article": "$0.02-0.05"
}
```

**HTTP Status Codes:**

- `200 OK` - Always returns 200

**Use Case:** Health check before initiating compose requests

---

### 4. Publish Status

**Endpoint:** `GET /api/articles/publish/status`

**Purpose:** Check if GitHub publishing is properly configured.

**Request:** No body required

**Response:**

```json
{
  "configured": true,
  "github_token_set": true,
  "github_owner": "Balizero1987",
  "github_repo": "Teman2",
  "target_branch": "main"
}
```

**HTTP Status Codes:**

- `200 OK` - Always returns 200

**Use Case:** Health check before initiating publish requests

---

## Error Handling

### Common Error Scenarios

#### 1. Claude API Errors

**Cause:** Anthropic API down, rate limit, or invalid API key

**Response:**

```json
{
  "success": false,
  "error": "Claude API error: Rate limit exceeded"
}
```

**Retry Strategy:** Exponential backoff (1s, 2s, 4s, 8s)

#### 2. JSON Parse Errors

**Cause:** Claude returned invalid JSON or non-JSON response

**Response:**

```json
{
  "success": false,
  "error": "Failed to parse Claude response: Expecting value: line 1 column 1"
}
```

**Resolution:** Check Claude system prompt, verify model version

#### 3. GitHub API Errors

**Cause:** GitHub down, rate limit, or invalid token

**Response:**

```json
{
  "success": false,
  "message": "Failed to publish to GitHub",
  "error": "GitHub API error: Bad credentials"
}
```

**Resolution:** Verify `GITHUB_TOKEN` secret on Fly.io

#### 4. Missing Configuration

**Cause:** API key or GitHub token not set

**Response (Compose):**

```http
HTTP 500 Internal Server Error
{
  "detail": "API key not configured"
}
```

**Response (Publish):**

```json
{
  "success": false,
  "message": "GitHub API not configured",
  "error": "Missing GITHUB_TOKEN environment variable"
}
```

**Resolution:** Set secrets on Fly.io:

```bash
fly secrets set ANTHROPIC_API_KEY="sk-..." -a nuzantara-rag
fly secrets set GITHUB_TOKEN="ghp_..." -a nuzantara-rag
```

---

## Rate Limits

### Claude API

**Limits (Anthropic):**

- Tier 1: 50 requests/min, 40K tokens/min
- Tier 2: 1,000 requests/min, 80K tokens/min

**Current Usage:**

- ~1,500-2,500 tokens per article
- Can process 15-25 articles/min (Tier 1)

**Recommendation:** Implement client-side rate limiting (5 requests/min)

### GitHub API

**Limits (GitHub):**

- Authenticated: 5,000 requests/hour
- Content API: 5,000 requests/hour

**Current Usage:**

- 1-2 requests per article publish
- Can publish 2,500-5,000 articles/hour

**Recommendation:** No client-side limiting needed

---

## Best Practices

### 1. Content Preparation

**DO:**

- ✅ Provide structured raw content (headline, intro, body, conclusion)
- ✅ Include dates, numbers, sources for better enrichment
- ✅ Specify correct category for proper classification

**DON'T:**

- ❌ Send content > 10,000 chars (will be truncated to 8000)
- ❌ Use generic titles like "News Update" (Claude needs context)
- ❌ Mix multiple topics in single article

### 2. Cover Images

**Recommendations:**

- Format: JPEG or PNG
- Size: 1200x630px (optimal for social sharing)
- Max file size: 2MB
- Encode as base64 before sending

**Example (JavaScript):**

```javascript
const file = event.target.files[0];
const reader = new FileReader();
reader.onload = (e) => {
  const base64 = e.target.result.split(',')[1]; // Remove data:image/jpeg;base64,
  publishArticle({ ..., cover_image_base64: base64 });
};
reader.readAsDataURL(file);
```

### 3. Slug Generation

**Auto-generated slugs:**

- Lowercase
- Spaces → hyphens
- Remove special characters
- Max 60 chars

**Custom slugs:**

- Must be URL-safe
- Should match headline semantics
- Avoid generic terms like "article-1"

### 4. Error Recovery

**Compose failures:**

1. Check `/compose/status` first
2. Retry with exponential backoff (max 3 retries)
3. If JSON parse fails, check raw response in logs
4. Log error + `article.title` for debugging

**Publish failures:**

1. Check `/publish/status` first
2. Verify article object is valid EnrichedArticle
3. If image upload fails, retry without image
4. Check GitHub commit history for partial commits

---

## Monitoring

### Prometheus Metrics

**✅ IMPLEMENTED** - Metrics are exposed at `/metrics` endpoint

**Available metrics:**

- `article_compose_requests_total{status, category}` - Total compose requests by status and category
- `article_compose_duration_seconds` - Histogram of compose duration
- `article_enrichment_word_count{priority}` - Histogram of word count by priority (high/medium/low)
- `article_publish_requests_total{status, has_cover_image}` - Total publish requests by status and image presence
- `claude_api_cost_cents` - Histogram of Claude API cost per article (in cents)

**Example Prometheus queries:**

```promql
# Compose success rate (last 5min)
rate(article_compose_requests_total{status="success"}[5m])
/ rate(article_compose_requests_total[5m])

# Average enrichment word count by priority
avg(article_enrichment_word_count{priority="high"})

# 95th percentile compose duration
histogram_quantile(0.95, article_compose_duration_seconds)

# Total Claude API cost (daily)
sum(increase(claude_api_cost_cents[24h])) / 100
```

**Access metrics:**

```bash
# View all metrics
curl https://nuzantara-rag.fly.dev/metrics | grep article_compose

# Example output:
# article_compose_requests_total{category="immigration",status="success"} 15.0
# article_compose_duration_seconds_bucket{le="1.0"} 5.0
# article_compose_duration_seconds_bucket{le="2.0"} 12.0
# article_compose_duration_seconds_bucket{le="5.0"} 15.0
```

### Grafana Dashboards

**Status:** Metrics available, dashboard creation recommended

**Recommended dashboard queries:**

- Compose success rate (last 5min)
- Average enrichment word count by priority
- 95th percentile compose duration
- Total Claude API cost (daily/monthly)
- Publish success rate
- Articles published per day by category

### Logging

**Log Levels:**

- `INFO` - Success paths, API calls, cost tracking
- `WARNING` - Retries, fallbacks
- `ERROR` - Failures, exceptions

**Example logs:**

```
INFO: Composing article: New Visa Regulation 2026...
INFO: Calling Claude API for enrichment...
INFO: ✅ Article enriched: Indonesia Tightens Visa Rules...
INFO:    Cost: $0.0345 (1000 in, 1500 out)
INFO: Will upload cover image: apps/mouth/public/static/news/visa-2026.jpg
INFO: ✅ Article published: https://balizero.com/immigration/indonesia-tightens-visa-rules
INFO:    Commit: abc1234
```

---

## Development

### Local Testing

**Prerequisites:**

```bash
cd apps/backend-rag
source .venv/bin/activate
export ANTHROPIC_API_KEY="sk-..."
export GITHUB_TOKEN="ghp_..."
```

**Start server:**

```bash
PYTHONPATH=. python -m backend.app.main_cloud
```

**Test compose:**

```bash
curl -X POST http://localhost:8080/api/articles/compose \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Article",
    "content": "Test content for development...",
    "category": "business"
  }'
```

**Test publish:**

```bash
curl -X POST http://localhost:8080/api/articles/publish \
  -H "Content-Type: application/json" \
  -d @publish_request.json
```

### Running Tests

**Test suite location:** `backend/tests/unit/routers/test_article_composer.py`

**Run all tests:**

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/routers/test_article_composer.py -v
```

**Run specific test:**

```bash
PYTHONPATH=. pytest backend/tests/unit/routers/test_article_composer.py::test_compose_article_priority_word_count -v
```

**Test coverage:**

```bash
PYTHONPATH=. pytest backend/tests/unit/routers/test_article_composer.py --cov=backend.app.routers.article_composer
```

**Expected output:**

```
23 tests passing
Coverage: 100%
```

---

## Deployment

### Environment Variables

**Required secrets (Fly.io):**

```bash
ANTHROPIC_API_KEY="sk-ant-..."
GITHUB_TOKEN="ghp_..."
GITHUB_OWNER="Balizero1987"
GITHUB_REPO="Teman2"
```

**Set secrets:**

```bash
fly secrets set ANTHROPIC_API_KEY="sk-..." -a nuzantara-rag
fly secrets set GITHUB_TOKEN="ghp_..." -a nuzantara-rag
```

**Verify secrets:**

```bash
fly secrets list -a nuzantara-rag
```

### Health Checks

**Backend health:**

```bash
curl https://nuzantara-rag.fly.dev/health
# → {"status": "healthy"}
```

**Compose status:**

```bash
curl https://nuzantara-rag.fly.dev/api/articles/compose/status
# → {"configured": true}
```

**Publish status:**

```bash
curl https://nuzantara-rag.fly.dev/api/articles/publish/status
# → {"configured": true}
```

---

## Changelog

### v1.1 (2026-01-24)

**Updated:**

- Metrics documentation: Changed from "To be implemented" to "✅ IMPLEMENTED"
- Added Prometheus query examples
- Added metrics access instructions

### v1.0 (2026-01-19)

**Added:**

- Dynamic word count by priority (400-600 words)
- Proper JSON serialization for React components in MDX
- Prometheus metrics (article_compose_requests_total, article_compose_duration_seconds, etc.)

**Removed:**

- `image_prompt` field (cover images now provided by frontend)
- `generate_cover_image()` function

**Fixed:**

- MDX template JSON serialization for `next_steps` arrays
- Enrichment prompt now specifies priority-based word counts

**Changed:**

- Enrichment from 200-300 to 400-600 words
- High priority = 600 words, Medium = 500, Low = 400

---

## Support

**Questions or issues?**

- Check logs: `fly logs -a nuzantara-rag`
- Review CLAUDE.md for session notes
- Contact: Backend Team

**Known Issues:**

- See `apps/backend-rag/CLAUDE.md` section "Known Issues & Tech Debt"

---

**Last Updated:** 2026-01-19
**Maintained by:** Backend Team
**API Version:** 1.0
