---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/nb2-answers/response-log.jsonl
    note: "2 new live NB-2 queries this task (E3A-CF1-Q1-EXT-COUNT, E3A-CF1-Q2-D12-EXT-COUNT); citation-audit VERIFIED for both, reproduced via nb2_citation_audit.py and persisted at nb2-answers/e3a-cf1-citation-audit.json — every citation resolves against the frozen 131-source snapshot. A 3rd candidate question (re-entry/exit reset of the 180-day ceiling) was scoped but never actually run in this worktree — no record of it exists (corrected 2026-08-17 after kimi-k3 flagged an earlier, false claim that it had been logged); 2 of the 8-query CF-1 budget used."
  - path: research/visa/doctrine-factory/nb2-answers/e3a-cf1-citation-audit.json
    note: "citation-audit artifact for E3A-CF1-Q1-EXT-COUNT / E3A-CF1-Q2-D12-EXT-COUNT, both VERIFIED — generated after kimi-k3's delta review flagged the VERIFIED status as asserted-but-unrecorded"
  - path: research/visa/doctrine-factory/claims/e2a-claim-ledger.md
    note: "baseline claim ledger this addendum extends — E2a is MERGED (PR #4245), treated as read-only; new claims appended here, never edited into that file"
  - path: research/visa/doctrine-factory/claims/e2a-conflict-report.md
    note: "CF-1, the finding this addendum resolves"
  - path: research/visa/doctrine-factory/cards/D2.md
    note: "MERGED (PR #4250) D2 doctrine card — §5/§7 updated by this fast-follow to reflect the resolution below"
  - path: research/visa/doctrine-factory/cards/D12.md
    note: "MERGED (PR #4250) D12 doctrine card — extension-count doctrine added by this fast-follow"
  - path: research/visa/doctrine-factory/source-hierarchy-draft.md
    note: "§3.1.2 (cross-level supersession) — the correct resolution mechanism, §3.1.5 (pointer-resolvability test) — checked and found NOT to justify the exclusion an earlier internal draft of this file relied on"
adversarial_review: kimi-k3
---

# E3a CF-1 resolution fast-follow — D2/D12 extension-count doctrine

