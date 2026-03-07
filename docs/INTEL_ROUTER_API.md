# Intel Router API Documentation

**Version:** 2.0
**Last Updated:** 2026-03-07
**Base URL:** `https://nuzantara-rag.fly.dev/api/intel`

---

## Overview

The Intel Router API provides endpoints for managing intelligence articles from the Bali Intel Scraper pipeline. It handles:

1. **Scraper Integration** - Receives articles from `bali-intel-scraper` pipeline
2. **Staging Management** - Stores articles pending approval
3. **Approval Workflow** - Manages approval/rejection/publishing
4. **Search & Analytics** - Semantic search and intelligence analytics

**Architecture:**

```
Intel Scraper Pipeline
    ↓
POST /api/intel/scraper/submit (+ cover_image_base64 → Google Drive)
    ↓
Staging Area (data/staging/{type}/{item_id}.json) [image_drive_file_id stored]
    ↓
Team Approval (Telegram + News Room UI + Position Select)
    ↓
POST /api/intel/staging/publish/{type}/{item_id}
    ↓
Download image from Drive → Generate MDX → Git commit+push → Vercel deploy
    ↓
Qdrant Knowledge Base + Live on balizero.com
```

---

## Authentication

**Method:** Internal API Key (for scraper) or JWT Bearer Token (for admin endpoints)

```http
X-API-Key: <internal-api-key>
# OR
Authorization: Bearer <jwt-token>
```

**Public Endpoints (no auth):**

- `GET /api/intel/staging/pending`
- `GET /api/intel/staging/preview/{type}/{item_id}`
- `POST /api/intel/search`
- `GET /api/intel/metrics`
- `GET /api/intel/critical`
- `GET /api/intel/trends`
- `GET /api/intel/analytics`
- `GET /api/intel/stats/{collection}`

---

## Endpoints

### 1. Submit Article from Scraper

**Endpoint:** `POST /api/intel/scraper/submit`

**Purpose:** Receive articles from `bali-intel-scraper` pipeline and save to staging area.

**Authentication:** Required (Internal API Key)

**Request Body:**

```json
{
  "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
  "content": "The Indonesian government announced...",
  "source_url": "https://jakartapost.com/article",
  "source_name": "Jakarta Post",
  "category": "immigration",
  "relevance_score": 85,
  "published_at": "2026-01-24T10:00:00Z",
  "extraction_method": "intel_pipeline",
  "tier": "T2",
  "cover_image": "https://example.com/image.jpg"
}
```

**Parameters:**

| Field                | Type   | Required | Description                                      |
| -------------------- | ------ | -------- | ------------------------------------------------ |
| `title`              | string | Yes      | Article title (min 1 char)                       |
| `content`            | string | Yes      | Article content (min 1 char)                     |
| `source_url`         | string | Yes      | Original article URL                             |
| `source_name`        | string | Yes      | Source name (e.g., "Jakarta Post")               |
| `category`           | string | Yes      | Category: `immigration`, `business`, `tax`, etc  |
| `relevance_score`    | int    | Yes      | Score 0-100 from LLAMA scorer                    |
| `published_at`       | string | No       | ISO timestamp                                    |
| `extraction_method`  | string | No       | Default: `intel_pipeline`                        |
| `tier`               | string | No       | Tier: `T1`, `T2`, `T3` (default: `T2`)           |
| `cover_image`        | string | No       | Cover image URL/path (legacy)                    |
| `cover_image_base64` | string | No       | Cover image as base64 (uploaded to Google Drive) |

**New fields in staging JSON when `cover_image_base64` is provided:**

| Field                 | Description                                       |
| --------------------- | ------------------------------------------------- |
| `image_drive_file_id` | Google Drive file ID for the uploaded cover image |
| `image_drive_url`     | Google Drive view URL for the cover image         |

**Response (Success):**

```json
{
  "success": true,
  "message": "Article saved to visa staging",
  "item_id": "65708874ed4d",
  "intel_type": "visa",
  "staging_path": "data/staging/visa/65708874ed4d.json",
  "duplicate": false
}
```

**Response (Duplicate):**

```json
{
  "success": true,
  "message": "Article already exists in staging",
  "item_id": "65708874ed4d",
  "intel_type": "visa",
  "duplicate": true
}
```

**HTTP Status Codes:**

- `200 OK` - Article saved or duplicate detected
- `500 Internal Server Error` - Server error

**Classification Logic:**

The backend automatically classifies articles as `visa` or `news` based on:

- Category field
- Title keywords
- Content analysis

