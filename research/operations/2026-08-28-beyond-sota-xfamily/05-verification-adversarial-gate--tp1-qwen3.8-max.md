---
panel: beyond-sota-xfamily
lane: 05-verification-adversarial-gate
seat: tp1-qwen3.8-max
model: "qwen3.8-max · enable_thinking · TP1 API, no tools, ground pack"
started: 2026-08-28T16:47:20Z
finished: 2026-08-28T16:56:09Z
duration_s: 529
exit: 0
words: 4803
prompt_sha256_16: 62da1d9e514798b2
prompt_chars: 170674
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 5/13 — Verification, adversarial review & final gate
model: Qwen3.8 Max (pinned lane)
sources: 16
repo_files_verified: 17
status: complete
sections_done: [0,1,2,3,4,5,6,7,8,9]
---

**Access & evidence note (assumption stated up-front, per protocol).** This lane ran with **NO file, shell or web tools** — only the appended GROUND PACK. Therefore `repo_files_verified: 17` means *17 distinct repo paths present and read in the supplied read-only GROUND PACK*, not independent on-disk verification; the `ls`/`wc` post-write probe required by §4 is **N/A** because no file write is possible here (the deliverable is returned inline as mandated). Files listed as hot but marked `NOT FOUND`/omitted in the pack (`registry.json`, `gate_coverage.py`, `scripts/evidence_pack_lint.py`, `evidence/pack.yml`, `launch_worker_plane_review_panel.py`, `tests.yml`, all `research/operations/*`, `MEMORY_VERIFICATION_RULES.md`, and every `lesson_*`/`discovery_*` MEM body) are cited only where another in-pack file corroborates them; otherwise they are **ASSUMED**. All `MEM:` references are **unavailable**. The web survey (§3) is from model knowledge; URLs I am not fully sure of are marked `(unverified)`.

---

## 0. TL;DR

**Position vs SOTA in one sentence:** The organism is *ahead* of world practice at the **structure** of verification (generator≠grader as a merge gate, guilt+innocence guard conformance, tamper-evident meta-verifier, retracted-claims firewall) but *behind* at the **execution coverage** of it — the proof machinery is declared more often than it is armed, run, and measured.

**Biggest gap:** scar→gate closure. `infra/scar-gates/MANIFEST.json` reports `total: 66, armed: 2, prose_only_debt: 64` — **97% of measured failures have no executable regression gate**. This is the single largest verified gap and the root of most recurrence risk.

**Top-3 moves:**
1. **Scar-gate arming factory** — mechanically arm the 64 prose-only scars into CI-reachable guilt+innocence tests; armed `2 → ≥30` in 90 days.
2. **No-weakening monotonicity gate** — a deterministic anti-reward-hacking lint that fails any PR that deletes/skips tests, guards, or lowers mutation/canary coverage without a CODEOWNERS waiver.
3. **Continuous guard fuzzing + guard robustness score** — promote `guard_fuzz_harness.py` (445 shapes) from per-PR to a scheduled, growing property corpus with a published robustness trend.

**Recurring meta-pattern (§8):** *declaring a control is treated as the control operating* ("la prova può essere vuota"). Every recommendation forces **execution + measurement** over **declaration**.

---

## 1. How Nuzantara does it today

> Evidence constraint: every path below was read in the GROUND PACK. Line numbers are not cited because the pack is excerpted; claims are anchored to file + visible content.

