# exa_search_agent — GENOME

## Mission

Run a curated pool of semantic-search queries against Exa
(https://exa.ai) on a schedule and publish each hit to `garuda:raw`.
Closes the gap where traditional .go.id harvesters miss English-language
press / blog / analyst coverage.

## Inputs

- Env: `EXA_API_KEY` (required; agent case_not_resolved if missing).
- Query pool (hardcoded in `DEFAULT_QUERIES`, rotatable per run):
  - Indonesia visa policy changes 2026
  - Indonesia KITAS permit regulations
  - Bali PMA foreign investment updates
  - Indonesia tax residency foreigners 2026
  - Indonesia property ownership expat

## Outputs

- Redis stream `garuda:raw`
- Fields: `title`, `url`, `source=exa.ai`, `source_type=exa`,
  `source_agent=exa_search_agent`, `content` (up to 500 chars),
  `agent`, `timestamp`, `query`.

## Constraints

- Retrieval-only: Exa API is ok for search (Legge 1), never for LLM
  generation. We only POST /search.
- Max 10 results per query.
- Timeout: 20s per query.
- MUST terminate with `case_resolved` / `case_not_resolved`.
- CLI-only: curl subprocess, no openai-style SDK.

## Success criteria

- `published > 0` per run under normal conditions.
- Graceful handling when `EXA_API_KEY` missing — reason surfaced for
  meta_agent; no crash.

## Escalation Rules

- 3 consecutive `case_not_resolved` with HTTP 401/403 → TG alert (key
  expired or rate-limited).
- Query pool becoming stale (no new unique URLs for 7 days) → meta-agent
  suggests new queries.

## Known gotchas

- Exa paginates with `next_cursor`; we take the first page only
  (10 items). Acceptable for daily cadence.
- Some hits have empty `text` field — we default to empty content.

## Mutations history

_(empty — meta_agent will append entries)_
