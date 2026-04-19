# bkpm_harvester — GENOME

## Mission

Monitor Indonesia's Ministry of Investment / Badan Koordinasi
Penanaman Modal press releases for PMA / investment regulation
updates. Publish fresh items to `garuda:osint`.

## Inputs

- Landing: `https://www.bkpm.go.id/id/publikasi/siaran-pers`
- Allow prefixes: `https://www.bkpm.go.id/id/publikasi/`,
  `https://bkpm.go.id/id/publikasi/`.

## Outputs

- Redis stream `garuda:osint`
- Fields: `title`, `url`, `source=bkpm.go.id`,
  `source_type=osint_goid`, `source_agent=bkpm_harvester`,
  `content=""`, `agent`, `timestamp`.

## Constraints

- Rate limit: 1 req / 2s (shared, `tools/goid_tools.py`).
- UA: `Mata-Garuda/0.1 (Intelligence research; contact: zero@balizero.com)`.
- Timeout: 15s.
- Max 10 items per run.
- MUST terminate with `case_resolved` / `case_not_resolved`.
- OSINT blindato — publish ONLY to `garuda:osint`.
- CLI-only: curl subprocess.

## Success criteria

- `published > 0` on a normal operating day (BKPM publishes 2-5/week).
- Drift tolerant: empty extraction returns `case_not_resolved`
  with "structure drift" insight for meta-agent review.

## Escalation Rules

- 3 consecutive failures → meta-agent review of allow prefixes.
- HTTP >= 500 sustained >24h → TG alert (site likely down).

## Known gotchas

- BKPM occasionally returns 403 for bare curl when UA string is empty —
  shared tool always sends the MG UA; if site later requires browser
  UA, update the shared helper, not this agent.
- Press-release index pagination is JS — we harvest first page only
  (top 10 latest). Acceptable: cron runs daily, latest 10 covers 24h
  easily.

## Mutations history

_(empty — meta_agent will append entries)_
