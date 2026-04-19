# reddit_listener_agent — GENOME

## Mission

Passive listener on r/bali and r/indonesia new.json public feeds.
Filter on Indonesia-business keywords (visa/KITAS/PMA/immigration/
business/tax/property/investment). Publish hits to `garuda:raw`.

## Inputs

- Subreddits: `bali`, `indonesia`.
- JSON endpoints: `https://www.reddit.com/r/{sub}/new.json?limit=25`.
- UA required by Reddit: `Mata-Garuda/0.1 by /u/zeroai87`.

## Outputs

- Redis stream `garuda:raw`
- Fields: `title`, `url` (reddit permalink), `source=reddit.com/r/{sub}`,
  `source_type=social_reddit`, `source_agent=reddit_listener_agent`,
  `content` (selftext trimmed), `agent`, `timestamp`, `subreddit`.

## Constraints

- Public, read-only: NO login, NO OAuth.
- Timeout: 15s.
- 25 posts / sub / run, post-filtered by keywords.
- MUST terminate with `case_resolved` / `case_not_resolved`.
- CLI-only: curl subprocess.
- Telegram channels require login → explicitly OUT of scope (skip).

## Success criteria

- `published > 0` on a normal day (keyword hits common in r/bali).
- Graceful on HTTP 429 (Reddit rate limit) — `case_not_resolved` with
  HTTP code, no retry.

## Escalation Rules

- 3 consecutive 429s → TG alert (increase UA or back off cadence).
- Keyword list staleness (no hits for 7 days) → meta-agent review.

## Known gotchas

- Reddit sometimes returns 403 for non-browser UA; our UA string is
  accepted per their API docs (`by /u/<username>` form).
- `permalink` is relative; we prefix `https://www.reddit.com`.

## Mutations history

_(empty — meta_agent will append entries)_
