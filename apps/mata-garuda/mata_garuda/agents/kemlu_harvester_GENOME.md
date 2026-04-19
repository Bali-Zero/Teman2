# kemlu_harvester — GENOME

## Mission

Monitor Indonesia's Ministry of Foreign Affairs (Kementerian Luar
Negeri) news feed for treaty updates, bilateral agreements, and
diplomatic announcements that affect visas, business travel, and
expat policies. Publish fresh items to `garuda:osint`.

## Inputs

- Landing: `https://kemlu.go.id/portal/id/list/berita`
- Allow prefixes: `https://kemlu.go.id/portal/id/read/`,
  `https://www.kemlu.go.id/portal/id/read/`.

## Outputs

- Redis stream `garuda:osint`
- Fields: `title`, `url`, `source=kemlu.go.id`,
  `source_type=osint_goid`, `source_agent=kemlu_harvester`,
  `content=""`, `agent`, `timestamp`.

## Constraints

- Rate limit: 1 req / 2s (shared).
- UA: `Mata-Garuda/0.1 (Intelligence research; contact: zero@balizero.com)`.
- Timeout: 15s.
- Max 10 items per run.
- MUST terminate with `case_resolved` / `case_not_resolved`.
- OSINT blindato — publish ONLY to `garuda:osint`.
- CLI-only.

## Success criteria

- `published > 0` on a normal operating day.
- Insight string on empty result for meta-agent to review URL drift.

## Escalation Rules

- 3 consecutive `case_not_resolved` → meta-agent inspection.
- Cert errors / unusual TLS failures → TG alert (foreign ministry
  portals occasionally rotate certs, curl should follow).

## Known gotchas

- URL scheme changed in 2023 from `/read/news/...` to `/read/<slug>`.
  Allow prefix keeps just `/read/` to remain resilient.
- Bahasa Indonesia and English sub-paths (`/id/` vs `/en/`) diverge;
  we take `/id/` as canonical — English version is auto-translated
  downstream.

## Mutations history

_(empty — meta_agent will append entries)_
