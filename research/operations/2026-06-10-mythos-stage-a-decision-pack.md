---
date: 2026-06-10
domain: operations
client_case: none (internal — balizero.com frontend, Mythos Round 1, Stage-A gate artifact)
sources:
  - Phase-0 ground-state report + GSC demand baseline + exemplar study (same branch, 2026-06-10)
  - origin/main verified 2026-06-10 14:00 WITA (incl. Subhi PRs #1205 #1216 #1255 #1257 merged this morning)
  - CTA inventory verified in code ((marketing)/page.tsx, HeroCTA.tsx, FunnelFeature.tsx, Footer.tsx)
  - Brand cortex ~/.claude/skills/bali-zero-brand/ (constitution.md 423 lines, tokens.json, voice/forbidden-phrases.md)
  - Live probes: balizero.com/pricing (200, "Pricing Insights" editorial), visa.balizero.com (200, untracked in GA4)
---

# MYTHOS · Stage-A Decision Pack — Round 1A

**This is the Law-5 gate artifact (charter §6 Stage A).** It asks Subhi (operator) and Antonello (principal) to approve four things: the paradigm fork, the IA direction, the design language + rubric, and four secondary-token proposals. Until approval, no `gated-structural` code is built. The approval checklist is §5 — everything else is the defense.

> Ground-truth note: local M5 main was 4 commits behind origin/main during research; every load-bearing claim below was re-verified against **origin/main** and live URLs. Subhi's IMMEDIATE tier is substantially **shipped as of this morning**: hero CTA → direct WhatsApp (#1205), WA CTA tracking (#1216), nav contrast 0.65 (#1257). This pack builds the next layer; it does not re-do his.

---

## §1 — The fork: page-first or conversation-first (charter §4)

### Recommendation

**Page-first — with Zantara elevated from ambient widget to deliberate instrument.** Pages are the funnel and the seat of authority. Zantara is the Guardian's voice *inside* the house: embedded at the moments of doubt (the tools, the guides), prominent and branded — but never the front door, and never the primary conversion path. One small, reversible pilot (below) gathers the conversation-first evidence that today does not exist.

### (a) Evidence from current behavior + audience signals

- **All measurable conversion behavior today is page-shaped.** Public traffic lands on brand + editorial pages (GSC: 540 clicks/90d, 29% branded, rest = news + KBLI long tail). `/chat` gets 20 sessions/28d (~2% of public traffic). Embedded chat where it exists is used but small: `kbli_chat_question` 32 / `visa_chat_question` ~0 measurable / 28d.
- **The growth lever identified in Phase 0 is page-dependent.** The high-intent foreigner queries are absent from GSC — the SEO/GEO feeder is unbuilt. GEO (being the source AI assistants cite) requires crawlable, structured, dated *pages*. A conversation-first architecture starves the very feeder this round must build.
- **Audience contact norms are conversational — but the conversation they want is WhatsApp with a human** (64% of SEA users prefer messaging a business; exemplar study §C2), not a web AI chat as the front door. The page→qualified-WhatsApp handoff *is* the conversational close, with a human on the other end — the human moat, not a bot.
- **Market patterns:** no charismatic-authority exemplar (Wise, e-Residency, GOV.UK, Henley, Fragomen) is conversation-first; all are task-page-first with strong utility embeds. Competitors are page-first; differentiating by conversation-first would be a bet with zero behavioral support — and the charter forbids fabricating the counterfactual.
- Per charter §4a: no "evidence" for conversation-first is claimed or fabricated — the case above is behavioral + analogical, and the pilot below is the honest way to learn more.

### (b) How page-first serves the Soul

Rumah Putih is a *place*. A seat of power is architecture: rooms, weight, permanence — pages with editorial gravitas carry that; a chat box does not. Charisma = presence: visible named humans, visible published expertise, one confident next step — all page artifacts (exemplar patterns 6, 7, 9). And the moat is the **team**, not the AI: a conversation-first site makes Zantara the protagonist; the charter says the guardians are. Zantara-as-instrument keeps the AI where the Soul wants it — the Guardian's voice, threaded through the house, impressive precisely because the house doesn't *need* it to stand.

### (c) Costs and risks — including the operational/SLA implication

- **Conversation-first SLA load:** a chat promising instant answers that under-delivers converts worse than a page (charter's own warning). First-touch, high-ticket strangers asking regulatory questions = the highest-stakes conversational surface possible.
- **Empirical quality-cost evidence from our own organism:** the production WhatsApp conversational layer required three documented hardening rounds in two days (scars W68/W72/W73 — guard family over-clobbering correct regulatory answers) *for existing-client traffic*. That is the real, recurring maintenance cost of conversational quality. Putting that surface in front of first-impression PT-PMA buyers multiplies the blast radius of every wrong answer.
- **Page-first costs:** it is the harder editorial road — content, trust assets, IA discipline. Accepted; that work is the moat.
- **Cost of the middle path chosen:** maintaining embedded chat in tools = bounded (it already exists in Visa Match/Clock + KBLI today — verified in code).

### (d) Why the alternative loses (now — the door stays open)

Conversation-first loses Round 1 on five counts: zero behavioral base; SLA/quality risk at the worst possible moment (first touch); it starves the GEO feeder; it miscasts the protagonist (AI over team); and it re-platforms the site for an audience (~10 engaged organic sessions/day) that must first be *brought in* by pages. None of this is forever: the component system keeps chat first-class (§2e), and if the pilot signals strongly, Round 2 re-opens the question with data.

### (e) The reversible pilot — "Zantara Concierge" on the KBLI Navigator

The one place with real measured chat demand today (32 chat questions/28d, 304 code views). Feature-flagged, 56-day directional readout: instrument the full chain `kbli_code_viewed → kbli_chat_question → kbli_consult_click/whatsapp` and make the embedded panel a first-class, branded element on `/kbli/[code]` (it exists; this is elevation + measurement, not new platform). Claim tier: directional-signal only. Rollback: flag off. If chat-assisted sessions convert measurably better, that is the first honest datum for conversation-forward design.

### Contested points for arbitration

None known against Subhi's audit — his thesis (demote the FAB as 1-of-6 competing CTAs) and this fork (FAB demoted on homepage; chat elevated *inside tools*) are compatible and complementary. If Subhi reads the Zantara role differently, that goes to Antonello per charter §9.

---

## §2 — IA blueprint (charter §7a, lean)

### 2a. The verified current state (what the blueprint must fix)

1. **CTA surplus, partially being fixed:** ~19 conversion-intent CTAs + ~14 content links on one homepage scroll (verified in code). Hero→WhatsApp now live (#1205). Remaining: FunnelFeature ships 2 CTAs × 4 cards; no single-primary discipline yet.
2. **Channel fragmentation:** each channel's surface is scattered across a tool route, a `/services/*` editorial page, a blog category — and for Visa, **a second, separate live site**: the homepage Visa card's primary CTA goes to `visa.balizero.com` (FunnelFeature.tsx:28-33), which is live but **absent from GA4's hostname list — an unmeasured funnel receiving our primary Visa traffic (defect D10)**. Tax card → `tax.balizero.com` (7 GA4 sessions). The funnel cards leak traffic off the measured property.
3. **The booked-consultation rail does not exist:** `/book` is long-form brand content (verified); no calendar/form flow anywhere in apps/mouth. Yet booked consultation is the charter's primary metric for Company/Tax/Property.
4. **Pricing mismatch:** funnel cards display hardcoded prices (D1) and link to `/pricing`, which is an editorial category ("Pricing Insights"), not a price list. The user clicking "pricing" expects prices.
5. Trust assets exist but unstructured: SocialProof is category-leading (audit KEEP), `/team` has real organic demand (870 impressions/90d), but no license/NIB display, no official-fee anchoring, no bylines on guides.

### 2b. Target IA (the moves, each tied to evidence)

| # | Move | Grounding |
|---|---|---|
| IA-1 | **Persona doors on the homepage** — three task-framed doors: *I'm moving to Bali · I'm starting a business · I'm buying property* (Visa+Tax fold into journeys) | Exemplar P10 (Fragomen), P5 (GOV.UK one-task-one-link) |
| IA-2 | **Channel Hubs** — one canonical page per channel on balizero.com unifying tool + plain-language journey (real timeframes), humans, guides, ONE primary CTA. Visa hub absorbs/canonicalizes the `visa.balizero.com` question (decision flagged below). | Fragmentation 2a-2; exemplar P4 (journey stages); audit thesis |
| IA-3 | **`/book` consultation flow (NEW)** — the missing rail for Company/Tax/Property primary metric. Thin v1: qualified form + calendar handoff; events `book_*` added to FUNNEL_EVENTS. | Charter §2 stretch; 2a-3 |
| IA-4 | **Trust layer, sitewide** — license/registration + NIB block in footer; Google-listing badge (live link, not quoted stars); office photos + map; AuthorByline on every guide | Exemplar P13, P7; trust signals C1/C3/C5 |
| IA-5 | **"Indonesia Regulation Watch" public feed** — dated, geo-tagged regulatory alerts on the homepage + own page. Reuses the existing daily regulatory-watcher output (zero new intelligence cost). The GEO instrument: citable, structured, owned. | Exemplar P9 (Fragomen/Henley); GEO strategy |
| IA-6 | **Pricing transparency** — `/pricing` becomes a real PricingTool-driven price list with official-fee vs service-fee split; funnel-card prices switch from hardcoded to PricingTool. The largest unclaimed flank vs all three competitors. **Gated on D2 (PricingTool access) + Antonello's commercial sign-off on publishing prices.** | Exemplar P11; trust signal C4; D1 |
| IA-7 | **Nav model:** 4 channels + Dispatch + Team/About + one primary CTA. Single-primary discipline per viewport (completes Subhi's thesis structurally). | Audit central thesis; rubric #3 |
| IA-8 | **Measurement design:** hostname-scoped engaged-organic denominator (D3/D9); event-taxonomy cleanup (D5 dup, D6 gaps, `app_*` reconciliation); per-channel primary events incl. `book_*`; PII-scrub test + event allowlist per §6 guardrails. | Phase-0 D-ledger; charter §D |

### 2c. Funnel flows (per channel, target)

- **Visa** (volume, WhatsApp-close): organic/brand → Visa hub → decision tree (KEEP — polish only) → result → **qualified WhatsApp handoff** (utm-tagged, event-chained). Tier-1 verify every event; tier-2 trend.
- **Company** (high-ticket, considered): KBLI tail/articles → KBLI Navigator (the engine — KEEP) → PT-PMA journey page → **booked consultation** (`/book`). Pilot 1e runs here.
- **Tax** (1B study; feeder-first): calendar + guides grow organic presence (pos 22.6 today) → hub later. No funnel rebuild before demand exists.
- **Property** (1B study; feeder-first): eligibility tool + guides; zero organic demand today — demand creation precedes funnel design.

### 2d. Component-system spec (build list, all token-driven in `packages/core` + `apps/mouth`)

`CTAButton` (primary/secondary/tertiary variants — enforces single-primary) · `PersonaDoor` · `ChannelHub` layout · `BookingFlow` · `TrustStrip` (license/NIB/Google) · `AuthorByline` · `RegWatchFeed` · `PriceCard` (PricingTool-driven, no literals — lint rule candidate) · `StatCounter` (CRM-fed, monthly). Existing kept: decision tree, KBLI Navigator, SocialProof, dispatch system, ChatAccordion/ZantaraChat (pilot 1e).

### 2e. Future-proofing (charter §1)

Nothing above forecloses the portal, subdomain convergence, or a conversation-forward Round 2: hubs are routes + components (portable into a unified shell); chat components stay first-class citizens of the design system; `/book` and RegWatch are backend-agnostic. The visa./tax. subdomain consolidation is *flagged, not executed* — any move there ships with a redirect map per §6 guardrails.

---

## §3 — Charisma design language + rubric (charter §7e)

**Name: "Rumah Putih Editorial."** The dial: institutional weight is the default on money pages; warmth enters through *humans and voice*, never through decoration. Dispatch/team pages may sit warmer. Synthesis of: the frozen web identity (navy `#1e3863` system, red `#FF2D4C`, purple, green; Cormorant Garamond + Inter) + the exemplar patterns + the brand-cortex voice law.

### The rules (10)

1. **The scam-tagline test** (rubric #1 enforcement): if a fake agent could plausibly paste the sentence, cut it. Market evidence: "voted Bali's Number 1" is a documented scammer tagline — in this market restraint is load-bearing, not aesthetic.
2. **Numbers over adjectives:** quantified-proof blocks (permits processed, years, license number), official-fee vs service-fee anchoring. Safety as arithmetic (Wise pattern).
3. **Dual-type discipline:** Cormorant = display gravitas, Inter = utility — the Economist pattern already latent in the frozen identity; codify roles, never mix duties.
4. **One primary action per viewport.** Red is spent only on it. (Token proposal P2.)
5. **Faces with names and roles at decision points:** byline on every guide; a real face within one scroll of every CTA (Monocle pattern; anti-pattern: all three competitors).
6. **Dated, owned instruments:** RegWatch feed, monthly counters — expertise published, not asserted (Henley/Fragomen pattern).
7. **Authority via absence:** no carousels, no scarcity timers, no popups, no stock photos. Whitespace and hierarchy do the talking (GOV.UK/Economist).
8. **Soft primary CTAs for high-stakes steps:** "See how it works", "Book a consultation" — never urgency mechanics (e-Residency pattern; Sleek counterexample).
9. **Voice law shared with the cortex:** the carousel constitution's forbidden-phrases list (AI-tells, marketing-stock, empty metaphors) applies verbatim to all site copy, extended with the web-specific superlative ban.
10. **WCAG AA floor everywhere** (charter); AAA where cheap. Contrast work continues Subhi's #1257.

### The Charisma Rubric (final — the standing soul-defense standard, scored per phase with evidence)

1. **Expertise published, not asserted** — *test: could a fake agent paste this onto their site? Then delete it.*
2. **Named humans at the point of decision** — *test: can a visitor name who will handle their case before contacting?*
3. **One next step per page, two channels max** — *test: exactly one primary action visible at any scroll depth.*
4. **Editorial restraint as the authority signal** — *test: remove any element; if trust doesn't drop, it was clutter.*
5. **The backpacker-to-boardroom test** — *test: both the Canggu nomad and the corporate GM find one thing built specifically for them on the page.*

A soul-defense that scores in adjectives fails; evidence (screenshot, copy line, structure) is required per phase.

### Gated secondary-token proposals (charter §5.1 exception channel — each individually approvable)

| # | Proposal | Defense | Metric hypothesis (tier) |
|---|---|---|---|
| P1 | **Display type scale up** — H1 clamp ~40→60px desktop on money pages | Economist-grade gravitas; Subhi's audit already flags H1 31px as weak; core typefaces untouched | Engagement on hero (tier 2) |
| P2 | **CTA color system codification** — red = the single primary conversion action only; green = WhatsApp accents; purple = AI; navy-ghost = secondary | Makes the approved single-CTA thesis *enforceable in tokens* instead of per-page discipline; anchors untouched | CTA-click concentration (tier 1→2) |
| P3 | **Editorial spacing scale** — 8-pt rhythm, generous money-page whitespace | Restraint rule 7 made systematic; no identity change | Scroll/engagement (tier 2) |
| P4 | **Masthead block** — persistent navy band + red accent rule (Economist red-box pattern, BZ-ified) | Institutional presence on every page; uses only frozen anchors | Brand-query CTR over quarters (delayed monitoring, no causality claim) |

### Brand-systems coherence flag (observation, no action proposed)

The IG carousel cortex (antracite `#2C2F38`, Montserrat, yellow `#F4C430`, red `#C8102E`) and the web identity (navy `#1e3863`, Cormorant+Inter, red `#FF2D4C`) are **two different visual systems under one brand** — legitimate per the cortex's own surface taxonomy, but a visitor crossing IG→site changes worlds (even the reds differ). Out of Round-1 scope (web core is frozen by charter); flagged for Antonello as a Round-2+ brand-architecture question.

---

## §4 — Roadmap preview (thin — full §7b roadmap follows approval)

B1 **Measurement foundation** (events cleanup, `book_*`, hostname convention, PII-scrub test) → B2 **Homepage: persona doors + single-primary completion** → B3 **Visa hub consolidation** (incl. D10 decision, redirect map) → B4 **Company journey + `/book` flow** → B5 **Trust layer + RegWatch feed** → (1B: Tax/Property from the §11 study). Every phase: PR(s) into `sancho/*`, CI green, §6 enforceable checks, measurement tier declared up front, soul-defense scored on the rubric, named rollback. Safe-fix lane continues throughout (D5 event dup; canonical check; coordinated with Subhi to avoid collisions).

---

## §5 — The approval checklist (what you are actually deciding)

| ✔ | Decision | Who |
|---|---|---|
| A | **Fork: page-first + Zantara-as-instrument + KBLI Concierge pilot** (§1) | Subhi + Antonello (Antonello arbitrates if contested) |
| B | **IA direction** IA-1…IA-8 (§2b) — direction approval; each structural phase still ships gated per §6 | Subhi + Antonello |
| C | **Design language + Charisma Rubric** as the standing soul-defense standard (§3) | Subhi + Antonello |
| D | **Token proposals P1–P4** — individually | Antonello (brand owner) |
| E | **Pricing transparency direction** (IA-6) — publishing real prices is a commercial decision, separate from the D1 code fix | Antonello |
| F | **visa.balizero.com question** (D10): what is it, who owns it, consolidate or canonicalize? | Subhi (knowledge) → Antonello (decision) |

Operator asks still open from Phase 0: PricingTool role (D2) · original audit doc (D7) · GA4 filters (D3/D9).

*Approve by PR review or per-item note; partial approval is workable — every item is independently buildable except B3/B4, which depend on A+B.*
