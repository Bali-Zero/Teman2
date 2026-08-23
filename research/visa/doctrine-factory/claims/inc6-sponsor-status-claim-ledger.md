---
date: 2026-08-23
domain: visa
client_case: none — engine doctrine work (E5 increment 6, seq-13 rules-only fold, Fix 4)
sources:
  - path: data/source_documents/t0_regulations/permenkumham_22_2023_visa_izin_tinggal.pdf
    note: "primary law, Pasal 44/47/50 — re-extracted this session via `pdftotext -layout`, verified line-for-line"
  - path: data/source_documents/t0_regulations/permenkumham_11_2024_perubahan_visa.pdf
    note: "amendment, item 14 (replaces Pasal 50) + item 15 (inserts Pasal 50A) — re-extracted this session"
discovered_by: agent.air-m5.backend-rag.visaoracle-seq13-rules-0823
adversarial_review: exempt-no-external-seat-dispatched-fix-held-not-shipped-see-adversarial-review-section
---

# inc6 claim ledger — sponsor-status value check (seq-13, Fix 4)

Grounds the seq-13 tightening of `family.sponsor_status_code` on nine ELIGIBILITY rules
across E31B/E31E/E31H/E31J: today every one tests `op: known` (presence only) — a rule
literally named `*-sponsor-itas-itap` never checks that the sponsor actually holds an
ITAS, an ITAP, or an approved VITAS; any non-empty string passes.

**Method note, disclosed up front**: the four article citations below were first relayed by
the team-lead from another agent's PDF reading, with the team-lead stating explicitly they
had not opened the PDFs themselves. Per this repo's anti-hallucination discipline, a claim
this session did not itself verify cannot be marked VERIFIED on a second-hand relay — so
before writing this ledger, both PDFs were re-fetched from disk and re-extracted with
`pdftotext -layout` in THIS session, and every quoted passage below (Pasal 44, 47, 50, 50A,
their VITAS-fallback ayat, the "saudara" absence in the 2023 text, and the Pasal-44
footer-number check) was independently re-read from the resulting text. The relayed
citations were correct on every point checked; nothing here is taken on trust.

---

**CL-SPONSOR-E31B — E31B's spouse-sponsor must hold a currently-valid ITAS or ITAP, or (if
neither yet issued) an approved VITAS for the spouse.** Permenkumham 22/2023 Pasal 44(2)(b),
verbatim: *"Izin Tinggal Terbatas atau Izin Tinggal tetap suami atau istri yang sah dan
masih berlaku"* — a valid and currently-in-force ITAS or ITAP of the spouse. Pasal 44(3),
verbatim: *"Dalam hal suami atau istri belum memiliki Izin Tinggal Terbatas atau Izin
Tinggal Tetap sebagaimana dimaksud pada ayat (2) huruf b, Izin Tinggal Terbatas atau Izin
Tinggal Tetap dapat digantikan dengan Visa tinggal terbatas suami atau istri dari Orang
Asing"* — where the spouse does not yet hold ITAS/ITAP, a VITAS (limited-stay visa) for the
spouse substitutes. Three states, exhaustively: ITAS_ACTIVE, ITAP_ACTIVE, VITAS_APPROVED.

- Source: `permenkumham_22_2023_visa_izin_tinggal.pdf`, Pasal 44(2)-(3) (re-extracted and
  read this session, lines 1725-1755 of the `pdftotext -layout` output).
- **State: VERIFIED.** Products: E31B. Provenance: this session, direct PDF re-extraction.
- Backs: `el.e31b-spouse-itas-support`, `el.e31b-sponsor-itas-itap` (the `op:known` ->
  `op:in [ITAS_ACTIVE, ITAP_ACTIVE, VITAS_APPROVED]` edit on `family.sponsor_status_code`).
- **Correction of a doctrine-card citation error, recorded here so it is not propagated**:
  `E31B.md` cites "Pasal 44(2)(b) (as amended by Permenkumham 11/2024)". This is wrong.
  `grep -n "Pasal 44" permenkumham_11_2024_perubahan_visa.pdf` (re-extracted text) returns
  ZERO hits, and the only occurrence of the bare token `44` anywhere in that document is a
  page-footer number (`- 44 -`), independently re-verified this session. Pasal 44 is
  unamended 22/2023 law; cite it that way.

