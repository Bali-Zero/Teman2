# intel_scraper_bridge — GENOME

## Mission

Bridge the 609 curated sources maintained by `apps/bali-intel-scraper/`
into Mata Garuda's Layer 1 stream `garuda:raw`. Read-only consumer of the
scraper's on-disk output; never mutates it, never re-crawls.

## Inputs

- File: `apps/bali-intel-scraper/data/published_articles.json`
- Env override: `BALI_INTEL_SCRAPER_DATA_DIR` (absolute path) takes
  precedence when set.
- Schema expected: `{"articles": [{"url": str, "title": str,
  "published_at": ISO8601, "source"?: str}, ...]}`.

## Outputs

- Redis stream `garuda:raw` (published via `workers.base_worker.stream_publish`)
- Fields per message: `title`, `url`, `source`, `source_type=intel_scraper`,
  `source_agent=intel_scraper_bridge`, `content` (empty, scraper didn't
  fetch bodies), `agent=intel_scraper_bridge`, `timestamp` (article
  `published_at`).

## Constraints

- Window: last 24h (`window_hours=24` default); configurable per invocation.
- Max 50 items per run to avoid flooding downstream consumers.
- MUST terminate with `case_resolved` (>=1 published) or
  `case_not_resolved` (file missing, no recent items, or all publishes
  failed).
- NEVER export data outside Mata Garuda (OSINT blindato).
- NEVER write to the scraper's data dir.
- CLI-only LLM — no HTTP API imports.

## Success criteria

- `published > 0` on healthy day.
- No duplicates on repeat runs within the same `window_hours` — handled
  downstream by Layer 2 dedup (by url hash). This agent trusts that.
- `failures / (published + failures) < 0.1` over a week.

## Cron Schedule

- Suggested: 06:30 WITA daily, after bali-intel-scraper's 03:00 batch.
- Plist: `infra/launchagents/com.matagaruda.intel-bridge.daily.plist`.
- Manual: `python -m mata_garuda.cli run intel_scraper_bridge`.

## Escalation Rules

- 3 consecutive runs with `published==0` and file present → meta-agent
  review (scraper upstream likely broken).
- File missing for >48h → TG alert to Zero (scraper cron dead).
- `source_type=intel_scraper` missing in downstream stream → meta-agent
  inspection of field drift.

## Known gotchas

- `published_articles.json` is rewritten atomically by the scraper —
  reads during the rare mid-write window can hit empty/partial files;
  we return `[]` gracefully and wait for next run.
- `published_at` is lexicographically comparable because it's ISO-8601
  with seconds precision. Do NOT switch to locale-formatted dates.
- Items without `published_at` are skipped (prevents re-publish every
  run). Scraper is expected to always stamp this field.

## Mutations history

_(empty — meta_agent will append entries)_