---

### 2. List Pending Items

**Endpoint:** `GET /api/intel/staging/pending`

**Purpose:** List all items pending approval in staging area.

**Authentication:** Not required (public endpoint)

**Query Parameters:**

| Parameter     | Type   | Required | Description                                               |
| ------------- | ------ | -------- | --------------------------------------------------------- |
| `type`        | string | No       | Filter by type: `visa`, `news`, or `all` (default: `all`) |
| `filter_type` | string | No       | Additional filter type                                    |
| `sort_type`   | string | No       | Sort order                                                |
| `search`      | string | No       | Search query                                              |

**Response:**

```json
{
  "items": [
    {
      "item_id": "65708874ed4d",
      "title": "Indonesia Extends Digital Nomad Visa",
      "category": "immigration",
      "relevance_score": 85,
      "source_name": "Jakarta Post",
      "source_url": "https://example.com/article",
      "intel_type": "visa",
      "status": "pending",
      "detected_at": "2026-01-24T10:00:00Z"
    }
  ],
  "total": 1,
  "visa_count": 1,
  "news_count": 0
}
```

---

### 3. Preview Staging Item

**Endpoint:** `GET /api/intel/staging/preview/{type}/{item_id}`

**Purpose:** Get full content of a staging item for preview.

**Authentication:** Not required (public endpoint)

**Path Parameters:**

| Parameter | Type   | Description                  |
| --------- | ------ | ---------------------------- |
| `type`    | string | Intel type: `visa` or `news` |
| `item_id` | string | Item ID                      |

**Response:**

```json
{
  "item_id": "65708874ed4d",
  "title": "Indonesia Extends Digital Nomad Visa",
  "content": "Full article content...",
  "source_url": "https://example.com/article",
  "source_name": "Jakarta Post",
  "category": "immigration",
  "relevance_score": 85,
  "intel_type": "visa",
  "status": "pending",
  "cover_image": "https://example.com/image.jpg",
  "seo_metadata": {
    "title": "...",
    "keywords": [...],
    "faq_items": [...]
  }
}
```

**HTTP Status Codes:**

- `200 OK` - Item found
- `404 Not Found` - Item not found

---

### 4. Approve Staging Item

**Endpoint:** `POST /api/intel/staging/approve/{type}/{item_id}`

**Purpose:** Initiate approval process by sending Telegram notification to team.

**Authentication:** Required (Internal API Key)

**Path Parameters:**

| Parameter | Type   | Description                  |
| --------- | ------ | ---------------------------- |
| `type`    | string | Intel type: `visa` or `news` |
| `item_id` | string | Item ID                      |

**Request Body (Optional):**

```json
{
  "enriched_data": {
    "headline": "...",
    "facts": "...",
    "bali_zero_take": {...}
  },
  "image_path": "/path/to/image.jpg"
}
```

**Response:**

```json
{
  "success": true,
  "message": "Approval voting initiated. Team notified via Telegram.",
  "id": "65708874ed4d",
  "voting_status": "pending"
}
```

**Note:** This endpoint triggers Telegram voting. Actual publishing happens when team reaches majority (2/3) via Telegram callback.

---

### 5. Reject Staging Item

**Endpoint:** `POST /api/intel/staging/reject/{type}/{item_id}`

**Purpose:** Reject item and move to archive.

**Authentication:** Not required (public endpoint)

**Path Parameters:**

| Parameter | Type   | Description                  |
| --------- | ------ | ---------------------------- |
| `type`    | string | Intel type: `visa` or `news` |
| `item_id` | string | Item ID                      |

**Response:**

```json
{
  "success": true,
  "message": "Item rejected and archived",
  "id": "65708874ed4d"
}
```

---

### 6. Publish Staging Item

**Endpoint:** `POST /api/intel/staging/publish/{type}/{item_id}`

**Purpose:** Publish approved item to Qdrant knowledge base and register in anti-duplicate system.

**Authentication:** Not required (public endpoint)

**Path Parameters:**

| Parameter | Type   | Description                  |
| --------- | ------ | ---------------------------- |
| `type`    | string | Intel type: `visa` or `news` |
| `item_id` | string | Item ID                      |

**Response:**

```json
{
  "success": true,
  "message": "Article published successfully",
  "id": "65708874ed4d",
  "title": "Indonesia Extends Digital Nomad Visa",
  "published_url": "https://balizero.com/immigration/65708874ed4d",
  "published_at": "2026-01-24T10:30:00Z",
  "collection": "visa_oracle"
}
```

