---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
    note: "companion claim ledger this report supports — each CF below is cross-referenced from a CONFLICTING claim there"
  - path: research/visa/doctrine-factory/claims/e2a-conflict-report.md
    note: "frozen E2a template + CF-1..CF-6 numbering; this report continues numbering at CF-7 to avoid collision"
adversarial_review: kimi-k3
---

# E2b batch-1 conflict report — CF-7 through CF-12

Numbering continues from `e2a-conflict-report.md`'s CF-1..CF-6 (this batch does not renumber or
re-litigate those — see the claim ledger's "Cross-referenced findings" section for the one place
this batch's answers touch e2a's CF-5). Each finding below is a REAL, self-flagged or
cross-answer-corroborated disagreement inside this batch's 34 NB-2 answers, not a stylistic nitpick —
per the task's honesty instruction, findings that turned out to be the same underlying disagreement
restated (not a new conflict) are folded into the closest existing CF rather than given a new number
(see CF-8's note on E33F).

## Findings

### CF-7 — E33E minimum age: 55 (legal-text figure) vs 60 (repeated operational claim)

Six independent answers touch E33E's minimum-age eligibility gate. `VO-FUSED-T1-032` (E33 doctrine
card) and `VO-FUSED-T1-037` (E33F doctrine card, in its E33E-comparison table) both state the
Permenkumham/Kepmen legal-text figure as **55 years**. `VO-FUSED-T4-004` (E33 threshold query,
PROSE_ONLY), `VO-FUSED-T10-009` (family-minors, VERIFIED), `VO-FUSED-T14-002` (retirement-second-home,
VERIFIED), and `VO-FUSED-T14-004` (retirement-second-home, VERIFIED) all instead state **60 years**,
attributed to Bali Zero's operational/marketing guide materials rather than the primary legal text.

This is not a single stray typo — the 60-figure recurs across four independently-queried answers
spanning three different topic categories (threshold, family-minors, retirement-second-home), which
argues it is a genuine, entrenched operational-vs-legal discrepancy rather than a one-off NB-2
synthesis error. **Disposition: OPEN, escalate.** Neither figure is dismissed as noise; both are
well-corroborated within their own citation class (primary-law text vs. operational guide). Per
`source-hierarchy-draft.md` §3.2, a primary-law citation should outrank an internal operational guide
where they conflict on the same numeric fact — **55 is provisionally the higher-authority figure**,
but this report does not unilaterally resolve it the way e2a's CF-2 resolved a clean primary-vs-
secondary case, because the 60-figure's persistence across four separately-sourced operational answers
raises the possibility that Bali Zero's actual current OPERATIONAL practice (what immigration officers
apply at the counter, as opposed to the codified minimum) really is 60, and the doctrine-card build
(E5) needs an operator/primary-source pull to confirm which age the Kantor Imigrasi Ngurah Rai
actually applies before the RulePack HARD_FILTER is set. Recording as escalated, not silently defaulted
to the legal-text number.

### CF-8 — E33/E33E to KITAP conversion timing: 3 years (Permenkumham 11/2024) vs 5 years (operational guide)

`VO-FUSED-T14-004` self-flags this discrepancy explicitly within its own answer text: Permenkumham
11/2024 Pasal 179(1)/Pasal 76 sets the ITAS-to-ITAP eligibility window at **3 years** of continuous
residence, while Bali Zero's operational/commercial guide materials (cited within the same answer)
state **5 years** as the practical conversion timeline. The 3-year legal figure is corroborated by
`VO-FUSED-T1-032` and `VO-FUSED-T1-037`, which cite the same 3-year figure in their own KITAP-path
discussions without flagging any conflict (i.e. they were not asked the comparison question directly,
but their stated figure agrees with the legal-text side of the T14-004 conflict).

`VO-FUSED-T1-037` (E33F doctrine card) also touches the SAME class of legal-vs-operational timing gap
in its own comparison table — this is folded into CF-8 rather than given a separate number, since it
is the identical underlying disagreement (statutory conversion window vs. Bali Zero's operational
practice figure), not a distinct new fact.

