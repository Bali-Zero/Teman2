---
date: 2026-08-23
domain: visa
client_case: none — Visa Oracle v2 engine audit, catalogue-wide sweep across all 38 products
sources:
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-012.source.json
  - apps/backend-rag/backend/services/visa_engine/enums.py
  - apps/backend-rag/backend/services/visa_engine/fact_registry.py
  - apps/backend-rag/backend/services/visa_engine/evaluator.py
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.tsx
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/page.tsx
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/shadow-parity.ts
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/preview-adapter.ts
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/gold-oracle-baseline.ts
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.ts
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/shadow-client.ts
  - apps/backend-rag/backend/scripts/visa_engine/probe_evaluate.py
  - .claude/skills/modus/PENDING-ARMS.md (parity-telemetry row, PR #4671)
  - https://github.com/Bali-Zero/Teman2/pull/4671
  - memory lesson_presence_value_check_and_effect_on_outcome_are_three_axes_2026_08_23
adversarial_review: codex
---

# Catalogue-wide sweep — "name promises a restriction the rules never test"

Session capture, author v2-d12. Ported verbatim from working scratch per team-lead's instruction
(2026-08-23) that the sweep's findings — expensively obtained, no other document carries the
full per-product verdict table — should not live only in a session-scoped scratchpad path that
disappears when the session ends. Nothing below has been strengthened, re-verified, or
re-interpreted in the port; hedges, uncertainty markers, and "not run"/"could not resolve"
statements are preserved exactly as written during the original investigation, per team-lead's
explicit instruction not to upgrade any hedge on the way into the repo.

Live pack `rulepack-prod-012.source.json` (sequence 12, version 2026.8.20), 38 products.
Read-only investigation throughout — no pack edits were made in the course of this sweep, no
mouth-surface code was touched. Companion to an earlier, narrower pass (the "9-rule seq-6
dropped-review-rules audit," not itself committed as a repo file — it lives in the originating
session's working scratch and is referenced here only for context, not as a citable source);
this catalogue-wide sweep is the follow-on team-lead asked for after a third accidental instance
of the same failure shape (E31C) turned up in one day.

## SEVERITY CORRECTION (added after initial delivery, re-verified independently)

**None of the findings below reach a public client's screen today — conditional on the deployed
mode, see correction.** Verified verbatim against
`apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.tsx:581-596`: in
`mode === "SHADOW"`, the real engine response is fetched, compared against a local preview for
parity telemetry, and then **discarded** — the function returns
`buildShadowOutcome({ code: "SHADOW_VERIFICATION_ONLY", ... })`, not the engine's candidates and
not the preview's. Every finding in this document (E31D's unconstrained rule, E30E/E30F's
aliasing, E23's missing statutory gates, the 4 partial `known`-only failures) is real, is
computed on every completed interview, and — **if the deployment is actually running in
`SHADOW` mode** — is not shown to a public applicant. These are defects waiting at the ENFORCE
boundary, not defects operating in front of clients today — the Ranking section below is
corrected on this basis.

**[CORRECTED per codex adversarial review, 2026-09-02]** This claim is conditional, not
verified from the checkout. `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/runtime-mode.ts`
shows `resolveVisaOracleMode()` defaults an unset/invalid `NEXT_PUBLIC_VISA_ORACLE_MODE` to
`"ENGINE"` in production (`PREVIEW` is force-downgraded to `ENGINE` in production too; only
`test` NODE_ENV defaults to `PREVIEW`). `modeUsesEngine()` treats both `ENGINE` and `SHADOW` as
engine-backed, but only `SHADOW` discards the candidates via `buildShadowOutcome`; `ENGINE` mode
returns the real candidates straight through. Nothing in this repo checkout records which mode
is actually configured on the live deployment (that is an environment variable set outside
version control) — so "not live-client-facing today" holds only if `SHADOW` is what is actually
deployed, and this document does not establish that. Treat the severity framing below as
correct **conditional on the deployment's `NEXT_PUBLIC_VISA_ORACLE_MODE`**, not as independently
verified fact.

**One nuance beyond "shown to nobody," verified this pass:** `OracleShell.tsx` has a second
branch, `internalMode` (`page.tsx:16-22`, server-gated by a verified internal-access cookie —
`verifyInternalAccessToken`, unforgeable client-side, `force-dynamic` rendering). When
`internalMode` is true, the function returns `buildInternalPreviewOutcome(response, ...)` —
**the real engine candidates, not the SHADOW placeholder.** This path requires a server-verified
internal-access credential, so it is not reachable by a public applicant — but it means an
authorized internal tester (staff exercising the internal preview) DOES see the raw, broken
candidate list today, including E31D unconditionally SUPPORTED. Worth knowing if anyone on the
team uses the internal-preview mode to sanity-check advice: it will currently show wrong
answers for at least E31D/E30E/E30F/E23.

**The parity-telemetry check, as requested — `shadowParityMatches` does NOT only compare
`state`.** Read `shadow-parity.ts` in full: it builds a `semanticProjection` of both outcomes
(engine and local baseline) covering the FULL candidate list — id/code/rank/name/legal status +
reasons/operational status + reasons/service status + reasons/price/timeline/documents — plus
missingInputs/reviewReasons/noPathReasons/alternatives/sources/nextSteps, then does a deep
`JSON.stringify` equality check. A shallow state-only check is refuted.

**But the more consequential finding is upstream of the comparator: the local baseline it
compares against essentially never predicts `SUPPORTED_CANDIDATES` at all.**
`preview-adapter.ts::buildPreviewOutcome` does exactly one of two things: (1) if the interview's
facts match one of a small, hand-curated set of "gold-oracle personas"
(`gold-oracle-baseline.ts`), it returns a pinned, hardcoded expectation — and its own doc
comment states, verified verbatim, that **every pinned persona predicts `HUMAN_REVIEW_REQUIRED`,
never `SUPPORTED_CANDIDATES`**; (2) for every other interview — i.e. essentially every real,
non-curated applicant — it falls back to `unavailablePreviewOutcome()`:
`state: "TEMPORARILY_UNAVAILABLE"`, zero candidates, an honest "no independent baseline
available" placeholder.

**Consequence for team-lead's original diagnostic question.** The hypothesis was "if E31D isn't
producing a steady stream of mismatches, either the preview has the same defect or the parity
check doesn't compare candidates." Neither branch is quite right: the parity check DOES compare
candidates (deeply), and the preview does not independently reproduce E31D's defect — it simply
never predicts SUPPORTED at all, for anyone. The practical result is the same telemetry
behavior team-lead was probing for, but for a different reason: **`state: TEMPORARILY_UNAVAILABLE`
(baseline) can never JSON-equal `state: SUPPORTED_CANDIDATES` (engine)**, so ANY real applicant
who reaches a supported candidate list — through E31D's bug or through a completely correct
rule — mismatches by construction. A `visa_oracle_v2_parity_mismatch` event is therefore
expected on nearly every completed non-test interview that resolves to SUPPORTED_CANDIDATES,
and is **not currently a usable signal for "this specific candidate list is wrong"** — it fires
identically on a correct SUPPORT and a broken one. If the parity telemetry is ever meant to
catch a defect like E31D's, the gold-oracle persona set (or its underlying method) would need to
be extended to include personas that predict a real candidate list, not just the
disclosed-review-flag cases it currently covers. (This finding was subsequently written up as
its own PENDING-ARMS row and shipped as PR #4671 — see that row for the fuller, independently
re-verified trace, including the constructed disagreeing pair below.)

**The concrete disagreeing pair, constructed and traced — does it get caught?** Read
`buildShadowComparisonOutcome` (`engine-adapter.ts:848-852`, `origin/main`
`3f41c6b0294f04576fdd33480361aaba911454bb` at the time of this trace) — it calls the SAME
`buildValidatedOutcome` the real public render path uses, so the "engine" side of the comparison
is a complete, faithful mapping of `response.display.candidates` (id/code/rank/name/legal/
operational/service/decisionReasons/timeline/price/documents, `engine-adapter.ts:716-763`) —
nothing simplified or dropped there. Two things narrow what the comparison can actually
discriminate, though: `assumptions` and `pathsRemaining` are *injected into the engine-side
projection from the baseline itself* (`buildShadowComparisonOutcome(response, { assumptions:
visibleBaseline.assumptions, interviewBranchesRemaining: visibleBaseline.pathsRemaining })`) —
they can never disagree, by construction, not a real signal. `nextSteps` is similarly forced:
the gold-persona baseline deliberately reuses the literal `ENGINE_NEXT_STEPS` constant "so this
must match" (its own comment). Strip those out and the real discriminating fields, for the
narrow set of interviews that match a pinned gold-oracle persona, reduce to: `state` +
`reviewReasons` (code+sourceRefs) + `sources` + `outage`.

**The pair, concretely: an E31C/E31D-shaped interview (real engine returns
`SUPPORTED_CANDIDATES`, correctly or via the defect) vs. the local baseline for that same
interview.** Since gold-oracle personas ALL predict `HUMAN_REVIEW_REQUIRED` and NEVER
`SUPPORTED_CANDIDATES` (verified above), no interview that reaches a real candidate list —
right or wrong — can ever match a gold persona; it falls to `unavailablePreviewOutcome()`:
`state: TEMPORARILY_UNAVAILABLE`, `outage.code: "PREVIEW_FIXTURE_ONLY"`. The real engine's own
`TEMPORARILY_UNAVAILABLE` mapping uses `response.decision.outage?.code ?? "ENGINE_UNAVAILABLE"`
— a structurally different literal, so even a genuine double-outage coincidence would still
mismatch on `outage.code` alone. **Verdict: this exact pair is caught — it emits
`parity_mismatch`, not `parity_match`.** Team-lead's specific fear ("the E31C exclusion defect
would have logged `parity_match` for as long as it existed") does not hold for this defect
shape: a `SUPPORTED_CANDIDATES`-reaching interview cannot spuriously match the baseline,
because the baseline can only ever assert `HUMAN_REVIEW_REQUIRED` or
`TEMPORARILY_UNAVAILABLE`, never a candidate list of its own.

**What this changes and what it doesn't.** It refutes the sharpest form of the worry (a false
`parity_match` silently hiding this class of bug) — the check cannot go green for the wrong
reason here, because it structurally cannot go green on this axis at all for a non-gold-persona
interview. What stands, unchanged: the mismatch signal is uninformative noise for this whole
class, because it fires unconditionally on every `SUPPORTED_CANDIDATES`-reaching interview,
correct or defective — so nobody reviewing the SHADOW evidence ledger could ever have used "the
mismatch rate went up" as a signal that E31C/E31D/E30E/E30F/E23 specifically were wrong; the
rate has been elevated by design since the gold-oracle baseline was built, for reasons that have
nothing to do with candidate-list correctness.

**Dead-code note, re-verified independently:** `shadow-client.ts::sendShadowEvaluation` and
`SHADOW_EVALUATE_URL` — grepped the whole app excluding test files — have zero call sites
outside their own definition file. Confirmed, matches team-lead's find exactly. Not worth a PR
on its own, noted for whoever next touches that file.

## Controls run first, per team-lead's caution

Method must reproduce all 4 known-broken instances or the method itself is wrong, not the
pack. All 4 re-derived independently this session by scoping the live pack to each
`product_version_id` and reading the actual `when` JSON (not from memory):

- **E23** ("Working Visa") — 2 scoped rules, both check only
  `intent.purposes`/`work.employer_is_indonesian_entity`/`work.indonesian_work_sponsor_confirmed`/
  `investment.proposed_role`. Zero fact-path for RPTKA/KBLI-match/jabatan/prohibited-role
  anywhere in `enums.py`/`fact_registry.py`. **Fails at step 1.**
- **E30E** ("SEZ Education Visa") — 1 scoped rule (`el.e30e-student-support`). Zero fact-path
  for KEK-zone/institution-type. **Fails at step 1.** **[CORRECTED per codex adversarial
  review, 2026-09-02]** The original wording here said the rule "checks `sponsor.type in
  [EDUCATION, INDIVIDUAL]` only" — that undersold what the rule actually tests and is wrong as
  written. Verbatim `when` (`op: all`) has four conjuncts: `intent.purposes intersects
  [STUDY]`, `study.admission_confirmed == true`, `study.sponsor_confirmed == true`, AND
  `sponsor.type in [EDUCATION, INDIVIDUAL]`. The step-1 finding is unaffected by the
  correction — none of those four conjuncts is a KEK-zone/institution-type discriminator, so
  the qualifier the product name promises is still untested — but the rule is materially less
  permissive than "sponsor.type only" implied.
- **E30F** ("Student Exchange Visa") — 1 scoped rule (`el.e30f-student-support`). Zero
  fact-path for exchange-program-type. **Fails at step 1.** **[CORRECTED per codex adversarial
  review, 2026-09-02]** Same correction as E30E: the rule is not "`sponsor.type == EDUCATION`
  only" — verbatim `when` also requires `intent.purposes intersects [STUDY]`,
  `study.admission_confirmed == true`, and `study.sponsor_confirmed == true` before
  `sponsor.type == EDUCATION`. Step-1 finding unaffected: none of those four conjuncts tests
  exchange-program-type.
- **E31C** ("Family Visa — Child of Legal Mixed Marriage") —
  `el.e31c-mixed-marriage-parents`'s `when` is `purposes∩FAMILY AND relation_to_sponsor==PARENT
  AND family.sponsor_nationalities intersects [ID] AND family.marriage_registered==true`.
  Verbatim confirms team-lead's framing exactly: `family.sponsor_nationalities` has ONE slot
  and it only ever checks that the sponsor-parent is Indonesian. There is no second fact for
  "the child's other parent holds a foreign nationality" anywhere in the schema — the
  *mixed*-ness of the marriage, which is this product's entire reason to exist as distinct from
  E31F/E31G, is untestable. **Fails at step 1 on the WNA-parent axis** (the WNI-parent axis is
  real — `intersects [ID]` — which is exactly why this is a *partial* failure, not a total
  purpose-only one like E31D below).

**Controls passed, 4/4.** Proceeding.

## Method (team-lead's, applied per product)

1. Does a fact-path exist for the qualifier at all (`enums.py`/`fact_registry.py`)? No → stop,
   that is the finding.
2. If a fact exists: does any rule scoped to the product's `product_version_id` reference it?
   No → stop, that is the finding.
3. If referenced: with what operator? `known`/`exists` is presence wearing a constraint's
   clothing — not a real check. Only `eq`/`in`/`intersects`/`not_in`/`between` against a value
   counts.
4. Only for survivors of 1-3: is it consequential (live probe)? **Not run in this pass** — see
   "What step 4 would still need" below. Every survivor of steps 1-3 checked out on a real,
   non-trivial value comparison (a concrete list/enum/threshold, not a boolean truism), which is
   the signal team-lead's ordering exists to let a sweep stop before spending a live probe.

## Denominator

38 products total. 10 have no name-encoded restriction to test (generic/base products —
BRIDGING, C1, C2, C6, D1, D2, E28A, E30, E33 — plus D12, which carries a *different*, already
fully-audited defect from a prior pass, `investment.pt_pma_committed`, not re-litigated here).
**28 products carry a name-encoded qualifier and were examined.**

| Verdict | Count | Products |
|---|---|---|
| **Enforced** (real value-check on the qualifier) | 10 | A1, B1, E30A, E30B, E31A, E31F, E31G, E33E, E33F, **E33G** (guarded, see below) |
| **Unreachable** (no SUPPORT/ELIGIBILITY rule exists at all — qualifier moot, no admission path to guard) | 9 | E23U, E23V, E28B, E28C, E28D, E28F, E33A, E33B, E33C |
| **Broken — full** (SUPPORT fires, qualifier untested by any mechanism) | 4 | E23, E30E, E30F, **E31D** |
| **Broken — partial** (a real relationship/marriage check exists; the "…of ITAS/ITAP Holder" half of the name is tested only with `op: known`, i.e. presence not value) | 5 | E31B, E31C, E31E, E31H, E31J |

**"9 of 28 examined are broken (4 full + 5 partial), 9 more can't even be tested because
nothing supports them, 10 are genuinely enforced." Not "9 of 38" — 10 products carry no
name-encoded qualifier to test in the first place.**

## The worst instance found — new to this sweep, not part of the original 9-rule audit

**E31D ("Family Visa — Stepchild of Foreigner in Legal Mixed Marriage") — worse than any of
the 4 controls.** All three of its scoped rules, verbatim:

```
el.e31d-stepchild-support:      purposes∩FAMILY
el.e31d-step-parent-relation:   purposes∩FAMILY AND (purposes∩FAMILY)   <- duplicate nesting, no 2nd conjunct
el.e31d-sponsor-mixed-marriage: purposes∩FAMILY AND (purposes∩FAMILY)   <- same
```

Rule names promise a step-parent relationship check and a sponsor mixed-marriage check.
Neither exists — not weakly, not via `known` — the second and third rules' extra nesting
literally repeats the SAME single purpose conjunct instead of adding a real one. Step 1 also
fails structurally: at the time of this sweep, the `RelationType` enum had no `STEPCHILD` value
(matches an existing, already-flagged memory finding that E31D was "not correctable to rules as
currently constructed" — this sweep reproduces that mechanically rather than discovering it
fresh, and the citation stands). **Any applicant declaring `purposes=[FAMILY]` gets E31D
SUPPORTED, unconditionally, with zero check of relationship, marriage, or nationality — the
least constrained rule in the entire 38-product catalogue at the time of this sweep.** This was
a genuinely new addition to the "unenforced restriction" list this sweep exists to build (E31D
was not one of the rules in the original dropped-review-rules audit, and not one of the 4
controls team-lead named) — found by applying the same mechanical method to a product nobody
had looked at yet that day. (Note for a future reader: subsequent work in this repo — see PR
#4650, "extend fact vocabulary — stepchild, sponsor permit basis, active-permit derivation" —
added a `STEPCHILD` value to `RelationType`; this document is a snapshot of the state found at
the time of the sweep and does not claim to describe the pack's current state.)

## The 5 partial failures — already-known, reproduced independently, not claimed as new

E31B/E31E/E31H/E31J all share the identical defect on their "…of ITAS/ITAP Holder" qualifier:
`family.sponsor_status_code` is tested with `op: known` only (confirmed verbatim for E31B —
`{"fact": "family.sponsor_status_code", "op": "known"}` — any non-empty string, including a
value with no relationship to ITAS/ITAP status, satisfies it). This is the exact finding
already captured in memory
`lesson_presence_value_check_and_effect_on_outcome_are_three_axes_2026_08_23` ("9 rules on 4
products... `op:known` proves only that the field is populated") — this sweep's contribution
is confirming it falls inside the SAME catalogue-wide pattern as E30E/F/E31D/E23, not a
separate coincidence, and that it is exactly 4 products (E31B, E31E, E31H, E31J), all sharing
one root cause (`family.sponsor_status_code` has no `allowed_values`/closed enum — a free-text
field a `known` check can't meaningfully gate). E31C is grouped with the controls above since
team-lead named it directly.

## Good design found along the way — worth reporting because a denominator needs both sides

**E33G ("Second Home Visa — Remote Worker") has NO fact-path for its actual restrictive
figure (USD 60k/year income) — and is correctly guarded anyway.** `el.e33g.remote-work`
(SUPPORT) and `review.e33g.income-evidence` (REQUIRE_REVIEW) have byte-identical `when`
clauses — confirmed by diffing the two JSON bodies. Whenever the generic remote-work facts
would grant SUPPORT, the REQUIRE_REVIEW rule fires on the exact same trigger, and per the
evaluator's own precedence (REVIEW checked before SUPPORTED within a product's proof), E33G
can never resolve to a confident `SUPPORTED_CANDIDATES` — it always lands in
`HUMAN_REVIEW_REQUIRED` instead. Someone deliberately compensated for the missing fact-path by
forcing every otherwise-qualifying case to a human, instead of leaving the silent gap E30E/F
have. Matches the `visaoracle` skill's own LIVE_STATE log describing this exact fix ("E33G can
no longer reach SUPPORTED silently"). **This is the design pattern E30E/E30F/E23/E31D should
have gotten and didn't** — worth citing as the fix template if/when those get cured.

Also enforced correctly, no notes needed beyond the table: A1/B1's nationality-tier hard
filters (real `intersects` against a concrete country-code list — though the A1 list is only
19 codes, unusually short for a "visa-free" product; that is a content-freshness question,
already covered generically by the pack-wide `CL-CROSS-06` UNVERIFIED gap, not a new
structural finding, so not counted as broken here), E30A/E30B's disjoint `study.level` bands,
E31A/E31F/E31G's real relation+nationality(+marriage) checks, and E33E/E33F's real age
thresholds.

## What step 4 (live probe) would still need, if wanted

Not run — team-lead's ordering explicitly exists so a sweep like this one doesn't have to.
If a live-observable proof is wanted for the E31D finding, matching the E30E/E30F standard
established in the prior document, the same `probe_evaluate.py --full-body` method applies: a
synthetic FAMILY-purpose applicant with `family.relation_to_sponsor` left UNKNOWN (or set to a
value that isn't even STEPCHILD-shaped, at the time of this sweep, since no such value existed)
should still return E31D as a SUPPORTED candidate. Not run in this pass to keep scope to the
sweep itself; flag if wanted.

## Ranking by consequence (commercially-live where I can tell) — read against the SEVERITY

## CORRECTION above: this ranks readiness-to-cure, not present client exposure

None of these are live-client-facing today (SHADOW mode discards every verdict before it
reaches a public applicant — see correction above). The ranking below is about which defects
most need curing before ENFORCE can be considered, not about current harm.

Cannot authoritatively state which of these 38 codes Bali Zero actively sells without
checking the pricing catalog (`bali_zero_official_prices_2026.json` per repo CLAUDE.md) or the
CRM, which was out of this sweep's read-only, pack-only scope — flagging rather than guessing.
What the pack itself signals: E23 (work KITAS) and the E31 family-visa family are both
`LIMITED_STAY` products with broad `covered_purposes`, the same class as D12 (which a prior
audit already established as a real, priced, actively-evaluated product family — not a
dormant/BLOCKED one like E28B-F/E33A-C). On that basis, ranked:

1. **E23** (already escalated by team-lead at the time of this sweep) — work KITAS, core
   commercial product.
2. **E31D** — new this sweep, the single least-constrained rule found in the whole catalogue at
   the time of this sweep; family-visa products are the most-used FAMILY-purpose route per the
   pack's own breadth.
3. **E30E, E30F** (already P1, live-probe-confirmed at the time of this sweep) —
   education-visa siblings, lower volume than E23/E31 by product-shape but still a real,
   reachable, actively-evaluated path.
4. **E31B, E31E, E31H, E31J** — real relation/age gates exist, only the ITAS/ITAP-holder value
   check is missing; narrower practical exposure than E31D's total absence, but same root
   cause repeated 4 times.
5. **E31C** (already a control, team-lead's own finding) — same tier as the E31 partial-failure
   group; one real axis (WNI-parent) enforced, one (WNA-parent) not.
6. E23U/E23V/E28B-F/E33A-C — unreachable, no live consequence today; lowest priority, though
   E28B-F (investor golden-visa sub-variants) may be commercially significant if/when their
   `intent.requested_product_code` production-inertness (same PENDING-ARMS row already covering
   E23U/E23V/E33A-C) is ever fixed — worth remembering that fixing that ONE upstream defect
   would simultaneously make 9 currently-dormant products live, several with NO SUPPORT rule
   ready to receive the traffic.

## Adversarial review

**Date**: 2026-09-02. **Seat**: `codex` (`gpt-5.6-sol`, `model_reasoning_effort=high`,
`--sandbox read-only`, stance REFUTE — generator≠grader, this seat did not author the document).
Independently re-derived all 4 headline findings from the live checkout (rule pack JSON,
`enums.py`, `fact_registry.py`) rather than trusting the document's quotes, and spot-checked the
SHADOW-mode severity claim against `OracleShell.tsx` and `runtime-mode.ts`. All corrections below
were re-verified independently in this session (direct `sed`/grep against the pack JSON and
`runtime-mode.ts`) before being folded in — not taken on the refuter's word alone.

**Per-finding verdict:**

- **E23** — CONFIRMED. The two product-scoped rules reference only `intent.purposes`, the two
  work-sponsor booleans, and `investment.proposed_role`; no RPTKA/KBLI-match/jabatan/
  prohibited-role fact-path exists anywhere in the closed vocabulary. No correction needed.
- **E30E** — REFUTED-AND-CORRECTED. The document's "checks `sponsor.type` only" quote was
  factually wrong (the rule's `when` has 4 conjuncts, not 1) — corrected in place above, with the
  step-1 KEK-zone/institution-type gap finding itself unaffected.
- **E30F** — REFUTED-AND-CORRECTED. Same defect as E30E, same correction applied.
- **E31D** — CONFIRMED, including the STEPCHILD-enum disclaimer. All three scoped rules are
  still `SUPPORT` on a bare `FAMILY` purpose with no relationship/marriage/nationality gate;
  `RelationType.STEPCHILD` does now exist in `enums.py` (added 2026-08-23, matching the
  document's own note that PR #4650 added it after this sweep), but seq-12's E31D rules consume
  none of the new stepchild facts.

**SHADOW-mode severity claim** — CONFIRMED-CONDITIONAL, folded in as a correction above. The
code path itself is exactly as described (SHADOW discards candidates via `buildShadowOutcome`,
`internalMode` bypasses that). What the refuter caught, and what independent re-reading of
`runtime-mode.ts` confirmed: this checkout cannot establish which mode is *actually deployed* —
production defaults an unset/invalid `NEXT_PUBLIC_VISA_ORACLE_MODE` to `ENGINE`, not `SHADOW`,
and that env var lives outside version control. The "not live-client-facing today" claim is
therefore conditional on the deployment's actual configured mode, not an independently verified
fact from the repo alone — flagged in place above rather than asserted as settled.

**BLOCKER: none surviving.** Both raised issues (E30E/E30F misquote, SHADOW-mode deployment
assumption) were real and are folded into the document as attributed corrections; the four
headline verdicts (E23/E30E/E30F/E31D all fail-at-step-1 / unconstrained) are unaffected by
either correction.