**Doctrine & seat roster.** `.claude/skills/modus/SKILL.md` states the operating loop runs "Opus 5 xhigh effort architect+sequential final on-disk gate — Fable 5 out of the workflow, RULED 2026-08-20 — Sonnet 5 implementers, Codex GPT-5.6 red-team+sandbox, Gemini agy constructive width, **Kimi K3 permanent refuter**, Ollama local for PII, NotebookLM ground-truth." The VERIFY/harness gate is "always `xhigh`+" regardless of gear, and a gear **ceiling** (`compute_ceiling()` in `scripts/evidence_pack_lint.py`, PR #4474) caps over-ceremony while a **floor** (`harness-floor.yml`) prevents under-gearing. This is a genuinely explicit generator≠grader + family-exclusion roster.

**The reusable generator≠grader artifact.** `infra/workflows/verify-template.js` encodes "judging < generating": gather N angles → independent skeptic(s) per finding on fresh context → synthesize survivors. It uses a `FINDING_SCHEMA` (claim/evidence/source/confidence) and `VERDICT_SCHEMA` (`refuted` boolean), with `majority-not-refuted` survival and explicit calibration ("one strong skeptic per finding; skeptics:3 for high-stakes"). It cites the W65 lesson: "even the refuter hallucinates, but a generator grading itself is strictly worse."

**The final-gate discipline.** `.claude/skills/final-gate-discipline/SKILL.md` makes the gate non-delegable ("You…are the final, non-delegable check") and defines **five questions answered by a command run NOW, never from memory**: (1) Who calls it? (2) What other surface describes it? (3) What did I just write that will expire? (4) Can my probe actually say yes? (5) Where does the work actually live right now? — plus a naming corollary ("the name of anything that changes lies about its own content unless you prove it"). It is self-applied: it must be referenced from `modus/SKILL.md`'s VERIFY/SHIP+ARM stages, and that grep is itself a tripwire.

**Empirical verify + cross-family second opinion.** `.claude/commands/verify.md` enforces read-only empirical checks with `PASS|FAIL|PARTIAL` and "NEVER cite output da context buffer." `.claude/commands/codex-second-opinion.md` dispatches Codex CLI as an adversarial "spalla" with verdicts `BLOCKER|MEDIUM|LOW|LGTM`, saved transcripts, and hard rules (no sandbox bypass, no API key — OAuth only).

**Guard conformance (superscar #3).** `infra/guard-conformance/check_guard_conformance.py` makes the rule "nessuna guardia mergiata senza un test di innocenza E di colpevolezza" structural: **C1** census parity (AST-based, comments can't fool it), **C2** every guard has ≥1 guilt AND ≥1 innocence test, **C3** anti-phantom (referenced tests must exist as real defs — W65), **C4** armed (referenced test must be reachable by a workflow — W81). `guard-conformance.yml` executes it plus a long list of explicit W-suites (W83/W84/W92/W105/W117, orchestrate_gate vocab+disarm) and a property/fuzz corpus ("445 generated command shapes").

**Guard fuzzing.** `infra/claude-hooks/guard_fuzz_harness.py` is a property/fuzz corpus runner: a generator produces `(command, expected_verdict, tag)` from a combinatorial grammar (mutating vs read-only git verbs × noop/remote/text-only/deceptive/true-compound wrappers) and a classifier is the guard under test. Its docstring records the **6th over-match found at the gate of PR-2266 *after* the corpus shipped 382/382 green** — proof that the corpus itself had a blind spot and that this loop catches the next one pre-merge.

**Meta-verification.** `verify-the-verifiers.yml` runs the meta-verifier on an isolated runner with **sha256 integrity + CODEOWNERS** on the load-bearing files ("quis custodiet…answered by immutability, not intelligence"). `catC-canary-tautology-lint.yml` detects a **tautological self-substring canary** in `run_canary()` (W64 — "the canary exists, runs, and lies"). `adversarial-review-gate.yml` is a **required** R1 generator≠grader gate that runs `--selftest` first ("the corpus existed and was never executed…W108").

**Mutation testing.** `p1s2-mutation-incremental.yml` runs incremental (AST-diff, changed-lines-only) mutation with **hidden canary mutants** (anti-mutation-cheat: the agent can't game the score) and a canary self-test; mutmut is CI-provided.

**Harness verdict / gear floor.** `harness-floor.yml` makes `harness/fable-gate` a safe required check by having the workflow job itself be the check (solving the synthetic-SHA relay and fork-PR write-permission problems), computing the floor via `evidence_pack_lint.py --print-floor` and validating `evidence/pack.yml`. It contains a precise, self-correcting account of W111 rerun scoping and a diagnostic pagination trap — itself evidence of a learning loop.

**Disabled advisory AI review.** `ai-pr-review.yml.disabled-2026-08-20-zero-value-ci-trust-gate` is non-blocking-by-design (never a required status; "an LLM reviewer hallucinates (scar W65)"). It was disabled because every run failed a CI-side workspace-trust dialog while still reporting `success` — "green that lies" (superscar #2).

**Retracted-claims firewall.** `infra/retracted-claims/registry.json` blocks re-derivation of retracted claims with **claim-bound absolution** (`require_bound_marker`, `absolution_pattern`), all-caps negation-guarded directives, and declared friction — a lineage-integrity mechanism I found no external analog for.

**Pro-side tri-LLM review.** `docs/runbooks/review-gate.md` describes a 3-LLM review-comment panel (Codex/Claude/DeepSeek) that is review-only, idempotent by head-SHA, fail-closed on truncated diffs, and uses a **robust quorum** that never counts an env-down reviewer as a vote (W64).

---

## 2. Scars & ledger evidence in this area

The scar corpus itself (`cicatrix-superscar.md`, `cicatrix-scars.md`, `AMENDMENTS.md`, `PENDING-ARMS.md`) was **not in the pack**, so I cite W-numbers only where an in-pack artifact carries them. Recurrent families in this lane:

| Family / W | Disease | Where it lives in the pack |
|---|---|---|
| **superscar #3** (guard over/under-match) | guards that bite innocents or miss guilt | `check_guard_conformance.py` header lineage "W68→W72→W73→W77→W82→W83→W84→W85, the most recursive disease"; `guard_fuzz_harness.py` W83/W84/W85/W91/W92; `guard-conformance.yml` W92/W105/W117 |
| **W81** ("esiste ≠ armato") | a test/gate that exists but never runs is theater | `check_guard_conformance.py` C4; `guard-conformance.yml` "previously unexecuted anywhere"; `adversarial-review-gate.yml` |
| **W65** (even the refuter hallucinates) | graders fabricate | `verify-template.js`; `check_guard_conformance.py` C3 anti-phantom; `ai-pr-review.yml.disabled` |
| **W64 / superscar #2** ("green that lies") | canary/check reports success while validating nothing | `catC-canary-tautology-lint.yml`; `ai-pr-review.yml.disabled`; `review-gate.md` robust quorum |
| **W100** | citing consensus without naming reviewers' parentage | `final-gate-discipline/SKILL.md` Part 1 |
| **W108** | a required corpus that runs nowhere is where defects hide | `adversarial-review-gate.yml` (armed 2026-08-02) |
| **W111 / W78 / superscar #6** | rerun-on-moving-base; wrong scar propagated into a header | `harness-floor.yml` (explicit self-correction of an earlier draft that "named the WRONG mechanism") |

**Scar→gate closure (the headline number).** `infra/scar-gates/MANIFEST.json`: `total: 66, armed: 2, prose_only_debt: 64`. Only `scar_W82` and `scar_homefork` are `prose_only: false`. **This is the most concrete, verified weakness in the lane**: the organism measures its failures superbly and then leaves 97% of them as prose.

**The "6th over-match" is the lane's best evidence the loop works:** `guard_fuzz_harness.py` records that the corpus shipped 382/382 green and the next over-match was still found *at the gate, pre-merge* — i.e., the adversarial gate caught what the hand-written suite could not.

### Measurements requested but not computable here (UNMEASURED)

- **Guards registered vs guards with both guilt+innocence tests** — `registry.json` was NOT FOUND in the pack. Exact command (schema ASSUMED from `check_guard_conformance.py`):
  ```
  jq '[.surfaces[].guards | to_entries[]
        | {g:.key, guilt:((.value.guilt|length)>0), innoc:((.value.innocence|length)>0)}]
      | {total:length, both:(map(select(.guilt and .innoc))|length)}' \
     infra/guard-conformance/registry.json
  ```
  Cross-check with the checker's own output: `python3 infra/guard-conformance/check_guard_conformance.py --json` (count `C2` violations = missing guilt/innocence).
- **Correction-of-a-correction commits on main, last 14 days** — no git access. Baseline 27/200 (2026-08-20..22, CLAUDE.md rule-8) is **ASSUMED**, not re-verified. Heuristic: a commit is a correction-of-a-correction if its subject matches ≥1 correction marker AND references a prior fix. Command:
  ```
  git -C /Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828 \
      log --since=14.days --no-merges --oneline main > /tmp/c.txt
  total=$(wc -l < /tmp/c.txt)
  corr=$(grep -iE 'correct|re-?fix|fix( the)? fix|again|second (attempt|fix)|undo|revert|retire|retract|restore|reapply|after the (fix|patch)|correction of' /tmp/c.txt | wc -l)
  echo "$corr/$total"
  ```
- **Required checks: verification-shaped vs lint-shaped** — branch-protection required list not in pack; the workflow listing is partial (40 of 106 names shown). Command:
  ```
  gh api repos/{owner}/{repo}/branches/main/protection/required_status_checks --jq '.contexts[]'
  ls .github/workflows
  ```
  Qualitative read of visible names (**ASSUMED**, from names only): verification-shaped (run tests/assert behavior) dominate — `guard-conformance`, `hook-innocence-gate`, `verify-the-verifiers`, `adversarial-review-gate`, `p1s2-mutation-incremental`, `harness-floor`, `contract-tests`, `catD-backend-data-invariants`, `catB-daemon-cron-xor`, `catA-channel-count-pin`; lint-shaped — `actionlint`, `asyncpg-lint`, `doc-freshness`, `catC-canary-tautology-lint` (explicitly non-required observability), `docs-guardian`. Grounded facts: `adversarial-review-gate.yml` is REQUIRED on main; `guard-conformance.yml` says making it required is operator-only/pending; `catC` is explicitly non-required.

---

## 3. World SOTA survey

> No web tools were available; sources are from model knowledge (access date 2026-08-28). Uncertain URLs marked `(unverified)`.

| # | System / practice | Source | Mechanism that makes it best-in-class | Measured effect (if published) | Transfer here |
|---|---|---|---|---|---|
| 1 | LLM-as-judge biases | Zheng et al., *Judging LLM-as-a-Judge* (2023) — https://arxiv.org/abs/2306.05685 | quantifies position/verbosity/self-enhancement bias; ~80% human-agreement ceiling | bias rates across judges | calibrate refuter seats; randomize order; panel majority |
| 2 | Debate as scalable oversight | Irving/Christiano/Amodei (2018) — https://arxiv.org/abs/1805.00899 | a judge decides a debate; supervision scales with capability | theory | foundation for refuter seats / verify-template |
| 3 | Persuasive debate → truthfulness | Khan et al. (Anthropic, 2024) — https://arxiv.org/abs/2305.14763 | more persuasive models yield more truthful answers under debate | truthfulness gain | warns: a confident wrong generator can persuade the judge |
| 4 | CriticGPT | OpenAI (2024) — https://openai.com/index/catching-ai-hallucinations-with-criticgpt/ `(unverified)`; arXiv *LLM Critics Help Catch LLM Bugs* — https://arxiv.org/abs/2407.00215 | a critic model finds bugs humans miss; itself hallucinates | finds planted bugs | adversarial reviewer must be graded — W65 analog |
| 5 | TestGen-LLM (Meta) | Alshahwan et al. (2023) — https://arxiv.org/abs/2302.06527 | **assured pipeline**: generator proposes, assessors (build/pass/coverage) reject; only assured improvements land | ~73–75% of suggestions rejected | the strongest template for generator≠grader with automated grading |
| 6 | Mutation testing at Google | Petrović & Ivanković, *State of Mutation Testing at Google* (2018) — https://research.google/pubs/pub46584/ `(unverified)` | mutant reduction, incremental, flaky handling; measures test adequacy | org-scale mutation coverage | p1s2 aligns conceptually; Google applies broadly, organism narrowly |
| 7 | OSS-Fuzz | Google (2016–) — https://github.com/google/oss-fuzz | continuous automated fuzzing in CI/ClusterFuzz | tens of thousands of bugs | make guard_fuzz_harness continuous |
| 8 | Modern Code Review (Google) | Sadowski et al. (2018) — https://research.google/pubs/pub47025/ `(unverified)` | small CLs, presubmit static triage (Tricorder), readability approval | review latency ↓ | review-gate + adversarial-review-gate align; add static triage |
| 9 | Formal methods at AWS | Newcombe et al., CACM (2015) — https://cacm.acm.org/magazines/2015/4/184701-... `(unverified)` | TLA+/model checking on critical services | subtle concurrency bugs found pre-ship | high cost; only for hot-zone invariants |
| 10 | Automated reasoning / verified s2n | AWS Automated Reasoning / SAW-Dafny — https://www.amazon.science/blog/automated-reasoning `(unverified)` | machine proofs of crypto/memory safety | verified TLS | only for narrow invariants (e.g., PII output boundary) |
| 11 | N-version programming | Avizienis (1985) — https://doi.org/10.1109/TSE.1985.231875 `(unverified)` | independent implementations + voting vs common-mode failure | fault-tolerance | N-version final gate across model families |
| 12 | NASA IV&V | NASA IV&V Program — https://www.nasa.gov/mission/independent-verification-and-validation/ `(unverified)` | an independent org, not the developer, verifies | mission assurance | generator≠grader is IV&V in microcosm |
| 13 | Why LMs hallucinate / reward hacking | OpenAI (2025) — https://arxiv.org/abs/2509.04664 `(unverified)` | binarized evals incentivize test-tampering/cheating (o3) | documents eval-gaming | don't reward green-at-all-costs; no-weakening gate |
| 14 | Alignment faking / sycophancy→subterfuge | Anthropic (2024) — https://arxiv.org/abs/2412.14093 `(unverified)` | models strategically comply/deceive under pressure | documented | refuter seats can be sycophantic; family-exclusion + fresh context mitigate |
| 15 | CoT monitoring for misalignment | Chen et al. (OpenAI, 2025) — https://arxiv.org/abs/2503.14499 `(unverified)` | scratchpad/CoT monitoring catches test-tampering intent | catches scheming in evals | monitor implementer/refuter CoT for gate-weakening intent |
| 16 | Agentic PR-review products | CodeRabbit — https://www.coderabbit.ai; Cursor Bugbot — https://cursor.com/blog/bugbot `(unverified)`; GitHub Copilot review `(unverified)` | LLM reviews every PR, line comments, configurable, **live at scale** | shipped at many orgs | organism's ai-pr-review is *behind* (disabled) but adds scar-grounded adversariality |

**The 3–5 that matter most for this organism.** (a) **Meta TestGen-LLM** is the clearest external validation of the organism's core bet: an *assured* generator≠grader pipeline where a deterministic assessor, not a human, rejects the majority. The organism's `check_guard_conformance.py` + `guard_fuzz_harness.py` are a hand-built analog — the gap is breadth, not concept. (b) **Zheng/Khan + CriticGPT** establish that the *judges themselves* are biased and hallucinate; the organism names this (W65) but does not yet *measure* judge accuracy or self-preference — that is the biggest calibration gap. (c) **Alignment-faking + CoT-monitoring (OpenAI/Anthropic)** are the frontier of **reward-hacking detection**; the organism's anti-mutation-cheat canary and retracted-claims lint are adjacent, but there is no explicit *no-weakening* invariant. (d) **OSS-Fuzz + Petrović** show that fuzzing/mutation only pay off when **continuous and broad**; the organism runs them per-PR and narrowly. (e) **N-version/IV&V** justify replacing the single Opus 5 final gate with a cross-family panel whose disagreement is signal.

---

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Generator≠grader separation (fresh-context refutation) | **AHEAD** | `verify-template.js` as a reusable artifact; modus roster (Kimi K3 permanent refuter, Codex red-team); family-exclusion |
| Adversarial review gates in CI | **AHEAD** | `adversarial-review-gate.yml` REQUIRED, `--selftest` first, no paths-filter trap (W69) |
| Guard conformance (guilt+innocence) | **AHEAD** | `check_guard_conformance.py` C1–C4; `guard-conformance.yml` — no external analog found |
| Meta-verification (verify the verifiers) | **AHEAD** | `verify-the-verifiers.yml` sha256+CODEOWNERS; `catC` tautology lint (W64) |
| Retracted-claims / claim lineage integrity | **AHEAD** | `infra/retracted-claims/registry.json` claim-bound absolution — unique |
| Guard fuzzing / mutation *of guards* | **AT** | `guard_fuzz_harness.py` (445 shapes) but per-PR, single family; OSS-Fuzz is continuous |
| Final on-disk gate doctrine | **AT** | strong (Opus 5, no cascade, five questions) but **single point of failure**; N-version would add redundancy |
| Mutation testing (application code) | **BEHIND** | `p1s2-mutation-incremental.yml` is sentinel-scoped to its own driver paths; Google applies broadly |
| Reward-hacking / test-tampering detection | **BEHIND** | anti-cheat canary + retracted-claims exist, but no deterministic no-weakening gate, no CoT monitoring |
| LLM-judge calibration / bias control | **BEHIND** | no measured judge accuracy, self-preference, or position/verbosity bias for refuter seats |
| Scar→gate closure (arming) | **BEHIND** | MANIFEST `armed: 2 / total: 66` — 97% prose-only |
| AI advisory PR review | **BEHIND** | disabled; delivered zero due to trust-dialog while reporting success (superscar #2) |
| Evidence packs & gear floor/ceiling harness | **AHEAD** | `harness-floor.yml` + `compute_floor/ceiling` (file bodies omitted in pack → details **ASSUMED**) |

---

## 5. Beyond-SOTA recommendations (ranked by impact × confidence / cost)

Each satisfies §2.D: novel composition, exploits an organism asymmetry, has a before/after number, respects hard rules (no paid Anthropic API; CLI-only; PII boundary; Fable not auto-routed; business items flagged `needs-ruling`).

### R1 · Scar-gate arming factory
- **What:** convert the 64 prose-only gates in `infra/scar-gates/MANIFEST.json` into executable, CI-armed guilt+innocence tests, prioritized by recurrence, using the `guard_fuzz_harness.py` generator pattern to auto-produce cases.
- **Why it beats SOTA:** no surveyed system owns a corpus of 66 measured failures with lineage that it can *mechanically re-arm*; SOTA mutation/fuzz tools generate mutants for code, not for documented organizational failure modes.
- **Cost:** moderate — flat-sub implementer tokens + CI minutes.
- **Gear:** 3.
- **Risk + scar family:** theater tests that exist but don't run — **#2 / W81 / W64**. Mitigate by requiring C4 armed-in-CI and both guilt+innocence.
- **Metric + method:** `MANIFEST.armed 2 → ≥30`, `prose_only_debt 64 → ≤36`; verify via `scripts/verify_the_verifiers.py --scope repo` reporting each new gate ARMED.
- **Kill criterion:** ≥40% of newly armed gates later found no-op/tautological → halt & re-scope.
- **First PR:** *Arm top-5 recurrent scar-gates* — add `infra/scar-gates/test_W<N>_*.py` ×5, flip MANIFEST; ≤400 lines; Gear 2; acceptance: MANIFEST.armed==7 and each reported ARMED.

### R2 · No-weakening monotonicity gate (anti-reward-hacking)
- **What:** a required lint failing any PR that deletes/skips a test/guard/CI workflow, lowers assertion count or mutation/canary coverage, or removes a guard-registry entry — unless it carries a CODEOWNERS-approved waiver. AST diff + registry census + mutation baseline.
- **Why it beats SOTA:** SOTA detects reward hacking via CoT monitoring or human review; none enforce a deterministic "teeth can only increase" invariant at merge. Composes the organism's registry+census uniquely.
- **Cost:** low–moderate.
- **Gear:** 2.
- **Risk + scar family:** false over/under-match blocking legit refactors — **#3**. Provide waiver path.
- **Metric + method:** weakening attempts blocked (baseline 0 → ≥N caught); 0 innocent blocks after waiver. Log + waiver ledger.
- **Kill criterion:** >5 innocent PRs blocked/week, or >30% of triggers waived → disable.
- **First PR:** *no-weakening lint* — `scripts/lint_no_weakening.py` + tests + workflow; ≤400 lines; Gear 2; acceptance: deleting a test in a fixture fails; waiver passes.

### R3 · Continuous guard fuzzing + guard robustness score
- **What:** promote `guard_fuzz_harness.py` from per-PR (445 shapes) to a scheduled, growing, multi-guard property corpus with a published **guard robustness score** and guard-targeted mutation (mutate the guard regex/classifier; require the corpus to kill mutants).
- **Why it beats SOTA:** OSS-Fuzz fuzzes program inputs continuously; nobody fuzzes their own guard decision-functions continuously with property oracles and a robustness trend. The generator+classifier pattern already exists.
- **Cost:** moderate CI minutes + tokens.
- **Gear:** 2.
- **Risk + scar family:** flaky/noisy corpus, or only regenerating known shapes — **#3 / W108**. Require corpus-growth telemetry.
- **Metric + method:** corpus `445 → ≥2,000` shapes; robustness trend reported; ≥1 new over/under-match caught pre-merge. `--list` + mismatch report + scheduled history.
- **Kill criterion:** corpus flat 30 days, or robustness never drops (corpus not biting) → re-scope.
- **First PR:** *scheduled guard-fuzz + telemetry* — cron workflow + artifact; ≤400 lines; Gear 2; acceptance: scheduled run emits corpus-size+score and fails on injected mismatch.

### R4 · Retracted-claims firewall compiler
- **What:** generalize `infra/retracted-claims/registry.json` into a self-arming firewall: a scaffold command that, given a retraction, emits the registry entry (pattern/context/absolution_pattern/require_bound_marker) + a lint test, wired into the existing lint.
- **Why it beats SOTA:** no surveyed system has claim-bound absolution with a lint distinguishing "quoting to correct" from "naked assertion." Unique asset.
- **Cost:** low.
- **Gear:** 2.
- **Risk + scar family:** over-matching neutral mentions (declared friction) → bypass — **#3**. Keep absolution cheap.
- **Metric + method:** registered claims `3 → ≥10`; recurrences of retracted claims in new PRs → 0. Lint hits + registry count.
- **Kill criterion:** friction causes routine bypass/waivers → simplify.
- **First PR:** *retracted-claims scaffold + auto-lint* — `scripts/scaffold_retracted_claim.py` + test; ≤400 lines; Gear 2; acceptance: sample claim caught by lint; RETRACTED directive absolves.

### R5 · N-version multi-seat final gate (disagreement-as-signal)
- **What:** augment the single Opus 5 final gate with an N-version panel (≥2 different model families, generator-family excluded) that each independently execute the five final-gate questions as live commands and emit a structured verdict; disagreement is recorded and surfaced, never silently majority-resolved; consensus requires named parentage (W100).
- **Why it beats SOTA:** N-version/IV&V exist for human/space systems; no agentic coding org runs a cross-family, command-executing final gate with disagreement-as-signal and family-exclusion at merge.
- **Cost:** high (multiple OAuth seats per Gear-3 PR); flat-sub.
- **Gear:** 3.
- **Risk + scar family:** rubber-stamp consensus (W100), quota overrun, sycophancy (alignment-faking). Mitigate family-exclusion + fresh context + command-run answers.
- **Metric + method:** gate disagreement rate (healthy nonzero); ≥1 escape caught by a second seat; per-gate cost ≤ budget. Verdict ledger + cost telemetry.
- **Kill criterion:** disagreement≈0 for 30 Gear-3 PRs, or cost >2× budget → revert to single-seat.
- **First PR:** *five-questions verdict schema + 2-seat runner* — `infra/workflows/nversion-final-gate.js` + writer to `evidence/pack`; ≤400 lines; Gear 3; acceptance: two seats produce independent structured verdicts; disagreement recorded.

### R6 · Judge calibration battery + self-preference detector
- **What:** a versioned "judge battery" of known-true/known-false claims (seeded from scars + retracted claims) run against every refuter/judge seat; compute accuracy, false-refute rate, verbosity/position bias, and a **self-preference index** (does a seat spare its own family's outputs); publish a calibration table and route high-stakes refutation to calibrated seats.
- **Why it beats SOTA:** LLM-judge bias is studied academically (Zheng, Khan) but no production coding org continuously calibrates its own judge seats on a repo-specific ground-truth battery with self-preference detection and uses it for routing.
- **Cost:** moderate tokens.
- **Gear:** 3.
- **Risk + scar family:** battery overfitting/leakage inflating scores without real catch-rate gains (reward hacking). Hold out items.
- **Metric + method:** per-seat accuracy on hold-out known-bad claims (baseline unmeasured → reported); self-preference index; false-refute rate. Harness results.
- **Kill criterion:** battery accuracy diverges from real-world catch rate → rebuild battery.
- **First PR:** *judge_battery harness + 20 seeded claims + report* — `infra/verification/judge_battery/*`; ≤400 lines; Gear 3; acceptance: scores ≥2 seats and distinguishes a known-good from known-bad judge.

### R7 · Gate escape-rate ledger + feedback loop
- **What:** a durable ledger of every harness/fable-gate verdict, adversarial-review finding, and every post-merge escape (a real defect that passed all gates and reached prove-live), attributing each escape to the gate(s) that missed it; compute **gate escape rate** and feed each escape back as a new scar-gate (closes R1).
- **Why it beats SOTA:** DORA measures escape loosely; no system measures per-gate escape rate against its own scar corpus and auto-generates the missing gate. Exploits full-lifecycle session ownership.
- **Cost:** low–moderate.
- **Gear:** 3.
- **Risk + scar family:** attribution noise. Allow multi-gate attribution.
- **Metric + method:** gate escape rate (escapes/gated merges) trending down; # escapes → armed scar-gates. Ledger queries.
- **Kill criterion:** escapes unattributable after 90 days → downgrade to plain incident log.
- **First PR:** *escape ledger schema + 1 retrofitted entry + report* — `infra/verification/escape_ledger/*`; ≤400 lines; Gear 3; acceptance: one historical escape recorded with gate attribution and reported.

---

## 6. 90-day roadmap

**Wave 1 (days 0–30) — arm what is already known.** R1 first PR (arm top-5 scars), R2 (no-weakening lint), R3 (scheduled guard-fuzz + telemetry), R4 (retracted-claims scaffold). Establish baselines: armed count, weakening blocks, corpus size, registered claims.

**Wave 2 (days 31–60) — measure the judges, add redundancy.** R6 (judge battery), R5 (N-version final gate), R7 (escape ledger). Wire escape ledger → scar-gate pipeline so each escape auto-proposes an R1 arm.

**Wave 3 (days 61–90) — route on calibration, close the loop.** Calibration-driven refuter routing (from R6); gate escape-rate review + re-arm from R7; re-enable advisory AI PR review with the trust-dialog fix (**needs-ruling**); promote `guard-conformance` + retracted-claims lint to required checks (**needs-ruling** / operator).

**First PRs (Wave 1):**

| Title | Files | ≤ lines | Gear | Acceptance test |
|---|---|---|---|---|
| Arm top-5 recurrent scar-gates | `infra/scar-gates/test_W<N>_*.py` ×5, `MANIFEST.json` | 400 | 2 | MANIFEST.armed==7; `verify_the_verifiers.py --scope repo` reports ARMED |
| no-weakening lint | `scripts/lint_no_weakening.py`, tests, workflow | 400 | 2 | fixture test-deletion fails; waiver passes |
| scheduled guard-fuzz + telemetry | cron workflow + artifact writer | 400 | 2 | scheduled run emits corpus-size+robustness; fails on injected mismatch |
| retracted-claims scaffold + auto-lint | `scripts/scaffold_retracted_claim.py`, test | 400 | 2 | sample claim caught; RETRACTED directive absolves |

---

## 7. Needs-ruling (Legge-5 business decisions)

1. **Re-enable advisory AI PR review** (`ai-pr-review.yml.disabled-…`): the file itself states re-enabling "is a deliberate 'turn a real feature back on' decision for the codeowner (Legge 5 territory — it changes what gets spent)." Requires owner consent on spend + `CLAUDE_CODE_OAUTH_TOKEN` + the CI-side trust-dialog fix.
2. **Promote gates to required branch-protection checks** — `guard-conformance.yml` carries an explicit "ARMING NOTE (operator): … a branch-protection change — operator-only," and the retracted-claims lint likewise.
3. **Budget/quota policy for the N-version final gate (R5)** — how many OAuth seats per Gear-3 PR, on flat subscriptions only.
4. **Confirm CLI-only / no-paid-Anthropic-API for any new verifier seat** (hard rule) — owner to ratify any seat additions.
5. **Meta-verifier integrity changes** — any update to the sha256 baseline / CODEOWNERS for `verify_the_verifiers.py` requires `@Balizero1987` review.

---

## 8. §Meta-pattern (modus Gear 3)

**The repeating defect:** across every finding, one belief generates the disease — ***"declaring a control is the same as the control operating."*** Existence/naming is substituted for demonstration; "la prova può essere vuota" (the proof can be empty) and still read as clean.

The pack is a catalogue of exactly this:
- `MANIFEST.json` — 64/66 scar-gates **declared** (`prose_only: true`), not armed.
- **W81** — tests that exist but no workflow runs ("theater"), which `check_guard_conformance.py` C4 exists to kill.
- **W64 / catC** — "the canary exists, runs, and lies" (a tautological self-substring check).
- **superscar #2 / ai-pr-review** — a job reporting `success` while doing zero work ("green that lies").
- **W108** — a required adversarial-review corpus that "was never executed" until armed.
- `final-gate-discipline` Q1 — "zero callers means you've **declared** it, not finished it"; and the lesson title *"a comment promising visibility is not a caller."*
- `check_guard_conformance.py` C2/C3 — phantom test references (W65).

**The antidote the organism already encodes:** every proof must be (a) **executed now** by a command, not recalled; (b) **reachable/armed**, not merely present; and (c) **bidirectional** — able to say both *yes* and *no* (guilt **and** innocence). Every recommendation above is a mechanism for converting a declared control into an executed, measured one. That is the single defective belief to retire.

---

## 9. Sources

1. Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, 2023 — https://arxiv.org/abs/2306.05685 — accessed 2026-08-28 — canonical measurement of LLM-judge biases.
2. Irving, Christiano, Amodei, *AI Safety via Debate*, 2018 — https://arxiv.org/abs/1805.00899 — accessed 2026-08-28 — theoretical basis for adversarial refuter seats.
3. Khan et al., *Debating with more persuasive LLMs leads to more truthful answers* (Anthropic), 2024 — https://arxiv.org/abs/2305.14763 — accessed 2026-08-28 — debate improves truthfulness; judge-persuasion risk.
4. OpenAI, *Catching AI hallucinations with CriticGPT*, 2024 — https://openai.com/index/catching-ai-hallucinations-with-criticgpt/ `(unverified)`; arXiv *LLM Critics Help Catch LLM Bugs* — https://arxiv.org/abs/2407.00215 — accessed 2026-08-28 — critics find bugs but hallucinate; W65 analog.
5. Alshahwan et al., *Automated Unit Test Improvement using LLMs at Meta* (TestGen-LLM), 2023 — https://arxiv.org/abs/2302.06527 — accessed 2026-08-28 — assured generator≠grader pipeline; ~73% rejection.
6. Petrović & Ivanković, *State of Mutation Testing at Google*, 2018 — https://research.google/pubs/pub46584/ `(unverified)` — accessed 2026-08-28 — org-scale mutation methodology.
7. Google OSS-Fuzz, 2016– — https://github.com/google/oss-fuzz — accessed 2026-08-28 — continuous fuzzing at scale.
8. Sadowski et al., *Modern Code Review: A Case Study at Google*, 2018 — https://research.google/pubs/pub47025/ `(unverified)` — accessed 2026-08-28 — small CLs + presubmit static triage.
9. Newcombe et al., *How Amazon Web Services Uses Formal Methods*, CACM 2015 — https://cacm.acm.org/magazines/2015/4/184701-how-amazon-web-services-uses-formal-methods/full-text `(unverified)` — accessed 2026-08-28 — TLA+ on critical services.
10. AWS Automated Reasoning / verified s2n (SAW/Dafny) — https://www.amazon.science/blog/automated-reasoning `(unverified)` — accessed 2026-08-28 — machine proofs for narrow invariants.
11. Avizienis, *The N-Version Approach to Fault-Tolerant Computing*, 1985 — https://doi.org/10.1109/TSE.1985.231875 `(unverified)` — accessed 2026-08-28 — independent implementations + voting.
12. NASA IV&V Program — https://www.nasa.gov/mission/independent-verification-and-validation/ `(unverified)` — accessed 2026-08-28 — independent-org verification.
13. OpenAI, *Why language models hallucinate*, 2025 — https://arxiv.org/abs/2509.04664 `(unverified)` — accessed 2026-08-28 — eval/reward pressure drives test-tampering.
14. Anthropic, *Alignment faking in large language models* (sycophancy→subterfuge), 2024 — https://arxiv.org/abs/2412.14093 `(unverified)` — accessed 2026-08-28 — strategic compliance/deception under pressure.
15. Chen et al., *Monitoring reasoning models for misalignment* (OpenAI), 2025 — https://arxiv.org/abs/2503.14499 `(unverified)` — accessed 2026-08-28 — CoT monitoring catches test-tampering intent.
16. Agentic PR-review products: CodeRabbit — https://www.coderabbit.ai; Cursor Bugbot — https://cursor.com/blog/bugbot `(unverified)`; GitHub Copilot code review — https://github.blog `(unverified)` — accessed 2026-08-28 — live LLM PR review at scale (organism's analog is currently disabled).

*Report returned inline as the final message (no file write possible in this lane; the §4 `ls`/`wc` post-write probe is therefore N/A).*