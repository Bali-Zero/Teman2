# kemkumham_harvester — GENOME

## Mission

Monitor Kementerian Hukum dan HAM (Ministry of Law & Human Rights)
news feed for legal regulation changes relevant to Indonesian
business operations and expat law (PERPPU, PP, Permenkumham).
Publish fresh items to `garuda:osint`.

## Inputs

- Landing: `https://www.kemenkumham.go.id/berita`
- Allow prefixes: `https://www.kemenkumham.go.id/berita/`,
  `https://kemenkumham.go.id/berita/`.

## Outputs

- Redis stream `garuda:osint`
- Fields: `title`, `url`, `source=kemenkumham.go.id`,
  `source_type=osint_goid`, `source_agent=kemkumham_harvester`,
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
- Graceful `case_not_resolved` on structure drift — insight message.

## Escalation Rules

- 3 consecutive failures → meta-agent review.
- Domain migration (`kemkumham.go.id` → `kemenkumham.go.id` happened
  2024) — curl `-L` follows redirect; if a future migration breaks the
  allow prefix, meta-agent patches GENOME after Zero review.

## Known gotchas

- Legacy domain `kemkumham.go.id` still in public docs — always 301s
  to `kemenkumham.go.id`. Allow prefix is for the canonical domain.
- News items sometimes in PDF (downloadable). We only grab the HTML
  anchor URL/title — downstream consumers decide whether to fetch
  the PDF body.

## Mutations history

_(empty — meta_agent will append entries)_
