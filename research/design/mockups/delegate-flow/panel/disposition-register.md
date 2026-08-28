---
adversarial_review: exempt-this-file-IS-the-panel-output-the-joint-disposition-register-not-a-reviewed-research-deliverable
---

# Joint disposition register — items 4+5 panel (2026-08-28)

Panel: 4 cross-family seats (codex gpt-5.6-sol xhigh filesystem 13 · kimi k3 filesystem 15 ·
agy gemini-3.1-pro inline 12 · qwen3.8-max inline 17 = 57 raw findings) + 1 independent
Explore verification pass (10 load-bearing claims: 8 TRUE, 1 IMPRECISE, 1 FALSE-by-letter).
Deduped into the rows below. D = delegate-flow lane, I = sponsor-i18n lane, J = joint.
Conductor synthesis; every contested claim re-verified on the tree before disposition.

## CRITICAL

R1 [J — agy F1, codex F6, qwen F1] APPLY. The two dossiers mandate mutually exclusive
pronoun mechanisms (D: pron()/tag rewrite funnel-wide; I: authored variants, regex banned).
Winner: I's contract (authored self/delegate keys per locale — Indonesian has no closed
pronoun set for a regex). D §3.5 + §4 amended: pronoun layer = mode-variant authored keys;
acceptance becomes "no pronoun-substitution logic, no raw tags, full EN/ID key parity".