**Disposition: OPEN, escalate.** Same reasoning as CF-7 — the 5-year operational figure may reflect a
real practical delay pattern (processing backlog, documentation gathering) rather than a wrong legal
citation, and this report does not collapse that distinction without an operator/primary-source check.

### CF-9 — E31 child-dependent index letter: E31E (per query-bank target) vs the batch's own answers
leaning E31B, layered on top of e2a's already-REFUTED E31B/E31D swap question

This batch's two E31-child-dependent answers (`VO-FUSED-T13-003`, `VO-FUSED-T14-005`) establish the
age-≤18 rule for the child-dependent index confidently, but are NOT fully consistent on which letter
(E31B or E31E) that rule attaches to — some passages within these answers frame the Kepmen mapping as
E31B=spouse/E31E=child (matching e2a's already-verified production mapping for E31B=spouse), which
would put the child-dependent index at **E31E**, matching the query bank's own `target_products`
label for `VO-FUSED-T1-027`/`VO-FUSED-T14-005`. Other passages in the SAME two answers, when
discussing internal Bali Zero materials, use an E31D=spouse/E31B-or-E31E=child framing inherited from
the same `nb2_visa_types_final.txt` artifact e2a's CF-5 already identified as internally
inconsistent.

**Disposition: NOT a new production-risk finding — this is CF-5's already-disposed-of NB-2-source
artifact resurfacing in a different query set, not a new swap.** Per CF-5's disposition (checked
directly against `seed_visa_types_complete_2026.py` and `rulepack-prod-007.source.json`, both showing
the correct E31B=spouse/E31D=stepchild/E31E=child-of-foreigner mapping), production is unaffected.
This CF-9 entry exists only to (a) confirm the artifact recurs independently in a second, unrelated
query batch — strengthening the case that it is a genuine NB-2 ingestion defect worth an operator fix,
not a one-off hallucination — and (b) flag that `freshness-recheck-2026-08-16.md` record #10
(`ecd22722-...`, CHANGED) is the sole source for E31E's age/marital HARD_FILTER rules regardless of
which letter is correct, so the CHANGED-source risk applies to whichever index actually governs child
dependents (see the claim ledger's CL-E31E-01 caveat).

### CF-10 — E28A to KITAP conversion timing: 3 years (PP 31/2013) vs "5+ years" (commercial guide)

Self-flagged explicitly within `VO-FUSED-T1-013` (E28A doctrine card, PROSE_ONLY) itself: PP No.
31/2013 sets the investor-KITAS-to-KITAP conversion window at **3 years**, while the same answer notes
an erroneous commercial-guide figure of **"5+ years"** circulating in Bali Zero materials. This is the
SAME class of legal-vs-operational timing conflict as CF-8, but for a different product (E28A rather
than E33/E33E) and a different governing instrument (PP 31/2013 rather than Permenkumham 11/2024) — a
distinct finding, not folded into CF-8.

**Disposition: OPEN, escalate.** Because the answer is PROSE_ONLY (no structured, independently
resolvable citation), this report does not treat the 3-year figure as more firmly established than
CF-7/CF-8's VERIFIED-audited figures — flagged with a lower evidentiary confidence than CF-7/CF-8,
still real, still worth an operator check before either figure is hardcoded into a HARD_FILTER rule.

### CF-11 — MERP fee schedule: PP 45/2024 (priced) vs UU 63/2024 (automatically integrated, no fee)

Self-flagged within `VO-FUSED-T4-009` (PNBP fee-schedule query, VERIFIED-audited): PP No. 45/2024
(adopted 2024-10-18) lists a standalone PNBP fee schedule for the Multiple Exit Re-entry Permit
(MERP) — e.g. Rp 1,500,000 for a 1-year MERP — while UU No. 63/2024 (adopted 2024-09-19, the Omnibus
immigration-law amendment) states MERP is now **automatically integrated** into every KITAS/KITAP at
the moment of issuance, with no separate procedure or fee required. The answer itself resolves the
apparent conflict by statutory hierarchy (UU outranks PP under Indonesian legislative hierarchy,
independent of adoption date — UU 63/2024 was adopted one month before PP 45/2024 in any case), and
concludes officers should apply the Rp 0 automatic-integration rule, treating the PP's fee table as
superseded-in-practice for MERP specifically (not for the rest of the PP 45/2024 schedule, which
remains current per CL-CROSS-03 in the claim ledger).

**Disposition: RESOLVED, by the answer's own hierarchy reasoning** (UU > PP; more recent
immigration-specific amendment) — the automatic-integration rule governs; the PP's standalone MERP fee
line should be treated as `SUPERSEDED` if it appears in any doctrine card, matching the answer's own
conclusion rather than left as an open escalation. Recorded as RESOLVED rather than OPEN because,
unlike CF-7/CF-8/CF-10 (legal-text vs. operational-guide, same authority tier ambiguity), this is a
clean primary-law-vs-primary-law hierarchy case with an unambiguous outranking instrument, matching
the pattern of e2a's CF-2.

