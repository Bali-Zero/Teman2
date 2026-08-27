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
adversarial_review: codex
adversarial_review_detail: joint round-grade panel with the delegate-flow (item 4) dossier, run 2026-08-28 — codex gpt-5.6-sol xhigh filesystem (13) · kimi k3 filesystem (15) · agy gemini-3.1-pro inline (12) · qwen3.8-max inline (17) = 57 raw findings, deduped to 27 register rows (23 apply / 3 partial / embedded rejects on R11's second-field proposal and R21.v) + 1 independent Explore verification pass (10 load-bearing claims: 8 true, 1 imprecise, 1 false-by-letter); register and raw seat outputs archived in mockups/sponsor-i18n/panel/; dispositions in mockups/sponsor-i18n/adversarial.json. This file's earlier "PROPOSED, panel pending" framing (2026-08-28 draft) is superseded — see §6.
---

# Sponsor i18n — designing language for a surface that doesn't exist yet

**What this file is.** Third build-lane design deliverable of the R7 §4 backlog. Item 5,
verbatim (R7:188-190): "**i18n for the sponsor** — the delegate flow cannot pass Wharton for
an Indonesian sponsor until it speaks Bahasa (R6-P3's blocking scope limit); i18n presupposes
item 4's surface and also covers the wider funnel." Study only: no product code,
`GARUDA_PUBLIC_ENABLED` untouched, no locale JSON edited, no PII.

**Retitled subject, post-panel (R9).** "Sponsor i18n" above is R7's OWN backlog label, quoted
as the mandate's name for this item — it is not this file's claim about who the persona is.
The joint panel (R9: agy F4, codex F3+F12, kimi F2, qwen F7) found this dossier's draft
conflating two distinct roles the codebase already keeps separate: the **compiler/delegate**
(whoever operates the screen — a helper, an assistant, a spouse; no legal standing) and the
**sponsor** (the codebase's own `family_sponsor_*` term, the family-route immigration
guarantor). This file's actual subject is **delegate-mode i18n** — language for the person
operating the form, not for the family sponsor persona. §1 documents R5b's SOURCE copy
verbatim where it uses "sponsor" for the compiler (that is what the prototype currently
says); §3/§9 declare where this design DEPARTS from that source text to fix the vocabulary,
and each departure is marked as a declared edit, never silent.

The mandate's own text names its hardest constraint: this round designs language for a
surface — the delegate flow, R7 backlog item 4 — that **does not exist as a product surface**.
It exists only as a study prototype (R5b's `journey.html`). This file is therefore
prospective by construction: a translated key-set and a component pattern for item 4's build
lane to consume, not a fix to a live screen. §1 grounds exactly how prospective, and how far
the "also covers the wider funnel" clause reaches once the live tree is actually read.

## §1 Ground — what actually exists (class a unless marked; read from this worktree's checkout
of origin/main, this round)

**(class a) The delegate flow itself is R5b's prototype, nowhere else.** `grep`-ing the live
`apps/mouth/src/app/(visa-oracle)/visa-oracle/` tree and the live `apps/mouth/src/app/visa/voa/`
tree for "delegate" or "Delegate" returns zero hits for the compiler/helper persona this file
designs for — qualified post-panel (R19: kimi F8 + Explore verifier claim 1): one incidental
verb hit exists elsewhere in the tree, `flow.ts:1208`, the English verb "Delegate to …",
unrelated to this persona. The only place `who_answers`,
`delegate_confirm`, a delegate banner, or a pronoun layer exist in this repository is
`research/design/mockups/r5b-tree-as-journey/journey.html` — a study artifact, not shipped
code. R4:140 already states the LAW the moment item 4 ships: "the identity must not block a
delegate-compiler flow — EN/ID, editable review, opaque-code handoff all serve the delegate;
no fourth persona is adopted … and R5b owns the delegate at journey level." The law exists;
the surface it binds does not yet.

**(class e — quoted from R6, re-verify at consumption) R6's own P3 walkthrough already found
the exact gap this item exists to close, and is this file's SOLE persona anchor post-panel
(R14 — see the retraction below)** (R6:102-105): "**Scope limit on the Wharton pass**: it
holds for an EN-reading operator; for the Indonesian sponsor persona the delegate flow is
EN-only with the ID toggle honestly disabled, so Wharton Q1-Q3 CANNOT pass for her until the
product i18n lands." "Wharton" is this loop's own term of art for the walkthrough's pass/fail
bar (used identically at R6:88-109 and R6:119-120, e.g. "M5 supported+payment. Wharton
passes: verdict, price, rails…" — pin corrected post-panel, R21: this quote sits at
R6:119-120, not R6:304) — not a typo, not this file's invention; quoted verbatim from the
source it was coined in.

**(class a) The delegate prototype's pronoun mechanism is a plain JS regex, English-structural, and
untranslated** (`journey.html:336-342` — pin corrected post-panel, R21):
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

**(class a) The delegate banner and meta-questions carry the only load-bearing copy that needs
translating**, verbatim from the prototype (journey.html:156-158, 199-200 — banner pin
corrected post-panel, R21). **This is the SOURCE text as it exists today, unedited** — §3.9/§6
declare where the design departs from it (R9: "a sponsor" in `who_answers.why` is scrubbed at
the copy-authoring layer, since the codebase reserves "sponsor" for `family_sponsor_*`; the
ground quote below is left intact because it accurately reports what the prototype currently
says, not what this design ships):
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

**(class a, tree-read this round) Three DIFFERENT i18n mechanisms already coexist in this
codebase, at three different scopes** — conflating them is the first mistake this design
refuses to make:
1. **The global content provider** (`apps/mouth/src/i18n/`) — five locales
   (`en/id/it/fr/ru.json`), used for marketing articles and `visa/second-home/[locale]/`
   routing. Site-wide scope, not funnel-scoped. Corrected post-panel (R22, kimi F11):
   `LanguageSettings.tsx` (workspace/portal settings) is NOT a consumer of this provider — it
   reads `@/hooks/useLanguage` against separate portal preferences, a fourth, distinct
   mechanism this design does not touch and does not need to reconcile with.
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
   delegate MODE — the case where a delegate/helper is the one operating the screen (never
   "the sponsor" for this role — R9), as distinct from the family sponsor being the SUBJECT
   of a question asked to the traveller. `who_answers`/`delegate_confirm`/the banner/`pron()`
   exist ONLY in the R5b prototype and were never ported into this dictionary.
3. **(class a) No mechanism at all in GARUDA checkout.** `apps/mouth/src/app/visa/voa/checkout/
   [resultId]/CheckoutFlow.tsx` (192 lines, read in full this round) contains zero
   `useLanguage`/`locale`/`'id'` references — nothing. Yet the checkout **design mockup**
   (R7 backlog item 1, PR-landed 2026-08-27) already renders `<a href="{LANG_TOGGLE}"
   aria-label="Ganti bahasa">EN · ID</a>` in its identity header, per R4:108's law that every
   funnel screen carries the toggle. **The mockup promises a control the live surface has
   nothing to serve it with.** This is the "also covers the wider funnel" half of item 5's own
   text, made concrete: it is not a polish request, it is a load-bearing gap on the funnel's
   OWN highest-risk step (checkout dossier §2 T1: R1 rated it 5-quits — pin corrected
   post-panel, R21; the original citation pointed at the wrong section).

**(class e, RETRACTED as this file's persona grounding — see below) R1's psychology
grounding, as first drafted, cited the wrong persona (R14: kimi F7).** The draft read R1:70's
P3 (spouse) trust trigger — "Bahasa Indonesia for the sponsor and English for the applicant"
— as grounding for the delegate/compiler this file designs for. It is not: per §9's own
retitling, P3's "sponsor" in that quote is the family-route immigration GUARANTOR (R1's own
persona subject), not the screen-operating compiler/helper — R9/R14 established these are two
different roles the codebase already keeps apart, and a persona quote about one cannot ground
design for the other. **This file's sole persona anchor is R6:102-105/290-291** (quoted
above and at §6), which is specifically about the delegate-flow OPERATOR, not the family
sponsor. The external evidence in R1's quote — CSA 2020 (88% of Indonesian consumers prefer
their own language) and EF EPI 2025 (Indonesia "low" English proficiency) — are general
market findings, not persona-specific; they remain legitimate supporting evidence for WHY
Indonesian-language support matters broadly, but they ground the general case, not this
file's specific persona, and are cited here only on that narrower basis.

