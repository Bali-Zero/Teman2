# Weekly Digest Agent — GENOME

## Mission
Every Sunday 08:00 WITA, aggregate last-7-days `garuda:enriched` items,
ask Claude CLI for a cross-domain strategic digest (top 3 trends,
risks, opportunities, ≤500 words), send to Zero via Telegram.

## Inputs
- Redis stream `garuda:enriched` (XREVRANGE, last ~1000 items)
- Claude CLI (multi-token fallback via `CLAUDE_CODE_OAUTH_TOKEN_{1,2,3}`)

## Outputs
- Telegram message to Zero
- Redis stream `garuda:digest`
- KB entry type `weekly_digest`

## Success criteria
- One digest/week on Sunday 08:00 WITA
- Uses real titles/URLs from stream, never fabricates
- On Claude CLI failure → fallback: top-10 raw list with scores

## Known gotchas
- Reuses `_xrevrange` + `_send_telegram` from daily_briefing_agent —
  any fix there applies here.
- Claude CLI timeout 120s. Multi-token fallback: 3 tokens × 120s =
  up to 6 min worst case. LaunchAgent has no timeout override, that's
  acceptable for a weekly job.
- 1000-item window is intentional overshoot — XREVRANGE is cheap, and
  the 7-day filter is applied in Python after the fact.

## Mutations history
_(meta_agent appends here)_
