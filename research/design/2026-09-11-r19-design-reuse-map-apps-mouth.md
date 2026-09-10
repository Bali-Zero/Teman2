---
date: 2026-09-11
domain: design
lane: website-r19 design reuse inside apps/mouth (topic 5 of the 2026-09-11 Mini session)
status: map for owner ruling — no product code changed, no flag, no deploy
adversarial_review: codex
adversarial_review_detail: codex exec gpt-5.6, read-only sandbox, 20 findings (18 applied, 2 partial, 0 rejected) — every contested claim re-verified on the source before disposition; log in §10
---

# R19 design reuse inside `apps/mouth` — surface-by-surface map

## 0. Mandate and boundary

- Owner decision 2026-09-11: `apps/mouth` stays the only live site. The standalone
  candidate `apps/website` (R19) stays **archived** — not resurrected, not landed on
  main, its branch not reopened. This document only extracts the design language.
  It is a targeted visual alignment, not a redesign.
- R19 source read for this map: `origin/codex/website-r19-integrated` at
  `6603d2913e` (2026-09-10), which is also the head of `codex/website-pro-continuation`.
  It is a superset of the M5 quarantine patch
  `.agent-receipts/quarantine-Users_balizero_nuzantara_.worktrees_infra-website-r19.patch`
  (596,458 B, 9,758 lines, 60 files, +8,743/−468 — stat read on M5 over SSH; every
  file in that stat exists on the integrated branch). Nothing was checked out; every
  R19 file was read with `git show`. The patch was never applied.
- Live baseline measured today with unauthenticated GETs (author's measurement, not
  reproducible from the repo): `/api/health` commit `8d743ab7c3`; sitemap 2,429 `<loc>`
  entries, 1,581 of them under `/kbli/` (the 2026-09-07 transplant audit counted
  2,423 / 1,581); `/journal` still returns HTTP 200 with title "Page not found".

## 1. What the R19 design language actually is (measured on the branch)

The skill summary says "warm paper, forest, copper, editorial typography". On the
branch there are two token layers, and the second one dominates every surface built
in the 2026-09-09 art-direction loops (Astra, Pro worktree):

| Layer | Where | Ground | Ink | Structure / action | Accent | Lines |
| --- | --- | --- | --- | --- | --- | --- |
| Base R19 | `src/app/globals.css` `:root` (6,513 lines), `components/entry.css` (header + hero), `styles/design-system.module.css` (`--bz-*`) | paper `#f6f3ed`, raised `#fffdf8` | `#202824`, muted `#646963` | forest `#253e33` (primary button, hover `#385345`) | copper `#a44725` (text links, 3 px focus ring, offset 5 px) | `#cecfc5`, strong `#aaaca2` |
| Direction A (09-09) | every component module: Footer, Team, Contact, Company, HomeTools, HomeJourney, SiteShell, `journal/*`, `services/*`, ZantaraEntry, `features/visa-oracle/atlas.css`, `features/visa-tools/visa-tools.css` | paper `#F7F4EE`, elevated `#FFFCF7`, wash `#EAE3D8`, footer `#EEE9E1` | slate `#1D2C3B`, muted `#58626B` | canopy slate-blue `#233D52` | copper `#A44B36` | `#DAD8D1`, strong `#A8ACA9` |

Hex census, reproducible: over the 33 stylesheets under `apps/website/src` on the
ref (`git ls-tree -r --name-only <ref> -- apps/website/src | grep '\.css$'`, each read
with `git show` and lower-cased), 22 contain both `#233d52` and `#a44b36`; forest
`#253e33` appears in exactly three files — `globals.css`, `components/entry.css` and
`styles/design-system.module.css` (`--bz-color-green`). So "forest" is the
header/hero/primary-button green of the base layer and of the `--bz-*` contract; the
structure colour of every 09-09 surface is slate `#233D52`. Both are R19.

Typography (Direction A): **Fraunces** variable serif at weight 450, letter-spacing
−0.035 em, display `clamp(48px, 5vw, 68px)/1`, section `clamp(38px, 4vw, 56px)/1.08`,
card 28 px/1.14, option 25 px/1.2; **Manrope** variable sans, body 400 15 px/1.75,
labels 650 at 9–12 px with 0.09–0.16 em tracking. Base layer: h1–h3 serif weight 400,
line-height 1.08, `h2 clamp(38px, 4.2vw, 64px)`, body 15 px/1.5, eyebrow 10 px /
2.2 px tracking uppercase 600, text link 13 px copper, controls min-height 48 px,
radius 0.25 rem (control) / 0.5 rem (card), 2 px on the Oracle, one restrained shadow.

Font assets on the branch: `fraunces-variable.ttf` 360,440 B and
`manrope-variable.ttf` 165,420 B, unsubset TrueType. `apps/mouth` self-hosts four
latin-subset woff2 files in `packages/core/fonts/files`: Inter 48,432 B, Cormorant
37,776 B, Montserrat 35,508 B, League Spartan 23,884 B. Inter and Cormorant are
loaded by the root layout on every route.

