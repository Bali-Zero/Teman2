---
date: 2026-08-28
domain: design
client_case: none
round: build-lane design deliverable (post-loop) — sponsor i18n, R7 §4 item 5
sources:
  - R7 doctrine + backlog — research/design/2026-08-27-r7-doctrine-loop-closure.md (item 5, §4:188-190; item 4, §4:184-187)
  - R4 identity law (P6 EN/ID toggle, funnel-wide scope, delegate clause) — research/design/2026-08-27-r4-identity-merah-putih-token-spec.md:108,122,124,130,140
  - R1 psychology (P3 spouse/sponsor persona, trust triggers) — research/design/2026-08-27-r1-psicologia-utente-personas-mappa-emotiva.md:70
  - R6 walkthrough (P3 Wharton-pass scope limit on the EN-only delegate flow) — research/design/2026-08-27-r6-walkthrough-perception-runtime.md:88-105,290-291,304
  - R5b prototype (the only place a delegate flow exists in this repo) — research/design/mockups/r5b-tree-as-journey/journey.html; its own dossier research/design/2026-08-27-r5b-tree-as-journey-interactive-prototype.md:103-121,145-146
  - checkout lane (visual identity, tokens, trust footer, custody-line pattern reused here) — research/design/2026-08-27-checkout-garuda-design.md; mockups/checkout-garuda/checkout.html
  - consent-placement lane (custody component, two-density pattern reused here) — research/design/2026-08-27-consent-placement-design.md; mockups/consent-placement/a4-dates-consent.html
  - live surfaces read this round — apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/i18n.ts, _components/LanguageToggle.tsx, apps/mouth/src/app/visa/voa/checkout/[resultId]/CheckoutFlow.tsx, apps/mouth/src/i18n/ (global provider, locales/{en,id,it,fr,ru}.json), apps/mouth/src/app/visa/second-home/[locale]/
adversarial_review: pending — this deliverable has NOT gone through the round-grade panel. Per the mandate, the conductor runs that panel and ships; this file's §6 is written as PROPOSED, not adopted, following R7 §3.1's own evidence-class discipline rather than borrowing the checkout/consent lanes' "adopted" framing before a panel has actually run.
---

# Sponsor i18n — designing language for a surface that doesn't exist yet

