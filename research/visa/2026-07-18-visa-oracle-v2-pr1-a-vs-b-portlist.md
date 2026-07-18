---
date: 2026-07-18
domain: visa
client_case: none — engineering follow-up to the Visa Oracle v2 PR1 twin-PR adjudication (ADOPT_A, Zero 2026-07-18)
sources:
  - "apps/backend-rag/backend/services/visa_engine/ @ origin/main f73cbb4a (tree A, PR #2654, merged)"
  - "branch agent/nuzantara/mouth/visa-engine-pr1-0718 (tree B, PR #2718, closed — kept as PR3 seed)"
  - "research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-concretization.md (Codex 8-gap list, §4)"
adversarial_review: glm
adversarial_review_detail: "GLM 5.2 (claude-glm --print) report-level refutation pass 2026-07-18 (see §Adversarial review); plus empirical confirmation of every live-gap claim via TDD guilt tests that must FAIL against unmodified main code before each hotfix commit (pre-fix failure output recorded in the hotfix PR body)"
---

# Visa Oracle v2 engine PR1 — A (main, PR #2654) vs B (closed PR #2718) port-list

**Purpose**: after Zero's ADOPT_A adjudication (tree A merged to main as PR #2654; tree B's PR #2718
closed, branch kept as the PR3 evaluator seed), this report answers: (a) which correctness gaps are
LIVE on main and need an immediate hotfix, (b) which B-only hardenings have proven incremental value
worth porting (PR1b), (c) whether A carries B's import-cycle problem, (d) what belongs to the PR3
seed instead.

**Method**: read A via `git show origin/main:apps/backend-rag/backend/services/visa_engine/{compiler,models,enums,fact_registry,errors}.py`
(+ `contracts/*.schema.json`), and B via the closed-branch worktree files
(`{compiler,models,enums,fact_registry,_types}.py`), side-by-side, invariant by invariant.
Analysis lane: Sonnet subagent (read-only), 2026-07-18.

**Legend**: A-has/B-has = behavior exists and is enforced. DELTA = what needs to change on top of A
(now on main). Severity: P0 wrong-legal-answer, P1 correctness, P2 robustness, P3 style.

## Dimension 1 — Compiler invariants

