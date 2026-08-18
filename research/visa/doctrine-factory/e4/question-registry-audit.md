---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/tree.ts
    note: "question registry, 49 entries in QUESTIONS — measured this session via a Python regex parse (research/visa/doctrine-factory/tools/gen_branch_graph.py), not eyeballed"
  - path: apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/flow.ts
    note: "state machine — computeNextNode, FIXED_CATEGORY_QUESTIONS, getCategoryQuestionIds; the 2 dead nodes are named verbatim in the code's own comment (lines 333-337), not inferred"
  - path: research/visa/doctrine-factory/e4/branch-graph.json
    note: "generated artifact this task produced, cross-checked against the manual read above"
  - path: research/visa/doctrine-factory/cards/E31B.md
    note: "the mapFamilySponsorStatus fail-open finding this audit's §3 coordination note is grounded on, MERGED PR #4245"
adversarial_review: kimi-k3
---

# Question registry audit — E4 slice

## 1. Real measured node count

**49 questions in `QUESTIONS`, not 50** — a naive `grep -c "  id:"` on `tree.ts` returns 50 because one
extra `id:` field lives inside an `OracleOption` sub-object (not a question). Verified with a parser that
anchors on 4-space-indented `id: "…"` (the `QUESTIONS` map's own indentation level), cross-checked against
`branch-graph.json`'s `node_count_total`. This matches the execution plan's "49→pulizia" line exactly.

## 2. The 2 dead nodes

**`tourism_duration` and `remote_income`.** Confirmed verbatim from the code, not inferred behaviorally —
`flow.ts:333-337`:

```ts
// Legacy fixture snapshots can still be inspected, but this bucket is
// no longer reachable in the live graph and never feeds the API mapper.
case "tourism_duration":
case "remote_income":
  return { kind: "question", questionId: "review_gate" };
```

Both ids are still present in `QUESTIONS` (49 includes them) and still appear as string literals elsewhere
in `flow.ts` — e.g. `getCategoryQuestionIds`'s `other` category array still lists `"stay_days"` /
`"entry_pattern"` but neither dead id is reachable from `computeNextNode`'s live dispatch (`in_indonesia` →
… → `category` → `trip_scope` → per-category `FIXED_CATEGORY_QUESTIONS`/dynamic branch → `review_gate`).
No live category sequence contains either id — confirmed by grep: `tourism_duration` and `remote_income`
each appear in `tree.ts` (question definition) and in the `case` list above, and nowhere in
`FIXED_CATEGORY_QUESTIONS` or the dynamic `family`/`invest`/`retirement` branch builders.

**Recommendation: delete both from `tree.ts` in E5/E6 build work** (not in this design-only PR) — they are
unreferenced dead code with an explicit self-documenting "legacy, unreachable" comment. No claim/doctrine
implication: neither node ever reaches the engine (E4/E5 fact ontology is unaffected either way), so this
is pure cleanup, not a fact-schema decision.

## 3. The 12 HUMAN_CONTEXT lanes — per-lane reclassification proposal