**What this file is.** Third build-lane design deliverable of the R7 §4 backlog. Item 5,
verbatim (R7:188-190): "**i18n for the sponsor** — the delegate flow cannot pass Wharton for
an Indonesian sponsor until it speaks Bahasa (R6-P3's blocking scope limit); i18n presupposes
item 4's surface and also covers the wider funnel." Study only: no product code,
`GARUDA_PUBLIC_ENABLED` untouched, no locale JSON edited, no PII.

The mandate's own text names its hardest constraint: this round designs language for a
surface — the delegate flow, R7 backlog item 4 — that **does not exist as a product surface**.
It exists only as a study prototype (R5b's `journey.html`). This file is therefore
prospective by construction: a translated key-set and a component pattern for item 4's build
lane to consume, not a fix to a live screen. §1 grounds exactly how prospective, and how far
the "also covers the wider funnel" clause reaches once the live tree is actually read.

## §1 Ground — what actually exists (class a unless marked; read from this worktree's checkout
of origin/main, this round)

**The delegate flow itself is R5b's prototype, nowhere else.** `grep`-ing the live
`apps/mouth/src/app/(visa-oracle)/visa-oracle/` tree and the live `apps/mouth/src/app/visa/voa/`
tree for "delegate" or "Delegate" returns zero hits in either. The only place `who_answers`,
`delegate_confirm`, a delegate banner, or a pronoun layer exist in this repository is
`research/design/mockups/r5b-tree-as-journey/journey.html` — a study artifact, not shipped
code. R4:140 already states the LAW the moment item 4 ships: "the identity must not block a
delegate-compiler flow — EN/ID, editable review, opaque-code handoff all serve the delegate;
no fourth persona is adopted … and R5b owns the delegate at journey level." The law exists;
the surface it binds does not yet.

**R6's own P3 walkthrough already found the exact gap this item exists to close** (R6:102-105):
"**Scope limit on the Wharton pass**: it holds for an EN-reading operator; for the Indonesian
sponsor persona the delegate flow is EN-only with the ID toggle honestly disabled, so Wharton
Q1-Q3 CANNOT pass for her until the product i18n lands." "Wharton" is this loop's own term of
art for the walkthrough's pass/fail bar (used identically at R6:88-109 and R6:304, e.g. "M5
supported+payment. Wharton passes: verdict, price, rails…") — not a typo, not this file's
invention; quoted verbatim from the source it was coined in.

**The delegate prototype's pronoun mechanism is a plain JS regex, English-structural, and
untranslated** (`journey.html:336-343`):
```
function pron(s){ return delegate
  ? s.replace(/@Are you@/g,"Is the traveller").replace(/@Do you@/g,"Does the traveller")
     .replace(/@Have you@/g,"Has the traveller").replace(/@are you@/g,"is the traveller")
     .replace(/@do you@/g,"does the traveller").replace(/@you@/g,"the traveller")
     .replace(/@Your@/g,"The traveller's").replace(/@your@/g,"the traveller's")
     .replace(/@yours@/g,"theirs").replace(/@You@/g,"The traveller")
  : s.replace(/@([^@]+)@/g,"$1"); }
```
It runs on strings like `family_relation`'s `branchNote:"@Your@ sponsor — 6 questions"`
(journey.html:211) and the not-sure escape `delegate?"check with the traveller, or hand this
to a person":"a person can pick this up"` (journey.html:396). There is exactly one dictionary
in this whole flow — English — and the substitution table is a closed set of ten English
2nd-person surface forms swapped for one fixed 3rd-person phrase each. §2.1 explains why this
specific mechanism does not survive translation, as opposed to merely lacking one.

**The delegate banner and meta-questions carry the only load-bearing copy that needs
translating**, verbatim from the prototype (journey.html:156-157, 199-200):
- `who_answers` — label "Who is filling this in?"; why "If someone is helping — a sponsor, a
  family member, an assistant — we adapt the wording. The answers must still be the
  traveller's facts."; options "I'm the traveller" / "I'm helping someone else".
- `delegate_confirm` (delegate-only) — label "Answering for the traveller"; why "Their
  immigration history is theirs to share. Confirm they asked you to do this — and if you
  don't know an answer, say so instead of guessing."; options "The traveller asked me to fill
  this in, and I'll check with them when unsure" / "Actually, I'll let the traveller do it".
- `delegateBanner` (shown once `delegate_confirm==="confirmed"`, journey.html:444) — "**You're
  answering for someone else.** Their case, their facts — answer as the traveller would. Who
  sees what: `{CUSTODY_WHO_SEES}`."

**Three DIFFERENT i18n mechanisms already coexist in this codebase, at three different
scopes** — conflating them is the first mistake this design refuses to make:
1. **The global content provider** (`apps/mouth/src/i18n/`) — five locales
   (`en/id/it/fr/ru.json`), used for marketing articles, workspace/portal settings
   (`LanguageSettings.tsx`), and `visa/second-home/[locale]/` routing. Site-wide scope, not
   funnel-scoped.
2. **The Visa Oracle's own standalone dictionary** (`_lib/i18n.ts`) — EN canonical key set,
   `id` typed as `Record<Keys, string>` so a missing/extra Indonesian key is a **TypeScript
   build error**, re-checked at runtime by `i18n.test.ts` as defense-in-depth. Its own header
   comment states why it is separate: "Deliberately NOT the global `src/i18n` provider (spec
   item 30 — avoids the I18nProvider lint chain; this route is a standalone experience)." Its
   own ID-register law, quoted verbatim from the file: "body-first, warm-formal, 'Anda' never
   'kamu', Imigrasi's own terminology natively — not machine-translated." This dictionary
   **already translates every traveller-facing sponsor QUESTION** — `q.sponsor_category`,
   `q.family_relation`, `q.family_sponsor_nationalities`, `q.family_sponsor_status_code`,
   `q.family_sponsor_permit_basis`, `q.family_marriage_registered`, all with ID mirrors
   (i18n.ts:191-398 EN, matching ID block starting :828). What it does NOT cover is the
   delegate MODE — the case where the sponsor is the one operating the screen, not the subject
   of a question asked to the traveller. `who_answers`/`delegate_confirm`/the banner/`pron()`
   exist ONLY in the R5b prototype and were never ported into this dictionary.
