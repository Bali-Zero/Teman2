---
lane: L10 — The Accessibility and Performance Floor, 2026
seat: Claude Sonnet 5
date: 2026-08-31
sources_verified_live: 21
sources_from_memory: 7
---

## Executive summary

WCAG 2.2 (W3C Recommendation) is the enforceable floor today — not WCAG 3.0, which is still an incomplete Working Draft not expected as a finished standard before 2028, and whose own contrast algorithm is explicitly undecided (APCA was dropped from the draft in 2023). The four surfaces named in the brief are all touch-first, form-heavy, and paid — which means WCAG 2.2's newest AA criteria (target size, dragging, redundant entry, accessible authentication) bite directly on the VOA passport-upload flow and the Oracle's editable-answer form, and the EU Accessibility Act likely reaches Bali Zero the moment a euro-passport client pays via card on the VOA flow, regardless of where the company sits. Contrast should be computed twice — WCAG 2.x ratio (4.5:1 body / 3:1 large) for compliance, APCA Lc for how the color actually reads on a dark ground — because the two disagree in exactly the direction this brief's palette will tempt: light, thin text on a dark hero passes 4.5:1 on paper and reads washed-out in daylight on a 390px Android screen. Performance is not a separate workstream: 53% of mobile users abandon past 3 seconds, and Bali's real network is the accessibility floor, not a nice-to-have. And the fad to actively refuse is the accessibility overlay widget — it is now better evidence *against* a site than for it, with FTC enforcement behind that conclusion.

---

## 1. WCAG 2.2 status and the criteria that bite here

**The named example.** W3C's own WCAG 2.2 document, `https://www.w3.org/TR/WCAG22/` — VERIFIED-LIVE (fetched 2026-08-31): the page's own status line reads **"W3C Recommendation 12 December 2024."** That is the current enforceable normative document. WCAG 3.0 (the successor once called "Silver") is a different, much younger document: W3C's own intro page, `https://www.w3.org/WAI/standards-guidelines/wcag/wcag3-intro/` — VERIFIED-LIVE — states plainly **"WCAG 3 is currently an incomplete draft"** and **"WCAG 3 is not expected to be a completed W3C standard for a few more years,"** adding that **"WCAG 3 will not supersede WCAG 2 and WCAG 2 will not be deprecated for at least several years after WCAG 3 is finalized."** Secondary sources found in search (not independently fetched, so treat as directional only) put Candidate Recommendation around 2027 and final Recommendation no earlier than 2028, with the March 2026 draft reorganizing guidance into ~174 outcome-based requirements and a Bronze/Silver/Gold scoring model replacing pass/fail A/AA/AAA.

**The measurable rule — the six 2022+ criteria that touch a paid, form-heavy, touch-first flow**, each confirmed against its own W3C Understanding page (all VERIFIED-LIVE, fetched 2026-08-31):

- **2.5.8 Target Size (Minimum), AA** — `w3.org/WAI/WCAG22/Understanding/target-size-minimum.html`. Exact text: *"the size of the target for pointer inputs is at least 24 by 24 CSS pixels,"* with five exceptions — **spacing** (a 24px circle centered on each undersized target must not overlap an adjacent one), **equivalent** (an equally-functional bigger control exists elsewhere), **inline** (text-embedded links), **user-agent-controlled** (native date pickers), **essential** (dense map pins). 24×24 is the *floor*, not the target — see §4 below for the number you should actually design to.
- **2.4.11 Focus Not Obscured (Minimum), AA** — a focused element must not be *entirely* hidden by author content (sticky headers, cookie banners, chat widgets).
- **2.4.13 Focus Appearance, AAA** — `.../focus-appearance.html`. Exact text: the focus indicator must be *"at least as large as the area of a 2 CSS pixel thick perimeter of the unfocused component"* and have *"a contrast ratio of at least 3:1"* between the focused and unfocused states of the same pixels. AAA, so not mandatory even under EAA/ADA, but it is the right bar for a trust-sensitive product and cheap to hit.
- **2.5.7 Dragging Movements, AA** — `.../dragging-movements.html`. Exact text: *"All functionality that uses a dragging movement for operation can be achieved by a single pointer without dragging"* unless dragging is essential. Relevant if the Oracle ever ships a drag-to-reorder or slider control — it must have tap alternatives.
- **3.2.6 Consistent Help, A** — `.../consistent-help.html`. If a "talk to a human" / WhatsApp / FAQ mechanism exists, it must sit in the same relative position on every page of the flow, unless the user moves it.
- **3.3.7 Redundant Entry, A** — `.../redundant-entry.html`. Exact text: information *"required to be entered again in the same process"* must be **auto-populated or selectable**, not retyped. This is a direct hit on GARUDA VOA: passport number/name entered at question intake must not be asked again at payment.
- **3.3.8 Accessible Authentication (Minimum), AA** — `.../accessible-authentication-minimum.html`. Exact text: a *"cognitive function test (such as remembering a password or solving a puzzle) is not required for any step in an authentication process"* unless an alternative, mechanism (paste/autofill), object recognition, or personal-content option exists. This governs the VOA magic-link/OTP flow directly — copy-paste and autofill on the OTP field must work, and a memorized password should not be the only path.

