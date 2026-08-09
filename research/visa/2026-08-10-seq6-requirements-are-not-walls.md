---
date: 2026-08-10
domain: visa
adversarial_review: devils-advocate
adversarial_review_note: "DeepSeek-backed refuter, 2026-08-10 — 11 objections, 5 CRITICAL/HIGH REFUTED against the first draft of prod-006. That draft was discarded; the pack described here is the rewrite, and the refutation is reproduced below because it is the reason the pack has the shape it has."
client_case: none (Visa Oracle V2 rule pack seq-6)
sources:
  - rulepack-prod-005.source.json (seq-5, ACTIVE in SHADOW since 2026-08-09)
  - rulepack-prod-006.source.json (seq-6, this document — unsigned, unactivated)
  - evaluator.py (REVIEW>SUPPORTED precedence :1381-1394; union coverage :650-678)
  - models.py:1262 (Decision forbids review_reasons on SUPPORTED_CANDIDATES)
  - research/visa/2026-08-09-visa-oracle-decision-tree-audit.md (the prior audit this reverses in part)
  - offline harness — real evaluate(), real prod packs, synthetic facts only
---

# seq-6 — a requirement is a condition, not a proof

Zero, 2026-08-09, on a live production result that offered a clean Albanian remote worker
nothing at all: *"NON VA BENE!!!! DEVE DARE OPZIONE"*, then *"ma non voglio solo e33g! ma tu
non hai lavorato su 38 visti"*. This is the pack that answers the second sentence.

## The defect in seq-5

`evaluator.py:1381-1394` returns `HUMAN_REVIEW_REQUIRED` — carrying review reasons and **no
candidates** — the moment ONE product proves REVIEW, and `models.py:1262` forbids
`review_reasons` on a `SUPPORTED_CANDIDATES` decision. The two together mean a single
triggered wall deletes all 38 products from the answer, including products that proved fully
supported. Measured by building, for each product, the applicant its own eligibility rules
describe: **seq-5 reaches 5 products out of 38**.

Of the 67 HUMAN_REVIEW rules, most detect nothing. `hr.d2-funds-usd-2000` is literally
`intent.purposes intersects [BUSINESS_MEETINGS]` and reads no funds fact. `hr.e30-living-cost-2000`
is the STUDY purpose alone. `hr.e23-prohibited-hr-roles` is the EMPLOYMENT purpose alone and
never consults `investment.proposed_role`, which the pack does carry — and `ProposedRole`
(`enums.py:281-286`) has no HR value, so it never could. Their `when` selects an audience,
not a defect. Twelve more name a money or qualification threshold the engine has no fact to
test at all: there is no income field anywhere in `work.*`, which is why the USD 60k rule
behind E33G could only ever hand every qualifying remote worker to a human.

The pack already carried the distinction the engine ignores: exactly 4 of the 67 are
`safety_critical`, and the review precedence never reads that field (it is consulted only by
`_apply_safety_critical_source_hold`, about source freshness).

## The first draft, and why it was wrong

Draft 1 converted 59 rules to `ELIGIBILITY`/`SUPPORT` and was refuted. Eligibility coverage
is a **union**: `evaluator.py:650-678` builds `covered` from every TRUE support rule and
declares SUPPORTED on `purposes <= covered`. A converted requirement, true for anyone with
the purpose, was therefore enough **on its own** to carry a product whose real gate was FALSE.

Measured over 4000 fuzzed applicants: **1235 of 2033 emitted candidates (60.7%)** rested on
no rule that had tested eligibility. Concretely — a 200-day business traveller offered D2,
whose gate caps stay at 60 days; a tourist offered D12, the investment visa, as their only
option; an unmarried applicant with no Indonesian sponsor offered the spouse KITAS E31A;
`intent.requested_product_code == "E33A"` serving as the entire proof of E33A.

The metric used to defend draft 1 ("0 options lost across 43 personas") measured the wrong
direction. A change of this shape **cannot** lose options; it can only manufacture them. The
number that needed reporting was false gains.

## What seq-6 does

1. Every converted rule is **conjoined with its product's genuine seq-5 eligibility gate**
   and takes that gate's `covered_purposes`. It can only be TRUE where the gate is TRUE, and
   contributes no coverage the gate did not earn. The requirement still reaches the
   applicant — as a reason on a candidate the gate approved.
