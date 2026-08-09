---
date: 2026-08-10
domain: visa
adversarial_review: codex
adversarial_review_note: "gpt-5.6-sol at xhigh, 2026-08-10, read-only sandbox — 8 findings against DRAFT 2, verdict DO-NOT-SHIP. Two CRITICAL and one HIGH were reproduced independently against the real evaluator and are cured in draft 3, which is what this document describes; one LOW (rule_pack_id off-convention) was checked and DOES NOT HOLD. Draft 2's own review was the in-house `devils-advocate` agent, which is pinned `model: sonnet` — the same family as the generator, and it passed the pack that this one rejected. The earlier note here called that agent 'DeepSeek-backed', repeating its stale description rather than its pin; provenance of a review is a claim like any other."
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

## The second draft, and why it was wrong too

Draft 2 — the conjunction fix above — was reviewed by the in-house `devils-advocate` agent
and passed. That agent is pinned `model: sonnet`: the same family as the generator. A
cross-family seat (gpt-5.6-sol, xhigh, read-only sandbox) pointed at the same pack returned
**DO-NOT-SHIP** with eight findings, and the two CRITICAL ones were reproduced here against
the real evaluator before anything was changed:

- **A requirement that reads a disqualifying threshold is not a requirement.**
  `review.e33f.age-under-55` tests `RETIREMENT ∧ age < 55`. Converted to SUPPORT, it made a
  46-year-old eligible for the retirement KITAS, and with the age unestablished the product
  was offered without the question ever being asked. The same shape hit E33E, E31J and D12.
  The triage had two boxes, wall and support, and the right answer for these was a third.
- **A conjunction is only as strong as the gate it conjoins.** E23U and E23V were "gated" by
  `EMPLOYMENT ∧ a confirmed Indonesian work sponsor` — true of every ordinary employee. The
  cure that made a requirement unable to carry a product on its own did nothing here,
  because the gate itself proved nothing. The refutation of draft 1 said a requirement must
  not be the proof; it did not say the proof must be adequate, and that is the gap.

One HIGH inverted the mandate outright: `hr.e30a-minor-consent` was KEPT as a wall on the
grounds that guardian consent is not a document reminder — but it never tests consent, so a
16-year-old with admission, a study sponsor and a confirmed guardian still got a blank
answer. One LOW (a `rule_pack_id` allegedly off-convention) was checked and **does not
hold**: recomputing the UUIDv5 from the canonical sequence URL reproduces the stored id
exactly. A refuter is not a verdict either.

The lesson generalises past this pack: **the in-family reviewer passed the pack the
cross-family one rejected**, which is the failure mode the arsenal already has a scar for.
The seat's name in the frontmatter of a research file is therefore load-bearing, not
paperwork.

## What seq-6 does

1. Every converted rule is **conjoined with its product's genuine seq-5 eligibility gate**
   and takes that gate's `covered_purposes`. It can only be TRUE where the gate is TRUE, and
   contributes no coverage the gate did not earn. The requirement still reaches the
   applicant — as a reason on a candidate the gate approved.
2. Rules scoped to several products are **split per product**, since each product has its own
   gate and one conjunction cannot serve several. 113 rules become 115.
3. Two safety-critical HARD_FILTERs, `hf.e30a-level-band` and `hf.e30b-level-band`, gain an
   `intent.purposes intersects [STUDY]` guard. Their `when` was `study.level not_in [...]`
   with no purpose test, so for anyone who never mentioned studying both products returned
   UNKNOWN and the decision degraded to asking a tourist for their study level. seq-5 does
   this too; removing the walls is what makes it the answer people see, so the guard ships
   with them.

4. **Four rules move to `HARD_FILTER`** — the box the first two drafts did not have. A rule
   that tests a fact which genuinely disqualifies ONE product belongs there: it removes that
   product and leaves the other 37 standing. As `HUMAN_REVIEW` it walls the whole answer; as
   `SUPPORT` it asserts an eligibility the fact denies. `review.e33f.age-under-55`,
   `review.e33e.age-55-59-disputed-band`, `hr.e31j-dependency-age` and
   `hr.d12-long-stay-review` all read a threshold the applicant can fail, and draft 2 had
   converted them to `SUPPORT` — so a 46-year-old was offered the retirement KITAS. Their
   `on_unknown` is `NEEDS_INPUT`, which is what makes a missing age produce a QUESTION
   instead of a silent offer.
5. **E23U and E23V leave the offer set entirely.** E23U is a foreign diplomat's household
   assistant, E23V is a trade/economic office posting; the contract carries no fact that
   tells either apart from an ordinary E23. Their four review rules are literally
   `intent.purposes intersects [EMPLOYMENT]` — as walls they would wall every employed
   applicant, as supports they offered both products to any engineer with an Indonesian
   sponsor. Their generic seq-5 gates are dropped with them. Nine products are now
   out of reach, not seven.

Fifteen walls remain: the 4 `safety_critical` gates, 4 prohibitions that test the violating
fact, and 7 belonging to products with no eligibility rule at all (below). Guardian consent
is no longer among them: `hr.e30a-minor-consent` fires on `STUDY ∧ is_minor` and never looks
at consent or a guardian — the global `family.sponsor_confirmed` rule is what actually checks
that — so keeping it walled the whole answer for a 16-year-old who had everything in order.

## Measured

| | seq-5 | seq-6 |
|---|---|---|
| products carrying at least one eligibility rule | 5 / 38 reachable | **29 / 38** |
| HUMAN_REVIEW rules | 67 | **15** |
| product-scoped HARD_FILTER exclusions minted | — | 4 |
| `backend/tests/services/visa_engine` | pass | **pass (rc 0)** |
| `test_seq6_refuter_witnesses.py` | — | **8 / 8** |

