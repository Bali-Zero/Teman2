---
date: 2026-08-28
domain: design
client_case: none
round: build-lane design deliverable (joint panel applied, R1-R27) — delegate flow, R7 §4 item 4
sources:
  - R7 doctrine + backlog — research/design/2026-08-27-r7-doctrine-loop-closure.md (§4 item 4, verbatim quoted below)
  - R5b tree-as-journey prototype (the delegate mechanics this design draws on, PARTIALLY superseded by panel R1 — see §3.5) — research/design/2026-08-27-r5b-tree-as-journey-interactive-prototype.md + research/design/mockups/r5b-tree-as-journey/journey.html
  - R4 identity law + ruling on the delegate persona (Q4, R4:140) — research/design/2026-08-27-r4-identity-merah-putih-token-spec.md
  - R3 defect inventory (the sponsor/EA compiler persona, OPEN — R3:112) — research/design/2026-08-27-r3-heuristic-autopsy-defect-inventory-axis-gap.md
  - R1 psychology (P3 spouse persona, B9 sponsor-branch defect — Oracle-tree specific, distinct persona, see §2) — research/design/2026-08-27-r1-psicologia-utente-personas-mappa-emotiva.md
  - checkout lane (identity header law, trust footer, consent-line handoff) — research/design/2026-08-27-checkout-garuda-design.md
  - consent-placement lane (custody component two densities, three-tier consent form, client_consent_log gap) — research/design/2026-08-27-consent-placement-design.md
  - live surfaces read this round — apps/mouth/src/app/visa/voa/page.tsx (self_pay/travellers ask), apps/mouth/src/app/visa/voa/upload/{UploadFlow.tsx,messages.ts}, apps/mouth/src/app/visa/voa/checkout/[resultId]/CheckoutFlow.tsx, apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/ConsentHandoff.tsx, apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/{tree.ts,flow.ts,fact-mapper.ts,i18n.ts}, apps/backend-rag/backend/services/garuda_flow/eligibility.py, apps/mouth/src/components/garuda/declineEducation.ts, apps/backend-rag/backend/app/routers/garuda_voa_public.py, apps/backend-rag/backend/db/migrations_v2/{284_garuda_orders,286_garuda_voa_check_results}.sql, apps/backend-rag/backend/migrations/migration_091_client_consent_log.py
adversarial_review: codex
adversarial_review_detail: joint round-grade panel (R7 §4 items 4+5, run 2026-08-28) — codex gpt-5.6-sol xhigh filesystem (13 findings) · kimi k3 filesystem (15) · agy gemini-3.1-pro inline (12) · qwen3.8-max inline (17) = 57 raw + an independent Explore verification pass (10 load-bearing claims: 8 TRUE, 1 IMPRECISE, 1 FALSE-by-letter) — deduped into 27 joint register rows (23 applied, 3 partial, 1 with an embedded reject), dispositions in mockups/delegate-flow/adversarial.json and the copied register in mockups/delegate-flow/panel/
---

# Delegate flow — who fills the form, who it's for, who pays, and who may delete it

**What this file is.** Third build-lane design deliverable of the R7 §4 backlog. Item 4,
verbatim (R7:184-187): *"Delegate flow as product surface (R5b §8 item 2): who-answers gate,
authorization checkpoint, pronoun layer, check-with-the-traveller escapes — the design answer
to the sponsor persona, now needing an owner lane. (The custody split is a separate R5b §5 tree
proposal, already in the ENG lane's remit.)"* Study only: no product code, `GARUDA_PUBLIC_ENABLED`
untouched. **This draft has now been through a joint round-grade panel** (this lane, item 4,
paired with the sponsor-i18n lane, item 5 — 57 raw findings across 4 cross-family seats plus an
independent verification pass, deduped to 27 joint rows) — every §1/§3/§4/§6 claim below
reflects the applied dispositions; `mockups/delegate-flow/adversarial.json` and the copied
register in `mockups/delegate-flow/panel/` are the record.

Note on terminology: R7's own backlog item 4 (quoted above, unchanged) names the design's
central artifact an "authorization checkpoint." This design implements it as a **delegate
declaration** (panel R10) — the record below explains why the weaker word is the honest one.

**Scope correction stated up front.** R5b already built and shipped delegate *mechanics* — a
`who_answers`/`delegate_confirm` meta pair, a pronoun-rewriter, escapes — as a study prototype
against the **Visa Oracle's 53-question tree** (`journey.html`, R5b §5: *"no on-behalf flow
exists anywhere in the live funnel (verified: zero hits outside fact-vocabulary)"* — qualified
below, §1). That prototype is done; redrawing it is not this lane's job. What R7 §4 item 4 hands
to a build lane is different in kind from R5b: apply the *pattern* R5b proved to the **live
GARUDA VOA product funnel** — the same funnel the checkout (item 1) and consent-placement (item
2) lanes already designed for, not the study tree. This matters because grounding this round
turned up a fact R5b never had to face: **the GARUDA VOA eligibility engine hard-declines exactly
two shapes of the delegate persona today, as SOP-v0-GARUDA-B1 §1 policy** (§1, §2). A design for
the *live* funnel has to reckon with that; the joint panel's own correction (R3, R5, R7 — §3.1)
is that this lane's first attempt at that reckoning still had two mistakes of its own: a gate
that named the exclusion with a label instead of the facts behind it, and a pronoun mechanism
borrowed from a tree study that cannot survive a second locale (§3.5, R1).

