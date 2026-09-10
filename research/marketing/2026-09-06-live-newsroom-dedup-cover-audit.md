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