**What to steal.** Treat 2.5.8/24×24, 3.3.7 and 3.3.8 as hard gates on the VOA intake→payment→tracking chain specifically, because that is the only surface here with a multi-step form and an auth step; the home page and the Oracle verdict screen barely touch them. Use GOV.UK Design System's own focus-state pattern as the concrete implementation of 2.4.11/2.4.13 — `https://design-system.service.gov.uk/get-started/focus-states/`, VERIFIED-LIVE: a **yellow background with a thick black border**, explicitly designed so *"the yellow has a high contrast with dark backgrounds and the thick black border has a high contrast against light backgrounds"* — i.e. one focus treatment that survives both a light card and a dark hero, which is exactly the two-tone territory this project's home page occupies.

**What to avoid.** The AAA-labelled criteria (2.4.12, 2.4.13, 3.3.9) are not legally required by EAA/EN 301 549 (which target AA) — don't let a designer gold-plate focus rings while a payment-flow AA criterion (redundant entry, auth) is still broken. And don't treat WCAG 3.0's Bronze/Silver/Gold language as something to design against yet — it has no fixed passing bar and is explicitly not going to obsolete 2.2 before this project needs to ship.

---

## 2. Contrast: WCAG ratio vs APCA — and where the ratio lies to you

**The named example.** The APCA project itself, `https://apcacontrast.com/`, VERIFIED-LIVE (fetched 2026-08-31): the algorithm measures an **Lc (lightness contrast) value** rather than a ratio, is *"polarity-aware"* (light-on-dark and dark-on-light are scored asymmetrically, matching how eyes actually perceive them), and its own documentation states outright that WCAG 2's ratio *"far overstates contrast for dark colors"* and **"cannot be used for guidance designing dark mode."** Recommended Lc thresholds per the same source: **Lc 90 preferred / Lc 75 minimum for body text**, **Lc 60 minimum for large/UI text**, **Lc 45 for headlines**.

**The measurable rule for status.** Adrian Roselli's contrast-tracking post, `https://adrianroselli.com/2026/04/wcag3-contrast-as-of-april-2026.html`, VERIFIED-LIVE (fetched 2026-08-31), is the sharpest and most current account: **"the contrast algorithm used in WCAG 3 is yet to be determined."** APCA was formally **removed from the WCAG 3 draft in July 2023** (exploratory content without working-group support inside six months auto-expires), and even APCA's own creator has acknowledged the versions that had circulated in drafts were *"early versions that were very obsolete."* Roselli's explicit recommendation — the one to follow here — is: **until WCAG 3 lands (he estimates 2030+), pick colors that pass both APCA and WCAG 2, or document any deliberate non-compliant choice.** Separately, secondary aggregator sources (not independently fetched — flag as directional) claim the DOJ has begun citing perceptual/APCA-style contrast reasoning in some ADA Title III settlement negotiations; I could not verify a specific settlement document, so treat this as unconfirmed pressure, not established law.

