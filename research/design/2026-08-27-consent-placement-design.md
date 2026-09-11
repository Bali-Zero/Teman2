---
date: 2026-08-27
domain: design
client_case: none
round: build-lane design deliverable (post-loop) — consent placement, R7 §4 item 2
sources:
  - R7 doctrine + backlog — research/design/2026-08-27-r7-doctrine-loop-closure.md
  - R1 fragile moments A4/A6 — research/design/2026-08-27-r1-psicologia-utente-personas-mappa-emotiva.md
  - R4 identity law (question protocol, custody line R4:120, tokens) — research/design/2026-08-27-r4-identity-merah-putih-token-spec.md
  - R5 M2b custody template — research/design/mockups/r5-merah-putih/m2b-garuda-upload.body.html
  - checkout lane (§3.1 why-we-ask; §5.4/§5.7 handoffs consumed in §3.7) — research/design/2026-08-27-checkout-garuda-design.md (PR #5099)
  - live surfaces read this round — apps/mouth/src/app/visa/voa/page.tsx, upload/UploadFlow.tsx + messages.ts, [hash]/page.tsx, checkout/[resultId]/CheckoutFlow.tsx, (visa-oracle)/visa-oracle/_components/{ConsentHandoff,WhyWeAsk}.tsx + _lib/consent-store.ts, visa/privacy/page.tsx, visa/match/page.tsx, apps/backend-rag/backend/app/routers/garuda_voa_public.py
  - backend reality — apps/backend-rag/backend/db/migrations_v2/{264_visa_decision_retention_policy,281_garuda_voa_retention,284_garuda_orders,285_garuda_magic_link,286_garuda_voa_check_results}.sql, apps/backend-rag/backend/migrations/migration_091_client_consent_log.py
  - internal doctrine — SYMBIOSIS.md Law 2 (2026-08-09 consent ruling), CLAUDE.md §14
adversarial_review: codex
adversarial_review_detail: 4-seat round-grade panel (codex sol xhigh filesystem, kimi k3 self-verifying, agy gemini-3.1-pro, qwen3.8-max) — 47 findings, 38 applied / 6 partial / 3 confirmed-sound / 0 rejected; two of the conductor's own §1 claims were overturned by the filesystem seat (a customer-facing DELETE endpoint exists; a consent ledger exists) and one of the panel's was overturned back by the tree (no automated purge) — dispositions in mockups/consent-placement/adversarial.json
---

# Consent placement — say why, who sees it, and for how long, BEFORE the ask

**What this file is.** Second build-lane design deliverable of the R7 §4 backlog. Item 2,
verbatim (R7:177-179): "Consent placement (R1-A4, unmocked): why-and-who-sees-it BEFORE the
fields, M2b's custody pattern as template — plus the custody-line AUDIT that unlocks M2b's
own placeholders (R4 §5's honesty constraint stands: no audited facts, no reassurance
copy)." The audit is PART of the mandate — §3.8 specs it. Executed under the loop's
doctrine: evidence classes, declarations through the round-grade process, async veto open.
Study only: no product code, `GARUDA_PUBLIC_ENABLED` untouched.

## §1 Ground — every consent and PII-ask surface, as it exists (class a; ground pass by a
dispatched reader; the load-bearing claims re-verified by the conductor, and three of them
CORRECTED by the panel's filesystem seats against the tree)

**A4 (GARUDA dates + consent), `visa/voa/page.tsx`:** the issuance path renders entry date
→ passport expiry → THEN a bare acknowledgement checkbox (`retention_notice_acknowledged`,
page.tsx:356-369): "I understand how my answers are stored and that I can delete this check
any time." The extension path inserts two more fields (VOA expiry, extension-already-used,
page.tsx:306-346) between expiry and checkbox. The checkbox names no duration, no who-sees,
links no policy — R1-A4's trigger ("passport expiry + storage consent after the fields",
R1:105) confirmed in position and semantics against the live code.

**A6 (passport upload), `upload/UploadFlow.tsx` + `messages.ts`:** ZERO custody language —
the four-bullet checklist is photo-quality only. The funnel's most sensitive ask carries
the least copy (R1-A6). M2b (R5) designed the cure but its custody module is placeholder
tokens (`{CUSTODY_WHO_SEES}` · `{CUSTODY_RETENTION}`), never filled — R4:120's own
constraint: only AUDITED facts may fill them, and that audit does not exist.