## §2 The two tensions this design resolves

**T1 — `pron()`'s substitution is a property of English, not a translatable artifact.**
English marks the 2nd person with one small closed set of surface forms — you/your/yours,
uniform across singular and plural, formal and informal — so a ten-entry regex table can
losslessly rewrite "you" into "the traveller" anywhere it appears. Indonesian has no
equivalent closed set to hook the same regex onto: formal register commonly **drops the
subject pronoun entirely** ("Sudah menikah?" needs no "Anda" to be a complete, correct,
polite question), and the direct-address pronoun that DOES exist ("Anda") is doing a
different job in delegate mode than English "you" does — in delegate mode, "you" the reader
IS the delegate/helper (never "the sponsor" — R9 reserves that word for the family-route
guarantor, `family_sponsor_*`), and "the traveller" is a THIRD person the delegate is
answering about. A regex built to turn "you" into "the traveller" has nothing to grab in
Indonesian, because the Indonesian sentence very often never says "Anda" in the first place —
and where it must name someone, repeating a bare pronoun ("dia") reads as informal and
referentially thin in a formal register that instead prefers the noun ("pemohon" — corrected
post-panel, R16.ii; not "wisatawan", tourist-specific) or the resolved relation ("pasangan
Anda"). Porting the regex table 1:1 would either do nothing (no "you" token to
replace) or produce a stilted, over-explicit Indonesian that repeats "pemohon" where a
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
   prototype left out. **Post-panel (R1: agy F1, codex F6, qwen F1) — D aligned to this
   contract.** The delegate-flow dossier's own draft had gone the opposite way, proposing to
   extend `pron()`'s regex/tag mechanism funnel-wide; the panel found the two dossiers
   mandated mutually exclusive build laws for the SAME surface and picked this file's
   contract as the winner (Indonesian has no closed pronoun set to hook a regex onto — §2's
   T1 argument, independently confirmed by three seats). D §3.5/§4 are now amended to match:
   the funnel-wide acceptance criterion is uniform across both dossiers — "no
   pronoun-substitution logic, no raw tags, full EN/ID key parity."
