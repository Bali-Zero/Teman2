---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/tools/gen_branch_graph.py
    note: "throwaway generator this task wrote, run this session against apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/{tree,flow}.ts"
  - path: research/visa/doctrine-factory/e4/branch-graph.json
    note: "generated artifact, this session"
  - path: research/visa/doctrine-factory/e4/branch-graph.mmd
    note: "generated mermaid source, this session"
  - path: apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/flow.ts
    note: "computeNextNode — the ground truth this graph renders"
adversarial_review: kimi-k3
---

# Branch graph — interview as it IS today

Generated from the live code, not hand-drawn: `python3 research/visa/doctrine-factory/tools/gen_branch_graph.py`
reads `tree.ts` (the 49-question registry) and `flow.ts` (`computeNextNode`, `FIXED_CATEGORY_QUESTIONS`)
and emits `branch-graph.json` (structured) + `branch-graph.mmd` (mermaid). **Re-run after any `tree.ts`/
`flow.ts` edit** — this prose and the checked-in artifacts will drift otherwise, same class of staleness the
2026-08-12 fact-vocabulary design's citations already fell into (`fact-schema-v2-proposal.md` §0).

**Caveat on the generator itself**: it is regex-based, not a TypeScript parser, and its docstring says so.
Two known artifacts in `branch-graph.mmd`, both harmless for a documentation diagram and called out here
rather than silently left in the picture:

1. A stray `remote_income --> review_gate` edge — the regex that extracts `computeNextNode`'s
   `switch`-case bodies picks up the dead-node case (`case "tourism_duration": case "remote_income":`) as
   if it were a live edge from `remote_income`, because the two `case` labels share one return statement.
   It is real code, but per `question-registry-audit.md` §2 that whole bucket is unreachable — the edge
   exists in the source text but never fires at runtime.
2. A `review_gate -. cond .-> review_gate` self-loop — an artifact of the generator's `default:` branch
   in the switch (the shared "next in sequence" fallthrough for any question not explicitly cased);
   `review_gate` itself is handled by an earlier explicit case (`review_gate` → `confirmation`), so this
   self-loop is dead regex noise, not a real cycle. Confirmed against `flow.ts:338-339` by hand.

Neither artifact changes any conclusion in this report or in `question-registry-audit.md`; both are
generator limitations, disclosed rather than silently cleaned up, per the no-silent-caps convention.

## Entry spine (shared prelude, all categories)

```
framing → in_indonesia
  in_indonesia=yes → permit_expiry → current_status_code → overstay_days
  in_indonesia=no  → overstay_days
overstay_days
  in_indonesia=yes → wants_onshore_conversion → application_channel → nationalities
  in_indonesia=no  → nationalities
nationalities → birth_date → category → trip_scope → [per-category branch]
```

10 questions before the interview even knows which of the 10 categories the applicant is in. This spine is
identical for all 10 categories — the only branch point inside it is `in_indonesia` (onshore vs offshore
entry, 2-way) and `overstay_days` (re-converges the onshore-only `wants_onshore_conversion`/
`application_channel` pair).

## Per-category branches (7 fixed, 3 dynamic)

Fixed sequences (`FIXED_CATEGORY_QUESTIONS`, verified by the generator against the live array literal):

| Category | Sequence after `trip_scope` |
| --- | --- |
| `tourism` | `stay_days → entry_pattern` |
| `business` | `business_activity → work_indonesia_compensation → stay_days → entry_pattern` |
| `work` | `sponsor_category → work_payer → work_indonesia_compensation → work_sponsor_confirmed → work_role → stay_days` |
| `remote` | `sponsor_category → remote_clients → remote_compensation → remote_employer_country → remote_pt_pma → stay_days` |
| `study` | `sponsor_category → study_level → study_admission_confirmed → study_sponsor_confirmed → stay_days` |
| `diaspora` | `diaspora_connection → diaspora_documents → stay_days` |
| `other` | `other_purpose → other_paid_activity → stay_days → entry_pattern` |

Dynamic sequences (built inside `getCategoryQuestionIds`, branch-dependent on an earlier answer within the
same category — read from `flow.ts:394-471`, not from a static array):

- **`invest`** — `sponsor_category → investment_vehicle → [branch by investment_vehicle]`:
  - `pt_pma` → `investment_pt_pma → investment_capital_idr → investment_paid_up_capital_idr → investment_role`
  - `property` → `secondhome_property_value_usd`
  - `bank_deposit` → `secondhome_deposit_usd → secondhome_state_bank → secondhome_own_name`
  - any other/unanswered value → no branch questions, falls straight to `stay_days`
  - all four sub-paths converge on `stay_days`
- **`retirement`** — `sponsor_category → retirement_basis → [branch by retirement_basis]`:
  - `bank_deposit` → `secondhome_deposit_usd → secondhome_state_bank → secondhome_own_name → secondhome_passive_income_usd`
  - `property` → `secondhome_property_value_usd`
  - `passive_income` OR `family_sponsor` → `secondhome_passive_income_usd → family_sponsor_confirmed` (**both
    values converge on the identical two-question sequence** — a design choice, not a code gap: worth
    flagging to E3/E5 as a candidate discriminator loss, since two doctrinally distinct retirement bases
    collect identical facts today)
  - any other/unanswered value → straight to `stay_days`
- **`family`** — `sponsor_category → family_relation → marital_status → family_sponsor_nationalities →
  [family_sponsor_status_code IF sponsor is non-Indonesian] → [family_marriage_registered IF relation=SPOUSE]
  → family_sponsor_confirmed → stay_days`. Two conditional insertions, both fact-dependent, not a fixed
  array — the only category whose *question count*, not just downstream routing, varies by earlier answer.

All branches converge on `review_gate → confirmation → verdict`.

## Dead subgraph

`tourism_duration` and `remote_income` are present as `QUESTIONS` entries and as `case` labels in
`computeNextNode`, but reachable from no live category sequence — see `question-registry-audit.md` §2 for
the verbatim code citation and recommendation (delete in E5/E6 build work, out of scope for this design PR).

## Machine-readable artifacts

- `branch-graph.json` — full structured dump: every question id + group + `decisionMapping.kind`, the
  category list, the fixed-sequence map, the dead-node list, and a best-effort edge list extracted from the
  entry-spine `switch` body.
- `branch-graph.mmd` — mermaid `flowchart TD` rendering of the above (entry spine + one subgraph chain per
  category + dead nodes styled/dashed in red).

## Adversarial review

Kimi K3 refutation, narrow scope (facts without claim backing, wire-contract impacts, HUMAN_CONTEXT
reclassification/fail-open), 2026-08-17, run against the full 5-doc pack at once. No finding in this pass
targeted this document specifically — its content is generated/measured, not a claim proposal, and outside
the pass's three named scopes. Two findings landed on sibling documents that reference this one
(`question-registry-audit.md`'s "7 have a fixed sequence" numeric slip, now cured, was cross-checked here
against this document's own "7 fixed / 3 dynamic" figure, which was correct throughout and required no
change).
