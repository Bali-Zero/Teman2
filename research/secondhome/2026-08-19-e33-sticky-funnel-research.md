---
date: 2026-08-19
domain: visa
client_case: none (product/funnel design for the E33 Second Home vertical)
adversarial_review: codex
sources:
  - 5-seat panel (2026-08-19): Codex GPT-5.6 sol (xhigh), Kimi K3, Gemini 3.1 Pro (agy), plus 2 Sonnet web researchers (competitor scan + global residency-program UX scan)
  - Competitor sites probed live: letsmoveindonesia.com, emerhub.com, flado.id, cekindo.com, balivisas.com, ilaglobalconsulting.com, sevenstonesindonesia.com, indonesiavisas.id, atlys.com, ivisa.com, visahq.com
  - Global programs probed live: movingto.com/tools, henleyglobal.com (Passport Index family), artoncapital.com, globalcitizensolutions.com, ltr.boi.go.th, Thailand Privilege, e-resident.gov.ee, hub.citizenremote.com, uaegoldenvisacost.com, immigrantinvest.com
  - Internal: .claude/skills/secondhome/SKILL.md (corner), research/secondhome/e33-fact-registry.json, research/competitive/2026-06-digest.md
---

# E33 Second Home — Sticky-funnel research & the "Second Home Studio" concept

> Mandate (Zero, 2026-08-19): besides re-authoring the RulePack, build "qualcosa di più
> nella UI — dove l'utente non molla l'interfaccia fin quando non ci chiama per applicare".
> This capture is the research + synthesized product concept. Build decisions are Zero's
> (Legge 5); a phased recommendation is at the end.

## 1. Executive summary

Five independent seats (3 LLM families + 2 live web researchers) converged on one product
shape: **an adaptive, TurboTax-style interview that builds a personal, persistent plan
artifact in front of the user's eyes** — with the custody-anxiety killer ("your USD 130k
stays in your own name; we never touch it") as the emotional core, no email gate before
value, and a WhatsApp handoff that exports the whole plan instead of restarting the
conversation. All three LLM seats independently named **TurboTax** as the pattern to steal.

The market scan says the timing is right: **no competitor anywhere (Indonesia or global)
has an eligibility + cost + timeline tool for the Second Home visa**, none has a
consumer-facing application tracker, and pricing is opaque market-wide except one
e-commerce outlier (Flado, Rp 35M SKU). The interactive-funnel space for E33 is
**unclaimed territory**, and Bali Zero already owns most of the machinery a competitor
would have to build from scratch (pricing SSOT, 13-stage lifecycle, Day-90 scanner, fact
registry, RAG, claim guard).

## 2. Market findings

### 2.1 Indonesia competitors (live probe, Aug 2026)

| Agency | Interactive tools | E33 pricing shown | Notable |
|---|---|---|---|
| Lets Move Indonesia | none | no (only the statutory deposit) | award-badge trust signaling; 3+ SEO articles per visa |
| Emerhub | none consumer-side (B2B "Entity Management System" portal exists) | no | enterprise social proof (11.7k companies) |
| Flado | **full e-commerce checkout** (cart, Buy Now, crypto/QRIS) | **Rp 35,000,000 "Taxes & Fees Included"** | the only true public price list in the market |
| Cekindo/InCorp | 2 ungated tax calculators; 15+ gated ebooks; 5 languages | no | "value first, gate second" done right |
| Bali Visas | thin "suitability checker" modal (static underneath) | Rp 35.25–45.25M tiered (Regular/Priority × onshore/offshore) | ISO badges; price list only as PDF |
| Gaya Bali Visa | none | Rp 30,000,000 all-in headline | undercuts on price alone |
| ILA / Seven Stones | none | no | FR/ES content (ILA); comparison-editorial positioning (7S) |
| Atlys / iVisa (aggregators) | passport OCR pre-fill (BoltOCR, ~90% form pre-filled); free ungated status checker; 15-min completion promise | yes, upfront | trust-metric saturation at the CTA |

**Price positioning fact for Zero:** our IDR 39M all-inclusive sits mid-range
(Gaya 30M < Flado 35M < us 39M < Bali Visas priority tiers to 45.25M). Transparency
costs us nothing competitively and differentiates against the contact-form-gated majority.

**White space nobody covers:** (1) a real E33 eligibility/cost/timeline tool; (2) a
consumer application-status portal ("your case is at step 3 of 5"); (3) grounded AI Q&A on
Indonesian immigration; (4) proof-of-funds document pre-check; (5) RU/ZH/KO/FR language
coverage for the HNW second-home segment.

### 2.2 Global residency-program patterns (ranked by observed power)

1. **Instant-answer eligibility wizard, 3–5 questions, no login** (UAE cost calculators).
2. **Full-scenario financial simulator with editable assumptions** (Movingto Portugal) —
   the number feels self-derived, not sales-pitched.