| #   | Invariant                                                        | A-has                                                                                                             | B-has                                                                      | DELTA                                                                                     | Severity        |
| --- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | --------------- |
| 1   | Recursive literal-type validation vs FactSpec                    | YES — `_check_fact_literal_kind` + `_safe_ast_nodes`/`iter_nodes`                                                 | YES — `_validate_condition_tree` + `_check_literal_type` (`type(x) is T`)  | none                                                                                      | —               |
| 2   | Canonical `YYYY-MM-DD` on **rule-condition literals**            | **NO** — dates are `FactValueKind.STRING`, no shape check; JSON schema (`EqCondition.value`) is bare `anyOf[bool,int,str]` | **YES** — `_CANONICAL_ISO_DATE_RE.fullmatch` before `date.fromisoformat` | **Port B's canonical-date-regex check** into A's literal-kind checker, gated on date-typed facts | **P0**          |
| 3   | Set-member type validation (`intersects`/`contains_all`)         | YES                                                                                                               | YES (`_check_set_member_types`)                                            | none                                                                                      | —               |
| 4   | `BetweenCondition` lower ≤ upper                                 | **YES** — `_check_between_bounds`                                                                                 | NO                                                                         | none (A already ahead)                                                                    | n/a             |
| 5   | Ordering ops rejected on bool AND opaque enum strings            | PARTIAL — bool only                                                                                               | PARTIAL — bool only                                                        | **Neither has it — new check needed**, not portable from B                                | P1 (new finding) |
| 6   | Unicode NFC over signed payload                                  | **YES** — `_check_utc_and_nfc` walks entire payload tree                                                          | NO                                                                         | none (A already ahead)                                                                    | n/a             |
| 7   | `commercial_only` banned in legal stages                         | YES                                                                                                               | YES                                                                        | none                                                                                      | —               |
| 8   | Presence-only ELIGIBILITY ban                                    | **BANNED**                                                                                                        | allowed (no check)                                                         | none (A already ahead)                                                                    | n/a             |
| 9   | SUPPORT `covered_purposes` vs product (incl. GLOBAL intersection) | **YES, harder-won than B ever had**                                                                               | NO                                                                         | none (A already ahead)                                                                    | n/a             |
| 10  | Duplicate rule_id/product_version_id/**product_code**/source_id  | **PARTIAL — missing product_code dedup**                                                                          | YES, all 4                                                                 | **Port product_code duplicate check** into `_check_unique_ids`                            | **P1**          |
| 11  | Dangling product/source refs                                     | YES, all 3                                                                                                        | YES, all 3                                                                 | none                                                                                      | —               |
| 12  | `protected.environment == payload.environment`                   | YES, defensively                                                                                                  | YES, plainly                                                               | none (A more robust)                                                                      | n/a             |
| 13  | `required_facts == collect_fact_paths(when)`                     | YES                                                                                                               | YES                                                                        | none                                                                                      | —               |
| 14  | AST/rule/product limits (12/256/4096/256)                        | YES, **plus** revalidate-before-check + safe-call crash-proofing vs cyclic trees                                  | YES numeric limits, **no RecursionError guard**                            | Carry A's safe-call pattern forward                                                       | P2              |
| 15  | Semantic `STAGE_ORDER` vs alphabetical                           | **N/A by design** — A defers `CompiledRulePack`/`rules_for()` to PR3                                              | YES — `RuleStage.order`/`STAGE_ORDER`                                      | **Not PR1b — belongs in PR3 seed**                                                        | n/a for PR1b    |

## Dimension 2 — Models strictness

| Item                                            | A                                                                                                                                     | B                                                                                             | DELTA                                                              | Severity                       |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------ |
| StrictInt                                       | Comprehensive (every int field is `Field(strict=True)`)                                                                                | Comprehensive                                                                                  | none                                                               | —                              |
| StrictBool                                      | **5 gaps**: `ExtensionPolicy.allowed`, `ClockPolicy.available`, `VisaProductVersion.public_catalog`, `Rule.safety_critical`, `Outage.retryable` — plain `bool` | Comprehensive (`StrictBool` everywhere via `_StrictModel`)                                     | Add `Field(strict=True)`/`StrictBool` to these 5                   | P2 (P1 for `safety_critical`)  |
| Alias-only wire names (`populate_by_name` off)  | **2 exceptions**: `TimeRange` + `ApplicantFactsData` set `populate_by_name=True`                                                       | Zero exceptions — `_StrictModel` hardcodes `False`                                             | Flip those 2 classes to `False`                                    | P2                             |
| `KnownDate` strict vs coercive                  | **Immune by construction** — `value: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]`, never Pydantic's `date` type              | Vulnerable — `value: date`, no `strict=True`, accepts epoch-int/midnight-datetime              | none (A already safe, different architecture)                      | n/a                            |
| GLOBAL + `product_version_ids=null`             | Accepts explicit null — ~~hole~~ **deliberate design** (schema round-4/5 correction; see §Post-implementation correction)              | Same acceptance + cosmetic output-serializer                                                   | ~~fix needed~~ **NONE — refuted at implementation**                | ~~P1~~ n/a                     |
| Quote↔candidate integrity on `Decision`         | **MISSING** — 5-state shape checks only, no cross-check                                                                                | **YES** — `_check_quotes_reference_real_candidates` (F6): product_version_id membership + product_code match | **Port B's F6 check**                                              | P1                             |

## Dimension 3 — Structure (import cycle)

**A has NO import cycle.** Verified graph: `enums.py`/`errors.py` are dependency-free leaves;
`ast.py` and `fact_registry.py` each import only from those leaves (never each other, never
`models.py`); `models.py` sits above both. Clean DAG:
`{enums,errors} → {ast,fact_registry} → models → {compiler,schema_export}`.

