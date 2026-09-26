---
date: 2026-06-10
domain: operations
client_case: none (internal — balizero.com frontend, Mythos Round 1)
sources:
  - apps/mouth route tree (find, 131 page.tsx, verified 2026-06-10)
  - packages/core/analytics/funnel-view.ts (read in full)
  - GA4 property via ga4-analytics MCP (28d window, hostName + pagePath + eventName)
  - GSC API sites.list probe (service account .secrets/google-credentials.json)
  - NotebookLM notebook_list (86 notebooks)
  - ~/Desktop/frontend-map/index.html (atlas, 2026-06-10, summarizes Subhi UX Audit v5.2.0)
  - gh api branch protection (required status checks, main)
---

# MYTHOS · Phase 0 — Ground-State Report

**Charter:** MYTHOS CHARTER v2 §6 Phase 0 · **Lane:** `research-only` (no gate required to produce)
**Author:** Mythos (Fable 5) · **Machine:** Air-M5 · **Date:** 2026-06-10
**Every claim below was verified by a tool call on 2026-06-10. Items marked UNVERIFIED are explicitly flagged.**

---

## 1. Access preflight checklist

| Resource | Status | Evidence / caveat |
|---|---|---|
| **GA4** (property covering balizero.com) | ✅ **WORKS** | `ga4-analytics` MCP returns live data. **3 caveats below (§4) — the property is shared across 7 hostnames and daily data begins 2026-05-21.** |
| **GSC** | ✅ **WORKS** (script path) | Service account `.secrets/google-credentials.json` → `sites.list` returns `https://balizero.com/ (siteOwner)`. Note: `sc-domain:balizero.com` is **siteUnverifiedUser** → only the URL-prefix property is queryable; subdomain coverage limited. No MCP — access is via Python script (e.g. `scripts/gsc_resubmit_sitemap.py` pattern). |
| **NotebookLM NB-2/3/4/5** | ✅ **WORKS** | `notebook_list` verified: NB-2 Visa (`cff93ab0`, 110 src) · NB-3 Company (`933509f9`, 283 src) · NB-4 Tax (`d4b2eedb`, 162 src) · NB-5 Property (`d9438180`, 143 src). NB-7 Editorial (`f51ab8a0`, 99 src) also available. |
| **Brand cortex** | ✅ **WORKS** | `~/.claude/skills/bali-zero-brand/` present (constitution, tokens, voice, layouts, anchors). |
| **Brand tokens file** | ⚠️ **PARTIAL** | `packages/core/tokens/themes/editorial.css` exists (2.3 KB) but contains **only the navy surface system** (`#0c1f3a → #1e3863`). Red `#FF2D4C`, purple `#8b5cf6`, green `#25D366`, Cormorant/Inter are NOT in this file — they live elsewhere (Tailwind config / component-level). **Stage-A task: locate and inventory the full token surface before any design-language work.** |
| **PricingTool** | ❌ **MISSING** (RBAC) | Both `search_service_pricing` AND `get_all_prices` MCP tools refuse: *"requires role in [company_setup, visa_specialist]; caller has 'unknown'"*. Mythos has no pricing read access. **Needs: role grant for this caller, or a sanctioned backend API path.** Until then any pricing claim = unverified. |
| **CI required-check list** | ✅ **WORKS** | `gh api .../branches/main/protection`: 11 required checks — E2E Tests (Playwright), MCP Server Tests, Detect Secrets, Backend Tests (Python), Bandit, CodeQL (js+py), root-guard, **Frontend Tests (Next.js) (mouth, true)**, Canary self-test + incremental mutation, verify-the-verifiers. |
| **`sancho/*` perimeter** | ✅ **WORKS** | 5 existing remote branches incl. `sancho/d1-funnel-tracking`, `sancho/company-stub-pages`. |
| **Vercel preview workflow** | ⚠️ **PARTIAL** | `apps/mouth/vercel.json` + `.github/workflows/vercel-build-guard.yml` exist. End-to-end preview-URL flow **UNVERIFIED until the first sancho PR** — verify then. |
| **Subhi UX Audit v5.2.0 (8 Jun, 18 pages)** | ❌ **MISSING** (original) | Not found in repo, `~/Desktop`, or Drive (`gdrive_search` = 0 results). **What exists:** the atlas `~/Desktop/frontend-map/index.html` (2026-06-10) embeds its summary — scores, central thesis, 4-tier roadmap (§3). **Action: request the original 18-page document from Subhi.** Downstream claims sourced from the audit are marked *atlas-mediated*. |