2. **Register split, grounded in T1**: Indonesian copy addresses the delegate/helper directly
   as "Anda" (formal, per the dictionary's own P6 law) at the META questions
   (`who_answers`/`delegate_confirm`, where the delegate IS the addressee) — and refers to the
   traveller in the THIRD person using a concrete noun, never a bare pronoun ("dia"). **Noun
   corrected post-panel (R16.ii: qwen F13, kimi F15) — "pemohon" (applicant) is the DEFAULT
   neutral noun, not "wisatawan" (tourist)**: this funnel handles business, socio-cultural,
   investment and family routes, not only tourism, and "wisatawan" misclassifies an
   applicant under Ditjen Imigrasi's own visa-category vocabulary except where the copy is
   explicitly scoped to a tourism VOA stream (kimi's scoping rule, stated so a future author
   cannot default back to "wisatawan" by habit). Before `family_relation` resolves
   (who_answers/delegate_confirm both fire earlier in the tree — journey.html:199-200 vs.
   :211), the neutral noun is **"pemohon"**; after `family_relation` resolves to a known
   value, downstream copy MAY use the resolved relation noun ("pasangan Anda" — your spouse)
   instead — a recommendation to the build lane (§5.3), since no downstream string in the
   current prototype was found that would need it (class c, not measured against a string
   that does not exist yet).
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
     fakta mereka") it reads as translated-not-written, and "mereka" (they/them, grammatically
     plural) disagrees in NUMBER with the single named person it refers to — a corrected
     rationale post-panel (R16.iv: kimi F14ii; the draft's original "colder register" framing
     was the wrong reason to reject it). §3.4 shows both forms side by side with the
     reasoning, not just the winner.