Every number in that table is re-derivable from the repo: the counts by reading the pack,
the last two by running the suites. That is deliberate and it is a change from draft 2,
whose headline claims rested on scratch scripts nobody else had. Two of them are worth
naming as withdrawn rather than quietly dropped:

- **"27 / 38 reachable"** contradicted this document's own list of unreachable products,
  which implied 31. Neither number survives: the true count for the pack as shipped is
  **29**, pinned by `test_reachability_is_what_the_document_claims`.
- **"0 of 771 candidates supported by no eligibility rule"** came from a fuzz harness that
  was never committed, so it cannot be re-run by a reader — the adversarial seat said so
  explicitly. It is withdrawn rather than restated. What replaces it is narrower and real:
  the invariant that every converted rule literally contains its product's gate as a
  conjunct is asserted by the generator, and the four ways that invariant was NOT enough
  are now tests.

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

- **Nine products remain unreachable**: E28B, E28C, E28D, E28F, E33A, E33B, E33C have **no
  eligibility rule at all**, so there is nothing to conjoin with, and the pack has no fact
  for a USD investment band or a government invitation. E23U and E23V were added to that
  list by this draft: they HAD a gate, but one so generic it could not tell them apart from
  an ordinary E23. Converting any of their review rules would make the applicant's own
  request the entire proof — the defect that sank draft 1. Reaching them needs new facts in
  the interview contract, not new rules over the facts we have.
- **An ABSENT fact and an UNKNOWN one are answered differently, and only one of them asks.**
  With the age declared unknown the engine returns `NEEDS_INPUT` naming `person.birth_date`;
  with the key simply not present it returns `NO_SUPPORTED_PATH` and asks nothing. Neither
  produces a false offer, so this is not the CRITICAL — but an applicant the interview never
  asked about age gets a blank answer rather than a question. Pinned, not fixed, by
  `test_deleting_the_age_key_is_not_the_same_as_declaring_it_unknown`.
- **Excluding E33E for the 55-59 band is deliberately conservative.** The source calls that
  band disputed, not disqualifying. With only four effect types available, the honest
  choices were to assert eligibility in a disputed band, to wall the whole answer, or to
  drop that one product — and a 55-59 applicant still reaches E33F, so dropping it costs
  them an option they would not otherwise lose. If the band is later resolved in the
  applicant's favour, this exclusion is the line to delete.
- **The four exclusion reason codes have no client-facing copy.** `SUPPORT_REASON_COPY` in
  the mouth adapter covers reasons that appear ON an offer; a product removed by a
  HARD_FILTER carries its reason nowhere the applicant sees. So today a 46-year-old is
  correctly not offered E33F and is told nothing about why.
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

## Adversarial review

Seat: **codex** (`gpt-5.6-sol`, `model_reasoning_effort=xhigh`, `--sandbox read-only`),
2026-08-10, pointed at draft 2 of this pack with instructions to refute and to cite
file:line. Eight findings, verdict **DO-NOT-SHIP**. Every one was re-checked here against
the pack and the real evaluator before being accepted or rejected — a refuter's citation is
a lead, not a fact.

| # | severity | finding | disposition |
|---|---|---|---|
| 1 | CRITICAL | E23U/E23V gates are generic (`EMPLOYMENT` + any confirmed Indonesian sponsor), so the conjunction cure does not bite | **accepted, cured** — both products taken out of reach; `test_ordinary_employee_is_not_offered_the_diplomatic_or_trade_office_routes` |
| 4 | CRITICAL | age/threshold rules (E33F, E33E, E31J, D12) converted to SUPPORT can be silently ignored — a 46-year-old is offered E33F, and with no age it is offered without asking | **accepted, cured** — all four moved to product-scoped `HARD_FILTER` with `on_unknown: NEEDS_INPUT`; two tests |
| 5 | HIGH | `hr.e30a-minor-consent` kept as a wall although it tests neither consent nor guardian, so a compliant 16-year-old still gets a blank answer | **accepted, cured** — converted; `test_a_compliant_minor_is_not_walled_out_of_the_whole_answer` |
| 6 | MEDIUM | the converted D12 long-stay rule is unsatisfiable (`stay > 365 ∧ stay ≤ 180`) — the signal was lost, not moved | **accepted, cured** — same HARD_FILTER move as #4 |
| 7 | MEDIUM | the reachability headline (27/38) contradicts this document's own list of unreachable products; `0/771` is not reproducible because its harness is not in the repo | **accepted** — recounted to 29/38 and pinned by a test; the 771 claim is withdrawn, see *Measured* |
| 2 | — | no finding: no product gains a literal purpose value | noted; it does not cure #1, and the report says so |
| 3 | — | no finding: the E30A/E30B level bands still discriminate correctly | independently re-probed, agrees |
| 8 | LOW | `rule_pack_id` allegedly violates the UUIDv5-from-canonical-URL convention | **REJECTED** — recomputing `uuid5(NAMESPACE_URL, ".../2026.8.10/seq-6")` reproduces the stored `e04a21e7-8716-584b-90ac-de3b5c192330` exactly |

Not raised by the seat and still open: the ABSENT-vs-UNKNOWN asymmetry, the conservatism of
the E33E band exclusion, and the missing client-facing copy for exclusion reasons — all
three are in *Open, and not papered over* rather than here, because nobody found them for me.

## Activation prerequisite

`bundle.py:966-993` requires `previous_payload_sha256` to equal the currently-active pack's
payload hash. seq-6 declares seq-5's. **seq-5 exists only as `.source.json`** — the last
signed bundle in the repo is `rulepack-prod-004.signed.json` — so seq-5 must be signed
byte-identically to its source and activated before seq-6 can be. Signing and activation are
separate, irreversible steps and are Zero's.