## §1 Ground — the persona, the prior art, and the live funnel as it exists (mixed evidence
class, reclassified per panel R12: live-read code — the eligibility engine, the wizard, the
schema, the checkout flow, `ConsentHandoff.tsx` — is class a, re-verified this round by reading
the file cited; quotes of R7/R5b/R4/R3/R1 are class e, prior-round dossier citations; readings
like "a different sponsor, not the same thing" are class c, interpretive judgment)

**The persona, as R3 and R4 actually scoped it (class e).** R3:112 (agy finding 7, carried OPEN
to R4): *"the sponsor/executive-assistant compiler persona (an Indonesian partner or employer
filling the form on the applicant's behalf) appears in neither the corpus nor ruling Q4's three
personas — carried as a persona-scope question for R4, not silently adopted."* R4:140 closed
the question: *"the identity must not block a delegate-compiler flow — EN/ID, editable review,
opaque-code handoff all serve the delegate; no fourth persona is adopted (Q4's three stand) and
R5b owns the delegate at journey level, including the applicant/payer data separation and
custody surfaces it implies."* Two facts do the load-bearing work here: (a) "delegate" names the
**compiler** — who operates the keyboard — not a new persona category; (b) R4 itself names
**"applicant/payer data separation"** as an implication this design has to carry, which is
exactly what §2's T2 and §5's findings turn out to be about.

**A different "sponsor" already lives in this codebase — not the same thing (class a for the
code, corrected per panel R9/codex F12).** The Oracle tree's family/marriage route asks about a
**sponsor**: `family_sponsor_nationalities`, `family_sponsor_status_code`,
`family_sponsor_confirmed` (`fact-mapper.ts:628-645`, `i18n.ts:191-202,340-357,393-398`) — the
sponsor named by these facts is the **SUPPORTING party**: an Indonesian citizen or KITAS/KITAP
holder who backs the traveller's family-route visa, never "the person being sponsored for." The
traveller is the one sponsored; the sponsor is who sponsors them. R1:70 (persona P3, "the
spouse") and R1:124 (defect B9: *"six consecutive sponsor questions, no sub-progress"*, closed
by R5b's D-V11 sub-flow ordering) are both about *that* sponsor — the supporting party, being
asked about, not typing. This design's "delegate" is a different axis entirely — the person
**holding the device**, who may or may not also be that family-route sponsor. Reusing the word
"sponsor" for the compiler role in this design's copy would collide with a meaning the codebase
already owns; §3.6 and §5.5 make this explicit — this design says "delegate" throughout, never
"sponsor," for the compiler.

**R5b's mechanics (study prototype, `journey.html`) — the reference this design draws from,
partially superseded by the panel (class a for the code, class e for the R5b framing).** A meta
question `who_answers` (id, `journey.html:199`) precedes the tree with options `self`/
`delegate`; choosing `delegate` inserts a second meta question `delegate_confirm`
(`journey.html:200`, `delegateOnly:true`) whose two options are *"The traveller asked me to fill
this in, and I'll check with them when unsure"* / *"Actually, I'll let the traveller do it"* —
the second option resets `delegate=false` and clears all facts (`answer()`,
`journey.html:450-451`). This design carries the `delegate_confirm` statement copy forward
verbatim (§3.2) because it already passed R5b's own panel. It does **not** carry forward R5b's
pronoun mechanism: a `pron(s)` function (`journey.html:336-342`) rewrote `@you@`/`@your@`-tagged
strings into third person at render time — a live regex substitution over one shared copy
source. The joint panel (R1 — this lane's dossier and the sponsor-i18n lane's dossier had
proposed mutually exclusive pronoun mechanisms) ruled the tag-rewrite approach OUT: Indonesian
has no closed pronoun set a regex can safely substitute over, so the winning contract is
**authored, mode-variant copy keys** (a self-mode string and a delegate-mode string, both
written by hand, never derived from one by substitution) — §3.5 carries this forward as this
design's actual mechanism, not `pron()`. A persistent `delegateBanner`
(`journey.html:156-158,444`) shows once `delegate_confirm==="confirmed"`: *"You're answering for
someone else. Their case, their facts — answer as the traveller would. Who sees what:
{CUSTODY_WHO_SEES}."* — its own placeholder, unresolved, exactly like the consent-placement
lane's M2b tokens (that lane's audit is what will eventually resolve it, not this one — R5b §5
already assigned "the custody split" to the ENG lane, per R7's own backlog quote above). Every
`notSure` escape offers, in delegate mode, *"check with the traveller, or hand this to a
person"* instead of *"a person can pick this up"* (`journey.html:396`) — this design's own
escape line (§3.8) is a declared VARIANT of this phrasing, not a verbatim port (panel R23): it
fires on a different trigger (consent-to-share, not answer-uncertainty), so the wording differs
and the difference is stated, not silent.

**A live standing-to-act gate already exists — one product family over, and this design borrows
its shape under a more honest name (class a for the code; renamed per panel R10).** The Oracle's
`ConsentHandoff.tsx` (the WhatsApp handoff at the end of an interview) ships a **guardian
consent gate**: a `guardianConsentRequired` prop (`ConsentHandoff.tsx:32`) that, when true,
requires an explicit confirmation — *"I confirm that I am the parent or legal guardian and
consent to this handoff for the minor"* (`:44-45`) — gated to render and block **before** the
general consent line can be actioned (`guardianFirst` copy at `:46`; the render-order and
disable logic at `:296,317,328-329`; the submit-time guard `if (guardianConsentRequired &&
!guardianConfirmed) return;` at `:245`). That shape — a gate distinct from and sequenced before
the general consent — is what this design borrows (§3.2, §3.3); but the panel (R10) corrected
what to call it. "Authorization checkpoint" — R7's own backlog language, and this draft's
original name — overstates what a click can actually attest: there is no witness, no verified
identity, nothing that would hold up as an authorization in the legal sense the word implies.
This design's artifact is a **delegate declaration** — a self-reported statement, no more and no
less, and every downstream reference to it says so. `ConsentHandoff`'s guardian gate has the
same honesty gap in principle (a checkbox is not proof of guardianship either), but this lane
does not correct that surface — it is not this lane's.

**The live GARUDA VOA funnel has almost zero delegate awareness — one incidental hit, unrelated
to the persona (class a, corrected per panel R19).** `grep -rn "delegate"` across
`apps/mouth/src/app/(visa-oracle)/` and `apps/mouth/src/app/visa/voa/` (neither of which
contains `journey.html` — that prototype lives under `research/design/mockups/`, outside both
trees, so an earlier "outside journey.html itself" framing was a category error) returns exactly
one line: `flow.ts:1208`, a code comment — *"…Delegate"* — using the word as a verb about a
different function's responsibility, not the persona. Concretely, on the persona itself:

- **The wizard's own "About you" step already asks a payer question — in first person, with no
  escape.** `voa/page.tsx` step `trip` (`:184-268`) asks nationality, *"How many travellers on
  this application?"* (`:226-244`, `min={1}`), and a checkbox — *"I am paying for this
  application myself"* (`:246-260`, default checked) — three fields with zero indication that
  anyone but the traveller could be answering, and no branch for "someone else is filling this
  in for a solo, self-paying traveller."
- **Both answers are hard eligibility gates, by SOP, not by oversight.** `eligibility.py`'s
  docstring (`:1-30`) states the SOP-v0-GARUDA-B1 §1 positive-criteria list verbatim: *"1 adult
  traveler … self-pay"*; `screen()` declines on `not inp.self_pay` → `NOT_SELF_PAY` (`:201-202`)
  and on `family_or_group` (= `travellers > 1`, `intake.py:311`) → `GROUP_CASE` (`:209-210`).
  **Corrected per panel R15**: the literal tag `"(excluded from pilot)"` does NOT appear at
  every exclusion site — it marks exactly five (`URGENT_CASE:208`, `GROUP_CASE:210`,
  `SPECIAL_PASSPORT:212`, the overstay/refusal/blacklist decline `:221`, `FASTLANE_REQUEST:224`);
  `NOT_SELF_PAY` (`:201-202`) and the work/business decline (`:213-217`) carry no such tag. Both
  sit inside the SAME docstring-declared SOP §1 boundary (`:1-30`), so the pilot-scope framing
  still holds for `NOT_SELF_PAY` — it is grounded in the docstring, not in a per-site tag that
  isn't actually there. §5.7 flags the consequence of that boundary.
- **The decline copy is unambiguous about WHY, and it reads as SOP policy, not a bug — "owner
  decision" is a claim this round could not verify, so it is not made (panel R15).**
  `declineEducation.ts` renders `NOT_SELF_PAY` as *"You told us someone else is paying for this
  application."* → *"The online checkout only accepts payment from the traveller's own card."* →
  *"A consultant can take a third-party payment for you"* (`:147-155`, `routeKind: "whatsapp"`);
  `GROUP_CASE` as *"…travelling with {N} people…"* → *"This online form only files one passport
  at a time…"* → *"A consultant can open and track every passport in your group side by side"*
  (`:118-127`, `routeKind: "whatsapp"`). **Third-party payment and multi-traveller cases are
  already routed to a human, as policy implemented by SOP-v0-GARUDA-B1 §1 — today, only at the
  very end**, after the visitor has already answered case-type, purpose, nationality, traveller
  count and the payer checkbox (`page.tsx` steps `case_type→purpose→trip→dates`, decline
  surfaces only at `[hash]/page.tsx:157-160` on the result screen).
- **No custody language, no pronoun, anywhere downstream.** `upload/messages.ts` — the passport
  photo step, the funnel's most sensitive ask — is entirely second-person: *"we couldn't find
  your application"* (`:21`), *"your photo and details"* (`:65`); zero delegate branch.
  `CheckoutFlow.tsx` collects email and phone with bare labels *"Email"* / *"Phone"*
  (`:105-135`) — no indication of whose contact this is, while `full_name`/`passport_number`
  arrive pre-fixed from the OCR'd upload handoff (`:16-19,70-75`) — by checkout, the traveller's
  *identity* is locked, but the *contact channel* is anonymous as to who holds it.
- **The data model has no applicant/payer separation — R4:140's "implication" is a real gap, not
  a hypothetical.** `garuda_orders` (migration 284) stores exactly four contact/identity
  columns, every one prefixed `applicant_`: `applicant_full_name`, `applicant_email`,
  `applicant_phone`, `applicant_passport_number` (`284:52-55`). There is no `payer_*` or
  `filler_*` column set. Whatever email/phone `CheckoutFlow.tsx` collects is written to the
  applicant's own record — even if a delegate typed their own inbox and number there.
- **The deletion right is bound to the browser session, not to the traveller.** `garuda_voa_check_
  results` stores only a hashed session bearer — `session_secret_hash CHAR(64) NOT NULL`
  (`286:99`, comment `:96-98`) — and both `getEligibilityResult` and `deleteEligibilityResult`
  key on the `garuda_result_session` cookie, non-enumerating on its absence
  (`garuda_voa_public.py:545-556` GET, `:575-593` DELETE — the match logic reads the SAME
  cookie name at `:578` and requires it to match the stored hash at `:585-595`). If a delegate
  ran the check on their own device, **the delegate's browser — not the traveller — holds the
  only credential that can view or delete the result**, unless the delegate later hands the
  session over. `travellers` and `self_pay` are stored on this same row (`286:112-113`) as plain
  columns — present in the schema, never surfaced to a delegate as "this is what you're
  declaring."
- **The consent ledger can't record a delegate's declaration any more than it can the funnel's
  own consent events (consent-placement lane's finding #5, confirmed again here).**
  `client_consent_log` requires `client_id INTEGER NOT NULL REFERENCES clients(id)`
  (`migration_091_client_consent_log.py:29`) — a CRM-scoped foreign key. GARUDA VOA's anonymous,
  session-cookie funnel produces no `clients` row for either the traveller or the delegate;
  neither actor's declaration can be written to the one append-only ledger the codebase has for
  exactly this purpose (`:30-31`, `purpose_key`/`action`).

## §2 The two tensions this design resolves

**T1 — "delegate" is two different personas colliding under one unlabeled checkbox, and the
split is revealed too late to matter.** R4:140 draws one delegate persona; the live SOP draws a
harder line inside it that R4 never had to see: a delegate filling the form for a **solo,
self-paying** traveller is a case the online funnel fully supports today (nothing in
`eligibility.py` objects to who typed the answers) — but a delegate who **also pays**, or who is
filling in for **more than one traveller**, is declined by `screen()` regardless of how good the
form's UX is (`NOT_SELF_PAY`/`GROUP_CASE`, §1). Today the visitor discovers which persona they
were only at the result screen, after answering case-type, purpose, nationality, traveller
count, and the payer checkbox — four to five screens of work for a "no, talk to a person"
outcome that a single up-front question could have surfaced immediately. R5b's `who_answers`/
`delegate_confirm` pair, ported here, is the natural place to ask that up-front question — but
naively, it only captures "who is filling this in," not "who is this for and who pays," which
is the actual fork `eligibility.py` cares about. §3.1 designs the honest version — corrected
once more by the joint panel (R3, R5) into an explicit-facts gate, not a label-based one.

**T2 — the funnel collapses three identities (who answers, who the case is about, who pays)
into one, everywhere, and R4:140's own call for separation has no data model to land on.** The
"About you" step's checkbox — *"I am paying for this application myself"* — is phrased as if
filler and traveller are the same person (§1); `garuda_orders` has only `applicant_*` columns,
no `payer_*` (§1); the session-cookie-bound delete right (§1) makes *whoever holds the browser*
the de facto owner of the result, regardless of whose passport is in it. A design that adds a
who-answers gate and a pronoun layer without also being honest about where these three
identities still collapse into one would be cosmetic — it would make the *copy* say "the
traveller" while the *data* still only knows "the applicant" and the *access control* still only
knows "this session." §3.4 and §5.1-§5.2 keep the design honest about which half of T2 it can
actually close (copy, consent, routing) and which half it hands to product/ENG lanes (schema,
access model) — exactly the discipline R4 §5 requires: no invented reassurance.

## §3 Design decisions (mockup: `mockups/delegate-flow/authorization-checkpoint.html` — filename
unchanged, a rename is not this round's disposition; the screen itself IS the delegate-
declaration screen described below, the pattern's reference implementation; the plain branch
choice that precedes it is declared not drawn, §3.1)

1. **Who-answers gate, first screen, asking the SOP's fork in EXPLICIT FACTS — not a label.**
   Panel-corrected twice over (R3, R5): the original draft's three options used a vague label —
   *"I'm arranging this for someone else, or for more than one person"* — that is NOT the same
   set as `NOT_SELF_PAY ∪ GROUP_CASE`: a supported delegate is, in plain language, ALSO
   "arranging this for someone else." A label can't carry the fork; the fork is about payment
   and traveller count, so the options have to say so. Corrected gate, before `case_type`
   (`page.tsx`'s first live step today): *"I'm the traveller, answering for myself"* /
   *"I'm filling this in for one traveller, who will pay for themselves with their own card"* /
   *"This is for more than one traveller, or someone else will be paying"* — every option states
   the fact it routes on, not a euphemism for it. R5 further corrected which MODE the middle
   option is: its own downstream copy (§3.5's authored delegate-mode strings) is written in
   third person with the delegate as declarant — that is **delegate-answers mode** (the shape
   R5b's own `delegate_confirm` copy already assumes), not a "the traveller answers, I just hold
   the phone" mode with the traveller kept as the addressed party. This design covers
   delegate-answers mode only; a lighter "helper operates, traveller stays addressed" mode is a
   real, simpler case this design does not attempt (§5.9 hands it forward as a scoping note, not
   a build).
   **Panel R7 correction — the third option's ROUTING is an owner decision, not something this
   design adopts.** The gate's DESIGN (asking these explicit facts) is design and stays adopted
   (§6.1). WHETHER choosing the third option exits to WhatsApp immediately, versus letting the
   visitor continue and discovering the same routing at today's result screen, is a **business
   decision R7:170 already assigns to Zero** — moving the exit earlier changes lead-capture
   economics in a direction nobody has measured (§5.4 admits zero instrumentation exists). The
   DEFAULT this design ships with is **deferred decline** — i.e., today's behavior, unchanged:
   the third option, chosen honestly, still lets the visitor continue through the wizard and
   meets the same WhatsApp routing only at the existing result screen, using the existing
   `declineEducation.ts` copy unmodified. An early-exit variant is drawn as an OPTION for Zero to
   activate (§3.7), not shipped as this design's adopted behavior.
2. **Delegate declaration (mockup's subject; renamed from "authorization checkpoint" per panel
   R10), modeled on the LIVE guardian-consent shape, not invented from scratch.**
   `ConsentHandoff.tsx`'s `guardianConsentRequired`/`guardianFirst` pattern (§1) — a gate that
   renders and blocks BEFORE the general consent can be actioned — is the direct model: an
   explicit statement, R5b's own proven copy carried over verbatim (*"The traveller asked me to
   fill this in, and I'll check with them when unsure"*, `journey.html:200`), plus one line this
   design adds that R5b's tree-only context never needed. **Panel-corrected (R8)**: the original
   scope-limit line — *"This does not authorize payment on the traveller's behalf. At checkout,
   payment still has to come from the traveller's own card"* — overclaimed an enforcement that
   does not exist (no cardholder-name check anywhere in the checkout path; `self_pay` is a
   self-declared checkbox, not verified; `xendit.py` restricts payment METHOD, not payer
   identity). The corrected line states only what is true: *"The online checkout is for
   travellers paying for themselves. If someone else is paying, a consultant handles it on
   WhatsApp."* — a description of the funnel's scope, not a promise the system checks. Naming
   this scope here, before the wizard, is still cheaper for the visitor than discovering it at
   the decline screen after finishing the form (T1). Two CTAs: continue as delegate, or R5b's
   own "actually, I'll let the traveller do this" reset (`journey.html:451`).
3. **The delegate declaration is a FOURTH axis, not a fourth tier of the consent-placement
   lane's three-tier form — and it is a self-declaration, not a verified authorization (panel
   R10).** That lane's tiers (notice-acknowledgement / contract-acceptance /
   affirmative-authorization, consent §3.7b) answer "what may this system do with the data";
   this declaration answers "does the person clicking say they have standing to answer for
   someone else" — orthogonal, and it has to be answered FIRST (mirroring `guardianFirst`'s
   ordering rule, `ConsentHandoff.tsx:328-329`) because every later mode-variant copy key (§3.5)
   depends on knowing which mode is active. Naming it a "checkpoint" or "authorization" would
   overstate what a click can attest: there is no witness, no verified identity, and — per §1's
   `client_consent_log` finding (§5.3) — no ledger anywhere in this codebase that could even
   record it today. A real authorization design (a traveller-side handoff, a receipt, a
   revocation path) is product work this lane does not perform; this declaration is honestly
   scoped to what it is: a self-reported statement the delegate makes, that the design believes
   and acts on, without proof.
4. **Delegate banner, ported from R5b, filled honestly, and now carrying an explicit density
   rule (panel R18).** The persistent strip (`journey.html:156-158`) carries over verbatim in
   shape; its `{CUSTODY_WHO_SEES}` token resolves only through the consent-placement lane's
   §3.8 audit (unchanged — this lane does not invent that answer, R4 §5). **Density rule, stated
   once here and cross-referenced by the sponsor-i18n lane (R18):** custody-component density
   follows the sensitivity of the SCREEN'S ASK (consent-placement §6.1), not the presence of the
   delegate. The declaration screen's own custody hint (the mockup's aside) stays COMPACT
   because no PII is collected on that screen — only a role is being declared. The banner, once
   it starts riding downstream screens that DO collect PII (upload, checkout), does not
   duplicate a five-part full module of its own; it supplements whatever tier that screen's own
   custody component already carries (consent-placement §3.1's compact/full split), adding only
   the delegate-specific context (`{CUSTODY_WHO_SEES}`, the third-person framing) on top. One
   line is added to the banner that the audit does NOT gate, because it is already true today
   and worth the traveller knowing: *"This browser is what controls this result — viewing or
   deleting it later needs this same device and session, not a login."* (§5.2's finding, stated
   as the honest present tense, not a future promise.) **Panel R27 note**: an earlier
   consideration — adding "if this browser's session is lost, a consultant can help via
   WhatsApp" — is deliberately NOT added, because this round could not verify that support route
   actually exists as an operational path; per R27 the design states nothing beyond the verified
   fact rather than promise an unverified fallback.
5. **Pronoun layer is AUTHORED per-mode copy keys, not a tag-rewrite — the panel's largest
   correction to this design (R1).** R5b's `pron()` (`journey.html:336-342`) rewrote
   `@you@`/`@your@`-tagged strings into third person at render time, one shared source, one
   substitution rule. The joint panel found this mechanism in direct conflict with the
   sponsor-i18n lane's own contract (authored self/delegate variants per locale, regex banned)
   and ruled for the i18n lane's approach: **Indonesian has no closed pronoun set a regex can
   safely substitute over** — a single rewrite rule that works for English "you"/"your" does not
   generalize. This design therefore ships every mode-sensitive string as TWO hand-authored keys
   — a self-mode string and a delegate-mode string, written independently, never derived from
   one by substitution — and, in delegate mode, phrased as **reported speech** where the string
   makes a claim about the traveller (panel R10): the payer question renders as *"The traveller
   has confirmed to me that they will pay themselves"* (not "the traveller will pay themselves,"
   which claims a fact the delegate cannot actually attest to) rather than the live *"I am paying
   for this application myself"* (`page.tsx:259`) — removing the first-person identity-collapse
   that string carries today, honestly, without inventing a rewrite mechanism the panel found
   unsafe for a second locale. `upload/messages.ts` and `CheckoutFlow.tsx`'s copy get the same
   authored-key treatment. §4's acceptance bar changes to match: no raw tag, no substitution
   logic, and full EN/ID key parity for every mode-sensitive string (the i18n lane owns the ID
   half; this lane owns the key contract both sides fill).
