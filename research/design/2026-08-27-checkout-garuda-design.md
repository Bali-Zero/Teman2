---
date: 2026-08-27
domain: design
client_case: none
round: build-lane design deliverable (post-loop) — GARUDA checkout page, R7 §4 item 1
sources:
  - R7 doctrine + backlog — research/design/2026-08-27-r7-doctrine-loop-closure.md (PR #5091)
  - R4 identity law (pricing surfaces, tokens) — research/design/2026-08-27-r4-identity-merah-putih-token-spec.md
  - R2 competitor census (official e-VOA payment terms) — research/design/2026-08-27-r2-sota-competitor-census-distance-map.md
  - R5 M5 mockup (price contract) — research/design/mockups/r5-merah-putih/m5-vo-verdict-supported-payment.body.html
  - R1 fragile moment A7 — research/design/2026-08-27-r1-psicologia-utente-personas-mappa-emotiva.md
  - live surfaces read this round — apps/mouth/src/app/visa/voa/checkout/[resultId]/CheckoutFlow.tsx, apps/mouth/src/app/visa/voa/[hash]/page.tsx, apps/backend-rag/backend/services/payments/xendit.py, services/garuda_orders/{models,outbox_handlers}.py, backend/app/main_api.py
  - the mockup — research/design/mockups/checkout-garuda/checkout.{body.,}html
adversarial_review: codex
adversarial_review_detail: 4-seat round-grade panel (codex sol xhigh filesystem, kimi k3, agy gemini-3.1-pro, qwen3.8-max) — 43 findings, 30 applied / 8 partial / 5 rejected, dispositions in mockups/checkout-garuda/adversarial.json; all load-bearing refuter citations independently re-verified against the tree before disposition
---

# GARUDA checkout — the design the funnel's highest-risk step never had

**What this file is.** NOT a loop round — the Design Study Loop closed at R7. This is the first
build-lane design deliverable of the R7 §4 backlog (item 1: "the funnel's highest-risk step has
NO mockup"), executed under the loop's doctrine: R4 is the law (deviations declared, never
silent — see §6, which this round grew from three declarations to four), claims carry their
evidence class (R7 §3.1), and the declarations go through the round-grade process (report,
panel, dispositions, async veto) because they decide surface behavior, not just styling.
Study only: no product code, `GARUDA_PUBLIC_ENABLED` untouched.

## §1 Ground — what actually exists (class a, read from origin/main eeeadaead this round)

A live checkout page EXISTS, ship-dark: `apps/mouth/src/app/visa/voa/checkout/[resultId]/`
behind `GARUDA_PUBLIC_ENABLED` (fail-closed, noindex). It collects email + phone, shows
full name + passport read-only from the session handoff, and guards with "We need your
reviewed passport details first." — the only state R1's capture could reach (the guard copy
lives in R1's A7 row, R1:107; the not-reached table at R1 §7 explains why: CheckoutFlow
guards on a completed upload handoff). On submit it creates the order and redirects to the
PSP. Payments: Xendit **Invoices API** (hosted page; sandbox-key enforced in this build), and
the live adapter is **card-only**: the invoice payload sends `payment_methods:
["CREDIT_CARD"]` (xendit.py:153), and the module contract declares Virtual Account out of
scope **by owner decision** (xendit.py:3-6, "DECISIONS.md owner decision 1"). No QRIS. The
provider fee is absorbed into the one `price_idr`. The return route is deliberately single
(no success/failure split): "the browser return is an OBSERVATION, never a truth"
(xendit.py:108). Order shape (`models.py`): one `price_idr` figure, `order_id` opaque;
**no BZ-XXXX case-code generator exists anywhere** — the codes in R5/R5b mockups are design
placeholders (class a: repo-wide search found no generator). One more ground fact the panel
surfaced: **email is already asked BEFORE checkout** — the accepted-result screen renders
`MagicLinkRequestForm` (voa/[hash]/page.tsx:276) with an email field; phone appears nowhere
in that file. Checkout is the funnel's first ask for phone, and its SECOND ask for email.