**What happens:**

1. If `image_drive_file_id` exists: downloads cover image from Google Drive
2. Generates MDX file from enriched content
3. If `position` specified: updates `homepage-layout.json` (hero_main, hero_2-5, insight_1-3)
4. Atomic Git commit: MDX + cover image + homepage-layout.json
5. Pushes to GitHub (triggers Vercel auto-deploy)
6. Ingests article to Qdrant (knowledge base)
7. Registers article in anti-duplicate system
8. Archives to `data/staging/{type}/archived/approved/`

**Collections:**

- `visa` → `visa_oracle`
- `news` → `bali_intel_bali_news`

---

### 7. Bulk Approve Items

**Endpoint:** `POST /api/intel/staging/bulk-approve/{type}`

**Purpose:** Bulk approve multiple items.

**Authentication:** Not required (public endpoint)

**Path Parameters:**

| Parameter | Type   | Description                  |
| --------- | ------ | ---------------------------- |
| `type`    | string | Intel type: `visa` or `news` |

**Request Body:**

```json
["65708874ed4d", "65708874ed4e", "65708874ed4f"]
```

**Response:**

```json
{
  "success": 2,
  "failed": 1,
  "errors": ["65708874ed4f: not found"]
}
```

---

### 8. Bulk Reject Items

**Endpoint:** `POST /api/intel/staging/bulk-reject/{type}`

**Purpose:** Bulk reject multiple items.

**Authentication:** Not required (public endpoint)

**Path Parameters:**

| Parameter | Type   | Description                  |
| --------- | ------ | ---------------------------- |
| `type`    | string | Intel type: `visa` or `news` |

**Request Body:**

```json
["65708874ed4d", "65708874ed4e"]
```

**Response:**

```json
{
  "success": 2,
  "failed": 0,
  "errors": []
}
```

---

### 9. Search Intel

**Endpoint:** `POST /api/intel/search`

**Purpose:** Semantic search across intel collections.

**Authentication:** Not required (public endpoint)

**Request Body:**

```json
{
  "query": "digital nomad visa",
  "category": "immigration",
  "date_range": "last_7_days",
  "tier": ["T1", "T2", "T3"],
  "impact_level": "high",
  "limit": 20
}
```

**Parameters:**

| Field          | Type     | Required | Description                                                                            |
| -------------- | -------- | -------- | -------------------------------------------------------------------------------------- |
| `query`        | string   | Yes      | Search query                                                                           |
| `category`     | string   | No       | Filter by category                                                                     |
| `date_range`   | string   | No       | `today`, `last_7_days`, `last_30_days`, `last_90_days`, `all` (default: `last_7_days`) |
| `tier`         | string[] | No       | Filter by tier: `T1`, `T2`, `T3` (default: all)                                        |
| `impact_level` | string   | No       | Filter by impact: `critical`, `high`, `medium`, `low`                                  |
| `limit`        | int      | No       | Max results (default: 20)                                                              |

**Response:**

```json
{
  "results": [
    {
      "id": "65708874ed4d",
      "title": "Indonesia Extends Digital Nomad Visa",
      "summary_english": "The Indonesian government announced...",
      "summary_italian": "",
      "source": "Jakarta Post",
      "tier": "T2",
      "published_date": "2026-01-24T10:00:00Z",
      "category": "visa_oracle",
      "impact_level": "high",
      "url": "https://example.com/article",
      "key_changes": "...",
      "action_required": true,
      "deadline_date": "2026-03-01",
      "similarity_score": 0.95
    }
  ],
  "total": 1
}
```

---

### 10. Store Intel

**Endpoint:** `POST /api/intel/store`

**Purpose:** Store intel news item directly in Qdrant (bypass staging).

**Authentication:** Not required (public endpoint)

**Request Body:**

```json
{
  "collection": "visa",
  "id": "65708874ed4d",
  "document": "Article content...",
  "embedding": [0.123, 0.456, ...],
  "metadata": {
    "title": "...",
    "source": "...",
    "category": "..."
  },
  "full_data": {
    "title": "...",
    "content": "...",
    "source_url": "..."
  }
}
```

**Response:**

```json
{
  "success": true,
  "collection": "visa_oracle",
  "id": "65708874ed4d"
}
```

---

### 11. Get System Metrics

**Endpoint:** `GET /api/intel/metrics`

**Purpose:** Get real-time system metrics for System Pulse dashboard.

**Authentication:** Not required (public endpoint)

**Response:**

