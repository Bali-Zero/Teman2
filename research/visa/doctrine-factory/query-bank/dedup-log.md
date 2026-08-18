---
date: 2026-08-17
domain: visa
client_case: none
sources: [visa-oracle-adjudication/output-A/03-nb2-interrogation-program.md, visa-oracle-adjudication/output-B/03-nb2-interrogation-program.md, visa-oracle-adjudication/output-C/blueprint-completa.md, docs/plans/2026-08-15-visa-oracle-doctrine-factory (git show b49bb8d98:visa-oracle-adjudication/execution-plan.md)]
adversarial_review: kimi-k3
---

# E2b PREP — dedup log

## Method

1. Parsed all three blueprints' query tables programmatically (`grep`-verified row counts, not
   trusted from prose headers — output-B's own title claims "164 queries" but the table itself
   has 166 rows; caught by counting `QB\d+-\d+` row markers, not by reading the header).
2. Assigned every raw query to one of 21 topic codes (T0..T18, T20) — a taxonomy built from
   output-B's own §3 coverage-audit table (which already maps its 18 batches to the master
   prompt's 20 numbered dimensions) plus T1N (external-neighbor doctrine, unique to output-C)
   and T20 (gold/QA/compiler-local jobs, unique to output-C's B7b, NOT NB-2-facing).
3. Within each topic, merged raw queries when they targeted the **same product-set (or the same
   "ALL"/family-prefix scope) AND the same question intent** — not merely the same batch. Two
   queries asking the same thing about the same products in different words were fused into one,
   keeping the best-worded / most structurally complete phrasing (in practice: output-C's
   templated 17-field doctrine-card ask for T1; output-B's per-product breakdown for T2/T4/T5/T7;
   output-A's more terse phrasing was folded in as a provenance id wherever a B/C equivalent
   existed, and kept as the base only for topics where A was uniquely granular, e.g. T6
   compensation and T15 blacklist-exit-procedure).
4. Two batches were kept intentionally UN-compounded because compounding would destroy their
   purpose: T2's BLOCKED-11 pinpoint hunt (output-B §B15, 11 rows — one atomic article-level
   pinpoint probe per BLOCKED product, feeding OD-4 directly) and T18's benchmark-variant battery
   (output-C §B7a, 7 rows — each changes exactly one fact from the Argentina benchmark, by design
   parametric/atomic).
5. output-C's B0 canary (5 rows, `VO-NB2-001..005`) is a **procedural isolation test**, not a
   content query — kept as 5 distinct atomic probes (topic T0, `category: canary`), never merged
   with the substantive corpus/freshness queries from output-B's B0+B1.

## Real per-blueprint counts (do not trust the numbers in the task brief or in the blueprints' own
headers — verified on disk)

| Blueprint | Claimed | Measured | How verified |
|---|---|---|---|
| A | "140 query + 20 refuter" | **140** query rows; **no discrete 20-item refuter query list** — output-A §6.4 has a 10-category red-team *attack plan* (Precedence/Freshness/Unknown-laundering/Boundary-probing/Multi-purpose/Language-asymmetry/Graph-cycles/LLM-injection/Back-edit/Review-fishing), not 20 individually-worded queries | `grep -oE '\| nb2q-b\d+-\d+' \| wc -l` = 140; grepped for "refut\|red.team" in output-A, found only the §6.4 prose plan |
| B | "164+18" | **166** query rows; **no dedicated refuter batch** (its own red-team content lives in `08-red-team-and-verdict.md`, a prose critique of the proposal itself, not a query list) | `grep -oE '\| QB\d+-\d+' \| wc -l` = 166 (doc's own title/batch-sum-table says 164 — off by 2, both undercount) |
| C | "154+10 with B0 canary" | **154** numeric `VO-NB2-0xx` rows + **10** `VO-NB2-B1N-*` rows = **164** total; B0 canary is 6 of the 154 (`VO-NB2-001..006`) | `grep -oE 'VO-NB2-[0-9]{3}' \| sort -u \| wc -l` = 154; `grep -oE '\`VO-NB2-B1N-[A-Z0-9]+\`'` = 10 |

The task brief's "20 refuter" (A) / "18 refuter" (B) figures do not correspond to any discrete
query list in either blueprint — they were carried over loosely from OD-3's shorthand
("A: 140/20; B: 164/18") in the execution-plan.md, which itself appears to be citing each
blueprint's *red-team section item count* (A has 10 attack categories + some sub-items; B's
red-team doc is unstructured prose) rather than a query count. This is flagged, not silently
corrected in the task brief — see `fused-bank.md` §Real per-blueprint counts.

## Fusion result vs OD-3's "~160-170" estimate

**247 fused unique queries** (raw ≈470 across A+B+C: 140+166+164; grew from an intermediate 239 to
247 after the Kimi refuter pass below split 4 mega-compound rows into 10 atomic rows net +8, minus
the pre-existing rows they replaced, plus 1 net-new RPTKA row). This is materially above OD-3's
"~160-170" planning estimate. Root cause: OD-3's estimate was written before any line-by-line
fusion pass — it appears to average the three blueprints' own totals (roughly (140+166+164)/3 ≈
157) rather than reflecting an actual deduped merge. A defensible fusion that does not silently
drop genuine legal discriminants (e.g. the E28 tier matrix needs distinct rows for E28A-vs-B,
C-vs-D-vs-F, not one omnibus "compare E28" query, because each pair has a different legal test)
lands near 250. **This is reported as a finding for the gate-owner, not
force-fitted down to the earlier estimate** — the task's own instruction was to report the real
number, and OD-3 itself says the size is not the gate (the coverage matrix is).

