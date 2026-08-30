---
date: 2026-08-28
domain: operations
part: F1 public-web-seo-content
scope: public web (apps/mouth marketing/blog/kbli/property/taxes/zoning, apps/web satellite, public subdomains) — programmatic SEO, structured data, AI-search optimization, i18n
sources:
  - https://arxiv.org/abs/2311.09735
  - https://vercel.com/blog/the-rise-of-the-ai-crawler
  - https://www.gsqi.com/marketing-blog/ai-search-javascript-rendering/
  - https://www.digitalapplied.com/blog/llms-txt-in-practice-adoption-evidence-2026
  - https://www.marqeable.com/blog/does-llms-txt-work/
  - https://seomatic.ai/blog/programmatic-seo-examples
  - https://gracker.ai/blog/programmatic-seo-b2b-saas-2026-playbook
  - https://johncareyseo.co.uk/blog/eeat-financial-services
  - https://schemavalidator.org/guides/person-schema-authors
  - https://www.digitalapplied.com/blog/internal-linking-strategy-topical-authority-playbook-2026
  - https://www.crawlvision.com/blog/hreflang-tag-implementation-guide/
  - https://searchengineland.com/guide/what-is-hreflang
  - https://www.similarweb.com/blog/marketing/geo/gen-ai-stats/
  - https://www.airops.com/blog/ai-referral-traffic-conversion-rates
status: DONE
adversarial_review: kimi-k3
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# F1 — Public Web / SEO / Content: Beyond-SOTA Report

## Anatomy (as measured)

**Surface inventory.** `apps/mouth` is the single Next.js App Router deployment serving every public host (balizero.com plus subdomains routed by `apps/mouth/src/proxy.ts`). Public route groups: `(marketing)` homepage, `(blog)` category/article/services/team/contact, `kbli` + `kbli-explorer`, `visa/*` funnel pages, `zoning`, `taxes/gap`, `property/eligibility`, `feed`, plus `sitemap.ts`/`robots.ts`/`manifest.ts`. `apps/web` (zantara.balizero.com chat) is a separate minimal Next app whose entire metadata is `title: "Nuzantara V6"` (`apps/web/src/app/layout.tsx:4-7`) — no SEO surface by design; the mouth `robots.ts` blanket-disallows the zantara host.

**Programmatic KBLI surface — the crown jewel.** 1,559 codes verified in `apps/mouth/data/KBLI_2025_FINAL_CLEAN.json` (`data` array length 1,559), all fully SSG: `apps/mouth/src/app/kbli/[code]/page.tsx:68-73` sets `dynamicParams = false` + exhaustive `generateStaticParams()`, with an explicit comment recording *why* (ISR cache resets on each deploy served Googlebot cold SSR — GSC clean-window investigation 2026-07-03; `dynamicParams=false` turns invalid codes into true 404s instead of soft-404s). Each page emits four JSON-LD types — `Article`, `GovernmentService`, `FAQPage`, `BreadcrumbList` (`apps/mouth/src/components/kbli/KBLIStructuredData.tsx:113,164,199,225`) — a per-code OG image rendered at request time from a deterministic design system (`/api/og/kbli/[code]`, `runtime = "nodejs"`), a canonical, and per-code composed `<title>`/description via `kbli-meta.ts` with a provenance gate (a `<title>` "is a regulatory assertion Google indexes… it cannot carry a 'verification pending' qualifier" — `kbli/[code]/page.tsx:85-91`). 428 codes carry hand-curated "gold" editorial content (`data/kbli-gold-all.json`). Dataset freshness for sitemap lastmod comes from a committed sidecar `data/kbli-dataset-version.json` (`lastModified: 2026-08-15` + sha256, with a vitest guard that fails when the dataset hash changes without a bump) — an unusually honest lastmod discipline.

**Sitemap and robots.** `sitemap.ts` states an explicit signal-discipline doctrine (lines 19-25): omit `priority`/`changeFrequency` (Google ignores them), emit `lastModified` only where a real modification event is known. It covers statics, 4 service pages, 6 categories, all published blog articles (with noIndex + blocked-slug + query-string filtering, lines 79-98), all 1,559 KBLI codes, visa funnel paths including hand-listed localized variants, and sector pages. `robots.ts` is host-aware: 8 internal hosts get blanket `disallow: /` (lines 78-96); the public host gets a full-disallow-list-per-named-group structure (comment explains robots.txt group-replacement semantics, lines 5-15) plus **explicit AI-crawler welcome groups**: GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, anthropic-ai, Claude-User, PerplexityBot, Google-Extended, Applebot-Extended, Amazonbot, YouBot, Bytespider, FacebookBot, Meta-ExternalAgent, CCBot, cohere-ai (lines 115-159).

