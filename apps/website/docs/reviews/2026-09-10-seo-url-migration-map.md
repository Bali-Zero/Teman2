# SEO URL migration map — R19 website transplant

Date: 2026-09-10 WITA. Verifier: Claude (Fable) session ff3a541e, window 2. Generator: Codex lane `codex/website-pro-continuation`. Scope: every URL in the live production sitemap plus the public URLs that live outside it, mapped to the route the new `apps/website` app would serve at cutover. This is a preparation artifact: nothing here is deployed, armed or merged. Row-level data: `2026-09-10-seo-url-migration-map.csv` (2,466 rows: 2,429 sitemap + 37 live-non-sitemap).

## Evidence

| Source                                          | Observation                                                                                                                                                                                    |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Live sitemap `https://balizero.com/sitemap.xml` | 2,429 `<loc>` entries on 2026-09-10 (2,423 on 2026-09-07; growth is `news_*` articles). 1,582 under `/kbli` (1,559 codes + 21 sectors + index + explorer).                                     |
| New app routes                                  | 50 `page.tsx` + 23 `route.ts` under `apps/website/src/app`; `next.config.ts` 53 redirects, all `permanent: false`.                                                                             |
| Local dev server `127.0.0.1:3100`               | 124 sampled URLs probed: every sitemap class resolves except `llms*.txt` (404). Full table in the CSV `evidence` column.                                                                       |
| KBLI parity                                     | `apps/website` imports `getAllCodes/getCode/getSections` from `apps/mouth/src/lib/kbli-data`; dataset codes 1,559 = sitemap codes 1,559, symmetric difference 0; sectors A–U 21/21 render 200. |
| Article API                                     | 30 sampled slugs (24 editorial + 6 `news_*`) → `GET /api/blog/articles/{cat}/{slug}` 200, `status: published`, `noIndex` false/undefined, slug identity intact.                                |
| Production robots/canonical                     | Probed 57 URLs (`prod_probe.tsv`): `/privacy`,`/terms`,`/visa`,`/kbli/*`,`/visa/clock                                                                                                          | match | second-home*`,`/book`,`/zoning`,`/tax-calendar`,`/property/eligibility`,`/kbli/builder | decoder`are`index,follow`; `/v2/_`,`/visa/voa`,`/visa-oracle_`,`/prime`,`/journal`,`/about`are`noindex`. |

## Disposition summary (sitemap, 2,429 URLs)

| Class                                                                                                                                 | Count | New route                          | Disposition                       | Cutover status                                           | Indexable |
| ------------------------------------------------------------------------------------------------------------------------------------- | ----: | ---------------------------------- | --------------------------------- | -------------------------------------------------------- | --------- |
| KBLI code `/kbli/NNNNN`                                                                                                               | 1,559 | `kbli/[code]`                      | keep                              | 200                                                      | yes       |
| Editorial article `/{cat}/{slug}`                                                                                                     |   814 | `[category]/[slug]` via legacy API | keep                              | 200                                                      | yes       |
| KBLI sector `/kbli/sectors/[A-U]`                                                                                                     |    21 | `kbli/sectors/[id]`                | keep                              | 200                                                      | yes       |
| Static (`/kbli`, `/kbli-explorer`, `/kbli/sectors`, `/services`, `/services/tax`, `/services/property`, `/news`, `/team`, `/contact`) |     9 | own page                           | keep                              | 200                                                      | yes       |
| Category index `/visas … /trends`                                                                                                     |     6 | `[category]`                       | keep                              | 200                                                      | yes       |
| `news_*` article                                                                                                                      |     6 | `[category]/[slug]`                | keep                              | 200                                                      | yes       |
| Visa tools (`/visa/match`, `/visa/clock`, `/visa/second-home{,/id,/it,/studio}`)                                                      |     6 | own page                           | keep                              | 200                                                      | yes       |
| `/llms.txt`, `/llms-full.txt`, `/llms-id.txt`                                                                                         |     3 | none                               | **provision** (ORPHAN, 404 today) | 200                                                      | yes       |
| `/services/visa`, `/services/company`                                                                                                 |     2 | `services/[slug]`                  | **301 (D2)**                      | 308 → `/services/immigration`, `/services/company-setup` | redirect  |
| `/`                                                                                                                                   |     1 | `page.tsx`                         | keep                              | 200                                                      | yes       |
| `/taxes/gap`                                                                                                                          |     1 | `taxes/gap`                        | keep                              | 200                                                      | yes       |
| `/visa`                                                                                                                               |     1 | route → `/visa-oracle`             | **301 (D1)**                      | 308 → `/visa-oracle`                                     | redirect  |

