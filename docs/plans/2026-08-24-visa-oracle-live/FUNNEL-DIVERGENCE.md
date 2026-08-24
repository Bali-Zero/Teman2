# Funnel divergence — measured, not just possible by construction

Closes the gap `TWO-DOORS.md` named explicitly: "whether the old funnel's recommendations
actually diverge from the engine's on the same inputs... is possible by construction... but not
measured." This document measures it. Read-only throughout: no edits to `quiz-logic.ts`,
`match_tree.py`, `shadow.py`, `visa_oracle_service.py`, or the engine. No PR opened.

**There are two distinct "old" recommendation surfaces, not one — disambiguated up front so the
two comparisons below are not conflated:**

|                  | Endpoint                             | Backend logic                                                        | Live UI caller today?                                                                                                                                                                                                                                                                                                           |
| ---------------- | ------------------------------------ | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Old engine 1** | `POST /api/visa/match`               | `match_tree.recommend_visa()`                                        | **Yes** — `/visa/match/page.tsx`, the actual public, indexable page                                                                                                                                                                                                                                                             |
| **Old engine 2** | `POST /api/v1/visa-oracle/recommend` | `VisaOracleService.recommend_visas()` (`visa_oracle_service.py:210`) | **No** — `lib/visa-oracle/api.ts:241`'s `recommendVisas()` wraps it, fully typed and tested, but grepping every `.tsx`/`.ts` in `apps/mouth/src` for a caller of that function finds none. The endpoint is live, public, and unauthenticated — reachable by anyone who knows the URL — but no shipped page currently drives it. |

Part 1 below measures Old engine 1 against the signed engine (this unit's own original framing).
Part 2 measures Old engine 2 against the signed engine directly at the endpoint-logic level, per
the sharpened, corrected ask from team-lead — including the correction that Old engine 2, not Old
engine 1, is the pairing team-lead's message actually named (`api.ts:241`, `visa_oracle_service.py:210`).

## Part 1 — old engine 1 (`match_tree.py`, the live `/visa/match` page) vs the signed engine

## Method — what actually ran, and what did not

**The input alphabet used is the real live one, not `quiz-logic.ts`.** `quiz-logic.ts` (the file
`TWO-DOORS.md` and the mandate both point to) is option-list/validation scaffolding
(`PURPOSE_OPTIONS`/`DURATION_OPTIONS`/`FAMILY_OPTIONS`, `isQuizComplete`) — it is never called by
`/visa/match/page.tsx`. The page that is actually live defines its own four fields locally
(`nationality` as an ISO-3 select, `purpose` as one of 8 ids, `duration` as a 1–60 month slider,
`budget` as one of 3 bands) and POSTs them through the Next.js catch-all proxy
(`app/api/[...path]/route.ts`) straight to the FastAPI backend's `POST /api/visa/match`
(`app/routers/visa_check.py`), whose entire recommendation logic is
`backend.services.visa_check.match_tree.recommend_visa()` — a small, pure, fully-read function.
This is the real old funnel; `quiz-logic.ts`'s `QuizAnswers` shape (`nationality`/`purpose`/
`duration`/`family`) is a distinct, differently-shaped type consumed elsewhere (`VisaChat.tsx`,
`lib/visa-oracle/api.ts`'s `recommendVisas()`, which calls a _different_ backend endpoint,
`/api/v1/visa-oracle/recommend`) — not by the match wizard's own submit path. **Correction to the
new task's own framing, stated plainly per the anti-hallucination discipline**: the 4-question
input alphabet to use is `{nationality, purpose (8 values), duration_months (1–60), budget_band (3
bands)}` from `match_tree.py`, not the 7-purpose/4-duration-bucket/family shape in `quiz-logic.ts`.