**Magic-link email, `[hash]/page.tsx:343-345`:** a mechanism explainer ("one-time link, no
password") and nothing about custody or data handling.

**Checkout email+phone, `CheckoutFlow.tsx:105-135`:** no consent surface; the why lives in
a code comment. The checkout LANE's design already cures the surface (§3.1 there) and hands
this lane two explicit findings — email dedup (§5.4 there) and consent-form adequacy (§5.7
there) — consumed in §3.7 below.

**Visa Oracle:** the one REAL consent block is the WhatsApp-handoff gate — copy in
`ConsentHandoff.tsx:40-58` (scope, 2h TTL, no-CRM-record), guardian gate implemented at
238-253/296-330, schema-versioned expiring receipt in `_lib/consent-store.ts:3,18-27,99-130`
— but it sits at the END; the 15-question interview has no upfront data-collection
statement. `WhyWeAsk.tsx` explains each question's decision/fact boundary (its own comment:
the claim-level source ledger is not frozen yet), not custody. `visa/match` has zero
consent language.

**Backend reality (migrations 264/281/284/285/286 + `garuda_voa_public.py` +
migration 091):** the retention AUTHORITY exists and fails closed — `264` creates
`visa_decision_retention_policies` ("Zero-approved retention authority"; "NOT a
cryptographic signature", 281:11-13) and **deliberately seeds NO policy row** (264:5-7);
`281`/`285`/`286` extend its scopes, and even the magic-link 14-day value is "proposed,
not asserted as final" (285:145-152). The live check table is `garuda_voa_check_results`
(286 — `garuda_voa_checks` is retired with no writers, 286:14): acknowledgement is
`NOT NULL` (286:121) and the policy binding trigger is 286:161; `garuda_magic_link_tokens`
fails closed on the policy HALF only (no acknowledgement column — legitimate: a 15-minute
auth artifact, 285:51-56). **A customer-initiated erasure path EXISTS**:
`DELETE /eligibility-checks/{result_id}` (`garuda_voa_public.py:569-590`,
`deleteEligibilityResult`), which 286:78-86 frames as "a customer may withdraw consent and
ask for erasure at any time … direct, customer-facing" — but **no screen exposes it**.
The retention-window purge, by contrast, is NOT automatic: the purge function "has no
caller — no scheduler, cron or service invokes it" (PENDING-ARMS ledger; 281:809-810,
286:390-391 both defer the scheduler to an explicit operator grant). **A consent ledger
EXISTS**: `client_consent_log` (migration 091 — append-only, per-purpose grant/revoke,
`legal_basis`, `policy_version`, channel; its docstring cites UU PDP Art. 20/31) — but
nothing in the GARUDA or Oracle funnels writes to it. And `garuda_orders` — holding
`applicant_full_name/email/phone/passport_number` (284:52-55) — has NO consent column and
NO retention-binding trigger (zero `consent` occurrences in 284), unlike its check/magic-
link siblings.

**The privacy-policy contradiction (verified verbatim by the conductor):**
`visa/privacy/page.tsx:60-71` states "We do not collect, and have no interest in
collecting:" — name, email, passport number, phone number, photographs. GARUDA VOA
collects ALL FIVE. Today GARUDA is dark, so the page misleads no live VOA customer — it
becomes false THE MOMENT the flag arms. Neither GARUDA VOA nor Visa Match links ANY
privacy policy from any screen; four separate privacy pages exist (root, /v2, /visa,
/visa-oracle) and only the Oracle shell links its own. CODEOWNERS assigns the /visa/ code
paths (CODEOWNERS:183); what is unresolved is CANONICAL/content ownership — which page is
authoritative for which surface, and who maintains the claims.

## §2 The two tensions this design resolves

**T1 — the explanation comes after the ask, everywhere except the Oracle handoff.** A4
puts the storage notice after the fields; A6 and the interview say nothing about custody;
magic-link explains mechanism only; checkout said nothing until its own lane. R1-A4's fix
hypothesis ("say why and who sees it, before the fields" — the A4 row; A6's own row asks
"who sees it, how long, retake") + R4's question protocol + M2b's custody template all
point one way: custody information PRECEDES or ACCOMPANIES every PII ask — never trails
it.