**Where 4.5:1 gives a wrong answer, concretely.** The textbook failure mode is exactly what a "hero on a dark ground" home page invites: thin, large, light-grey text on a near-black background. A pair like `#FFFFFF` text at 24px on `#1A1A1A` will clear WCAG 2's 4.5:1 easily (it's roughly 18:1), yet if the actual copy is a *lighter grey* (say `#999999`) at a *thinner* weight, WCAG 2 can still report a passing ratio around 5–6:1 while the perceptual read is markedly worse than the same grey on a white ground at the same ratio — because WCAG 2's formula does not account for font weight or polarity, only relative luminance. APCA would flag that combination with a materially lower Lc than its WCAG-ratio "pass" implies.

**What to steal.** Run every text/background pair on all three surfaces through *both* checkers before shipping: WCAG 2.x ratio for the number a lawyer or auditor will ask for, APCA Lc for the number that predicts how it actually reads on a cheap Android screen in Bali daylight. Any dark-mode or dark-hero panel (the home page's likely night-mode-adjacent hero, per the brief's own history of rejected night-mode rounds) is exactly the case APCA exists for — don't trust the ratio alone there.
**What to avoid.** Don't switch the whole design system to APCA-only thresholds and drop WCAG 2 ratios "because APCA is the future" — it has zero legal standing right now (no finalized standard cites it), and Roselli's piece is explicit that promoting APCA as *the* WCAG 3 standard while abandoning WCAG 2 compliance is itself a source of legal risk, not a hedge against it.

---

## 3. The legal environment: EAA, and what Indonesia actually requires

**The named example — EAA scope, direct from the directive.** `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32019L0882` (Directive (EU) 2019/882), VERIFIED-LIVE (fetched 2026-08-31): obligations apply to products placed on the market and **services provided to consumers after 28 June 2025**. The European Commission's own summary page, `https://commission.europa.eu/.../european-accessibility-act_en`, VERIFIED-LIVE, lists the in-scope service categories explicitly, and **e-commerce and banking services are named categories**; separate search-derived material (not independently fetched, flag as directional) describes EAA e-commerce as *"services provided at a distance, through websites... by electronic means and at the individual request of a consumer with a view to concluding a consumer contract"* — which is a precise description of the GARUDA VOA flow (four questions → price → payment → tracking) sold to any consumer, EU-resident or not, who happens to be an EU national booking a Bali trip from Paris or Berlin. The scope test in EAA case law and Commission guidance is about the **consumer's location/market**, not the seller's registration country — the directive targets goods and services *placed on the EU market*, and an EU citizen completing a card payment from within the EU on balizero.com is that market contact. **One real carve-out found live in the text**: `Article 4(5)` — *"Microenterprises providing services shall be exempt... "*, with microenterprise defined at `Article 3(23)` as **fewer than 10 employees and ≤ EUR 2 million annual turnover**. If Bali Zero's EU-facing service delivery entity is under that threshold, it has a live legal exemption worth confirming with counsel rather than assuming compliance is mandatory.

**The measurable rule.** Deadline already passed: **28 June 2025**. Penalties are set per Member State, not centrally in the directive (my WebFetch of the Commission summary page did not surface a figure; a search-derived secondary source claims up to €500,000 in some jurisdictions — unverified, treat as illustrative not precise). EAA's technical presumption-of-conformity route runs through **EN 301 549**, which itself incorporates WCAG 2.1/2.2 AA — so "meet WCAG 2.2 AA" is the practical compliance target, not a separate EAA-specific checklist.

**Indonesia.** Indonesia has **Law No. 8/2016 on Persons with Disabilities** (ratifying the UNCRPD) and **Government Regulation 70/2019**, which tasks the Ministry of Communication and Information with accessible public-communication standards — but this is oriented at *government/public* digital services, not a private legal mandate on commercial websites with a WCAG-referenced technical standard the way EAA has EN 301 549. I could not verify, live or from memory with confidence, that Indonesia's BSN has adopted ISO/IEC 40500 (the ISO edition of WCAG 2.0) as a binding SNI standard for private commercial sites — this is a genuine gap, flagged below, not a claim.

