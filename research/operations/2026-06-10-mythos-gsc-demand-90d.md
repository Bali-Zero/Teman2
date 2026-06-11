---
date: 2026-06-10
domain: operations
client_case: none (internal — balizero.com frontend, Mythos Round 1)
sources:
  - GSC Search Analytics API, property https://balizero.com/ (siteOwner SA), 2026-03-10 → 2026-06-08
  - GA4 sessionDefaultChannelGroup, hostName==balizero.com, 28d
  - Raw pull: /tmp/mythos-gsc-90d.json (volatile; tables below are the durable copy)
---

# MYTHOS · Organic Demand Baseline — GSC 90 days

**Companion to the Phase-0 ground-state report.** Lane: `research-only`. This is the demand-side ground truth that feeds the §4 fork decision, the SEO/GEO strategy (§7d), and the Tax/Property study (§11b).

## 1. Headline numbers (90d, 2026-03-10 → 06-08)

- **540 clicks · 43,175 impressions · CTR 1.25% · avg position 8.5.**
- Branded queries ≈ **29% of all clicks** ("bali zero" 109c, "balizero" 26c, "bali zero visa" 14c, "zero bali" 5c).
- GA4 cross-check (28d, hostName=balizero.com): Organic Search 276 sessions / **68% engaged** vs Direct 585 sessions / **13% engaged**. Organic is the real human core (~10 engaged sessions/day); the Direct mass looks largely non-human (monitors/bots/webviews) — flagged as **D9** below.

## 2. What the demand actually is (three clusters)

1. **Brand** (~155 clicks): people who already know Bali Zero. Navigational, not growth.
2. **News spikes** (~35 clicks): the dengue-alert article family (pos 2–3 on "bali dengue fever 2026"). Proof the dispatch can win SERPs fast — editorial muscle is real.
3. **KBLI long tail, largely Indonesian-language** (~25 clicks visible in top-60, many more in tail): "kbli 55203", "kbli homestay", "kbli nya apa", "kbli bibit tanaman", "npwp orang asing". The KBLI Navigator is the site's strongest non-brand SEO asset — **but the searchers are mostly Indonesian SMEs, not foreign PT-PMA buyers.** Channel-fit question for Stage A: does this audience ever convert to the Company funnel, or is it a (valuable) authority/GEO asset with a different monetization path?

**What is missing is the finding:** the money queries of the charter's audience — *bali visa agent, company setup bali, kitas extension service, pt pma setup, bali tax consultant, buy property bali foreigner* — are **absent from the top-60 clicked queries**. The site does not currently capture high-intent foreigner service demand from search. The SEO/GEO feeder isn't underperforming — it is **unbuilt**. That is the growth lever, and it is wide open.

## 3. Page-level opportunities (impressions exist, clicks don't)

| Page | 90d clicks | impressions | avg pos | Read |
|---|---|---|---|---|
| `/` | 203 | 2,024 | 4.1 | brand home, healthy |
| `/services/visa` | 11 | **1,196** | 8.8 | **CTR 0.9% — title/meta + position work = nearest-term organic win for the Visa channel** |
| `/team` | 14 | 870 | 4.7 | people searching the humans — the "human moat" has organic demand |
| `/contact` | 4 | 490 | 5.0 | |
| `/services` | 3 | 283 | 3.4 | pos 3.4 with 1% CTR → snippet problem |
| `/services/tax` | 3 | 81 | **22.6** | Tax has no organic presence (page 3) |
| `/living/dengue-alert-2026` | 64+6 | ~1,074 | 5–6 | news asset; duplicated under `/lifestyle/` too (canonical check) |
| `/kbli/*` (tail) | ~40 | thousands | 4–9 | the long-tail engine; Indonesian-language demand |

Property: **no property-intent page or query appears anywhere in the top-60** — organic demand for the Property channel is effectively zero today.

## 4. Implications for Stage A (pre-registered, before the fork decision)

1. **Fork-decision input (§4a):** there is no measurable "conversation-seeking" organic traffic today; today's converters arrive on brand or content pages. Any conversation-first thesis must argue from analogy/competitors/pilot — the behavioral data cannot support it yet (nor refute it: `/chat` gets 20 sessions/28d).
2. **The feeder is the lever:** with ~10 engaged organic sessions/day, on-page CRO moves single visitors; intent-capture content (service-intent pages, GEO citability) moves the denominator. Round-1A structural work should weight accordingly.
3. **Tax & Property (§11):** GSC confirms both channels have ~zero organic demand captured. Their Round-1B design must start from demand *creation* (intent pages + GEO), not funnel polish. This is the first hard datum for the 1B study.
4. **Quick wins queue (`ungated-safe-fix` candidates):** `/services/visa` + `/services` title/meta rewrite; dengue article `/living/` vs `/lifestyle/` canonical check. Small, brand-neutral, measurable at tier 2 (GSC CTR windows).

## 5. New defect

| # | Finding | Severity | Lane / owner |
|---|---|---|---|
| D9 | Direct = 585 sessions/28d with 13% engagement on balizero.com — likely bot/monitor traffic inflating the public baseline. Engaged-organic (~276) is the honest denominator. | P2 | Measurement design (Stage A): adopt *engaged sessions, hostname-scoped* as scoreboard denominator; investigate top Direct landing paths |

## 6. Raw top-30 queries (durable copy)

```
109c   490i pos 2.1  bali zero          | 26c 103i pos 1.6  balizero
 22c    67i pos 2.7  bali dengue fever 2026 | 14c 60i pos 1.7  bali zero visa
  7c    34i pos 2.6  dengue bali 2026   |  5c 158i pos 4.5  zero bali
  3c    15i pos 3.1  dengue fever bali 2026 | 2c 54i pos 5.0  kbli 55203
  2c    10i pos 5.6  kbli 64995         |  1c   7i pos 2.9  dengue in bali 2026
  1c     3i pos 5.3  dharma dewata      |  1c  11i pos 9.3  kbli 02409
  1c     6i pos 9.3  kbli 42201 ...     |  1c  31i pos 6.0  kbli 46721
  1c     1i pos 31   kbli 49214         |  1c  22i pos 4.7  kbli 55901
  1c     9i pos 5.1  kbli 64210         |  1c  13i pos 1.2  kbli 68126
  1c    65i pos 8.6  kbli 78101         |  1c   1i pos 12   kbli ai
  1c    23i pos 9.0  kbli bibit tanaman |  1c  62i pos 9.2  kbli homestay
  1c     4i pos 4.8  kbli nya apa       |  1c   1i pos 15   npwp orang asing
```
(Queries below this line are zero-click noise incl. scraper-style `-site:` exclusion strings — ignored.)