```json
{
  "agent_status": "active",
  "last_run": "2026-01-24T10:00:00Z",
  "items_processed_today": 15,
  "avg_response_time_ms": 1250,
  "qdrant_health": "healthy",
  "next_scheduled_run": "2026-01-24T14:00:00Z",
  "uptime_percentage": 99.8
}
```

---

### 12. Get Critical Items

**Endpoint:** `GET /api/intel/critical`

**Purpose:** Get critical impact items.

**Authentication:** Not required (public endpoint)

**Query Parameters:**

| Parameter  | Type   | Required | Description                    |
| ---------- | ------ | -------- | ------------------------------ |
| `category` | string | No       | Filter by category             |
| `days`     | int    | No       | Days to look back (default: 5) |

**Response:**

```json
{
  "items": [
    {
      "id": "65708874ed4d",
      "title": "Critical Visa Regulation Change",
      "source": "Jakarta Post",
      "tier": "T1",
      "published_date": "2026-01-24T10:00:00Z",
      "category": "visa_oracle",
      "url": "https://example.com/article",
      "action_required": true,
      "deadline_date": "2026-02-01"
    }
  ],
  "count": 1
}
```

---

### 13. Get Trends

**Endpoint:** `GET /api/intel/trends`

**Purpose:** Get trending topics and keywords.

**Authentication:** Not required (public endpoint)

**Query Parameters:**

| Parameter  | Type   | Required | Description                     |
| ---------- | ------ | -------- | ------------------------------- |
| `category` | string | No       | Filter by category              |
| `_days`    | int    | No       | Days for analysis (default: 30) |

**Response:**

```json
{
  "trends": [
    {
      "collection": "visa",
      "total_items": 150
    }
  ],
  "top_topics": []
}
```

---

### 14. Get Intelligence Analytics

**Endpoint:** `GET /api/intel/analytics`

**Purpose:** Get historical analytics and trends for Intelligence Center.

**Authentication:** Not required (public endpoint)

**Query Parameters:**

| Parameter | Type | Required | Description                     |
| --------- | ---- | -------- | ------------------------------- |
| `days`    | int  | No       | Days for analysis (default: 30) |

**Response:**

```json
{
  "total_items": 150,
  "visa_count": 80,
  "news_count": 70,
  "pending_count": 5,
  "approved_today": 3,
  "rejected_today": 1,
  "trends": {...}
}
```

---

### 15. Get Collection Stats

**Endpoint:** `GET /api/intel/stats/{collection}`

**Purpose:** Get statistics for a specific intel collection.

**Authentication:** Not required (public endpoint)

**Path Parameters:**

| Parameter    | Type   | Description                           |
| ------------ | ------ | ------------------------------------- |
| `collection` | string | Collection name: `visa`, `news`, etc. |

**Response:**

```json
{
  "collection_name": "visa_oracle",
  "total_documents": 150,
  "last_updated": "2026-01-24T10:00:00Z"
}
```

---

## Error Handling

### Common Error Scenarios

#### 1. Duplicate Article

**Response:**

```json
{
  "success": true,
  "message": "Article already exists in staging",
  "duplicate": true
}
```

**Status Code:** `200 OK`

#### 2. Item Not Found

**Response:**

```http
HTTP 404 Not Found
{
  "detail": "Item not found"
}
```

#### 3. Invalid Collection

**Response:**

```http
HTTP 400 Bad Request
{
  "detail": "Invalid collection: invalid_name"
}
```

#### 4. Server Error

**Response:**

```http
HTTP 500 Internal Server Error
{
  "detail": "Failed to submit article from scraper: <error message>"
}
```

---

## Staging File Structure

Articles are stored in JSON files:

```
data/staging/
├── visa/
│   ├── {item_id}.json          # Pending items
│   └── archived/
│       ├── approved/
│       │   └── {item_id}.json  # Approved items
│       └── rejected/
│           └── {item_id}.json  # Rejected items
└── news/
    ├── {item_id}.json
    └── archived/
        ├── approved/
        └── rejected/
```

**Staging Item Format:**

```json
{
  "item_id": "65708874ed4d",
  "title": "...",
  "content": "...",
  "source_url": "...",
  "source_name": "...",
  "category": "...",
  "relevance_score": 85,
  "intel_type": "visa",
  "status": "pending",
  "detection_type": "scraper_auto",
  "detected_at": "2026-01-24T10:00:00Z",
  "cover_image": "...",
  "seo_metadata": {...}
}
```

---

## Integration with Intel Scraper