**Orphans in the sitemap: 3** (`llms*.txt`). Every other sitemap URL has a route. **Orphans outside the sitemap: 5** (`/llms-kbli.txt`, `/sitemap-ai.xml`, `/sitemap.xml`, `/robots.txt`, `/feed`). All eight are static files or generators, not page rebuilds.

## Live URLs outside the sitemap (37 rows)

| URL                                                                                                                  | Prod                                    | New app today                         | Disposition                                                      |
| -------------------------------------------------------------------------------------------------------------------- | --------------------------------------- | ------------------------------------- | ---------------------------------------------------------------- |
| `/kbli/builder`, `/kbli/decoder`, `/property/eligibility`, `/tax-calendar`, `/book`, `/zoning`, `/privacy`, `/terms` | 200 index                               | 200                                   | keep, indexable, add to sitemap                                  |
| `/journal`                                                                                                           | 200 soft-404 noindex                    | 200 duplicate of `/news`              | **301 (D4)** → `/news`, or canonical                             |
| `/v2/company/about`                                                                                                  | 200 noindex                             | 200 duplicate of `/about`             | 301 → `/about`                                                   |
| `/v2`                                                                                                                | 200 noindex preview                     | 307 → `/`                             | 301 → `/`                                                        |
| `/v2/privacy`, `/v2/terms`, `/v2/cookies`, `/visa/privacy`, `/visa/terms`                                            | noindex                                 | noindex (per-route)                   | keep noindex                                                     |
| `/v2/company/careers`, `/v2/company/press`, `/visa-oracle/unlock`, `/visa-oracle/privacy`, `/visa/voa`, `/prime`     | noindex                                 | noindex **only via global**           | keep, **add per-route noindex before the global one is removed** |
| `/visa-oracle`                                                                                                       | noindex                                 | 200, no metadata                      | D1 decides indexability                                          |
| `/feed`                                                                                                              | 200 RSS, `rel=alternate` in root layout | 307 → legacy origin (503 without env) | **provision** RSS route or 308 to legacy host                    |
| `/llms-kbli.txt`, `/sitemap-ai.xml`, `/sitemap.xml`, `/robots.txt`                                                   | 200                                     | 404                                   | **provision**                                                    |
| 9 legacy redirect families (`/kbli-navigator*`, `/immigration*`, `/tax-legal                                         | tax                                     | lifestyle                             | tech                                                             | bali_news | digital-nomad*`, `/insights*`, `/tax/gap`, `/visa-v2`, `/visa/second-home-e33`, freelancer/e33 guides) | 308/301 | 307 | flip to 308 (risk 1) |

## The four SEO risks, mapped to a cutover action

1. **Temporary redirects (307).** 53 config entries (`permanent: false`), `redirect()` in `services/visa` + `services/company` + `kbli-navigator`, `Response.redirect(…,307)` in `tax/gap`, hard 307 in `visa-v2` and `/visa`. Production serves 308 for all of them. Cutover: `permanent: true`, `permanentRedirect()`, 308 in handlers. Keep 307 only on `retainedHandoff` (cross-host hop). Bug found: `/visa/second-home-e33` resolves through the retained alias and 307s to the _legacy_ origin instead of the local `/visa/second-home` page; make it an internal 308.
2. **Global noindex + no sitemap.** Root layout `robots {index:false}` + header `X-Robots-Tag` on `/:path*`; no `sitemap.ts`/`robots.ts`. Cutover: remove both globally, add per-route `robots: {index:false}` to the six pages listed above (they currently inherit it), add `sitemap.ts` generating the classes marked _indexable yes_ (2,426 sitemap rows + 8 tier-2 keeps + the two renamed service slugs), add `robots.ts` mirroring the production disallow list (`/api/`, `/_next/`, `/*?tag=`, staff/portal paths).
3. **Legal canonical mismatch.** Production: `/privacy` and `/terms` are `index,follow`; `/v2/*` are noindex. New footer (`Footer.tsx`) links `/v2/privacy|terms|cookies`. Cutover needs D3. Note production has no indexable `/cookies` (404 soft); `/v2/cookies` is the only cookie page.
4. **Soft-404 / soft-503.** `/journal` in production is a soft-404; the new app serves a real page there (fixes the soft-404, creates a duplicate of `/news` → D4). New soft-error: when the legacy origin is unavailable, `[category]/[slug]` renders “This story is temporarily unavailable” and the journal index renders an empty state, both with **HTTP 200**. Return 503 with `Retry-After` in that branch so Google does not cache the placeholder.

