# KBLI GSC Clean-Window Investigation — 2026-07-03

## Scope
- Filter: balizero.com/kbli/*
- Window A (pre-rollout): 2026-05-14 – 2026-05-20
- Window B (post-rollout): 2026-06-09 – 2026-06-15
- Source: GSC Performance UI + Coverage report (manual export + URL Inspection)

## Aggregate — Site-wide (no filter)
| Metric | Window A | Window B | Δ% |
|---|---|---|---|
| Total clicks | 76 | 70 | -8% |
| Total impressions | 10.1k | 6.81k | -32.6% |
| Average CTR | 0.8% | 1% | +25% |
| Average position | 8.7 | 8 | improved |

**Verdict**: Site-wide health is fine — CTR up, position improved. This rules out a generic Core Update / manual action as root cause.

## Aggregate — /kbli/* filtered (Pages tab)
| Metric | Window A | Window B |
|---|---|---|
| Total clicks | 24 | (incomplete) |
| Total impressions | 4.15k | (incomplete — near-zero across queries) |
| Average CTR | 0.6% | — |
| Average position | 7 | 2 (improved, but low sample) |

**Verdict**: KBLI cluster impressions collapsed almost entirely in Window B (~250 active queries → ~10). Deficit (~3.3k-4.1k impressions) accounts for nearly all of the site-wide drop — confirms this is KBLI-specific, not site-wide.

## Coverage Report (Indexing → Pages, last update 12/06/2026)
| Reason | Pages |
|---|---|
| Alternative page with proper canonical tag | 1,459 |
| Blocked by robots.txt | 30 |
| Page with redirect | 18 |
| Excluded by 'noindex' tag | 8 |
| Duplicate without user-selected canonical | 5 |
| Soft 404 | 2 |
| Crawled - currently not indexed | 200 |
| Discovered - currently not indexed | 88 |
| Duplicate, Google chose different canonical | 1 |

- Total not-indexed: 1,811 / Total indexed: 2,899
- `/kbli/*` share of not-indexed: 97 (Crawled) + 25 (Discovered) = **122 pages**
- Timeline: "not indexed" area started rising ~24 Apr, peaked ~14 May 2026

## URL Inspection — 5-sample deep dive
| URL | Status | Canonical | Last crawled | Verdict |
|---|---|---|---|---|
| /kbli/10296 | not indexed | user-declared present | 12 Jun | Crawl-priority gap |
| /kbli/55103 | **indexed** | present | 27 Jun | Control — recrawl → index works fine |
| /kbli/10314 | not indexed | **N/A** — invalid code, `getCode()` returns null, soft-404 render | 10 Jun | **Not a bug** — code doesn't exist in 1,563 dataset (data model, out of scope) |
| /kbli/49297 | not indexed | present, confirmed via direct fetch | 13 May (51 days) | Crawl-priority gap |
| /kbli/85104 | not indexed | present | 13 May (51 days) | Crawl-priority gap |

**Sample verdict: 4/5 = genuine crawl-priority gap (actionable, Subhi scope). 1/5 = invalid code in data model (out of scope, informational note sent to Antonello).**

## Root Cause
Not a Google Core Update or algorithmic ranking loss. Pattern points to **crawl-budget/priority deprioritization** for long-tail `/kbli/*` pages — Google visits infrequently (40-50+ day gaps for some URLs), and pages not recently recrawled don't get indexed even when canonical/metadata are correct. One isolated case of an invalid KBLI code serving a live "soft 404" URL — not connected to the main pattern.

## Conclusion
- **KBLI Batch 3 title/meta rewrite: stays PAUSED.** Root cause isn't title/meta quality — it's crawl frequency. Rewriting titles won't fix an indexing gap.
- Priority shifts to: sitemap priority hints + internal linking density for long-tail KBLI pages, to signal crawl priority to Google.

## Next Action
1. Audit `apps/mouth/src/app/sitemap.ts` (or equivalent) — verify all 1,563 `/kbli/*` URLs present, check `priority`/`changefreq` values
2. Audit internal link density to long-tail KBLI pages (orphan pages get recrawled less)
3. Re-check GSC in 2-3 weeks post-fix to measure recrawl rate improvement
4. Informational note sent to Antonello re: `10314` invalid code (no action required)

---
*Investigation conducted: 2026-07-03 · Tools: GSC Performance UI, Coverage report, URL Inspection, direct HTML fetch, codebase grep*