---

**CL-SPONSOR-E31E — E31E's parent-sponsor must hold a currently-valid ITAS or ITAP, or an
approved VITAS.** Permenkumham 22/2023 Pasal 47(2)(c), verbatim: *"Izin Tinggal Terbatas
atau Izin Tinggal Tetap orang tua yang masih berlaku"* — a valid and currently-in-force
ITAS or ITAP of the parent(s). Pasal 47(3), verbatim: *"Dalam hal ayah dan/atau ibu belum
memiliki Izin Tinggal Terbatas atau Izin Tinggal Tetap sebagaimana dimaksud pada ayat (2)
huruf c, Izin Tinggal Terbatas atau Izin Tinggal Tetap dapat digantikan dengan Visa
tinggal terbatas ayah dan/atau ibu dari Orang Asing"* — VITAS substitutes where the
parent(s) do not yet hold ITAS/ITAP. Same three-state enum as E31B, independently enacted
for the parent-sponsor case.

- Source: `permenkumham_22_2023_visa_izin_tinggal.pdf`, Pasal 47(2)-(3) (re-extracted and
  read this session, lines 1852-1886).
- **State: VERIFIED.** Products: E31E. Provenance: this session, direct PDF re-extraction.
- Backs: `el.e31e-child-itas-support`, `el.e31e-sponsor-itas-itap`.

---

**CL-SPONSOR-E31H — E31H's child-sponsor must hold a currently-valid ITAS or ITAP, or an
approved VITAS.** Permenkumham 22/2023 Pasal 50(2)(b), verbatim: *"Izin Tinggal Terbatas
atau Izin Tinggal Tetap anak yang masih berlaku"* — a valid and currently-in-force ITAS or
ITAP of the child (E31H is the reverse-direction family-reunion product: a parent applicant
joins a child sponsor). Pasal 50(3), verbatim: *"Dalam hal anak belum memiliki Izin Tinggal
Terbatas atau Izin Tinggal Tetap sebagaimana dimaksud pada ayat (2) huruf b, Izin Tinggal
Terbatas atau Izin Tinggal Tetap dapat digantikan dengan Visa tinggal terbatas anak dari
Orang Asing"* — VITAS substitutes where the child does not yet hold ITAS/ITAP.

- Source: **11/2024 item 14** ("Ketentuan Pasal 50 diubah sehingga berbunyi sebagai
  berikut") replaces the whole article; re-extracting BOTH the original 22/2023 Pasal 50
  and the 11/2024 replacement this session shows the (2)(b)/(3) text is byte-identical
  across the amendment — the operative ITAS/ITAP/VITAS requirement is unchanged in
  substance, only re-enacted. Cited against `permenkumham_11_2024_perubahan_visa.pdf`
  item 14 (lines 1263-1300) as the currently-governing text, with the original
  `permenkumham_22_2023_visa_izin_tinggal.pdf` Pasal 50 (lines 1977-2008) as the
  pre-amendment corroborator.
- **State: VERIFIED.** Products: E31H. Provenance: this session, direct PDF re-extraction
  of both the original article and its replacement.
- Backs: `el.e31h-parent-itas-child-support`, `el.e31h-sponsor-itas-itap`.

---

**CL-SPONSOR-E31J — E31J's sibling-sponsor must hold a currently-valid ITAS or ITAP, or an
approved VITAS.** Permenkumham 11/2024 item 15, inserting a NEW Pasal 50A(2)(c), verbatim:
*"Izin Tinggal Terbatas atau Izin Tinggal Tetap saudara kandung yang masih berlaku"* — a
valid and currently-in-force ITAS or ITAP of the sibling. Pasal 50A(3), verbatim: *"Dalam
hal saudara kandung belum memiliki Izin Tinggal Terbatas atau Izin Tinggal Tetap
sebagaimana dimaksud pada ayat (2) huruf c, Izin Tinggal Terbatas atau Izin Tinggal Tetap
dapat digantikan dengan Visa tinggal terbatas saudara kandung dari Orang Asing"* — VITAS
substitutes where the sibling does not yet hold ITAS/ITAP.

- **E31J did not exist under the base 2023 law.** `grep -c "saudara" permenkumham_22_2023_
  visa_izin_tinggal.pdf` (re-extracted text, independently re-run this session) returns
  `0` — sibling was not in the family-reunion taxonomy at all until 11/2024 item 15
  inserted Pasal 50A between Pasal 50 and Pasal 51. Worth carrying forward: any future
  doctrine work on E31J's other requirements has no 2023-law fallback to check against.
- Source: `permenkumham_11_2024_perubahan_visa.pdf`, item 15 / Pasal 50A(2)-(3)
  (re-extracted and read this session, lines 1302-1339).
- **State: VERIFIED.** Products: E31J. Provenance: this session, direct PDF re-extraction.
- Backs: `el.e31j-sibling-itas-support`, `el.e31j-sponsor-itas-itap`, `el.e31j-dependency-age`.

---

## Adversarial review

**Not yet performed as of this ledger's authoring** — this Fix is being folded and tested
in the same session it was grounded in, ahead of the cross-family adversarial pass the
team-lead's other fixes received (Codex/Kimi K3 on Fix 1/Fix 3's predecessor cures). The
citations above were independently re-verified against the primary PDFs by THIS session
(not merely relayed), which is the anti-hallucination floor, not a substitute for a second
reviewer. Flagged to the team-lead as an open item, not silently treated as equivalent to
the two-reviewer cures this pack otherwise carries.