2. Rules scoped to several products are **split per product**, since each product has its own
   gate and one conjunction cannot serve several. 113 rules become 121.
3. Two safety-critical HARD_FILTERs, `hf.e30a-level-band` and `hf.e30b-level-band`, gain an
   `intent.purposes intersects [STUDY]` guard. Their `when` was `study.level not_in [...]`
   with no purpose test, so for anyone who never mentioned studying both products returned
   UNKNOWN and the decision degraded to asking a tourist for their study level. seq-5 does
   this too; removing the walls is what makes it the answer people see, so the guard ships
   with them.

Sixteen walls remain: the 4 `safety_critical` gates, 4 prohibitions that test the violating
fact, guardian consent for a minor, and 7 belonging to products with no eligibility rule at
all (below).

## Measured

| | seq-5 | seq-6 |
|---|---|---|
| products reachable by an applicant built from their own rules | 5 / 38 | **27 / 38** |
| candidates supported by no eligibility rule (4000 fuzzed applicants) | — | **0 / 771** |
| 23 gold_harness personas | — | 5 gain options, **0 lose any** |
| HUMAN_REVIEW rules | 67 | 16 |

Safety gates verified still walling: calling visa, active overstay, citizenship divergence,
minor without guardian. Level bands verified still discriminating: a PRIMARY-level student
gets E30A and never E30B; an UNDERGRADUATE gets E30B and never E30A.

## What this reverses, deliberately

`research/visa/2026-08-09-visa-oracle-decision-tree-audit.md` concluded, after its own
adversarial round and after Zero's direct pushback, that **BUSINESS (D2)** document review
was *"intended verification, not a defect — no seq-5 change"* and that **EMPLOYMENT (E23/U/V)**
review was *"legitimate: government/RPTKA verification"*. seq-6 removes both walls. Zero
confirmed the reversal on 2026-08-10: *"per D2 ed E23 non voglio nessun muro"*. The
verification itself is not removed — it becomes a stated condition on an offered product
instead of a blank screen.

## Open, and not papered over

- **Seven products remain unreachable**: E28B, E28C, E28D, E28F, E33A, E33B, E33C. They have
  **no eligibility rule at all**, so there is nothing to conjoin with, and the pack has no
  fact for a USD investment band or a government invitation. Converting their review rules
  would make the applicant's own request the entire proof — exactly the defect that sank
  draft 1. Reaching them needs new facts in the interview contract.
- **The E30 family cannot be told apart.** A student is offered E30, E30B, E30E and E30F
  together, each with its correct caveat ("KEK institutions only", "exchange programmes
  only"), because no interview fact distinguishes them. The 2026-08-09 audit already named
  this; seq-6 turns a blank wall into four captioned options, which is better and is not
  right.
- **Four sibling HARD_FILTERs have the same missing purpose guard** as the two fixed here:
  `hf.e31e-adult-excluded`, `hf.e31e-married-excluded`, `hf.d12-onshore-conversion-excluded`,
  `hf.e33f.sponsor-required`. Not fixed in this pack.
- **`ELIGIBILITY_RULE_PRESENCE_ONLY` (`compiler.py:131-135`) did not catch draft 1**, because
  `_PRESENCE_ONLY_OPERATORS` is only `{known, unknown}`. A check that rejects a SUPPORT rule
  whose `when`, with every `intent.purposes` leaf removed, is vacuously true would have
  failed all 59 conversions and blocked that pack at authoring time. Recommended, not built.
- **Fifteen reason codes and 59 rule ids were renamed.** No live consumer references the old
  ones, but Decisions persisted under seq-1..5 carry them, so historical replay keyed on a
  rule id will not resolve against this pack.

## Activation prerequisite

`bundle.py:966-993` requires `previous_payload_sha256` to equal the currently-active pack's
payload hash. seq-6 declares seq-5's. **seq-5 exists only as `.source.json`** — the last
signed bundle in the repo is `rulepack-prod-004.signed.json` — so seq-5 must be signed
byte-identically to its source and activated before seq-6 can be. Signing and activation are
separate, irreversible steps and are Zero's.