Correction recorded while grounding (class a vs class e): `outbox_handlers.py`'s docstring
still claims nothing invokes the outbox drain in production — that text is STALE. Commit
63bfa19ec (#5035) shipped the drain dark: `main_api.py:127` defines the scheduler and the
lifespan spawns it via `asyncio.create_task` at main_api.py:282-284, armed by one variable.
The R7 ladder's decay rule caught its second stale-doc claim in one day.

## §2 The two live-vs-law tensions this design resolves

**T1 — the live checkout shows NO price.** `CheckoutFlow.tsx:13-14` declares it by design
("the price only appears once, on the order tracker"). But R4's pricing law (Q6c, R4:114)
requires the exact bundle price at quoted verdicts and at the pay button, verbatim-identical
in those TWO places; and R1-A7's own evidence (Baymard 2025, cited at R1:132) counts 12%
checkout abandonment because "the total was not visible up front" — on the step R1 rated
**5-quits** with "scam fear" as the dominant emotion. A pay button with no number next to
it, on a brand fighting scam-adjacency (R6 §4), is the exact fear surface. The design puts
the price ON the checkout page: the pay button this page owns is Q6c's second place, and the
page renders it twice (price card + CTA) so the M5 payment contract's three-renderings
scheme (R6:73 — verdict → card → CTA, "the contract inheritance goes to the product lane")
holds with every string identical. The panel forced the cardinality to be stated precisely:
Q6c names two PLACES; three RENDERINGS is M5's contract, not Q6c's text. The PSP's hosted
page renders the invoice amount from the same `price_idr` field by construction — §4 makes
that an acceptance check rather than an assumption. §6.1 declares the surface change.

**T2 — M5's rail promise exceeds what the product offers.** M5's mockup renders QRIS/VA/card
as a selectable radiogroup, but the shipped provider is Xendit's hosted Invoice — the user
never picks a rail on our page — and the live config offers **card only** (owner decision,
§1). So checkout can promise neither a selector (a control whose choice the product discards
is a dishonest control, R3's autopsy class) nor a rail set the config doesn't carry (a false
promise on the highest-fear surface). The design demotes rails to informational chips whose
set is CONFIG-DRIVEN — today that renders a single "Card" chip. R4:114's QRIS/VA/card badge
components remain the design system; a chip renders only when the config offers that rail.
§6.2 declares it; M5's radiogroup stays correct for a future direct rails integration and is
not amended.

## §3 Design decisions (mockup: `mockups/checkout-garuda/checkout.html`, mobile-first single column, max-width 26rem, light)

0. **Identity header** — R4:108 law (every screen in the perimeter): wordmark BALI ZERO left,
   EN/ID toggle + WhatsApp entry right, slim carta variant (never a red band in a funnel).
   The panel caught its absence; it is not optional chrome.
1. **Review-before-pay before anything else** (A7 cure; R4 question protocol): name and
   passport read-only with Edit→ links (anchored to the review section, `#ck-review`);
   email/phone fields preceded by why-we-ask-and-who-sees-it copy — the backlog item 2
   consent pattern applied at its first surface (class c: expert application of R1/R4).
   Email PREFILLS from the session where the visitor already gave it at the result screen
   (§1) — the page never asks as if unknown.
2. **The price card** — one figure instance (`{BUNDLE_NAME}` is the bundle's label, never a
   number), composition line (R6 §8 item 2 verbatim scope: categories, never figures),
   receipt-itemizes promise (post-payment, outside the guardrail's surfaces), the **refund
   line** (A7's four-item demand includes refund — see §3.3), the FX note with an indicative
   equivalent that renders only with a resolved live rate (multi-currency display is an
   R5b/ENG behavioral acceptance, R4:146), and **the PNBP line** — declared in §6.4 with its
   full chain of custody, conditional per §4. All figures masked; PricingTool remains the
   sole source of real prices.
3. **"What happens after you pay"** above the CTA (A7's carried demand: "total, inclusions,
   refund, time above the pay button" — R1:107): three steps — card payment on the PSP page
   (config-driven rail chips), receipt + tracker with the order identity (`{ORDER_ID}` —
   honest: no case-code exists, §5.1), then preparation ending on the DELIVERABLE (outcome
   and documents by email, `{DELIVERABLE_DETAIL}`) with the human-escalation promise. The
   refund demand lands in the price card as a placeholder line ("If your application can't
   proceed: {REFUND_POLICY_LINE}") — refund TERMS are a Legge-5 business decision, and R4 §5
   forbids invented reassurance, so the design reserves the slot and §5.6 hands the decision
   to Zero. Context for that decision: the official e-VOA flow states **no refunds**
   (R2:75) — whatever Zero sets is a differentiator either way.
4. **Team-control human module** — the FIRST surface designed under R6 §8 item 1's flipped
   production default: "our team answers … within {SLA}", no named person, no photo. The
   promise appears in exactly two places: step 3 of "what happens after you pay"
   (escalation) and the talk-first card (pre-payment contact). `{SLA}` is a placeholder by
   R4 §5 law — the value is an operational commitment only Zero can make (Legge 5). The
   named variant may only enter via the A/B under the verifiability contract; this page does
   not pre-empt it.
5. **Trust block, full §2.4 contract**: role-separation line, PT/NPWP/registry link, physical
   office address — and the talk-first WhatsApp card as a SIBLING below the trust block,
   offering contact BEFORE payment ("before you pay, not after"). The below-trust placement
   mirrors M1's cure but is decided here on this page's own terms (R7 §2.4's move is scoped
   to M1 — the register "does not add a general rule"), so it is part of §6.3's declaration,
   not an inherited law. The `{WA_LINK}` carries an OPAQUE case code only — never personal
   facts in the URL (R4 §5 WhatsApp-handoff privacy law).
6. **Sticky CTA** (position:sticky, in-flow) — the pay-button rendering — with the consent
   line above it ("By paying you agree to our terms and privacy policy" — the legal FORM of
   consent is the consent lane's call, §5.7) and the payment-window honesty note under it
   ("This total holds for {PAYMENT_WINDOW} — no price change while you decide"). The
   official flow imposes a 120-minute payment window (R2:75); ours becomes a stated promise
   instead of an implicit one.
7. **Rem-native type scale** — the first surface applying R7 §2 amendment 3 at its own
   scope: TYPE tokens in rem (radii and hairline borders stay px, per amendment 2's own
   `--radius-nested: 8px`), so text-only zoom is no longer inert at the UA-default root.
   R6's runtime probe becomes this page's acceptance test (§4).
8. **Guard state kept verbatim** ("We need your reviewed passport details first.") — the
   live copy already reads clearly and R6's walkthrough raised no finding against it; it was
   also the ONLY state the walkthrough could reach (R1 §7), so "clear" is a copy judgment,
   not an end-to-end validation. Restyled under R4 tokens; the guard's link routes to the
   upload step (`{UPLOAD_ROUTE}`).
9. **Touch targets** — every interactive element (inputs, CTA, Edit links, registry/WA
   links, header entries) carries the 44px floor (2.75rem) with clearance, per R4:146's
   house rule.

## §4 Behavioral acceptance (what a build of this page must prove)

- Price renders identically, to the rupiah, across the verdict fixture, this page's price
  card, and this page's CTA (M5 contract; Q6c's two places covered by construction) — a
  diff between any two is a failed build. The on-page instances are exactly two: the price
  card figure and the CTA figure.
- The invoice amount sent to the PSP equals the rendered price (same `price_idr` source
  field) — asserted, not assumed.
- The PNBP line renders ONLY when the state-set figure is resolved for the case type; no
  resolved figure, no line (C1 discipline extended; the mockup marks the line conditional).
- The indicative FX equivalent renders ONLY with a resolved live rate; absent rate, the FX
  note renders without it.
- The rail chips render exactly the rails the live payment config offers (today: Card), and
  never as a selectable control while the provider is a hosted invoice.
- Text-only zoom at 200% enlarges every text line (would_fail_if: any computed font-size
  equal to its default-zoom value under text-only zoom — R6 probe 5's exact instrument).
- The refund line renders with a resolved `{REFUND_POLICY_LINE}`; the build fails if the
  placeholder ships unresolved to a public surface.
- The guard state is reachable and the priced state is NOT, when the handoff is absent.

## §5 Findings handed to product lanes (not design's to fix)

1. **No case-code exists.** R7 backlog item 3 promises "the case code surviving onto the
   receipt and the first WhatsApp message" — there is nothing to survive: no generator, no
   column; the tracker/email use raw `order_id`. Either mint a human-grade code at order
   creation or amend item 3 to speak `order_id`. (class a)
2. **Price-at-checkout divergence** (T1): `CheckoutFlow.tsx` needs the price card once §6.1
   stands — it currently cannot render one by design. (class a)
3. **Stale outbox docstring** (§1 correction): `outbox_handlers.py` should stop claiming the
   drain is unwired — #5035 wired it dark (spawned at main_api.py:282-284). A doc that
   contradicts main misleads the next ground pass, and today it briefly did. (class a)
4. **Email dedup across the funnel**: email is asked at the result screen (magic link) and
   again at checkout; phone only at checkout. The consent-lane question (backlog item 2) is
   therefore placement AND deduplication — checkout must prefill the session email, and the
   consent copy must cover both asks. (class a)
5. **No PNBP figure source exists.** The conditional render in §4 requires a resolved
   state-set figure per case type; `models.py` has a single `price_idr` and no PNBP
   field/config anywhere. The product lane must mint the source before the line can render.
   (class a)
6. **Refund policy is undecided.** The design reserves `{REFUND_POLICY_LINE}`; the terms are
   Zero's (Legge 5). Official-flow context: no refunds (R2:75). (business decision)
7. **Consent form** (checkbox vs by-paying-you-agree) and its UU PDP adequacy belong to the
   consent lane; the design ships the line with links as the minimal honest form. (class c)
8. **Passport validity horizon** (6-month rule) is an upstream oracle-rules surface, not a
   checkout copy concern — noting it here so the oracle lane sees it. (class c)
9. **Multi-applicant/group purchase** has no UI affordance anywhere in the funnel; whether
   VOA group orders exist is a product decision predating any checkout design for it.
   (business decision)

## §6 Declarations (adopted under the standing pre-confirmation, async veto open)

1. **The checkout page shows the exact bundle price** — the pay button this page owns is
   Q6c's second place (R4:114), rendered twice on-page (card + CTA) per M5's three-renderings
   contract (R6:73); the tracker-only choice in the live code is superseded for the design.
   Alternative: keep the priced surface at verdict+PSP only (rejected: Baymard's 12% + A7's
   5-quits both point at the unpriced pay step).
2. **Rails render as informational, config-driven chips — never a selector — while the
   provider is a hosted invoice.** Today the config offers card only (owner decision,
   xendit.py:3-6), so one chip renders. Alternatives rejected: M5's radiogroup on checkout
   (choice the product discards = dishonest control); rendering the full QRIS/VA/card set as
   static copy (a false promise about rails the config doesn't carry — the panel's
   filesystem seat caught it against `payment_methods: ["CREDIT_CARD"]`, xendit.py:153).
3. **This page ships the team-control human module** per the flipped production default — no
   named person until the R6/R7-gated A/B decides — in two placements: the escalation
   promise in "what happens after you pay", and the talk-first card BELOW the trust block
   (M1's cure applied to this surface by this declaration — R7 scopes the original move to
   M1, so checkout needed its own). Alternative: named module (barred by doctrine until the
   human gate); no talk-first card (rejected: R6 §4's scam-adjacency dissent is at its
   sharpest on the payment surface).
4. **The PNBP line renders pre-payment, inside the total** — "Government charges: IDR 5XX.XXX
   (PNBP, set by the state) — included in the total above, not added to it." Chain of
   custody, stated completely because two standing texts point the other way: R7 §5.1 poses
   this as an OPEN question ("may a single state-set line appear … or is bundle-only
   absolute?", R7:197; "the pre-payment PNBP question stays open in §5.1", R7:99); R4:114's
   charter guardrail says "The bundle never names the PNBP figure"; owner decision 7(b)
   (CheckoutFlow.tsx:11-12) says "never split into fee + PNBP anywhere the customer can
   see". The conductor recommended YES with the included-not-added frame (one state-set
   figure, never a service-fee breakdown — the total minus nothing, no arithmetic invited),
   and Zero's 2026-08-27 standing order ("confermo tue raccomandazioni e anche per le
   prossime") pre-adopted that recommendation with the async veto open. This declaration is
   the first repo artifact carrying the adoption: FOR THIS SURFACE it amends R4:114 and
   owner decision 7(b); a veto strikes this declaration and the line, nothing else. The
   figure is state-set public law, masked here, and renders only when resolved (§4).

## Adversarial review (§7)

Round-grade panel (this deliverable carries four §6 declarations on the funnel's
highest-risk surface — above the single-refuter ASSEMBLY-LINE floor): **codex gpt-5.6-sol
xhigh** (filesystem seat — 9 findings, all 6 load-bearing citations independently
re-verified TRUE against the tree before disposition), **kimi k3** (15 findings, itself
source-verifying — the panel's hardest round), **agy gemini-3.1-pro** (10 findings + 3
structural, UX/SEA lens), **qwen3.8-max** (6 claim-set verdicts). Tally: **43 findings — 30
applied, 8 partial, 5 rejected** (computed from the row-by-row registry, not estimated);
dispositions in `mockups/checkout-garuda/adversarial.json`.

What the panel changed, in order of weight: the PNBP line's authority was mis-cited as an
"R7 ruling" — R7 leaves it OPEN, and two standing texts forbid it; the cure is §6.4's full
chain of custody (codex 1 + kimi 1: the panel's two lead seats converged from filesystem
and inline evidence independently). The rail promise was FALSE on the live config —
card-only by owner decision (codex 2, verified at xendit.py:153) — reshaping T2 and §6.2.
The Q6c cardinality was misattributed (codex 3, kimi 2, qwen C1 — three seats). Refund was
quoted in A7's demand and silently missing from the design (agy 3, kimi 3). The identity
header was absent against R4:108 (codex 5). Email duplication across the funnel was
invisible to the report (codex 4). Plus: DOM order of the talk card, M1-scoped amendment
mis-generalized, rem overreach, unconditional PNBP markup, quote fidelity (kimi 4-15),
touch targets (codex 6), consent line (agy S1), deliverable-ending step 3 (agy 6), CTA
padding (agy 9). Rejected with source citations: strip-the-PNBP-acronym (adopted wording;
the gloss translates it), international re-badge (R4:114 law + card-only reality),
above-fold role banner (R4 trust-strip law places it in the footer), passport-validity
check at checkout (upstream oracle surface), qwen C4 (round-grade process is R7's own
prescription for declaration-carrying deliverables).

## §Meta

The loop's doctrine got its first full field test the same day it merged — and the panel's
sharpest catch was the doctrine's own point: an adoption that lives in a standing order but
not yet in any repo text reads, to a filesystem refuter, exactly like a fabricated
authority. The cure was not to soften the refuter but to write the chain of custody down
(§6.4) — the report is now the artifact that makes the decision state visible. The page
itself still tries to do one thing: make the moment of highest fear the moment of highest
honesty — the number, what is inside it, what the state takes, what happens next, what
comes back if it fails, and a human reachable BEFORE the money moves.
