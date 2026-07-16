---
date: 2026-07-17
domain: visa
client_case: none
sources: round 3 arbitration (lane: claude-opus-4.8-xhigh, fresh context, generator≠grader)
status: round-3 verdict, faithfully preserved
---

Crux confirmed independently — [GoRules ZEN docs](https://docs.gorules.io/docs/decision-table) support **only `first` and `collect`** hit policies (also confirmed for Switch nodes); the [ZEN expression language](https://docs.gorules.io/learn/zen-language/syntax) evaluates unary tests to **boolean**, with no documented three-valued/null-propagating semantics. (Bonus signal for criterion 3: an open [issue #257](https://github.com/gorules/zen/discussions/257) reports `Decision.Evaluate` not returning the trace as expected — ZEN's trace is its own thing.) The dossier's two load-bearing claims hold. Ruling:

---

# ARBITER VERDICT — Visa Oracle v2 engine

## 1. Verdict: **A (BUILD custom Python evaluator) — for everything load-bearing (runtime, truth, trace, rules).** Confidence **0.85**.
ZEN may be *imitated and optionally borrowed as a non-runtime authoring aid* (see §3), but a hybrid where ZEN **executes any stage** is rejected. This is not a close call on the top-3 criteria; it is only close on maintenance, and that closeness dissolves under scrutiny.

## 2. Reasoning per criterion (brutally honest)

**1 — UNKNOWN + purpose-coverage semantics (highest weight): decisive for A.**
Neither required semantic exists in ZEN. `collect` returns matching rows; it cannot compute `union(covered_purposes of TRUE rules) ⊇ declared_purposes` — that set-cover is *your* post-processing. Tri-state Kleene logic isn't in a boolean unary-test engine — UNKNOWN needs sentinel encoding + your truth tables *around* ZEN. So in Option B, **all the semantically dangerous logic (tri-state propagation, cover-all, precedence, the "unknown can't increase eligibility" invariant) lives in your Python wrapper anyway**, and ZEN degrades to a table-matcher. That is the textbook second-truth-layer the criterion forbids: ZEN says "these rows matched," your wrapper says "but here's what supported/blocked/unknown *means*." Two authorities, one seam to get wrong. A expresses both natively in one pass (§3). **Strongly A.**

**2 — Auditability for Ditjen Imigrasi: A.**
A reviewer's chain must be *one* legible artifact: signed RulePack → condition AST → canonical trace → source ref, all Python/JSON. Option B forces the auditor to understand JDM graphs **and** the wrapper's tri-state/coverage **and** the ZEN↔canonical trace mapping **and** trust a Rust binary's evaluation equals the documented semantics. Split decision authority = the auditor must reason about the seam. For a "credible to demo to a ministry" bar, single-artifact wins hard. **A** (with one honest concession: ZEN's *visual* JDM editor is genuinely compelling in a live demo — that's an authoring/visualization asset, not a runtime argument; §3).

**3 — Determinism + trace fidelity: A.**
Contract demands no-short-circuit (all children evaluated), full deterministic trace, `trace_sha256` over *your* canonical JSON, raw fact values never exposed. An executor optimized for evaluation fights every one of those. You'd rebuild the trace in the wrapper regardless — which means **ZEN's computed path and your emitted trace can diverge** (trace asserts one thing, ZEN did another). That's a correctness *and* audit landmine in a signed-artifact product. In A, the evaluator and the trace-builder are the same code path; the trace is a faithful byproduct of evaluation. **Strongly A.**

**4 — Maintenance + supply-chain, 3+ yrs, solo-dev: leans A (this is B's only real pitch, and it fails).**
B's case: "GoRules maintains it, MIT, active." Counterweights that dominate: (a) it's a **Rust binary** — opaque to a Python solo-dev, platform-specific wheels, can't easily read/patch/audit, breaks are upstream-gated; (b) **"no documented third-party production users"** — betting a government-credible *legal* product's core on a single-vendor engine with no production peers is a real yellow flag; (c) "pushed yesterday" cuts both ways (active *or* churning). A's "we own every bug" con is **overstated**: the evaluator core is bounded (~2–4k lines), the R2 spec is complete with semantics tables + pseudocode, and it's pure readable Python the dev fully controls — bug *and* fix are yours, no binary-wheel breakage on a 3.11 bump, no unaudited Rust CVE tree. For a solo dev in a legally-audited product, **controllable+readable+zero-runtime-dep > outsourced maintenance of an opaque binary you're the only one relying on.** Net: A.

**5 — Build-cost delta (claimed 25–30%): not real; A.**
The saving is on the **condition-table matcher** — the cheapest, most-trodden, lowest-risk module. It's *zero* on the hard parts (cover-all, tri-state, precedence, canonical trace) because **you build those in Python either way**. Meanwhile B *adds* cost: RulePack→JDM compile, UNKNOWN sentinel + truth-table glue, trace reconciliation, dual-format test surface, Rust build/CI. Netted, the saving is ≈0 or negative — and it's a saving on the *wrong risk-axis* (you save days on the safe part, buy complexity-tax on the dangerous part). **A.**

**6 — Lock-in / reversibility: A.**
Adopting ZEN as the *core executor* is the highest-lock-in choice on the board: JDM becomes a second rule format, and abandonment/binding-break forces you to migrate rules out of JDM **and** rebuild the executor — under duress, the worst time to build. A has zero external runtime dep → maximally reversible. (Note: ZEN as *authoring-only* has near-zero lock-in precisely because the runtime never depends on it — that's the safe way to borrow it, §3.) **A.**

## 3. How A handles the two hard semantics natively (single truth layer) + which ZEN ideas to imitate

**UNKNOWN (native, one truth value per node, in the trace):** the AST evaluator returns Kleene `{TRUE, FALSE, UNKNOWN}`; AND/OR/NOT use strong-Kleene tables (`TRUE∧UNKNOWN=UNKNOWN`, `FALSE∧UNKNOWN=FALSE`, `TRUE∨UNKNOWN=TRUE`, `FALSE∨UNKNOWN=UNKNOWN`, `¬UNKNOWN=UNKNOWN`). **"Unknown can't increase eligibility" is structural, not a rule:** a support-rule contributes its `covered_purposes` to the union **only when it evaluates TRUE** — UNKNOWN rules are inert for coverage, so UNKNOWN can only ever *leave a purpose uncovered* (→ NEEDS_INPUT) or block, never satisfy one. No coercion, no sentinel.

**COVER_ALL_DECLARED_PURPOSES (native, same pass):** union the `covered_purposes` of TRUE support-rules; emit candidate iff `union ⊇ declared_purposes`; else the uncovered set drives the state — NEEDS_INPUT if a relevant blocking rule is UNKNOWN and could flip, NO_SUPPORTED_PATH if all are FALSE. One code path, one trace, one `trace_sha256`. **This is the whole reason A wins: both semantics are byproducts of the same evaluation that writes the trace — there is no seam.**

**ZEN/JDM ideas to steal anyway:**
- **JDM visual graph as a demo/audit visualization** — render your RulePack as a decision graph for the Jakarta demo; a visual is far more persuasive to non-engineers than Python. Generate it *from* your RulePack, one-directional.
- **The visual editor as an internal authoring aid that *compiles to* signed RulePack** — optional, deferred, and only if the RulePack↔editor mapping earns its keep; the editor never touches runtime or becomes a source of truth. This is the *only* sanctioned "hybrid," and it's authoring-only.
- **Decision-table row ergonomics** (input columns = AND, top-to-bottom order) as an *authoring UX* convention for how humans write hard-filter rules.
- **Simulation/test-vector UX** — mirror ZEN's "run inputs, see which rows fire" in your gold-case harness for rule authors.
- Borrow their **trace-completeness discomfort as a warning** (issue #257): make your trace a first-class, always-returned, tested contract — the thing they struggle with is your headline feature.

## 4. Single strongest argument AGAINST my own verdict
*For a solo-dev agency, a hand-rolled strong-Kleene evaluator + bespoke set-cover hit policy is exactly the class of subtle-semantics code where **your** bug becomes a wrong legal-eligibility answer with no upstream and no peer users to have hit it first — validated by only 20 gold personas. A battle-tested engine, even wrapped, means the boolean-matching core is exercised by thousands of other users.*
**Why it still doesn't flip me:** the risky semantics aren't in ZEN — you write cover-all/tri-state/precedence regardless — so ZEN de-risks only the trivial matcher you'd get right anyway, while the *correct* mitigation for A's real risk is already in the spec (metamorphic + property-based tests over the truth tables and the set-cover, plus the gold harness). Property tests validate *your* semantics far more than "another engine matched a boolean" ever could. The counter-argument correctly identifies a real risk and correctly points at **test investment**, not at ZEN.

## 5. What evidence would flip me
- **Flip toward B/C-executor** if ZEN is shown to natively support *all three*: (a) a hit policy expressing set-cover-over-outputs, (b) documented three-valued/null-propagating evaluation with "unknown ≠ false," and (c) a pluggable trace hook honoring our canonicalization + no-short-circuit. That collapses the second-truth-layer objection and lets maintenance win. (Today's evidence says none of the three exist.)
- **Weakens A** if a time-boxed spike measures the tri-state + cover-all + canonical-trace core at **>2× the R2 estimate**, *while* a parallel ZEN-wrapper spike proves the semantics live cleanly in JDM expressions with a faithful trace.
- **De-risks B materially** if a second/third independent legal-tech or regulated product is found running ZEN in **audited production** (removes the "no production peers" supply-chain flag).
- **Team growth** (no longer solo) lowers A's "own every bug" cost — but note this pushes *further* toward A (more hands maintain readable Python), it does not rescue B.

**Bottom line:** Build the evaluator (A). ZEN cannot hold the two semantics that define this product's correctness, and wrapping it splits truth and trace across a seam no government auditor should have to reason about. Borrow its *editor and visualization* for authoring and the demo — never its runtime.