**The comparison did not require hand-simulating either side.** The codebase already contains a
purpose-built adapter from this exact input alphabet onto the engine's fact vocabulary:
`backend.services.visa_engine.shadow.build_shadow_facts()`, written for STEP-6c's own SHADOW-MATCH
audit wiring (`maybe_spawn_shadow_match()`, called unconditionally after every real
`POST /api/visa/match`, gated OFF by default via `VISA_ENGINE_MATCH_MODE`). This document drives
representative inputs through the **unmodified** `recommend_visa()` and, via the **unmodified**
`build_shadow_facts()` + `evaluator.evaluate()`, the same **unmodified** engine — against the real,
currently-active signed **PRODUCTION** pack, `rulepack-prod-013.signed.json` (seq-13, 38 products,
111 rules), not a smaller test fixture. Companion script, runnable and unmodified from this
report: `research/visa/2026-08-24-two-funnel-divergence-probe.py`.

**What is disclosed, not silently glossed over:**

- **No production DB access from this session.** The only Postgres MCP available here
  (`postgres-nuzantara-local`) connects to `nuzantara_dev`, a local database where the
  `visa_decisions` table (STEP-6c's own write target) does not even exist. I cannot say whether
  `VISA_ENGINE_MATCH_MODE=SHADOW` is armed in production today, nor pull real audit rows if it is.
  Everything below is a direct re-execution of the same production code paths against
  representative synthetic inputs, not a read of live traffic.
- **The engine's STEP-6d identity-provider guard required a throwaway key.** `evaluate()` refuses
  to run a PRODUCTION-environment pack under the default placeholder identity provider
  (`PlaceholderIdentityNotAllowedError`). The probe script mints a local, all-zero, never-persisted
  HMAC key via `VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON`, exactly the pattern the repo's own
  `test_shadow_match.py::test_provisioned_prod_key_writes_a_real_shadow_row` uses — not a real
  secret, nothing written anywhere.
- `effective_at`/`observed_at` fixed at `2026-08-24T00:00Z`, inside `rulepack-prod-013`'s open
  `valid_period` (from `2026-07-25`, no `to`).

## Finding 1 (the headline): the SHADOW-MATCH pipeline cannot produce a differentiated verdict

A defect in the audit pipeline itself, found by exercising it, not invented.

Running all twelve representative cases below (eight purposes × varied duration/budget, plus one
nationality variant) produced **`HUMAN_REVIEW_REQUIRED` in twelve of twelve**, every one carrying
the **identical** four `review_reasons` — `BRIDGING_ONSHORE_ONLY`, `BRIDGING_FROM_VISIT_ITK_PROHIBITED`,
`BRIDGING_TO_BRIDGING_PROHIBITED`, `BRIDGING_ADVERSE_HISTORY` — regardless of purpose, duration,
budget, or nationality. That is not eleven independent verdicts; it is one constant.

**Root cause, confirmed by reading the pack and by a control run, not guessed:** all four reasons
belong to four rules scoped to a single product — `BRIDGING` (`product_version_ids: [one UUID]`) —
each with `on_unknown: HUMAN_REVIEW` on a fact (`immigration.currently_in_indonesia` /
`immigration.current_status_code` / `immigration.violation_history`) that `build_shadow_facts()`
never sets (by design — it only ever populates 3 of 45 applicant facts:
`person.nationalities`/`intent.purposes`/`intent.stay_days`; confirmed independently by the repo's
own `test_shadow_match.py::test_exactly_3_known_and_42_unknown_fields`). Per the five-state
precedence (`TEMPORARILY_UNAVAILABLE > HUMAN_REVIEW_REQUIRED > SUPPORTED_CANDIDATES > NEEDS_INPUT >
NO_SUPPORTED_PATH`), **any** unresolved `on_unknown=HUMAN_REVIEW` rule anywhere across the full
38-product catalogue — even for BRIDGING, a product the applicant never asked about and the old
funnel never offers — wins over every other product's real, purpose-specific candidates, review
holds, or abstentions.

**Control experiment, to isolate whether this is a probe artifact or a real property of the shipped
adapter+pack combination:** re-ran the `long_tourism/2mo/under_50m` case with one additional fact
set to `KNOWN` — `immigration.currently_in_indonesia = False` — using the same unmodified
`evaluate()` against the same real pack. The four BRIDGING reasons vanish entirely and the state
flips to `NEEDS_INPUT` (empty `review_reasons`, empty `candidates`) — proving the BRIDGING noise is
exactly and only the cause, not a broader evaluator malfunction. It also shows the 3-fact adapter
is still too narrow to reach `SUPPORTED_CANDIDATES` even for a basic tourism case once the noise is
removed — consistent with `GROUND.md`'s independent finding that the full interview asks ~50
questions and reaches only 29/38 products; three facts were never going to be enough regardless of
BRIDGING.

**Consequence, stated as what it is:** as built today, if `VISA_ENGINE_MATCH_MODE=SHADOW` were ever
armed in production, the STEP-6c pipeline would write a `visa_decisions` row of
`verdict='HUMAN_REVIEW_REQUIRED'` for **every** Match submission, carrying zero information about
what the applicant actually asked for. This is a second, more specific instance of the
"exists ≠ armed" family (`.claude/rules/cicatrix-superscar.md` #2) sitting on top of the
already-documented "gated OFF by default" one: even if armed, the audit signal this pipeline is
designed to produce is not currently obtainable. Not this unit's to fix (no code changes were
made) — flagged for whoever owns STEP-6c/6d next: either give the BRIDGING rules an
`on_unknown=EXCLUDE`/scoped default, or extend `build_shadow_facts()` with a same-onshore-status
assumption reasonable for a Match-wizard submission (most submitters are not yet in Indonesia).

## Finding 2: the two catalogues do not name the same products — a static defect, no input needed

Diffing `match_tree.py`'s own `VisaType` enum (20 codes) against the real engine catalogue's 38
product codes (`rulepack-prod-013`):

**Old-funnel-only codes — do not exist in the engine's catalogue by that code at all:**
`C7`, `C7A`, `C7B`, `C18`, `C22A`, `E23-FREELANCE`, `E31`.

The old funnel can (and in the cases below, does) recommend `E23-FREELANCE` and `E31` as a primary
or alternative pick, and `C18`/`C22A` as alternatives. None of these seven strings is a
`product_code` the engine's signed pack recognizes. This directly answers the "does it offer a
product the engine would abstain on" question — sharper than abstention: for these seven, the
engine has no representation to abstain _on_. (`E23`/`E33`/`E33E`/`E33F`/`E33G`/`B1`/`C1`/`C2`/
`C6`/`D2`/`D12`/`E28A`/`E30A` are shared codes and do exist on both sides.)

**Engine-only codes — the old funnel never offers these under any input:** `A1`, `BRIDGING`, `D1`,
`E23U`, `E23V`, `E28B`, `E28C`, `E28D`, `E28F`, `E30`, `E30B`, `E30E`, `E30F`, and the nine `E31A`–
`E31H`/`E31J` family-relation sub-codes (no `E31I` — the pack skips that letter; 25 engine-only
codes in total). `match_tree.py`'s bare `E31` collapses nine distinct engine products
(spouse/child/parent/stepchild by exact relation) into one undifferentiated code — the old funnel
cannot express _which_ family relation, so it can never land on the correct `E31X`.

## Finding 3: `budget_band` has no honest mapping onto the engine's fact vocabulary

Reported as the instructions require — not forced.

Per the assignment's own instruction — "if a specific input combination cannot be honestly mapped
onto the engine's fact vocabulary, that inability IS itself a finding" — this is exactly that case,
for the fourth of the old funnel's four fields (`budget_band` is never even reached by the
scoring-branch inputs below because it plays no role in _this_ mapping at all):
`build_shadow_facts()` does not map `budget_band` onto anything, and there is no _generic_ "budget
band" fact — a 3-way IDR bucket applicable purpose-agnostically — anywhere in the 45-key `FactPath`
vocabulary. **Correction after independent re-verification**: an earlier version of this finding
claimed `E33E`/`E33F`'s retirement pension threshold has no engine-side fact at all — that is wrong.
`FactPath.SECONDHOME_PASSIVE_MONTHLY_INCOME_USD` (`secondhome.passive_monthly_income_usd`) is a real
fact, and it is actively wired into three ELIGIBILITY/band rules in the currently-signed production
pack — `el.e33e.retirement`, `el.e33f.retirement`, `el.e33e.age-55-59-disputed-band` — gating on a
USD 3,000/month threshold, alongside a companion `secondhome.bank_deposit_usd` savings/deposit
fact. So the retirement-income check DOES have a real analog; `build_shadow_facts()` simply never
sets it (same 3-of-45 gap as everything else). The narrower claims that DO hold, independently
re-checked: `investment.investment_capital_idr`/`investment.paid_up_capital_idr` exist but are
investor/PT-PMA-specific (not a general savings threshold), and `build_shadow_facts()` doesn't wire
even that partial overlap for the `invest` purpose; `E33G`'s USD 60,000 digital-nomad savings step
has no gating fact of its own in the pack at all — that one case is a genuine vocabulary gap, not
merely an unwired one. A funnel rebuilt to ask a generic "budget" question still cannot honestly
claim the engine evaluates it as one concept — the real facts that exist are purpose-specific
(`investment.*`, `secondhome.*`), never a single generic budget/funds field — but "no engine fact
exists at all for any budget-adjacent product" was an overstatement this correction retracts.

