# SEO_STATE — balizero.com

**Owner:** AISO (standing SEO manager) · **Operator:** Subhi Darajat
**Created:** 2026-09-07 · **Source measured at commit:** `6c6f25a960f108d3cf88c85b5ba428cc3604c1b1` (`origin/main`)
**Served surface measured at commit:** `1bdadc5f2839f2d49d3d4f5d0424ccdaf4937d50` (2026-09-07, `curl /api/health`) — 5 commits behind `main`

> Rule: a route that is not in the ledger below has SEO status **unknown**, not "fine".
> Rule: update this file in the same PR that changes anything it describes.

---

## 0. Measurement layer of this file

Counts in §1 and §2 were measured at **layer 2 — `origin/main` source**, quotable as `file:line`.
**§3.1 is the exception: it was closed at layer 3 on the served surface**, see that section.
The session that created this file ran in the Anthropic cloud sandbox, where:

- `curl https://balizero.com/api/health` → egress proxy `connect_rejected` from the sandbox. The layer-3 probes in §3.1 were therefore run from Subhi's machine on 2026-09-07 and are recorded with the served commit they measured.
- Ahrefs MCP → `{"error":"Insufficient plan"}` on `site-audit-projects`, `site-explorer-top-pages`, `site-explorer-metrics`, `gsc-pages`, and even the free `subscription-info-limits-and-usage` (measured 2026-09-07). **No traffic figure in this file. None was invented.**
- `docs/SYSTEM_INVENTORY.md` → does not exist at that path on `origin/main` @ `6c6f25a9`. `find . -iname 'SYSTEM_INVENTORY*'` → 0 hits.

Consequence: the debt list in §3 is ranked by **crawl exposure and internal-link evidence**, explicitly _not_ by measured traffic. Re-rank it the first time a session with Ahrefs/GSC access runs.

---

## 1. Counts at `6c6f25a9`

| Measure                                                                               | Pattern                             | Value   |
| ------------------------------------------------------------------------------------- | ----------------------------------- | ------- |
| `page.tsx` under `apps/mouth/src/app`, excl. `api/` and `__tests__/`                  | `find … -name page.tsx`             | 161     |
| of those, in route group `(workspace)` (internal, noindex by design — memory item 37) | path prefix                         | 67      |
| public-candidate routes                                                               | 161 − 67                            | 94      |
| public routes whose chain sets `alternates.canonical` below the root layout           | `grep -l 'canonical:'` walk         | 65      |
| **public, crawlable routes with NO route-level canonical**                            | see §3.1                            | **27**  |
| public routes with any JSON-LD in the route subtree                                   | `application/ld+json`\|`schema.org` | 6       |
| files under `app/` exporting `metadata`/`generateMetadata`                            | `grep -l`                           | 59      |
| files under `app/` containing `alternates:` / `canonical:`                            | `grep -l`                           | 25 / 26 |

Positive control for the canonical walk: `apps/mouth/src/app/visa/layout.tsx:13-14` sets
`alternates: { canonical: "https://balizero.com/visa" }` and the walk reports `/visa` as covered.

---

## 2. Route ledger — public surfaces

"Self-canonical = NO" means no segment between the page and the root layout defines `alternates`,
so the route inherits `apps/mouth/src/app/layout.tsx:131` `canonical: appUrl` — the homepage.

