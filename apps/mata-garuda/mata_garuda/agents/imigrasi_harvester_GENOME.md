# imigrasi_harvester — GENOME

## Mission

Monitor Indonesia's Directorate General of Immigration (Direktorat
Jenderal Imigrasi) news feed for visa/KITAS/immigration policy shifts.
Publish fresh items to Mata Garuda's OSINT stream.

## Inputs

- Landing: `https://www.imigrasi.go.id/berita/`
- Allow prefixes: `https://www.imigrasi.go.id/berita/`,
  `https://imigrasi.go.id/berita/` (strip www variants).

## Outputs

- Redis stream `garuda:osint`
- Fields: `title`, `url`, `source=imigrasi.go.id`,
  `source_type=osint_goid`, `source_agent=imigrasi_harvester`,
  `content=""`, `agent`, `timestamp`.

## Constraints

- Rate limit: 1 req / 2s per host (shared via `tools/goid_tools.py`).
- UA: `Mata-Garuda/0.1 (Intelligence research; contact: zero@balizero.com)`.
- Timeout: 15s connect + 15s total.
- Max 10 items per run.
- MUST terminate with `case_resolved` / `case_not_resolved`.
- OSINT blindato — publish ONLY to `garuda:osint`, never to any stream,
  log, or file visible outside Mata Garuda.
- CLI-only: uses `curl` subprocess, no httpx/requests.

## Success criteria

- `published > 0` on a normal operating day.
- HTTP 4xx/5xx surfaced as `case_not_resolved` with code, no retry loop.
- No duplicates handled downstream (Layer 2 dedup by URL hash).

## Escalation Rules

- 3 consecutive `case_not_resolved` due to HTTP >= 500 → meta-agent
  inspects UA/path; do NOT auto-apply GENOME changes.
- Structure drift (`no matching links`): meta-agent reviews allow
  prefixes. Log kept in `feedback/imigrasi_harvester.md`.

## Known gotchas

- Site occasionally serves JS-rendered pages; regex extractor works
  because `/berita/` links appear in SSR HTML for the list view. If
  individual article pages ever become JS-only, bodies stay empty —
  fine, we only harvest titles + URLs here.
- `https://` vs `http://`: landing sometimes 301s to www. curl follows
  redirects (`-L`), so fine.

## Mutations history

_(empty — meta_agent will append entries)_
