---
date: 2026-08-28
domain: design
client_case: none
round: build-lane design deliverable (draft, pending round-grade panel) — delegate flow, R7 §4 item 4
sources:
  - R7 doctrine + backlog — research/design/2026-08-27-r7-doctrine-loop-closure.md (§4 item 4, verbatim quoted below)
  - R5b tree-as-journey prototype (the delegate mechanics this design ports) — research/design/2026-08-27-r5b-tree-as-journey-interactive-prototype.md + research/design/mockups/r5b-tree-as-journey/journey.html
  - R4 identity law + ruling on the delegate persona (Q4, R4:140) — research/design/2026-08-27-r4-identity-merah-putih-token-spec.md
  - R3 defect inventory (the sponsor/EA compiler persona, OPEN — R3:112) — research/design/2026-08-27-r3-heuristic-autopsy-defect-inventory-axis-gap.md
  - R1 psychology (P3 spouse persona, B9 sponsor-branch defect — Oracle-tree specific, distinct persona, see §2) — research/design/2026-08-27-r1-psicologia-utente-personas-mappa-emotiva.md
  - checkout lane (identity header law, trust footer, consent-line handoff) — research/design/2026-08-27-checkout-garuda-design.md
  - consent-placement lane (custody component two densities, three-tier consent form, client_consent_log gap) — research/design/2026-08-27-consent-placement-design.md
  - live surfaces read this round — apps/mouth/src/app/visa/voa/page.tsx (self_pay/travellers ask), apps/mouth/src/app/visa/voa/upload/{UploadFlow.tsx,messages.ts}, apps/mouth/src/app/visa/voa/checkout/[resultId]/CheckoutFlow.tsx, apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/ConsentHandoff.tsx, apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/{tree.ts,flow.ts,fact-mapper.ts,i18n.ts}, apps/backend-rag/backend/services/garuda_flow/eligibility.py, apps/backend-rag/backend/components/garuda/declineEducation.ts (apps/mouth), apps/backend-rag/backend/app/routers/garuda_voa_public.py, apps/backend-rag/backend/db/migrations_v2/{284_garuda_orders,286_garuda_voa_check_results}.sql, apps/backend-rag/backend/migrations/migration_091_client_consent_log.py
