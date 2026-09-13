---
adversarial_review: codex
---

# Live Newsroom Deduplication and Cover Audit — 2026-09-06

## Result

The public Bali Zero newsroom exposed 818 articles before cleanup. The audit found seven exact-title duplicate groups, representing seven redundant articles.

Three inferior backend-generated duplicates were archived through the production news API. The public count then revalidated to 815. Four truncated-slug MDX duplicates are removed by the accompanying frontend change, with permanent redirects to the retained canonical articles. After independent review, merge, and deployment, the expected public count is 811 with zero exact-title duplicate groups.

## Duplicate actions

| Source | Removed or archived | Retained canonical article |
| --- | --- | --- |
| Static MDX | bali-vs-koh-samui-where-your-property-money-actually-works-h | bali-vs-koh-samui-where-your-property-money-actually-works-harder |
| Static MDX | rupiah-under-pressure-what-bank-indonesias-intervention-mean | rupiah-under-pressure-what-bank-indonesias-intervention-means-for-you |
| Static MDX | indonesia-gives-tax-authority-power-to-override-your-interco | indonesia-gives-tax-authority-power-to-override-your-intercompany-prices |
| Static MDX | indonesias-data-law-now-covers-us-transfers-what-expats-and- | indonesias-data-law-now-covers-us-transfers-what-expats-and-businesses-must-know |
| Backend | archived duplicate record | dengue-alert-2026 |
| Backend | archived duplicate record | property-green-zone-alert |
| Backend | archived duplicate record | pajak-hiburan-tax-shock |

The four static duplicate bodies were also checked for textual similarity. Their body cosine similarities ranged from 0.922 to 0.988, confirming that they were duplicate articles rather than related coverage.

## Cover audit

The cover review uses the intended 811-article post-dedup corpus.

| Measure | Count |
| --- | ---: |
| Article cover references | 811 |
| Unique cover URLs | 786 |
| Strictly aligned article covers | 266 (32.8%) |
| Article covers requiring replacement | 545 (67.2%) |
| Broken or undecodable cover files | 9 |
| Reused cover URL groups | 8 groups / 33 article references |
| Exact-byte duplicate assets | 19 groups / 134 URLs |
| Redundant exact-byte files | 115 |

A cover passes only when it has an article-specific editorial concept, cinematic documentary composition, restrained Bali Zero grading, useful negative space, and no generic tourism, airport, corporate, vector, or gradient treatment. It must also decode correctly and be original at both URL and byte level. This is a strict design threshold, not a technical image-presence check.

All 786 unique cover URLs were inspected across 40 contact sheets. The machine inventory found 777 decodable files and nine invalid files containing error responses. URL reuse and SHA-256 equality were evaluated separately so an attractive image could not pass as original when it was reused.

## Batch handoff

The companion JSON stores the exact aligned and replacement slug sets. It is the input manifest for the later low-cost ImageGen prompt and generation batch. Replacement prompts should be written only for the 545 replacement slugs, then generated and applied as one reviewed batch.

## Evidence

- Public inventory endpoint: https://balizero.com/api/blog/articles?limit=10000
- Backend approved feed: https://nuzantara-rag.fly.dev/api/news?status=approved&limit=100
- Brand baseline: Bali Zero brand constitution and editorial-image doctrine
- Machine checks: file decoding, URL reuse, SHA-256 duplicate groups
- Human review: 40 contact sheets covering all 786 unique URLs

## Adversarial review

Reviewer: `codex` (OpenAI Codex CLI, `gpt-6-astra`, reasoning effort xhigh, sandbox
read-only), dispatched via `.claude/scripts/codex-spalla.sh review origin/main` against the
`origin/main`-merged branch (base `origin/main`, 21 files / ~2000 committed diff lines).
Full transcript: `~/logs/codex-spalla/20260913T135535Z-17e59-review-Adversarial-review-for-R1-gate-audit-the.md`
(local log, not committed — path recorded for audit).

**Verdict: LOW**

> Claude propone di eliminare quattro articoli duplicati e le loro 14 traduzioni, aggiungere
> quattro redirect permanenti e registrare l'audit delle copertine e tre archiviazioni backend
> dichiarate.

- **LOW — conteggio previsto ormai datato.** Questo audit (riga 7) prevede ancora 811 articoli
  dopo il deploy, ma il merge con `origin/main` incorpora sei articoli pubblicati l'11 settembre
  e assenti da questo manifest (es. `apps/mouth/src/content/articles/tax-legal/indonesia-spp-tdln-vat-foreign-digital-payments.mdx`).
  Il numero 811 descrive lo snapshot del 6 settembre, non il totale post-merge — va ricalcolato
  prima della verifica live, non usato come conteggio finale.
- **Verifiche superate:** tutti i 18 file duplicati rimossi hanno un gemello canonico ancora
  leggibile dal loader nella lingua corrispondente; i quattro redirect terminano sulle
  destinazioni corrette senza cicli; il parser TypeScript non riporta errori e tutti i redirect
  preesistenti restano nello stesso ordine (`apps/mouth/next.config.ts:223`).
- **Coerenza interna confermata:** 818 − 3 − 4 = 811; i sette gruppi duplicati corrispondono
  esattamente a quattro eliminazioni statiche + tre archiviazioni backend dichiarate. Il
  manifest JSON allegato contiene 266 + 545 slug distinti, senza sovrapposizioni.
- **Limite della verifica:** raggiungibilità HTTP e archiviazioni backend non confermate in
  questa sessione (sandbox read-only, nessun accesso di rete); gli endpoint elencati sopra
  richiedono verifica da un ambiente con accesso alla rete prima del prove-live.

No BLOCKER or MEDIUM finding. The stale-count observation does not block this PR's merge; it is
a note for whoever runs the post-deploy prove-live count.