Fast-follow to **PR #4250** (`feat(visa-oracle): E3a slice doctrine cards (D1/D2/D12/E31B/E31D)`, MERGED).
That PR carried CF-1 (D2's 180-day extension-count discrepancy) **OPEN/ESCALATED by design**, and its own
`D2.md` §8 named "CF-1's extension-count resolution... a targeted [NB-2] query" as *"the single
highest-priority gap in this card"*. This addendum runs exactly that query, resolves CF-1 with a
primary-source pinpoint, and updates `D2.md`/`D12.md` accordingly. It does not edit `e2a-claim-ledger.md`
or the merged `D1.md`/`E31B.md`/`E31D.md` (out of scope for this fast-follow, unaffected by CF-1).

## What CF-1 was (per the merged D2.md §5)

**Settled already**: D2's 180-day figure (Permenkumham 11/2024 Pasal 95(3)) is a per-continuous-stay
ceiling, never a calendar-year cumulative aggregate.

**Left open**: two same-tier NB-2 answers disagreed on extension mechanics — `E2A-D2-DURATION` implies
2×60-day extensions (60 base + 2×60 = 180, verbatim Pasal 95(3) pinpoint); the dissenting
`E2A-D12-VS-D2` comparison-table cell states "one 60-day extension only" (bracket-cited `[2, 29]`,
resolving to internal guide `0c22e859-...`, no verbatim block-quote of statute text). `D2.md` §5 correctly
declined to pick a winner under `source-hierarchy-draft.md` §3.1.3 (same-tier disagreement is never
auto-resolved) and flagged the targeted-query path as the way to close it.

## New queries this session

**`E3A-CF1-Q1-EXT-COUNT`** (citation-audit `VERIFIED`) asked directly: does Pasal 95 (or any other
provision of Permenkumham 11/2024) fix a NUMERIC CAP on the number of times an Izin Tinggal Kunjungan
(D1/D2) may be extended, distinct from the 180-day total ceiling?

- Re-quotes **Pasal 95 Ayat (3)** in full (matches the existing ledger pinpoint) and states explicitly:
  **Pasal 95(3) itself fixes no numeric extension-count cap for the ITK (D1/D2) category** ("Non esiste
  alcuna disposizione esplicita che fissi un numero massimo di proroghe espresso in cifre... come 'paling
  banyak 1 kali' o 'paling banyak 2 kali'") — the only constraint stated is the 60-day-per-extension /
  180-day cumulative-per-stay mechanism. **Scope correction (kimi-k3 delta review, 2026-08-17)**: the
  answer's own broader phrasing ("no provision anywhere in Permenkumham 11/2024...") is an NB-2 assertion
  that outruns what this session actually examined — Q1/Q2 verified Pasal 95(3)/(4)/(7) specifically
  (verbatim, self-checkable — the quoted text contains no "paling banyak N kali" language), not every
  article of the regulation. `CL-D2-04`/`CL-D12-06` below are scoped to Pasal 95(3)/(4) accordingly; the
  wider "nowhere in the whole regulation" reading is NB-2-asserted, not independently pinpointed, and is
  not needed to close CF-1 (the actual dispute was over Pasal 95(3)'s mechanics, not the whole instrument).
- **The primary-source pinpoint that closes CF-1** is the answer's own explicit disclaimer on the "2
  extensions" figure: *"La legge non scrive letteralmente 'massimo 2 volte', ma tale limite è la
  conseguenza matematica diretta del tetto insuperabile dei 180 giorni"* — i.e. "2" is an **arithmetic
  derivation** from 60-day-base + 180-day-ceiling (60+60+60=180), never a number the statute itself states.
- **Corroborating comparison actually returned this session**: Pasal 95 **Ayat (7)** (Visa-on-Arrival
  extension — a different ITK sub-case in the *same article*) uses the identical drafting pattern —
  day-per-extension (30) + cumulative ceiling (60), again with **no** "paling banyak N kali" language —
  which the answer treats as evidence that Pasal 95 as a whole regulates extension limits exclusively via
  duration math, never via an extension-count figure, for any of its sub-cases.
- **Correction to this addendum's own earlier working assumption**: an internal planning draft of this
  task (informed by a prior, separately-run query in a now-superseded worktree) had expected this pinpoint
  to take the form of an explicit numeric-cap contrast against Pasal 113 Ayat (3) huruf a ("paling banyak 5
  kali", ITAS maritime). **That citation was NOT reproduced by this session's live query** — NB-2 answers
  are not deterministic across runs, and this session's actual transcript (quoted above, in
  `nb2-answers/response-log.jsonl`) cites Pasal 95(7), not Pasal 113(3)(a). Per this task's own
  anti-hallucination discipline (never cite a tool output not obtained in this turn), the resolution below
  rests only on what THIS session's Q1/Q2 actually returned — the Pasal 95(7) comparison plus the answer's
  own direct disclaimer, which is sufficient primary-source grounding on its own and does not need the
  Pasal 113(3)(a) contrast to close CF-1.

**`E3A-CF1-Q2-D12-EXT-COUNT`** (citation-audit `VERIFIED`) asked the analogous question for D12's
**Pasal 95 Ayat (4)** (180-day-per-extension, 12-month/360-day ceiling). Re-quotes Ayat (4) in full
alongside Ayat (3) for direct structural comparison ("la struttura sintattica e logica è identica") and
states explicitly: no numeric extension-count cap exists for D12 either — "senza alcuna menzione a un
numero massimo di istanze." Operationally, D12's 180-day-per-extension mechanic reaches the 360-day
(12-month) ceiling in a single extension (180+180=360, "basterà presentare una sola richiesta di proroga"),
so "one extension" is what a D12 holder actually files for in practice — different arithmetic outcome than
D1/D2's typical "2 extensions", same underlying legal principle (no numeric cap, only the day-ceiling
mechanism). Also independently corroborates the existing USD 5,000 D12 funds figure (`CL-D-FUNDS`).

**Correction (kimi-k3 delta review, 2026-08-17)**: an earlier version of this section additionally claimed
Q2's answer "notes Permenkumham 11/2024 was partially revoked by Permen Imipas 3/2025 — but Pasal 95 ...
is not among the revoked articles (Pasal 43/45/52/53/54/55 only)". **That claim was checked directly
against Q2's actual transcript in `response-log.jsonl` and found false — zero occurrences of "Imipas",
"3/2025", or a revoked-article list anywhere in Q2's answer.** This was the same class of cross-session
contamination this file already caught and cured once for the Pasal 113(3)(a) claim (see "New queries
this session" §Q1 above) — caught there, missed here on first pass; now removed. The fact itself may well
be true, but it was never obtained by any tool call executed in this worktree this session, so per this
task's anti-hallucination discipline it is dropped from this addendum's evidence rather than re-asserted
without a live query behind it.

**A third question** (whether the 180-day D2 ceiling resets on exit/re-entry or aggregates across a
calendar year) was **not run in this worktree** — no such query exists in this session's
`response-log.jsonl`, and it is not needed to resolve CF-1's extension-count question (settled by Q1/Q2
above). **Correction (kimi-k3 delta review, 2026-08-17)**: an earlier version of this section labeled this
`E3A-CF1-Q3-REENTRY-RESET` with status `TIMEOUT` and described it as "correctly logged" / "logged
honestly" — checked directly against `response-log.jsonl` and every other file in the repo, and found
**no record of that query_id anywhere**. That description was itself a false claim about logging
behavior (residue from a superseded, now-obsolete worktree's plan, never actually executed here) and is
corrected: the query was simply not attempted in this session. 2 of the 8-query CF-1 budget were used;
6 remain unused.

## Disposition: CF-1 CLOSED — resolution mechanism is §3.1.2, not §3.1.5

**Both readings were wrong to look for a numeric extension-count cap: it does not exist.** Reading A
("2×60-day extensions") and Reading B ("1×60-day extension only") were each treating "how many extensions"
as a fact primary law states — it doesn't. What primary law states is a single number: the 180-day (D2) /
360-day (D12) cumulative ceiling. The dispute dissolves once that is understood, rather than resolving in
favor of either side's extension-count.

**On the resolution mechanism** (important correction, made during this task's own internal kimi-k3
adversarial pass before this file was finalized — recorded here for the audit trail, per this task's
generator≠grader discipline): an earlier internal draft of this addendum tried to exclude the dissenting
`E2A-D12-VS-D2` cell under `source-hierarchy-draft.md` §3.1.5 ("a claim with no resolvable source
pointer... is UNVERIFIED, excluded"), on the premise that the cell "carried no citation". **That premise is
false, checked directly against the raw record**: the cell's dissenting sentence in
`nb2-answers/response-log.jsonl` for `E2A-D12-VS-D2` IS bracket-cited (`[2, 29]`), resolving to internal
guide `0c22e859-00d2-4dc9-a3bf-e894dbca98a8` (`visto_d2_d12_multiplo_guida_2025.txt`) via the `citations`
field of that record itself (structured, NB-2-provided mapping). **Correction (kimi-k3 delta review,
2026-08-17)**: an earlier version of this paragraph attributed the `[29]` resolution to
`e2a-citation-audit.json` — checked, and that audit's prose-pointer extractor only resolved the compound
citation's first number (`[2]`); `[29]` is absent from both its resolved and unresolved lists. The
resolution (`[29]→0c22e859`) is independently correct via the record's own `citations` field, just not via
the artifact originally cited. §3.1.5 tests pointer resolvability against the frozen snapshot, not
verbatim-ness of the citation — the pointer resolves, so §3.1.5's exclusion precondition does not hold.

**The correct mechanism is §3.1.2, cross-level supersession**: `0c22e859-...` is an internal guide
(NB-2's own `type: generated_text` classification — Level 6, "guide operative interne" per
`source-hierarchy-draft.md` §1). `E2A-D2-DURATION`'s claim rests on a verbatim quote of **Permenkumham
11/2024 Pasal 95(3)** (Level 2, ministerial regulation, still in force). Two claims on the same fact at
different authority levels disagree → the higher-level claim (L2, still valid) wins → the lower-level
claim (L6, "one extension") is marked `SUPERSEDED`, not excluded as unverified, and does not block
compilation. **New evidence (Q1's own disclaimer + the Pasal 95(7) VoA structural comparison) then goes
further**: it shows the winning L2 reading ("2 extensions") is itself imprecise — the day-ceiling is what
the law states, not an extension count — so the resolved doctrine is "no numeric cap, only the day-ceiling,"
not simply "Reading A wins."

## New claims (extend the E2a ledger, do not edit it)

**CL-D2-04 — Extension-count doctrine (no numeric cap, day-ceiling only).** Permenkumham 11/2024 Pasal
95(3) sets no maximum NUMBER of extensions for D1/D2's Izin Tinggal Kunjungan — only the 60-day-per-extension
/ 180-day cumulative-per-stay ceiling (already `CL-D2-03`). The provision's own text is explicit that no
"paling banyak N kali" language exists in Pasal 95(3), and the answer explicitly names the popular "2
extensions" figure as the arithmetic consequence of 60+60+60=180, not a statutory cap; corroborated by the
structurally-identical Pasal 95(7) VoA extension mechanism (also duration-only, no count language).
Resolution mechanism: §3.1.2 cross-level supersession over the dissenting L6 reading (see Disposition
above).
- **State: VERIFIED** (verbatim Pasal 95(3) requote + verbatim Pasal 95(7) structural comparison,
  citation-audit `VERIFIED`, `nb2-answers/e3a-cf1-citation-audit.json`). Products: D1, D2. Provenance:
  `E3A-CF1-Q1-EXT-COUNT`.
- Closes CF-1. No pack rule currently encodes this (E4/E5 gap, not compiled here) — the doctrine to carry
  forward is "no extension-count fact should ever be authored", not "author a 2-extensions cap fact".

**CL-D12-06 — Extension-count doctrine (no numeric cap, day-ceiling only), D12 analogue of CL-D2-04.**
Permenkumham 11/2024 Pasal 95(4) sets no maximum NUMBER of extensions for D12 — only the
180-day-per-extension / 360-day (12-month) cumulative-per-entry ceiling (already `CL-D12-03`). Same
drafting pattern as `CL-D2-04` (Pasal 95(3)/(4)/(7) all use duration-only language, never an explicit
extension-count figure), confirmed by the answer's direct structural comparison of Ayat (3) and Ayat (4).
Operationally the 180-day base + 180-day extension already exhausts the 360-day ceiling in one extension,
but this is arithmetic, not a legal 1-extension cap.
- **State: VERIFIED** (verbatim Pasal 95(4) requote + verbatim Pasal 95(3) structural comparison,
  citation-audit `VERIFIED`, `nb2-answers/e3a-cf1-citation-audit.json`). Products: D12. Provenance:
  `E3A-CF1-Q2-D12-EXT-COUNT`.
- No pack rule currently encodes this (E4/E5 gap, not compiled here).

## Adversarial review

Cross-family review run via `kimi -p "REFUTA questa risoluzione CF-1: verifica il meccanismo §3.1.2 vs
§3.1.5, i digest ricalcolati, e se D2.md/D12.md riflettono davvero il pinpoint" -m kimi-code/k3`
(generator≠grader, mandatory per this task's brief), scoped across this file and the updated
`cards/D2.md`/`cards/D12.md`. Dispositions below.

1. **[Internal, pre-finalization]** An earlier draft of this file's Disposition section applied
   `source-hierarchy-draft.md` §3.1.5 to exclude the dissenting `E2A-D12-VS-D2` cell on the premise that it
   "carried no citation" — checked directly against the raw record (`nb2-answers/response-log.jsonl`) and
   found false: the cell IS bracket-cited (`[2, 29]`, resolving to `0c22e859-...`). **Cured before this
   file was written to disk**: the correct mechanism is §3.1.2 cross-level supersession (L6 internal guide
   superseded by the still-valid L2 ministerial regulation); substantive conclusion unchanged (no numeric
   extension-count cap exists), mechanism corrected.
2. **[Confirmed, cured]** `D2.md`'s recomputed `claims_digest` — `CL-D2-03`'s formal `state` (as recorded
   in the immutable, merged `e2a-claim-ledger.md`) is left unchanged at `VERIFIED-WITH-CAVEAT`; only the
   new `CL-D2-04=VERIFIED` pair is added to the digest input, and the card's prose is updated to say the
   caveat's underlying citation-disagreement is now resolved (not that the claim's formal state changed) —
   this task does not edit `e2a-claim-ledger.md`.
3. **[Confirmed, cured]** `D12.md`'s recomputed `claims_digest` adds `CL-D12-06=VERIFIED`; `CL-D12-03`
   remains `VERIFIED` unchanged (CF-2 was already fully resolved before this fast-follow — no caveat to
   remove there).

**Delta-scoped kimi-k3 pass, run 2026-08-17 after the above was drafted and D2.md/D12.md were updated**
(per this fast-follow's own brief: "the diff post-merge is a new claim" — a second, independent adversarial
pass against the actual delta, not a repeat of the pre-finalization self-check above). Full transcript
verified every claim against the live repo state (raw `response-log.jsonl`, `e2a-citation-audit.json`, the
frozen 131-source snapshot, `source-hierarchy-draft.md`) and recomputed all four digests (both new, both
original-pre-extension) from scratch. Verdict: **the core doctrine and both digests are sound; the delta
as first drafted was NOT clean** — 5 findings, all confirmed and cured below.

4. **[P0, CONFIRMED, cured]** `D2.md`'s header (original lines 24-25) still read *"CF-1 is carried here as
   OPEN/ESCALATED — it is NOT resolved by this card"* — directly contradicting the new §5 ("RESOLVED") and
   §7 ("CF-1 CLOSED"). Same defect in the frontmatter `sources` note for `source-hierarchy-draft.md`, which
   still described §3.1.3 (the superseded mechanism) as the one CF-1 applies. **Cured**: both rewritten to
   state CF-1 was resolved 2026-08-17, pointing to §5/`e3a-cf1-resolution.md`.
5. **[P0, CONFIRMED, cured]** This file's Q2 section claimed Q2's answer "notes Permenkumham 11/2024 was
   partially revoked by Permen Imipas 3/2025... Pasal 95 not among the revoked articles" — checked directly
   against Q2's actual transcript and found **zero occurrences** of "Imipas"/"3/2025"/a revoked-article
   list anywhere in it. Cross-session contamination, same class as the Pasal 113(3)(a) claim this file
   already caught and disclosed once (see "New queries this session" §Q1) — caught there, missed here on
   first pass. **Cured**: removed from this file and from `CL-D12-06` in both this file and `D12.md`; not
   re-queried (the fact isn't needed to close CF-1).
6. **[P1, CONFIRMED, cured]** This file described a third query, `E3A-CF1-Q3-REENTRY-RESET`, as status
   `TIMEOUT` and "correctly logged, not silently dropped" — checked against `response-log.jsonl` and the
   whole repo, and **no record of that query_id exists anywhere**. The "logged" claim was itself false —
   residue from a superseded worktree's plan, never actually executed in this session. **Cured**: rewritten
   to state plainly that a third question was scoped but never run here.
7. **[P1, CONFIRMED, cured]** The "citation-audit VERIFIED" status for Q1/Q2 was asserted in prose with no
   backing artifact (`e2a-citation-audit.json` predates this task and has no E3A entries). kimi-k3
   independently reproduced the check (all 10 Q1 + 8 Q2 citation pointers resolve against the frozen
   131-source snapshot) and confirmed VERIFIED is substantively correct. **Cured**: re-ran
   `nb2_citation_audit.py` against this session's log and persisted the result at
   `nb2-answers/e3a-cf1-citation-audit.json`; both frontmatter and the claim entries now cite that file.
8. **[P2, CONFIRMED, cured]** `CL-D2-04`/an earlier phrasing used the broad form "no provision anywhere in
   Permenkumham 11/2024 fixes a numeric extension-count cap" — this outruns what Q1/Q2 actually examined
   (Pasal 95(3)/(4)/(7) specifically, not the whole instrument); the broad form is NB-2-asserted, not
   independently pinpointed. **Cured**: scoped the claim language to Pasal 95(3)/(4), noted as NB-2-asserted
   beyond that scope, and flagged as non-blocking for CF-1's actual dispute (which was about Pasal 95(3)
   specifically).
9. **[Note, not a defect]** The dissenting `E2A-D12-VS-D2` cell carried **two** wrong claims, not one —
   "one 60-day extension" AND the already-resolved "180 cumulative days per calendar year" category error
   — both traced to the same superseded L6 source, so §3.1.2's supersession disposes of both consistently.
   Recorded in `D2.md` §5 for completeness; not a correction to anything previously stated as fact.
10. **[Procedural caveat, surfaced not cured — belongs to Zero, not this task]** `source-hierarchy-draft.md`
    is still an unratified **DRAFT** (gate G-E1). Using its §3.1.2 to remove an OWNER-ESCALATION marker is
    consistent with the ledger's existing conventions (the merged card already used the same draft's
    vocabulary), but the closure procedurally leans on a document Zero has not yet approved. Not resolved
    here — flagged for the team-lead/Zero alongside this PR.

Net: 2 P0 + 2 P1 + 1 P2 finding from the delta-scoped pass were real and are cured above; 1 note recorded
for completeness; 1 procedural caveat surfaced but left for Zero's ratification decision, not curable by
this task. The core doctrine (no numeric extension-count cap in Pasal 95(3)/(4), only the day-ceiling) and
all four digests (2 new, 2 original-pre-extension, all independently recomputed by the reviewer) survive
both passes unchanged.
