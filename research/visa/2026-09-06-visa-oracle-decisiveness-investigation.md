---
date: 2026-09-06
domain: visa
client_case: none — Visa Oracle public funnel decisiveness investigation (offline replay + 3 synthetic prod probes, signed pack seq-19)
sources:
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-019.signed.json (active signed pack, sequence 19, version 2026.9.5, payload_sha256 bac5da8e…e6ea, 109 rules / 38 products)
  - apps/backend-rag/backend/services/visa_engine/evaluator.py (per-product proof construction and decision-state precedence)
  - apps/backend-rag/backend/services/visa_engine/evaluate_path.py (public policy adapters, incl. disclosed-review-flag hold)
  - apps/backend-rag/backend/services/visa_engine/models.py (Decision state conditionals)
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/flow.ts (interview routing)
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts (OracleFacts → signed FactPaths, disclosed review flags)
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/tree.ts (53-question registry)
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.ts (missing-fact → question mapping)
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.tsx (NEEDS_INPUT rendering)
  - research/visa/doctrine-factory/claims/e2a-claim-ledger.md (CL-D2-01, CL-D12-05)
  - research/visa/2026-07-24-w2-factbase-e33.md (E33/E33E/E33F thresholds)
  - research/visa/doctrine-factory/e4/question-registry-audit.md (per-question REVIEW_ONLY dispositions)
  - scratchpad/inv/d1-tree/ (43 interview walks driven through the real flow.ts/fact-mapper.ts, NOT_ASKED matrix, per-walk wire payloads)
  - scratchpad/inv/d4/ (45 complete-fact personas, what-if folds wi-none/wi-e33g/wi-ext)
  - scratchpad/inv/d3-evalsem/ (evaluator semantics experiments exp1–exp7)
  - scratchpad/inv/synth/ (this synthesis: base.json, cure.json, wave.json, probe_wave.py, probe_flag.py)
adversarial_review: gemini-3.1-pro
---

# Visa Oracle — why the funnel almost never answers, and the one intervention that fixes it

> Six investigation seats + two adversarial skeptic passes, 2026-09-06, on `origin/main`
> `9a36edab26`…`e7a11cd633` (no Visa Oracle file changed between those two commits —
> `git diff --stat 9a36edab26 e7a11cd633 -- apps/mouth/src/app/'(visa-oracle)' apps/backend-rag/backend/services/visa_engine apps/backend-rag/backend/scripts/visa_engine` is empty, so every
> anchor below is current). Production is in ENFORCE on seq-19. Nothing in this document
> has been shipped; it is a spec plus the measurements that justify it.

---

## 1. Executive summary

1. The Visa Oracle is live, correct and almost never decisive: replaying the **43 real
   interview walks** through the signed seq-19 pack gives **36 NEEDS_INPUT / 7
   SUPPORTED_CANDIDATES / 0 NO_SUPPORTED_PATH** (`scratchpad/inv/synth/base.json`).
2. Every one of those 36 NEEDS_INPUT names a fact **the interview has no question for** —
   the user is asked to answer something the product cannot ask. It is fail-closed, so no
   wrong answer has shipped, but it is a dead end, not an answer.
3. On top of that, a frontend flag erases even the answers that DO exist: an
   ACTIVITY_BOUNDARY flag is attached to every `work` interview, and it turns a clean
   `SUPPORTED_CANDIDATES [E23]` into `HUMAN_REVIEW_REQUIRED` with zero candidates
   (`scratchpad/inv/synth/probe_flag.py`, measured this session).
4. Three layers cause this, and no single layer's fix is sufficient: (L1) the mapper's
   blunt review flag, (L2) unaskable facts crossed with an evaluator that blocks on
   products it could never recommend, (L3) pack content — stay-day caps frozen at the
   initial grant, and one review rule that is a byte-for-byte copy of its own SUPPORT rule.
5. The highest-leverage single change is a **12-line reorder inside `evaluator.py`**: test
   purpose-feasibility BEFORE blocking on a gate unknown. It cannot fail open (its only
   possible output is UNSUPPORTED) and it alone removes 27 of 43 dead ends.
6. Measured with that reorder alone: **13 NEEDS_INPUT / 23 NO_SUPPORTED_PATH / 7
   SUPPORTED** (`scratchpad/inv/synth/cure.json`). Honest, but not yet useful.
7. Measured with the reorder **plus** the four seq-20 pack edits: **24
   SUPPORTED_CANDIDATES / 11 NEEDS_INPUT / 8 NO_SUPPORTED_PATH**
   (`scratchpad/inv/synth/wave.json`). The 11 residual NEEDS_INPUT are all on facts a
   **+1-question** interview change can supply, and each one then resolves decisively
   (`probe_wave.py`).
8. Two proposals from the investigation are REFUTED and must not ship: deriving
   `process.wants_onshore_conversion = false` offshore, and emitting a KNOWN sentinel for
   `intent.requested_product_code`. Both were measured to produce a confident wrong
   recommendation (D12 and BRIDGING respectively). §6 records them so nobody re-tries them.
9. The intervention is one coordinated wave of 5 PRs in a fixed order: seq-20 fold and
   ceremony first, evaluator reorder second, interview questions third, flag narrowing
   fourth (it is unsafe before the fold), census gate fifth.
10. Six calls are yours, not the engine's — all in §5, all legal or product content
    (extension caps, D2 local-compensation doctrine, second-home routing, diaspora
    routing, ITAS-sponsor certification, work_role doctrine). Everything else is mechanical.

---

## 2. The three blocking layers as measured

### 2.0 What "the interview" is, exactly

`tree.ts` holds 53 questions (41 `FACT`, 11 `HUMAN_CONTEXT`, 1 `REVIEW_ONLY`; 52 of 53 carry
`notSure: {mode: "human-review"}`). `flow.ts`'s `computeNextNode` (flow.ts:455-568) is a
fixed two-arm spine — onshore and offshore — and then `getCategoryQuestionIds`
(flow.ts:613-714) picks a branch out of 10 categories, 3 of which sub-branch. That is 43
distinct walks. Nine questions are asked in all 43; branch-specific cost is 1-8 questions,
so the interview is ~70-90% identical for everyone
(`scratchpad/inv/d1-tree/questions.json`, `walk2.json`).

`fact-mapper.ts` emits 45 signed FactPaths on every call. The 109 seq-19 rules read 39
distinct paths. Nine emitted paths are read by **no rule at all**: `commercial.*` (2),
`family.sponsor_permit_basis`, `immigration.last_entry_date`, `immigration.renewal_paid`,
`intent.desired_entry_date`, `process.application_channel`, `work.employer_country_code`,
plus `person.birth_date` which is load-bearing only indirectly via `derived.age_years` (19
references in the pack). Four of those nine cost a real question in at least one branch.
Verified by grepping the signed payload: `renewal_paid`, `application_channel`,
`employer_country_code`, `sponsor_permit_basis`, `last_entry_date`, `desired_entry_date`,
`service_fee_budget`, `wants_quote` and `has_active_stay_permit` all return **0** matches.

### 2.1 Layer 1 — the frontend flag: `mapDisclosedReviewFlags` is a presence veto

`fact-mapper.ts:415-432` adds `ACTIVITY_BOUNDARY` if **any** of eleven raw answers is merely
`!== undefined`. It does not look at the value; it looks at whether the question was
answered:

```
facts.category === "diaspora" || facts.business_activity !== undefined ||
facts.work_role !== undefined || facts.tourism_duration !== undefined ||
facts.remote_income !== undefined || facts.diaspora_connection !== undefined ||
facts.diaspora_documents !== undefined || facts.other_purpose !== undefined ||
facts.other_paid_activity !== undefined || facts.retirement_basis === "property" ||
(facts.investment_vehicle !== undefined && facts.investment_vehicle !== "pt_pma") ||
facts.retirement_basis === "family_sponsor" || facts.retirement_basis === "undecided"
```

Backend side, any disclosed flag is terminal: `_apply_disclosed_review_flags`
(evaluate_path.py:1304-1341) rewrites the decision with `"candidates": ()` at
evaluate_path.py:1341, and `models.py:1416-1418` makes that structural — every state other
than `SUPPORTED_CANDIDATES` **forbids** a non-empty `candidates`, so a flagged decision
cannot carry the product it had already proven. Four other adapters do the same at
evaluate_path.py:1060, :1085, :1188, :1291.

Measured cost (mine, this session, `scratchpad/inv/synth/probe_flag.py`, offline against the
signed seq-19 pack):

```
offshore/work   flags=[]                    SUPPORTED_CANDIDATES  cand=E23
offshore/work   flags=['ACTIVITY_BOUNDARY'] HUMAN_REVIEW_REQUIRED cand=-  rv=['DISCLOSED_ACTIVITY_BOUNDARY_REVIEW']
```

