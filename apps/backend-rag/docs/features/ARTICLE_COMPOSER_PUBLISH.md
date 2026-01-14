# Article Composer - Auto-Publish Feature

## Overview

The Article Composer enables the marketing team to create articles manually with AI enrichment and auto-publish them to the blog. Articles are committed directly to the GitHub repository, triggering automatic Vercel deployment.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Article Composer Flow                        │
└─────────────────────────────────────────────────────────────────┘

   User Input                  Backend                    Output
   ──────────                  ───────                    ──────
┌──────────────┐         ┌──────────────────┐       ┌──────────────┐
│ Title        │         │ POST /compose    │       │ Enriched     │
│ Content      │────────▶│   Claude API     │──────▶│ Article      │
│ Category     │         │   enrichment     │       │ + Image      │
│ Author       │         └──────────────────┘       │   Prompt     │
└──────────────┘                                    └──────────────┘
                                                           │
┌──────────────┐         ┌──────────────────┐              │
│ Slug         │         │ POST /publish    │              │
│ Cover Image  │────────▶│   GitHub API     │◀─────────────┘
│ Position     │         │   atomic commit  │
│ Category     │         └──────────────────┘
└──────────────┘                │
                                ▼
                    ┌──────────────────────┐
                    │ GitHub Repository    │
                    │  ├── MDX article     │
                    │  └── Cover image     │
                    └──────────────────────┘
                                │
                                ▼ (auto-deploy)
                    ┌──────────────────────┐
                    │ Vercel               │
                    │ balizero.com/...     │
                    └──────────────────────┘
```

## API Endpoints

### POST /api/articles/compose

Enrich raw article content with Claude AI into a BaliZero Executive Brief.

**Request:**
```json
{
  "title": "New Tax Regulation for Expats",
  "content": "The Indonesian government announced...",
  "category": "tax",
  "source_url": "https://example.com/source",
  "author": "Marketing Team"
}
```

**Response:**
```json
{
  "success": true,
  "article": {
    "title": "New Tax Regulation for Expats",
    "headline": "New Tax Rules Could Save Expats 30% on Foreign Income",
    "tldr": {
      "should_worry": "No",
      "what": "Tax reduction for foreign-sourced income",
      "who": "All expats with offshore income",
      "when": "Effective January 2026",
      "risk_level": "Low"
    },
    "facts": "...",
    "bali_zero_take": {
      "hidden_insight": "...",
      "our_analysis": "...",
      "our_advice": "..."
    },
    "next_steps": {
      "expat": ["Step 1", "Step 2"],
      "investor": ["Step 1", "Step 2"]
    },
    "category": "tax",
    "priority": "high",
    "relevance_score": 85,
    "ai_summary": "...",
    "ai_tags": ["tax", "expat", "foreign income"],
    "suggested_components": ["timeline", "checklist"],
    "image_prompt": "Professional editorial cover image...",
    "enriched_at": "2026-01-14T12:00:00Z"
  },
  "api_cost_cents": 3.5
}
```

### GET /api/articles/compose/status

Check if the article composer is properly configured.

**Response:**
```json
{
  "configured": true,
  "api_key_set": true,
  "model": "claude-sonnet-4-20250514",
  "estimated_cost_per_article": "$0.02-0.05"
}
```

### POST /api/articles/publish

Publish an enriched article to GitHub (triggers Vercel auto-deploy).

**Request:**
```json
{
  "article": { /* EnrichedArticle from /compose */ },
  "slug": "new-tax-rules-expats-2026",
  "cover_image_base64": "iVBORw0KGgo...",
  "cover_image_filename": "cover.jpg",
  "position": "mainNews1",
  "category": "tax"
}
```

**Response:**
```json
{
  "success": true,
  "published_url": "https://balizero.com/tax/new-tax-rules-expats-2026",
  "mdx_path": "apps/mouth/src/content/articles/tax/new-tax-rules-expats-2026.mdx",
  "image_path": "apps/mouth/public/static/news/new-tax-rules-expats-2026.jpg",
  "commit_sha": "abc123def456789",
  "position_snippet": "// To feature this article..."
}
```

### GET /api/articles/publish/status

Check if the article publisher is properly configured.

**Response:**
```json
{
  "configured": true,
  "github_owner": "Balizero1987",
  "github_repo": "Teman2",
  "token_set": true
}
```

## Configuration

### Required Environment Variables

```bash
# Anthropic API (for Claude enrichment)
ANTHROPIC_API_KEY=sk-ant-api03-...