---

## Known scope gap — Pasal 33(7), NOT closed by this fix (found 2026-08-23)

**This fix closes the VALIDITY axis only; a second, distinct axis remains open.**
A cross-family refuter found, and this session independently re-verified via its own
`pdftotext -layout` re-extraction of `permenkumham_11_2024_perubahan_visa.pdf`
(item 10, replacing Pasal 33), that the amendment inserts **Pasal 33(7)**, verbatim:

> *"Visa tinggal terbatas sebagaimana dimaksud pada ayat (2) huruf h angka 2, angka 5,
> angka 8, dan angka 9 tidak dapat diajukan untuk penyatuan kepada pemegang Izin
> Tinggal Penyatuan Keluarga."*

Independently re-derived the angka mapping from the same document's Pasal 33(2)(h)
list (lines 850-882 of the re-extraction) rather than taking the mapping on trust:
angka 2 = spouse joining an ITAS/ITAP-holder spouse (**E31B**), angka 5 = minor child
joining an ITAS/ITAP-holder parent (**E31E**), angka 8 = parent joining an
ITAS/ITAP-holder child (**E31H**), angka 9 = minor sibling joining an ITAS/ITAP-holder
sibling (**E31J**) — confirmed exact, all four of this fix's products.

**What this means concretely**: the law puts TWO conditions on the sponsor, not one.
(1) The sponsor's permit must be currently valid — Pasal 44(2)/47(2)/50(2)/50A(2), the
axis `family.sponsor_status_code` now checks via this fix's `op:in [ITAS_ACTIVE,
ITAP_ACTIVE, VITAS_APPROVED]`. (2) The sponsor's permit must not itself BE a family-
reunification permit (Izin Tinggal Penyatuan Keluarga) — Pasal 33(7), a condition on
the permit's *basis/category*, not its validity. This fix expresses condition (1) only
and is blind to condition (2): a sponsor holding a currently-valid ITAS that was
itself issued on a family-reunification basis satisfies this fix's enum and the law
forbids the chain regardless.

**Why not fixed here**: expressing condition (2) requires a fact this pack does not
yet have — `family.sponsor_permit_basis`, a closed enum distinguishing a
family-reunification-based permit from an independent-basis one (work/investment/
retirement/etc.). That fact is introduced on **PR #4650**, not yet merged (red on two
stale count literals as of this writing). Bolting condition (2) onto this fix would
mean gating on a fact this pack cannot yet populate.

**Disposition (this session's call, per team-lead's explicit request to choose and
state it)**: LAND this fix now, described precisely as closing the validity axis only.
The choice is safe because it is a strict subset improvement, never a new false
exclusion: every applicant this fix's `op:in` check now rejects was ALREADY failing to
meet Pasal 44(2)/47(2)/50(2)/50A(2)'s validity requirement under today's `op:known`
(which the same law never satisfied either — `op:known` only checks the field is
non-empty, not that it names a real permit state); every applicant condition (2) alone
would reject is UNCHANGED by this fix — neither newly admitted nor newly excluded,
because `op:known` was already blind to permit-basis and remains so here. Condition
(2) is a real, separately-trackable gap, not created or worsened by this fix, and is
the natural scope of the increment `family.sponsor_permit_basis` lands in once PR
#4650 merges. **This fix must never be described as "the sponsor-status constraint is
now enforced"** — only as closing the validity axis; the permit-basis axis (Pasal
33(7)) stays open and tracked here until PR #4650 lands and a follow-up increment
adds the second conjunct to these same nine rules.

---

## Known scope gap #2 — vocabulary/domain mismatch, FIX 4 HELD HARD (2026-08-23)

**Disposition: HELD, not "pending" — the enum in this fix's current form is wrong, not merely
incomplete.** Team-lead dispatched an independent read after this session's own subset-safety
argument was challenged; that read found the real defect, and this session independently
re-verified every load-bearing citation below before writing it here (file:line, not taken on
report).

**First, a correction to team-lead's own earlier objection, recorded for the trail**:
team-lead initially worried this fix would wrongly exclude a sponsor whose ITAS renewal was
filed and paid on time but still processing (cited Permenkumham 22/2023 Pasal 116(2)-(3) and
Pasal 180). That citation does not hold up — Pasal 116 in this repo's corpus belongs to a
different regulation (11/2024) answering a different question (the *applicant's* own renewal
grace period, not the *sponsor's* eligibility), and Pasal 180 traces to PP 31/2013. More
directly: `CL-E31B-REFUTER` (this same file family, `e2a-claim-ledger.md:258-274`, VERIFIED,
independently re-read by this session at those exact lines) is the claim that ORIGINALLY
proposed this three-value enum, and it already considered a "pending / in corso di
lavorazione" sponsor and explicitly REJECTED it as insufficient, citing Pasal 119's
2-working-day cure-notice-then-automatic-rejection: *"Uno sponsor il cui ITAS/ITAP risulti
scaduto, non verificato, non registrato, assente o semplicemente dichiarato 'in corso di
lavorazione' [...] non è mai sufficiente ad attivare la pratica."* So excluding a pending
sponsor is the legally correct outcome, and this session's original subset-safety argument
survived that particular objection.

**What actually kills the fix, independently re-verified against the live corpus**:

`fact_registry.py:297` (re-read this session), verbatim:
```python
_spec(FactPath.FAMILY_SPONSOR_STATUS_CODE, FactValueKind.STRING, "product_code"),
```
The fact's own declared domain is **product codes**, with no `allowed_values`. The values
actually populated in this repo's own test/gold corpus (grepped this session, not assumed):
`"E23"` (`test_evaluator_gold.py:95,351`; `_gold_fixtures.py:444` even models the plausible
condition as `in(family.sponsor_status_code, ["E23", "E28A"])` — product codes, the SAME
vocabulary the fact's own spec declares), `"NONE"` (`_gold_fixtures.py:648`), and a raw human
name, `"Nguyễn Thị Hà"` (`gold_harness/fixtures/personas/18_nfc_unicode_name.json:190`, an
edge-case Unicode-normalization fixture, not a placeholder). The proposed enum
(`ITAS_ACTIVE`/`ITAP_ACTIVE`/`VITAS_APPROVED`) is immigration-STATUS vocabulary — a disjoint
namespace from the fact's declared and populated product-code vocabulary. Not one corpus value
matches it, including the legitimate one: `CL-E31B-PRINCIPAL` (this file, above) names E23/E25
work-permit holders as an explicitly guaranteed-eligible sponsor category — a sponsor holding a
valid E23 work KITAS is exactly who the rule means to admit, and "E23" cannot equal
"ITAS_ACTIVE" under `op:in`.

So this fix, as authored, is not a narrowing of an over-permissive gate on the same vocabulary.
It is a **silent vocabulary substitution**: the value space the fact is documented and
populated with is swapped for a disjoint one, with no migration and no producer anywhere
emitting the new values.

**Two mechanisms, both independently re-verified this session, that make this worse than
merely inert**:

1. **A KNOWN value outside the enum resolves deterministic silent FALSE, never UNKNOWN.**
   `ast.py`, `InCondition` branch (re-read this session): `truth = TruthValue.TRUE if value in
   condition.values else TruthValue.FALSE` — no third branch. `evaluator.py:338`-area
   (`_safety_unknowns`, re-read this session) filters entries on `result.truth is
   TruthValue.UNKNOWN` before `on_unknown` (NEEDS_INPUT/HUMAN_REVIEW) is ever consulted — FALSE
   never reaches that gate. These 9 rules are the only rules covering the FAMILY purpose on
   their respective products, so a `"E23"` sponsor resolves the whole product UNSUPPORTED with
   `missing_purposes` set and **zero reason codes** — indistinguishable, from the applicant's
   side, from "no family product exists for you at all."

2. **The reverse (UNKNOWN) case is worse, and is the one that is actually live today.**
   `fact-mapper.ts`, `mapFamilySponsorStatus` (re-read this session, full function body,
   `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts:417-434`): every single
   branch returns `unknownFact(...)` — `NOT_APPLICABLE`, `UNVERIFIED`, or `NOT_ASKED`. There is
   no branch that ever returns a KNOWN value. The function's own comment (lines 431-432)
   states the intent explicitly: *"The UI accepts a human-entered status label. It is not
   backed by the signed status-code catalogue, so even a syntactically plausible value must
   never satisfy an engine rule that checks `op: known`."* — i.e. a PRIOR author already knew
   `op:known` was too permissive and built this frontend guard specifically to defeat it on the
   interview path. **That guard was written against `op:known`'s FALSE-on-unknown behavior —
   swap the operator to `op:in` and the same guard silently stops protecting and starts
   producing the dead-end instead. A mitigation written against one operator becoming a
   liability under another is a genuinely non-obvious failure mode**, not a coincidence of this
   one fact:
   ```
   op:known on UNKNOWN  ->  FALSE     ->  silent UNSUPPORTED        (today, live)
   op:in    on UNKNOWN  ->  UNKNOWN   ->  on_unknown=NEEDS_INPUT (8 of 9 rules)
                                       ->  BLOCKED_UNKNOWN
   ```
   Tightening the operator, on the ONLY path the frontend can currently walk, routes every real
   interview user requesting E31B/E31E/E31H/E31J into a permanently unanswerable NEEDS_INPUT
   prompt — the interview has no field that could ever resolve it, by the same guard's own
   design. Inert while the visa-engine runs in SHADOW (today); live the moment ENFORCE arms,
   which is precisely the milestone this whole correctness effort exists to unblock.

**One correction to this session's own earlier premise, which team-lead flagged and which
still matters**: this session wrote that holding the fix means "production keeps accepting
literally any non-empty string until #4650 merges," on the assumption the frontend guard made
that path unreachable. It does not, and the underlying vulnerability is real: the public
evaluate endpoint accepts canonical `ApplicantFacts` directly, `KnownString` validates only
`min_length=1, max_length=64` with no enum check, `allowed_values` (where declared elsewhere in
the registry) is consumed only at rule-compile time to check rule AUTHORS' literals — never
applied to caller-submitted data — and `traffic_source=real` requires no credential. So any API
caller can put an arbitrary 1-64 character string in this field today and satisfy `op:known`.
**That hole is real, and closing it was the right instinct.** The enum this fix chose is simply
aimed at the wrong vocabulary to close it.

**Do not attempt to fix this by widening the enum to include product codes.** The prior
question — what evidence establishes a valid ITAS/ITAP/VITAS — is answered (CL-SPONSOR-E31B/
E31E/E31H/E31J above, all VERIFIED, unaffected by this hold). The NEW, unanswered question is
what this fact IS *for*: a product code (as declared and as every corpus value shows) or an
immigration status (as every VERIFIED claim in this ledger assumes)? That is a data-modelling
decision with a signed pack and a frontend contract behind it, not something a fold should
settle by picking a wider literal list. Tracked in `.claude/skills/modus/PENDING-ARMS.md`
(owner: team-lead) rather than resolved here.