3. **No mechanism at all in GARUDA checkout.** `apps/mouth/src/app/visa/voa/checkout/
   [resultId]/CheckoutFlow.tsx` (192 lines, read in full this round) contains zero
   `useLanguage`/`locale`/`'id'` references — nothing. Yet the checkout **design mockup**
   (R7 backlog item 1, PR-landed 2026-08-27) already renders `<a href="{LANG_TOGGLE}"
   aria-label="Ganti bahasa">EN · ID</a>` in its identity header, per R4:108's law that every
   funnel screen carries the toggle. **The mockup promises a control the live surface has
   nothing to serve it with.** This is the "also covers the wider funnel" half of item 5's own
   text, made concrete: it is not a polish request, it is a load-bearing gap on the funnel's
   OWN highest-risk step (checkout dossier §1: R1 rated it 5-quits).

**R1's psychology grounding for why this matters, not just that it is owed** (R1:70, P3
persona): "Trust triggers: 'Not sure?' that leads to a person, every fact editable before the
verdict, **Bahasa Indonesia for the sponsor and English for the applicant** (CSA 2020: 88% of
Indonesian consumers prefer their own language; EF EPI 2025 Indonesia 'low')." The persona
whose trust trigger THIS ITEM exists to satisfy is sourced, not assumed.

## §2 The two tensions this design resolves

**T1 — `pron()`'s substitution is a property of English, not a translatable artifact.**
English marks the 2nd person with one small closed set of surface forms — you/your/yours,
uniform across singular and plural, formal and informal — so a ten-entry regex table can
losslessly rewrite "you" into "the traveller" anywhere it appears. Indonesian has no
equivalent closed set to hook the same regex onto: formal register commonly **drops the
subject pronoun entirely** ("Sudah menikah?" needs no "Anda" to be a complete, correct,
polite question), and the direct-address pronoun that DOES exist ("Anda") is doing a
different job in delegate mode than English "you" does — in delegate mode, "you" the reader
IS the sponsor, and "the traveller" is a THIRD person the sponsor is answering about. A
regex built to turn "you" into "the traveller" has nothing to grab in Indonesian, because the
Indonesian sentence very often never says "Anda" in the first place — and where it must name
someone, repeating a bare pronoun ("dia") reads as informal and referentially thin in a
formal register that instead prefers the noun ("wisatawan") or the resolved relation
("pasangan Anda"). Porting the regex table 1:1 would either do nothing (no "you" token to
replace) or produce a stilted, over-explicit Indonesian that repeats "wisatawan" where a
native writer would drop the subject — the opposite failure mode from English, which needs
the pronoun stated to disambiguate self vs. delegate mode at all. §3.1 resolves this by
replacing template+substitution with **authored self/delegate STRING VARIANTS per locale**,
matching the pattern `_lib/i18n.ts` already uses (a full key per meaning, never a derived
string) rather than inventing a second substitution mechanism for Indonesian.

**T2 — "EN/ID everywhere" is funnel LAW (R4 P6) with real infrastructure on exactly one of
three surfaces this item's own text names.** R4:124 lists "P6 the EN/ID toggle as shell
component" among the six organs binding "every screen in the perimeter." The interview tree
(`_lib/i18n.ts`) already delivers it, compile-time enforced. The delegate flow (R5b) delivers
it nowhere — R6 already caught this ("the ID toggle honestly disabled"). Checkout (item 1)
renders the CONTROL in its mockup with no dictionary behind it at all — not even an English
one, since the live page has no i18n hook to begin with. The law is uniform; the
infrastructure is not, and item 5's "also covers the wider funnel" clause is the doctrine
catching up to that gap.