Composition and content rules carried by the R19 corner (`.agents/skills/website/SKILL.md`):
homepage order Hero → Services (four tool cards with index) → Reviews (Google link +
Adit portrait, no rating figure) → E-VOA → Second Home Studio → Portal → Journal →
Team (founder band, two portraits 88×104) → Contact (office panel) → Footer; header
sticky 88 px on paper, logo 62 px, centred 13 px nav, "My BALI ZERO" account link;
footer four columns (identity / Explore / Bali Zero / Connect) plus a base row. The
R19 candidate has **no floating contact control**: its QA-001 collision finding was
closed (`FIX_VERIFIED`) by removing it. Never invent prices, reviews, processing
times, client counts, testimonials, credentials or biographies. Faysha and Sahira are
excluded from the published roster by owner instruction (pinned by R19
`page.test.tsx`). Ari owns Second Home Studio, Surya owns E-VOA (both carry a project
link in `content/team.ts`; Subhi's Zantara role has none).

## 2. What `apps/mouth` is today (the target)

- Token architecture: Tailwind v4 + `@balizero/core/tokens` (primitives → semantic →
  operative → nine themes). Semantic vocabulary components read: `--surface-base /
  -raised / -sunken`, `--text-primary / -secondary / -tertiary`, `--border-subtle /
  -default / -strong`, `--nav-bg`, `--footer-bg`, `--cta-primary-bg`, `--accent-funnel`
  (remapped per `data-funnel`). Standing contract: `packages/core/tokens/*` is not
  edited per route; a route-scoped theme is an inline var set on the page wrapper,
  never on the root layout. Two such sets exist in `apps/mouth/src/lib/theme/`:
  - `rumahVars.ts` — Rumah Putih: paper `#f7f6f2`, ink `#16213a`, navy `#1e3863`
    (headings/accent/masthead), CTA red `#D01033`; applied on `/`, `/news`,
    `/[category]/[slug]`, `/team`, `/services*`, `/contact`.
  - `merahPutihDayVars.ts` — Merah Putih day (R4 spec 2026-08-27, "Cap Dinas v2"
    contest 2026-08-30): same paper and ink, red family `#C8102E / #D01033 / #c40020`
    as structure/action, navy retired; applied on `/visa/second-home` and the Studio.
    Its contrast table is guarded by `.github/workflows/merah-putih-day-contrast.yml`,
    which is a **required, path-filtered context** (`infra/required.d/contexts.json`);
    the file's own header still calls it advisory — that comment is stale.
- Route-local systems: `(visa-oracle)/visa-oracle/oracle.css` (1,642 lines, scoped
  under `.oracle-root`, light default `#f7f5ef` / canopy `#1f4d3d` / gold `#a8791f`
  and a dark theme, own toggle with `localStorage['visa-oracle-theme']` and a pre-paint
  bootstrap script; the Oracle does not use `NavShell` or the shared footer);
  `src/styles/kbli-theme.css` (`--kbli-*` declared at `:root`, anthracite `#1d273b`,
  terracotta `#d4845a`, periwinkle `#8b9cf7`, imported by `globals.css`).
- Fonts: Inter + Cormorant at the root layout; Montserrat on the `/kbli` and `/visa`
  layouts.
- Shared chrome: `NavShell` (`packages/core/components`, fixed 56 px glass bar reading
  `--nav-bg`; the home page mounts its own `NavShell` inside the page wrapper and
  paints it navy via `MASTHEAD_VARS`; the `accentBar` prop exists but no consumer in
  `apps/mouth` passes it, so no 3 px red rule renders anywhere), `v2/_components/Footer`
  (dark `--footer-bg`), `ZantaraFAB`, `MobileNav`. In the `(blog)` group the chrome is
  mounted by `(blog)/layout.tsx` as **siblings** of `<main>` (`BlogNav` + `Footer` +
  `ZantaraFAB`), so page-wrapper vars never reach it. `/kbli` and `/visa` mount their
  own `NavShell` in their layouts. The portal and kita have their own.
- Live design rules pinned by tests that R19 contradicts:
  - `e2e/persona-doors.spec.ts:67` — "exactly one red primary CTA on the page (P2)"
    on the homepage (`.cta-primary`, computed colour) and `:93` "doors band contains
    no red primary styling"; the same file also pins the WhatsApp destination. R19 has
    no red; its primary is forest or slate.
  - `e2e/blog-news-light.spec.ts` — the `.rumah-putih` wrapper must compute
    `rgb(247, 246, 242)` and the first `nav` must stay dark (luminance < 90) on `/news`
    and on one article; the article case does not check the footer.
  - `e2e/service-pages-light.spec.ts` — same wrapper/nav assertions on `/services`,
    `/services/visa` (the only detail slug sampled) and `/contact`; `/services` must
    stay price-free.
  - `merah-putih-day-contrast.yml` — required context on the Second Home files.

## 3. The collision that must be ruled before any coloured surface moves

Two owner rulings, both binding, disagree on the structure/action colour of the public
perimeter — and the perimeter includes the home:

| | Merah Putih (ruled 2026-08-27 Q2 + Q-R3.2, R4 token spec, contest 2026-08-30) | R19 (approved direction 2026-09-07 → 09-11) |
| --- | --- | --- |
| Ground | carta `#f7f6f2` | paper `#F7F4EE` / `#f6f3ed` |
| Ink | `#16213a` | `#1D2C3B` / `#202824` |
| Structure / action | red logo family `#C8102E / #D01033 / #c40020`; navy retires | slate `#233D52` (Direction A) or forest `#253e33` (base); copper for links; no red anywhere |
| Serif / sans | Cormorant ≥ 24 px / Inter; Montserrat killed from funnels | Fraunces / Manrope |
| Home | R4 §6 "band swap — the declared exception": hero and footer navy bands → merah bands, body carta unchanged, `FunnelCTAs` → merah-action, EN/ID toggle; identity header law names "GARUDA, VO, my, home" | paper header 88 px and paper footer, no band, no red |
| Funnels | GARUDA VOA, Visa Oracle ("identity graft": canopy → merah, slim carta header), `/visa`, Second Home, my.balizero.com | native Visa Oracle atlas (slate/copper) and a Second Home Studio fork (copper) |
| Debt | KBLI, `/visa` v1, tax, property = non-conforming, no deadline (R4 §7) | KBLI light re-skin exists on the branch |
| Live today | Second Home landing + Studio only; the Oracle is still canopy green / gold (neither system); home is Rumah Putih navy (neither system) | nothing |

The 2026-09-11 decision (mouth stays, extract R19 design) does not say whether the
later R19 approval supersedes R4 §6 on the home or R4's funnel prescriptions. That
inference is plausible but it is the owner's to make — ruling question Q1 in §7, and
the primary coordination point with topics 3 (Visa Oracle) and 4 (Second Home).

A second, R19-internal finding for the Oracle: `atlas.css` maps the four outcome
states onto two colours (`--oracle-state-eligible` and `--oracle-state-likely` both
to canopy; `--oracle-state-conditional` and `--oracle-state-likely-not` both to
copper, all four backgrounds to the same wash). The live `oracle.css` keeps four
distinguishable, WCAG-tuned state colours. Porting the atlas palette verbatim would be
a semantic regression, whatever Q1 decides.

## 4. Surface map

Legend: **Bring** = design language to port. **Frozen** = must not move in a design
PR. **Guards** = tests and checks that must stay green or be re-pinned in the same PR.

### 4.1 Home `/` — Wave A, priority 1

- Live: `(marketing)/page.tsx`, Rumah Putih + navy masthead, `HeroBlueprint` (team
  photo), `PersonaDoors` (four doors carrying `#visa/#kbli/#tax/#property`),
  `SocialProof` (six roster portraits + Google figures from `trust-figures`),
  `NewsHero` carousel, `TopicPills`, `LatestNews`, `Footer`, `ZantaraFAB`. Metadata
  claims "#1 Visa & PT PMA Experts", "Trusted by 5000+ clients since 2020" while
  `/team` says "since 2006" — a content lane matter, noted because the R19 content
  rule forbids unverifiable claims and the two pages disagree with each other.
- R19: `src/app/page.tsx` + `Entry.tsx` (paper header, illustrated hero with serif
  h1 and four category links), `Services.tsx` (four indexed tool cards),
  `Reviews.tsx`, `Evoa.tsx`, `SecondHome.tsx`, `Portal.tsx`, `HomeJournal.tsx`,
  `Team.tsx` (two founders), `Contact.tsx`, `Footer.tsx`.
- Bring: the Direction A token set as a third var set next to `rumahVars.ts`;
  Fraunces/Manrope (Q2); paper header and paper footer as a chrome variant (§4.8);
  section rhythm, eyebrow/text-link grammar, indexed tool cards; founder band (two
  portraits) in place of the six-portrait strip; Reviews block that links to Google
  without a stale count.
- Frozen: door hrefs (`/visa`, `/kbli`, `/taxes/gap`, `/property`) and their anchors;
  tool links (`https://visa.balizero.com/`, `/kbli`, `https://tax.balizero.com/`,
  `/property/eligibility`); `persona_door_click` and `home_whatsapp_cta` events and
  `SessionInit funnel="home"`; metadata + JSON-LD; `getAllArticles` +
  `content/homepage-layout.json` selection; the Login link; `ZantaraFAB` unless an
  explicit replace decision is recorded (R19 resolved its own floating-control
  collision by removing the control; mouth has to decide, not inherit).
- Guards: `e2e/persona-doors.spec.ts` (doors, anchors, single red CTA → Q4),
  `e2e/funnel-ctas.spec.ts`, `e2e/page.spec.ts`, `e2e/seo-smoke.spec.ts`,
  `npm run lighthouse`.

### 4.2 Team `/team` — Wave A, priority 2 (content deltas gated on Q3)

- Live: `(blog)/team/page.tsx`, five editorial sections resolved from the roster SSOT
  `src/data/team-roster.ts` (20 members, none with `publicListed: false`). Includes
  Sahira (setup section), Faisha (tax section), Kadek, Rina and a "Zero" entry with
  `nameOverride` and `/static/team/zero.jpg` (not in the roster).
- R19: `src/app/team/page.tsx` + `content/team.ts`: two founders, Ruslana as board
  member, thirteen members in four responsibility groups with project links for Ari
  (Studio) and Surya (E-VOA); homepage shows founders only; Faysha and Sahira
  excluded; Kadek and Rina absent too; no Zero entry.
- Bring: responsibility-group composition, portrait treatment, type scale, project
  links.
- Content deltas that are not design and need the owner (Q3): the four names present
  live and absent from R19 (Sahira, Faisha, Kadek, Rina), the Zero entry, and role
  labels that differ (Damar "Setup Team" in R19 vs marketing section live). Mechanism
  warning: `publicListed: false` only filters `PUBLIC_ROSTER`, which today feeds the
  book (`components/book/book-data.ts`); `/team`, `SocialProof` and
  `/v2/company/about` resolve people through `rosterBySlug`, which reads the full
  `TEAM_ROSTER`. An exclusion has to be applied in those three consumers or by making
  `rosterBySlug` honour the flag — either is a content change with three call sites,
  not an automatic propagation.
- Guards: no visual test today; the roster helpers have no test pinning the
  `publicListed` semantics.

### 4.3 Journal `/news`, `/[category]`, `/[category]/[slug]` — Wave B, priority 3

- Live: Rumah Putih; `NewsPageClient` (NewsHero carousel, four section cards with
  per-category accents `#c8102e / #d4a017 / #3a6dff / #22c55e`, search, grid);
  `ArticleClient` (MDX via `renderMDXBody`, TOC + FloatingToc, ReadingProgress,
  NewsletterSidebar, ArticleEngagement, views API). `/journal` is a soft-404.
- R19: `journal/JournalIndex.tsx` (lead + two secondary stories + compact archive,
  native search/category/pagination, `Card/Container/SectionHeading/TextLink`
  primitives); `journal/ArticleTemplate.tsx` (Fraunces h1, standfirst, byline and
  metadata block incl. reviewer/AI disclosure, 68 ch reading column, grouped marginal
  contents, sources footer, "View the published edition").
- Bring: index hierarchy; reader typography and column; metadata block; category
  eyebrow grammar; one accent instead of the rainbow of category colours in
  `NewsHero`, `LatestNews` and `NewsPageClient` (which accent: Q1).
- Frozen: `/news` as canonical (R19 itself treats "Journal" as a label), category
  aliases and 308s, article slugs, MDX pipeline, JSON-LD (Article / FAQ /
  Breadcrumb), `/feed`, `llms-full.txt` generation, views and newsletter APIs,
  `force-dynamic`, `?category=` / `?q=` server filters. Proposal: `/journal` → 308
  to `/news` to close the soft-404 the transplant audit already flagged.
- Guards: `e2e/blog-news-light.spec.ts` (wrapper paper + first nav dark; re-pin in the
  chrome PR), `e2e/article-404.spec.ts`, `e2e/category-alias-redirect.spec.ts`,
  `page.metadata.test.tsx` ×2, `layout.test.tsx`, `e2e/seo-smoke.spec.ts`.

### 4.4 Services `/services`, `/services/{visa,company,tax,property}`, `/contact` — Wave B, priority 4

Not in the six named surfaces, but it shares the `(blog)` shell and the R19 dossier
work is the most complete piece of the branch.

- Live: Rumah Putih, lucide icons, per-service accent, price-free index (#1263).
- R19: services hub + four dossier pages (`ServiceCatalog` 103 identities,
  `ServicePrice` from PricingTool, `ServiceJourneys`, `ServiceSections`), `Contact`
  with the office panel and `ContactOptions`.
- Bring: dossier layout, office panel, catalogue typography.
- Frozen: mouth slugs (`visa`, `company` — not R19's `immigration`,
  `company-setup`), price-free index, WhatsApp UTM builders, `trust-figures` source.
- Guards: `e2e/service-pages-light.spec.ts` (samples `/services`, `/services/visa`,
  `/contact`; re-pin chrome), `e2e/funnel-ctas.spec.ts`.

### 4.5 Visa Oracle `/visa-oracle` (+ `/privacy`, `/unlock`) — Wave C, priority 5, blocked on Q1

- Live: scoped `.oracle-root`, light (canopy green / gold) and dark, own toggle and
  bootstrap, Inter, living-tree tokens, four WCAG-tuned outcome colours; `layout.tsx`
  carries the SHADOW rationale in its metadata comment and `layout.test.tsx` pins the
  `noindex, nofollow` directive, title and description (the visible review copy lives
  in `OutcomeSheet`); engine adapter with 34 review codes (topic 3 today: walk census
  2 / 10 / 55 over 67 walks; the residual gap is copy in `engine-adapter.ts`). The
  Oracle conforms to neither ruling today: R4's "identity graft" (canopy → merah) was
  never built.
- R19: `features/visa-oracle/atlas.css` re-skins the **same class contract**
  (`.oracle-root`, `.oracle-topbar`, `.oracle-question`, `.oracle-option-card`,
  `.oracle-submit`, `.oracle-checklist`) and adds `atlas-*` chrome (brand topbar,
  kicker/title intro, 225 px route rail, junction labels); Direction A palette, Fraunces
  headings, 2 px radius, canopy → slate, gold → copper, Day/Night preserved. Its
  source pin `889935da` says 14 canonical core modules identical, 54 exact imports,
  31 adaptations — i.e. a presentation layer over the live engine, not a new engine.
- Bring, only if Q1 selects R19 for funnels: palette, type and radius **in every
  theme block of `oracle.css`** — the `:root`-like base, `[data-oracle-theme="light"]`,
  `[data-oracle-theme="dark"]` and the pre-hydration bootstrap block — because a block
  prepended at the top is overridden by the later same-specificity declarations. Verify
  both themes before and after hydration. The route rail is an optional follow-up. Keep
  four distinct state colours (§3).
- Frozen: everything under `_lib/`, `OracleShell` / `QuestionScreen` DOM and roles,
  the toggle storage key and bootstrap script, `noindex` + metadata,
  `/api/visa-oracle-unlock`, the same-origin evaluate boundary.
- Guards: the `_lib` suite (45 engine-adapter tests among them), `ThemeToggle`,
  `OracleShell`, `QuestionScreen`, `OutcomeSheet` tests, `layout.test.tsx`,
  `e2e/visa-oracle-v2.spec.ts`, `e2e/visa-oracle-fullstack.spec.ts`, backend
  walk-census test.
- Coordination: topic 3's worktree touches `.agents/skills/visaoracle/*` and
  `research/visa/…` only; a CSS-only re-skin has no file overlap, but future copy-deck
  work lands in `engine-adapter.ts`, which this map freezes for design PRs → sequence
  the two, do not parallelise on the Oracle.

### 4.6 Second Home `/visa/second-home`, `/[locale]`, `/studio` — Wave C, priority 6, blocked on Q1

- Live: the only implementation of the Merah Putih ruling; Cormorant; `StudioAtmosphere`
  procedural SVG with a determinism test (identical markup across fresh module loads,
  30 contours, decorative-only); plan codec, `localStorage['bz_shs_plan_v1']`,
  `#p=` fragment, verdict bands, 55–59 edge case, ≤ 6 WhatsApp bullets, no plan URL in
  the payload, positive-only deposit phrasing, sitemap guard, price 35,000,000 from
  PricingTool, `?lang=` on first load, `second-home-e33` 308 — all pinned.
- R19: a **fork** of the whole feature under `features/visa-tools/secondhome/` with
  its own engine copies (`rules.ts`, `plan-codec.ts`, `pricing-key.ts`,
  `whatsapp-bullets.ts`, `sequence.ts`, `timeline.ts`) restyled by `visa-tools.css`
  (copper-dominant).
- Bring: nothing by default. If Q1 selects R19: swap `MERAH_PUTIH_DAY_VARS` for the
  R19 set and the heading font; never import the R19 engine copy.
- Frozen: every invariant above. Retiring Merah Putih here also means editing the
  required-context snapshot (`infra/required.d/contexts.json`) and the contrast
  workflow in a coordinated PR, or the merge queue waits on a check that never reports.
- Guards: `StudioApp.test.tsx` + 12 component tests, `page.test.tsx` ×2, the contrast
  workflow.
- Coordination: topic 4's worktree touches `scripts/ci/npm_audit_gate*` only. No overlap.

### 4.7 KBLI `/kbli`, `/kbli/[code]` ×1,559, `/kbli/sectors*`, `/kbli/builder`, `/kbli/decoder`, `/kbli-explorer` — Wave D, priority 7, explicit go

- Live: anthracite theme at `:root`, Montserrat, hero on `#141416`, `FunnelFrame`,
  semantic badges (PMA open/restricted/closed, risk levels, transition map colours),
  `kbli-gold-all.json` precedence, `KBLIStructuredData`, `ZantaraChat`; 1,581 sitemap
  URLs = 65 % of the site's inventory.
- R19: `features/kbli/kbli.module.css` light re-skin (paper `#f7f4ee`, greys) and
  `kbli-navigator` retained routes.
- Bring, last: shell only — paper chrome, hero on paper with Fraunces, card surfaces;
  badge colours re-tuned only for AA on paper, meanings unchanged.
- Frozen: data files, routes, `/kbli-navigator` 308, sitemap generation, JSON-LD,
  `ZantaraChat`, PMA/risk semantics, gold precedence.
- Guards: the twelve `components/kbli/*.test.tsx`, `e2e/seo-smoke.spec.ts`, sitemap
  count invariant (1,581), Lighthouse on `/kbli` and a `/kbli/[code]` sample, Search
  Console watch after promote. R4 already classes KBLI as non-conforming debt with no
  deadline; nothing forces it, and it carries the largest visual distance and the
  highest SEO exposure.

### 4.8 Shared chrome — `NavShell`, `Footer`, `MobileNav`, `ZantaraFAB`

- Bring: a paper variant of the header (88 px sticky, paper ground, `#dddcd4` rule,
  62 px logo, centred 13 px nav, account link) and of the footer (`#eee9e1`,
  four columns + base row).
- How, honestly: two colour overrides are not enough. `NavShell` is a fixed 56 px
  glass bar; an 88 px sticky paper header is a **variant** (a `variant` prop on
  `NavShell` with the default byte-identical, or a marketing header component inside
  the route group). Mounting: on `/` the home page owns its `NavShell` and footer, so
  the wrapper vars reach them (that is how `MASTHEAD_VARS` works); in the `(blog)`
  group the chrome lives in `(blog)/layout.tsx` as siblings of `<main>`, so the
  variant and the `--nav-bg` / `--footer-bg` overrides must be applied on a wrapper in
  that route-group layout — which is allowed (it is not the root layout) but converts
  the chrome of every `(blog)` route at once (`/news`, articles, `/team`, `/services*`,
  `/contact`). Never by editing `packages/core/tokens`, never by importing R19's
  `globals.css` (its bare `header`, `nav`, `img`, `body` selectors are exactly what
  R19's own `legacy-css-adoption.md` says must not be imported wholesale).
- Guards: `NavShell.test.tsx` (extend for the variant); the nav-luminance assertions
  in `blog-news-light` and `service-pages-light` pin dark chrome and must be re-pinned
  in the converting PR.

## 5. Priority criterion (proposal)

Order = visibility × visual distance ÷ ruling dependency ÷ regression exposure.

- **Wave A** — home, team, shared chrome on `(marketing)` + `(blog)`. Needs Q1 part
  (a) for the home chrome and accents (R4 §6 prescribes red bands there), Q2 (fonts)
  and Q4 (single-red CTA rule); Q3 only for the roster content. Because the `(blog)`
  chrome is converted at the layout, Wave A already repaints the chrome of the Wave B
  routes and must re-pin both light specs; body-level work on those routes stays in
  Wave B. What is ruling-free in Wave A: layout, rhythm, type scale, founder band,
  responsibility groups, paper ground.
- **Wave B** — journal/news + reader, services + contact bodies. Needs Q1 (a) for the
  category accent, nothing else new.
- **Wave C** — after Q1 (b): Visa Oracle theme blocks; Second Home var-set swap or
  no-op.
- **Wave D** — after an explicit go and a performance baseline: KBLI shell.

Mechanism for every wave: one var set `apps/mouth/src/lib/theme/r19Vars.ts` (working
name) with the same scoping contract as `rumahVars.ts`, a computed contrast table in
its header and a required path-filtered CI guard modelled on
`merah-putih-day-contrast.yml`; two fonts via `next/font/local` in
`packages/core/fonts`, subset to latin woff2 (target ≤ 60 KB each, from 360 / 165 KB
TTF) and loaded by the converted route-group layouts, not the root — which means a
converted route carries Inter + Cormorant (root) **plus** Fraunces + Manrope until the
root fonts are revisited, so the budget in §6 is per route, not per file; components
ported one at a time as CSS modules under the route group; no global stylesheet import.

## 6. Non-regression bar (proposal for Zero and Astra)

Per surface, before promote:

1. **Route identity** — HTTP status and `<title>` identity for every route of the
   surface (the `/journal` soft-404 class is caught by title, not by status); sitemap
   `<loc>` count unchanged from the 2026-09-11 baseline (2,429 total / 1,581 kbli)
   unless a listed redirect changes it; every in-page anchor resolves.
2. **Functional** — `npm run test:ci` and the surface's e2e specs green; analytics event
   parity test green; no `_lib/`, engine, data or API file in the diff. Note that
   `scripts/ci/change_map.py` only selects which test legs run; a blocking allowlist
   check for design PRs (CSS, modules, theme var sets, route-group layouts, e2e
   re-pins) is new work and needs its own negative test.
3. **Visual and accessibility** — 360 / 390 / 768 / 1280 / 1440 CSS px without
   horizontal overflow; every text/background pair computed ≥ 4.5:1 (R4 doctrine:
   computed, never estimated); visible focus; keyboard menu with Escape; skip link;
   fixed-widget collision pass (the class R19's QA-001 documented).
4. **Performance** — Lighthouse LCP / CLS / transfer on `/`, `/news`, one article,
   `/team`, `/kbli`, one `/kbli/[code]` not worse than the pre-wave baseline; fonts
   self-hosted, no new external host; per converted route, font bytes ≤ baseline +
   the two subset files, and a decision on the root Inter/Cormorant preload recorded
   before Wave B.
5. **Content** — no new number or claim; roster from the SSOT; roster exclusions only
   after Q3; `noindex` and metadata unchanged on Oracle and VOA.
6. **Release** — one PR per wave; Vercel STAGED build; Mini autopromote
   (`mini.vercel_autopromote`, about 12 minutes measured); prove-live browser
   screenshots at 390 and 1440 for each converted route, plus `/visa-oracle` and
   `/visa/second-home/studio` as untouched controls; rollback = promote the previous
   READY build, with the autopromote held during the window.

## 7. Ruling questions for Zero (closed, four)

- **Q1 Which ruling wins where.** (a) Home and `(blog)` chrome and accents: R4 §6
  (red hero/footer bands, merah-action CTAs, navy retired) or R19 (paper header and
  footer, slate/copper accents, no red)? (b) Funnels — Visa Oracle, Second Home,
  GARUDA: (b1) R19 slate/copper, Merah Putih retired and Second Home repainted;
  (b2) funnels keep their **current live systems** (Second Home = Merah Putih; Oracle =
  canopy green / gold, R4's graft still pending in its own lane) and R19 goes on
  home / team / journal / services; (b3) R19 tokens with the red family as the single
  action colour. Recommendation: **(a) R19, (b2) now**, (b1) only after a rendered
  side-by-side of the Oracle in both — Merah Putih is the one ruling that was
  implemented, contrast-guarded and contest-tested, and the R19 atlas collapses four
  outcome states into two colours.
- **Q2 Typography.** Adopt Fraunces + Manrope on converted surfaces (retiring
  Cormorant/Inter there and Montserrat on funnels, consistent with R4), or keep
  Cormorant/Inter and port only the scale? Recommendation: **adopt**, subset to latin
  woff2 before shipping, with the per-route budget of §6.4.
- **Q3 Roster content on the live site.** Four people are live and absent from the
  R19 roster (Sahira, Faisha, Kadek, Rina — the first two by recorded owner
  instruction, the last two without a recorded reason), plus the "Zero" entry on
  `/team`. Which of the five stay on public pages? Recommendation: apply the recorded
  instruction for Faysha and Sahira in the three `rosterBySlug` consumers; keep Kadek
  and Rina unless the owner says otherwise; the Zero entry is the owner's call (the
  codename is public-safe, the photo is a real face).
- **Q4 The P2 "one red primary CTA per page" rule (2026-06-11).** Does the R19 primary
  colour replace red as the single conversion colour on converted surfaces, or does the
  red CTA remain the one exception on paper? Recommendation: the R19 primary replaces
  red; re-pin `persona-doors.spec.ts` to "exactly one primary CTA" by token, not by
  hue, keeping its WhatsApp-destination assertion.

## 8. What this document does not claim

No rendered comparison was produced. No product code changed. R19 acceptance figures
quoted (test counts, checkpoints) are the R19 lane's own receipts, not re-run here.
Live figures (sitemap, health commit, `/journal` response) are the author's
unauthenticated measurements of the day and are not reproducible from the repository.
The M5 patch was read only through `git apply --stat` over SSH; its content was read
from the integrated origin branch that carries the same files.

## 9. Evidence index

- R19: `origin/codex/website-r19-integrated` — `.agents/skills/website/SKILL.md`,
  `references/state.md`, `apps/website/src/app/globals.css`,
  `src/styles/design-system.module.css`, `src/styles/brand-fonts.css`,
  `src/components/*.module.css`, `src/components/journal/*`,
  `src/features/visa-oracle/atlas.css`, `src/features/visa-tools/*`,
  `src/content/team.ts`, `src/content/destinations.ts`,
  `docs/design-system/{API,legacy-css-adoption}.md`,
  `docs/reviews/2026-09-07-production-transplant.md`, `docs/qa/acceptance-matrix.md`,
  `docs/handoffs/2026-09-09-*.md`.
- Live: `apps/mouth/src/app/(marketing)/page.tsx`, `(blog)/{layout,team/page,news/page}.tsx`,
  `(blog)/_components/BlogNav.tsx`, `(blog)/[category]/[slug]/{page,ArticleClient}.tsx`,
  `(visa-oracle)/visa-oracle/{layout,layout.test,page}.tsx` + `oracle.css`,
  `visa/second-home/{SecondHomeLanding,studio/StudioApp}.tsx`, `kbli/{layout,page}.tsx`,
  `src/styles/kbli-theme.css`, `src/lib/theme/{rumahVars,merahPutihDayVars}.ts`,
  `src/data/team-roster.ts`, `packages/core/tokens/{semantic,themes/light,themes/editorial}.css`,
  `packages/core/components/NavShell.tsx`,
  `e2e/{persona-doors,funnel-ctas,blog-news-light,service-pages-light}.spec.ts`,
  `infra/required.d/contexts.json`, `.github/workflows/merah-putih-day-contrast.yml`,
  `scripts/ci/change_map.py`, `README.md` (promotion), `vercel.json`.
- Rulings: memory `project_design_study_loop_garuda_visa_oracle_2026_08_27` (Q2, Q-R3.2,
  R4 §9, R7 registry), `research/design/2026-08-27-r4-identity-merah-putih-token-spec.md`
  (§4 identity header, §6 home band swap and Oracle graft, §7 perimeter),
  `research/design/2026-08-30-merah-putih-rendering-contest-result.md`.

## Adversarial review (§10)

Seat: codex (`codex exec`, gpt-5.6, read-only sandbox, run from this worktree with the
R19 ref available). 20 findings; every L1 was re-verified on the source by the author
before disposition. Tally: 18 applied, 2 partial, 0 rejected.

| # | Class | Finding (abridged) | Disposition |
| --- | --- | --- | --- |
| 1 | L1 HIGH | `publicListed:false` does not hide anyone from `/team`: `rosterBySlug` reads the full roster; only the book uses `PUBLIC_ROSTER` | Applied — §4.2 mechanism warning, Q3 reworded |
| 2 | L1 MED | Forest also lives in `design-system.module.css` | Applied — §1 census lists three files |
| 3 | L1 MED | "20 of 24 modules" not reproducible; denominators differ | Partial — census re-run with the published command: 33 stylesheets, 22 with both hexes; the seat's own 27/19 used a narrower file set |
| 4 | L1 MED | The single-red-CTA test is `persona-doors.spec.ts`, home-only, and also pins WhatsApp | Applied — §2, §4.1, Q4 |
| 5 | L1 MED | Light specs check the `.rumah-putih` wrapper and first `nav`, not `body`; article case skips the footer; services sample only `/services/visa` | Applied — §2, §4.3, §4.4 |
| 6 | L1 HIGH | R4 does not exclude the home: §6 prescribes red hero/footer bands there | Applied — §3 table and text, §5 Wave A, Q1 split into (a)/(b) |
| 7 | L2 HIGH | Page-wrapper vars cannot reach the `(blog)` chrome (siblings in the layout); two colours do not make an 88 px header | Applied — §4.8 rewritten (variant + route-group layout mounting) |
| 8 | L1 MED | No consumer passes `accentBar`; the blog has no red rule | Applied — §2 |
| 9 | L1 HIGH | The Merah Putih contrast workflow is a required context, not advisory | Applied — §2, §4.6 (coordinated retirement) |
| 10 | L2 HIGH | A token block at the top of `oracle.css` is overridden by later theme blocks | Applied — §4.5 |
| 11 | L1 MED | `layout.test.tsx` pins robots/metadata, not a visible SHADOW notice | Applied — §4.5 |
| 12 | L1 MED | StudioAtmosphere test is determinism, not byte-pinning; 12 component tests, not 13 | Applied — §4.6 |
| 13 | L2 MED | Kadek and Rina are also absent from R19; the delta is larger than two names | Applied — §4.2, Q3 |
| 14 | L1 LOW | Subhi has no project link | Applied — §1, §4.2 |
| 15 | L1 LOW | QA-001 is `FIX_VERIFIED` on the ref (control removed) | Applied — §1, §4.1 |
| 16 | L2 MED | Wave A's chrome change reaches Wave B routes; team Q3 dependency missing | Applied — §5 |
| 17 | L2 MED | Q1(b) "Merah Putih stays" misdescribes the Oracle, which is neither system | Applied — §3 live row, §4.5, Q1 (b2) |
| 18 | L2 MED | `change_map.py` selects tests; it is not a blocking allowlist | Applied — §6.2 |
| 19 | L3 MED | Two 60 KB fonts do not bound the budget while root loads Inter/Cormorant | Partial — §5 and §6.4 now state a per-route budget and a root-font decision before Wave B; the root layout itself stays out of scope |
| 20 | L2 LOW | Live numbers and the M5 patch stat are unverifiable from the repo | Applied — §0 and §8 label them as the author's measurements |

Checks the seat reported as held without findings: 2 (atlas state collapse and shared
class contract) and 5 (Second Home fork with engine copies).
