# Daily Briefing Agent — GENOME

## Mission
Every morning 07:00 WITA, aggregate last-24h `garuda:enriched` items by
domain, pick top 5 per domain by relevance_score, render a Markdown
briefing, and send it to Zero via Telegram.

## Inputs
- Redis stream `garuda:enriched` (XREVRANGE, last ~200 items)
- (optional) Claude CLI for per-item TL;DR (max 2 lines)

## Outputs
- Telegram message to Zero (chat `1125336968`), chunked if >3800 chars
- Redis stream `garuda:digest` (briefing body, for observability)
- KB entry type `briefing`

## Success criteria
- One briefing sent per day, 07:00 WITA
- All domains with >0 items appear in the briefing
- Items ordered by `relevance_score` desc within each domain
- On empty window: "quiet day" briefing still sent (positive confirmation)

## Known gotchas
- Enriched items must carry a parseable timestamp in one of:
  `normalized_at`, `timestamp`, `alert_time`, `created_at`. Items
  without any timestamp are INCLUDED (defensive — better over-include
  than drop).
- Claude CLI is best-effort. Rate-limited / missing token → fallback
  to first-line-of-content TL;DR.
- TG sendMessage hard limit 4096; we chunk at 3800 for safety margin.
- `_xrevrange` uses the same flat-line redis-cli parser as
  `base_worker._parse_xreadgroup`. redis-cli output format is positional,
  not JSON.

## Mutations history
_(meta_agent appends here)_