B's `_types.py` cycle-break existed because B's PR1-scoped `fact_registry.py` already wired
`derive()` against `models.ApplicantFacts`, creating two real cycles CodeQL's
`py/unsafe-cyclic-import` flags. A avoided this entirely by deferring that wiring to PR3 — its
narrower PR1 scope is what kept it acyclic. **CodeQL would not flag A today.** Note for the PR3
seed: when the evaluator wires `FactRegistry.derive()` to `ApplicantFacts`, A may hit the same
cycle B pre-solved — B's `_types.py` pattern is worth carrying forward there, not into PR1b.

## Dimension 4 — The 8 Codex gaps: present in A?

| #   | Gap                                                                        | Status in A                                                                                                                                                                |
| --- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | ELIGIBILITY presence-only compiles                                          | **ABSENT** — banned                                                                                                                                                          |
| 2   | SUPPORT purposes not checked vs product                                     | **ABSENT** — checked, incl. GLOBAL intersection                                                                                                                              |
| 3   | Literal validation Python-types-only (`marital_status="ALIEN"` / 3-letter country) | **PARTIALLY PRESENT** — enum-closed facts (marital_status etc.) caught via `allowed_values`; country-code facts have zero format/length/ISO check → **still live for country codes** |
| 4   | Between bounds never validated                                              | **ABSENT** — checked                                                                                                                                                         |
| 5   | Ordering rejected only for booleans, not enum strings                       | **PRESENT** — live gap (and B has it too — not portable)                                                                                                                     |
| 6   | NFC validation omitted                                                      | **ABSENT** — comprehensive walker exists                                                                                                                                     |
| 7   | KnownDate coercive parsing (int 0 / midnight datetime)                      | **ABSENT** — architecturally immune (str+regex, no `date` type)                                                                                                              |
| 8   | GLOBAL + null product_version_ids accepted                                  | ~~PRESENT~~ → **REFUTED at implementation** — deliberate, documented design in A (see §Post-implementation correction)                                                        |

## Executive summary

**(a) Port items and severity**: 5 concrete ports from B into A — canonical-date-literal check
(**P0**), product_code dedup check (**P1**), StrictBool on 5 fields esp. `safety_critical`
(**P1/P2**), `populate_by_name=False` on 2 classes (**P2**), quote↔candidate integrity validator
(**P1**) — plus 2 net-new checks neither implementation has (ordering-on-enum-strings, real
GLOBAL-null fix, both **P1**), plus 1 forward-looking note for the PR3 seed (STAGE_ORDER).

