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

### CF-7 — E33E minimum age: 55 (legal-text/decree figure) vs 60 (repeated operational claim) — neither
side carries a clean, uncontested article-level pinpoint in this batch

Six independent answers touch E33E's minimum-age eligibility gate, but they do **not** cleanly split
into "55 = both primary-law answers" vs "60 = four operational answers" the way an earlier draft of
this finding described. Re-verified directly against the raw JSONL in this pass:

- `VO-FUSED-T4-004`, `VO-FUSED-T10-009`, `VO-FUSED-T14-002`, `VO-FUSED-T14-004` (four answers) DO
  consistently attribute **55 years** to the named decree `Kepmen M.IP-08.GR.01.01/2025` and **60
  years** to Bali Zero's own internal operational guide / Ditjen Imigrasi Bali counter practice — e.g.
  `VO-FUSED-T10-009`: "*discrepanza diretta tra la fonte regolamentare primaria nazionale (Kepmen
  M.IP-08.GR.01.01/2025 che fissa l'età minima di E33E a 55 anni) [9] e la prassi operativa... che ne
  limita il rilascio ai soli soggetti con almeno 60 anni*." None of these four passages quotes a
  Pasal/article number for the 55-year figure — only the decree name.
- `VO-FUSED-T1-032` (E33 doctrine card) is **internally self-contradictory**: its prose explicitly
  cites an article-level pinpoint — "*Il Permenkumham 11/2024 (Art. 33 comma 2 lettera j) ha ridotto
  ufficialmente il requisito di età minima a 55 anni per le sottocategorie E33E... e E33F*" — but the
  SAME answer's own later comparison table lists `E33E | Silver Hair (Anziani 60+) | Età ≥ 60 anni +
  Deposito USD 50k`, directly contradicting its own prose citation. This is the only Pasal-level
  citation for either figure found anywhere in this batch, and it is contradicted by its own source.
- `VO-FUSED-T1-037` (E33F doctrine card) does **not** corroborate "55" as E33E's legal-text figure
  the way an earlier draft claimed. Its own "DECISIONI CHIAVE" section reads: "*Alcune disposizioni
  nazionali generiche... indicano un'età generica di 55+ per la categoria Casa Vacanza. Tuttavia, le
  guide pratiche operative mostrano che per il visto premium Silver Hair E33E la prassi ministeriale a
  Bali esige tassativamente un'età minima di 60 anni, lasciando la soglia dei 55 anni unicamente
  all'E33F pensionistico standard*" — i.e. T1-037 reserves 55 for E33F specifically and treats 60 as
  the applicable figure for E33E via ministerial practice, the OPPOSITE framing from what the earlier
  CF-7 draft attributed to it (see also CL-E33F-02, corrected below to match).

**Disposition: OPEN, escalate — and neither figure gets called "provisionally higher-authority."**
Per `source-hierarchy-draft.md` §3.2, a primary-law article citation should outrank an internal
operational guide where they conflict — but the only article-level citation this batch's answers
offer for either figure (`T1-032`'s "Art. 33 comma 2 lettera j") is contradicted by its own source's
comparison table, and the source most naturally read as corroborating "55" for E33E specifically
(`T1-037`) in fact argues the opposite. §3.2 cannot mechanically break this tie when the strongest
candidate pinpoint self-contradicts. Both 55 and 60 remain unconfirmed pending a primary-source pull
(the Permenkumham 11/2024 text itself, not an NB-2 synthesis of it) — the doctrine-card build (E5)
needs an operator check against the actual Pasal 33(2)(j) text and against what the Kantor Imigrasi
Ngurah Rai counter applies before the RulePack HARD_FILTER is set.

### CF-8 — E33/E33E to KITAP conversion timing: 3 years (Permenkumham 11/2024) vs 5 years (operational guide)

`VO-FUSED-T14-004` self-flags this discrepancy explicitly within its own answer text: Permenkumham
11/2024 Pasal 179(1)/Pasal 76 sets the ITAS-to-ITAP eligibility window at **3 years** of continuous
residence, while Bali Zero's operational/commercial guide materials (cited within the same answer)
state **5 years** as the practical conversion timeline. `VO-FUSED-T1-032` and `VO-FUSED-T1-037`
independently STATE the same 3-year figure in their own KITAP-path discussions — but neither was
ever asked the 3-vs-5 comparison question directly, so neither one weighed the two figures against
each other or resolved a dispute. That is weaker than "corroboration" of one side of an open,
disputed question: it means two more answers happen to state 3 years when asked in isolation, not
that two more answers were shown the conflict and sided with the legal-text figure.

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
a commercial-guide figure of **"5+ years"** that conflicts with it, circulating in Bali Zero
materials. This is the
SAME class of legal-vs-operational timing conflict as CF-8, but for a different product (E28A rather
than E33/E33E) and a different governing instrument (PP 31/2013 rather than Permenkumham 11/2024) — a
distinct finding, not folded into CF-8.

**Disposition: OPEN, escalate.** Because the answer is PROSE_ONLY (no structured, independently
resolvable citation), this report does not treat the 3-year figure as more firmly established than
CF-7/CF-8's VERIFIED-audited figures — flagged with a lower evidentiary confidence than CF-7/CF-8,
still real, still worth an operator check before either figure is hardcoded into a HARD_FILTER rule.
Neither figure is called "erroneous" here — that word would pick a side this disposition explicitly
does not pick; "5+ years" is a commercial-guide figure that conflicts with the PP 31/2013 3-year
figure, nothing more is asserted about which one is wrong.

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
"E28G" (`nb2_visa_types_final.txt`) is defined internally as "Golden Visa 10Y" carrying an investment
threshold of **"Rp 5 miliar+" OR "USD 700,000"** [43, 65] — cited as if these were the same figure,
but they are not. **Numeric mismatch, verified directly against the raw JSONL in this pass and
strengthening the underlying finding**: Rp 5,000,000,000 is approximately USD 300-320K at any
plausible 2025-26 exchange rate (~15,500-16,500 IDR/USD) — the answer's own text makes this same
observation, converting "Rp 5 billion" to "approx. USD 310,000" and noting it does not match the
USD 5,000,000 corporate (E28B) threshold. Neither does it match the "USD 700,000" figure the SAME
internal "E28G" label also carries — USD 700,000 is roughly Rp 11+ billion at the same rate, and is
in fact the E28C portfolio-investor threshold under Permenkumham 11/2024. So the Rp-figure and the
USD-figure attributed to "E28G" **do not reconcile with each other at any plausible exchange rate**,
on top of neither one cleanly matching either real Kepmen-defined tier — **E28B** (corporate
investor, 10-year validity, USD 5M threshold) or **E28C** (portfolio investor, 10-year validity, USD
700K threshold). This double mismatch (internal-vs-internal AND internal-vs-Kepmen) is itself part of
the E28G finding, not a separate issue to note in passing: it strengthens the case that "E28G" is an
internal-material labeling error rather than a real, distinct investment tier — the two figures
attached to it were never meant to describe the same threshold and were conflated. The answer notes a
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
(E31B/E31D/E31E index-letter confusion) IS given a new CF number — **CF-9** — because the recurrence
of the underlying NB-2-source artifact across a second, independent query batch is itself worth
recording as evidence. What is deliberately NOT re-opened is CF-5's *disposition*: CF-9's own verdict
defers entirely to e2a's CF-5 finding that production is unaffected, rather than re-litigating it —
see CF-9's disposition above and the claim ledger's "Cross-referenced findings" section, both of which
point back to e2a's CF-5 for the production-risk verdict while still logging the recurrence as a new
entry. CF-7/CF-8/CF-10 are three DISTINCT legal-vs-operational
timing/age conflicts (different products, different governing instruments) that happen to share a
common SHAPE (primary law says X, Bali Zero's own operational guide says Y) with each other but not
with any e2a finding — each is real and independently sourced, not a single conflict inflated into
three CF entries for appearance's sake.

## Status

Six findings this batch: **CF-7, CF-8, CF-10, CF-12 remain OPEN**; **CF-9 is a new entry in this
report (recording that the underlying NB-2-source artifact recurs in a second, independent query
batch) but is already DISPOSED, not open** — it defers entirely to e2a's CF-5 finding that production
is unaffected, and is not re-litigated here; **CF-11 is RESOLVED** by the sourced answer's own
hierarchy reasoning (UU > PP), matching e2a's CF-2 resolution pattern. None of the four OPEN findings
are unilaterally resolved by this report — each needs either a primary-source pull (CF-7, CF-8,
CF-10: which figure the Ngurah Rai counter actually applies) or an operator check against CURRENT
(not historical) Bali Zero internal materials (CF-12), consistent with the task's instruction to flag
real conflicts rather than paper over them by picking a side.

## Adversarial review

**Round 1** — Kimi K3 refutation was run jointly against this report and the companion claim ledger
(see the ledger's own `## Adversarial review` for the full account — it was killed before delivering a
verdict, having fanned out into unbounded per-claim sub-agent verification beyond the 8-minute
timebox). The one partial finding it surfaced (a 6-vs-7 timeout-count question) did not touch any CF
in this report.