**Preflight verdict: 7 WORKS · 2 PARTIAL · 2 MISSING.** Nothing blocks Stage A; the two MISSING items have named owners/actions.

---

## 2. Route & funnel inventory (the real `apps/mouth`)

### 2a. Route tree — charter errata

- **131 `page.tsx` routes** verified by `find` (charter said ~123 — correct to 131).
- **The live homepage `/` is served by `apps/mouth/src/app/(marketing)/page.tsx` — NOT `v2/page.tsx`.** The charter's "live homepage is `apps/mouth/src/app/v2/`" is wrong as stated: `/v2` is a **separate, `robots: noindex` design-preview route** that shares the same `v2/_components/*` (the marketing page imports `HeroBlueprint`, `FunnelFeature`, `SocialProof` etc. from `../v2/_components/` — verified imports at `(marketing)/page.tsx:6-10`).
- Homepage section order **verified — matches the charter**: SessionInit + NavShell → HeroBlueprint → 4× FunnelFeature (visa/kbli/tax/property) → SocialProof → NewsHero → TopicPills → LatestNews → Footer → ZantaraFAB (`(marketing)/page.tsx:76-153`).
- Indicative split (arithmetic from verified 131): ~8 marketing/legal · ~27 client portal (`/portal/*`) · ~68 internal workspace (`(workspace)/*`) · **~28 public funnels + blog + special** (`/visa*`, `/kbli*`, `(tax-calendar)`, `/property/*`, `(blog)`, `(assessment)`, `(book)`, `/chat`, `/prime`...). Exact per-route classification belongs to the Stage-A blueprint, not this report.

### 2b. Channel funnel routes (all verified on disk)

| Channel | Routes | Notes |
|---|---|---|
| Visa | `/visa` (branch selector) → `/visa/clock`(+`[hash]`), `/visa/match`(+`[hash]`) | Decision-tree entry confirmed |
| Company/KBLI | `/kbli`, `/kbli/[code]` (1,563 SSG), `/kbli/sectors`(+`[id]`), `/kbli-explorer` (AI chat) | |
| Tax | `/(tax-calendar)/tax-calendar` | Single public tool page |
| Property | `/property/eligibility` | Single public tool page |
| AI layer | `/chat` (public Zantara), `ZantaraFAB` on homepage | |

### 2c. FUNNEL_EVENTS taxonomy (`packages/core/analytics/funnel-view.ts`, read in full)

- **32 events** (not 40): visa 9 · kbli 8 · tax 6 · property 7 · hero 2.
- Defects found in the taxonomy itself:
  - `property_cta_clicked` **and** `property_cta_click` both exist (legacy duplicate — see GA4: both fire).
  - Tax has **no** `tax_chat_question` (visa/kbli/property have one).
- Transport: `trackFunnelEvent()` fires `gtag(...)` **and** POSTs to `/api/analytics/funnel-event` (silent-fail by design). GA4 wired via `@next/third-parties` + Consent Mode v2 in `layout.tsx`; measurement ID from `NEXT_PUBLIC_GA_MEASUREMENT_ID` (env, not hardcoded — correct).

---

## 3. Subhi UX Audit — what we actually have (atlas-mediated)

From the atlas (`~/Desktop/frontend-map/index.html`, built 2026-06-10 from the audit):