## §3 Design decisions (mockup: `mockups/sponsor-i18n/delegate-i18n.html`, side-by-side EN/ID
comparison layout — not mobile-single-column like the shipped-surface mockups, because this
study's own purpose is bilingual comparison, not a single screen state; light theme, same
tokens as the checkout/consent lanes)

1. **Extend `_lib/i18n.ts`'s pattern, not `journey.html`'s regex, when item 4 ships.** Every
   string that today carries a `@token@` gets TWO keys instead — one full, hand-authored
   sentence per mode, per locale (e.g. `who_answers.why` stays one key since it does not
   depend on mode, but `family_relation.branchNote.self` / `.delegate` become two keys, each
   translated on its own terms). This is not more work than `_lib/i18n.ts` already does for
   every other question in this file — it already authors full ID sentences per key rather
   than deriving them; delegate mode is the same discipline applied to the meta layer the
   prototype left out.
2. **Register split, grounded in T1**: Indonesian copy addresses the sponsor directly as
   "Anda" (formal, per the dictionary's own P6 law) at the META questions
   (`who_answers`/`delegate_confirm`, where the sponsor IS the addressee) — and refers to the
   traveller in the THIRD person using a concrete noun, never a bare pronoun ("dia"). Before
   `family_relation` resolves (who_answers/delegate_confirm both fire earlier in the tree —
   journey.html:199-200 vs. :211), the neutral noun is **"wisatawan"** (the traveller); after
   `family_relation` resolves to a known value, downstream copy MAY use the resolved relation
   noun ("pasangan Anda" — your spouse) instead — a recommendation to the build lane (§5.3),
   since no downstream string in the current prototype was found that would need it (class c,
   not measured against a string that does not exist yet).
3. **Translation strategy is deliberately NOT one rule — it splits by copy TYPE**, and the
   mockup shows both with a literal back-translation so the split is falsifiable, not
   asserted:
   - **Faithful/literal** for procedural, regulatory-adjacent copy where R4 §5's "no invented
     reassurance, no dropped nuance" constraint is highest-stakes: the custody hint, the
     retention line, the trust footer. A paraphrase here risks silently adding or dropping a
     legal claim the way R6's own honesty-register work worried about.
   - **Cultural reformulation** for persuasive/reassurance copy whose ENGLISH RHETORIC does
     not survive literal translation: the delegate banner's "Their case, their facts" is
     English chiasmus (a parallel repetition structure); translated literally ("Kasus mereka,
     fakta mereka") it reads as translated-not-written and the plural "mereka" (they/them)
     is colder than the warm-formal register the rest of this dictionary holds. §3.4 shows
     both forms side by side with the reasoning, not just the winner.
4. **The literal-vs-reformulated example, in full** (mockup §"Translation strategy" panel):
   - Literal attempt: *"Anda sedang menjawab untuk orang lain. Kasus mereka, fakta mereka —
     jawablah seperti wisatawan akan menjawab. Siapa yang melihat apa: {CUSTODY_WHO_SEES}."*
     Rejected: the repetition reads as translated, "mereka" under-specifies a single named
     relation the flow already knows in most cases, and "seperti wisatawan akan menjawab"
     (as the traveller would answer) is a hypothetical construction where Indonesian prefers
     a direct instruction.
   - Recommended: *"Anda sedang menjawab atas nama wisatawan. Jawablah sesuai fakta miliknya,
     bukan pendapat Anda sendiri — siapa yang dapat melihat jawaban ini:
     {CUSTODY_WHO_SEES}."* Keeps every regulatory-honesty commitment of the English (answer
     as the fact-holder, not a guesser; disclose who sees the answer) in a direct-instruction
     register matching the dictionary's own existing tone (compare `framing.body`: "Jawab
     dengan jujur, termasuk 'Saya tidak tahu.'" — i18n.ts:831).
5. **Placeholders stay locale-invariant tokens** (`{RETENTION_WINDOW}`, `{CUSTODY_WHO_SEES}`,
   `{PT_LEGAL_NAME}`, `{NPWP}`, `{SLA}`) — only the surrounding prose translates. The
   RESOLVED value is itself a locale-aware render (a duration or a date formats differently
   in `id-ID` than `en`), which §4 makes an acceptance check rather than an assumption, so a
   shared token is never mistaken for a shared literal string.
6. **Scope law, stated explicitly so it cannot be over-read**: this design is EN/ID ONLY,
   matching R4 P6's funnel perimeter — never RU/IT/FR. Those three exist in the SEPARATE
   global content provider (marketing articles, `second-home/[locale]`) and are out of scope
   here by construction, not by omission; the mockup's language control renders exactly two
   options, matching `LanguageToggle.tsx`'s existing `aria-pressed` EN/ID pair
   (`_components/LanguageToggle.tsx:46-56`) rather than inventing a five-way switcher.
7. **Statutory and proper-noun terms are preserved unchanged across both locales** — "Ditjen
   Imigrasi", "PT", "NPWP", "KITAS/KITAS", "WhatsApp" are not translated in the EN copy
   either (i18n.ts never anglicizes them); the ID column keeps them byte-identical, per the
   dictionary's own "Imigrasi's own terminology natively — not machine-translated" law.
8. **Identity header, custody hint, and trust footer are reused verbatim from the checkout
   and consent lanes**, not redrawn — same CSS custom properties (`--carta`, `--merah-action`,
   `--font-display`, the rem type scale, the 44px touch-target floor), same component
   contracts (the custody component's two densities from the consent lane, §6.1 there;
   applied here at the delegate banner's HIGH-sensitivity tier because the banner discloses
   who sees the answer, the same reason A6/checkout/Oracle-interview-start got the full
   module in that lane).

## §4 Behavioral acceptance (what a build of item 4 must prove, once it exists)

- A missing or extra Indonesian key in a delegate-mode dictionary is a TypeScript build
  error, matching `_lib/i18n.ts`'s existing `Record<Keys, string>` + `i18n.test.ts` parity
  pattern — never a silent English fallback.
- No string in the shipped delegate flow is produced by regex substitution on an English
  base string; every self/delegate variant, in every locale, is an authored dictionary entry.
  (would_fail_if: a `.replace(/@…@/g` pattern, or equivalent, appears in the shipped
  component.)
- The neutral noun ("wisatawan") renders for every meta-question that fires before
  `family_relation` resolves, in both languages; a resolved-relation noun never appears
  before the fact that would resolve it has been answered.
- The checkout page's `{LANG_TOGGLE}` control is wired to an actual dictionary before it
  ships publicly — an EN/ID toggle rendered with no dictionary behind it (today's live
  state) is a failed build, not a cosmetic gap. (would_fail_if: `CheckoutFlow.tsx` renders
  the toggle markup with zero locale-branching logic reachable from it.)
- Placeholder tokens are byte-identical across the EN and ID dictionary entries that share
  them; only the surrounding prose differs. (would_fail_if: the same semantic placeholder
  has two different token spellings across locales.)
- The delegate banner, custody hint, and trust footer render at the SAME visual density and
  position contract as their EN counterparts — translation must never silently promote a
  compact hint to a full module or vice versa because the ID string is longer or shorter.

## §5 Findings handed to product lanes (not design's to fix)

1. **`CheckoutFlow.tsx` has zero i18n infrastructure** while its own R7-item-1 mockup already
   renders an EN/ID toggle in the identity header. Either the toggle is scoped OUT of the
   checkout build's first cut (and the mockup's header comment should say so), or checkout's
   build lane inherits `_lib/i18n.ts`'s pattern before the toggle ships live. Today it is a
   promise with nothing behind it. (class a)