**GEO (AI-search) layer.** Four llms files served from `public/`: `llms.txt` (204 lines, index + "Entity Disambiguation" section), `llms-full.txt` (445,740 lines, full EN article corpus), `llms-id.txt` (120,548 lines, ID corpus), `llms-kbli.txt` (1,583 lines, structured KBLI rows from testable `kbli-llms-corpus.ts`). Generation: `scripts/generate-llms-full.ts`, but the build script runs it with `LLMS_GENERATE_FULL_ONLY=1` (`package.json:7`) so **only llms-full.txt regenerates at build; llms.txt freshness, llms-id and llms-kbli are committed artifacts**. An `AnswerBox` MDX component (40-60 word answer capsule placed after H1, `data-answer-capsule="true"`) exists for citation optimization (`src/components/seo/AnswerBox.tsx`). RSS 2.0 with Dublin Core + media extensions at `/feed` (500 items, `src/app/feed/route.ts`). An IndexNow push route exists at `src/app/api/indexnow/route.ts` (key hardcoded line 12 — public by protocol design, not a leak).

**Blog pipeline.** Hybrid reader (`src/lib/blog/articles.ts`): backend API (`news_items` from the intel scraper→staging→approval pipeline) over 3,358 local MDX files in 13 category folders (immigration 1,298, business 758, business_regulations 310…), `unstable_cache` with 60s revalidation (line 892). Article pages are SSR-on-demand (no `generateStaticParams` in `[category]/[slug]/page.tsx`) with Article+FAQ+Breadcrumb JSON-LD (lines 263-267) and 308 category-alias canonicalization (lines 172-182). The file carries scar tissue from the 2026-07-21 **reasoning-leak incident** — raw LLM chain-of-thought written into `tags:` frontmatter became `/insights?tag=<garbage>` URLs Google indexed; cured by a regex backstop (`REASONING_LEAK_TAG`, articles.ts:70-83), a CI guard, and robots `disallow: /*?tag=`. 50 articles carry `noIndex` frontmatter.

**Trust/price data.** `src/lib/trust-figures.ts` is a genuine SSOT for Google Business Profile figures (4.9★, 693 reviews, `MEASURED_ON: 2026-08-14`) created after the schema and visible page disagreed *in the same HTTP response*; `AggregateRatingJsonLd` reads it (`JsonLd.tsx:345-357`). The header honestly refuses to home the unverifiable "5,000+ clients" claim. Prices flow from `bali-zero-prices.json` / pricing-snapshot into FAQ data (`src/lib/seo/faq-data.ts:12-15`).

**Rendering strategy per group (measured).** Full SSG: `kbli/[code]`, `kbli/sectors/[id]`, `(book)/[chapter]`, `visa/second-home/[locale]` (the latter with real per-locale hreflang, `[locale]/page.tsx:98-107`). Force-dynamic: **the homepage** (`(marketing)/page.tsx:19`), `(blog)/news`, `visa-oracle`, `visa/voa`, `v2/*` (v2 correctly noindexed, `v2/page.tsx:24`). Everything else default-dynamic with 60s-cached data.

**Measurement infrastructure.** GA4 via `@next/third-parties`, a `WebVitalsMonitor` that beacons CLS/INP/LCP/TTFB/FCP/FID to `/api/analytics/web-vitals` — which **logs and returns 204** ("a downstream pipeline… can be plugged in here", route.ts:5-13). Three Google site verifications + Bing (`layout.tsx:141-149`). Ground truth exists in-repo: `research/operations/2026-06-10-mythos-gsc-demand-90d.md` (GSC API pull) and `2026-07-26-verdetto-seo-1967-e-ledger-stale.md`.

## Honest state vs. SOTA