### CF-12 — Golden Visa investment-tier index mismatch: internal "E28G" label vs E28B/E28C

Self-flagged within `VO-FUSED-T4-010` (E33/E33A/E33E threshold query, which also touches E28
Golden-Visa tiers in its comparison context, VERIFIED-audited): an internal Bali Zero index label
"E28G" (cited with an investment figure around Rp 5 miliar / USD 700K) does not cleanly match either
of the two Kepmen-defined Golden Visa tiers — **E28B** (corporate investor, 10-year validity, USD 5M
threshold) or **E28C** (portfolio investor, 10-year validity, USD 700K threshold). The answer notes a
**2026-03-28 ERRATA CORRIGE** on this point within Bali Zero's own change-log materials, implying the
"E28G" label was already flagged internally as an error once, but the answer's own citation trail
shows it still appearing in at least one still-live internal reference.

**Disposition: OPEN, escalate to E5/operator.** The existence of a documented internal errata-corrige
means this may already be a known, partially-fixed issue rather than a fresh discovery — this report
does not claim novelty, only that the mismatch is still detectable in at least one NB-2-ingested
source as of this batch's query date, and should be checked against Bali Zero's CURRENT (not
2026-03-28) internal materials before E5 treats it as closed.

## Dedup

No findings in this batch duplicate e2a's CF-1 through CF-6 outright. The one point of overlap
(E31B/E31D/E31E index-letter confusion) is deliberately NOT given a new CF number — see CF-9's
disposition above and the claim ledger's "Cross-referenced findings" section, both of which point back
to e2a's CF-5 rather than re-opening it. CF-7/CF-8/CF-10 are three DISTINCT legal-vs-operational
timing/age conflicts (different products, different governing instruments) that happen to share a
common SHAPE (primary law says X, Bali Zero's own operational guide says Y) with each other but not
with any e2a finding — each is real and independently sourced, not a single conflict inflated into
three CF entries for appearance's sake.

## Status

Six findings this batch: **CF-7, CF-8, CF-9, CF-10, CF-12 remain OPEN** (CF-9 disposed as
"not-new-risk" per CF-5's prior production-check, but its recurrence is logged, not silently dropped);
**CF-11 is RESOLVED** by the sourced answer's own hierarchy reasoning (UU > PP), matching e2a's CF-2
resolution pattern. None of the five OPEN findings are unilaterally resolved by this report — each
needs either a primary-source pull (CF-7, CF-8, CF-10: which figure the Ngurah Rai counter actually
applies) or an operator check against CURRENT (not historical) Bali Zero internal materials (CF-12),
consistent with the task's instruction to flag real conflicts rather than paper over them by picking
a side.

## Adversarial review

Kimi K3 refutation was run jointly against this report and the companion claim ledger (see the
ledger's own `## Adversarial review` section for the full account — it was killed before delivering a
verdict, having fanned out into unbounded per-claim sub-agent verification beyond the 8-minute timebox).
The one partial finding it surfaced (a 6-vs-7 timeout-count question) does not touch any CF in this
report — it concerns the response-log/claim-ledger relationship, not a conflict finding. None of
CF-7 through CF-12 were independently re-verified beyond what each finding's own text already states
(self-flagged within its source answer, or corroborated by the count of independent answers agreeing)
— this report's OPEN/RESOLVED dispositions stand as originally written, not additionally confirmed by
an external adversarial pass this round.