This is not hypothetical for the `work` category: `work_role` is the fifth question of
`FIXED_CATEGORY_QUESTIONS.work` (flow.ts:578-585), so it is **always** answered, so the flag
is **always** set, so E23 — the one product seq-19 answers cleanly for an employment
interview — is **never** shown to anybody. And `work_role` is `decisionMapping: { kind:
"HUMAN_CONTEXT" }` (tree.ts:543-548): it maps to no FactPath at all. The rule that actually
supports E23, `el.e23-employment-support`, requires only `intent.purposes`,
`work.employer_is_indonesian_entity` and `work.indonesian_work_sponsor_confirmed` — no role.
(A second E23 rule, `el.e23-operational-work-boundary`, does read `investment.proposed_role`
— but that path is written from the invest branch's `investment_role` question,
fact-mapper.ts:623, never from `work_role`.) The question is engine-inert and its only live
effect is to suppress the answer.

The same mechanism, measured by the review-flags seat on the D2 gold persona
(`02_business_c2`, a German entrepreneur flying in for a week of meetings): baseline
`SUPPORTED_CANDIDATES [D1, D2]`; with `ACTIVITY_BOUNDARY`, `MULTI_PURPOSE_TRIP` or
`NOT_CERTAIN` — each alone — `HUMAN_REVIEW_REQUIRED`, 0 candidates. And `MULTI_PURPOSE_TRIP`
is attached by `fact-mapper.ts:411` to anyone who says their trip has more than one purpose.

Two of the eleven clauses are dead code: `facts.tourism_duration` and `facts.remote_income`
(fact-mapper.ts:419-420) name question ids that exist nowhere in `tree.ts`.

**The owner ruling "human review must almost never appear" is violated by construction
here**, and the fix is not "trust the LLM more" — it is to stop treating *the presence of an
answer* as evidence of danger.

### 2.2 Layer 2 — unaskable facts × evaluator ordering

Two independent defects that only bite together.

**(a) Facts the interview cannot supply.** Five paths are hardcoded `unknownFact(NOT_ASKED)`
in the mapper, pinned by `test_reachability_report.py:177-183`. The load-bearing one is
`"intent.requested_product_code": unknownFact(NOT_ASKED)` (fact-mapper.ts:596) — no question
in `tree.ts` can ever set it. Three more are unaskable by routing rather than by hardcoding:

| Fact                              | Why it is unaskable                                                                                                                                                                    |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `process.wants_onshore_conversion` | flow.ts:539-542 emits the question only when `facts.in_indonesia === "yes"`. Both offshore permit sub-branches (flow.ts:515-529) bypass it — including the D12 target population flow.ts:479-480 itself names, "someone abroad holding an unlapsed KITAS". |
| `sponsor.type`                     | its only source question `sponsor_category` (tree.ts:441-444 → fact-mapper.ts:496-500) is absent from `tourism`, `business`, `other`, `diaspora` in `FIXED_CATEGORY_QUESTIONS` (flow.ts:570-606). |
| `work.employer_is_indonesian_entity` | the `remote` sequence (flow.ts:586-593) never asks `work_payer`, the only input to `mapEmployerIsIndonesianEntity` (fact-mapper.ts:317-321).                                          |
| `family.sponsor_status_code`       | asked, but the mapper **deliberately** returns `unknownFact(UNVERIFIED)` for every answer (fact-mapper.ts:505-520): a self-declared status label must never satisfy `op: known`. It is a permanent wall by design. |

**(b) The evaluator asks on behalf of products it could never recommend.**
`evaluate_product` returns `BLOCKED_UNKNOWN` from a hard-filter/review unknown at
evaluator.py:663-676 — **before** the purpose-feasibility tests at evaluator.py:678 (`purposes
<= covered`) and evaluator.py:701-715 (`purposes <= naive_potential_coverage`). Then
evaluator.py:1424 picks `min(blocked, key=lambda proof: len(proof.missing_facts))`. Result: a
product whose SUPPORT rules can never cover the applicant's declared purposes still gets to
choose the question the applicant is asked.

Two clean instances, verified against the signed payload:

- **Nine products carry zero SUPPORT rules** — E23U, E23V, E28B, E28C, E28D, E28F, E33A,
  E33B, E33C. Each has exactly one `HUMAN_REVIEW / REQUIRE_REVIEW` rule requiring
  `intent.requested_product_code`, `on_unknown: NEEDS_INPUT`. They can never be candidates
  (`purposes <= covered` is unreachable when `covered` is always empty) and yet they produce
  a one-missing-fact blocked proof that wins the `min()` for everybody else.
- **E33A/B/C's `hf.e33{a,b,c}.sponsor-not-government*`** (HARD_FILTER / EXCLUDE /
  `safety_critical: true` / `on_unknown: NEEDS_INPUT`) are the sole cause of the
  `sponsor.type` dead end — on products that, having no eligibility rule, cannot be
  recommended under any sponsor value.
