# tavily_research_agent — GENOME

## Mission

Run a curated pool of research-focused queries against Tavily
(https://tavily.com) on a schedule and publish each hit to
`garuda:raw`. Complements Exa by giving broader web coverage with
Tavily's own ranking.

## Inputs

- Env: `TAVILY_API_KEY` (required; agent case_not_resolved if missing).
- Query pool (hardcoded in `DEFAULT_QUERIES`, rotatable per run):
  - Indonesia business regulations 2026
  - Bali property law foreigners
  - Indonesia digital nomad visa
  - Jakarta foreign investment incentives
  - Indonesia company setup PT PMA requirements

## Outputs

- Redis stream `garuda:raw`
- Fields: `title`, `url`, `source=tavily.com`, `source_type=tavily`,
  `source_agent=tavily_research_agent`, `content` (up to 500 chars),
  `agent`, `timestamp`, `query`.

## Constraints

- Retrieval-only (Legge 1): Tavily API used for search only.
- Max 10 results per query.
- Timeout: 20s per query.
- MUST terminate with `case_resolved` / `case_not_resolved`.
- CLI-only: curl subprocess.

## Success criteria

- `published > 0` per run under normal conditions.
- Graceful handling when `TAVILY_API_KEY` missing.

## Escalation Rules

- 3 consecutive `case_not_resolved` with HTTP 401/403 → TG alert (key
  expired).
- Query pool stale (no new unique URLs for 7 days) → meta-agent
  suggests rotation.

## Known gotchas

- Tavily returns up to 20 results by default; we cap at 10 locally
  for stream volume control.
- Some hits lack `content` — default to empty.

## Mutations history

_(empty — meta_agent will append entries)_