**What to steal.** Design to WCAG 2.2 AA as the baseline regardless of the legal question — it is the one standard that satisfies EAA (via EN 301 549), the practical expectation under ADA-adjacent US litigation culture that Bali Zero's international client base will bring with them, and it is simply good practice for a service that must not *feel* like a scam to a nervous first-time buyer. Treat the GARUDA VOA payment flow as the highest-risk EAA surface (it is unambiguously e-commerce to a consumer) and the informational home page as lower-risk.
**What to avoid.** Do not treat "we are an Indonesian company, EAA doesn't apply" as settled — the extraterritorial reach is real and the microenterprise exemption is the only clean out, and that needs an actual headcount/turnover check, not an assumption.

---

## 4. Touch, motor, and situational impairment — sizes, zones, and the bus test

**The named example and rule — three converging size floors.** WCAG 2.5.8 sets the **legal minimum at 24×24 CSS px** (with 24px spacing as the escape hatch for smaller targets — see §1). Apple's Human Interface Guidelines and Google's Material Design independently converge on a materially larger practical number: **44×44pt (Apple)** and **48×48dp (Material)**, both landing at roughly **9mm physical size** regardless of screen density — this is FROM-MEMORY (unverified live: both `developer.apple.com` and `m3.material.io` are JS-rendered SPAs that returned only page titles to the fetch tool, not body text — but this figure is extremely well-established across both design systems and multiple secondary sources agreed on it independently). Material's guidance additionally recommends **≥8dp spacing** between adjacent targets. The practical takeaway: **24×24 is the floor you must not go below; 44–48px is the size you should actually design every tap target to**, because that is the number both native platforms' own accessibility teams settled on after real usage data, not just the compliance minimum.

**One-handed reach on a 390px phone.** Smashing Magazine's thumb-zone piece, `https://www.smashingmagazine.com/2016/09/the-thumb-zone-designing-for-mobile-users/`, VERIFIED-LIVE (fetched 2026-08-31): it defines three zones — **natural/easy-to-reach** (roughly the bottom third to bottom half of the screen for a one-handed grip), an **in-between** middle zone, and a **hard-to-reach/stretch** zone (top of the screen, opposite the holding hand) — and states the guiding rule directly: *"keep frequently used links in the easy-to-reach zone and... infrequently used links in the hard-to-reach zone."* It also notes swipe-gesture targets should be **at least 45px tall and wide**. Context confirms this is not a fringe concern: the same research area (49% one-handed phone use, ~75% of touches thumb-driven — figures repeated across multiple secondary sources, FROM-MEMORY/unverified-precise) matches this brief's stated audience of people using 360–390px Android phones.

**The bus test — what a form must do.** On a moving vehicle, with one thumb, on a flaky connection: (1) primary CTA ("Continue", "Pay now") sits in the bottom third of the viewport, never top-right; (2) every input is ≥44px tall with a label that stays visible when the field is focused (not a placeholder that vanishes on tap — placeholder-as-label is a known Nielsen Norman anti-pattern, FROM-MEMORY); (3) numeric/passport fields trigger the correct mobile keyboard (`inputmode="numeric"`, `type="tel"`) so no manual keyboard-switch tap is needed; (4) nothing requires a drag, a precise pinch, or a double-tap (2.5.7 above); (5) the OTP/payment step supports paste and autofill (3.3.8 above) since typing a 6-digit code accurately on a bus is exactly the failure case that criterion exists for; (6) errors are inline, not only summarized at the top, because scrolling back up on a jolting bus to find "field 3 has an error" is a design failure, not a UX nicety.

**What to steal.** On GARUDA VOA specifically: put the price and the "Continue" button in the natural thumb zone on every step, size every tap target to 44–48px (not 24px), and make the passport-upload button itself large and single-purpose rather than a small icon-button. On the Oracle's "every answer still editable" promise, each editable field needs a large, thumb-reachable edit affordance — not a tiny pencil icon in a corner.
**What to avoid.** Decorative micro-icons as the *only* tap target for a critical action (edit, remove, retry) — common in "clean minimal" mockups, and precisely the pattern 2.5.8's spacing exception exists to patch over rather than a pattern to lean on.