Where the count could still legitimately shrink toward 160-170: T2 (31, boundary comparatives) and
T3 (18, activity boundary) are the two largest non-doctrine-card topics and the ones most amenable
to further compounding if NB-2 query-budget pressure appears during E2b execution — flagged for the
E2b execution-time operator, not compounded here (compounding further now would re-introduce the
exact loss-of-discriminant risk this pass was designed to avoid).

## Adversarial review

Seat: `kimi-k3`. **10 objections raised** (5 dedup, §a; 5 coverage-gap, §b). **7 survived and were
acted on**: 3 mega-compound splits applied verbatim (T7-9, T8-2, T8-4; a 4th split, T8-3, was added
proactively on the same defect class during disposition), 2 comparatives (T2-048, T2-061) kept as-is
with a logged execution-time caveat rather than re-split, 1 net-new coverage row added (RPTKA
job-title binding), 1 net-new row folded into an existing split (EPO into T8-3). **3 did not
survive** — false alarms from partial-context review (dependent-cascade, overstay, bridging —
already covered by topics outside Kimi's extract, verified against the full matrix, §b).

Dispatched: `~/.kimi-code/bin/kimi -p "REFUTA: cerca dedup sbagliati (query fuse che chiedono cose
diverse) e buchi di coverage non dichiarati" -m kimi-code/k3` (timebox 8 min), pasting: the topic
taxonomy, the T2/T3/T7/T8 fusion tables (highest fan-in topics, most dedup risk), and the coverage
matrix's gap-detection result (0 gaps on REACHABLE products after the E33G fix: the fact
`work.employer_is_indonesian_entity` was initially mapped to both T6 and T11, leaving E33G with an
unmet T11 requirement since T11 is RPTKA-administrative and conceptually doesn't apply to E33G; the
mapping was corrected to T6 only — for which an `ALL`-target row already gave coverage — and a
dedicated confirmatory row was also added under T13, remote-work).

Kimi's response (kimi-code/k3, session `session_56f9763b-190e-42b9-9567-bc296776b05a`), verbatim
dispositions applied:

### (a) Dedup findings — applied

- **T7-9 mega-compound** (5 heterogeneous claims: per-product sponsor matrix, invitation-sufficiency,
  hotel/villa sponsor, D-series exemption, E28C semantics-change): CONFIRMED real — a single query
  cannot verify 5 legally-disjoint claims. **Split into 5 atomic rows** (T7 grew from 9 to 13).
- **T8-2 compound** (blackout-window ≠ biometrics/online filing mode): CONFIRMED — **split into 2**.
- **T8-3 compound** (KITAS-exit-without-reentry ≠ re-entry-permit/reporting/maintenance conditions):
  CONFIRMED — **split into 2**, plus Kimi's own EPO (Exit Permit Only) suggestion folded into the
  first half as an added sub-ask (not a new row, to avoid re-introducing a mini-compound).
- **T8-4 compound** (conversion-matrix eligibility ≠ offshore/onshore filing-locus): CONFIRMED —
  **split into 2**.
- **T2-048** (C2/D2/D12 activity comparative) and **T2-061** (E33/E33E/E33F/E33G family comparative):
  Kimi flagged both as risky fusions. Checked against provenance: **both are single-source, verbatim
  from output-C's own B2 batch** (`VO-NB2-048`, `VO-NB2-061`) — not artifacts of this task's A∪B∪C
  fusion. Disposition: **kept as-is**, with a caveat now logged here for E2b execution time — if NB-2's
  answer conflates the sub-products, split the *answer* into per-product claims at claim-ledger time
  rather than re-splitting the query now (splitting now would diverge from "keep the blueprint's own
  best-worded phrasing" without new information).

### (b) Coverage-gap findings — checked, false alarms (context Kimi didn't have)

- "Dependent cascade on principal loss (death/divorce/job loss)": **already covered**, T10 row 8
  (`QB9-08`, "Death or divorce of the sponsor spouse: effect on the dependent's permit and lawful
  transitions"). Kimi's extract only showed T2/T7/T8.
- "Overstay/sanctions coverage zero": **already covered**, T15 has 8 rows including the overstay fine
  ladder (`QB14-01`/`nb2q-b15-01`) and the immigration.overstay_days fact maps to T15 in the coverage
  matrix — 0 REACHABLE-product gaps confirmed by the coverage-matrix script, not just asserted.
- "Bridging visa eligibility/conditions, not just sponsor": **already covered** by the T1 doctrine
  card for BRIDGING (permitted/prohibited activities, entry, duration, extensions, conversions is the
  card's own field list) — T7's bridging row only ever claimed to cover the sponsor-of-record facet.

### (c) Net-new finding accepted

- **RPTKA job-title/position binding for E23** (does the RPTKA-approved position bind the actual role
  performed?): genuinely not covered by any of A/B/C's RPTKA-adjacent rows (`QB10-01`..`07` ask who
  files/pays/exempts/changes-employer, never whether the registered position is binding). **Added as a
  new T11 row.**

### Verdict (Kimi's own words, translated)

"Defensible with reservation: yes on structure, but only if the multi-claim compounds (T7-9, T8-2/3/4)
are split or marked multi-assert at grading time — otherwise the dedup false positives stay inside the
matrix as apparent coverage." **All 4 flagged compounds were split** (see §a) — the reservation is
resolved, not waived.