**Round 2** — the orchestrator re-ran Kimi K3 directly with a narrower text-only scope (no tool calls,
no sub-agents), which completed inside budget and returned 25 numbered findings, several of which
concern CF-7/CF-8/CF-9/CF-10/CF-12 directly. All were cured against the raw JSONL/citation-audit
evidence in this session:

| Finding | Disposition |
|---|---|
| CF-9 (ledger + this report's Dedup section both say "not logged as a new number") self-contradicts — CF-9 IS a new entry | **FIXED** — reworded: CF-9 is a new report entry recording the recurrence as evidence; its *disposition* defers to e2a's CF-5 (production unaffected) |
| Status list calls CF-9 "OPEN" while its own disposition says disposed | **FIXED** — CF-9 pulled out of the OPEN list, given its own sentence |
| CF-7 declares 55 "provisionally higher-authority" without an article-level pinpoint for either side | **FIXED, deeper than the literal finding** — re-checking `VO-FUSED-T1-032`'s raw text found its own comparison table CONTRADICTS its own "Art. 33(2)(j)" prose citation, and `VO-FUSED-T1-037`'s actual text argues the OPPOSITE of what this report originally attributed to it (reserves 55 for E33F, applies 60 to E33E via ministerial practice). CF-7 rewritten: neither figure is called higher-authority; the disposition and the finding-body now agree |
| CF-8: T1-032/T1-037 counted as "corroborating" the 3-year figure though neither was asked the 3-vs-5 comparison | **FIXED** — reworded to "independently stated the figure without being asked to compare it," not "corroborated" |
| CF-10 narrates the 5+yr figure as "erroneous" while its own disposition says neither side is more firmly established | **FIXED** — "erroneous" removed, replaced with neutral "conflicts with"; narrative now matches disposition |
| CF-12: "Rp 5 miliar / USD 700K" don't reconcile at any plausible exchange rate (≈USD 310K vs USD 700K) | **FIXED** — the mismatch is now stated explicitly, as additional evidence the "E28G" label is itself an internal-material error rather than a genuine distinct tier |

No finding was rejected/refuted as wrong — every item Kimi raised against this report was a real
defect, cured against primary evidence (the JSONL raw answer text), not by narrative repair alone.
This report has now been through two independent adversarial passes: Round 1 (whole-document, timed
out, one non-issue self-verified) and Round 2 (narrow-scope, completed, 6 real findings against this
file's text, all cured). CF-11 (RESOLVED, statutory hierarchy) was not flagged by either round and
stands as originally written.
