# Publish-to-MDX Bridge with Homepage Position Control

**Date:** 2026-03-07
**Status:** Implemented and Deployed (2026-03-07)
**Author:** Bali Zero AI Team

## Problem

When articles are approved in the newsroom (`/intelligence/news-room`), they exist only as staging JSON files. They never reach the frontend because:

1. No MDX file is generated for the `apps/mouth/src/content/articles/` directory
2. No record is inserted into the `news_items` PostgreSQL table
3. The homepage (`NewsPageClient.tsx`) uses hardcoded slugs for hero/insight positions

## Solution: Option A — Newsroom UI Dropdown

Add a position dropdown to the newsroom publish flow. When an article is approved:

1. Backend generates an `.mdx` file from the enriched content
2. Backend updates `homepage-layout.json` if a position was selected
3. Frontend reads positions from `homepage-layout.json` instead of hardcoded slugs

## Architecture

### 1. Homepage Layout Config

**File:** `apps/mouth/src/content/homepage-layout.json`

```json
{
  "hero_main": "slow-paralysis-kbli-2025",
  "hero_2": "beginners-guide-kbli-2025",
  "hero_3": "kbli-2025-oss-transition-update",
  "hero_4": "bali-property-foreign-ownership-2025",
  "hero_5": "digital-nomad-visa-indonesia-2025",
  "insight_1": "indonesia-tax-changes-2025",
  "insight_2": "bali-coworking-spaces-guide",
  "insight_3": "indonesia-golden-visa-program"
}
```

- 8 named positions (hero_main, hero_2–5, insight_1–3)
- Values are article slugs
- Omitted positions fall back to chronological
- When a position is taken, previous occupant drops to chronological (auto-demotion)

### 2. Backend Endpoint

**`POST /api/news/publish-to-site`**

Request:

```json
{
  "item_id": "abc123",
  "position": "hero_main" // optional, default: "latest"
}
```

Actions:

1. Read enriched content from staging JSON
2. Generate `.mdx` file with proper frontmatter (title, slug, category, tags, excerpt, etc.)
3. Write to `apps/mouth/src/content/articles/{category}/{slug}.mdx`
4. If position != "latest", update `homepage-layout.json`
5. Insert/upsert into `news_items` table with `status=approved`
6. Commit + push to GitHub (triggers Vercel deploy)

Response:

```json
{
  "success": true,
  "slug": "article-slug",
  "mdx_path": "src/content/articles/business/article-slug.mdx",
  "position": "hero_main",
  "deploy_triggered": true
}
```

### 3. Frontend Changes

**`NewsPageClient.tsx`** — Replace hardcoded slugs:

```typescript
import layout from "@/content/homepage-layout.json";

const mainNews1 = articles.find((a) => a.slug === layout.hero_main);
const mainNews2 = articles.find((a) => a.slug === layout.hero_2);
// ... etc
```

Fallback: if a slug from layout.json doesn't match any article, skip that position and fill from chronological.

### 4. Newsroom UI

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/` (existing)

Add a dropdown when publishing:

- **Position options:** Hero Main, Hero 2–5, Insight 1–3, Latest (chronological)
- Shows current occupant of each position (so user knows what gets demoted)
- Default: "Latest"

## Positions

| Position    | UI Label           | Homepage Location           |
| ----------- | ------------------ | --------------------------- |
| `hero_main` | Hero Main (Large)  | Main collage card, top-left |
| `hero_2`    | Hero 2             | Collage card, top-right     |
| `hero_3`    | Hero 3             | Collage card, bottom-left   |
| `hero_4`    | Hero 4             | Collage card, bottom-center |
| `hero_5`    | Hero 5             | Collage card, bottom-right  |
| `insight_1` | Featured Insight 1 | Below hero, left            |
| `insight_2` | Featured Insight 2 | Below hero, center          |
| `insight_3` | Featured Insight 3 | Below hero, right           |
| `latest`    | Latest (default)   | Chronological feed          |

## MDX Generation Template

```markdown
---
title: "{title}"
slug: "{slug}"
category: "{category}"
excerpt: "{summary or ai_summary}"
coverImage: "/static/insights/{category}/{slug}.jpg"
coverImageAlt: "{title}"
publishedAt: "{ISO date}"
tags: [{ ai_tags }]
featured: { true if hero position }
trending: false
aiGenerated: true
author:
  name: "Zantara AI"
  avatar: "/static/zantara-avatar.png"
  role: "AI Research Assistant"
  isAI: true
readingTime: { calculated }
---

{content body}
```

## Data Flow

```
Newsroom UI → POST /api/news/publish-to-site
  → Read staging JSON
  → Generate .mdx file
  → Update homepage-layout.json (if positioned)
  → Upsert news_items row
  → Git commit + push
  → Vercel auto-deploy
  → Article live on balizero.com
```

## Error Handling

- If staging file not found → 404 with clear message
- If GitHub push fails → return error, MDX still written locally
- If position already taken → auto-demote previous, proceed
- If MDX generation fails (missing fields) → return validation errors

## Implementation Notes (2026-03-07)

**Cover image pipeline added** (not in original design):

- Scraper sends `cover_image_base64` in submit payload
- Backend uploads to Google Drive `Intel_Images` folder
- At publish time, downloads from Drive and commits alongside MDX
- Drive folder ID: `12UhfVLsNJgHSqXQP3vFbWk3THpDeU-2-`

**Commits:**

- `341cb41d7` - fix: copy-paste bug in our_advice extraction
- `e7e5b03` - feat: publish-to-MDX bridge with homepage position control
- `742bd28e1` - feat: cover image pipeline via Google Drive

**Full documentation:** `docs/INTEL_PIPELINE_COMPLETE.md`

## Out of Scope

- Drag-and-drop position reordering (future)
- Scheduled publishing (future)
- Multi-language MDX generation (`.id.mdx` translations handled separately)