2. **Item 4 (delegate flow as product surface) is the hard dependency this item's own text
   names** (R7:190: "i18n presupposes item 4's surface") — there is no live delegate mode to
   localize yet; this dossier is the key-set and pattern item 4's build lane should consume
   rather than porting `journey.html`'s `pron()` mechanism as-is. (class a)
3. **The relation-specific noun for POST-`family_relation` screens is a recommendation, not
   a measured requirement** — no string in the current prototype needed it because the
   prototype's own downstream sponsor-detail screens (the six-question sub-flow) were not
   read for pronoun content this round; the product lane should re-ground this specific point
   against the actual downstream copy once it exists, rather than trusting §3.2's
   extrapolation blind. (class c)
4. **The global 5-locale provider and the funnel's EN/ID law are two different systems with
   two different scopes** — a future contributor reaching for `apps/mouth/src/i18n/` inside
   the GARUDA/Oracle perimeter would be reaching for the wrong tool; this is worth a code
   comment at the point of first delegate-mode dictionary creation, not just a design note.
   (class c)
5. **The sponsor sub-progress badge** ("Sponsor {i} of {n}", journey.html render logic) needs
   an Indonesian ordinal convention, not a literal "Sponsor {i} dari {n}" — "ke-{i}" is the
   natural Indonesian ordinal marker ("Sponsor ke-{i} dari {n}"). Flagged here because it is
   a small, easy-to-miss instance of the same literal-vs-natural tension §3.3/§3.4 resolve at
   larger scale. (class c)