- Scores: **UX 72/100 · UI 78/100 · AIDA Action 6/10 · LCP 3.5 s+ desktop · trust density 9/10**.
- Diagnosis: *brand & content are category-leading; the funnel breaks at the Action stage* — **6 competing CTAs**, hero CTA goes to a scroll anchor not a booking/handoff, est. 15–25 % intent drop, attribution broken.
- Central thesis: collapse to **one CTA hierarchy** (Primary = WhatsApp red · Secondary = AI tools purple · Tertiary = content). "Until there's ONE optimisable funnel entry, no CRO/A-B test is even possible."
- 4-tier roadmap (IMMEDIATE/SHORT/MID/LONG); parts of IMMEDIATE **already shipped**: hero→WhatsApp + footer links (PR #1205), home WA tracking (PR #1216). One item needs Antonello, not Subhi: **PPJK/DJP license data** for cert badges.
- Audit scope = homepage funnel only; portal/workspace explicitly excluded; treats Zantara as a widget to demote (the atlas itself flags this as the open page-vs-conversation tension → charter §4).

---

## 4. Measurement baseline (GA4, 28d window 2026-05-13 → 06-09)

### 4a. ⚠️ Three property-level caveats (load-bearing for every future "before/after")

1. **One GA4 property collects 7 hostnames.** 28d sessions: `balizero.com` **913** · `kita.balizero.com` **580** (59 users — the team's workspace) · `zantara.` 57 · `my.` 23 · **`localhost` 11 (dev pollution)** · `tax.` 7 · `prime.` 3. Aggregate, unfiltered numbers mix staff + dev + public. **Convention from today: the public scoreboard is `hostName == balizero.com`, always.** (Recommend to Subhi, who has Editor: GA4 internal-traffic/dev filters; until then, filter at query time.)
2. **Daily data begins 2026-05-21** — the 28d query returned only 20 daily rows (May 21 → Jun 9). Cause unverified (likely measurement-ID/property cutover). Trend windows older than May 21 are not available; 56-day comparisons won't be possible until mid-July.
3. **WA-handoff instrumentation is young**: home WhatsApp tracking landed ~PR #1216 (June). Near-zero WhatsApp events (below) may be instrumentation recency, not true zero — a tier-1 *instrumentation-verified* pass on every CTA event is the first Stage-B prerequisite.

### 4b. Public traffic (hostName = balizero.com, 28d → effectively 20 days)

- **913 sessions / 823 users ≈ 33 sessions/day ≈ 230/week.**
- Top public pages: `/` 263 · `/living/dengue-alert-2026` 75 · `/visa` 26 · `/chat` 20 · `/services/visa` 17 · `/kbli` 15 · `/news` 15 · `/visa/match` 9 · `/property/eligibility` 6 · `/tax-calendar` 3 — plus a long editorial tail (`/visas/*`, `/business/*`, `/taxes/*`, `/living/*` articles at 2–11 sessions each).
- Channel-tool sessions (28d): **Visa tools ≈ 37** (26+9+2) · **KBLI ≈ 75–90** (entry 15 + `[code]` long tail; `kbli_code_viewed` = 304 events = strongest tool signal on the site) · **Tax tool = 3** · **Property tool = 6**.

### 4c. Conversion events (28d, whole property)

| Event | Count | Reading |
|---|---|---|
| `kbli_code_viewed` | 304 | KBLI Navigator is the most-used interactive asset |
| `kbli_chat_question` / `kbli_search` | 32 / 30 | |
| `visa_consult_click` / `visa_cta_click` | 20 / 16 | |
| `tax_dashboard_viewed` / `tax_consult_click` / `tax_cta_click` | 18 / 6 / 2 | |
| `property_*` (all) | ~8 | incl. the cta_click/cta_clicked dup |
| `hero_cta_read_dispatch` / `hero_cta_book_call` | 8 / 4 | |
| **`*_whatsapp_cta` (ALL channels)** | **2** (property only) | **The measured handoff baseline is ~zero.** visa/kbli/tax = 0 in 28d (see caveat 4a-3) |

Also present: `app_wizard_step_completed` 89, `app_form_submitted` 45, `app_branch_selected` 14 — an `app_*` family **outside** the FUNNEL_EVENTS taxonomy (assessment wizard). Taxonomy and reality have drifted; reconcile in Stage A measurement design.

---

## 5. Measurement-power audit (the honesty table, charter §D)

With ~230 public sessions/week and a primary-CTA click baseline of ~2 % (≈70 funnel CTA clicks / 913 sessions):

- A 2-arm A/B test detecting a **+30 % relative lift** on a 2 % conversion needs ≈ 8,500 sessions/arm → **≈ 17,000 sessions ≈ 70+ weeks at current traffic.** Per-phase `statistically-powered` claims (tier 3) are **unreachable** on any single channel and on the homepage itself.
- **Operative tiers for Round 1A: tier 1 (instrumentation-verified) + tier 2 (directional 28/56-day windows) — for every channel.** Tax (3 sessions) and Property (6) cannot even support tier-2 channel-level trends yet; their scoreboard is the *feeder* metric (GSC impressions/clicks growth) until traffic exists.
- Consequence (per charter §D decision rule): Stage-B phases ship on *instrumentation-verified + directional + Soul rubric + qualitative review*. Nobody should promise a "proven lift" — and this report is the pre-registered evidence of why.

| Channel | 28d tool sessions | 28d conversions (measured) | Realistic tier |
|---|---|---|---|
| Visa | ~37 | 36 cta/consult, 0 WA | 1 + weak 2 |
| Company/KBLI | ~75–90 | 304 code views, 8 cta, 0 WA | 1 + 2 (usage signals) |
| Tax | 3 | 8 | 1 only (feeder = GSC) |
| Property | 6 | ~8 | 1 only (feeder = GSC) |
| Site-wide composite | 913 | ~70 CTA + 12 hero | 2 (28/56d windows) |

---

## 6. Defect ledger (found during Phase 0 — routed by lane)

| # | Finding | Severity | Lane / owner |
|---|---|---|---|
| D1 | **Hardcoded prices on the live homepage** — `FunnelFeature.tsx:103,136,168,198` ("$350", "$1,850", "$220", "$850"), rendered by `(marketing)/page.tsx`. Violates Golden Rule 11 (PricingTool only). Also: `FUNNEL_PRICING_HREF` points at `visa.balizero.com/pricing`, `tax.balizero.com/pricing` etc. — destinations not verified live. | **P1** | **Gated-structural decision in Stage A** (price display = funnel surface; also blocked by PricingTool RBAC, see D2). NOT silently changed. |
| D2 | PricingTool MCP refuses role `unknown` → Mythos cannot read canonical prices | P1 | Operator (Antonello): grant role or sanction a backend read path |
| D3 | GA4 property mixes 7 hostnames + localhost dev traffic; no internal-traffic filter | P2 | Subhi (GA4 Editor): define filters; Mythos: hostname-scoped queries from today |
| D4 | GA4 daily data begins 2026-05-21 (cause unknown) | P3 | Ask Subhi what changed ~May 21 |
| D5 | `property_cta_clicked` vs `property_cta_click` duplicate event | P3 | `ungated-safe-fix` candidate (tiny PR, with event-allowlist note) |
| D6 | No `tax_chat_question` event; `app_*` wizard family outside FUNNEL_EVENTS | P3 | Stage-A measurement design |
| D7 | Original 18-page Subhi audit not on disk/Drive | P3 | Request from Subhi |
| D8 | `editorial.css` holds only navy tokens; red/purple/green/type anchors live elsewhere | P3 | Stage-A token inventory |

---

## 7. Charter errata (corrections to feed back into the charter)

1. Live homepage = `(marketing)/page.tsx`; `v2/` is a noindex preview sharing components (§2a).
2. Route count = 131, not ~123.
3. FUNNEL_EVENTS = 32 events, not an unstated count; taxonomy has the §2c defects.
4. "Editorial theme tokens in `editorial.css`" is partial — only the navy surface system lives there.
5. "~697 articles" and Visa-funnel "owner likes it" remain **UNVERIFIED** by Phase 0 (article count not recounted; qualitative claim) — carried as leads.

---

## 8. What Phase 0 hands to Stage A

1. **Decision pack inputs ready:** real route tree, real funnel events, real (tiny) traffic baseline, power tiers per channel, Subhi thesis (atlas-mediated), the Zantara-as-widget-vs-surface tension already framed by the atlas.
2. **Pre-Stage-A asks (blocking only what they touch):** PricingTool role (D2) · original audit doc (D7) · GA4 filter convention with Subhi (D3).
3. **Next deliverable (this is what gets gated):** Stage-A decision pack = §4 fork decision + IA blueprint + charisma design language + rubric — built on this ground state.
4. Until the gate: `ungated-safe-fix` (D5 + WCAG/a11y/speed items from Subhi's IMMEDIATE tier not yet shipped) and `research-only` (Tax/Property study via NB-4/NB-5 + GSC demand analysis) lanes proceed.