# GitHub API (for publishing)
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPO=Teman2
GITHUB_OWNER=Balizero1987
```

### Setting Secrets on Fly.io

```bash
fly secrets set ANTHROPIC_API_KEY=sk-ant-api03-xxx -a nuzantara-rag
fly secrets set GITHUB_TOKEN=ghp_xxx -a nuzantara-rag
fly secrets set GITHUB_REPO=Teman2 -a nuzantara-rag
fly secrets set GITHUB_OWNER=Balizero1987 -a nuzantara-rag
```

## GitHub Token Requirements

Create a Personal Access Token (Classic) with **`repo`** scope:

1. Go to https://github.com/settings/tokens/new
2. Set Note: "Article Composer Publisher"
3. Set Expiration: 30-90 days (remember to rotate!)
4. Select scope: `repo` (Full control of private repositories)
5. Click "Generate token"
6. Copy the `ghp_xxx` token and set as `GITHUB_TOKEN`

## News Page Positions

When publishing, you can specify a featured position:

| Position | Description |
|----------|-------------|
| `mainNews1` | Main News 1 (Large Right) |
| `mainNews2` | Main News 2 (Large Left) |
| `mainNews3` | Main News 3 (Medium Middle) |
| `mainNews4` | Main News 4 (Large Middle) |
| `mainNews5` | Main News 5 (Medium Left) |
| `latestInsights` | Latest Insights (Grid) |
| `none` | No Featured Position |

After publishing, you'll receive a code snippet to manually update `news/page.tsx`.

## Slug Validation Rules

Slugs must:
- Be lowercase letters, numbers, and hyphens only
- Be at least 3 characters
- Be less than 100 characters
- Not already exist in the repository

Examples:
- ✅ `new-tax-rules-2026`
- ✅ `kitas-extension-guide`
- ❌ `New Tax Rules` (uppercase, spaces)
- ❌ `ab` (too short)

## Category Mapping

| Input Category | Output Folder |
|----------------|---------------|
| `immigration` | `/articles/immigration/` |
| `business` | `/articles/business/` |
| `tax` | `/articles/tax/` |
| `tax-legal` | `/articles/tax/` |
| `legal` | `/articles/tax/` |
| `property` | `/articles/property/` |
| `lifestyle` | `/articles/lifestyle/` |
| `tech` | `/articles/tech/` |

## Error Handling

| Error Code | Meaning | Solution |
|------------|---------|----------|
| 400 | Invalid slug format | Fix slug to match validation rules |
| 400 | Invalid base64 image | Re-encode image as valid base64 |
| 409 | Slug already exists | Choose a different slug |
| 413 | Image exceeds 2MB | Compress image below 2MB |
| 500 | GitHub API not configured | Set GITHUB_TOKEN, REPO, OWNER |
| 500 | Anthropic API not configured | Set ANTHROPIC_API_KEY |

## File Structure After Publish

```
apps/mouth/
├── public/
│   └── static/
│       └── news/
│           └── {slug}.{jpg|png|webp}  # Cover image
└── src/
    └── content/
        └── articles/
            └── {category}/
                └── {slug}.mdx          # MDX article
```

## MDX Template

Published articles include:

```yaml
---
title: "{headline}"
slug: "{slug}"
description: "{ai_summary}"
excerpt: "{tldr.what}"
category: "{category}"
tags: [...]
publishedAt: "{date}"
author:
  name: "Zantara AI"
  avatar: "/static/zantara-avatar.png"
  role: "AI Research Assistant"
image:
  src: "/static/news/{slug}.{ext}"
  alt: "{headline}"
featured: false
trending: {priority == 'high'}
readingTime: {calculated}
aiGenerated: true
tableOfContents: true
seo:
  title: "{headline[:60]}"
  description: "{ai_summary[:160]}"
---

## TL;DR
{table with should_worry, risk_level, what, who, when}

## The Facts
{facts}

## Bali Zero Take
### Hidden Insight
{hidden_insight}

### Our Analysis
{our_analysis}

### Our Advice
{our_advice}

## Next Steps
### For Expats
{expat steps}

### For Investors
{investor steps}
```

## Logging

Both the composer and publisher emit structured logs:

### Compose Logs
```
INFO  Composing article: New Tax Regulation...
      {"title": "...", "category": "tax", "content_length": 2500}

INFO  ✅ Article enriched: New Tax Rules Could Save Expats...
      {"headline": "...", "category": "tax", "priority": "high",
       "input_tokens": 1200, "output_tokens": 800, "cost_cents": 3.5,
       "total_elapsed_ms": 4500}
```

### Publish Logs
```
INFO  Publish request received: new-tax-rules-2026
      {"slug": "...", "category": "tax", "position": "mainNews1"}

INFO  Creating atomic commit with 2 files (150.5 KB total)
      {"files": ["image.jpg", "article.mdx"], "branch": "main"}

INFO  ✅ Article published: https://balizero.com/tax/new-tax-rules-2026
      {"slug": "...", "commit_sha": "abc123d", "elapsed_ms": 2300}
```

## Testing

Run unit tests:

```bash
# GitHubPublisher tests
PYTHONPATH=backend pytest tests/unit/services/integrations/test_github_publisher.py -v

# Article Composer router tests
PYTHONPATH=backend pytest tests/unit/app/routers/test_article_composer.py -v
```

## Related Files

| File | Purpose |
|------|---------|
| `backend/app/routers/article_composer.py` | API endpoints |
| `backend/services/integrations/github_publisher.py` | GitHub API service |
| `apps/mouth/src/lib/api/articles.api.ts` | Frontend API client |
| `apps/mouth/src/app/(workspace)/intelligence/article-composer/page.tsx` | UI component |
| `tests/unit/services/integrations/test_github_publisher.py` | Service tests |
| `tests/unit/app/routers/test_article_composer.py` | Router tests |