6. **CSA 2020 / EF EPI 2025 citations** (R1:70) are the psychology grounding for WHY this
   item matters, not just that R7 lists it — worth carrying into item 4's own build-lane
   dossier so the requirement does not read as pure process compliance when it lands. (class c)

## §6 Proposed declarations (DRAFT — round-grade panel and dispositions pending)

Per R7 §3.2, a design deliverable carrying declarations that decide surface behavior goes
through a round-grade panel before adoption. This deliverable has not yet had one — the
mandate that commissioned it names the conductor as the party who runs that panel and ships.
Writing these as already "adopted under the standing pre-confirmation" (the checkout and
consent lanes' own framing, after THEIR panels ran) would misstate this file's own evidence
class under R7 §3.1 — an unclassed or falsely-elevated claim is exactly the failure mode that
ladder exists to catch. These four are therefore proposals for the panel to accept, amend, or
reject:

1. **Self/delegate variants replace pronoun-substitution as the mechanism for any locale
   beyond English** (§3.1). Alternative considered: extend `pron()`'s regex table with an
   Indonesian branch (rejected in this draft — §2's T1 argument is that Indonesian has no
   closed pronoun set to hook a regex onto; a panel with filesystem access should verify this
   against the actual prototype code before the alternative is closed out, per R7 §3.2's
   filesystem-seat requirement on any claim citing live tree/DB/filesystem state).
2. **Neutral-noun ("wisatawan") default before `family_relation` resolves, resolved-relation
   noun optionally after** (§3.2, §5.3). Alternative: always use "wisatawan" regardless of
   resolution state (simpler, no re-grounding needed against unread downstream strings —
   a real trade-off the panel should weigh against the warmth cost of a fixed generic term).
3. **Faithful translation for procedural/legal copy, cultural reformulation for
   persuasion/reassurance copy, as a named split rather than a single translation policy**
   (§3.3-§3.4). Alternative: one policy (either "always literal" or "always localized"),
   rejected in this draft because the two shown examples (custody hint vs. delegate banner)
   demonstrably need different treatment — but this is this file's own untested judgment
   call, not yet panel-verified.
4. **Item 4's build lane inherits `_lib/i18n.ts`'s compile-time-parity dictionary pattern
   rather than inventing a fourth i18n mechanism** (§3.1, §5.4). Alternative: a delegate-mode
   dictionary lives inside the global `src/i18n` provider instead (rejected in this draft —
   the standalone-dictionary lane's own stated reason for existing, avoiding the
   I18nProvider lint chain per its header comment, applies here too — but this reasoning
   should be checked against that lint chain directly, which this round did not read).

## §Meta

This lane's honest position is that it designed language for a screen nobody has built yet,
grounded in a prototype nobody is shipping as-is. That is not a weakness to hide — R7 §4's
own backlog ordering put the risk-order ahead of the schedule and named this item's
dependency on item 4 in its own text. What this file could actually verify against the live
tree turned out to matter more than the delegate flow itself: a live checkout page, already
designed with an EN/ID toggle in its header, that has no dictionary behind that toggle at
all. The mandate said "also covers the wider funnel" as an afterthought clause; the ground
pass found that the wider funnel is where the actual, present-tense gap lives.