**T2 — the live copy and the machinery point past each other, in BOTH directions.** A4's
label promises "delete any time" — and the panel proved the promise is BACKED (the public
DELETE endpoint exists) but UNREACHABLE (no screen exposes it); this design's own first
draft then over-corrected by stripping the promise, and the panel's three seats
independently rebuilt the honest position: state the right, wire the affordance, and never
claim the one thing that is actually false — automatic purge ("deleted automatically" has
no scheduler; kept-for copy must not imply it). Meanwhile the one value the copy should
state — the retention duration — has an AUTHORITY table but NO ROW YET: Zero has not
recorded a duration for any GARUDA scope (264:5-7 seeds none by design), so the fill is a
pre-arm act, not a present-tense fact. The 2026-08-09 consent ruling (SYMBIOSIS Law 2, in
the Art. 56 cloud-transfer context) says it in the organism's own words: «Decidere di
raccogliere il consenso non è averlo: mancano la clausola a contratto, la registrazione
della prova per-cliente, il meccanismo di revoca e l'enforcement» — deciding to collect
consent is not yet having it (gloss, not verbatim).

## §3 Design decisions (mockup: `mockups/consent-placement/a4-dates-consent.html` — the
A4 issuance-path screen as the pattern's reference implementation; the extension path adds
its two fields inside the same frame, declared not drawn)