**(b) Which of the 8 Codex gaps are PRESENT-IN-A (live on main, urgent)**: **#5** (ordering ops
only reject booleans, not enum-ish strings) is fully live on main. **#3** is partially live
(country-code facts only — enum-closed facts like marital_status are already protected). **#8**
was initially assessed live but **refuted at implementation** — deliberate, documented design
(see §Post-implementation correction). The other 5 (#1, #2, #4, #6, #7) are already fixed on main.

**(c) Import cycle**: A has none — verified the full cross-module import graph is a clean DAG.
CodeQL would not flag main today. B's `_types.py` cycle-break was needed only because B wired
`FactRegistry.derive()`→`ApplicantFacts` inside PR1; A deferred that to PR3.

**(d) Recommendation**: port only the P0/P1 correctness gaps, not everything. Of ~15
dimension-1/2 items compared, the large majority are either equivalent or already _better_ on A
(NFC walker, SUPPORT/GLOBAL semantics, presence-only ban, crash-proofing, environment-check
defensiveness) — porting those would be pure churn against code that's already ahead. The real
PR1b scope is the 5 ports + 2 net-new checks above, each with a concrete exploit shape (malformed
date literal → wrong legal comparison; duplicate product_code → wrong product resolved;
orphan/mismatched quote → wrong price shown; enum-string ordering → nonsensical rule silently
accepted; GLOBAL-null → schema-violating pack accepted). Skip the P3/style-only diffs. The B-only
`STAGE_ORDER`/`CompiledRulePack` material should ride with the **PR3 seed** (strong-Kleene
evaluator + truth-table tests), not PR1b.

## Shipping plan (binding order, Zero 2026-07-18)

1. **Hotfix PR (first, before everything)** — the live-on-main correctness holes: canonical-date
   literal check (P0, same class as the Codex gaps even though surfaced by this comparison),
   ordering-ops-on-enum-strings (#5), country-code format (#3 partial), and KnownDate calendar
   validity (P0, surfaced by the GLM refutation pass). One atomic commit per gap, guilt+innocence
   tests in the same commit, TDD: each guilt test must FAIL against unmodified main code first
   (empirical confirmation of the claim — recorded in the PR body). GLOBAL+explicit-null (#8) was
   in the original scope but refuted at implementation (see §Post-implementation correction).
2. **PR1b port-list** — the remaining proven-value ports: product_code dedup (P1), quote↔candidate
   integrity F6 (P1), StrictBool ×5 (P1/P2), `populate_by_name=False` ×2 (P2).
3. **PR2** — signed-bundle loader re-adapted to A's API; 3-seat adversarial verify REDONE on the
   adaptation (the old verdict on B's API is void).
4. **PR3** — evaluator from the strong-Kleene seed (branch `agent/nuzantara/mouth/visa-engine-pr1-0718`,
   kept alive by ruling), carrying STAGE_ORDER/CompiledRulePack and, if the derive() wiring creates
   the known cycle, B's `_types.py` leaf-module pattern.

## Adversarial review

**Seat**: GLM 5.2 (`claude-glm --print`), cross-family refutation pass, 2026-07-18. The reviewer
read the REAL code of both trees (A = `origin/main`, B = commit `98c112ed`) and ran empirical
probes against A's actual models with Pydantic 2.12.5 — it did not review the report text alone.
Verbatim transcript retained by the orchestrating session; verdicts summarized here.

**Claim-by-claim verdicts**:

1. _A has no import cycle (clean DAG)_ — **CONFIRMED**. Import graph re-read module by module: no
   `TYPE_CHECKING` blocks, no function-local sibling imports in A; `fact_registry` doesn't even
   define `derive()` (references to `models` are docstring prose). B's cycle is real
   (`fact_registry:67` TYPE_CHECKING + `:333` runtime function-local import).
2. _Gaps #5 and #8 live; #8 needs `mode="before"`_ — **CONFIRMED (both)**. #5: `compiler.py:713-720`
   rejects ordering only on `FactValueKind.BOOLEAN`. #8 proven empirically: `{"scope":"GLOBAL"}`
   and `{"scope":"GLOBAL","product_version_ids":null}` both parse to `None` and are both accepted;
   only a before-validator can distinguish explicit null from absent key in Pydantic v2.
3. _KnownDate str+regex "architecturally immune"_ — **CONFIRMED literally, but half-truth flagged**:
   immune to type coercion (int 0 / datetime / compact string all rejected, proven empirically),
   **but the regex is calendar-blind — `"2020-13-45"` is ACCEPTED by A** and would be rejected by
   B's `date.fromisoformat`. A and B have dual blind spots; the report's implicit "A strictly
   better" was an overclaim.
4. _Port-list severities_ — 4 CONFIRMED (canonical-date P0, StrictBool-on-`safety_critical` P1 —
   plain `bool` empirically accepts `1/0/"true"/"yes"/"on"`, populate_by_name P2,
   quote↔candidate P1); product_code-dedup gap CONFIRMED but **severity P1 not contractual**
   (`rule-pack.schema.json` does not declare product_code unique; two versions sharing a
   product_code may be legitimate versioning) — P2 more defensible unless downstream resolves by
   product_code.
5. _Phantom-citation hygiene_ — PASS: every cited symbol verified on disk. One refinement: #5's
   real scope is STRING facts **with closed `allowed_values`** (free-text lexicographic ordering
   is not inherently wrong); one underspecification: B's F6 is a **model** validator on
   `Decision`, not a compiler check — the port touches `models.py`.

**OVERALL: SOUND** — all four load-bearing claims verified against real code; defects are
second-order and do not change the PR1b recommendation.

**Dispositions (orchestrator)**:

- **KnownDate calendar-blindness → promoted to hotfix Gap E (P0 family)**: add
  `date.fromisoformat` round-trip validation to `KnownDate.value`; guilt tests `2026-13-45`,
  `2026-02-30`; innocence `2026-02-28`, `2024-02-29` (leap year). Dispatched to the hotfix
  implementer with the same TDD fail-first discipline (the guilt test failing pre-fix is the
  independent confirmation of the reviewer's empirical claim — W65: even the refuter is verified).
- **#5 design kept fail-closed** (ordering only on INT and date-format STRING, stricter than the
  reviewer's minimum of "reject closed-enum strings"): for a legal engine the default is to reject
  semantically ambiguous comparisons; relaxing later is cheap, un-rejecting compiled nonsense is
  not. Recorded in the hotfix PR body.
- **product_code dedup downgraded P1→P2 for PR1b**, unless PR3's resolution path turns out to key
  on product_code (re-evaluate there).
- **F6 port note for PR1b**: implement as `Decision` model validator per B's shape
  (`_check_quotes_reference_real_candidates`), file `models.py`.

## Post-implementation correction (Gap C / Codex #8) — claim REFUTED by the implementer

The hotfix implementer, following the mandated TDD fail-first discipline, investigated Codex gap
**#8** (GLOBAL rule + explicit `product_version_ids: null` accepted) before fixing it and found the
premise does not hold against this repository's actual, intentional state. Three evidence points,
each independently re-verified on disk by the orchestrating session:

1. `contracts/contract.schema.json` (Rule `allOf` block) types `product_version_ids` as
   `{"type": "null"}` when `scope` is GLOBAL — it constrains the value, it does **not** forbid the
   key's presence. `schema_export.py`'s docstring documents this as a deliberate round-4/5
   correction away from the spec's original "forbid presence" text.
2. Pydantic always re-serializes the declared field: `pack.model_dump(mode="json")` emits
   `"product_version_ids": null` for every GLOBAL rule, and `compiler.py::_revalidate_structurally`
   (the bypass-proof serialize→reparse invariant) feeds exactly that shape back through the model
   on **every** `compile_rule_pack` call — rejecting explicit null would break every valid GLOBAL
   rule.
3. `test_schema_contracts.py::test_global_scope_without_product_version_ids_accepted` is an
   existing, named, passing test that constructs `Rule(scope="GLOBAL", product_version_ids=None)`
   and asserts acceptance — the behavior is encoded as intentional.

**Consequence**: the original Codex #8 was written against the spec *text*; A deliberately and
documentedly diverged from that text. No fix shipped; rows above amended. Note the layering of
verification this demonstrates: the report claimed the gap, the GLM refutation pass "confirmed" it
(it proved the *acceptance behavior* empirically — true — but inherited the report's framing that
acceptance = defect), and only the implementer's contract-semantics check caught that the premise
itself was stale (W90 family: the ground truth had moved — the schema was corrected in round 4/5
after the gap list was written).

**Hotfix as actually shipped** (branch `agent/nuzantara/mouth/visa-engine-hotfix-0718`): Gap A
(date literals, P0) `2dc65cad7` · Gap B (ordering ops fail-closed, P1) `5d232854e` · Gap D
(country-code shape, P1) `0fb7a7788` · Gap E (KnownDate calendar validity, P0 — surfaced by the
GLM pass above) `456e555b1`. Gap C: no change, this section is the record. Suite: 258 passed
(baseline 235, +23 guilt/innocence tests), re-run by both implementer and orchestrator.