## The comparison table

Twelve representative inputs, chosen to cover each of the eight purposes plus the three explicit
early-referral branches `recommend_visa()` itself defines (`OTHER` always refers; `LONG_TOURISM`
past 6 months refers; `INVESTOR` at `UNDER_50M` refers). Nationality held at a neutral `USA`
throughout except the last row, which swaps it to show that `match_tree.py`'s own
`recommend_visa()` discards `nationality` entirely (`del nationality  # reserved for future
visa-waiver rules` — visible in the source, no probe needed to find it: **the old wizard's own step
1 answer, nationality, plays zero role in which visa it recommends**, a structural fact about the
old funnel by itself, independent of any comparison to the engine).

"Agree" here means: if the old funnel named a product, the engine reached `SUPPORTED_CANDIDATES`
and that exact code is among its candidates; if the old funnel referred to a human (no product
named), the engine also did not confidently name a `SUPPORTED_CANDIDATES` product. Given Finding 1,
twelve of twelve engine verdicts are the constant BRIDGING-noise `HUMAN_REVIEW_REQUIRED` described
above — read the "agree" column together with that finding, not as twelve independent business
disagreements about which visa fits.

| #   | Input (purpose / months / budget)      | Old funnel recommends                               | Old funnel alternatives | Engine state                                                                                                                 | Agree?           | Characterization                                                                                                                                                                             |
| --- | -------------------------------------- | --------------------------------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | work_remote / 6 / mid                  | **E33G**                                            | E23-FREELANCE, C1       | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | No               | Old funnel confidently names a real, priced product (E33G exists on both sides); engine's verdict is Finding-1 noise, uninformative either way.                                              |
| 2   | investor / 12 / under_50m              | _(referral — old funnel's own budget hard-exclude)_ | —                       | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | Yes (both refer) | Coincidental agreement — the engine never actually reasoned about investment capital; it never got that far.                                                                                 |
| 3   | investor / 12 / over_500m              | **E33G**                                            | D12, E28A               | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | No               | Same as #1 — a real shared product (E28A, the one Investor product the engine can currently sell) buried under noise.                                                                        |
| 4   | work_employee / 24 / mid               | **E23**                                             | C18, C22A               | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | No               | E23 exists on both sides; C18/C22A are Finding-2 old-funnel-only codes regardless.                                                                                                           |
| 5   | family / 12 / mid                      | **E31**                                             | —                       | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | No               | E31 is a Finding-2 old-funnel-only code — even with clean facts the engine cannot land on bare `E31`, only one of nine `E31A`–`E31J` (no `E31I`), which the old funnel cannot ask which one. |
| 6   | long_tourism / 2 / under_50m           | **B1**                                              | C1, C2                  | HUMAN_REVIEW_REQUIRED (BRIDGING noise); **control run with onshore-status supplied → NEEDS_INPUT, not SUPPORTED_CANDIDATES** | No               | Even past Finding 1's noise, three facts are not enough to reach a supported B1/C1/C2 — consistent with `GROUND.md`'s ~50-question measurement.                                              |
| 7   | long_tourism / 8 / mid                 | _(referral — old funnel's own >6mo hard-exclude)_   | —                       | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | Yes (both refer) | Coincidental, same caveat as #2.                                                                                                                                                             |
| 8   | retirement / 60 / over_500m            | **E33E**                                            | E33F                    | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | No               | Shared code (E33E), buried under noise; `secondhome.passive_monthly_income_usd` DOES gate E33E in the real pack (Finding 3, corrected) — `build_shadow_facts()` just never sets it.          |
| 9   | student / 12 / under_50m               | **E30A**                                            | C22A                    | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | No               | Shared code; C22A is old-funnel-only.                                                                                                                                                        |
| 10  | other / 6 / mid                        | _(referral — old funnel's own catch-all)_           | —                       | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | Yes (both refer) | Coincidental, same caveat as #2.                                                                                                                                                             |
| 11  | work_remote / 1 / under_50m            | **C1**                                              | C2, E23-FREELANCE       | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | No               | Shared code (C1) buried under noise; E23-FREELANCE is old-funnel-only.                                                                                                                       |
| 12  | work_remote / 6 / mid, nationality=IRN | **E33G** (identical to #1)                          | E23-FREELANCE, C1       | HUMAN_REVIEW_REQUIRED (BRIDGING noise)                                                                                       | No               | Confirms nationality is a no-op for the old funnel — row is byte-identical to #1 except the discarded input.                                                                                 |

## Part 2 — old engine 2 (`VisaOracleService.recommend_visas`) vs the signed engine, endpoint-level

Team-lead's sharpened ask: hit `POST /api/v1/visa-oracle/recommend` and `POST /api/visa-oracle/evaluate`
directly with the same facts, and classify each disagreement into one of four kinds — (a) old
offers a product the signed engine would abstain on [the dangerous one], (b) old offers a
_different_ product than the signed engine, (c) old asserts one answer where the signed engine
returns two candidates, (d) old is silent where the signed engine has an answer [harmless].

**Method, and the one blocker reported honestly rather than routed around**: `run_evaluation()`
(the real orchestration behind `/evaluate`) requires a live `asyncpg.Pool` — pack-binding
resolution, a retention gate, and persistence all touch the database. This session has no
production DB access and no local DB carrying the visa-engine schema (see Part 1's Method). Per
the instruction to say so and stop rather than manufacture a shape: I did not fabricate a DB. What
I did instead, and disclose plainly: `evaluate_path.py`'s own docstring on
`apply_public_policy_adapters()` states it is "kept in one pure helper" specifically "to prevent
offline evidence tools from silently drifting away from the endpoint" — i.e. the module is
designed for exactly this kind of offline replay. This probe therefore runs `evaluator.evaluate()`
(the real engine, real signed PRODUCTION pack) followed by the real, unmodified
`apply_public_policy_adapters()` — the full decision-shaping logic `/evaluate` runs — while
disclosing what is skipped: DB-backed pack-binding/retention resolution (assumed to succeed against
the same real pack used throughout), price-quote attachment, and persistence. None of the skipped
parts change `decision.state` or `decision.candidates`, which is what the four-kind taxonomy is
about. `VisaOracleService.recommend_visas()` needed no such workaround — it is genuinely pure
(no DB, no LLM, scores against the on-disk PricingService JSON directly).

Facts mapping (`QuizAnswers` → engine `ApplicantFacts`, honestly, per the same instruction):
`nationality` → `person.nationalities` when 2-letter (a 3-letter/free-text value degrades to
UNKNOWN rather than guessed — `QuizAnswers.nationality` is an unaudited free string in this old
surface, unlike `match_tree`'s ISO-3 select). `purpose` (7 values, exhaustive, no "other" bucket)
→ `intent.purposes` via a direct 1:1 map (visit→TOURISM, work→EMPLOYMENT, invest→INVESTMENT,
retire→RETIREMENT, digital_nomad→REMOTE_WORK, family→FAMILY, study→STUDY). `duration` (4 buckets)
→ `intent.stay_days` via the SAME `DURATION_THRESHOLDS` the old service itself scores against, so
both doors judge the identical semantic duration. **`family` (bool: "bringing a spouse or
dependents") is deliberately NOT mapped onto any engine fact** — `family.relation_to_sponsor` asks
which specific relation the applicant has _to an existing sponsor_, a different question entirely
from "is a companion coming with me." No honest mapping exists; reported as its own finding per the
instruction, not forced.

Companion script: `research/visa/2026-08-24-two-endpoint-divergence-probe.py`.

### Results

Running the same eight purpose/duration/family combinations that feed `recommend_visas()` through
`build_quiz_facts()` + `evaluate()` + `apply_public_policy_adapters()` reproduced **Finding 1
exactly, via a completely independent facts adapter** — all eight land on `HUMAN_REVIEW_REQUIRED`
with the identical four BRIDGING reasons. This independently corroborates that Finding 1 is a
property of the real production pack's rule authoring (an unscoped `on_unknown: HUMAN_REVIEW` on a
single always-relevant-catalogue-wide product), not an artifact of one specific adapter
(`build_shadow_facts()`); a second, differently-written adapter hits the identical wall.

To get past that noise and see what the four-kind taxonomy actually asks for, one additional fact
was supplied on a control pass — `immigration.currently_in_indonesia = KNOWN(false)` (the same
control technique as Part 1) — for all eight cases. Result: **all eight flip to `NEEDS_INPUT`**,
zero `candidates`, zero `review_reasons`, 3 `missing_facts` each. Not one of the eight reaches
`SUPPORTED_CANDIDATES` even once four semantically-clean facts are supplied.

| Purpose                                                | Old door top pick (score)               | Engine, raw (4 QuizAnswers facts) | Engine, +onshore-status control | Kind    |
| ------------------------------------------------------ | --------------------------------------- | --------------------------------- | ------------------------------- | ------- |
| visit / short                                          | C1 Tourism (5.5)                        | HUMAN_REVIEW_REQUIRED (BRIDGING)  | NEEDS_INPUT                     | **(a)** |
| work / medium                                          | Working KITAS (7.5)                     | HUMAN_REVIEW_REQUIRED (BRIDGING)  | NEEDS_INPUT                     | **(a)** |
| invest / long                                          | Investor KITAS 2y (7.5)                 | HUMAN_REVIEW_REQUIRED (BRIDGING)  | NEEDS_INPUT                     | **(a)** |
| retire / permanent, +spouse                            | Retirement KITAS (4.0)                  | HUMAN_REVIEW_REQUIRED (BRIDGING)  | NEEDS_INPUT                     | **(a)** |
| digital_nomad / medium                                 | E33G Remote Worker (5.5)                | HUMAN_REVIEW_REQUIRED (BRIDGING)  | NEEDS_INPUT                     | **(a)** |
| family / long, +spouse+children                        | Dependent 2y (4.5)                      | HUMAN_REVIEW_REQUIRED (BRIDGING)  | NEEDS_INPUT                     | **(a)** |
| study / medium                                         | C22A&B Internship 180d (5.5)            | HUMAN_REVIEW_REQUIRED (BRIDGING)  | NEEDS_INPUT                     | **(a)** |
| visit / short, +spouse (garbage-vs-family-bonus probe) | C1 Tourism (5.5, unchanged by `family`) | HUMAN_REVIEW_REQUIRED (BRIDGING)  | NEEDS_INPUT                     | **(a)** |

**8 of 8: kind (a) — the dangerous one.** `recommend_visas()` has no referral/abstention branch at
all (unlike `match_tree.recommend_visa()`, which refers on three explicit conditions); reading its
full body confirms it always returns whatever scores highest from the matched category, never an
empty/"talk to a human" result. Paired against an engine that abstains (`HUMAN_REVIEW_REQUIRED` or
`NEEDS_INPUT`) on every one of the same eight inputs, kind (a) is not a tail case here — it is the
only kind observed. Zero (b)/(c)/(d): the engine never once names a confident product to disagree
about, and the old door never once stays silent.

**The honest caveat, stated because it matters for how much weight this carries**: 8/8 is measured
against facts adapters that populate only 3–4 of 45 engine facts (this endpoint-level surface has
even less to work with than the full `/visa-oracle` interview, which per `GROUND.md` asks ~50
questions and still only reaches 29/38 products). A caller who fed the signed engine the full
interview's worth of facts would likely see some of these eight resolve to genuine
`SUPPORTED_CANDIDATES` — meaning the true rate of kind (a) under full information is probably lower
than 8/8, not higher. What does NOT improve with more facts, and is measured independently of this
caveat: Findings 2 and 3 above (catalogue-code mismatches, vocabulary gaps) are structural, not
fact-starvation artifacts.

## Answer to the assignment's central question

**Yes, both old engines diverge from the signed one, and it is now measured, not merely possible by
construction.** Old engine 1 (`match_tree.py`, live behind `/visa/match`) diverges on three
independent, structural axes: (1) the SHADOW-MATCH audit pipeline built to compare them cannot
currently produce a usable comparison at all — every one of 12 representative inputs lands on
`HUMAN_REVIEW_REQUIRED` for the same pack-authoring reason (Finding 1); (2) seven old-funnel product
codes and 25 engine product codes have no counterpart on the other side (Finding 2); (3)
`budget_band` has no _generic_ engine-side fact, and the specific purpose-scoped facts that do exist
(`investment.*`, `secondhome.*`) are unwired by the adapter or, for `E33G`'s savings step, absent
from the pack entirely (Finding 3, corrected). Old engine 2 (`VisaOracleService.recommend_visas`,
reachable but currently orphaned from any live UI) diverges even more starkly at the endpoint level:
using team-lead's own four-kind taxonomy, **8 of 8 representative inputs are kind (a)** — the old
door confidently names a specific product while the signed engine abstains — with zero (b)/(c)/(d)
observed, though the honest caveat (Part 2's close) is that this rate is measured against a
facts-starved adapter and would likely fall, not rise, under the full interview's richer fact set.
None of this required forcing an input into a mapping it could not honestly bear — where a mapping
was ambiguous or absent (`family`, the generic budget concept), that absence is reported as its own
finding. This is not the "clean, no-divergence" case; a clean result would have been reported just
as plainly if that were what running the code actually showed.

## What this does not claim

- Not claimed: what real production traffic through `/visa/match` or `/api/v1/visa-oracle/recommend`
  actually produces today — no production DB access from this session (see Method, both parts).
- Not claimed: that Finding 1 / Part 2's 8/8 is the _only_ or the _permanent_ rate of divergence —
  both are measured against facts-starved adapters (3–4 of 45 engine facts populated); a fuller fact
  set would likely change the mix, per each part's own caveat. What does not change with more facts:
  Findings 2–3 (catalogue-code mismatches, vocabulary gaps) are structural.
- Not claimed: that `/api/v1/visa-oracle/recommend` is "the public funnel's decision" in the sense
  team-lead's message implied — it is a live, public, unauthenticated endpoint, but no shipped page
  currently calls it (see the disambiguation table at the top). The actually-public, indexed
  `/visa/match` page runs through Old engine 1, not this one. Both pairings are measured above so
  this distinction does not have to be resolved to answer the question.
- Not touched: whether `VISA_ENGINE_MATCH_MODE`/`VISA_ENGINE_EVALUATE_MODE` are currently `SHADOW`
  or `OFF` in the live Fly deployment — that is a Fly-secrets read, `operator[secret]`, outside this
  session's access and outside a read-only mandate's scope regardless.