4. **The literal-vs-reformulated example, in full, corrected post-panel** (R16, all
   sub-findings: agy F9, codex F10, qwen F14, kimi F14; mockup §"Translation strategy" panel):
   - Literal attempt (rejected): *"Anda sedang menjawab untuk orang lain. Kasus mereka, fakta
     mereka — jawablah seperti wisatawan akan menjawab. Siapa yang melihat apa:
     {CUSTODY_WHO_SEES}."* Rejected on two independent grounds: the "Kasus mereka, fakta
     mereka" repetition reads as translated-not-written AND "mereka" disagrees in number with
     its singular referent (R16.iv); "seperti wisatawan akan menjawab" is a hypothetical
     construction where Indonesian prefers a direct instruction, and "wisatawan" itself is
     the wrong default noun (R16.ii).
   - A second draft tried *"…atas nama wisatawan. Jawablah sesuai fakta miliknya, bukan
     pendapat Anda sendiri…"* — ALSO rejected, on three further grounds the panel raised
     independently: (i) "atas nama" (agy F9) denotes formal legal proxy/power-of-attorney in
     Indonesian administrative usage — the delegate has no such standing, so this phrase
     makes an unintended legal claim; (ii) "bukan pendapat Anda sendiri" (kimi F14.iii) is an
     ID-only added obligation with no EN source clause, breaking EN/ID parity, and reads as
     accusatory in the warm-formal register this dictionary otherwise holds (codex F10); (iii)
     "fakta miliknya" (codex F10, kimi F14) is an unidiomatic possessive calque — formal
     Indonesian does not take "-nya" on "fakta" this way.
   - **Recommended** (post-panel, synthesized — not a single seat's verbatim text): *"Anda
     sedang membantu pengisian formulir untuk pemohon. Jawablah berdasarkan fakta pemohon —
     siapa yang dapat melihat jawaban ini: {CUSTODY_WHO_SEES}."* Replaces "atas nama" with
     agy's non-representative procedural phrasing (F9); drops the added obligation clause
     entirely rather than softening it (kimi F14.iii — EN parity, not just tone); names the
     referent as an explicit noun ("fakta pemohon") instead of a possessive-suffix calque.
     Keeps every regulatory-honesty commitment of the English (answer as the fact-holder, not
     a guesser; disclose who sees the answer) in a direct-instruction register matching the
     dictionary's own existing tone (compare `framing.body`: "Jawab dengan jujur, termasuk
     'Saya tidak tahu.'" — i18n.ts:831). Screen 4's shorter custody-hint line gets the same
     R16.v correction separately: "Siapa yang melihat:" → "Siapa yang dapat melihat apa:" —
     the faithful-copy class must not drop the object ("apa") the way the draft's compact hint
     did.
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
   Imigrasi", "PT", "NPWP", "KITAS/KITAP", "WhatsApp" are not translated in the EN copy
   either (i18n.ts never anglicizes them); the ID column keeps them byte-identical, per the
   dictionary's own "Imigrasi's own terminology natively — not machine-translated" law.
   Corrected post-panel (R16.viii: codex F12/F10): the term is "KITAS/KITAP" (Kartu Izin
   Tinggal Terbatas / Tetap), not the draft's duplicated "KITAS/KITAS"; the trust footer's
   Indonesian verb "menerbitkan" (issues) names its object explicitly ("visa atau izin
   tinggal", visa or stay permit) rather than standing intransitive, and "tautan
   pendaftaran" (registration link) is replaced with "entri registri perusahaan" (company
   registry entry) — a more precise match to the EN "registry entry."
8. **Identity header, custody hint, and trust footer are reused verbatim from the checkout
   and consent lanes**, not redrawn — same CSS custom properties (`--carta`, `--merah-action`,
   `--font-display`, the rem type scale, the 44px touch-target floor), same component
   contracts (the custody component's two densities from the consent lane, §6.1 there;
   applied here at the delegate banner's HIGH-sensitivity tier because the banner discloses
   who sees the answer, the same reason A6/checkout/Oracle-interview-start got the full
   module in that lane). **Density rule cross-referenced, not restated (R18: kimi F13)**: the
   single governing rule — density follows the sensitivity of the SCREEN'S ASK, per the
   consent lane's §6.1 — is now stated ONCE, in the delegate-flow (item 4) dossier, with this
   file cross-referencing rather than duplicating it: the checkpoint's compact hint is
   deliberate (no PII is collected at that screen), the persistent banner is full-tier
   because it rides screens that DO collect PII. Both mockups annotate the same rule; neither
   restates it as its own law.
9. **New EN/ID key-set table for item 4's amended surface, coordinated with the panel's D-side
   fixes (R13: qwen F12, kimi F3)** — §5.7 enumerates it. Without this, the claim that item 5
   "covers item 4" would be false against the SURFACE the joint panel actually amended, not
   just against R5b's older prototype.

## §4 Behavioral acceptance (what a build of item 4 must prove, once it exists)

- A missing or extra Indonesian key in a delegate-mode dictionary is a TypeScript build
  error, matching `_lib/i18n.ts`'s existing `Record<Keys, string>` + `i18n.test.ts` parity
  pattern — never a silent English fallback.
- No string in the shipped delegate flow is produced by regex substitution on an English
  base string; every self/delegate variant, in every locale, is an authored dictionary entry.
  (would_fail_if: a `.replace(/@…@/g` pattern, or equivalent, appears in the shipped
  component.)
- The neutral noun ("pemohon" — corrected post-panel, R16.ii; "wisatawan" only where a screen
  is explicitly tourism-VOA-scoped) renders for every meta-question that fires before
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
- **NEW (R2: codex F2, kimi F1, qwen F4) — deletion copy never names an actor the session
  model cannot reach.** The right to delete a check is bound to the browser/session cookie
  (`garuda_voa_public.py:578,590-595`), which is typically the DELEGATE's browser, not
  necessarily one the traveller can reach. "The traveller can delete this check at any time"
  is false twice over — the actor is wrong and "at any time" overclaims a right the session
  model does not durably grant. Copy must name the actor the mechanism actually reaches
  ("whoever ran this check, from this browser and session") and never invent a
  traveller-reachable deletion path that does not exist. (would_fail_if: shipped copy names
  "the traveller" as the one who can delete, or omits the session/browser qualifier.)
- **NEW (R26: qwen F16) — an unresolved custody or retention placeholder suppresses its own
  line**, in both languages: a raw `{TOKEN}` rendered to a visitor, or an invented value
  standing in for one, is a failed build — matching the checkout/consent lanes' own
  conditional-render discipline for PNBP and FX lines.
- **NEW (R16.ix: joint panel synthesis) — a native-speaker review pass is a build
  requirement before ANY Indonesian copy in this dossier ships.** Every ID string in this
  file, including the post-panel corrections, is draft copy authored (and now
  panel-corrected) by non-native-speaker seats; it has not had a native-speaker pass. This
  acceptance item exists precisely because the panel itself caught register and calque
  errors a native reviewer would catch faster and more completely — the panel's correction
  is not a substitute for that review, it is evidence the review is needed.

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
5. **The sponsor sub-progress badge — corrected post-panel (R16.vii: codex F9), not a
   simple ordinal fix.** The draft's "Sponsor ke-{i} dari {n}" was itself wrong, not just
   non-idiomatic: "ke-{i}" attached directly to "Sponsor" reads as the ordinal position of a
   SPONSOR ("the i-th sponsor"), not the question count within the sponsor sub-flow. The
   corrected form separates the section label from the count: "Bagian sponsor · Pertanyaan
   {i} dari {n}" (Sponsor section · Question {i} of {n}). Note "sponsor" is CORRECT here,
   unlike elsewhere in this file (§9) — this badge is literally about the family-route
   sponsor sub-flow (R5b's six-question branch), the one place R9 reserves the word for.
   (class c)
6. **CSA 2020 / EF EPI 2025 citations, re-scoped post-panel (R14).** These general-market
   language-preference findings remain worth carrying into item 4's own build-lane dossier as
   supporting evidence for why Indonesian-language support matters broadly — but see §1's
   retraction: they were originally attached to R1:70's DIFFERENT persona (the family
   sponsor), and this file no longer treats that quote as its own persona grounding. Carry
   the citations, not the persona attribution. (class c)
7. **New EN/ID key-set for item 4's amended surface (R13: qwen F12, kimi F3)** — the joint
   panel's fixes to the delegate-flow dossier (rows R3, R4, R8, R11) introduced new
   user-facing strings this file's original key-set did not cover: the explicit-facts
   who-answers gate, the rewritten scope-limit line, the early-exit mirror, and the checkout
   contact label. Without covering these, "i18n presupposes item 4's surface … also covers
   the wider funnel" (R7:190) would be true only against R5b's OLDER prototype, not against
   what the panel actually shipped for item 4. Coordinated table below — sourced from the
   register's own quoted text where available (marked class a-quote); where the register
   describes a requirement without quoting final copy, this file authors a plausible
   placeholder pending D's own final wording (marked class c, and NOT to be read as D's
   authoritative string):

   | Key | EN (source) | ID (draft, native review pending) | Class |
   |---|---|---|---|
   | `gate.scope_limit` | "The online checkout is for travellers paying for themselves. If someone else is paying, a consultant handles it on WhatsApp." (R8, quoted verbatim in the register) | "Pembayaran daring ini untuk pemohon yang membayar sendiri. Jika ada pihak lain yang membayar, konsultan kami akan membantu lewat WhatsApp." | a-quote (EN) / c (ID draft) |
   | `gate.early_exit_mirror` | Generic mirror, not the specific decline copy — e.g. "You told us you need help arranging for another person or a group." (qwen F8's own proposed generic mirror, register R4) | "Anda memberi tahu kami bahwa Anda perlu bantuan untuk mengatur perjalanan orang lain atau kelompok." | a-quote (EN) / c (ID draft) |
   | `checkout.contact_label` | "Traveller's contact" + "Receipts and updates about this application go to this contact." (register R11, both clauses quoted) | "Kontak pemohon" + "Kuitansi dan pembaruan tentang permohonan ini dikirim ke kontak ini." | a-quote (EN) / c (ID draft) |
   | `gate.who_answers_options` | Three explicit-fact options anchored to payment + traveller count (agy F8's proposal, cited by the register as the basis for R3's fix — D's build lane owns the FINAL wording; this row tracks the key exists, not the exact text) | pending D's final EN — no ID authored against unstable source text | c (placeholder, EN not yet fixed) |

   The last row is deliberately incomplete: authoring Indonesian against English the delegate
   dossier itself has not finalized would manufacture false precision. This file tracks the
   KEY, not a translation of text that may still change.

## §6 Declarations (adopted under the standing pre-confirmation — joint round-grade panel
run 2026-08-28, dispositions in `mockups/sponsor-i18n/adversarial.json`; async veto open)

Per R7 §3.2, a design deliverable carrying declarations that decide surface behavior goes
through a round-grade panel before adoption. This file's earlier draft correctly withheld
"adopted" status pending that panel (R7 §3.1's evidence-class discipline — an unclassed or
falsely-elevated claim is exactly the failure mode that ladder exists to catch). **The panel
has now run** — a joint round-grade panel covering both this dossier and the delegate-flow
(item 4) dossier together (4 cross-family seats + 1 independent verification pass, 57 raw
findings deduped to 27 register rows). Each of the four declarations below survived the
panel in AMENDED form, not verbatim — the amendments are cited inline and are the same
corrections applied throughout §1-§5 above:

1. **Self/delegate variants replace pronoun-substitution as the mechanism for any locale
   beyond English** (§3.1). CONFIRMED, and stronger than proposed: the panel found the
   delegate-flow dossier's OWN draft mandated the opposite mechanism for the same surface
   (R1) and picked this file's contract as the winner — D §3.5/§4 are now amended to match,
   so the acceptance criterion is uniform across both dossiers, not just this one's opinion.
2. **Neutral-noun default before `family_relation` resolves, resolved-relation noun
   optionally after** (§3.2, §5.3). APPLIED WITH CORRECTION (R16.ii): the default noun is
   "pemohon" (applicant), not the draft's "wisatawan" (tourist) — "wisatawan" is reserved for
   explicitly tourism-VOA-scoped copy only. The resolved-relation-noun recommendation for
   post-resolution screens stands unchanged, still class (c), still not measured against a
   string that does not exist yet.
3. **Faithful translation for procedural/legal copy, cultural reformulation for
   persuasion/reassurance copy, as a named split rather than a single translation policy**
   (§3.3-§3.4). CONFIRMED as the right split; the WORKED EXAMPLE under it was wrong on five
   independent points the panel caught (R16.i-v: "atas nama" implies unwarranted legal
   proxy, "wisatawan" was the wrong noun, an ID-only obligation clause broke EN/ID parity,
   "fakta miliknya" was an unidiomatic calque, and "Siapa yang melihat:" dropped its object).
   The split survives; the example that was meant to demonstrate it did not, until corrected.
4. **Item 4's build lane inherits `_lib/i18n.ts`'s compile-time-parity dictionary pattern
   rather than inventing a fourth i18n mechanism** (§3.1, §5.4). CONFIRMED, unamended — no
   seat contested this row; it stands on the same evidence this draft cited (the
   standalone-dictionary lane's own stated reason for existing, `_lib/i18n.ts`'s header
   comment). The lint-chain cross-check this file flagged as unread remains unread — carried
   forward as residual, not resolved by the panel running.

**New declaration, post-panel (R9): the vocabulary boundary is adopted as this file's own
law, not just D's.** "Sponsor" names the family-route immigration guarantor
(`family_sponsor_*`) exclusively; the compiler/helper this file designs for is "delegate" or
"helper," never "sponsor" — except the sub-progress badge (§5.5), which is correctly
"sponsor" because it names the family-sponsor sub-flow itself. Every place this file's DRAFT
used "sponsor" for the compiler is corrected in §1 (ground quotes, marked as unedited source)
and the mockup's design copy (marked as declared edits, per the "Retitled subject" note
after this file's title) — never silently.

## Adversarial review

Joint round-grade panel over items 4+5 (this file and the delegate-flow lane, run
2026-08-28): **codex gpt-5.6-sol xhigh** (filesystem — 13 findings), **kimi k3**
(filesystem — 15, including the Screen-4 CRITICAL: the mockup promised a deletion right to
an actor the session model cannot reach), **agy gemini-3.1-pro** (inline — 12, including
the "atas nama" legal-proxy objection that overturned this file's own recommended
Indonesian banner), **qwen3.8-max** (inline — 17, including the "wisatawan"→"pemohon"
register correction and the key-set coverage gap toward item 4). Where seats conflicted
(qwen's counter-proposal reused "atas nama"; agy showed it implies power-of-attorney) the
least-claim wording won. Tally: **57 raw findings, deduped to 27 joint register rows — 23
applied, 3 partial (R11, R12, R21), 1 with an embedded reject (R21.v: kimi's
"delegate-i18n.html does not exist" was a panel-setup artifact — the file ships on this
branch)** (computed from the register); dispositions in
`mockups/sponsor-i18n/adversarial.json`, the register and the four seats' raw verdict
extracts in `mockups/sponsor-i18n/panel/`. Surviving objections: none unresolved — the
native-speaker review this file's Indonesian copy still needs is now §4's own acceptance
item (R16.ix), not an open finding.

## §Meta

This lane's honest position is that it designed language for a screen nobody has built yet,
grounded in a prototype nobody is shipping as-is. That is not a weakness to hide — R7 §4's
own backlog ordering put the risk-order ahead of the schedule and named this item's
dependency on item 4 in its own text. What this file could actually verify against the live
tree turned out to matter more than the delegate flow itself: a live checkout page, already
designed with an EN/ID toggle in its header, that has no dictionary behind that toggle at
all. The mandate said "also covers the wider funnel" as an afterthought clause; the ground
pass found that the wider funnel is where the actual, present-tense gap lives.

**Post-panel addendum.** The joint panel's sharpest catch on this file was not a citation
error — it was that this file's own draft violated the vocabulary rule R9 later stated
before that rule existed on paper: "sponsor" for the compiler, "wisatawan" as a universal noun, an
Indonesian clause with no EN counterpart, a possessive calque a native reader would catch in
one pass. None of these survive a filesystem-armed refuter reading the SAME source this file
read. The lesson is not "translate more carefully" — it is that a solo Sonnet lane authoring
Indonesian copy without a native-speaker pass is exactly the failure mode §4's new acceptance
item (R16.ix) now names explicitly, and this file is Exhibit A for why that acceptance item
belongs in the doctrine, not just in this dossier.