1. **The custody pattern is ONE component with TWO densities** (§6.1): a **compact hint**
   for low-sensitivity asks (A4's dates, the magic-link email) — one line: purpose +
   duration + policy link; and a **full module** for high-sensitivity asks (A6 passport
   upload, checkout PII, Oracle interview start) — why we ask · who sees it (controller
   named) · kept-for · your deletion right · policy link. Both render BEFORE the fields
   they govern. The panel's UX seat showed one identical heavyweight box everywhere breeds
   banner blindness exactly where attention matters most; the invariant survives, the
   density scales.
2. **A4 reference implementation** (issuance path): identity header (R4:108) → counter
   (`aria-live="polite"`, as M2b already does) → compact custody hint → date fields
   (unambiguous form, "27 Aug 2026") → acknowledgement checkbox LAST — kept, because the
   live write path REQUIRES it (`garuda_voa_check_results.retention_notice_acknowledged_at`
   is NOT NULL, 286:121; removing the checkbox is a migration, not a design choice) — with
   a label that says what its column means: an acknowledgement of notice, not a consent
   grant: "I've read how my answers are stored." Duration renders in the hint ONLY when an
   active policy row exists (§4); the deletion right renders because its endpoint exists:
   "You can delete this check at any time — {DELETE_AFFORDANCE_NOTE}."
3. **The deletion affordance is part of this design** (§6.4): the funnel exposes the
   existing `deleteEligibilityResult` endpoint as a user-facing control (placement: the
   result screen and the tracker — where the check lives, not inside the wizard). Copy
   states the customer-initiated right the backend already implements; it never says
   "deleted automatically" — the retention purge has no scheduler (§1), and kept-for copy
   reads "Kept for {RETENTION_WINDOW}." with no automation claim until the purge is armed
   (§5.8).
4. **A6 upload inherits M2b at full density** — M2b amended by reference (§6.2):
   `{CUSTODY_RETENTION}` becomes `{RETENTION_WINDOW}` (same semantics, fills only from an
   active policy row); `{CUSTODY_WHO_SEES}` resolves ONLY through the custody audit —
   which is IN this lane's mandate, so §3.8 specs it instead of deferring it. The A6 tier
   also carries the affirmative-authorization line (the panel's
   acknowledgement-vs-consent distinction): an explicit "I authorize {LEGAL_ENTITY} to
   process my passport for this eligibility check" gate at upload, distinct in kind from
   A4's notice acknowledgement — its backend consent RECORD is §5.5's wiring finding.
5. **Magic-link email gains the compact hint**: "Used once, to send this link.
   {PRIVACY_LINK}." — an instance of §6.1, not a separate decision.
6. **Oracle interview start gains the full module** (before question 1 — an instance of
   §6.1 on the third product surface); `ConsentHandoff` is NOT touched (it remains the
   ecosystem's best consent surface); `WhyWeAsk` stays per-question decision-boundary
   explanation.
7. **Checkout — the two handoffs consumed, not waved off.** (a) Email dedup (checkout
   §5.4): the checkout email field prefills from the session's magic-link email, and the
   custody copy covers BOTH asks in one sentence ("the email you gave for your result link
   is reused for your receipt — edit it here if you want a different one"); asked-twice
   never looks like asked-as-if-unknown. (b) Consent form (checkout §5.7): the design's
   position is the three-tier form mapped to machinery — A4 = notice acknowledgement (its
   column's own semantics), checkout = contract acceptance ("By paying you agree…", the
   checkout lane's line), A6 = affirmative processing authorization; the UU PDP adequacy
   of each tier is handed to legal WITH this mapping (§5.6), not as a blank question.
8. **The custody audit — specified, because the mandate includes it.** What the audit must
   establish before `{CUSTODY_WHO_SEES}` resolves, per surface: (a) the named processing
   roles (which humans — role, not name — and which automated systems touch the passport
   image and the check answers); (b) every sub-processor in the path (OCR engine, storage,
   hosting region) and whether each is disclosed in the linked policy; (c) the retention
   path per store (live row, backups, logs); (d) the cross-border reality of each hop —
   CLAUDE.md §14's own admission stands: the Art. 56 transfer basis is not yet
   demonstrable, so the policy must not claim adequacy it cannot show (§5.7). Until the
   audit lands, the placeholder renders AS a placeholder — R4:120 verbatim: "never
   invented reassurance".
9. **Trust footer on every funnel page** — R7 §2 amendment 4 is funnel-wide law
   (role-separation line + PT/NPWP/registry + physical address); the first draft of this
   very mockup omitted it and the panel caught the silent violation. Now present, with the
   controller named — which also answers the UX seat's controller-transparency finding.

## §4 Behavioral acceptance (what a build must prove)

- Every screen that asks for personal data renders its custody tier (hint or full) BEFORE
  or WITH the ask — a PII input whose screen lacks it is a failed build.
- `{RETENTION_WINDOW}` renders the ACTIVE policy row's interval for the surface's scope;
  **no active policy row exists today by design (264:5-7)** — so: no row, no duration
  rendered, and the same absence blocks the funnel's own INSERTs (the trigger and the
  copy read the same table; seeding the row is a pre-arm act, §5.2).
- The deletion-right line renders wherever a check exists, and its affordance calls the
  live `deleteEligibilityResult` endpoint; the copy NEVER contains "automatically" while
  the purge has no scheduler (would_fail_if: automation words in kept-for copy while the
  purge caller count is zero).
- The acknowledgement checkbox cannot be pre-checked; the step cannot advance without it;
  the backstop is the LIVE table's NOT NULL + trigger (286:121, 286:161).
- The privacy link renders ONLY when it targets the corrected, surface-scoped policy
  (§6.3) — the mockup marks the link as gated; while GARUDA is dark the gate can never
  strand a public user, because policy correction is itself a pre-arm blocker (§5.1).
- The A4 extension path renders its two extra fields inside the same custody frame — the
  hint's purpose line covers them (would_fail_if: an extension-only field renders outside
  the custody-covered region).
- Text-only zoom, 44px tap targets on EVERY interactive element (the acknowledgement row's
  tap target is the full label row, not the 20px glyph), rem type scale — the checkout
  lane's instruments, inherited.

## §5 Findings handed to product lanes (not design's to fix)

1. **`/visa/privacy` is an arm-time trap** — it denies collecting the five things GARUDA
   collects (verified verbatim). Arm-order MUST be: correct/scope the policy → link it →
   arm the flag. Pre-5% BLOCKER in the GARUDA mandate. (class a)
2. **No retention policy row exists — seeding is a pre-arm blocker twice over**: without
   an active row the custody copy has no duration AND the check INSERT itself is refused
   fail-closed. The value is Zero's to record (Legge 5). (class a)
3. **`garuda_orders` has no retention binding and no consent column** while holding the
   funnel's heaviest PII — bind it like its siblings. (class a)
4. **The deletion endpoint has no surface**: `deleteEligibilityResult` exists and is
   customer-initiated by design (286:78-86) — no screen calls it. This lane specs the
   affordance (§3.3); a product lane must build it. (class a)
5. **A consent ledger exists and the funnels don't write it**: `client_consent_log`
   (migration 091, per-purpose, versioned, append-only) is live schema — wire the funnel
   consent events (A6 authorization, checkout acceptance, Oracle handoff receipt) into it
   instead of inventing a new store. The Oracle's sessionStorage receipt
   (consent-store.ts) is the shape to persist. (class a)
6. **Three-tier consent-form adequacy → legal**, WITH the design's mapping (§3.7b):
   acknowledgement / contract acceptance / affirmative authorization, each named against
   its machinery. (handoff with position)
7. **Cross-border disclosure belongs to the policy content**: hosting/transfer reality
   per hop, and no adequacy claim the organism cannot demonstrate (CLAUDE.md §14's own
   fail-closed posture). (class c)
8. **The retention purge has no caller** — arming the scheduler is an operator grant the
   ledger already tracks; until then no surface may say "automatically". (class a)
9. **Canonical policy ownership**: four privacy pages; code ownership exists (CODEOWNERS),
   CONTENT authority per surface does not. Consolidation is a business decision. (business
   decision)
10. **Unbundling**: visa-processing consent vs WhatsApp-contact vs any future marketing
    use — one consent must never cover all three; the ledger's `purpose_key` (091) is
    built for exactly this. (class c)
11. **EN/ID legal parity**: the custody copy and the policy need Indonesian twins with
    statutory terminology — R4's P6 EN/ID law applies to legal copy too. (class c)
12. **Session abandonment**: what happens to a half-submitted check's data (TTL, purge on
    abandon) is unspecified anywhere. (class c)

## §6 Declarations (adopted under the standing pre-confirmation, async veto open)

1. **Custody-before-ask is funnel law for every PII ask, at two declared densities** —
   compact hint (low-sensitivity: A4 dates, magic-link email) and full module
   (high-sensitivity: A6 upload, checkout, Oracle interview start); the per-surface
   applications in §3.2-§3.7 are INSTANCES of this declaration, not separate decisions.
   Alternatives rejected: one identical heavyweight box everywhere (the panel's
   banner-blindness case — attention is spent where risk is low and numbed where it
   peaks); per-screen ad-hoc copy (today's state: four behaviors, three of them nothing).
2. **M2b's custody module is amended by reference**: `{CUSTODY_RETENTION}` →
   `{RETENTION_WINDOW}` (fills only from an active policy row — none exists yet, §5.2);
   `{CUSTODY_WHO_SEES}` resolves only through the §3.8 audit, which is in-mandate, not
   deferred. Alternative: redraw M2b (rejected: the mockup is right; its tokens needed
   grounding, and its counter's `aria-live` was ahead of this lane's own first draft).
3. **Funnel screens link the scoped privacy policy — gated on the policy correction**
   (§5.1), and the custody tier is itself the on-screen interim disclosure, so the gate
   never leaves a surface with nothing said. While the flag is dark the gated state can
   never face a public user (correction precedes arming by §5.1's own order).
   Alternatives rejected: link the current page (it denies the funnel's own collection);
   no link (the status quo being cured).
4. **Consent copy states exactly what the machinery serves — in both directions.** The
   customer deletion RIGHT is stated and its affordance specced, because the endpoint
   exists (the first draft's strip is reversed — refuted by the tree itself); "deleted
   automatically" is barred while the purge has no scheduler; the retention duration
   renders only from an active policy row. Alternative: the first draft's
   silence-until-self-serve-UI (rejected: it converted a wiring gap into a denied right —
   three seats independently, and the endpoint's own migration comment, against it).

## Adversarial review (§7)

Round-grade panel, second lane: **codex gpt-5.6-sol xhigh** (filesystem — 16 findings,
including the two that overturned the conductor's ground: the DELETE endpoint and the
consent ledger both EXIST), **kimi k3** (13, self-verifying — both CRITICALs held: the
mockup promised automatic deletion its own §6.4 forbids, and "the data exists" was false
because the policy table is deliberately empty), **agy gemini-3.1-pro** (7 + §6 audit + 4
structural — the erasure-right challenge that started the reversal, layered disclosure,
controller transparency), **qwen3.8-max** (6 verdicts — 3 sound-confirmations, the
negative-certification kill on "nothing else is used"). Tally: **47 findings — 38
applied, 6 partial, 3 confirmed-sound, 0 rejected** (computed from the registry);
dispositions in `mockups/consent-placement/adversarial.json`. Every load-bearing NEW
claim (endpoint, ledger, retired table, extension fields, empty policy table) was
re-verified by the conductor against the tree before disposition; one codex citation
carried an invented R4 FILENAME with correct content — recorded, and a reminder that
verification runs on the tree, not on the seat's say-so.

## §Meta

This lane's first draft committed the exact sin its mandate exists to cure: it stripped a
true promise (deletion — the endpoint was there) while making a false one ("deleted
automatically" — the scheduler was not), both in the name of honesty. The panel's three
families triangulated the truth none of the drafts held alone: rights are stated because
machinery serves them, absences are stated because machinery lacks them, and the only way
a design knows which is which is to read the tree — all of it, including the router the
ground pass missed. The pattern that ships is small: one custody component, two
densities, before every ask, saying no more and no less than what the backend can keep.