---

## 5. Performance as accessibility

**The named example and rule.** Google's own Core Web Vitals documentation, `https://web.dev/articles/vitals`, VERIFIED-LIVE (fetched 2026-08-31): the three metrics and their "good" thresholds, measured **at the 75th percentile of page loads, mobile and desktop scored separately**:
- **LCP (Largest Contentful Paint) ≤ 2.5s**
- **INP (Interaction to Next Paint) ≤ 200ms**
- **CLS (Cumulative Layout Shift) ≤ 0.1**
"Poor" begins at LCP > 4s, INP > 500ms, CLS > 0.25 (secondary-sourced figure, matches the well-known published bands but not independently re-confirmed against the live page text in this session — treat the "poor" cutoffs as FROM-MEMORY, the "good" cutoffs above as VERIFIED-LIVE).

**Load time and abandonment — the numbers to design the payload budget against.** These are aggregate figures pulled from multiple secondary blog sources during search, not independently fetched from a single primary study — treat as directional, FROM-MEMORY: **53% of mobile users abandon a site past 3 seconds to load**; each **additional second of load time costs roughly 7% of conversions**; a joint Google/Deloitte analysis is widely cited (unverified primary) as finding **every 0.1s of improvement lifts retail conversion ~8%** and travel conversion ~10%. Given the stated audience — first-time visitors, often on slow connections, at night, already primed to suspect a scam — a slow-loading VOA payment page does not just lose a sale, it *confirms the suspicion* that this is not a legitimate operation. That reframes performance from an SEO concern into the same trust-signal category as the proof strip and licensed-notary claim already on the home page.

**The payload budget for a single-page mockup.** For a first-viewport-critical page on a real Bali 4G connection (effective throughput often closer to a slow-3G/fast-3G profile at night or in Kerobokan backstreets), set: **total page weight ≤ 500KB–1MB compressed** for first meaningful paint; **hero image ≤ 150–200KB** (WebP/AVIF, correctly sized for 390px not scaled down from desktop); **JS payload ≤ 150KB compressed** for the interactive shell, deferring anything not needed for the first CTA; **zero layout-shift-causing late-loading elements** above the fold (reserve space for images/ads/badges with explicit `width`/`height` or `aspect-ratio`) to protect CLS; and treat **LCP ≤ 2.5s on a throttled mid-tier Android profile**, not on a dev machine on wifi, as the actual acceptance test.

**What to steal.** Budget the home page hero and the VOA first screen against these numbers explicitly before any visual design review — a beautiful mockup that fails LCP on 4G is not a finished design, it's a desktop-only draft. Treat CLS discipline (reserved space for the trust-strip numbers, for images) as part of the "this is the real thing" trust signal, not a technical afterthought.
**What to avoid.** Autoplaying hero video or a heavy WebGL/canvas hero on the home page — a common "premium feel" fad that directly torches LCP and INP on the exact device profile this audience uses, and does so on the page whose entire job is to establish trust in the first three seconds.

---

## 6. The four user preferences a 2026 page must honour

All four confirmed live against MDN (VERIFIED-LIVE, fetched 2026-08-31):

```css
/* 1. Reduced motion — vestibular disorders, motion sickness */
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
}

/* 2. Contrast preference — low vision, situational glare (outdoor phone use) */
@media (prefers-contrast: more) {
  body { --text: #000; --bg: #fff; --border: 2px solid currentColor; }
}
/* values: no-preference | more | less | custom (custom matches forced-colors: active too) */

/* 3. Forced colors — Windows High Contrast Mode, screen-reader-adjacent low-vision tooling */
@media (forced-colors: active) {
  .button { border: 2px solid ButtonText; } /* box-shadow is force-stripped to none — don't rely on it for affordance */
}
.decorative-icon { forced-color-adjust: none; } /* opt an element OUT only when its color IS the information */

/* 4. Color scheme — OLED battery, night use, light sensitivity */
@media (prefers-color-scheme: dark) {
  body { background: #121212; color: #e6e6e6; }
}
```