| Route                               | Metadata owner                                 | Self-canonical        | Schema | In sitemap.ts | Source                                       |
| ----------------------------------- | ---------------------------------------------- | --------------------- | ------ | ------------- | -------------------------------------------- |
| `/`                                 | `(marketing)/page.tsx`                         | yes                   | no     | yes           | `(marketing)/page.tsx`                       |
| `/[category]`                       | `(blog)/[category]/page.tsx`                   | yes                   | no     | dynamic       | `(blog)/[category]/page.tsx`                 |
| `/[category]/[slug]`                | `(blog)/[category]/[slug]/page.tsx`            | yes                   | yes    | dynamic       | `(blog)/[category]/[slug]/page.tsx`          |
| `/agents`                           | `root layout only`                             | **NO — inherits `/`** | no     | no            | `agents/page.tsx`                            |
| `/assessment`                       | `(assessment)/assessment/layout.tsx`           | **NO — inherits `/`** | no     | no            | `(assessment)/assessment/page.tsx`           |
| `/assessment/briefing`              | `(assessment)/assessment/briefing/page.tsx`    | **NO — inherits `/`** | no     | no            | `(assessment)/assessment/briefing/page.tsx`  |
| `/book`                             | `(book)/layout.tsx`                            | **NO — inherits `/`** | no     | no            | `(book)/book/page.tsx`                       |
| `/book/[chapter]`                   | `(book)/book/[chapter]/page.tsx`               | **NO — inherits `/`** | no     | dynamic       | `(book)/book/[chapter]/page.tsx`             |
| `/contact`                          | `(blog)/contact/page.tsx`                      | yes                   | no     | yes           | `(blog)/contact/page.tsx`                    |
| `/dream`                            | `root layout only`                             | **NO — inherits `/`** | no     | no            | `dream/page.tsx`                             |
| `/edge`                             | `root layout only`                             | **NO — inherits `/`** | no     | no            | `edge/page.tsx`                              |
| `/exclusive`                        | `exclusive/page.tsx`                           | **NO — inherits `/`** | no     | no            | `exclusive/page.tsx`                         |
| `/interview_natalie`                | `(assessment)/interview_natalie/layout.tsx`    | **NO — inherits `/`** | no     | no            | `(assessment)/interview_natalie/page.tsx`    |
| `/kbli`                             | `kbli/page.tsx`                                | yes                   | no     | yes           | `kbli/page.tsx`                              |
| `/kbli-explorer`                    | `kbli-explorer/layout.tsx`                     | **NO — was mis-scored "yes" here, see §3.1a** | yes    | yes           | `kbli-explorer/page.tsx`                     |
| `/kbli/[code]`                      | `kbli/[code]/page.tsx`                         | yes                   | yes    | dynamic       | `kbli/[code]/page.tsx`                       |
| `/kbli/builder`                     | `kbli/builder/page.tsx`                        | yes                   | no     | no            | `kbli/builder/page.tsx`                      |
| `/kbli/decoder`                     | `kbli/decoder/page.tsx`                        | yes                   | no     | no            | `kbli/decoder/page.tsx`                      |
| `/kbli/sectors`                     | `kbli/sectors/page.tsx`                        | yes                   | no     | yes           | `kbli/sectors/page.tsx`                      |
| `/kbli/sectors/[id]`                | `kbli/sectors/[id]/page.tsx`                   | yes                   | no     | dynamic       | `kbli/sectors/[id]/page.tsx`                 |
| `/lab/voice-concierge`              | `root layout only`                             | **NO — inherits `/`** | no     | no            | `lab/voice-concierge/page.tsx`               |
| `/news`                             | `(blog)/news/page.tsx`                         | yes                   | no     | yes           | `(blog)/news/page.tsx`                       |
| `/prime`                            | `prime/page.tsx`                               | **NO — inherits `/`** | no     | no            | `prime/page.tsx`                             |
| `/prime/proposal/[token]`           | `root layout only`                             | **NO — inherits `/`** | no     | dynamic       | `prime/proposal/[token]/page.tsx`            |
| `/privacy`                          | `privacy/page.tsx`                             | **NO — inherits `/`** | no     | no            | `privacy/page.tsx`                           |
| `/property`                         | `(blog)/property/page.tsx`                     | yes                   | no     | no            | `(blog)/property/page.tsx`                   |
| `/property/eligibility`             | `property/eligibility/page.tsx`                | yes                   | no     | no            | `property/eligibility/page.tsx`              |
| `/services`                         | `(blog)/services/page.tsx`                     | yes                   | no     | yes           | `(blog)/services/page.tsx`                   |
| `/services/[slug]`                  | `(blog)/services/[slug]/page.tsx`              | yes                   | yes    | dynamic       | `(blog)/services/[slug]/page.tsx`            |
| `/tax-calendar`                     | `(tax-calendar)/tax-calendar/layout.tsx`       | **NO — inherits `/`** | no     | no            | `(tax-calendar)/tax-calendar/page.tsx`       |
| `/taxes/gap`                        | `taxes/gap/page.tsx`                           | yes                   | no     | yes           | `taxes/gap/page.tsx`                         |
| `/team`                             | `(blog)/team/page.tsx`                         | yes                   | no     | yes           | `(blog)/team/page.tsx`                       |
| `/terms`                            | `terms/page.tsx`                               | **NO — inherits `/`** | no     | no            | `terms/page.tsx`                             |
| `/v2`                               | `v2/page.tsx`                                  | **NO — inherits `/`** | no     | no            | `v2/page.tsx`                                |
| `/v2/company/about`                 | `v2/company/about/page.tsx`                    | **NO — inherits `/`** | no     | no            | `v2/company/about/page.tsx`                  |
| `/v2/company/careers`               | `v2/company/careers/page.tsx`                  | **NO — inherits `/`** | no     | no            | `v2/company/careers/page.tsx`                |
| `/v2/company/press`                 | `v2/company/press/page.tsx`                    | **NO — inherits `/`** | no     | no            | `v2/company/press/page.tsx`                  |
| `/v2/cookies`                       | `v2/cookies/page.tsx`                          | **NO — inherits `/`** | no     | no            | `v2/cookies/page.tsx`                        |
| `/v2/news`                          | `v2/news/page.tsx`                             | **NO — inherits `/`** | no     | no            | `v2/news/page.tsx`                           |
| `/v2/privacy`                       | `v2/privacy/page.tsx`                          | **NO — inherits `/`** | no     | no            | `v2/privacy/page.tsx`                        |
| `/v2/terms`                         | `v2/terms/page.tsx`                            | **NO — inherits `/`** | no     | no            | `v2/terms/page.tsx`                          |
| `/verification`                     | `root layout only`                             | **NO — inherits `/`** | no     | no            | `verification/page.tsx`                      |
| `/visa`                             | `visa/layout.tsx`                              | yes                   | no     | yes           | `visa/page.tsx`                              |
| `/visa-oracle`                      | `(visa-oracle)/visa-oracle/layout.tsx`         | **NO — inherits `/`** | no     | no            | `(visa-oracle)/visa-oracle/page.tsx`         |
| `/visa-oracle/privacy`              | `(visa-oracle)/visa-oracle/privacy/layout.tsx` | **NO — inherits `/`** | no     | no            | `(visa-oracle)/visa-oracle/privacy/page.tsx` |
| `/visa-oracle/unlock`               | `(visa-oracle)/visa-oracle/layout.tsx`         | **NO — inherits `/`** | no     | no            | `(visa-oracle)/visa-oracle/unlock/page.tsx`  |
| `/visa/clock`                       | `visa/clock/layout.tsx`                        | yes                   | no     | yes           | `visa/clock/page.tsx`                        |
| `/visa/clock/[hash]`                | `visa/clock/layout.tsx`                        | yes                   | no     | dynamic       | `visa/clock/[hash]/page.tsx`                 |
| `/visa/match`                       | `visa/match/layout.tsx`                        | yes                   | no     | yes           | `visa/match/page.tsx`                        |
| `/visa/match/[hash]`                | `visa/match/layout.tsx`                        | yes                   | no     | dynamic       | `visa/match/[hash]/page.tsx`                 |
| `/visa/privacy`                     | `visa/privacy/page.tsx`                        | yes                   | no     | no            | `visa/privacy/page.tsx`                      |
| `/visa/second-home`                 | `visa/second-home/page.tsx`                    | yes                   | yes    | yes           | `visa/second-home/page.tsx`                  |
| `/visa/second-home/[locale]`        | `visa/second-home/[locale]/page.tsx`           | yes                   | yes    | dynamic       | `visa/second-home/[locale]/page.tsx`         |
| `/visa/second-home/studio`          | `visa/second-home/studio/page.tsx`             | yes                   | no     | yes           | `visa/second-home/studio/page.tsx`           |
| `/visa/terms`                       | `visa/terms/page.tsx`                          | yes                   | no     | no            | `visa/terms/page.tsx`                        |
| `/visa/voa`                         | `visa/voa/layout.tsx`                          | yes                   | no     | no            | `visa/voa/page.tsx`                          |
| `/visa/voa/[hash]`                  | `visa/voa/layout.tsx`                          | yes                   | no     | dynamic       | `visa/voa/[hash]/page.tsx`                   |
| `/visa/voa/auth/continue`           | `visa/voa/layout.tsx`                          | yes                   | no     | no            | `visa/voa/auth/continue/page.tsx`            |
| `/visa/voa/checkout/[resultId]`     | `visa/voa/layout.tsx`                          | yes                   | no     | dynamic       | `visa/voa/checkout/[resultId]/page.tsx`      |
| `/visa/voa/orders/[orderId]`        | `visa/voa/layout.tsx`                          | yes                   | no     | dynamic       | `visa/voa/orders/[orderId]/page.tsx`         |
| `/visa/voa/orders/[orderId]/return` | `visa/voa/layout.tsx`                          | yes                   | no     | dynamic       | `visa/voa/orders/[orderId]/return/page.tsx`  |
| `/visa/voa/upload/[resultId]`       | `visa/voa/layout.tsx`                          | yes                   | no     | dynamic       | `visa/voa/upload/[resultId]/page.tsx`        |
| `/zoning`                           | `zoning/page.tsx`                              | yes                   | no     | no            | `zoning/page.tsx`                            |

