---
date: 2026-08-31
domain: design
client_case: none
sources: 365
---

# Web design sixteen-lane corpus — 2026-08-31

## What this is

A sixteen-lane research programme on web design for Bali Zero's three public surfaces (home page,
GARUDA VOA landing, Visa Oracle verdict), run in one day (2026-08-31) against a single shared brief.
Twelve lanes (L01–L12) are web-grounded — each ran with live fetch tools against a shared `CONTRACT.md`
covering colour, typography, depth/material, price display, the verdict screen, checkout, anti-scam
signals, social proof, the hero, accessibility, bilingual EN/ID localisation, and motion. Four lanes
(X-agy, X-codex, X-kimi, X-qwen) are cross-family seats — Gemini 3.1 Pro, GPT-5.6 (Codex), Kimi K3, and
Qwen 3.8 Max — run on the same brief as an independent, deliberately blind panel (none of the sixteen
lanes could see any other lane's work). A dedicated eighteenth pass, `FACT-voa-government-fee.md`,
resolved a three-way contradiction the lanes produced about the e-VOA fee. Everything is then read
together in `SYNTHESIS.md` (≈17.7k words): 11 cross-lane convergences, 9 contradictions with rulings,
a 116-gate hard floor, eleven design knobs, a set of decisions only the owner can make, and — most
important for anyone building on this later — a full accounting of what the corpus could **not**
verify.

This capture exists because the programme was produced in `/tmp`, which is session-scoped and would
otherwise have been lost. The files here are byte-identical copies of the originals (see Verification
below); nothing was edited, reformatted, or "improved."

## Aggregate source ledger, as the lanes themselves declared it

**254 `VERIFIED-LIVE`, 111 `FROM-MEMORY (unverified)`** — summed directly from each report's own
frontmatter (`sources_verified_live` + `sources_from_memory`), not restated from `SYNTHESIS.md`'s own
count (independently re-added here and it matches). This is a declared, self-reported ledger, not an
external audit — see the WARNING section below on what "verified" does and does not mean for the four
cross-family seats.

| Report | Seat | Verified-live | From-memory |
|---|---|---:|---:|
| L01-colour | Claude Opus 5, xhigh | 23 | 5 |
| L02-typography | Claude Sonnet 5 | 27 | 5 |
| L03-depth-material | Claude Sonnet 5 | 22 | 2 |
| L04-price | Claude Opus 5, xhigh | 24 | 8 |
| L05-verdict | Claude Opus 5, xhigh | 22 | 6 |
| L06-checkout | Claude Sonnet 5 | 15 | 9 |
| L07-anti-scam | Claude Opus 5, xhigh | 26 | 3 |
| L08-social-proof | Claude Sonnet 5 | 13 | 4 |
| L09-hero | Claude Sonnet 5 | 17 | 5 |
| L10-accessibility | Claude Sonnet 5 | 21 | 7 |
| L11-localisation | Claude Sonnet 5 | 19 | 7 |
| L12-motion | Claude Sonnet 5 | 17 | 6 |
| X-agy | Gemini 3.1 Pro (High) | 5 | 0 |
| X-codex | Codex / GPT-5 | 0 | 10 |
| X-kimi | Kimi K3 (Moonshot AI) | 3 | 11 |
| X-qwen | Qwen 3.8 Max | 0 | 23 |
| **Total** | | **254** | **111** |

## Files

- `CONTRACT.md` — the shared brief every lane received: client/surfaces context, the three prior
  rejected AI-design rounds (and the lesson — "whatever the brief supplies, the models return"), the
  four-part report shape required (named example / measurable rule / what to steal / what to avoid),
  sourcing rules, and the exact frontmatter contract.
- `SYNTHESIS.md` — the cross-lane synthesis. Read this first if you only read one file: it contains
  the 11 convergences (C1–C11), 9 contradictions with rulings (K1–K9), the §3 hard floor (116 gates
  across contrast, targets, motion, performance, type, bilingual, forms/checkout, the money moment, the
  verdict screen, copy/legal), §5 the eleven knobs, §6 owner-only decisions, and §7 — the honesty
  section this INDEX draws its WARNING from.
- `dossier.html` — the owner-facing presentation of the synthesis, published as a Claude Artifact for
  Antonello to review visually rather than as raw Markdown.
- `reports/FACT-voa-government-fee.md` — a dedicated verification pass that resolved a three-lane
  contradiction on the e-VOA government fee (see "Three facts" below).
- `reports/L01-colour.md` — colour systems, night/dark as the hard case. Dark-theme lightness-ramp
  arithmetic, chroma envelope for a "black" surface, APCA proof that `#C8102E` cannot be ink on a dark
  ground, daylight-flare collapse of tone-based elevation, the indigo→purple gradient as the 2026 AI
  tell.
- `reports/L02-typography.md` — typeface choice as a "safe average" trap, discrete step-tables over
  `clamp()`, `tabular-nums` + `id-ID` formatting, measured +40% Indonesian button-label length,
  variable-font CLS discipline, kinetic scroll-text as the fad to avoid.
- `reports/L03-depth-material.md` — what replaces flat without shadows: lightness steps, hairlines,
  grain: borrowing the *principle* of Liquid Glass / Material 3 Expressive while rejecting the
  expensive, accessibility-risky *implementation* (real-time blur).
- `reports/L04-price.md` — how a price is displayed. Partitioned pricing makes buyers underestimate the
  total (the opposite of Bali Zero's intuition); the FTC's itemization-must-not-overshadow-total rule;
  Wise's "Included in IDR amount" device; per-locale number formatters; the two-visa-tier price as a
  timeline, not a menu.
- `reports/L05-verdict.md` — the verdict screen as a second-person sentence, not a badge; the full
  price split at the verdict as the strongest anti-scam device; naming the actor ("Immigration
  decides") instead of hedging; showing editable inputs, never a confidence percentage; refusing
  artificial "analysing…" delay.
- `reports/L06-checkout.md` — checkout on Indonesian rails: QRIS as display-and-wait, QRIS Cross-Border
  excluding the actual GARUDA VOA audience's home countries, Virtual Account as async/leave-the-page,
  Baymard's 2026 abandonment numbers mapped onto the four-question flow, wait-psychology for the
  multi-day Immigration decision.
- `reports/L07-anti-scam.md` — looking legitimate in a scam-saturated market. Chrome's own padlock
  retirement; the live autopsy of `indonesia-evoa.com` (Immigration-named copycat, still live, with
  unfilled template variables in its own About page); price-before-data as the sharpest discriminator;
  why the star-rating strip is now a liability under the UK DMCC Act.
- `reports/L08-social-proof.md` — social proof and evidence of competence. Why 4.9★/693 reviews is
  already near-optimal and should not be pushed toward 5.0; why an uninspectable rating reads as
  fabricated; "Filed this month: 47 KITAS, 9 PT PMAs" as a rare, checkable-feeling proof asset; the
  2025–2026 legal risk of testimonials (FTC fake-review rule).
- `reports/L09-hero.md` — the hero and first screen. Zero of four fetched competitor homepages use a
  dateline/masthead on their converting hero; problem-first copy's real conversion evidence, but only
  for problem-aware audiences; above-the-fold geometry on a 390×700 viewport; hero video as the
  single most reliable way to blow the performance budget on this audience's devices.
- `reports/L10-accessibility.md` — the accessibility and performance floor, 2026. WCAG 2.2 as the
  enforceable floor (not WCAG 3.0, still a Working Draft); dual contrast computation (WCAG ratio +
  APCA); the EU Accessibility Act's likely reach the moment a euro-passport client pays by card; why
  accessibility overlay widgets are now evidence against a site, not for it.
- `reports/L11-localisation.md` — bilingual EN/ID and what Indonesian users actually expect. Why Bali
  Zero should read as the government/bank register (imigrasi.go.id, oss.go.id, BCA) and never the
  marketplace register (Tokopedia/Shopee); language names over flags; the danger of "all-inclusive"
  having no one-word Indonesian equivalent; formal Bahasa voice examples from BCA and OSS.
- `reports/L12-motion.md` — motion and micro-interaction. The converging timing bands (micro-feedback
  ≈50–150ms, transitions ≈150–400ms, nothing habitual over ~500ms); INP ≤200ms as the metric that
  actually gates Core Web Vitals; named-step skeletons over spinners for passport-upload/payment;
  plain-CSS `@starting-style`/`animation-timeline: scroll()` coverage; scroll-jacking as the fad to
  kill on sight.
- `reports/X-agy.md` — Gemini 3.1 Pro's cross-family pass: the 2026 bifurcation between award-winning
  WebGL sites and high-converting structural-grid sites, and the "Bank-Grade Ledger" direction
  (brutalist, thermal-receipt styling). Direction paper — see WARNING below before citing its specifics.
- `reports/X-codex.md` — Codex/GPT-5's adversarial pass on the money moment: don't charge at the
  provisional verdict, "supported" must never silently mean "approved," a refund matrix + price lock +
  case ledger, a named human before payment. Zero live sources by lane design — a design artefact, not
  evidence.
- `reports/X-kimi.md` — Kimi K3's pass on why a page feels expensive, calm, or cheap: "expensive" as a
  ratio (empty pixels, few type sizes, one accent, disciplined alignment), ten devices. 3 of 14 sources
  verified — see WARNING below.
- `reports/X-qwen.md` — Qwen 3.8 Max's pass on what Western-trained design gets wrong about Asian
  users: density as a service during verification and a crime during action (the Gojek split); banning
  fake urgency; red as a legitimate primary-CTA color locally; resumable-by-case-ID flow design. Zero
  live sources by lane design.

## Three facts established or corrected during the programme

**1. The e-VOA government fee is IDR 500.000.** Legal basis: PP 45/2024 §III.B.1.c, quoted verbatim on
`evisa.imigrasi.go.id/front/info/evoa` ("The Visitor Visa fee is IDR 500.000,00") and on
`imigrasi.go.id/wna/daftar-visa-indonesia/B1` ("Biaya visa B1 Rp 500.000 (untuk 30 hari)"). Three lanes
disagreed before `FACT-voa-government-fee.md` resolved it, and *why* is itself the finding: L04 fetched
the **bare root** `https://evisa.imigrasi.go.id`, which returns HTTP 200 with a literally **empty
body**, and correctly reported "no fee figure at all" for that URL — the figure lives on the inner page
`/front/info/evoa`, which L04 never reached. L05 had the right number (IDR 500.000) but only via a
secondary news source (The Bali Sun) and explicitly flagged it as unconfirmed. L07 verified a
*different*, real figure (IDR 1.500.000, the 60-day extendable visit visa) on the official FAQ, could
not find the e-VOA fee at all, and explicitly refused to publish its own IDR 500.000 recollection
("do not publish on my word"). Live caveat as of 31 Aug 2026: a **proposed** two-tier revision
(Rp 750.000 online / Rp 1.000.000 manual), announced by the DGI on 12 Aug 2026, is **not yet enacted**
— no amending PP found, both official portals still show Rp 500.000 on re-fetch the same day as this
research.

**2. The brand red is `#C8102E`.** Verified at `skills/bali-zero-brand/tokens.json:45`
(`"value": "#C8102E"`) and `packages/core/tokens/semantic.css:89`
(`--status-critical: #c8102e;`). `#CE1126` — the hex X-qwen assumed and flagged as unverified in its
own report — appears in **no brand-token file**. (Corrected 2026-08-31: an earlier draft of this index
said it appears nowhere in the repository; that was wrong. It occurs twice, as a hard-coded accent in
two export templates — `apps/backend-rag/scripts/templates/kbli_magazine.html:105` and
`kbli_presentation.html:208` — neither of which is a brand-token surface. Two agents on this programme
disagreed on this grep and the false one was believed first; the claim below is the one that survives
re-checking, and it is the stronger claim anyway.) L01's entire colour arithmetic (the APCA Lc −24
finding on a dark ground, the chroma ceiling, the hue-distance measurements in §3.1 of `SYNTHESIS.md`)
assumed `#C8102E` and is therefore the one grounded in the repo's actual token, not X-qwen's guess.

**3. `molina.imigrasi.go.id` is NXDOMAIN.** Confirmed independently via `dig` and `nslookup` against
the Tailscale resolver — no A/AAAA record, SOA-only NXDOMAIN response from `imigrasi.go.id`'s own
nameservers. Immigration's own Yogyakarta regional-office page names it as "the only official e-VOA
site," but that hostname has never resolved. "MOLINA" is the eVisa system's **internal application
name**, not a domain — it appears verbatim as `<meta property="og:site_name" content="MOLINA">` in the
raw HTML of `evisa.imigrasi.go.id`'s own pages. The system's real, live home is
`evisa.imigrasi.go.id`.

## WARNING — do not build on these without re-checking first

Reproduced from `SYNTHESIS.md` §7.1 ("Red flags — a future session must NOT build on these"). This is
not the full §7 (see `SYNTHESIS.md` directly for §7.2 directional-only numbers, §7.3 sources that
defeated the whole corpus, and §7.4 genuine open questions) — it is the subset judged dangerous enough
to repeat here.

1. The e-VOA government fee was contested until `FACT-voa-government-fee.md` — see "Three facts" above
   for the resolution and the live 2026-08-12 pending-revision caveat.
2. The brand red was contested until this capture — see "Three facts" above for the resolution.
3. **X-agy's target-size claim is wrong on the standard.** It states "Minimum 48×48dp… aligning with
   WCAG 2.2 SC 2.5.8." WCAG 2.2 SC 2.5.8 is **24×24 CSS px**, as L10 verified directly against the W3C
   Understanding page. 48dp is Material's recommendation, not the criterion. Use L10's numbers; do not
   cite X-agy's.
4. **Every APCA figure in L01 came from a locally reimplemented APCA-W3 0.1.9** (constants from
   memory, validated against only two canonical reference values). L01's own instruction: "Every Lc
   number in this report should be re-run through https://apcacontrast.com before it is used as a
   gate."
5. **L01's entire ambient-flare model is the lane's own engineering estimate**, not a measurement. The
   structure is sound (WCAG's 0.05 flare term, `E·ρ/π` Lambertian reflectance), but ρ = 4.5%, 400 nits,
   and the 10,000/20,000 lux figures were never measured on a real device. The daylight collapse of
   tonal hierarchy (contradiction K2 in `SYNTHESIS.md`) rests on these numbers. Replace with a
   photometer reading on an actual target device before quoting any ratio.
6. **`indonesia-evoa.com`'s current legal status is unverified beyond the 2022 naming.** L07 verified
   the 2022 Immigration statement and that the site is live today with the quoted content — not
   whether it has since been sanctioned or become a lawfully-disclosed intermediary. In any published
   copy, call it "the site Immigration named in 2022, still live today, with these characteristics" —
   never "a scam site."
7. **The live `balizero.com` strings quoted in `SYNTHESIS.md` §4.1** were read through summarising
   fetchers by both L07 and L09, and the two lanes disagreed on the dateline arithmetic. `curl` the
   page directly before acting on any of them.
8. **Whether "Filed this month: 47 KITAS, 9 PT PMAs" is auto-generated or hand-edited is unknown** —
   L09 flagged this as outside its scope. It is load-bearing for `SYNTHESIS.md` contradiction K4.

## On the four cross-family seats' verification status

Reproduced from `SYNTHESIS.md` §7.5. Read these as **direction papers, not evidence** — the label
"cross-family panel" describes where they came from, not how well-sourced they are:

- **X-agy** (Gemini 3.1 Pro): five `VERIFIED-LIVE` citations, all **bare homepage fetches with no
  quoted text** — this does not meet the CONTRACT's own sourcing bar ("fetch the page and quote it").
  Four findings where the web lanes deliver six to ten. Strong on direction, unreliable on specifics
  (see WARNING #3 above — it states WCAG SC 2.5.8 as 48×48 when the criterion is 24×24).
- **X-codex** (GPT-5.6/Codex): **zero** live sources; all ten citations `FROM-MEMORY` by lane design.
  Its state table is a design artefact, not evidence.
- **X-kimi** (Kimi K3): 3 verified of 14. Every product reference in its §1 and §3 — The Row, Stripe,
  Linear, Toss, Nod Young, BASAO/Tea'stone, MUJI/Hara — is `FROM-MEMORY`, and its maroon hex ranges are
  "reasoned proposals, not tested values." Its own explanation for the fifteen identical night modes
  ("training-data gravity") is, in its own words, "a reasoned hypothesis about model behavior, not an
  established finding."
- **X-qwen** (Qwen 3.8 Max): **zero** live sources; 23 `FROM-MEMORY`, and every named interface is a
  pre-2026 snapshot of a product that "change[s] quarterly." Its own closing note is the correct way to
  read it: the recommendations "stand on logic and named precedent, not on studies — and they are each
  testable within a week of launch."

## Where the doctrine derived from this lives

This corpus is raw research, not doctrine — per CLAUDE.md §15, it stays ad-hoc auditable and is never
auto-promoted. The doctrine distilled from it lives (or is being built, by sibling agents, at the time
of this capture) at:

- `skills/bali-zero-brand/surfaces/web.md` — the web-surface addition to the brand cortex.
- `scripts/lint_web_surface.py` — the CI-enforceable gate for the §3 hard floor.

Both are referenced here, not created or edited by this capture.