Browser support on all four is "Baseline: widely available" per MDN — `prefers-reduced-motion` and `prefers-color-scheme` since ~January 2020, `prefers-contrast` since ~May 2022, `forced-colors` similarly mainstream. There is no excuse to ship without them in 2026.

**What to steal.** Given the audience is "often at night," `prefers-color-scheme: dark` is not optional — but per §2, verify every dark-mode pair with APCA, not just the WCAG ratio, precisely because dark mode is where the ratio lies. `prefers-reduced-motion` matters directly for the Oracle's decision-tree transitions (question-to-question animation) — offer an instant/cross-fade fallback, don't just shorten the same motion. `forced-colors` matters most on the VOA payment step, where a Windows-high-contrast user relying on system colors must still be able to see the price and the pay button's boundary once `box-shadow` gets stripped.
**What to avoid.** A JS-only dark-mode toggle that ignores the OS-level `prefers-color-scheme` signal on first load — forcing every dark-mode user to find and click a toggle before the page respects a preference their OS already told the page about.

---

## 7. The fad: accessibility overlay widgets

**The named example.** The Overlay Fact Sheet, `https://overlayfactsheet.com/en/`, VERIFIED-LIVE (fetched 2026-08-31): **over 1,030 signatories** — named as including W3C WCAG/ARIA spec contributors, in-house accessibility teams at Google, Microsoft, Apple, Shopify and others, disability-rights lawyers, and disabled end users — state plainly: *"full compliance cannot be achieved with an overlay"* and *"no overlay product on the market can cause a website to become fully compliant."* Listed failure modes, quoted from the same live-fetched page: automated alt-text is unreliable, "keyboard access is not reliably repaired," overlays are largely incompatible with modern JS frameworks and with Flash/Java/PDF/Canvas/media content, and — the part that matters most for a trust-driven product — disabled users quoted on the page describe overlays as making sites *"harder to use"* and *"a hellish experience"* for screen-reader users, to the point some actively block them.

**The measurable rule / evidence.** The regulatory consequence is now concrete and dated: the **FTC took action against accessiBe** (announced January 2025, final order **~USD 1,000,000** approved April 2025) for making *"false, misleading, or unsubstantiated"* ADA-compliance claims — this is FROM-MEMORY/unverified in this session (the FTC.gov press release returned HTTP 403 to the fetch tool and I could not independently confirm the exact figures live; treat the number as directional pending a direct check of ftc.gov). Search-derived secondary sources (also unverified live) claim UsableNet's 2024 report found **~25% of ADA digital-accessibility lawsuits targeted sites that already had an overlay installed**, and a 2026 AudioEye analysis put the figure at **38.5% of sued businesses already having some accessibility "solution" in place** — i.e., an overlay is now, if anything, evidence used *against* a defendant, not a shield.

**What to steal for Bali Zero.** Nothing — this is the one section of the brief that is purely "what to avoid," and it is worth stating as a hard rule precisely because a tempting shortcut exists: do not install an overlay widget (accessiBe, UserWay, or similar) on any of the three surfaces as a substitute for the WCAG 2.2 AA work in §1 and §4. If a genuine accessibility toolbar/preferences panel is wanted (font-size, contrast toggle), build it as first-party functionality wired to the CSS custom properties in §6 — a `prefers-contrast`/`prefers-color-scheme`-aware toggle the team controls — not a third-party script injecting DOM patches it doesn't understand into a payment flow that touches passport numbers and card payments.
**What to avoid — the tell.** Any vendor pitch that promises "WCAG/ADA compliance in one line of JavaScript," or markets itself primarily on lawsuit-defense rather than actual usability improvement, is the overlay pattern regardless of branding.

---

## What I could not verify