R2 [I — codex F2, kimi F1, qwen F4] APPLY. I's mockup Screen 4 says "the traveller can
delete this check at any time" / "wisatawan dapat menghapus…kapan saja" — false twice: the
right is bound to the session cookie (286:99; garuda_voa_public.py:578,590-595 — normally
the DELEGATE's browser) and no deletion UI exists. Rewrite: actor = the session-holder
("whoever ran this check can delete it from this browser and session"); add §4 acceptance:
deletion copy never names an actor the session model cannot reach.

R3 [D — codex F1, qwen F3] APPLY. The 3rd gate option ("arranging for someone else, or for
more than one person") is NOT equivalent to NOT_SELF_PAY ∪ GROUP_CASE — a supported delegate
IS literally "arranging for someone else", and no travellers/self_pay fact is collected at
that point. Rewrite §3.1: the gate asks EXPLICIT facts (option copy anchored to payment and
traveller count, per agy F8's three-option phrasing), routes only on the owner-defined
exclusions, never on a vague label.

R4 [D — qwen F8, codex F1(b)] APPLY. Early-exit screen must NOT reuse the literal decline
copy: "You told us someone else is paying" / "travelling with {N} people" would be false
(facts never declared, {N} unknown). Author a generic early-exit mirror; specific copy only
after the underlying facts are explicitly declared. §3.7 amended.

R5 [D — qwen F2] APPLY. Mode ambiguity: middle option says the traveller "will answer for
themselves" but downstream copy renders third-person with the delegate as declarant. Split
cleanly in §3.1/§3.2: helper-operates mode keeps the traveller as addressed declarant where
feasible; delegate-answers mode uses delegate attestation + third person. State which one
the middle option IS (delegate-answers, per R5b's own confirm copy) and fix the option
wording accordingly.

## MAJOR

R6 [D — agy F6, codex F4, kimi F4] APPLY. D §6 header "adopted under the standing
pre-confirmation" contradicted its own frontmatter ("panel pending") and I's correct
PROPOSED framing. Post-amendment both §6 read: "adopted under the standing
pre-confirmation — joint round-grade panel run 2026-08-28, dispositions in
adversarial.json; async veto open". EXCEPT rows moved to owner decisions (R7 below).

R7 [D — agy F5, codex F4, kimi F5] APPLY. The screen-1 early-exit ROUTING is a business
decision (changes lead-capture economics; §5.4 admits zero measurement; R7:170 assigns
ownership to Zero). D §6.1 recast: the gate DESIGN (explicit-facts questions) is design and
stays; WHEN the WhatsApp exit fires (screen-1 vs deferred-decline default) is an OWNER
decision, default = deferred decline until Zero rules, instrument-first on a small cohort.

R8 [D — agy F7, codex F7, qwen F6] APPLY. Scope-limit line overclaims enforcement ("payment
still has to come from the traveller's own card" — the gateway checks no cardholder name;
self_pay is self-declared; xendit.py restricts method only). Rewrite: "The online checkout
is for travellers paying for themselves. If someone else is paying, a consultant handles it
on WhatsApp." No invented enforcement, no invented policy.

R9 [J — agy F4, codex F3+F12, kimi F2, qwen F7] APPLY. "Sponsor" vocabulary: compiler =
"delegate/helper" everywhere; "sponsor" reserved for the family-route guarantor. I retitles
its subject as delegate-mode i18n (keeping the R7 item-5 name as a quoted mandate label,
not as the persona's name); both mockups scrub "a sponsor, …" from the R5b why-text
(declared amendment of R5b copy, not silent); D §1's sponsor definition corrected per codex
F12 (the family_sponsor_* is the SUPPORTING party, not "the person being sponsored FOR").

R10 [D — codex F5, qwen F5+F10] APPLY. "Authorization checkpoint"/"standing-to-act"
overstates an unwitnessed self-declaration: rename to "delegate declaration" throughout;
the delegate-mode payer statement becomes reported speech ("The traveller has confirmed to
me that they will pay themselves"); note that no ledger can record it yet (091 gap, already
§5.3) and that a real authorization design (handoff/receipt/revocation) is product work.

R11 [D — agy F3, qwen F9] PARTIAL. Checkout contact relabel stays ("Traveller's contact")
but adds the honest routing line: "Receipts and updates about this application go to this
contact." No second delegate-contact field is invented (schema has none — R4 §5); the
schema decision remains §5.1's product finding. agy's optional-second-field proposal
REJECTED for this lane (schema-backed only).

R12 [J — codex F8] PARTIAL. Evidence-class inflation: §1 headers reclassified claim-family
by claim-family — live-read code stays (a); quotes of prior-round dossiers become (e);
linguistic judgments (c). No wholesale re-audit beyond the header discipline.

R13 [I — qwen F12, kimi F3] APPLY. I's key-set must cover D's actual (amended) surface:
add EN/ID entries + mockup rows for the explicit-facts gate options, the rewritten
scope-limit line, the early-exit mirror, and the checkout contact label — or that clause of
"covers item 4" is false. Enumerate them in a new keys table.

R14 [I — kimi F7] APPLY. Re-anchor the persona grounding on R6:102-105/R6:290-291 (the
Indonesian sponsor-OPERATOR reading); drop/re-scope the R1:70 P3 anchor (P3's "sponsor" is
the family-route subject, per D §1 — both readings cannot hold).

R15 [I — kimi F6 + verifier claim 1, codex F11] APPLY (lands in D). "'excluded from pilot'
appears at every exclusion site" is FALSE: 5 tagged sites (eligibility.py:208,210,212,221,224);
NOT_SELF_PAY (:201-202) and work/business (:214-217) lack the tag. Restrict the claim;
ground NOT_SELF_PAY's pilot status in the SOP docstring (:3-8) explicitly. Also (codex F11):
"explicit owner decision" for the gates is UNVERIFIED — say "policy implemented by
SOP-v0-GARUDA-B1 §1" unless an owner record is cited.

R16 [J — G-family: agy F9+F10+F11, codex F9+F10, qwen F13+F14, kimi F14+F15] APPLY, all
Indonesian-language items, synthesis where seats conflict:
 (i) "atas nama" OUT (agy: implies legal proxy/kuasa — least-claim wins over qwen's
     counter-proposal that reused it): "Anda sedang membantu pengisian formulir untuk …".
 (ii) neutral noun: "pemohon" ("applicant") as default; "wisatawan" ONLY on VOA
     tourism-scoped copy (kimi F15 scoping rule stated explicitly).
 (iii) drop the ID-only added obligation "bukan pendapat Anda sendiri" (kimi F14iii —
     EN/ID parity; the EN source has no such clause).
 (iv) "fakta miliknya" replaced (unidiomatic calque); rationale for rejecting "mereka"
     corrected to number-disagreement, not "colder" (kimi F14ii).
 (v) "Siapa yang melihat:" → "Siapa yang dapat melihat apa:" (faithful-copy class must not
     drop "apa" — kimi F14iv).
 (vi) "Sebenarnya, biar …" → "Biarkan …"/"Sebaiknya …" (register — kimi F14v, codex F10).
 (vii) sub-progress badge: "Bagian sponsor · Pertanyaan {i} dari {n}" (codex F9 — ke-{i}
     miscounts sponsors, not questions).
 (viii) "KITAS/KITAS" → "KITAS/KITAP"; "Bahasa" → "Bahasa Indonesia" in formal claims;
     "tautan pendaftaran" → "entri registri perusahaan"; "Ditjen Imigrasi … menerbitkan"
     names its object (codex F10).
 (ix) NEW §4 acceptance in I: a native-speaker review pass is a build requirement before
     any ID copy ships — this dossier's ID text is draft copy, not final.

R17 [I — qwen F11, kimi implicit] APPLY. D inherits the EN·ID header as "unchanged law"
while I proves the checkout toggle has no dictionary — D adds one line inheriting I's
dependency explicitly (toggle renders only with reachable locale logic; honest disabled
state otherwise).

R18 [J — kimi F13] APPLY. Custody-density rule stated once (in D, cross-ref in I): density
follows the sensitivity of the SCREEN'S ASK (consent §6.1) — the checkpoint's compact hint
is deliberate (no PII collected there); the persistent banner is full-tier because it rides
PII-collecting screens. One rule, both mockups annotated.

## MINOR

R19 [J — kimi F8 + verifier claim 7] APPLY. "zero delegate hits" qualified: one incidental
verb hit (flow.ts:1208 "Delegate to …"); "outside journey.html itself" wording fixed
(journey.html is not in the grepped trees).

R20 [D — kimi F10] APPLY. Citation pins corrected: declineEducation.ts real path
apps/mouth/src/components/garuda/; eligibility docstring :1-30; [hash]/page.tsx:157-160;
i18n.ts family_sponsor_confirmed at :393-398; garuda_voa_public.py match logic :585-595;
ConsentHandoff quote spans :44-45.

R21 [I — kimi F9] PARTIAL. Pins corrected: pron() :336-342; delegateBanner :156-158;
R6 quote at :119-120 (not :304); checkout 5-quits at checkout dossier §2 T1. Kimi's item
(v) — "mockups/sponsor-i18n/delegate-i18n.html does not exist" — REJECTED: panel-setup
artifact; the file exists on the I branch (commit d0974126a ships both .html and
.body.html); kimi only received the .body copy.

R22 [I — kimi F11] APPLY. LanguageSettings.tsx dropped from the global-provider consumer
list (it uses @/hooks/useLanguage + portal prefs, not src/i18n).

R23 [D+I — kimi F12] APPLY. Escape copy: either port R5b verbatim or declare the edit —
mockups annotated with the declared edit (current rendering differs from journey.html:396).

R24 [D — codex F13] APPLY. Mockup CTA gets disabled/aria-disabled in the unchecked state +
a comment that the mockup is compositional, matching §4's "blocks all progress".

R25 [D — qwen F15] APPLY. "self path completely unchanged" reworded: downstream self-mode
screens unchanged; the entry gains one gate screen (friction to be measured).

R26 [J — qwen F16] APPLY. Placeholder fallback acceptance added to both §4: an unresolved
custody/retention token suppresses its line — a raw token or invented value is a failed
build.

R27 [D — agy F2 residual] APPLY. The checkpoint custody line keeps the true session-bound
statement but drops the feature-like framing; adds "if this browser's session is lost, a
consultant can help via WhatsApp" only if that support route actually exists — otherwise
states nothing beyond the fact. (No false fallback promise.)

## Tally

27 register rows from 57 raw seat findings + 2 verifier corrections.
Dispositions: 23 APPLY · 3 PARTIAL (R11, R12, R21) · 1 with an embedded REJECT (R21.v;
plus R11 rejects agy's second-contact-field proposal). Kimi's verified-clean list (R7/R4/
R3/R1/R6 quotes, consent tiers, migrations substance, CheckoutFlow facts, journey.html
strings) stands confirmed-sound.

New owner decisions surfaced (NOT adopted, for Zero): (1) early-exit routing activation
(R7 row) — screen-1 exit vs deferred-decline default; (2) whether a traveller-reachable
deletion path (magic-link/opaque-code) gets product priority (R2's structural half).