`(workspace)` routes (67) are deliberately excluded: `X-Robots-Tag: noindex, nofollow` at
`apps/mouth/src/proxy.ts` on `isAppDomain`, permanent — memory item 37. Their missing metadata is not debt.

---

## 3. Open SEO debt

Ranked by crawl exposure, **not** by measured traffic — traffic could not be measured on 2026-09-07 (§0).

### 3.1 — Root-layout canonical leaks onto every non-overriding route — **CONFIRMED LIVE 2026-09-07**

**Evidence (layer 2, `6c6f25a9`):**

- `apps/mouth/src/app/layout.tsx:41` — `export const metadata: Metadata = {`
- `apps/mouth/src/app/layout.tsx:130-138`:
  ```ts
  alternates: {
    canonical: appUrl,                 // line 131
    languages: {
      "en-US": appUrl,
      "id-ID": appUrl,
      "x-default": appUrl,
    },
  ```
- `apps/mouth/src/app/layout.tsx:40` — `const appUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";`

Next.js App Router merges `metadata` **shallowly** down the segment tree: a segment that does not
define `alternates` inherits the parent's `alternates` object whole. The repo already carries a
written record of this exact failure mode for the sibling field `title.template` —
`apps/mouth/src/app/metadata-title-template.test.ts:6-40` ("the defect exists only in the
COMPOSITION of the page title with a template declared in another file").

There is **no equivalent guard for `alternates`**: `grep -rl 'canonical' apps/mouth/src --include='*.test.ts*'`
returns 0 files that assert a route's canonical.

**Consequence if the inheritance holds on the served page:** each of the 27 routes below emits
`<link rel="canonical" href="https://balizero.com/">` plus three hreflang entries pointing at the
homepage — an instruction to Google to consolidate the page into the homepage.

**MEASURED ON THE SERVED SURFACE — 2026-09-07, served commit `1bdadc5f2839f2d49d3d4f5d0424ccdaf4937d50`.**

```
$ curl -s https://balizero.com/api/health | grep -i commit
{"status":"ok","timestamp":1788769086856,"commit":"1bdadc5f2839f2d49d3d4f5d0424ccdaf4937d50"}

$ curl -s https://tax.balizero.com/ | grep -o '<link rel="canonical"[^>]*>'
<link rel="canonical" href="https://balizero.com"/>

$ curl -s https://balizero.com/tax-calendar | grep -o '<link rel="canonical"[^>]*>'
<link rel="canonical" href="https://balizero.com"/>

$ curl -s https://balizero.com/visa | grep -o '<link rel="canonical"[^>]*>'      # positive control
<link rel="canonical" href="https://balizero.com/visa"/>
```

The positive control printed its own path, so the two homepage results are a real finding and not a
grep that missed its target. The inference is closed: **`tax.balizero.com` and `/tax-calendar` both
serve `<link rel="canonical" href="https://balizero.com"/>` — they declare themselves duplicates of
the homepage.**

The source explanation holds at the served commit itself, not only at `main`:
`git show 1bdadc5f:apps/mouth/src/app/layout.tsx` → `canonical: appUrl` at line 131, `appUrl` at
line 39; `git show '1bdadc5f:apps/mouth/src/app/(tax-calendar)/tax-calendar/layout.tsx'` → `title`
at line 9, no `alternates`. `1bdadc5f` is an ancestor of `6c6f25a9` (`git merge-base --is-ancestor`,
RC=0); `git rev-list --count 1bdadc5f..6c6f25a9` = 5.

**Still unmeasured:** the other 25 routes in the list below were not probed individually. Two of
27 were measured; the remaining 25 share the same source condition but carry no layer-3 evidence
yet. Do not write "27 routes confirmed" anywhere — write "2 of 27 measured, 25 inferred".

**Affected crawlable public routes (27)** — robots-disallowed prefixes already excluded
(`/chat`, `/login`, `/admin`, `/dashboard`, `/clients`, `/settings`, `/analytics`, `/intelligence`,
`/whatsapp`, `/omnichannel`, `/portal/login`, `/api/`, `/_next/` per `apps/mouth/src/app/robots.ts`):

`/agents` · `/assessment` · `/assessment/briefing` · `/book` · `/book/[chapter]` · `/dream` ·
`/edge` · `/exclusive` · `/interview_natalie` · `/lab/voice-concierge` · `/prime` ·
`/prime/proposal/[token]` · `/privacy` · `/tax-calendar` · `/terms` · `/v2` · `/v2/company/about` ·
`/v2/company/careers` · `/v2/company/press` · `/v2/cookies` · `/v2/news` · `/v2/privacy` ·
`/v2/terms` · `/verification` · `/visa-oracle` · `/visa-oracle/privacy` · `/visa-oracle/unlock`

**Worst single case — the whole `tax.balizero.com` subdomain.**
`apps/mouth/src/proxy.ts:342-354` rewrites `tax.balizero.com/` → `/tax-calendar` and every other
path to `/tax-calendar/*`. `apps/mouth/src/app/robots.ts` states in its own comment that
`tax.balizero.com` is a **deliberately public marketing surface** ("Adding either would de-index a
funnel we pay to rank"). Its metadata owner is
`apps/mouth/src/app/(tax-calendar)/tax-calendar/layout.tsx:8-9`, which sets `title` and no
`alternates`. So a marketed subdomain would be telling Google it is the homepage.

`/tax-calendar` is not orphaned: `"/tax-calendar"` appears as a literal in **7 places across 5
non-test files** — `components/blog/ArticleToolEmbed.tsx:7`, `app/(blog)/NewsPageClient.tsx:31`,
`app/(blog)/NewsPageClient.tsx:60`, `app/(blog)/services/page.tsx:82`,
`app/(blog)/contact/page.tsx:268`, plus the two rewrite lines in `proxy.ts`.
It is also **absent from `apps/mouth/src/app/sitemap.ts`** (the static list at lines 33-43 does not contain it).

**Zone:** VERDE — the fix is per-route `alternates` inside `apps/mouth/**` layouts.
Removing the root-layout `languages` block would touch the shared root layout and every route at
once; that is a one-PR-per-surface decision, not a sweep (memory item 103 pattern).

### 3.1a — Correction (2026-09-08, session 3): `/kbli-explorer` was mis-scored, and is now the worst case

The §2 row above was written from a `grep -l 'canonical'` walk over `apps/mouth/src`, and
`apps/mouth/src/app/kbli-explorer/layout.tsx` @ `6c6f25a9` was measured directly today: it declares
`title`, `description` and `openGraph`, and **no `alternates`**. It is one of the 27 (now 28)
routes affected by §3.1 — the grep-based walk credited it off the word "canonical" appearing
elsewhere in the route's subtree, not inside a real `alternates` object. §3.1's own text already
warned this could happen ("no equivalent guard for `alternates`"); this is that warning landing.

`/kbli-explorer` is the **sharpest instance of §3.1**, not a random member of the list: it is the
only one of the 28 that `sitemap.ts` (`staticPaths`, line 41) actively submits to Google, it names
itself as a distinct application in the sitewide `SearchAction` JSON-LD
(`components/seo/JsonLd.tsx:320`, `urlTemplate` = `${baseUrl}/kbli-explorer?q=…`) and in its own
`openGraph.url`, and it still served `<link rel="canonical" href="https://balizero.com"/>` — a
submitted URL whose own HTML asks Google to fold it into the homepage.

**Fixed in [PR #5920](https://github.com/Bali-Zero/Teman2/pull/5920)** (`seo/kbli-explorer-canonical`,
branched from `origin/main` @ `246902e086`, 5 commits ahead of this ledger's `6c6f25a9`): adds
`alternates: { canonical: `${baseUrl}/kbli-explorer` }` to the layout, plus a new guard,
`apps/mouth/src/app/metadata-canonical.test.ts`, that resolves every route `sitemap.ts` submits via
its own literal path arrays and asserts each carries an own-segment canonical — so a future static
sitemap addition can't ship the same silent-inheritance bug. Verified locally by stashing the fix:
exactly 2 of 6 guard tests fail, both naming `/kbli-explorer`. PR opened with auto-merge armed;
not yet merged as of this note.

The **affected-routes count in §3.1 is therefore 28, not 27**, until the PR above merges — the
original walk's false "yes" undercounted by exactly this one route. The other 27 in the §3.1 list
are unaffected by this correction.

### 3.2 — Six of 94 public routes carry any JSON-LD

Only `/[category]/[slug]`, `/services/[slug]`, `/kbli/[code]`, `/kbli-explorer`,
`/visa/second-home`, `/visa/second-home/[locale]` resolve to a file containing
`application/ld+json` or `schema.org`. Helpers that already exist and must be reused rather than
re-invented: `apps/mouth/src/components/seo/JsonLd.tsx`, `EnhancedJsonLd.tsx`, `DynamicJsonLd.tsx`,
`apps/mouth/src/components/kbli/KBLIStructuredData.tsx`, `apps/mouth/src/components/seo/HomepageFAQ.tsx`.

**⚠️ This count is a source-tree count, not a served-DOM count.** RSC Flight chunks escape quotes,
so `curl | grep` under-reports JSON-LD; a route counted "no" here may still render schema.
Confirm in the rendered DOM before writing "schema missing" anywhere outward-facing.

### 3.3 — `/visas` pagination (carried over, memory item 61)

Last locked step of the item-61 chain. Baseline **cancelled 14 Aug 2026** — the 12 Aug figure
(`grep -o 'href="/visas/' | wc -l` = 305) predates #4164 and must be re-measured before any work.
Not touched in this session.

---

## 4. Claim ledger

Rows live in Airtable (`appZbrB6QZopNJFrb`, table Claim Ledger) — memory item 75. This file records
only what it measured itself:

| Claim                                                 | Pattern                                       | Value                                | Layer | Commit     | Date       |
| ----------------------------------------------------- | --------------------------------------------- | ------------------------------------ | ----- | ---------- | ---------- |
| public-candidate routes                               | `find app -name page.tsx` minus `(workspace)` | 94                                   | 2     | `6c6f25a9` | 2026-09-07 |
| crawlable public routes without route-level canonical | canonical walk, robots-disallow filtered      | 27                                   | 2     | `6c6f25a9` | 2026-09-07 |
| public routes with JSON-LD in subtree                 | `application/ld+json`\|`schema.org`           | 6                                    | 2     | `6c6f25a9` | 2026-09-07 |
| `"/tax-calendar"` literal, non-test files             | quoted-literal regex over `apps/mouth/src`    | 7 in 5 files                         | 2     | `6c6f25a9` | 2026-09-07 |
| served commit                                         | `curl /api/health`                            | **not measured** — egress blocked    | —     | —          | 2026-09-07 |
| organic traffic, any route                            | Ahrefs / GSC                                  | **not measured** — Insufficient plan | —     | —          | 2026-09-07 |

Forbidden claims still binding (memory item 70): `Avg reply: 2 min`, `4.8h avg first-reply`.
Founding year is contested (2019 vs 2006) — must not appear in copy or schema until Antonello settles it.

---

## 5. Blocked on Antonello

| Item                                                                       | Since                  | Note                                                         |
| -------------------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------ |
| `<meta name="robots">` host-awareness on `kita.` (memory item 37, layer 2) | deferred, ~11 Aug 2026 | host-aware `generateMetadata()` would kill SSG on 193 routes |
| Auto-merge suspension (memory item 60)                                     | 13 Aug 2026            | all PRs stop at `gh pr ready`                                |
| TrustBand / AppTrustStrip GIALLO decision (memory item 85, 2nd)            | 18 Aug 2026            | decision never reached Subhi's inbox                         |

---

## 6. Kill list

| Idea                                                        | Decided             | Why not                                                                                                        |
| ----------------------------------------------------------- | ------------------- | -------------------------------------------------------------------------------------------------------------- |
| Ahrefs-driven internal-link cleanup for `kita.balizero.com` | memory item 38      | the 1,584-link figure did not reproduce; 14 sampled URLs → 0 real hrefs. Do not act before a source-URL export |
| Adding `noindex` to `visa.` / `tax.` subdomains             | `robots.ts` comment | both are marketed public funnels; blocking would de-index paid-for ranking                                     |
| Hand-written sitemap XML / `.htaccess`                      | stack               | Vercel + Next App Router; `sitemap.ts` and `robots.ts` are the only surfaces                                   |
| Sweeping the root-layout `alternates` block in one PR       | 2026-09-07          | one surface per PR, each carrying its own measurement (memory item 103 pattern)                                |

---

## 7. Next session — first three commands

```
curl -s https://balizero.com/api/health | grep -i commit
git fetch origin && git rev-parse origin/main
curl -s https://balizero.com/visa | grep -o '<link rel="canonical"[^>]*>'
```

The third is the standing positive control for every canonical probe: if it stops printing
`https://balizero.com/visa`, the probe method is broken and no zero from it counts.

**Session 3 (2026-09-08):** shipped [PR #5920](https://github.com/Bali-Zero/Teman2/pull/5920) —
`/kbli-explorer` canonical fix + the `metadata-canonical.test.ts` guard (§3.1a). Opened with
auto-merge armed; confirm it merged before treating `/kbli-explorer` as closed.

**Open next action from §3.1 (confirmed, not yet fixed):** add `alternates.canonical` to
`apps/mouth/src/app/(tax-calendar)/tax-calendar/layout.tsx`, add `/tax-calendar` to the static list
in `apps/mouth/src/app/sitemap.ts`, and extend `metadata-canonical.test.ts`'s
`SITEMAP_STATIC_PATHS` to cover it (the guard only sees paths `sitemap.ts` already submits, so
adding `/tax-calendar` to the sitemap and to the guard is the same PR). One surface per PR. Zone
VERDE.