- **DOJ ADA Title III settlements citing APCA/perceptual contrast specifically** — appeared in search-derived secondary material; I could not locate or fetch a primary settlement document confirming this. Treat as unconfirmed regulatory pressure, not established precedent.
- **FTC v. accessiBe exact settlement figures and dates** (January 2025 announcement, ~$1M April 2025 final order) — ftc.gov returned HTTP 403 to the fetch tool; figures are from secondary sources only and should be confirmed directly against a Federal Register or ftc.gov press release before being cited to a client or in marketing copy.
- **UsableNet 2024 (~25% of lawsuits targeted overlay-equipped sites) and AudioEye 2026 (38.5% of sued businesses had a "solution" installed)** — both are search-derived, not independently fetched from the primary reports. Directionally consistent with the Overlay Fact Sheet's live-verified position, but the precise percentages are unconfirmed.
- **Apple HIG 44×44pt and Material Design 48×48dp target sizes** — both `developer.apple.com` and `m3.material.io` are JavaScript-rendered single-page apps that returned only page titles to the fetch tool, not body content. These are extremely well-established, widely corroborated figures, but this session did not obtain a live text quote from either primary source.
- **Baymard Institute mobile-cart-abandonment figures (70% overall, 23% attributed to complex checkout)** — the specific Baymard research URL returned 404; figures are from secondary aggregation only.
- **Load-time/conversion figures in §5** (53% abandon at 3s, 7% conversion loss per second, the Google/Deloitte 0.1s study, "average e-commerce conversion 3.05% under 2s vs 1.94% at 3–4s")** — all aggregated from multiple marketing/SEO blog sources during search, not independently fetched from a primary Google, SOASTA, or Deloitte report. Directionally very likely correct (the pattern is replicated across many independent studies over a decade) but the exact numbers should not be quoted to a client as precise without checking a primary source.
- **EAA per-country penalty amounts** (e.g. "up to €500,000") — not found on the live-fetched Commission summary page; penalties are set by each of the 27 Member States individually and were not enumerated in the sources this session could reach.
- **Whether Indonesia's BSN has adopted ISO/IEC 40500 (WCAG 2.0) as a binding SNI standard for private commercial websites** — could not confirm either way; this is a genuine open question, not a claim either direction.
- **Whether Bali Zero's actual EU-facing service delivery entity falls under or over the EAA microenterprise threshold (<10 employees, ≤€2M turnover)** — a factual question about the business, not a research question; needs an internal headcount/turnover check, ideally with counsel, before treating EAA as either binding or exempt.

---

## Hard checklist of numeric floors — any mockup in this project must pass

1. Every tap target ≥ **24×24 CSS px** (WCAG 2.5.8 legal floor); design to **44×44px minimum** in practice.
2. Adjacent small targets separated by ≥ **24px** center-to-center spacing where 24×24 itself can't be hit.
3. Primary CTA and price sit in the **bottom-third thumb zone** on every mobile step of GARUDA VOA and the Oracle verdict screen.
4. Text contrast passes **WCAG 2.x 4.5:1 (body) / 3:1 (large ≥18px or 14px bold)** *and* is checked against **APCA Lc 75+ (body) / Lc 60+ (large/UI text)** — both, not either.
5. Visible-focus indicator has **≥3:1 contrast** vs. its unfocused state and covers **≥ a 2px perimeter** of the component (2.4.13).
6. No functionality requires **dragging** without a single-pointer/tap alternative (2.5.7).
7. No information the user already gave (passport number, name) is asked for **twice** in the same flow without auto-populate/select (3.3.7).
8. Any authentication step (OTP/magic-link) supports **paste + autofill**, no memorization-only path (3.3.8).
9. **LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1**, all measured at the **75th percentile on a throttled mid-tier Android / 4G profile**, not desktop wifi.
10. First-viewport page weight **≤ 500KB–1MB compressed**; hero image **≤ 150–200KB**; critical JS **≤ 150KB compressed**.
11. All four preference media queries implemented and tested: **`prefers-reduced-motion`, `prefers-contrast`, `forced-colors`, `prefers-color-scheme`**.
12. **Zero third-party accessibility overlay widgets** on any surface, ever.