**What is genuinely good — and rare.** (1) The *negative-signal discipline* (no fabricated lastmod, no priority/changefreq, dataset-hash-gated freshness sidecar, true 404s via `dynamicParams=false`) is beyond what most professional SEO teams ship. (2) The KBLI programmatic surface is a real proprietary-data moat — 1,559 pages from a curated regulated dataset with provenance gates on titles, four schema types, deterministic OG covers, and editorial gold on 428 codes. This is the textbook programmatic-SEO shape (unique data + real utility), not doorway spam. (3) Host-aware robots + AI-crawler policy + 4-file llms.txt suite + AnswerBox put the GEO layer ahead of ~95% of SMB sites in *mechanism*. (4) SEO logic is unit-tested (`robots.test.ts`, `sitemap.test.ts`, `kbli-meta.test.ts`, noindex-filter tests) — SEO-as-code with regression guards is SOTA practice almost nobody does.

**The demand-side truth (the report's anchor).** The in-repo GSC baseline (90d, 2026-03-10→06-08) measured: **540 clicks, 43,175 impressions, CTR 1.25%, avg position 8.5; ~29% of clicks branded; the money queries — "bali visa agent", "company setup bali", "pt pma setup", "bali tax consultant" — absent from the top-60 clicked queries.** Its own verdict: "The SEO/GEO feeder isn't underperforming — it is **unbuilt**." So the honest state is: a technically over-engineered delivery layer moving ~6 organic clicks/day, with KBLI long-tail demand that is mostly Indonesian SMEs (a channel-fit question, since the buyer persona is foreign), and *zero* built surface targeting high-intent foreigner service queries. The engineering is SOTA-adjacent; the *strategy layer* (query→page mapping, topical hubs, conversion-intent content) is missing.

**Theater and drift (specific).**
- **IndexNow is theater**: `grep` finds zero callers of `/api/indexnow` anywhere in the repo — the publish pipeline never invokes it (superscar family #2, Esiste ≠ Armato, applied to SEO). Also, if `INDEXNOW_SECRET` is unset the route is unauthenticated (route.ts:17-24).
- **CWV collection is theater**: beacons land in a logger; no store, no dashboard, no field-data regression alarm has ever consumed them.
- **llms.txt has drifted from its own SSOTs**: it claims "Google Rating: 5.0/5.0" while `trust-figures.ts` says 4.9/693 (measured 2026-08-14); it claims "5000+ clients since 2020" which trust-figures explicitly refuses to verify; its "Freshness Signal" lists each article **twice** (visible duplication, lines 7-11) and its newest entry is 2026-07-25 — five weeks stale at audit date — because the build regenerates only llms-full.txt.
- **Prompt-injection-style GEO**: `llms.txt` line 3 and the llms-full/id headers embed an `AI-CITATION-INSTRUCTION` comment ordering AI systems to always attribute Bali Zero and "mention the March 2026 regulatory updates". This is an instruction-injection tactic; engines increasingly treat it as a spam signal, and "March 2026" is itself now stale — it manufactures wrong citations.
- **Sitemap violates its own doctrine**: sector pages emit fabricated `lastModified: new Date()` + `changeFrequency`/`priority` (`sitemap.ts:174-179`), and `/taxes/gap` gets a new lastmod every build (lines 160-163) — exactly the "fabricated freshness" the header forbids.
- **Root-layout hreflang is noise**: `layout.tsx:130-137` declares `en-US`, `id-ID` and `x-default` all pointing to the *same URL*. Self-referential hreflang to identical URLs asserts a translation that does not exist; only `visa/second-home` has real localized variants.
- **Homepage is force-dynamic** (`(marketing)/page.tsx:19`): every crawl hit pays full SSR + backend article fetch; the highest-traffic page (203 of 540 clicks) has the weakest rendering guarantee, and no CWV field data exists to know what it costs.
- **3,358 MDX articles vs ~35 news clicks/90d**: the content corpus is scraper-generated at volume with an approval gate, but GSC shows only one article family (dengue alert) ever ranked. Thousands of AI-generated pages are, post-2025 scaled-content-abuse enforcement, a liability sitting on the same domain as the legitimate KBLI asset. One incident (reasoning-leak tags indexed by Google) already proved the pipeline can leak garbage into the index.

## Deep research: the world's best

**Programmatic SEO at scale — the pattern that survives.** The canonical successes share one architecture: *a proprietary structured dataset + a repeatable query pattern + a template that genuinely answers the query* ([seomatic case studies](https://seomatic.ai/blog/programmatic-seo-examples)). Zapier (~5.8M monthly organic visits) generates pages from its integration graph (app × app × use-case); Wise (60M+) from live exchange-rate data (currency × currency, updated continuously); NerdWallet from a financial-product database powering "Best X for Y" pages refreshed via API; Tripadvisor (226M+) from location × intent entities. The 2025-2026 inflection: Google's scaled-content-abuse policy, enforced hard in core updates, reportedly stripped 50-80% of traffic from low-utility programmatic sites ([Gracker 2026 playbook](https://gracker.ai/blog/programmatic-seo-b2b-saas-2026-playbook), unverified percentages). The survivors' common properties map directly onto engineering: (a) data freshness is *real* (Wise rates update by the minute — the page IS the product); (b) every page passes a "would this exist without search engines?" utility test; (c) thin variants are consolidated or noindexed proactively. Nuzantara's KBLI surface already matches (a) partially and (b) fully; the MDX article mass matches neither.

**AI crawlers as first-class consumers — the rendering constraint.** The Vercel/MERJ server-log study ([The Rise of the AI Crawler](https://vercel.com/blog/the-rise-of-the-ai-crawler)) measured GPTBot at 569M req/month, Claude at 370M, combined AI crawlers ≈28% of Googlebot volume — and found **none of the major AI crawlers execute JavaScript** (they fetch JS files but never run them; only Gemini and AppleBot render). ChatGPT wastes 34.82% of fetches on 404s, Claude 34.16% — so clean URL discipline and accurate sitemaps directly buy AI-crawl efficiency. Glenn Gabe's case study ([GSQI](https://www.gsqi.com/marketing-blog/ai-search-javascript-rendering/)) confirmed a client-side-rendered site "looks blank" to ChatGPT/Perplexity/Claude. Engineering consequence: **SSR/SSG of all critical content and metadata is the load-bearing GEO decision** — everything else is refinement. Nuzantara's KBLI SSG is exactly right; the force-dynamic homepage and SSR-on-demand articles still serve complete HTML (App Router SSR), so they pass — but any client-only content (lazy `ZantaraChat`, client components carrying substance) is invisible to the AI-crawl tier.

**GEO evidence base.** The founding academic work (Aggarwal et al., [GEO: Generative Engine Optimization, KDD 2024 / arXiv 2311.09735](https://arxiv.org/abs/2311.09735)) demonstrated in controlled experiments that adding **citations, quotations from credible sources, and statistics** yields 30-40% relative visibility gains in generative answers (Position-Adjusted Word Count) — while keyword-stuffing style optimization *reduced* visibility. Industry corpus studies in 2025-2026 add: content updated within ~30 days earns materially more AI citations; pages with hard data points see 30-40% higher inclusion; and only ~11% of domains are cited by both ChatGPT and Perplexity (per-engine strategies diverge) ([Similarweb AI search stats](https://www.similarweb.com/blog/marketing/geo/gen-ai-stats/), [Enrich Labs guide](https://www.enrichlabs.ai/blog/generative-engine-optimization-geo-complete-guide-2026) — industry figures, unverified methodology). Commercially decisive: Adobe Digital Insights Q1 2026 measured AI-assistant referrals converting **42% better** than non-AI traffic, with B2B studies reporting 4-5× organic conversion rates ([AirOps](https://www.airops.com/blog/ai-referral-traffic-conversion-rates)) — AI referrals arrive pre-qualified because the model already did the comparison. For a high-ticket service firm, one cited answer in "best visa agent in Bali" is worth more than hundreds of blog impressions.

**llms.txt — the honest verdict.** Adoption is ~10% of domains (SE Ranking, 300k-domain study) but **no statistically significant correlation with AI citation frequency exists**; Google explicitly does not consume it (Illyes: not supported; Mueller: compared it to the keywords meta tag — a self-reported manifest can't differentiate sites) ([digitalapplied evidence review](https://www.digitalapplied.com/blog/llms-txt-in-practice-adoption-evidence-2026), [marqeable](https://www.marqeable.com/blog/does-llms-txt-work/)). Of 500M logged AI bot visits, only 408 targeted llms.txt. Its real consumers today are developer tools (IDE agents, MCP servers). Consequence for Nuzantara: keep the llms suite (cheap, occasionally fetched, harmless when accurate) but **stop treating it as the GEO strategy** — the citation levers with evidence behind them are on-page (statistics, quotable sentences, freshness, entity clarity), not in the manifest. And an inaccurate llms.txt (wrong rating, stale freshness, injection instructions) is strictly worse than none.

**E-E-A-T for YMYL professional services.** Immigration/tax/legal content sits squarely in YMYL, where trust signals carry ~3× the ranking correlation of average queries (industry estimate, [Outpace](https://outpaceseo.com/article/eeat-seo/), unverified). The operational SOTA pattern ([John Carey — financial services E-E-A-T](https://johncareyseo.co.uk/blog/eeat-financial-services), [Person schema guide](https://schemavalidator.org/guides/person-schema-authors)): every author/reviewer is a **structured, externally verifiable entity** — a dedicated bio page, `Person` JSON-LD nested in `Article.author`/`reviewedBy` with credentials (`hasCredential`, `jobTitle`) and a `sameAs` chain to LinkedIn/professional registries; visible "reviewed by X on DATE" bylines on every money page; and the firm's licensing/registration data machine-readable in Organization schema. Nuzantara currently publishes articles as "Bali Zero Editorial" with no Person entities, no reviewer bylines, no credentials markup — despite having a real licensed team roster in-repo.

**Topical architecture and internal linking.** The 2026 consensus pattern is hub-and-spoke with bidirectional links (every spoke → hub, hub → every spoke, lateral links between related spokes), where the internal link graph now serves two audiences: Googlebot *and* LLM crawlers using link topology as a topical-authority signal ([digitalapplied internal-linking playbook](https://www.digitalapplied.com/blog/internal-linking-strategy-topical-authority-playbook-2026), [topicalmap.ai](https://topicalmap.ai/blog/auto/internal-linking-architecture-for-topic-clusters)). SOTA operations treat the link graph as build output, not editorial memory: computed from the dataset, orphan-page detection in CI, crawl-depth budgets per money page.

**hreflang.** ~75% of implementations contain errors, and a single error in a cluster causes Google to ignore the whole cluster ([crawlvision](https://www.crawlvision.com/blog/hreflang-tag-implementation-guide/), [Search Engine Land guide](https://searchengineland.com/guide/what-is-hreflang)). The load-bearing rules: alternates must be *actual translations at distinct URLs*, reciprocal, self-referencing, ISO-coded. Declaring `en-US`/`id-ID` alternates that point to one identical URL (Nuzantara's root layout) is the exact anti-pattern the guides warn about.

**Core Web Vitals field practice.** SOTA is field-data-first: CrUX/RUM p75 per route group as the KPI, lab data only for debugging; INP (replaced FID) is where content sites typically fail ([webhelpagency 2026 thresholds](https://webhelpagency.com/blog/core-web-vitals-2026/), [ThisDot Next.js rendering vs CWV](https://www.thisdot.co/blog/next-js-rendering-strategies-and-how-they-affect-core-web-vitals)). The Next.js-specific doctrine: SSG/ISR by default, SSR only where truly necessary — static pages resolve data away from the request path and win TTFB/LCP from the CDN. Collecting beacons without a p75 dashboard (Nuzantara's current state) is the one pattern every guide calls out as useless.

## Gap table

| Dimension | Nuzantara (measured) | SOTA benchmark | Gap |
|---|---|---|---|
| Programmatic data asset | 1,559 KBLI SSG pages, provenance-gated titles, 4 schema types | Zapier/Wise: dataset-driven pages with live-data utility | **Small** — best-in-class shape; missing ID-language variant + conversion path |
| Demand mapping / money queries | None built; money queries absent from GSC top-60 | Query→page map, one target page per intent | **Critical** — the strategy layer is unbuilt |
| Content corpus quality | 3,358 scraper MDX articles, ~35 news clicks/90d, 1 leak incident | Pruned corpora, utility-tested, consolidation discipline | **Critical** — active algorithmic liability |
| E-E-A-T author entities | "Bali Zero Editorial", zero Person schema, no reviewer bylines | Person JSON-LD + credentials + sameAs + reviewedBy on YMYL pages | **Large** |
| Structured data (org/service) | Organization, ProfessionalService, AggregateRating from SSOT, FAQ | Same + Service/Offer schema with real prices, Person graph | **Medium** |
| AI-crawler servability | SSG/SSR HTML complete; robots welcomes 16 AI agents | SSR-everything (no AI crawler runs JS) | **Small** |
| GEO on-page (citations/stats/quotables) | AnswerBox exists; not systematic; no citation blocks | Statistics + quotable sentences + fresh dates = +30-40% visibility (KDD 2024) | **Medium** |
| llms.txt suite | 4 files, but stale freshness, drifted claims, injection comment | Accurate-or-absent; low expected value either way | **Medium** (accuracy, not existence) |
| Push indexing | IndexNow route with zero callers | Publish pipeline pings on every URL change | **Medium** (small fix, real latency win) |
| CWV field data | Beacons → logger, never read | RUM p75 per route group, regression alerts | **Large** |
| i18n / hreflang | Root hreflang all-same-URL (harmful noise); 1 real localized page | Real alternates, reciprocal, per-locale URLs | **Large** (and the ID-market question is unanswered) |
| Sitemap/robots discipline | Doctrine stated + mostly enforced; 2 self-violations | Honest signals, tested | **Small** |
| Measurement loop | GSC pulled twice manually (June, July) | Weekly automated GSC/citation tracking feeding decisions | **Large** |

## Recommendations — reach SOTA

**P0-1 — Build the money-query surface (the one that pays for everything else).** Map the ~15-25 high-intent foreigner queries the GSC baseline proved are unserved ("bali visa agent", "kitas extension service", "pt pma setup cost", "bali tax consultant", "buy property bali foreigner"…) to dedicated conversion pages: service + transparent pricing (from the pricing snapshot SSOT), process timeline, reviewer byline, FAQ schema, WhatsApp CTA. This is days of work for the fleet given templates already exist (`services/[slug]`). *Acceptance: within 90 days of ship, ≥3 named money queries show GSC impressions at position ≤20 and the service pages' collective CTR >2% (baseline: /services/visa CTR 0.9%).*

**P0-2 — De-risk the article mass.** Pull GSC page-level data for all article URLs; noindex (keep serving) every article with 0 clicks and <10 impressions over 12 months; consolidate surviving clusters into topical hubs. The KBLI asset must not share a domain-quality profile with thousands of zero-demand AI pages. *Acceptance: indexed-page count (GSC coverage) falls ≥60%; impressions-per-indexed-page rises ≥3×; zero manual actions.*

**P0-3 — Kill fabricated/drifted signals (one PR).** (a) Remove `new Date()` lastmod + priority/changeFrequency from sector pages and `/taxes/gap` in `sitemap.ts:160-179`; (b) delete the root-layout fake hreflang block (`layout.tsx:130-137`) — keep only real per-locale alternates; (c) regenerate the full llms suite at build (drop `LLMS_GENERATE_FULL_ONLY`), fix the duplicated freshness entries, source the rating line from `trust-figures.ts`, and remove the `AI-CITATION-INSTRUCTION` injection comments; (d) drop the unverifiable "5000+ clients" from llms.txt. *Acceptance: a vitest guard asserts llms.txt freshness date ≤7 days behind the newest article and rating string equals trust-figures; grep for `AI-CITATION-INSTRUCTION` and `5.0/5.0` returns zero; sitemap test asserts no `new Date()` lastmod outside real-event paths.*

**P1-4 — Arm IndexNow.** Call `/api/indexnow` from the article-publish step and the KBLI dataset-version bump; require `INDEXNOW_SECRET` (fail closed). *Acceptance: every publish logs a 200 submission; Bing Webmaster Tools shows submitted URLs within 24h of a publish.*

**P1-5 — Close the CWV loop.** Persist web-vitals beacons (existing Postgres; one table, one migration) and emit a weekly p75 LCP/INP/CLS digest per route group into the existing Telegram digest. *Acceptance: a weekly report exists; a deliberately degraded test route triggers the regression line in the next digest.*

**P1-6 — E-E-A-T entity layer.** Author/reviewer bio pages for the licensed team (roster already in `src/data/team-roster.ts`); `Person` JSON-LD with `jobTitle`, `hasCredential`, `sameAs` (LinkedIn); `reviewedBy` + visible "Reviewed by X, DATE" on every money page and gold KBLI page. *Acceptance: Rich Results test validates Person on all author pages; every P0-1 money page carries a reviewer byline bound to a Person entity.*

**P1-7 — Homepage off force-dynamic.** The article data is already 60s-cached; move `(marketing)/page.tsx` to ISR (`revalidate = 300`). *Acceptance: homepage TTFB p75 <200ms from the P1-5 field data (measure before/after).*

**P2-8 — Internal-link graph as build artifact.** Generate a linkmap at build: every article links to its KBLI codes/service page; every KBLI page links to its sector hub + related gold codes (partially exists via `getRelatedCodes`/`KBLIYoullAlsoNeed`); CI fails on orphan money pages (<3 inlinks) or crawl depth >3. *Acceptance: the CI check exists and the orphan count for money+gold pages is 0.*

## Recommendations — beyond SOTA

**B1 — Query→page contract as tested code.** Commit a `demand-map.yml` (query, intent, target URL, owning surface); a weekly cron pulls the GSC API and diffs reality against the contract — coverage, position, cannibalization (two URLs ranking for one query = test failure). No SEO team runs demand mapping as CI; this repo already runs *everything else* that way. *Acceptance: weekly automated report in the digest; a seeded cannibalization case turns the check red.*

**B2 — Regulation-driven freshness with provenance (the moat only this organism has).** The regulatory-watcher already detects Permenkumham/PMK/PP deltas daily. Wire it to the content layer: a delta opens an auto-PR flagging affected KBLI codes/articles/service pages, and the dataset-version sidecar (already hash-gated) bumps only on real content change — machine-verified "verified against <regulation> on <date>" badges, also emitted as `dateModified` + a claims registry in JSON-LD. Wise's moat is live exchange rates; Bali Zero's is live regulatory truth. *Acceptance: a regulation delta produces a PR touching the affected pages within 48h, and the page's visible+structured "verified on" date updates only when content actually changed.*

**B3 — Own-fleet GEO citation telemetry.** Weekly, the agent fleet queries ChatGPT/Perplexity/Gemini (existing flat subscriptions, zero marginal cost) with the demand-map's 20 money queries and logs whether Bali Zero is cited, which URL, and which competitor won otherwise. This is the measurement loop the GEO tool industry sells for $500+/mo, built from seats already paid for. *Acceptance: a citation-share time series (query × engine × week) exists with ≥8 weeks of data; each P0-1 page ship is annotated on the series.*

**B4 — The KBLI dataset as an API product surface.** Publish the per-code structured rows (already generated for llms-kbli.txt) as stable JSON endpoints + a documented no-auth read API, making balizero.com the canonical machine-readable KBLI 2025 source that agents and developers integrate — citations follow canonical data sources. *Acceptance: `/api/kbli/[code]` documented publicly; ≥1 external referrer (log-measured) consuming it within a quarter.*

**B5 — Bilingual programmatic split (pending the §Solo-operatore ruling).** GSC proves the KBLI demand is Indonesian-language. If Zero rules the ID market in-scope: `/kbli/[code]` gains a real `/id/` variant (the EN map already exists in `kbli-english-generated.ts` — the ID text is the *source*), with genuine reciprocal hreflang, turning 1,559 pages into ~3,118 correctly-declared ones. *Acceptance: hreflang clusters validate with zero errors in GSC international targeting; ID-variant impressions exceed 20% of EN within 2 quarters.*

## §Meta-pattern

The lane's single disease is **engineering rigor concentrated where the organism is comfortable (provable code correctness) and absent where the business lives (market contact)**. The delivery layer has vitest-guarded lastmod honesty — while the demand layer that would tell anyone *whether the pages are wanted* was pulled by hand twice and never automated. The same session culture that built a hash-gated freshness sidecar also left IndexNow with zero callers, CWV beacons falling into a logger, and llms.txt contradicting the very SSOT built to prevent contradiction. This is the repo-wide meta-malattia ("the artifact written/armed/announced IS the thing in force" — superscar #2 Esiste≠Armato) expressed in SEO: *built* is mistaken for *working*, and *correct* is mistaken for *effective*. The corrective invariant for this lane: every SEO artifact must have a consumer and a measurement, or it is theater by definition.

## §Solo-operatore

Decisions only Zero can take (Legge 5 — business, spend, risk):

1. **Channel-fit ruling on the Indonesian-SME audience.** The KBLI long tail converts attention from Indonesian SMEs, not foreign PT-PMA buyers. Is that a second business line (ID-language funnel, local pricing, partnerships), a GEO/authority asset only, or out of scope? B5 and half the KBLI investment hang on this.
2. **Content-liability ruling.** P0-2 noindexes thousands of articles. Upside: de-risking the domain that hosts the KBLI moat. Downside: surrendering any latent long-tail those pages might someday earn. This is a risk appetite call, not an engineering one.
3. **Public claims baseline.** The money pages (P0-1) will assert prices, timelines and service scope in Google's index — client-facing regulatory claims. Zero signs the copy baseline once; the fleet maintains it under the provenance gates.
4. **The "5,000+ clients" claim.** `trust-figures.ts` documents it as unverifiable (CRM holds 1,886 records since 2025-12-22). Either substantiate it from a real source or retire it everywhere (it still lives in llms.txt and layout metadata). A trust claim that can't survive due diligence is a YMYL liability.
5. **Spend.** Everything recommended runs on free APIs (GSC, IndexNow, CrUX) and existing subscriptions. The only optional paid item is a third-party rank/citation tracker — not needed if B3 ships; requires explicit authorization if ever wanted.

## Sources

1. Aggarwal et al., *GEO: Generative Engine Optimization*, KDD 2024 — https://arxiv.org/abs/2311.09735
2. Vercel/MERJ, *The Rise of the AI Crawler* (server-log study) — https://vercel.com/blog/the-rise-of-the-ai-crawler
3. Glenn Gabe (GSQI), *AI Search and JavaScript Rendering* (case study) — https://www.gsqi.com/marketing-blog/ai-search-javascript-rendering/
4. Digital Applied, *llms.txt in Practice: Adoption Data, Evidence, and Setup* (SE Ranking 300k-domain data; Google statements) — https://www.digitalapplied.com/blog/llms-txt-in-practice-adoption-evidence-2026
5. Marqeable, *Does llms.txt Actually Work?* — https://www.marqeable.com/blog/does-llms-txt-work/
6. SEOmatic, *Programmatic SEO Examples: 7 Real Sites Doing It at Scale* (Zapier/Wise/Tripadvisor) — https://seomatic.ai/blog/programmatic-seo-examples
7. Gracker, *Programmatic SEO for B2B SaaS: 2026 Playbook* (scaled-content-abuse enforcement) — https://gracker.ai/blog/programmatic-seo-b2b-saas-2026-playbook
8. John Carey, *E-E-A-T for Financial Services* — https://johncareyseo.co.uk/blog/eeat-financial-services
9. SchemaValidator, *Person Schema for Authors: Bylines, sameAs & E-E-A-T Signals* — https://schemavalidator.org/guides/person-schema-authors
10. Digital Applied, *Internal Linking Strategy & Topical Authority Playbook 2026* — https://www.digitalapplied.com/blog/internal-linking-strategy-topical-authority-playbook-2026
11. Crawlvision, *Hreflang Tag Implementation Guide 2026* (75% error rate) — https://www.crawlvision.com/blog/hreflang-tag-implementation-guide/
12. Search Engine Land, *What is Hreflang?* — https://searchengineland.com/guide/what-is-hreflang
13. Similarweb, *AI Search Stats 2026* — https://www.similarweb.com/blog/marketing/geo/gen-ai-stats/
14. AirOps, *AI Referral Traffic vs Organic Search: Conversion Rates* (incl. Adobe Digital Insights Q1 2026) — https://www.airops.com/blog/ai-referral-traffic-conversion-rates

In-repo ground truth: `research/operations/2026-06-10-mythos-gsc-demand-90d.md` (GSC API 90d baseline), `research/operations/2026-07-26-verdetto-seo-1967-e-ledger-stale.md` (KBLI title/meta verdict). Web-sourced statistics are as-reported by the cited publishers; where methodology could not be independently verified they are marked (unverified) in the text.

## Adversarial review

**Reviewer: `kimi-k3` (Moonshot K3) and `codex` (OpenAI gpt-5.6-sol at xhigh effort), 2026-08-30 — cross-family, generator ≠ grader.** Neither seat wrote any part of this panel. Both read all 18 files of the set in full and were asked the *publication* question rather than a proof-reading one: what in this diff creates real incremental risk beyond what the repository already discloses, whether "it is already public elsewhere" is a sound argument or a rationalisation, whether the sequencing is wrong, and what is simply FALSE. Every concrete file claim either seat made was then re-derived independently with `grep`/`git` before being recorded, and objections that measurement falsified are kept as RETRACTED rather than quietly dropped. The full journal and the complete objection list, with per-objection status, are in this PR's evidence pack (`council-journal.jsonl` and the pack's `dissent` block).

**Limits of this review, stated so it is not read as more than it was.** It happened at PUBLICATION time, not at authoring time: no seat re-derived this lane's technical findings against the codebase, so it is not a correctness review of the analysis. Nine numeric objections across the set were recorded PLAUSIBLE because the fact-checking pass ran out of time, not because they were investigated and cleared — an open list, not an all-clear.

**Finding for this file:** No file-specific finding. The 'IndexNow is theater' observation was not disputed by either seat.