3. **Self-referential ranking/simulation** (Henley/Arton passport indexes) — status
   mechanics; low fit for E33 (retirees optimize lifestyle, not mobility scores).
4. **Membership points economy post-purchase** (Thailand Privilege) — converts a one-time
   visa sale into a years-long logged-in relationship (StayGuard analogy).
5. **Status tracker inside the same environment you applied in** (Estonia e-Residency;
   Fragomen/Deel case trackers) — retention-by-relief; kills the radio-silence anxiety.
6. **Resumable auto-saving quiz** (Citizen Remote) — sunk-cost completion lever.
7. **Document vault + pre-briefed human handoff** (Nomads Embassy) — the call starts at
   step 10, not step 0.
8. **Live personalized progress + reward counter** (TurboTax refund counter) — unclaimed
   in immigration anywhere; see the adversarial cut in §4 before copying it.

## 3. The concept: **Second Home Studio** (working name)

One product, not a widget zoo (Codex's warning): every module is a **view over the same
saved case-state**. The prospect's journey is weeks of anxious research currently done on
Reddit, forums and competitor sites; the Studio's job is to repatriate that research phase
into our interface (Kimi's framing) and give a legitimate reason to return 5–10 times
before the WhatsApp click.

### Core loop (the sticky spine)

1. **Adaptive Navigator** — TurboTax mechanics: one question per screen, plain language,
   a "why we ask" aside on every intrusive question, visible section progress, branching
   (route deposit/property, age ≥55 → E33E/E33F variants, family, timeline horizon).
   Non-sensitive inputs only. Ends in a **verdict band, never a numeric score**:
   "Strong fit / Likely fit / Edge case — needs human review / Not eligible, here's why."
   (The bands map 1:1 onto the engine's real states, including HUMAN_REVIEW.)
2. **Live Fit Memo preview** — the personalized dossier builds *visibly* beside the
   interview (endowed-progress/IKEA effect; Gemini's "blurred preview unlocking" is one
   rendering of it). Completing the Navigator yields the **free Fit Memo** (existing owner
   decision) as a branded artifact — on screen first, PDF/email second.
3. **"Your money stays yours" module** — the custody map. The single highest-leverage
   trust asset (all seats agree the USD 130k custody fear, not our fee, is the #1 silent
   bounce): visual of the deposit sitting in the applicant's OWN name at a state-owned
   bank, Bali Zero never in the chain of custody. Facts only (own-name account; the bank's
   published rates exist) — **no yield projection** (see §4).
4. **Route comparator** — deposit USD 130k vs property USD 1M side by side (liquidity,
   timeline, what qualifies/what doesn't: completed strata only), senior variants for 55+.
   Property route honestly labeled as pending our validation standard (addendum 007).
5. **Honest timeline simulator** — pick a target date, get a week-by-week roadmap with
   RANGES not promises, split by "in your control / ours / Imigrasi's". Derived from the
   13-stage lifecycle, publicly simplified to ~7 steps.
6. **Document readiness checklist** — ~10 checkable items with plain-English "why this is
   asked"; a **readiness meter** (preparation completeness — ours to assert) rather than
   any approval probability. **No uploads in the public surface** (Codex cut; PII).
7. **Save without account** — anonymous local save + optional magic-link email
   ("Save my plan") = lead capture AFTER value, never before (Cekindo/Atlys evidence;
   Duolingo delayed-signup evidence). Resumable across sessions and devices.
8. **Context-preserving WhatsApp handoff** — the CTA exports the plan (route, verdict
   band, timeline target, readiness state) into the conversation: "Review my plan" instead
   of "chat with sales". Advisor sees the memo; the conversation starts at step 10.

### Second ring (after the core loop proves itself)

- **Country comparator** — E33 vs Malaysia MM2H vs Thailand LTR vs Portugal (SEO magnet +
  keeps the comparison-shopping phase on our site).
- **Couple/family share mode** — invite the spouse into the same plan (decisions this size
  are made at the kitchen table; the second decision-maker enters pre-briefed).
- **Evidence strip** — anonymized median processing times from real cases (needs real
  cases in `e33_cases` first; honest variance, no cherry-picking).
- **5-day "Second Home 101" email course** — offered only after a plan exists; each email
  deep-links back into the user's plan.
- **Grounded AI concierge** — RAG over the E33 corpus with citations and hard-capped
  honesty, `e33_claim_guard` in front. A module inside the plan, never the hero (Codex).
- **Regulatory radar** — surface the fact registry's confirmed/pending states as radical
  transparency ("what is settled, what we have asked the banks/Imigrasi in writing").

### Third ring (post-conversion — where StayGuard turns on)

- **Client case tracker** (Estonia pattern): the applicant follows their real case stage,
  sees the Day-90 guarantee clock, gets StayGuard offered as the natural "keep this
  monitored" continuation. Reuses `e33_cases` + the lifecycle; requires a client-auth
  surface (today's RBAC deliberately blocks role=client from the team console — the
  client view is a NEW scoped surface, not a hole in the existing one).

## 4. Adversarial cuts (what we will NOT build, and why)

- **No yield/return simulator** (Gemini's #1 was killed by Codex, and the cut is right):
  projecting deposit returns is investment advice — outside our perimeter and our rules.
  Facts only; no projections, no allocation guidance.
- **No numeric eligibility score** — reads as approval probability regardless of
  disclaimers. Verdict bands only, phrased as fit, with "Imigrasi decides".
- **No countdowns, scarcity, streaks, badges** — dark-pattern tone repels exactly the
  risk-aware HNW/55+ demographic this visa targets, and violates our own constraints.
- **No email gate before the result** — value first, capture after.
- **No document/passport uploads in the public surface** — PII boundary; checklists yes,
  vault only post-conversion behind auth.
- **No price decomposition** — IDR 39M appears as one line, always (owner decision).
- **No TurboTax-style accumulating "value counter"** in its literal form — a growing
  "total value" number borders on promised benefit. The compliant translation is the
  **readiness meter** (preparation completeness), which is ours to assert.
- **Forbidden-claims guard applies to every string** — the 10 `e33_claim_guard` patterns
  (USD 1,500, any-bank, ITAP-automatic, guaranteed approval, split-deposit, BSI, …) gate
  all Studio copy and any AI-generated answer.

## 5. Asset map (why we build this faster than anyone)

| Studio module | Existing asset | Gap to close |
|---|---|---|
| Navigator brain | Visa Oracle v2 engine + signed RulePack | **pack re-authoring** (the review-saturation fix) — until then, Phase-1 runs on a small curated deterministic rule set (age/route/capital bands) |
| Fit Memo artifact | Free-Fit-Memo owner decision; brand system | PDF/regen pipeline + memo template |
| Cost view | PricingTool (39M; E33E/F rows) | dependent pricing display waits on the 12M decision (draft, not live) |
| Timeline | 13-stage `e33_lifecycle` | public 7-step simplification |
| Readiness checklist | letters/fact registry know the real doc set | checklist content curation |
| Custody module | fact registry (own-name, BUMN banks confirmed) | visual design only |
| AI concierge | RAG backend + `e33_claim_guard` hook | productization, later ring |
| Client tracker | `e33_cases` + console shipped 2026-08-19 | client-auth scoped surface (Phase 3) |
| Regulatory radar | `e33-fact-registry.json` (33 facts, statuses) | rendering |

## 6. Recommended phasing

- **Phase A (parallel, its own lane): RulePack re-authoring** — the review-stage rewrite
  (65 HUMAN_REVIEW rules; the inverted `review.e33.guarantee-maintenance` trigger),
  re-sign + activation ceremony + adversarial review. This is the Navigator's real brain;
  the Studio ships against curated rules first and swaps the engine in when ENFORCE opens.
- **Phase B — Studio core loop** (§3 items 1–8) on `/visa/second-home`: this is the
  sticky product. No accounts, no uploads, no AI. Measurable from day one.
- **Phase C — second ring** (comparators, share mode, email course, concierge, radar).
- **Phase D — client tracker + StayGuard** (needs real cases flowing through F4a first).

**Metrics (Codex framework — never time-on-page):** % reaching first personal insight;
Navigator completion; % opening the memo preview; scenario comparisons per user; returns
to the plan within 7/30 days; WhatsApp handoffs carrying full context; advisor-reported
"conversation started warm" rate.

## Adversarial review

Codex GPT-5.6 sol (xhigh) served as the cross-family refuter on the synthesized
concept: it killed Gemini's top-ranked yield simulator (projecting deposit returns is
investment advice, outside our perimeter), rejected any numeric eligibility score
(reads as approval probability regardless of disclaimers), and its cut list — no email
gate, no public uploads, no chatbot-as-hero, no accumulating "value counter" — is
recorded as §4 and survived synthesis intact. Kimi K3 and Gemini 3.1 Pro were
independent ideation seats; their divergences from the surviving design are named in
§3/§4 rather than averaged away. Market claims come from two live web scans
(competitor + global) with URLs, not from any seat's memory.

## 7. Open decisions for Zero (Legge 5)

1. **GO/scope for Phase B** (the Studio core) and whether Phase A (pack re-authoring)
   starts in the same wave.
2. **Price posture**: hold 39M (mid-market, transparent) vs react to Flado 35M / Gaya 30M.
   Recommendation: hold and out-tool them — the scan says nobody competes on product.
3. **Dependent pricing** (12M/person draft) — confirming it unlocks the family module of
   the cost view.
4. **Languages**: IT/ID landings are already F4c; the scan adds RU/ZH/KO/FR as the
   underserved HNW segment. Sequence?
5. **Naming**: "Second Home Studio" is a working name.