adversarial_review: pending — this draft has not yet gone through the round-grade panel; the conductor runs it before ship (per this lane's mandate)
---

# Delegate flow — who fills the form, who it's for, who pays, and who may delete it

**What this file is.** Third build-lane design deliverable of the R7 §4 backlog. Item 4,
verbatim (R7:184-187): *"Delegate flow as product surface (R5b §8 item 2): who-answers gate,
authorization checkpoint, pronoun layer, check-with-the-traveller escapes — the design answer
to the sponsor persona, now needing an owner lane. (The custody split is a separate R5b §5 tree
proposal, already in the ENG lane's remit.)"* Study only: no product code, `GARUDA_PUBLIC_ENABLED`
untouched. This draft has NOT been through the round-grade panel yet — that is the conductor's
next step, per this lane's own mandate.

**Scope correction stated up front.** R5b already built and shipped the delegate *mechanics* —
`who_answers` / `delegate_confirm` / a `pron()` pronoun-rewriter / escapes — as a study
prototype against the **Visa Oracle's 53-question tree** (`journey.html`, R5b §5: *"no on-behalf
flow exists anywhere in the live funnel (verified: zero hits outside fact-vocabulary)"*). That
prototype is done; redrawing it is not this lane's job. What R7 §4 item 4 hands to a build lane
is different in kind from R5b: apply the *pattern* R5b proved to the **live GARUDA VOA product
funnel** — the same funnel the checkout (item 1) and consent-placement (item 2) lanes already
designed for, not the study tree. This matters because grounding this round turned up a fact R5b
never had to face: **the GARUDA VOA eligibility engine hard-declines exactly two shapes of the
delegate persona today, by explicit owner decision** (§1, §2). A design for the *live* funnel has
to reckon with that; a design for the study tree never would.

## §1 Ground — the persona, the prior art, and the live funnel as it exists (class a; every
claim below re-verified this round by reading the file cited)

**The persona, as R3 and R4 actually scoped it.** R3:112 (agy finding 7, carried OPEN to R4):
*"the sponsor/executive-assistant compiler persona (an Indonesian partner or employer filling
the form on the applicant's behalf) appears in neither the corpus nor ruling Q4's three
personas — carried as a persona-scope question for R4, not silently adopted."* R4:140 closed
the question: *"the identity must not block a delegate-compiler flow — EN/ID, editable review,
opaque-code handoff all serve the delegate; no fourth persona is adopted (Q4's three stand) and
R5b owns the delegate at journey level, including the applicant/payer data separation and
custody surfaces it implies."* Two facts do the load-bearing work here: (a) "delegate" names the
**compiler** — who operates the keyboard — not a new persona category; (b) R4 itself names
**"applicant/payer data separation"** as an implication this design has to carry, which is
exactly what §2's T2 and §5's findings turn out to be about.

**A different "sponsor" already lives in this codebase — not the same thing.** The Oracle
tree's family/marriage route asks about a **sponsor**: `family_sponsor_nationalities`,
`family_sponsor_status_code`, `family_sponsor_confirmed` (`fact-mapper.ts:628-645`,
`i18n.ts:191-202,340-357`) — the person **being asked about**, an Indonesian citizen or KITAS/
KITAP holder who legally backs the traveller's family-route visa. R1:70 (persona P3, "the
spouse") and R1:124 (defect B9: *"six consecutive sponsor questions, no sub-progress"*, closed
by R5b's D-V11 sub-flow ordering) are both about *that* sponsor. This design's "delegate" is a
different axis entirely — the person **holding the device**, who may or may not also be the
family-route sponsor. Reusing the word "sponsor" for the compiler role in this design's copy
would collide with a meaning the codebase already owns; §3.6 and §5.5 make this explicit.

**R5b's mechanics (study prototype, `journey.html`) — the pattern this design ports.** A meta
question `who_answers` (id, `journey.html:199`) precedes the tree with options `self` /
`delegate`; choosing `delegate` inserts a second meta question `delegate_confirm`
(`journey.html:200`, `delegateOnly:true`) whose two options are *"The traveller asked me to fill
this in, and I'll check with them when unsure"* / *"Actually, I'll let the traveller do it"* — the
second option resets `delegate=false` and clears all facts (`answer()`, `journey.html:450-451`).
A `pron(s)` function (`journey.html:336-342`) rewrites `@you@`/`@your@`/`@are you@`-tagged
strings into third-person ("the traveller"/"the traveller's") when `delegate===true`, and strips
the tags to plain second-person otherwise — one copy source, two renderings. A persistent
`delegateBanner` (`journey.html:156-158,444`) shows once `delegate_confirm==="confirmed"`:
*"You're answering for someone else. Their case, their facts — answer as the traveller would.
Who sees what: {CUSTODY_WHO_SEES}."* — its own placeholder, unresolved, exactly like the
consent-placement lane's M2b tokens (that lane's audit is what will eventually resolve it, not
this one — R5b §5 already assigned "the custody split" to the ENG lane, per R7's own backlog
quote above). Every `notSure` escape offers, in delegate mode, *"check with the traveller, or
hand this to a person"* instead of *"a person can pick this up"* (`journey.html:396`).

**A live authorization-checkpoint pattern already exists — one product family over.** The Oracle's
`ConsentHandoff.tsx` (the WhatsApp handoff at the end of an interview) ships a **guardian consent
gate**: a `guardianConsentRequired` prop (`ConsentHandoff.tsx:32`) that, when true, requires an
explicit confirmation — *"I confirm that I am the parent or legal guardian and consent to this
handoff for the minor"* (`:44`) — gated to render and block **before** the general consent line
can be actioned (`guardianFirst` copy at `:46`; the render-order and disable logic at
`:296,317,328-329`; the submit-time guard `if (guardianConsentRequired && !guardianConfirmed)
return;` at `:245`). This is the exact **shape** — a standing-to-act checkpoint, distinct from and
sequenced before the general consent — that a delegate-authorization checkpoint needs; it exists
today for a different actor (guardian-for-minor, not delegate-for-adult) and this design borrows
its shape, not its code (§3.3, §5.8).

**The live GARUDA VOA funnel has zero delegate awareness anywhere** (verified this round —
`grep -rn "delegate"` across `apps/mouth/src/app/(visa-oracle)/` and `apps/mouth/src/app/visa/
voa/` returns nothing outside `journey.html` itself). Concretely:

- **The wizard's own "About you" step already asks a payer question — in first person, with no
  escape.** `voa/page.tsx` step `trip` (`:184-268`) asks nationality, *"How many travellers on
  this application?"* (`:226-244`, `min={1}`), and a checkbox — *"I am paying for this
  application myself"* (`:246-260`, default checked) — three fields with zero indication that
  anyone but the traveller could be answering, and no branch for "someone else is filling this
  in for a solo, self-paying traveller."
- **Both answers are hard eligibility gates, by SOP, not by oversight.** `eligibility.py`'s
  docstring (`:1-27`) states the SOP-v0-GARUDA-B1 §1 positive-criteria list verbatim: *"1 adult
  traveler … self-pay"*; `screen()` declines on `not inp.self_pay` → `NOT_SELF_PAY` (`:201-202`)
  and on `family_or_group` (= `travellers > 1`, `intake.py:311`) → `GROUP_CASE` (`:209-210`).
  These are declared **pilot-scope exclusions** (`"excluded from pilot"` appears at every
  exclusion site, `:207-224`), not permanent product law — §5.7 flags the consequence of that.
- **The decline copy is unambiguous about WHY, and it is an owner decision, not a bug.**
  `declineEducation.ts` renders `NOT_SELF_PAY` as *"You told us someone else is paying for this
  application."* → *"The online checkout only accepts payment from the traveller's own card."* →
  *"A consultant can take a third-party payment for you"* (`:147-155`, `routeKind: "whatsapp"`);
  `GROUP_CASE` as *"…travelling with {N} people…"* → *"This online form only files one passport
  at a time…"* → *"A consultant can open and track every passport in your group side by side"*
  (`:118-127`, `routeKind: "whatsapp"`). **Third-party payment and multi-traveller cases are
  already, deliberately, routed to a human — today, only at the very end**, after the visitor has
  already answered case-type, purpose, nationality, traveller count and the payer checkbox
  (`page.tsx` steps `case_type→purpose→trip→dates`, decline surfaces only at
  `[hash]/page.tsx:159` on the result screen).
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
  (`garuda_voa_public.py:545-556` GET, `:575-593` DELETE — the DELETE handler reads the SAME
  cookie name at `:578` and requires it to match at `:585-587`). If a delegate ran the check on
  their own device, **the delegate's browser — not the traveller — holds the only credential
  that can view or delete the result**, unless the delegate later hands the session over.
  `travellers` and `self_pay` are stored on this same row (`286:112-113`) as plain columns —
  present in the schema, never surfaced to a delegate as "this is what you're declaring."
- **The consent ledger can't record a delegate's authorization any more than it can the funnel's
  own consent events (consent-placement lane's finding #5, confirmed again here).**
  `client_consent_log` requires `client_id INTEGER NOT NULL REFERENCES clients(id)`
  (`migration_091_client_consent_log.py:29`) — a CRM-scoped foreign key. GARUDA VOA's anonymous,
  session-cookie funnel produces no `clients` row for either the traveller or the delegate;
  neither actor's authorization event can be written to the one append-only ledger the codebase
  has for exactly this purpose (`:30-31`, `purpose_key`/`action`).

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
is the actual fork `eligibility.py` cares about. §3.1 designs the honest version.

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

## §3 Design decisions (mockup: `mockups/delegate-flow/authorization-checkpoint.html` — the
authorization-checkpoint screen as the pattern's reference implementation; the plain branch
choice that precedes it is declared not drawn, §3.1)

1. **Who-answers gate, first screen, asking the fork the SOP actually cares about — not just
   "who is typing."** Before `case_type` (`page.tsx`'s first live step today), insert a meta
   step with three options, not R5b's two: *"I'm the traveller"* / *"I'm helping one traveller
   who'll answer for themselves — I'm just operating the form"* / *"I'm arranging this for
   someone else, or for more than one person"* — the third option maps directly onto the union
   of `NOT_SELF_PAY ∪ GROUP_CASE` and routes straight to WhatsApp using declineEducation.ts's
   OWN copy (§3.7), before the visitor spends four screens finding out. The second option sets
   `delegate=true` and continues into the wizard pronoun-adjusted (§3.2) — this is the persona
   R4:140 actually cleared. The branch-choice screen itself is declared not drawn here (it is
   R5b's own `who_answers` shape, unchanged in kind — only the option set and destinations
   differ, and those are named above); the mockup draws what comes next for the middle option,
   because that screen is new in substance, not just in wording.
2. **Authorization checkpoint (mockup's subject), modeled on the LIVE guardian-consent shape,
   not invented from scratch.** `ConsentHandoff.tsx`'s `guardianConsentRequired`/`guardianFirst`
   pattern (§1) — a standing-to-act confirmation that gates BEFORE the general consent can be
   actioned — is the direct model: an explicit statement, R5b's own proven copy carried over
   verbatim (*"The traveller asked me to fill this in, and I'll check with them when unsure"*,
   `journey.html:200`), plus one line this design adds that R5b's tree-only context never
   needed: an explicit **scope limit**, because T1 makes the boundary real — *"This does not
   authorize payment on the traveller's behalf. At checkout, payment still has to come from the
   traveller's own card."* Naming the boundary here, before the wizard, is cheaper for the
   visitor than discovering it at the decline screen after finishing the form (T1). Two CTAs:
   continue as delegate, or R5b's own "actually, I'll let the traveller do this" reset
   (`journey.html:451`).
3. **The authorization checkpoint is a FOURTH axis, not a fourth tier of the consent-placement
   lane's three-tier form.** That lane's tiers (notice-acknowledgement / contract-acceptance /
   affirmative-authorization, consent §3.7b) answer "what may this system do with the data";
   this checkpoint answers "does the person clicking have standing to answer for someone else"
   — orthogonal, and it has to be answered FIRST (mirroring `guardianFirst`'s ordering rule,
   `ConsentHandoff.tsx:328-329`) because every later consent surface's "I"/"my" pronoun depends
   on knowing who "I" is.
4. **Delegate banner, ported from R5b, filled honestly.** The persistent strip
   (`journey.html:156-158`) carries over verbatim in shape; its `{CUSTODY_WHO_SEES}` token
   resolves only through the consent-placement lane's §3.8 audit (unchanged — this lane does not
   invent that answer, R4 §5). One line is added that the audit does NOT gate, because it is
   already true today and worth the traveller knowing: *"This browser is what controls this
   result — viewing or deleting it later needs this same device and session, not a login."*
   (§5.2's finding, stated as the honest present tense, not a future promise.)
5. **Pronoun layer reuses R5b's tag convention, extended past the tree to the whole VOA
   funnel.** The same `@you@`/`@your@` replace-tags, the same `pron()` rewrite rule
   (`journey.html:336-342`), applied to `page.tsx`'s own copy — most concretely the payer
   checkbox, which in delegate mode reads *"The traveller will pay for this application
   themselves"* (a statement the delegate confirms on the traveller's behalf, per the
   authorization already given) rather than *"I am paying"* — removing the first-person
   identity-collapse `page.tsx:259` carries today. `upload/messages.ts` and `CheckoutFlow.tsx`'s
   copy get the same tag treatment; §4 makes an un-rewritten string in delegate mode a failed
   build.
6. **Checkout labels the contact fields, and never calls the compiler a "sponsor."** Delegate
   mode relabels the bare *"Email"*/*"Phone"* fields (`CheckoutFlow.tsx:105-135`) to *"Traveller's
   contact — for the receipt and any questions about this application"*; if the design later
   needs a second, delegate-owned contact field, that is a schema change (§5.1) this lane does
   not perform. Nowhere does delegate-mode copy use the word "sponsor" for the compiler role —
   the codebase's `family_sponsor_*` vocabulary (§1) already owns that word for a different
   fact, and reusing it here would silently create a second meaning the way R3's own inventory
   warns against.
7. **The early WhatsApp exit reuses `declineEducation.ts`'s exact copy shape, not a new
   vocabulary.** When the who-answers gate's third option is chosen, the routing screen renders
   the SAME mirror → forbids → alternative structure and, where the visitor has already stated
   travellers>1 or third-party payment, the literal `GROUP_CASE`/`NOT_SELF_PAY` copy
   (`declineEducation.ts:118-127,147-155`) — so a consultant reading a WhatsApp handoff sees
   identical framing whether the visitor exited at question one (this design) or question twelve
   (today's path). No second decline-copy authority is created.
8. **Check-with-the-traveller escapes, ported verbatim in kind.** Every `notSure` affordance
   downstream, in delegate mode, offers R5b's own phrasing — *"check with the traveller, or hand
   this to a person"* (`journey.html:396`) — instead of the self-mode default.
9. **Identity header + trust footer, R4:108/R7 §2 amendment 4, unchanged law.** Same wordmark,
   EN·ID toggle, WhatsApp entry, and role-separation + PT/NPWP/registry + office-address footer
   the checkout and consent-placement mockups already carry — this screen sits in the same
   perimeter and inherits the same law, not a new decision.

## §4 Behavioral acceptance (what a build must prove)

- The who-answers gate renders before `case_type`; choosing "I'm the traveller" reaches today's
  live flow completely unchanged — this design must not alter one string or one gate on the
  self path (would_fail_if: any self-mode screen differs from main today).
- Choosing the delegate option and confirming the authorization checkpoint sets `delegate=true`
  for the rest of the session; every downstream screen's tagged copy renders in third person —
  a screen showing an un-rewritten `@you@`/`@your@` tag, or a first-person string with no tag at
  all, while `delegate===true` is a failed build (R5b's own acceptance bar, ported).
- Choosing "arranging for someone else / more than one person" at the gate routes to the
  WhatsApp handoff BEFORE `case_type` renders — no eligibility question is ever asked of a
  visitor who has already declared themselves outside SOP-v0-GARUDA-B1 §1's scope.
- The authorization checkpoint blocks all progress until confirmed — mirroring
  `ConsentHandoff.tsx`'s `guardianConsentRequired && !guardianConfirmed` guard
  (`:245`) — and cannot be pre-checked.
- Checkout's email/phone fields never render with a bare, unlabeled prompt while
  `delegate===true` (would_fail_if: the generic "Email"/"Phone" labels survive into delegate
  mode).
- The delegate banner never renders a resolved `{CUSTODY_WHO_SEES}` value until the
  consent-placement lane's audit (§3.8 there) has produced one — an invented value here is a
  failed build under R4 §5's own law, inherited, not re-declared.
- No screen, in either mode, ever labels the compiler's role "sponsor."

## §5 Findings handed to product lanes (not design's to fix)

1. **`garuda_orders` has no applicant/payer separation** — R4:140 named this as an implication
   of the delegate flow; today's schema (`284:52-55`) has only `applicant_*` columns. If a
   delegate's own contact needs to be stored distinctly from the traveller's, that is a new
   column set, not a copy fix. (class a)
2. **The deletion/view right is bound to the session cookie, not to the traveller** — a
   traveller who never touched the originating browser has no path to invoke their own
   `deleteEligibilityResult` right (`garuda_voa_public.py:575-593`) unless the delegate hands
   over the session. This compounds the consent-placement lane's finding #4 (the endpoint has
   no user-facing surface at all yet) with a second, harder question: whose surface would it
   even be, in delegate mode. (class a)
3. **`client_consent_log`'s `client_id` FK (`091:29`) still can't record either actor's
   authorization event** — the consent-placement lane already flagged this for the funnel's own
   consent events (its finding #5); this lane confirms the same gap now has two actors who might
   need an entry (traveller's authorization-to-delegate, delegate's confirmation-of-standing),
   not one. (class a)
4. **The early-exit gate is a genuinely new behavior with no measurement plan.** Moving the
   WhatsApp routing decision from the last screen (today) to the first (§3.1) should reduce
   wasted effort for the ~2 declined shapes, but nobody has measured whether an earlier "talk to
   a person" costs conversions a later one wouldn't have — recommend instrumenting the gate's
   exit rate before this ships past a small cohort, not assuming the earlier exit is strictly
   better. (class c)
5. **"Sponsor" is already a taken word in this codebase for a different fact** — the family
   route's `family_sponsor_*` vocabulary (`fact-mapper.ts:628-645`) names the person being
   sponsored FOR, not the person filling in the form. This design deliberately never uses
   "sponsor" for the compiler role (§3.6); any future copy pass on delegate-mode strings should
   hold that line. (class c)
6. **i18n is explicitly out of scope here, and is R7 backlog item 5's job, in that order** — R7
   §4 places item 5 ("i18n for the sponsor") after item 4 precisely because it "presupposes item
   4's surface" (R7:188-190); Bahasa Indonesia copy for the who-answers gate, the authorization
   checkpoint, and the pronoun-rewritten strings is not drawn here. (business/lane decision,
   already sequenced by R7)
7. **`NOT_SELF_PAY`/`GROUP_CASE` are PILOT-scope exclusions, not permanent product law** — every
   decline site in `eligibility.py` says "excluded from pilot" (`:207-224`) against
   SOP-v0-GARUDA-B1 §1. If the pilot later widens to accept third-party payment or multiple
   travellers, the who-answers gate's third option stops being a hard WhatsApp routing rule and
   becomes a real fork (self-pay-solo → online; third-party/group → still a product decision,
   not necessarily WhatsApp) — flagging so a future gate rebuild doesn't have to rediscover that
   today's routing is pilot-shaped, not law-shaped. (class c)
8. **The guardian-consent pattern this design borrows lives in a different code surface**
   (`ConsentHandoff.tsx`, the Oracle) **from the one this design targets** (GARUDA VOA's own
   wizard) — this lane borrows the shape, not the component; a future consolidation of the two
   authorization-checkpoint implementations is a refactor question, not something this design
   performs. (class c)

## §6 Declarations (adopted under the standing pre-confirmation, async veto open)

1. **The who-answers gate asks the SOP's own fork, not just "who is typing."** Three options —
   traveller / delegate-for-a-solo-self-payer / arranging-for-someone-else-or-a-group — with the
   third routing to WhatsApp before any eligibility question. Alternative: R5b's original binary
   `self`/`delegate` split, deferred discovery to the existing decline screen (rejected: T1 —
   the SOP's real fork is not "who types," and deferring it costs the visitor four to five
   screens for a "talk to a person" outcome a first question could give immediately).
2. **The authorization checkpoint is modeled on the live guardian-consent shape and carries an
   explicit payment-scope limit.** Alternative: reuse R5b's `delegate_confirm` copy unchanged,
   with no added scope line (rejected: R5b's tree-only context never had to face
   `NOT_SELF_PAY` — this funnel does, and silence on the boundary would let a delegate believe
   they can pay when `eligibility.py` will decline them for it).
3. **Standing-to-act is a fourth axis, sequenced before the consent-placement lane's three-tier
   form, never folded into it.** Alternative: add "delegate authorization" as a fourth consent
   tier (rejected: that lane's tiers answer what the system may do with data; this checkpoint
   answers who has standing to answer at all — conflating them would make the consent-placement
   lane's own three-tier mapping, already handed to legal, incorrect by addition after the fact).
4. **The applicant/payer/filler data-model gap is named as a finding, not patched with copy.**
   Alternative: invent a `{DELEGATE_CONTACT}` field in the checkout mockup as if the schema
   already supported it (rejected: R4 §5 forbids invented reassurance on a surface the schema
   cannot back — §5.1 hands the actual column design to the owning lane).

## §Meta

R5b proved the mechanics were buildable — a pronoun function, a meta question, an escape
phrase. What this round of grounding on the *live* funnel adds is the fact R5b's tree-only
context had no way to surface: the delegate persona R4 cleared is narrower than "someone else is
typing" — it is "someone else is typing, for exactly one traveller, who pays with their own
card" — because `eligibility.py`'s own SOP already draws that second line, in code, today, and
the decline copy that fires on it is not a bug to design around but an owner decision to design
*with*. The pattern that ships is the one R5b already validated, aimed at the funnel that
actually exists, honest about the one boundary the tree study never had to be honest about.