The Intel Router receives articles from the scraper pipeline:

```python
# In intel_pipeline.py
backend_url = os.getenv("BACKEND_API_URL", "https://nuzantara-rag.fly.dev")
endpoint = f"{backend_url}/api/intel/scraper/submit"

payload = {
    "title": article.title,
    "content": enriched_content,
    "source_url": article.url,
    "source_name": article.source,
    "category": article.final_category,
    "relevance_score": article.llama_score,
    "published_at": article.published_at,
    "extraction_method": "intel_pipeline",
    "tier": "T2",
    "cover_image": enriched.cover_image,
    "preview_url": preview_url,  # For E-E-A-T review
    "seo_metadata": article.seo_metadata
}

async with httpx.AsyncClient() as client:
    response = await client.post(endpoint, json=payload, headers=headers)
```

---

## Prometheus Metrics

The router exposes Prometheus metrics:

```
# Counters
intel_articles_submitted_total{scraper_type, intel_type, tier}
intel_articles_duplicates_total{intel_type}
intel_items_approved_total{intel_type}
intel_items_rejected_total{intel_type}
intel_user_actions_total{intel_type, action}
intel_bulk_operations_total{intel_type, operation}

# Histograms
intel_scraper_latency_seconds{scraper_type}
intel_bulk_operation_items{intel_type, operation}
```

---

## Rate Limits

**Current Limits:**

- No rate limiting implemented (internal API)
- Recommended: 100 requests/minute per scraper instance

---

## Best Practices

### 1. Error Handling

**DO:**

- ✅ Check `duplicate` field in response
- ✅ Handle 404 errors gracefully
- ✅ Retry on 500 errors with exponential backoff

**DON'T:**

- ❌ Ignore duplicate responses
- ❌ Submit same article multiple times
- ❌ Submit without checking staging status first

### 2. Bulk Operations

**DO:**

- ✅ Use bulk endpoints for multiple items
- ✅ Check `success` and `failed` counts
- ✅ Review `errors` array for failures

**DON'T:**

- ❌ Submit bulk requests > 100 items
- ❌ Ignore partial failures

### 3. Search Queries

**DO:**

- ✅ Use specific queries (not generic)
- ✅ Filter by category when possible
- ✅ Use date ranges to limit results

**DON'T:**

- ❌ Use very broad queries (> 1000 results)
- ❌ Search without date filters

---

## Development

### Local Testing

**Prerequisites:**

```bash
cd apps/backend-rag
source .venv/bin/activate
export NUZANTARA_API_KEY="your-internal-api-key"
```

**Test submit:**

```bash
curl -X POST http://localhost:8080/api/intel/scraper/submit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "title": "Test Article",
    "content": "Test content...",
    "source_url": "https://example.com",
    "source_name": "Test Source",
    "category": "immigration",
    "relevance_score": 85
  }'
```

**Test search:**

```bash
curl -X POST http://localhost:8080/api/intel/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "visa",
    "date_range": "last_7_days",
    "limit": 10
  }'
```

---

## Deployment

### Environment Variables

**Required:**

```bash
QDRANT_URL=https://nuzantara-qdrant.fly.dev
QDRANT_API_KEY=your_qdrant_key
OPENAI_API_KEY=your_openai_key  # For search embeddings
NUZANTARA_API_KEY=your_internal_key  # For scraper authentication
```

**Set secrets:**

```bash
fly secrets set QDRANT_API_KEY="..." -a nuzantara-rag
fly secrets set OPENAI_API_KEY="..." -a nuzantara-rag
fly secrets set NUZANTARA_API_KEY="..." -a nuzantara-rag
```

---

## Changelog

### v2.0 (2026-03-07)

**Added:**

- `cover_image_base64` field on submit endpoint (Google Drive upload)
- `image_drive_file_id` and `image_drive_url` in staging data
- Publish endpoint now generates MDX, commits to GitHub, triggers Vercel deploy
- Homepage position control (`homepage-layout.json`) with 8 named positions
- Cover image download from Drive at publish time
- Conditional MDX sections (empty Bali Zero Take/Next Steps omitted)

**See also:** `docs/INTEL_PIPELINE_COMPLETE.md` for full system documentation.

### v1.0 (2026-01-24)

**Added:**

- Complete API documentation for Intel Router
- All 15 endpoints documented
- Integration guide with Intel Scraper
- Error handling examples
- Prometheus metrics documentation

---

**Last Updated:** 2026-03-07
**Maintained by:** Bali Zero AI Team
**API Version:** 2.0