- **D12's `hf.d12-onshore-conversion-excluded`** (HARD_FILTER / EXCLUDE / `safety_critical:
  true` / `on_unknown: NEEDS_INPUT` / `required_facts: [process.wants_onshore_conversion]`)
  blocks every offshore interview, including tourism and retirement ones whose purposes
  D12's SUPPORT rules (all requiring `intent.purposes ∩ INVESTMENT`) can never cover.

Baseline census over the 43 interview walks (`scratchpad/inv/synth/base.json`, flags
stripped, signed seq-19):

| Blocking fact                                                  | Walks |
| -------------------------------------------------------------- | ----- |
| `process.wants_onshore_conversion`                              | 25    |
| `sponsor.type`                                                  | 5     |
| `intent.purposes` (diaspora)                                    | 2     |
| `investment.investment_capital_idr` + `paid_up_capital_idr`     | 2     |
| `family.sponsor_status_code`                                    | 1     |
| `intent.requested_product_code`                                 | 1     |
| **total NEEDS_INPUT**                                           | **36** |

Not one of these 36 is answerable. And it is worse than "the user must re-open a question":
`questionForFact` (engine-adapter.ts:642-655) offers an Edit only for a question present in
`editableQuestionIds`, which `OracleShell.tsx:644` and `:677` build from `state.history` —
the questions actually asked. `OutcomeSheet.tsx:508-527` therefore renders a missing-input
row with **no Edit button** and generic copy. The verdict-UX seat grepped the whole
`visa-oracle` route for any mechanism that turns a `missing_facts` entry into a NEW question
to ask: there are four non-test consumers of `missing_facts` (validation, mapping, shadow
telemetry, static render) and none of them is a follow-up loop. There is no follow-up loop.

### 2.3 Layer 3 — pack content

Four content defects in the signed pack itself, all measured offline.

**(L3-a) Stay-day caps encode the INITIAL GRANT, not the lawful total.** Twenty-three rules
carry an `intent.stay_days lte` bound; the caps are A1/B1 30, C1/C2/C6/D1/D2 60, D12 180.
Those are the first-grant numbers, not the extendable totals. Consequence, measured on the
45 complete-fact personas (`scratchpad/inv/d4/wi-none.txt` vs `wi-ext.txt`): raising seven
caps to the product's own lawful total moves exactly six rows, five of them from
`NO_SUPPORTED_PATH` to `SUPPORTED_CANDIDATES` — including the owner's own persona shape
(#14, 121-day multi-entry business) which goes from "no path" to `[C2, D1, D2]`. Nothing is
weakened: every flipped persona already satisfied all the product's other conditions.

**(L3-b) `review.e33g.income-evidence` is a byte-for-byte copy of `el.e33g.remote-work`.**
Both rules' `when` is the identical four-clause `all(purposes ∩ REMOTE_WORK,
employer_is_indonesian_entity == false, serves_indonesian_clients == false,
indonesia_source_compensation == false)`. So every applicant the SUPPORT rule qualifies is
simultaneously sent to human review, and REVIEW beats SUPPORTED at evaluator.py:1397-1402.
E33G — the only REMOTE_WORK product in the pack — can therefore **never** be recommended.
Dropping that one rule flips exactly two of 45 personas and nothing else
(`scratchpad/inv/d4/wi-e33g.txt`).

**(L3-c) The `family.sponsor_status_code` rules block on a fact the mapper refuses to
certify.** Eight rules read it with `on_unknown: NEEDS_INPUT` while fact-mapper.ts:505-520
guarantees it is always UNKNOWN. Products E31B/E31E/E31H/E31J are therefore unreachable from
the funnel — and they take the whole decision down with them.

**(L3-d) BRIDGING grants support on an unstated request.** Four rules
(`el.bridging.destination-stated`, `.t3-window-manual`, `.overstay-shield-payment`,
`.source-status-verify`) are `effect.type: SUPPORT` guarded on `intent.requested_product_code
neq BRIDGING`. Because `neq` is TRUE for any value other than the literal `"BRIDGING"`, any
KNOWN value would manufacture support with reason `BRIDGING_DESTINATION_STATED` — a claim
that a destination product was named, when none was. Today the fact is permanently UNKNOWN
so the rule is UNKNOWN and no support is granted; the latent hazard is why §6 refutes the
sentinel proposal.

**Two products are unreachable for reasons that live in the funnel, not the pack.** E33
(Second Home) has working rules — a complete-fact persona with `purposes = [SECOND_HOME]`
and USD 1.2M qualifying property returns `SUPPORTED_CANDIDATES [E33]`
(`scratchpad/inv/d4/d4-results.json` #39/#40) — but `CATEGORY_TO_PURPOSE`
(fact-mapper.ts:255-266) has no entry that emits `SECOND_HOME`, so no interview can ever
reach it. E31D is unreachable because `flow.ts:697-704` branches on
`family_relation === "STEPCHILD"` while `tree.ts:743-762` offers only SPOUSE / CHILD /
PARENT / SIBLING / DEPENDENT / OTHER — grep for `STEPCHILD` in `tree.ts` returns nothing.
Diaspora is in the same family: `CATEGORY_TO_PURPOSE` deliberately omits `diaspora`
(fact-mapper.ts:265, "Diaspora is intentionally represented only by request_category"), so
`mapPurposes` returns `unknownFact(NOT_APPLICABLE)` and the branch dead-ends on
`intent.purposes`.

---

## 3. Persona decisiveness table and the legally suspicious outcomes

45 complete-fact personas (every rule-read fact KNOWN with a neutral non-matching value, so
no NEEDS_INPUT can be an artifact of a gap), evaluated offline against
`rulepack-prod-019.signed.json` through the same `verify → compile → evaluate →
apply_public_policy_adapters` path the two committed gates use
(`scratchpad/inv/d4/run_personas.py`, `d4-results.json`, `wi-none.txt`).

**Totals: 25 SUPPORTED_CANDIDATES · 10 NO_SUPPORTED_PATH · 9 HUMAN_REVIEW_REQUIRED · 1
NEEDS_INPUT.**

| #   | Persona                                                        | State           | Candidates / reason               | Verdict                     |
| --- | -------------------------------------------------------------- | --------------- | --------------------------------- | --------------------------- |
| 01  | DE tourist 21d single offshore                                  | SUPPORTED       | B1, C1                            | correct                     |
| 02  | DE tourist 30d single offshore                                  | SUPPORTED       | B1, C1                            | correct                     |
| 03  | DE tourist 45d single offshore                                  | SUPPORTED       | C1                                | correct                     |
| 04  | DE tourist 75d single offshore                                  | NO_PATH         | —                                 | **L3-a defect**             |
| 05  | DE tourist 150d single offshore                                 | NO_PATH         | —                                 | **L3-a defect**             |
| 06  | TH tourist 30d (BVK + VOA nationality)                          | SUPPORTED       | A1, B1, C1                        | correct                     |
| 07  | PK tourist 30d (neither BVK nor VOA)                            | SUPPORTED       | C1                                | correct                     |
| 08  | NG tourist 30d (calling-visa nationality)                       | REVIEW          | CALLING_VISA_REVIEW               | correct law                 |
| 09  | TH transit 3d                                                   | SUPPORTED       | A1                                | correct                     |
| 10  | US business meetings 30d single, no local sponsor               | SUPPORTED       | D2                                | correct                     |
| 11  | US business meetings 30d single, sponsor confirmed              | SUPPORTED       | C2, D2                            | correct                     |
| 12  | US business meetings 60d single, sponsor confirmed              | SUPPORTED       | C2, D2                            | correct                     |
| 13  | US business meetings 60d MULTI, sponsor confirmed               | SUPPORTED       | C2, D1, D2                        | correct                     |
| 14  | IT business meetings 121d MULTI, sponsor confirmed (owner shape) | NO_PATH        | —                                 | **L3-a defect**             |
| 15  | IT business meetings 121d SINGLE, sponsor confirmed             | NO_PATH         | —                                 | **L3-a defect**             |
| 16  | IT business meetings 90d MULTI, sponsor confirmed               | NO_PATH         | —                                 | **L3-a defect**             |
| 17  | AU remote worker 180d, foreign employer, clean                  | REVIEW          | E33G_INCOME_EVIDENCE_REVIEW       | **L3-b mask**               |
| 18  | AU remote worker 365d + tourism, clean foreign income           | REVIEW          | E33G_INCOME_EVIDENCE_REVIEW       | **L3-b mask**               |
| 19  | AU remote worker serving Indonesian clients                     | REVIEW          | LOCAL_MARKET_ACTIVITY_REVIEW      | correct law                 |
| 20  | AU remote worker employed by an Indonesian entity               | NO_PATH         | —                                 | **purpose silo** (see below) |
| 21  | GB spouse of WNI, marriage registered, sponsor confirmed        | SUPPORTED       | E31A                              | correct                     |
| 22  | GB spouse of WNI, marriage NOT registered                       | NO_PATH         | —                                 | correct law                 |
| 23  | NL spouse of an E23 ITAS holder, marriage registered            | SUPPORTED       | E31B                              | correct (unreachable, L3-c) |
| 24  | US minor child (10) of an Indonesian parent, guardian confirmed | REVIEW          | MINOR_GUARDIAN_PRIVACY_REVIEW     | by design                   |
| 25  | US adult child (25) of an Indonesian parent                     | SUPPORTED       | E31C, E31F                        | correct                     |
| 26  | FR parent (68) of an adult Indonesian child                     | SUPPORTED       | E31G                              | correct                     |
| 27  | IN undergraduate, admission + sponsor confirmed                 | SUPPORTED       | E30, E30B, E30E, E30F             | correct                     |
| 28  | KR secondary pupil (15), admission + sponsor confirmed          | REVIEW          | MINOR_GUARDIAN_PRIVACY_REVIEW     | by design                   |
| 29  | JP postgraduate researcher, admission + sponsor confirmed       | SUPPORTED       | E30, E30E, E30F                   | correct                     |
| 30  | SG investor AT threshold (PT PMA, director, 2.5B / 10B)         | SUPPORTED       | E28A                              | correct                     |
| 31  | SG investor 1 IDR BELOW the paid-up minimum                     | **NEEDS_INPUT** | `intent.requested_product_code`   | **L2 dead end**             |
| 32  | SG pre-investment scouting trip, 60d, no PT PMA yet             | SUPPORTED       | D12                               | correct                     |
| 33  | SG investor at threshold, wants ONSHORE conversion              | SUPPORTED       | E28A                              | correct                     |
| 34  | IT retiree 57, USD50k state-bank deposit, USD3k/mo              | SUPPORTED       | E33E                              | correct                     |
| 35  | IT retiree 62, USD50k deposit, USD3k/mo                         | SUPPORTED       | E33E                              | correct                     |
| 36  | IT retiree 62, USD3k/mo passive, agency sponsor, no deposit     | SUPPORTED       | E33F                              | correct                     |
| 37  | IT retiree 62, USD2k/mo passive, no deposit, no sponsor         | NO_PATH         | —                                 | correct law                 |
| 38  | IT retiree 52 (below 55), USD50k deposit, USD3k/mo              | NO_PATH         | —                                 | correct law                 |
| 39  | RU second home, USD130k state-bank deposit, own name            | SUPPORTED       | E33                               | correct (unreachable)       |
| 40  | RU second home, USD1.2M qualifying property                     | SUPPORTED       | E33                               | correct (unreachable)       |
| 41  | RU second home, USD100k deposit (below threshold)               | NO_PATH         | —                                 | correct law                 |
| 42  | US-passport diaspora, Indonesian mother                         | SUPPORTED       | E31C, E31F                        | correct (unreachable)       |
| 43  | Dual US + ID national returning to Bali                         | REVIEW          | CITIZENSHIP_LIST_DIVERGENCE       | correct law                 |
| 44  | DE minor tourist (12) with a confirmed guardian                 | REVIEW          | MINOR_GUARDIAN_PRIVACY_REVIEW     | by design                   |
| 45  | DE minor tourist (16) with no confirmed guardian                | REVIEW          | MINOR_WITHOUT_CONFIRMED_GUARDIAN  | by design                   |

### 3.1 Legally suspicious outcomes

- **#04, #05, #14, #15, #16 — the extension cap.** Five personas are told "no path" for a
  stay length Indonesian practice grants by extension. The caps are traceable to the
  first-grant number, not to a claim that longer stays are illegal. **This is the single
  biggest content defect and it needs Zero's ruling** (§5, decision 1).
- **#17, #18 — E33G is unreachable.** The remote-work visa exists in the pack, the rules
  qualify the applicant, and a duplicate review rule vetoes it. No legal content supports
  the veto; the rule's own `when` is a copy of the SUPPORT rule's.
- **#20 — purpose silo.** A remote worker employed by an Indonesian entity is correctly
  refused E33G, and is then told "no path" — although the pack contains E23, the exact
  product for someone employed by an Indonesian entity. `mapPurposes` (fact-mapper.ts:304-310)
  emits exactly one purpose from the chosen category, so an applicant who picked `remote`
  can never be evaluated against `EMPLOYMENT` products. That is a routing gap, not a legal
  one: the honest verdict is "not E33G — you need a work permit route", which the current
  vocabulary cannot express.
- **#31 — one rupiah below the threshold.** The correct answer is "E28A is out, here is what
  is left". The engine instead asks an unanswerable question, because the nine zero-SUPPORT
  products win the `min()` tie-break.
- **#23, #39, #40, #42 — right answers nobody can get.** E31B, E33 and the diaspora route
  all work when the facts arrive; the funnel cannot produce those facts.
- **#37, #38, #41, #22 — correct and staying.** USD3,000/mo (research/visa/2026-07-24-w2-factbase-e33.md:114
  pins it verbatim and marks USD1,500 superseded), age 55 (Pasal 62 jo. Permenkumham
  11/2024), USD130k second-home deposit, and the unregistered-marriage spouse. Do not touch.
- **#24, #28, #44, #45 — the minor-guardian privacy hold** is a deliberate PII decision
  (`_apply_minor_privacy_hold`, evaluate_path.py:1033-1085) and stays. It is 4 of the 9
  reviews and the main reason "human review" will never be literally zero.

---

## 4. THE SINGLE INTERVENTION

One coordinated wave, five PRs, fixed order. The order is forced by two dependencies:
**(1)** narrowing the ACTIVITY_BOUNDARY flag is a fail-open until the pack encodes the D2
local-compensation prohibition, so the fold must land first; **(2)** the evaluator reorder
changes 27 of 43 walk outcomes, so the walk-census gate must exist before it, not after.

Every PR follows the builder contract: one concern, dedicated worktree on
`agent/<host>/<lane>/…`, auto-merge armed at open, `Bites:` line naming the consumer.
PR-1 and PR-2 both touch `apps/backend-rag`, so they serialize (and merging
`apps/backend-rag/**` **is** the deploy).

### PR-0 — the census gate (land first, pins today's numbers)

**Title:** `test(visa): pin the interview-walk decisiveness census — 36 of 43 walks dead-end today`

**Files**

- new `apps/backend-rag/backend/tests/services/visa_engine/test_interview_walk_census.py`
- new corpus `apps/backend-rag/backend/tests/services/visa_engine/gold_coverage/walks/*.json`
  (43 files, the wire payloads already produced at `scratchpad/inv/d1-tree/personas/`)

**Exact change.** Replay all 43 interview-shaped payloads against the highest-sequence
signed pack on disk and assert the exact state census, plus one invariant that is the whole
point of the wave:

> no walk may end in `NEEDS_INPUT` on a fact for which `tree.ts` has no question reachable
> in that walk's own history.

Today that invariant fails 36 times, so it ships as an **explicit allowlist of the 36 known
dead ends**, and every subsequent PR in the wave deletes rows from the allowlist. When the
allowlist is empty the assertion becomes the permanent antibody.

**Tests.** Guilt: mutate the corpus (e.g. force `sponsor.type` KNOWN in one walk) → the
census assertion fires. Innocence: on unmodified `origin/main` the file is green.

**Size.** ~180 lines of test + 43 small fixtures (generated, not hand-written).

**Risk to zero-wrong-answers.** None — test-only.

**Prove-live.** `pytest backend/tests/services/visa_engine/test_interview_walk_census.py` green on main, and
the allowlist length printed in the PR body.

### PR-1 — seq-20 fold: content fixes + sign + activate

**Title:** `feat(visa-engine): fold seq-20 — lawful stay-day totals, E33G unmasked, unaskable gates made NO_EFFECT`

**Files**

- new `apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq20.py` (same shape as
  `fold_pack_seq19.py`, which chains from the current signed anchor and edits only named
  rule ids)
- new `apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-020.source.json`
- new `…/packs/rulepack-prod-020.signed.json` (produced by the ceremony below)
- new `apps/backend-rag/backend/tests/services/visa_engine/test_seq20_pack.py`
- `research/visa/doctrine-factory/claims/e2a-claim-ledger.md` (the new D2 claim's `Backs:` line)

**Exact change — five edits, by rule id.**

1. **Extension caps (owner decision 1).** Raise the `intent.stay_days lte` bound on the
   seven support rules that gate the visit-visa family: `el.b1.tourism` 30 → 60,
   `el.c1.tourism-family` 60 → 180, `el.c2.business` 60 → 180, `el.c6.social` 60 → 180,
   `el.d1-multi-entry-support` 60 → 180, `el.d2-multi-entry-support` 60 → 180,
   `el.d12-multi-entry-support` 180 → 360. **Note the trap:** the D1/D2/D12 document-requirement
   siblings (`*-passport-validity`, `*-funds-usd-*`, `*-cv-required`, `*-itinerary-required`,
   `*-support-letter`, 16 rules total) carry the SAME old bound. They do not block support —
   `hit_policy.eligibility = COVER_ALL_DECLARED_PURPOSES` only needs the covering rule — but
   leaving them at 60 silently drops the document checklist for a 121-day applicant. Bump all
   23 rules together, or the fold ships an inconsistent pack.
2. **`review.e33g.income-evidence` — retire it.** Its `when` is byte-identical to
   `el.e33g.remote-work`'s, so it is an unconditional veto on the product's own success
   condition. If income evidence genuinely needs a human, it must be a rule with a
   DISCRIMINATING condition (e.g. income below a stated floor), not a copy.
3. **The eight `family.sponsor_status_code` rules — `on_unknown: NEEDS_INPUT` → `NO_EFFECT`.**
   The fact can never be KNOWN from the browser (fact-mapper.ts:505-520 by design), so
   `NEEDS_INPUT` is a request the funnel cannot honour. `NO_EFFECT` is fail-closed: the rule
   simply does not fire, E31B/E31E/E31H/E31J stay out of the candidate set, and the rest of
   the decision proceeds. This does not lose a candidate — those four products are already
   unreachable from the funnel.
4. **The four BRIDGING rules — conjoin `known`.** Rewrite each `when` as
   `all(<existing>, {"fact": "intent.requested_product_code", "op": "known"})` on
   `el.bridging.destination-stated`, `el.bridging.t3-window-manual`,
   `el.bridging.overstay-shield-payment`, `el.bridging.source-status-verify`. This makes the
   premise explicit — support may not be granted on an unstated destination — and it is the
   precondition that makes any future frontend change to that fact safe (§6).
5. **New rule `hf.d2.indonesia-source-compensation` (owner decision 2).** Nothing in seq-19
   compiles CL-D2-01's "absolute prohibition on subordinate employment or local
   compensation" (e2a-claim-ledger.md:99-107); the ledger's own `Backs:` line names only
   `el.d2-multi-entry-support`, which reads `intent.purposes` and `intent.stay_days` and
   nothing else. Measured consequence today: BUSINESS_MEETINGS + 60d +
   `work.indonesia_source_compensation = true` returns `SUPPORTED_CANDIDATES [D2]` with no
   review. Proposed condition, scoped to D1/D2/C2:
   `all({"fact":"intent.purposes","op":"intersects","values":["BUSINESS_MEETINGS"]}, {"fact":"work.indonesia_source_compensation","op":"eq","value":true})`
   → `EXCLUDE`, reason `BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED`, `on_unknown: NEEDS_INPUT`,
   `safety_critical: true`. The fact is asked in the business branch
   (`work_indonesia_compensation`, flow.ts:572-577), so `NEEDS_INPUT` cannot dead-end that
   branch. **This rule is the precondition for PR-3.**

**Ceremony (offline, operator).** The signing key is off-limits to this session; the steps
are, in order, exactly as seq-19 ran them:

```
# 1. fold
PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq20 --out <source.json>
# 2. sign (offline only; key must be chmod 0600)
PYTHONPATH=. python -m backend.scripts.visa_engine.sign_pack <source.json> \
  --kid <kid> --key-file <pem> --environment PRODUCTION --sequence 20 \
  --output <signed.json> --i-know-this-is-production
# 3. dry-run activation (default is a dry run that only verifies)
PYTHONPATH=. python -m backend.scripts.visa_engine.activate_pack <signed.json> \
  --actor <actor> --reason seq20-decisiveness --current-sequence 19 \
  --current-payload-sha256 bac5da8e…e6ea
# 4. execute
… same command … --yes
```

`activate_pack` takes `--current-sequence` and `--current-payload-sha256` precisely so a
concurrent activation cannot be clobbered; pass the seq-19 values verbatim.

**Tests.** Guilt: `test_seq20_pack.py` pins each of the five edits by rule id and asserts the
45-persona census moves 25/10/9/1 → 32/5/7/1 (`wi-ext.txt` + `wi-e33g.txt`, composed).
Innocence: `test_seq19_signed_bundle.py` and the whole `gold_coverage` floor stay green;
`gold_coverage_replay` must remain 18/18.

**Size.** Fold script ~350 lines (mostly docstring, per house style), test ~250, generated
pack JSON not counted as review surface.

**Risk to zero-wrong-answers.** Edits 2, 3, 4 are strictly fail-closed or neutral. Edit 5
strictly narrows. Edit 1 is the only one that can produce a NEW recommendation, and it is a
legal claim — hence owner decision 1. **Do not activate seq-20 with edit 1 unless Zero has
ruled on the caps.**

**Prove-live.** `probe_evaluate.py --traffic-source synthetic_driver` returns
`rule_pack.sequence = 20` and, for the 121-day business persona, `SUPPORTED_CANDIDATES`
containing `D2`.

### PR-2 — evaluator: purpose-feasibility BEFORE gate-unknown blocking

**Title:** `fix(visa-engine): a product that can never cover the declared purposes must not choose the question`

**Files**

- `apps/backend-rag/backend/services/visa_engine/evaluator.py` (evaluate_product, the block at
  :663-676 and the feasibility test at :701-715)
- `apps/backend-rag/backend/tests/services/visa_engine/test_seq9_new_rule_witnesses.py` (5 pinned mechanisms)
- `apps/backend-rag/backend/tests/services/visa_engine/test_seq19_pack.py` (gold baseline 5/20 → 6/20)
- the PR-0 allowlist (delete 27 rows)

**Exact change.** Hoist the `naive_potential_coverage` UNSUPPORTED return so it runs
immediately after `support_review_unknowns, support_input_unknowns =
_partition_unknowns_by_policy(support_safety)` (evaluator.py:661) and **before**
`if hard_input_unknowns or review_input_unknowns:` (evaluator.py:663):

```
    if not (purposes <= naive_potential_coverage):
        return finish(ProductProof(product=product,
                                   status=ProductProofStatus.UNSUPPORTED,
                                   missing_purposes=purposes - naive_potential_coverage),
                      applied_rule_ids=frozenset(rule.rule_id for rule, _ in true_support))
```

Everything the predicate reads — `covered` (:653-659), `support_safety` (:660), `purposes` —
is already computed above the block it moves past, so this is a reorder, not a new
computation. Delete the now-duplicated copy at :701-715.

**Why this cure and not the alternatives.** Three cures were measured
(`scratchpad/inv/d3-evalsem/`):

| Cure                                                   | Can it fail open?                                                                                                 | Cost                                            |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **(a) evaluator reorder — CHOSEN**                     | No. Its only possible output is `UNSUPPORTED`; it can never produce `SUPPORTED` or silence an EXCLUDE.             | 12 lines, one file, 6 test updates              |
| (b) scope every gate rule with an `intent.purposes` guard | No, but it edits 14 signed legal claims and cannot fix E33A/B/C at all (they have no eligibility rule to guard on) | a seq-20 rewrite of 14 rules + re-sign          |
| (c) neutral defaults in the mapper                     | **Yes.** Measured: it flips three HARD_FILTER rules UNKNOWN→TRUE (manufacturing three exclusion reason codes as if they were legal findings) and two UNKNOWN→FALSE (silencing real gates). Invisible to the engine's entire test suite. | rejected |

**Measured effect (mine, this session).** 43 interview walks, signed seq-19, flags stripped:

```
BASELINE  NEEDS_INPUT 36  SUPPORTED 7   NO_SUPPORTED_PATH 0
CURE (a)  NEEDS_INPUT 13  SUPPORTED 7   NO_SUPPORTED_PATH 23
```

(`scratchpad/inv/synth/base.json` vs `cure.json`.) All five `sponsor.type` dead ends and the
`intent.requested_product_code` dead end disappear outright — nobody has to add a question
for them. The `SUPPORTED` set is byte-identical: the cure never created a candidate.

Independently, the evaluator-semantics seat ran the backend suite either side of the same
patch: baseline `1 failed, 1789 passed`; cure `7 failed, 1783 passed`. The six new failures
are 5 mechanism pins in `test_seq9_new_rule_witnesses.py` (each test's own stated SAFETY
assertion, `is not EXCLUDED` / `is not REVIEW`, still passes — only the incidental
`BLOCKED_UNKNOWN` shape changed) plus the seq-19 gold baseline improving from 5/20 to 6/20
matching. All 20 canonical gold personas keep an IDENTICAL `DecisionState`.

**Tests.** Guilt: a new witness asserting that a product with zero SUPPORT rules
(e.g. E33A) yields `UNSUPPORTED`, not `BLOCKED_UNKNOWN`, for a TOURISM applicant, and that
the whole decision is no longer `NEEDS_INPUT: sponsor.type`. Innocence: `test_evaluator_gold`,
`test_evaluator_purpose_coverage`, `test_evaluator_state_precedence`,
`test_ast_no_short_circuit` and the 18-persona coverage floor all stay green.

**Size.** ~12 net lines in `evaluator.py`, ~120 in tests.

**Risk to zero-wrong-answers.** The lowest of the three cures, and structurally so: the only
new return is `UNSUPPORTED`. The behavioural change users see is `NEEDS_INPUT` → the honest
`NO_SUPPORTED_PATH`, never `NEEDS_INPUT` → `SUPPORTED`.

**Prove-live.** `probe_evaluate.py` with a synthetic offshore TOURISM persona at 121 days:
before, `NEEDS_INPUT missing=[process.wants_onshore_conversion]`; after PR-1 + PR-2,
`SUPPORTED_CANDIDATES` containing `C1`.

### PR-3 — mouth: the four missing questions and the NEEDS_INPUT follow-up loop

**Title:** `fix(visa-oracle): ask the four facts the engine still needs, and follow up instead of dead-ending`

**Files**

- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/flow.ts` (`FIXED_CATEGORY_QUESTIONS`
  :570-606, `getCategoryQuestionIds` :613-714)
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts` (`CATEGORY_TO_PURPOSE` :255-266)
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.tsx` (:644, :677)
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.ts` (`questionForFact` :642-655)
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/tree.ts` (STEPCHILD option)
- `…/_lib/fact-mapper.test.ts` (:396-427 — the pinned "design choice" block), `…/_lib/flow.test.ts` (:78-176 CATEGORY_CASES)

**Exact change — four questions, one loop, one option.**

1. **`wants_onshore_conversion` in the offshore invest branch.** After PR-2, the ONLY walks
   still blocked on it are the six `offshore/invest/*` ones (`cure.json`) — D12 is
   purpose-feasible for them and for nobody else. Add `"wants_onshore_conversion"` to
   `getCategoryQuestionIds`'s invest branch, gated on `facts.in_indonesia === "no"` (onshore
   already asks it in the spine, flow.ts:539-542). **+1 question on 6 branches, offshore
   only.** Measured payoff (`probe_wave.py`): with the answer supplied, invest/pt_pma returns
   `SUPPORTED_CANDIDATES [D12]` on `false` and `NO_SUPPORTED_PATH` on `true` — decisive both
   ways. **Do NOT derive this fact** (§6).
2. **`family_sponsor_confirmed` in the invest and other branches.** After PR-1 + PR-2 this
   becomes the new #1 blocker (8 of 43 walks in `wave.json`), because `el.c2.business`
   (covers BUSINESS_MEETINGS + INVESTMENT) and `el.c6.social` (covers OTHER) both require
   `family.sponsor_confirmed == true`. The question already exists and is already asked in
   family and retirement. **+1 question on 2 categories.** Measured: invest + confirmed=true
   → `SUPPORTED [C2]`; other + confirmed=true → `SUPPORTED [C6]`, false → `NO_SUPPORTED_PATH`.
3. **`work_payer` in the remote branch.** It is the only input to
   `work.employer_is_indonesian_entity` (fact-mapper.ts:317-321) and
   `hf.e33g.indonesian-employer` is `on_unknown: NEEDS_INPUT`. **+1 question on 1 branch.**
   Measured: `true` → `NO_SUPPORTED_PATH` (correct — an Indonesian employer is barred from
   E33G); `false` → the E33G route proceeds. Do **not** derive it from
   `work.employer_country_code` (which the remote branch already collects and which no rule
   reads): "employer's country is not ID" does not entail "employer is not an Indonesian
   entity" for an ID-registered branch of a foreign group.
4. **`diaspora` purpose mapping (owner decision 4).** `CATEGORY_TO_PURPOSE` has no
   `diaspora` entry, so `mapPurposes` returns `NOT_APPLICABLE` and both diaspora walks
   dead-end on `intent.purposes` — before AND after every other fix in this wave. Recommended
   default: map `diaspora → "FAMILY"` and append the family branch's questions, since the
   products a diaspora applicant actually reaches are E31C/E31F (persona #42). Measured:
   with `purposes = [FAMILY]` the diaspora walk returns `SUPPORTED_CANDIDATES [C1]` even
   before the family questions are added.
5. **STEPCHILD.** `flow.ts:697-704` already branches on it; `tree.ts:743-762` never offers
   it. Add the option and its two i18n labels, or delete the dead branch. One line either way.
6. **The follow-up loop.** Today `OutcomeSheet.tsx:508-527` renders a missing-fact row with
   an Edit button only if `questionForFact` found the question **in the interview history**
   (engine-adapter.ts:642-655 + OracleShell.tsx:644/:677). When the engine names a fact whose
   question exists in `QUESTIONS` but was never asked in this walk, the correct behaviour is
   to **ask it** — append the node to the interview and re-evaluate — not to render an
   unanswerable row. Change: widen `questionForFact`'s candidate set from
   `editableQuestionIds` to `QUESTIONS` when the state is `NEEDS_INPUT`, and have
   `OracleShell` push that question onto the flow instead of rendering a row. Keep the
   ambiguity rule (`matches.length === 1`) — an ambiguous fact still falls back to the
   handoff. This is the structural antibody: after it, a newly-added rule requiring an
   already-modelled fact self-heals instead of dead-ending.

**Tests.** Guilt: per-branch flow tests asserting each new question appears exactly once, in
the right position, only in the intended branch; an `OracleShell` test asserting a
`NEEDS_INPUT` on a not-yet-asked-but-modelled fact ADVANCES the interview rather than
rendering a dead row. Innocence: `fact-mapper.test.ts:396-427` must be REVISED, not deleted
— it encodes a documented design choice ("the categories where the sponsor discriminates")
and its comment explicitly says it "breaks if a branch's question list changes without this
describe block being revisited"; `flow.test.ts:78-176` CATEGORY_CASES fixtures likewise.

**Size.** ~120 net lines across flow/mapper/shell/adapter + ~200 test lines.

**Risk to zero-wrong-answers.** Low but not nil: every `tree.ts` question carries
`notSure: {mode: "human-review"}` and any `"unsure"` answer adds `NOT_CERTAIN`
(fact-mapper.ts:410), so each added question is one more roll of an existing die into human
review. Net effect is still strongly negative on review volume, because PR-4 removes the
unconditional flags.

**Prove-live.** Browser walk: offshore → invest → PT PMA → …answer the new question… →
verdict page shows a candidate, not a question list.

### PR-4 — mouth: narrow the disclosed-review flags to what is actually undecidable

**Title:** `fix(visa-oracle): stop vetoing a proven answer because a question was answered`

**Files**

- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts` (:415-432)
- `…/_lib/fact-mapper.test.ts` (:176-195 pins four of the exact (id, answer) pairs)
- `…/_lib/i18n.ts` (:206, :212-213 — the user-facing promise about human review)

**Exact change — remove three clauses, keep the rest, in this order.**

- **Free now, no dependency:** delete `facts.tourism_duration !== undefined` and
  `facts.remote_income !== undefined` (fact-mapper.ts:419-420). Both name question ids that
  do not exist in `tree.ts`; the clauses are unreachable.
- **After PR-1 edit 5 only:** delete `facts.business_activity !== undefined`. Until the D2
  local-compensation prohibition is compiled, this flag is the ONLY thing preventing a
  confident D2 recommendation to an applicant who declared local compensation. With the rule
  in place, the engine handles it and the blanket flag is pure noise. **Keep flagging the
  `training` and `other` values** — CL-D12-05 (e2a-claim-ledger.md:203-210) puts site
  scouting under D12 and states no `activity.*` fact discriminates it, so a value-level
  allowlist (`meetings`, `negotiation`, `conference` unflagged) is the honest shape, not a
  wholesale removal.
- **Owner decision 6:** delete `facts.work_role !== undefined`. `work_role` is
  `HUMAN_CONTEXT` (tree.ts:543-548), engine-inert, and its flag currently suppresses E23 for
  100% of employment interviews. `question-registry-audit.md` §3 prescribes REVIEW_ONLY
  pending E23/E31 role doctrine, so removing it overrules a written audit disposition —
  Zero's call, not the session's.
- **Keep, unchanged:** `category === "diaspora"`, `diaspora_connection`,
  `diaspora_documents`, `other_purpose`, `other_paid_activity`,
  `retirement_basis ∈ {property, family_sponsor, undecided}`, and
  `investment_vehicle !== "pt_pma"`. These guard routes that are genuinely undecidable today
  (second home unreachable, diaspora unmapped) — §6 records the measurement showing that
  unflagging them turns a correct "hold for a human" into a confidently wrong "no path".

**Tests.** Guilt: assert the exact flag set for each of the 43 walks (a table, not a
predicate) so any future clause change is visible in review. Innocence: the four pinned
(id, answer) pairs in `fact-mapper.test.ts:176-195` must be re-stated, and the i18n copy at
i18n.ts:206/212-213 promising a human reviewer must be updated in the SAME diff — it is a
user-facing promise about what happens to that answer.

**Size.** ~15 net lines in the mapper, ~150 in tests, ~10 in i18n.

**Risk to zero-wrong-answers.** This is the only PR in the wave that removes a guard, hence
the strict ordering. Shipped before PR-1 edit 5, it is a fail-open; shipped after, it is a
noise reduction.

**Prove-live.** Browser walk: offshore → work → …complete… → the verdict shows `E23`, not
"a specialist will review". Then a prod probe with the same synthetic facts and NO disclosed
flags returning `SUPPORTED_CANDIDATES [E23]`.

### PR-5 — gold personas and the CI gates

**Title:** `test(visa): retire the dead-end expectations the wave fixed, and pin the new floor`

**Files**

- `apps/backend-rag/backend/tests/services/visa_engine/test_evaluator_gold.py` (20 canonical personas)
- `…/gold_coverage/personas/` (18 coverage personas) and `…/gold_coverage/walks/` (PR-0's 43)
- `…/test_gold_replay_artifact.py`, `…/test_gold_coverage_floor.py`
- `…/test_reachability_report.py` (:177-183 NOT_ASKED census — only if PR-3 changes the five)
- the PR-0 allowlist (delete the remaining rows)

**Exact change.** Three gates move, and each move must be justified in the PR body by a
persona, not by a number:

1. The 20-persona gold replay currently matches 5/20 with a pinned floor of "matches ≥ 4,
   unexplained ≤ 16". After the wave the census changes; re-derive the expectations from the
   personas' own legal descriptions, not from the new output (generator is never grader).
2. `gold_coverage_replay` must stay 18/18 throughout — it is the "every corpus persona is
   supported for its own product" floor and it is the one gate that would catch a fail-open.
3. Add the four new coverage personas the wave makes reachable: E33G (remote, clean foreign
   income), E33 (second home) if owner decision 3 goes ahead, E31D (stepchild), and the
   121-day multi-entry business case.

**Tests.** Guilt: each retired expectation is replaced by a NAMED persona with a legal
citation, not by loosening a threshold. Innocence: `test_gold_replay_artifact.py`'s
determinism assertions (byte-identical artifacts across two runs) stay green.

**Size.** ~300 lines, mostly fixture data.

**Risk to zero-wrong-answers.** Indirect but real — this is the PR where a fail-open would
be laundered into "expected". Every changed expectation gets a source citation.

**Prove-live.** `gold_coverage_replay` 18/18 (now 22/22) and the walk-census allowlist at
length 0.

### Ship order, restated

```
PR-0 census gate            (test-only; land first so the wave's effect is measured, not asserted)
PR-1 seq-20 fold + ceremony (backend; merging apps/backend-rag/** IS the deploy)
PR-2 evaluator reorder      (backend; serializes behind PR-1)
PR-3 mouth questions + loop (frontend)
PR-4 mouth flag narrowing   (frontend; UNSAFE before PR-1 edit 5)
PR-5 gold + gates           (test)
```

---

## 5. Owner decision list

Six calls. Everything else in §4 is mechanical and needs no ruling.

1. **Stay-day caps — do we encode the lawful extendable total instead of the initial
   grant?** (B1 30→60, C1/C2/C6/D1/D2 60→180, D12 180→360.) _Recommended default: YES._ It is
   the single biggest content defect — it produces five "no path" answers to applicants who
   have a path — and it changes what we tell clients, so it is a legal claim and not the
   session's to make.
2. **Do we compile CL-D2-01's local-compensation prohibition as an EXCLUDE or as a
   REQUIRE_REVIEW?** _Recommended default: EXCLUDE_ — the ledger calls it an "absolute
   prohibition", and EXCLUDE is what lets us safely retire the blanket `business_activity`
   flag; REQUIRE_REVIEW would keep the review volume we are trying to remove.
3. **Second Home (E33): do we add a real interview route, or accept it as
   consultation-only?** _Recommended default: add a `second_home` category emitting
   `intent.purposes = ["SECOND_HOME"]` alone_ — the rules already work (personas #39/#40),
   and the purpose must REPLACE, not join, RETIREMENT, because
   `hit_policy.eligibility = COVER_ALL_DECLARED_PURPOSES` drops E33 the moment a second
   purpose is declared.
4. **Diaspora: map it to FAMILY, or give it its own purpose?** _Recommended default: map to
   FAMILY and reuse the family question set_ — the products a diaspora applicant actually
   reaches are E31C/E31F, and the mapping alone already makes the walk decisive.
5. **ITAS-sponsor family products (E31B/E31E/E31H/E31J): do we ever certify a sponsor's
   status code in the browser?** _Recommended default: NO for now_ — keep the mapper's
   deliberate `UNVERIFIED` wall and make the eight blocking rules `NO_EFFECT`, so those
   routes stay consultation-only instead of dead-ending everyone else.
6. **`work_role`: do we overrule `question-registry-audit.md` §3 and stop flagging it?**
   _Recommended default: YES, and delete the question entirely_ — it is engine-inert, it
   suppresses E23 for 100% of employment interviews, and a question that only costs the user
   time and the answer is worse than no question.

---

### Rulings (2026-09-06, Zero: "seguo le tue raccomandazioni, go")

All six calls are RULED with the recommended defaults: (1) caps encode the lawful
extendable total; (2) CL-D2-01 compiled as EXCLUDE; (3) a `second_home` category emitting
`SECOND_HOME` alone; (4) diaspora maps to FAMILY; (5) no browser certification of the
ITAS-sponsor status — the eight blocking rules become `NO_EFFECT`; (6) `work_role` is no
longer flagged and the question is removed. The wave in §4 is GO in its fixed order.

## 6. What was refuted, and why (do not re-investigate)

**R1 — "Derive `process.wants_onshore_conversion = false` when offshore with no permit."**
REFUTED as a fail-open. The fact is forward-looking INTENT, not present state: the
interview's own copy asks "Are you asking to change status without leaving Indonesia?" with
the hint "Answer about your intended process, not whether it will be approved"
(i18n.ts:118-121). An offshore investor planning "enter on D12, then alih status onshore"
answers TRUE. Measured on signed seq-19, same persona, only that fact flipped: `true` →
D12 correctly excluded (`NEEDS_INPUT missing=[intent.requested_product_code]`); `false` →
`SUPPORTED_CANDIDATES [D12]` with `review_reason_codes = []` and `notice_codes = []` — a
confident recommendation of a visa that by regulation cannot be converted onshore
(research/visa/2026-07-24-w2-factbase-dseries.md:23, :71). This is the exact regression
`flow.ts:381-390` records as already having happened once. The claimed precedent
(`NO_STAY_PERMIT`, fact-mapper.ts:473-484) does not cover it: that restates the answer just
given to the SAME question. Sensitivity also tracks `category = invest`, not permit status —
`offshore/holdsPermit/current/invest_pt_pma` and `offshore/noPermit/invest_pt_pma` BOTH flip.
**Ask it (PR-3 item 1); never derive it.**

**R2 — "Emit a KNOWN sentinel for `intent.requested_product_code`."** REFUTED as a
fail-open. The finding's load-bearing claim was "every one of the 13 guards is `eq <CODE>` /
`neq BRIDGING`, so it can never fabricate support". Wrong on two counts: the 13 rules span
TEN products, not nine (BRIDGING is a live candidate), and the four `neq BRIDGING` rules are
`effect.type: SUPPORT`. Any sentinel other than the literal `"BRIDGING"` makes `neq` TRUE and
manufactures support. Measured on a browser-reachable persona (onshore, E23 stay permit,
category `other`): today `NEEDS_INPUT`; with `KNOWN("NONE")` or `KNOWN("NOT_REQUESTED")`,
`SUPPORTED_CANDIDATES [BRIDGING]` carrying reason `BRIDGING_DESTINATION_STATED` — a
recommendation whose stated ground is false precisely because the sentinel means the
opposite. The inverse sentinel `KNOWN("BRIDGING")` avoids the fabrication only by killing
the bridging route entirely. **PR-2 removes 9 of the 10 blockers for free; PR-1 edit 4 makes
the tenth self-limiting. No sentinel is needed and none is safe without edit 4.**

**R3 — "Unflag retirement/investment `property` and `bank_deposit` because the branch already
collects the signed `secondhome.*` facts."** REFUTED, and its premise inverted. Those facts
feed product **E33**, not E33F, and every rule consuming
`secondhome.qualifying_property_value_usd` is gated on `intent.purposes ∩ SECOND_HOME` — a
purpose `CATEGORY_TO_PURPOSE` (fact-mapper.ts:255-266) can never emit. Measured on live
seq-19: retirement + USD2M property WITH the flag → `HUMAN_REVIEW_REQUIRED`; the same facts
with the flag dropped → `NO_SUPPORTED_PATH`; while `purposes = ["SECOND_HOME"]` + USD2M →
`SUPPORTED_CANDIDATES [E33]`. Unflagging would replace a correct "hold for a human" with a
confidently wrong "no path" for an applicant who has a product in the same signed pack.
E33F is NOT unreachable — the unflagged `passive_income` branch returns
`SUPPORTED_CANDIDATES [E33F]`. **Fix the purpose routing first (owner decision 3), then
revisit the flag. Never the other way round.**

**R4 — "Default `sponsor.type` to NONE for the four categories that do not ask it."**
Superseded rather than refuted: PR-2 removes the block entirely, because E33A/B/C have zero
eligibility rules and become UNSUPPORTED. Measured — all five `sponsor.type` dead ends
vanish in `cure.json` with no interview change. Adding `sponsor_category` to those four
branches would be a ceremonial question that cannot change any outcome under seq-19 AND
would open a new route into human review via `notSure: {mode: "human-review"}` (tree.ts:467)
+ `NOT_CERTAIN` (fact-mapper.ts:410). **Do not add it.** (The original rationale for
rejecting a NONE default — "`hf.e33a` would silently exclude a genuinely
government-sponsored applicant" — is itself false for seq-19: E33A cannot be a candidate
under any sponsor value.)

**R5 — "The blanket `business_activity` flag is safe to remove now."** REFUTED as sequencing.
`work.indonesia_source_compensation` is read by exactly three rules, all scoped to E33G;
`el.d2-multi-entry-support` fires on purposes + stay_days alone. Measured on the signed pack:
BUSINESS_MEETINGS + 60d + SINGLE + `indonesia_source_compensation = true` →
`SUPPORTED_CANDIDATES [D2]`, `review_reasons = []`. The blanket flag is currently the only
thing between that applicant and a wrong D2 recommendation. **PR-1 edit 5 first, PR-4
second.**

---

## Adversarial review

**Seat:** Gemini 3.1 Pro (High) via `agy` 1.1.27, 2026-09-06, briefed WITHOUT the rulings'
rationale and told to refute the diagnosis, the six rulings, the wave order and the
measurements. Its verdict was "would NOT ship as-is" on ten findings (2 BLOCKER, 5 MAJOR, 3
MINOR). Each finding was then checked against the signed seq-19 pack and the code on
`origin/main`, not against this document. Dispositions below are binding on the wave PRs.

| #   | Gemini finding (severity)                                                                                                | Disposition                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| --- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | BLOCKER — PR-3 item 6 pushes a missing question onto the flow and bypasses the tree's prerequisite ordering              | **ACCEPTED, narrowed.** PR-3 may push a question only when its prerequisites are satisfied by the current facts (the question would be a member of the walk's computed step list once appended, or it declares no gate). A question with unmet prerequisites keeps today's behaviour: the handoff row. The `OracleShell` guilt test must include one prerequisite-bearing fact that is NOT pushed.                                                                                                |
| 2   | BLOCKER — unflagging `work_role` (ruling 6) bypasses a compliance hold for restricted professions                        | **RULING STANDS, with one addition.** The question's five options (executive, manager, specialist, performer, other; tree.ts:543-558) cannot identify a restricted position, and no rule in seq-19 reads any role fact (the pack's `work.*` facts are employer-entity, compensation, sponsor and clients only), so the flag was a blanket hold, not a check. Position eligibility is the employer's RPTKA step. PR-3 adds one line to the E23 result copy (three locales) stating that the position must be RPTKA-approved and that some positions are closed to foreign nationals. |
| 3   | MAJOR — PR-1 edit 4 (`known` conjunct on the BRIDGING rules) is tautological; a stated `C1` still grants BRIDGING        | **REFUTED.** Only `el.bridging.destination-stated` reads `intent.requested_product_code`; its premise is "a destination product other than BRIDGING is stated", so a known `C1` is exactly the intended case (bridging TO C1), and the `hf.bridging.*` EXCLUDE rules still gate offshore and from-visit statuses. A conjunct can only narrow. Note for the PR-1 gate: the other three rules named in edit 4 do not read that fact; adding the conjunct there only deadens them, so the fold must apply edit 4 to `destination-stated` alone.                                    |
| 4   | MAJOR — PR-2's early UNSUPPORTED skips a purpose-mismatched product's EXCLUDE rules that may be global safety nets       | **REFUTED.** The hoist lives inside `evaluate_product` (evaluator.py:549-780), which builds ONE product's proof; the product loop at :873 evaluates every product independently, and an EXCLUDE on product A never blocks product B. A product that can never cover the declared purposes cannot be recommended, so returning UNSUPPORTED instead of BLOCKED_UNKNOWN for it cannot widen any candidate set. The gate re-measures: 20 canonical personas, zero state changes.                                                                                                       |
| 5   | MAJOR — bumping the document-requirement rules to 180 shows a 121-day applicant only the 60-day checklist                | **REFUTED as to the fold, kept as content follow-up.** Edit 1 bumps the 16 document siblings precisely so the checklist does NOT vanish for a 121-day applicant. Documents specific to onshore extensions are a content question for the product pages, outside this wave.                                                                                                                                                                                                                       |
| 6   | MAJOR — the eight `family.sponsor_status_code` rules become fail-open if they are EXCLUDE gates                          | **REFUTED with the pack.** All eight (`el.e31b/e31e/e31h/e31j-*-support`, `el.e31b/e31e/e31h/e31j-sponsor-itas-itap`) are `type: SUPPORT`. With `on_unknown: NO_EFFECT` a support rule that cannot fire supports nothing: E31B/E31E/E31H/E31J leave the candidate set. Fail-closed, as §4 states.                                                                                                                                                                                              |
| 7   | MAJOR — 43 walks are one permutation per branch, so the 36→8 dead-end count is overfitted                                | **ACCEPTED as a limitation.** The census is a floor, not a proof; the structural invariant it enforces (no NEEDS_INPUT naming an unaskable fact) is about fact reachability, not answer values. PR-5 adds a bounded per-branch option-matrix replay (every choice-option combination within each branch, capped) and reports the dead-end variance.                                                                                                                                              |
| 8   | MINOR — `diaspora → FAMILY` silos diaspora applicants away from investment or work routes                                | **REFUTED.** The category is the applicant's own choice; a diaspora applicant who wants to invest chooses invest. The mapping only gives the diaspora category a purpose instead of NOT_APPLICABLE.                                                                                                                                                                                                                                                                                              |
| 9   | MINOR — asking an offshore applicant about onshore conversion is geographically nonsensical                              | **ACCEPTED as wording.** PR-3 phrases the offshore question as a plan after arrival ("Once in Indonesia, do you plan to switch to a different permit without leaving the country?"), never as a present-tense status.                                                                                                                                                                                                                                                                             |
| 10  | MINOR — CL-D2-01 EXCLUDE misfires on mixed trips where local compensation concerns only the non-business portion         | **REFUTED.** The claim ledger records CL-D2-01 as an absolute prohibition on local compensation for the visa holder; a business visa permits no paid activity, whichever purpose the payment attaches to. A "comped" stay on a business visa is exactly the case the rule must catch.                                                                                                                                                                                                             |

**Net effect on the wave.** No ruling changes. Three conditions bind the builders: PR-1 applies
edit 4 to `el.bridging.destination-stated` only; PR-3 pushes a follow-up question only when its
prerequisites hold, adds the E23 RPTKA caveat line and phrases the offshore conversion question
as a post-arrival plan; PR-5 adds the bounded option-matrix replay. Gemini's raw output is
preserved in the session scratchpad and summarised here; the seat did not see the code.

## 7. Prove-live plan

### 7.1 The browser walks that must return an answer

Each row is a complete interview a human can actually perform on the live funnel. "Expected"
is the post-wave measurement from `scratchpad/inv/synth/wave.json` and `probe_wave.py`
(offline, cure (a) + the four seq-20 edits, signed seq-19 payload recompiled in process —
never signed, never activated).

| # | Browser walk                                                             | Expected after the wave                  |
| - | ------------------------------------------------------------------------ | ---------------------------------------- |
| 1 | offshore · tourism · 121d · single                                        | `SUPPORTED_CANDIDATES [C1]`              |
| 2 | offshore · business · meetings · 121d · multi                             | `SUPPORTED_CANDIDATES [D2]`              |
| 3 | onshore · business · meetings · 121d                                      | `SUPPORTED_CANDIDATES [D2]`              |
| 4 | offshore · work · employer confirmed · 365d                               | `SUPPORTED_CANDIDATES [E23]` (needs PR-4) |
| 5 | offshore · study · admission + sponsor confirmed                          | `SUPPORTED_CANDIDATES [E30, E30A]`       |
| 6 | offshore · family · SPOUSE · sponsor ID · marriage registered             | `SUPPORTED_CANDIDATES [C1, E31A]`        |
| 7 | offshore · family · PARENT · sponsor ID                                   | `SUPPORTED_CANDIDATES [C1, E31C, E31F]`  |
| 8 | offshore · family · CHILD · sponsor ID                                    | `SUPPORTED_CANDIDATES [C1, E31G]`        |
| 9 | offshore · invest · PT PMA · sponsor confirmed                            | `SUPPORTED_CANDIDATES [C2]`              |
| 10 | offshore · invest · PT PMA · no sponsor · onshore conversion NO           | `SUPPORTED_CANDIDATES [D12]`             |
| 11 | offshore · other · sponsor confirmed                                      | `SUPPORTED_CANDIDATES [C6]`              |
| 12 | onshore · holds permit · current · tourism · 121d                         | `SUPPORTED_CANDIDATES [C1]`              |

And the walks that must return an honest **`NO_SUPPORTED_PATH`** — not a question:

| # | Browser walk                                                     | Expected                                        |
| - | ---------------------------------------------------------------- | ----------------------------------------------- |
| A | offshore · remote · paid from an Indonesian source                | `NO_SUPPORTED_PATH` (hf.e33g excludes)          |
| B | offshore · invest · PT PMA · no sponsor · onshore conversion YES  | `NO_SUPPORTED_PATH` (D12 not convertible)       |
| C | offshore · other · no sponsor                                     | `NO_SUPPORTED_PATH`                             |
| D | offshore · retirement · deposit below the USD threshold           | `NO_SUPPORTED_PATH`                             |
| E | offshore · remote · employer is an Indonesian entity              | `NO_SUPPORTED_PATH` (and see §3.1 #20 — the honest verdict is "you need a work route", which needs owner decision on purpose vocabulary) |

**The invariant, not the list:** after the wave, **no browser walk may end in `NEEDS_INPUT`
naming a fact the interview has no reachable question for.** PR-0's census gate enforces it
with an allowlist that the wave empties.

### 7.2 Prod observation per PR

Only `apps/backend-rag/backend/scripts/visa_engine/probe_evaluate.py` with
`traffic_source = synthetic_driver` may touch production (it reads the driver token itself;
no other prod call, no prod write). The three probes taken during this investigation all
returned HTTP 200, mode `ENGINE`, `rule_pack` sequence 19 / version 2026.9.5 /
`payload_sha256 bac5da8e…e6ea` — that is the "before" baseline every PR must be diffed
against:

- synthetic IT / TOURISM / 20d / SINGLE → `SUPPORTED_CANDIDATES` (B1 + C1), 2 quotes
  AVAILABLE, 2 primary `imigrasi.go.id` sources VERIFIED + CURRENT;
- owner-shape offshore / BUSINESS_MEETINGS / 121d / MULTIPLE, no flags →
  `NEEDS_INPUT missing=[process.wants_onshore_conversion]`;
- same persona with `disclosed_review_flags = ["ACTIVITY_BOUNDARY"]` →
  `HUMAN_REVIEW_REQUIRED`, one reason `DISCLOSED_ACTIVITY_BOUNDARY_REVIEW`, 0 candidates.

(`scratchpad/inv/d5-verdict/req-supported.json`, `req-needsinput.json`, `req-humanreview.json`,
`resp-supported.json`.)

### 7.3 Where HUMAN_REVIEW is legitimate and must stay

After the wave, review should appear for these and essentially nothing else:

- **minors** — `MINOR_GUARDIAN_PRIVACY_REVIEW` / `MINOR_WITHOUT_CONFIRMED_GUARDIAN`
  (`_apply_minor_privacy_hold`, evaluate_path.py:1033-1085): a deliberate PII decision,
  4 of the 9 reviews in §3;
- **calling-visa nationalities** — `CALLING_VISA_REVIEW` (persona #08): correct law;
- **dual nationality** — `CITIZENSHIP_LIST_DIVERGENCE` (persona #43): correct law;
- **remote work serving Indonesian clients** — `LOCAL_MARKET_ACTIVITY_REVIEW` (persona #19):
  correct law, and unlike its `income-evidence` sibling it has a discriminating condition;
- **explicit uncertainty** — `NOT_CERTAIN`, when the user themselves answered "unsure";
- **the routes owner decisions 3/4/5 leave unmapped** — second home via
  retirement/investment property, diaspora, ITAS-sponsor family. Their ACTIVITY_BOUNDARY /
  AMBIGUOUS_SPONSOR flags stay until the routing exists, because §6 R3 measured that
  removing them first manufactures wrong negatives.

Everything else — a `work_role` answered, a `business_activity` named, a trip with two
purposes — must stop producing review. That is the measurable form of the owner ruling
"human review must almost never appear": not a promise, a census.

---

> Measured 2026-09-06 on `origin/main` `9a36edab26`…`e7a11cd633`. Offline replays used
> `verify_rule_pack` → `build_compiled_pack` → `evaluator.evaluate` →
> `apply_public_policy_adapters`, the same path both committed gates use. Three production
> reads via `probe_evaluate.py` (`synthetic_driver`); no production write, no signing key
> read, no client data touched.