## Precondition that decides 827 URLs

814 + 6 articles, `/news`, `/journal` and the 6 category pages read content through `readEditorialJson()` → `editorialUpstreamOrigin()`. On localhost the origin defaults to `https://balizero.com`; on any public host it returns `null` unless **both** `WEBSITE_LEGACY_ORIGIN` and `WEBSITE_PUBLIC_ORIGIN` are set, and the legacy origin must be an https host that is _not_ `balizero.com` nor any shared front door (`visa|tax|my|kita|zantara|prime.balizero.com`). So the mouth app must be reachable on an independent hostname before the new app owns the apex, or 34% of the sitemap degrades to the 200 placeholder. Same dependency for `/feed` and every `/legacy/*` handoff.

## Metadata gaps (dev title leaks)

Pages with no `metadata`/`generateMetadata`, rendering the root title “Bali Zero — Website development”: `/` (blocker), `/{category}` ×6, `/kbli/sectors/[id]` ×21, `/visa-oracle`, `/visa-oracle/unlock`, `/visa-oracle/privacy`, `/v2/company/about`. `kbli/[code]` emits a title only (no description, no canonical) for 1,559 indexed pages; production emits description + self-canonical. The root layout title itself must change at cutover.

## Decisions for Zero

| ID  | Question                                                                                                                                         | Recommendation                                                                                                                                                                                                    |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | `/visa` is the indexed public selector (canonical target of `/visa/voa`); the new app 307s it to `/visa-oracle`, which production marks noindex. | 308 `/visa` → `/visa-oracle`, make `/visa-oracle` indexable with self-canonical, keep `/visa-oracle/unlock` noindex. Alternative: serve the oracle at `/visa` and 308 `/visa-oracle` → `/visa` (zero URL change). |
| D2  | Keep `/services/visa`, `/services/company` or rename to `/services/immigration`, `/services/company-setup`.                                      | Rename with 308; both new slugs already built and production's new slugs are soft-404 today, so nothing to protect there.                                                                                         |
| D3  | Which legal edition is public: `/privacy`+`/terms` (indexable, UU-PDP, 10 sections) or `/v2/*` (noindex, 6 sections).                            | Footer → `/privacy`, `/terms`, `/v2/cookies`; keep `/v2/privacy                                                                                                                                                   | terms`noindex with canonical to`/privacy | /terms`. |
| D4  | `/news` vs `/journal` as canonical index.                                                                                                        | `/news` canonical (indexed, in sitemap, in all backlinks); 308 `/journal` → `/news`; rewrite internal `/journal?category=` links to `/news?category=`.                                                            |

## Cutover verification

The CSV is the contract: for each row curl the live URL and assert `cutover_status`, `cutover_location` and the robots directive implied by `indexable`. Run it against the release candidate on its preview hostname (expect global noindex still present) and again after promotion (expect it gone). Re-fetch the sitemap at that time; the article set grows daily.

## Addendum 2026-09-10 (after the local MDX loader)

The precondition above is resolved for the 808 authored articles, `/news`,
`/journal` and the six category indexes: `src/lib/server/article-archive.ts`
serves them from `apps/mouth/src/content/articles` with no legacy origin
(proved on a dev server with `Host: preview.example` and both origin variables
unset: `/property/leasehold-vs-freehold` 200 with the frontmatter title, `/news`
200 with 12 stories). The legacy origin remains a precondition only for the
scraper-published `news_*` slugs (6 in today's sitemap), `/feed` and the
`/legacy/*` handoffs. Follow-up for cutover: memoise the 808-file archive scan
across requests (today it is per-request `cache()` only).
