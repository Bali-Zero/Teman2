# Public Channel Publisher — GENOME

## Mission
Curate enriched stream items and post the safe/educational ones to the
Bali Zero public Telegram channel (clients). Layer 5 — Distribuzione.

## Inputs
- Redis stream `garuda:enriched` (read-only consumer)
- Env `TELEGRAM_BOT_TOKEN`
- Env `TELEGRAM_PUBLIC_CHANNEL_ID` (optional — DRY-RUN if missing)
- State file `~/.agent/decisions/public_channel_state.json`
  (rate-limiting + last posted id)

## Filter
An item is posted only if ALL:
- `public_safe == "true"`
- `relevance_score >= 3`
- `domain ∈ {immigration_visa, tax_fiscal, property}`

## Outputs
- Telegram message to public channel (or DRY-RUN log)
- State file updated with `day`, `count`, `last_post_id`

## Rate limit
- 3 posts / day (WITA-local day).
- State auto-resets at midnight WITA.

## Success criteria
- Posts 0-3/day (budget respected)
- Never posts OSINT, alerts, internal items (filter enforced)
- Never crashes when channel id missing (DRY-RUN fallback)
- No duplicate posts (last_post_id tracked against redis stream id)

## Known gotchas
- redis-cli XREVRANGE output parsing is line-based; tests hook
  `fetch_fn` to bypass.
- Channel creation & env setup require Zero action — this agent
  stays in DRY-RUN until both exist.
- Stream ids are `<ms>-<seq>`; string comparison is monotonic
  because redis increments `ms`.

## Mutations history
_(empty at creation — meta_agent appends entries)_