6. **Checkout labels the contact fields, adds an honest routing line, and never calls the
   compiler a "sponsor" — a second field was proposed and rejected (panel R11, PARTIAL).**
   Delegate mode relabels the bare *"Email"*/*"Phone"* fields (`CheckoutFlow.tsx:105-135`) to
   *"Traveller's contact — for the receipt and any questions about this application."*
   **Added per R11**: a second line makes the routing explicit rather than implied — *"Receipts
   and updates about this application go to this contact."* The panel also considered adding a
   SECOND, delegate-owned contact field (so the delegate could keep their own inbox on record
   distinct from the traveller's); this lane REJECTS that addition here, because `garuda_orders`
   has no column to back it (`284:52-55`, §1) — inventing a field in the mockup that the schema
   cannot store would be exactly the reassurance R4 §5 forbids. The schema decision stays §5.1's
   product finding, unclaimed by this lane. Nowhere does delegate-mode copy use the word
   "sponsor" for the compiler role — the codebase's `family_sponsor_*` vocabulary (§1, corrected
   per R9 to name the SUPPORTING party) already owns that word for a different fact, and reusing
   it here would silently create a second meaning the way R3's own inventory warns against.
7. **IF Zero activates the early exit (§3.1's owner decision) — the screen uses a GENERIC
   mirror, never the literal decline copy (panel R4).** The original draft reused
   `declineEducation.ts`'s exact `NOT_SELF_PAY`/`GROUP_CASE` mirror lines — *"You told us
   someone else is paying"* / *"…travelling with {N} people…"* — but the corrected gate (§3.1)
   never asks WHICH of the two facts applies, or how many travellers (`{N}` is never captured);
   reusing that copy at the gate would state a fact the visitor never actually declared. The
   early-exit variant instead authors a generic mirror — *"This is outside what our online form
   can process today — more than one traveller, or someone else paying, both need a person's
   help"* — followed by the SAME `alternative`/`routeKind: "whatsapp"` framing
   `declineEducation.ts` already uses (`:118-127,147-155`), so a consultant reading the handoff
   still recognizes the shape, without this design inventing a false level of specificity. Per
   §3.1/§6.1, this screen is drawn as the OPTION for Zero to activate — the shipped default is
   deferred decline, where this generic mirror is not shown and the visitor instead meets the
   existing, fact-accurate `declineEducation.ts` copy at today's result screen once the actual
   facts (nationality, purpose, travellers, self_pay) have been collected.
8. **Check-with-the-traveller escapes — ported in KIND, with the declaration screen's own
   variant declared as an edit, not a verbatim port (panel R23).** Every `notSure` affordance
   downstream, in delegate mode, offers R5b's own phrasing verbatim — *"check with the
   traveller, or hand this to a person"* (`journey.html:396`) — instead of the self-mode
   default. The declaration screen's own escape (§3.2's mockup) fires on a DIFFERENT trigger —
   consent-to-share, not answer-uncertainty — so its wording is a declared variant: *"Not sure
   the traveller wants this shared? Check with them first, or hand this to a person"* — same
   spirit, different context, stated as an edit rather than presented as R5b's own words.
9. **Identity header + trust footer, R4:108/R7 §2 amendment 4, unchanged law — with one added
   dependency (panel R17).** Same wordmark, EN·ID toggle, WhatsApp entry, and role-separation +
   PT/NPWP/registry + office-address footer the checkout and consent-placement mockups already
   carry — this screen sits in the same perimeter and inherits the same law, not a new decision.
   **Added per R17**: the sponsor-i18n lane's own grounding found the EN·ID toggle has no
   dictionary behind it on the checkout surface today; this design inherits that dependency
   explicitly rather than assuming the toggle just works — the toggle renders live only where
   reachable locale logic backs it, and an honest DISABLED state otherwise, never a dead control
   that looks live.

## §4 Behavioral acceptance (what a build must prove)

- The who-answers gate renders before `case_type` for every visitor — this is a NEW screen the
  self-mode visitor did not see before (panel R25: the earlier claim of "completely unchanged"
  overreached — the entry point itself changes for everyone). Downstream self-mode screens, past
  the gate, are unchanged — would_fail_if: any self-mode screen AFTER the gate differs from main
  today. The added friction of the gate screen itself is a measurement question (§5.4), not
  something this bar can assert away.
- Choosing the middle option and confirming the delegate declaration (§3.2/§3.3) sets
  `delegate=true` for the rest of the session; every downstream mode-sensitive string renders
  from its authored delegate-mode key (§3.5) — a screen showing the self-mode key, a raw
  substitution artifact, or a first-person string with no delegate-mode key defined at all,
  while `delegate===true`, is a failed build. (Replaces R5b's tag-rewrite acceptance bar, which
  this design does not use — panel R1.)
- Choosing the third option — "more than one traveller, or someone else will be paying" — routes
  to the WhatsApp handoff BEFORE `case_type` renders ONLY if Zero has activated the early-exit
  variant (§3.1/§3.7); the SHIPPED DEFAULT is deferred decline: the visitor continues normally
  and meets the existing `declineEducation.ts` routing at today's result screen once real facts
  are collected. A build that hard-codes the early exit as always-on, with no owner-gated
  toggle, does not match this design (panel R7).
- The delegate declaration blocks all progress until confirmed — mirroring
  `ConsentHandoff.tsx`'s `guardianConsentRequired && !guardianConfirmed` guard
  (`:245`) — and cannot be pre-checked.
- Checkout's email/phone fields never render with a bare, unlabeled prompt while
  `delegate===true` (would_fail_if: the generic "Email"/"Phone" labels, or the missing routing
  line §3.6 adds, survive into delegate mode).
- The delegate banner never renders a resolved `{CUSTODY_WHO_SEES}` value until the
  consent-placement lane's audit (§3.8 there) has produced one — an invented value here is a
  failed build under R4 §5's own law, inherited, not re-declared. **Added (panel R26, joint with
  the sponsor-i18n lane)**: any unresolved placeholder token — custody, retention, or otherwise
  — SUPPRESSES its line entirely; a raw `{TOKEN}` string or a fabricated stand-in value reaching
  production copy is a failed build, in either mode.
- No screen, in either mode, ever labels the compiler's role "sponsor."

## §5 Findings handed to product lanes (not design's to fix)

1. **`garuda_orders` has no applicant/payer separation, and no delegate-contact column either**
   — R4:140 named this as an implication of the delegate flow; today's schema (`284:52-55`) has
   only `applicant_*` columns. The panel considered adding a delegate-owned contact field to
   this design's own mockup and rejected it here (§3.6, R11) precisely because the schema has
   nowhere to put it — if a delegate's own contact needs to be stored distinctly from the
   traveller's, that is a new column set, not a copy fix. (class a)
2. **The deletion/view right is bound to the session cookie, not to the traveller** — a
   traveller who never touched the originating browser has no path to invoke their own
   `deleteEligibilityResult` right (`garuda_voa_public.py:575-593`, match logic `:585-595`)
   unless the delegate hands over the session. This compounds the consent-placement lane's
   finding #4 (the endpoint has no user-facing surface at all yet) with a second, harder
   question: whose surface would it even be, in delegate mode. (class a)
3. **`client_consent_log`'s `client_id` FK (`091:29`) still can't record either actor's
   declaration** — the consent-placement lane already flagged this for the funnel's own consent
   events (its finding #5); this lane confirms the same gap now has two actors who might need an
   entry (traveller's authorization-to-delegate, delegate's confirmation-of-standing), not one.
   (class a)
4. **The early-exit gate variant is a genuinely new behavior with no measurement plan — and per
   panel R7 it ships OFF by default, pending Zero's ruling.** Moving the WhatsApp routing
   decision from the last screen (today) to the first (§3.1) should reduce wasted effort for the
   two excluded shapes, but nobody has measured whether an earlier "talk to a person" costs
   conversions a later one wouldn't have; the gate DESIGN is adopted, the EXIT TIMING is not —
   recommend instrumenting the gate's exit rate on a small cohort before Zero rules either way.
   (class c; business decision per R7:170)
5. **"Sponsor" is already a taken word in this codebase for a different fact — corrected per
   panel R9 (codex F12).** The family route's `family_sponsor_*` vocabulary
   (`fact-mapper.ts:628-645`) names the SUPPORTING party — the Indonesian citizen or KITAS/KITAP
   holder who backs the traveller's visa — never "the person being sponsored for" (the
   traveller is who's sponsored). This design deliberately never uses "sponsor" for the compiler
   role (§1, §3.6); any future copy pass on delegate-mode strings should hold that line. (class c)
6. **i18n is explicitly out of scope here, and is R7 backlog item 5's job, in that order** — R7
   §4 places item 5 ("i18n for the sponsor") after item 4 precisely because it "presupposes item
   4's surface" (R7:188-190); Bahasa Indonesia copy for the who-answers gate, the delegate
   declaration, and the authored delegate-mode keys is not drawn here — this is the sponsor-i18n
   lane's remit, coordinated via the joint panel (that lane's own R13/R16 dispositions).
   (business/lane decision, already sequenced by R7)
7. **`NOT_SELF_PAY`/`GROUP_CASE` sit inside SOP-v0-GARUDA-B1 §1's pilot boundary — corrected per
   panel R15**: the literal `"(excluded from pilot)"` tag marks only five decline sites
   (`:208,210,212,221,224`); `NOT_SELF_PAY` (`:201-202`) carries no tag of its own, but sits
   inside the same docstring-declared pilot scope (`:1-30`). If the pilot later widens to accept
   third-party payment or multiple travellers, the who-answers gate's third option stops being a
   hard WhatsApp routing rule and becomes a real fork (self-pay-solo → online; third-party/group
   → still a product decision, not necessarily WhatsApp) — flagging so a future gate rebuild
   doesn't have to rediscover that today's routing is pilot-shaped, not law-shaped. (class c)
8. **The guardian-consent pattern this design borrows lives in a different code surface**
   (`ConsentHandoff.tsx`, the Oracle) **from the one this design targets** (GARUDA VOA's own
   wizard) — this lane borrows the shape, not the component; a future consolidation of the two
   delegate-declaration implementations is a refactor question, not something this design
   performs. (class c)
9. **A lighter "helper operates the device, traveller stays the addressed party" mode is real
   and this design does not build it (§3.1, panel R5's scoping split).** Someone typing on a
   traveller's behalf while the traveller is present and answering in their own words is a
   different, simpler shape than delegate-answers mode — it may need no declaration, no pronoun
   layer, nothing this design adds. Whether it deserves its own gate option is a scoping question
   for whichever lane picks this up next, not resolved here. (class c)

## §6 Declarations (adopted under the standing pre-confirmation — joint round-grade panel run
2026-08-28, dispositions in `adversarial.json`; async veto open)

1. **The who-answers gate DESIGN asks the SOP's own fork in explicit facts, not a label —
   ADOPTED.** Three options — traveller / delegate-for-a-solo-self-payer (payment- and
   traveller-count-anchored wording, panel R3) / more-than-one-traveller-or-someone-else-paying.
   Alternative: R5b's original binary `self`/`delegate` split (rejected: T1 — the SOP's real
   fork is not "who types"); a label-based third option, "arranging for someone else" (rejected
   per R3 — a supported delegate is also, in plain language, "arranging for someone else," so a
   label cannot carry the fork; the option must state the fact).
   **Split (panel R7) — NOT adopted here, moved to owner decisions (§5.4):** WHEN the third
   option's WhatsApp exit fires — at the gate (screen 1) versus deferred to today's existing
   result screen — is a business decision (R7:170 assigns it to Zero); this design ships with
   deferred decline as the default and draws the early-exit screen as the activatable option
   (§3.7), not as adopted behavior.
2. **The delegate declaration is modeled on the live guardian-consent shape and carries an
   honest, non-overclaiming scope-limit line — renamed from "authorization checkpoint" (panel
   R10) and its enforcement claim corrected (panel R8).** Alternative: reuse R5b's
   `delegate_confirm` copy unchanged, with no added scope line (rejected: R5b's tree-only
   context never had to face `NOT_SELF_PAY` — this funnel does, and silence on the boundary
   would let a delegate believe they can pay when `eligibility.py` will decline them for it).
   Alternative: keep the original scope-limit's enforcement language ("payment still has to
   come from the traveller's own card") (rejected per R8: no such enforcement exists in the
   checkout path — the corrected line states scope, not a promise the system checks).
3. **The delegate declaration is a fourth axis, sequenced before the consent-placement lane's
   three-tier form, never folded into it — and is named, throughout, as a self-declaration, not
   a verified authorization (panel R10).** Alternative: add "delegate authorization" as a fourth
   consent tier (rejected: that lane's tiers answer what the system may do with data; this
   declaration answers who says they have standing to answer at all — conflating them would make
   the consent-placement lane's own three-tier mapping, already handed to legal, incorrect by
   addition after the fact). Alternative: call it an "authorization checkpoint" as R7's backlog
   item literally does (rejected per R10: the word claims a verification this design cannot
   provide — no witness, no ledger, no proof — and the honest name is "declaration").
4. **The applicant/payer/filler data-model gap is named as a finding, not patched with copy —
   and the pronoun mechanism itself is authored keys, not a runtime rewrite (panel R1).**
   Alternative: invent a `{DELEGATE_CONTACT}` field in the checkout mockup as if the schema
   already supported it (rejected: R4 §5 forbids invented reassurance on a surface the schema
   cannot back — §5.1 hands the actual column design to the owning lane). Alternative: keep
   R5b's `pron()` tag-rewrite mechanism for the pronoun layer (rejected per R1: it conflicts with
   the sponsor-i18n lane's authored-variant contract, and a regex substitution does not
   generalize to Indonesian's pronoun set — the winning, joint mechanism is authored per-mode
   copy keys, §3.5).

## §Meta

R5b proved the mechanics were buildable — a pronoun function, a meta question, an escape
phrase. This round's own first draft ported that proof onto the live funnel and still got two
things wrong that only a hostile, filesystem-grounded reader caught: it borrowed a rewrite
mechanism that cannot survive a second locale, and it drew a gate that asked the SOP's real fork
through a label instead of the facts the label was standing in for — the same class of mistake
R3's own inventory warned this whole loop about, landing here anyway on the first pass. The
delegate persona R4 cleared is narrower than "someone else is typing" — it is "someone else is
typing, for exactly one traveller, who pays with their own card, and says so in their own
words" — and the panel's corrections (R1, R3, R5, R7, R8, R10) are what it took to make every
claim in this file say only that, stated as a self-report, never as a fact this design can
prove. The pattern that ships is the one R5b validated and the panel then re-verified against
the funnel it actually has to work on.