Measured via `decisionMapping.kind === "HUMAN_CONTEXT"` (12, not 13 — a naive grep on the literal string
`{ kind: "HUMAN_CONTEXT" }` returns 13 because the `NotSureBehavior`/`QuestionDecisionMapping` **type
union** declaration at `tree.ts:37` also contains the substring; a parse anchored on actual `QUESTIONS`
entries gives 12, matching the execution plan's "12 HUMAN_CONTEXT lanes to reclassify"). Per the RC-1 veto
reform doctrine (execution plan E5 item (a)): "ogni flag ri-derivato come fatto reale + regole mirate, o
domanda REVIEW_ONLY con ragione claim-backed, o eliminato." Applying that three-way test to each of the 12:

| # | Question id | Category | Current behavior (per its `decisionMapping`) | Reclassification proposal | Rationale |
| --- | --- | --- | --- | --- | --- |
| 1 | `trip_scope` | entry/global | HUMAN_CONTEXT, shown before category selection | **Real fact question** — candidate FactPath `intent.trip_scope` (does not exist today; new) | This is the earliest branch point after `category`; it plausibly discriminates single-vs-multi-entry intent, a distinction adjacent to (not currently backed by) the D1/D2 duration doctrine in `e2a-claim-ledger.md`'s `CL-D1-03`/`CL-D2-03` — **correction after Kimi K3 review**: those two claims are about D1/D2's per-entry vs continuous-stay *duration mechanics*, not about the interview's branch-selection semantics; citing them as claim-backing for this candidate fact overstated the support that exists. **Zero claim currently establishes `trip_scope` as an interview-facing discriminator** (`parity-harness-rescope.md` §2 independently confirms this — 0 Tier-B claims exist for any of the 3 real-fact-question candidates). This row is a structural observation (the UI already branches on the answer behaviorally) plus a plausibility argument, not a claim-backed proposal. Needs a genuine E3 claim, scoped specifically to interview-branch semantics, before any FactPath is authored. |
| 2 | `business_activity` | business | HUMAN_CONTEXT | **REVIEW_ONLY, claim-backed** — reason: business-purpose sub-activity taxonomy (meetings/negotiations vs field survey vs site inspection) is exactly the D2/D12 discriminator boundary `e2a-claim-ledger.md`'s `CL-D-COMPARE`/`CL-D12-05` already claim-back; a free-text-shaped HUMAN_CONTEXT answer cannot safely become an enum fact without the D2-vs-D12 boundary being authored as rules first (E5). Until then it stays advisory. |
| 3 | `work_role` | work | HUMAN_CONTEXT | **REVIEW_ONLY, claim-backed** — pending E23/E31 doctrine on role-based work eligibility; no claim in the merged ledgers backs a role taxonomy today (`e2a`/`e2b-batch1` cover D1/D2/D12/E23/E28A/E33-family, not a generic "work role" enum). |
| 4 | `investment_vehicle` | invest | HUMAN_CONTEXT | **Real fact question** — candidate FactPath, close analog to the existing `investment.pt_pma_committed`/`investment.proposed_role` wire keys; the PT-PMA/property/bank-deposit vehicle split is already a real branch in `getCategoryQuestionIds` (drives which sub-questions get asked), so the fact already functions as a discriminator behaviorally — promoting it to a genuine FactPath (rather than leaving it a HUMAN_CONTEXT-only branch key) closes a gap between what the UI already decides and what the engine can see. |
| 5 | `family_sponsor_status_code` | family | HUMAN_CONTEXT | **Eliminate as a direct fact; keep as REVIEW_ONLY input to the existing `mapFamilySponsorStatus`** — this is the exact E31B fail-open sentinel (§ below). The mapper already deliberately downgrades any answer here to `UNVERIFIED`, never `KNOWN`, specifically because the underlying pack rule is value-blind (`op:known`). Reclassifying this to a "real fact question" WITHOUT first landing the E5 rule fix would reintroduce the fail-open the current code deliberately avoids — this is the RC-1 reform's central risk case, not a routine promotion. |
| 6 | `retirement_basis` | retirement | HUMAN_CONTEXT | **Real fact question** — same reasoning as `investment_vehicle`: the bank-deposit/property/passive-income/family-sponsor branch already drives real sub-question sequencing; promote once E3 backs the retirement-basis boundary with claims (currently only E33/E33E/E33F general doctrine exists per `e2b-batch1-claim-ledger.md`, not a basis-level breakdown). |
| 7 | `diaspora_connection` | diaspora | HUMAN_CONTEXT | **REVIEW_ONLY, claim-backed** — diaspora coverage is documented as "product-level, Kepmen-gated" (visaoracle skill LIVE STATE, 2026-08-06 line); no atomic claim in the merged ledgers breaks it into a connection-type enum. Stays advisory until E3 covers it. |
| 8 | `diaspora_documents` | diaspora | HUMAN_CONTEXT | **REVIEW_ONLY, claim-backed** — same rationale as #7, downstream of the same gap. |
| 9 | `other_purpose` | other | HUMAN_CONTEXT | **Eliminate (structurally)** — `other` is the catch-all category by construction; by definition no closed enum can classify it as a real fact without contradicting the category's own purpose. Recommend: keep permanently REVIEW_ONLY, with a fixed non-claim-backed reason ("uncategorized purpose — human triage required") — the one lane in this set where "claim-backed reason" does not apply because there is no doctrine to cite, only an acknowledged gap in the category taxonomy itself. |
| 10 | `other_paid_activity` | other | HUMAN_CONTEXT | **Eliminate (structurally)**, same rationale as #9 — downstream of the same catch-all category. |
| 11 | `remote_income` | (dead node) | HUMAN_CONTEXT | **N/A — delete alongside the node itself (§2)**, not a reclassification target. Listed here only for completeness against the plan's "12 HUMAN_CONTEXT lanes" count, which includes it because it is still a live entry in `QUESTIONS` even though unreachable. |
| 12 | `tourism_duration` | (dead node) | HUMAN_CONTEXT | **N/A — delete alongside the node itself (§2)**, same as #11. |

**Split**: of the 12, **2 are dead-node cleanup** (not really a reclassification decision), **2 are
structural REVIEW_ONLY-forever** (`other_purpose`/`other_paid_activity` — the catch-all category has no
closed doctrine by design), **1 is the RC-1 central risk case** (`family_sponsor_status_code`, gated on the
E31B rule fix — see §3.1), **4 are REVIEW_ONLY pending E3 claims** (`business_activity`, `work_role`,
`diaspora_connection`, `diaspora_documents`), and **3 are real-fact-question candidates** (`trip_scope`,
`investment_vehicle`, `retirement_basis`) — none of the three real-fact candidates is a FactPath schema
change this proposal makes; each needs its own claim-backed FactPath authored in E3/E5 before the reform
lands, consistent with `fact-schema-v2-proposal.md`'s §0 finding that a fact without a real claim behind it
is exactly the failure mode this whole audit exists to avoid repeating.

### 3.1 `mapFamilySponsorStatus` coordination note (sequencing with E5)

`fact-mapper.ts:417-435`'s `mapFamilySponsorStatus` **never emits `KNOWN`**, by explicit design comment:
"even a syntactically plausible value must never satisfy an engine rule that checks `op: known`." This is a
**UI-side mitigation for a fail-open in the pack itself**, documented in the merged `E31B.md` doctrine card
§4: the active rule's `op:known` predicate is *value-blind* — any non-null value satisfies it, including a
sentinel like `"NONE"`. `E31B.md` is explicit that the frontend workaround "does not change what the rule
itself would do if a KNOWN sentinel ever reached it through any other path" — it is containment, not a fix.

**Sequencing requirement for E4/reform work**: any change to `family_sponsor_status_code`'s
reclassification (row #5 above) or to `mapFamilySponsorStatus`'s emission logic that lets it start emitting
`KNOWN` **must land strictly after** the E5 rule fix that makes `op:known` value-checking (not
value-blind). Landing the mapper change first — even as an apparently-unrelated RC-1 veto-reform side
effect — would silently reopen the exact fail-open E31B's mitigation exists to contain. This is a hard
ordering constraint, not a preference: **E4/E6 must not touch `mapFamilySponsorStatus`'s "never emit KNOWN"
guard until `E31B.md`'s tracked rule fix is merged and verified in E5.**

## 4. Category count

**10 categories** (`CATEGORY_KEYS`): tourism, business, work, invest, remote, family, retirement, study,
diaspora, other. 7 have a fixed `FIXED_CATEGORY_QUESTIONS` sequence (tourism, business, work, remote,
study, diaspora, other — 7 of 10 fixed); 3 (`invest`, `family`, `retirement`) have an empty fixed entry and
are built dynamically inside `getCategoryQuestionIds` from earlier answers (e.g. `investment_vehicle` /
`retirement_basis` / `family_relation` branch selection). This matches the interview categories the
2026-08-15 architect synthesis's "10 enum" note anticipated (visaoracle skill LIVE STATE, 2026-07-23 entry:
"v2 interview=10").

## Adversarial review

Kimi K3 refutation, narrow scope, 2026-08-17, run against the full 5-doc pack at once.

| Finding | Verdict | Disposition |
| --- | --- | --- |
| §3 row #1 (`trip_scope`) cited `CL-D1-03`/`CL-D2-03` as claim backing for the interview-branch discriminator — those claims are about D1/D2's per-entry vs continuous-stay duration mechanics, not about interview branch-selection semantics; `parity-harness-rescope.md` §2 independently confirms zero claims exist for any of the 3 real-fact-question candidates. The citation overstated support. | REFUTED (real defect) | **Cured** — row rewritten to state plainly that zero claim establishes `trip_scope` as an interview-facing discriminator; the row is now a structural observation + plausibility argument, explicitly not claim-backed. |
| §4 ("category count") stated "4 have a fixed `FIXED_CATEGORY_QUESTIONS` sequence" immediately before listing 7 category names — internal numeric contradiction, also inconsistent with `branch-graph.md`'s "7 fixed / 3 dynamic". | REFUTED (textual defect) | **Cured** — corrected to "7 have a fixed sequence". |
| `family_sponsor_status_code` (row #5) correctly refuses promotion to a real fact, keeps the "never emit KNOWN" guard, and imposes the E5-rule-fix-before-mapper-change ordering — no fail-open reintroduced; the one lane treated with a hard sequencing constraint, consistent across this file and `fact-schema-v2-proposal.md`. | SOSTENUTO | No change. |
| The 2 dead-node deletions (`tourism_duration`/`remote_income`) are grounded verbatim in the code's own "legacy, unreachable" comment, not inferred. | SOSTENUTO | No change. |
