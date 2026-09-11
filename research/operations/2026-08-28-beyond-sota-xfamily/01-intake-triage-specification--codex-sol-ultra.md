---
panel: beyond-sota-xfamily
lane: 01-intake-triage-specification
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T18:24:29Z
finished: 2026-08-28T18:35:14Z
duration_s: 645
exit: 0
words: 4935
prompt_sha256_16: 586d1ccb46ef40a0
prompt_chars: 18464
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 1/13 — Intake, triage & specification
model: OpenAI GPT-5.6 sol at reasoning effort ULTRA (Codex CLI, pinned lane)
sources: 14
repo_files_verified: 18
status: complete
---

## 0. **TL;DR**

- Nuzantara is ahead of SOTA in intake doctrine breadth, cost-aware gearing, scar-informed grounding, and full-lifecycle product artifacts—but behind in machine-enforced semantic triage.
- The largest gap is that the system often treats the existence of prose, reference hooks, or an evidence pack as proof that intake actually governed execution.
- The deterministic gear floor is computed from the eventual diff, so it catches scope growth late and cannot recognize semantic risk before the first edit.
- Top move 1: compile a semantic pre-edit gear prior and reconcile it with the post-diff CI floor.
- Top move 2: introduce an evidence-bearing intake receipt linking the mandate, assumptions, verified premises, PII scope, acceptance probes, appetite, and kill criterion.
- Top move 3: mechanize Rule 8 so repeated same-cause failures suspend into specification debt instead of producing another correction.
- Target after 90 days: under-geared escapes below 1%, same-cause fix chains below 2%, zero phantom premises, and over 90% of product changes with red journey acceptance before implementation.

## 1. **How Nuzantara does it today**

### From colloquial mandate to provisional gear

Nuzantara’s Language Protocol expects the agent to translate short, colloquial Italian into technical action without asking “what do you mean?” When two readings are plausible, it instructs the agent to select the most likely interpretation and state the assumption in one line (`CLAUDE.md`). This is optimized for a solo owner who does not review code and should not have to become the requirements engineer.

There is a real doctrinal conflict: `karpathy-discipline` says to state assumptions, expose multiple interpretations, and stop for clarification when ambiguity matters, while `CLAUDE.md` says to infer rather than ask. Neither file gives a shared decision rule based on reversibility, business authority, PII, or the behavioral distance between interpretations (`.claude/skills/karpathy-discipline/SKILL.md`, `CLAUDE.md`). The result is model-dependent behavior at the most consequential intake boundary.

`modus` assigns a provisional gear from the mandate and historical ledgers before grounding:

- Gear 1 covers mechanical, known-cause, usually one-file changes.
- Gear 2 covers ordinary features, fixes, research deliverables, and PR work with an independent reviewer.
- Gear 3 covers architecture, migrations, deep audits, cross-system changes, pre-deploy work, or mandates such as “go alone, do not stop.”

Grounding may only raise the gear. The doctrine also has an anti-waste ceiling: councils and broad fan-out require divergent priors capable of changing the result, sufficiently high error cost, and genuinely parallel units of work. Small or documentary changes that request a council or three graders require a reasoned override (`.claude/skills/modus/SKILL.md`).

This is stronger than a simple complexity label: it attempts to control both under-gearing and deliberation waste. However, “Gear 1/2/3” coexists with a separate “Preflight SDD L1/L2/L3” scale for authorization and review depth (`CLAUDE.md`, `AUTONOMOUS_OPS.md`). The two axes are not explicitly mapped. An agent can therefore confuse change risk with operating authority.

### Stadio Zero grounding

For nontrivial work, the repository-local Stadio Zero command requires a short pre-edit study:

1. retrieve relevant memory/scar lessons;
2. verify load-bearing files and lines on disk in the current turn;
3. classify PII scope explicitly;
4. write a binary, falsifiable acceptance condition;
5. search for reusable machinery before proposing new code.

Its output is intended to be structured evidence, not a ceremonial file. True one-line work may skip it, and a generated artifact is discouraged when no downstream gate consumes it (`.claude/commands/stadio-zero.md`). This is an unusually mature response to reward hacking.

The user-specified `/Users/nuzantara/.claude/skills/stadio-zero/SKILL.md` and every `MEM:` source were outside this lane’s permitted snapshot and were not read. Therefore, the repository command is the only verified Stadio Zero source here, and no claim is made about external memory contents.

### Specification and product-factory artifacts

For product work, `docs/factory/ASSEMBLY-LINE.md` supersedes generic modus. Its five-artifact set is:

1. product intent, metric, guardrails, non-goals, appetite, kill criterion, and owner log;
2. customer journeys expressed as state transitions, including failure and recovery;
3. contracts such as OpenAPI, types, events, errors, and compatibility;
4. code and tests;
5. operational proof through SLOs, synthetic probes, alerts, and runbooks.

Its lifecycle runs through intent, grounding, red-first journeys, contract freeze, build, gauntlet, dark release, and operation. Its strongest rule is that an artifact exists only if a gate consumes it (`docs/factory/ASSEMBLY-LINE.md`).

The Garuda VOA mandate demonstrates the pattern concretely: problem statement, source assets, primary metric, guardrails, kill criterion, owner switchboard, lanes, contract freeze, red-first journeys, and gates are defined before product construction (`docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`). One unresolved tension remains: that mandate marks the kill criterion as proposed while permitting dark work to begin, whereas the Assembly Line’s G0 model expects owner intent to be settled before the product factory advances.

The factory document records why this machinery exists: among the preceding 100 merged PRs, 39 were documentation, research, or ledger work, while an earlier audit classified 56% of product work as unreproducible (`docs/factory/ASSEMBLY-LINE.md`). It also admits that several enforcement mechanisms remain backlog items, including reliable gate-consumption checks and consistent independent refuters.

### Hooks and deterministic CI floors

The phase-aware hooks are currently weak signals rather than proof:

- `infra/claude-hooks/stadio_zero_nudge.py` sends a nonblocking reminder before a first edit. Its evidence of prior study is based partly on transcript markers and a young-session line window.
- `infra/claude-hooks/premise_gate.py` warns when an edited file does not appear to have been inspected. It is warn-only, excludes several locations, covers Edit/MultiEdit rather than every write path, and infers grounding from broad transcript evidence.
- `infra/claude-hooks/README.md` explicitly says repository hook files are reference copies; executable hooks live outside the repository.

Consequently, this lane can verify hook design but not hook deployment, parity, or effectiveness. The reference-versus-runtime split is itself an intake-control risk.

The hard control is later. `scripts/evidence_pack_lint.py` computes a post-diff floor:

- Gear 3 for configured hot zones or at least 1,828 changed lines;
- Gear 2 for at least 400 changed lines;
- otherwise Gear 1.

It also applies a ceiling to small/doc-only Gear-3 work that declares a council or at least three graders without a `gear_override`. The classifier’s hot zones include migrations, auth, configuration, pricing, invoicing, workflows, ownership, and deployment surfaces (`scripts/evidence_pack_lint.py`).

`.github/workflows/harness-floor.yml` recomputes this classification from the merge-base diff, validates the evidence pack, and rejects stale or mismatched root artifacts. As of the report date, its newer size-based Gear-2 floor was still in a grace period ending 2026-09-02 (`.github/workflows/harness-floor.yml`). `evidence/brief.yml` and `evidence/pack.yml` show a rich Gear-3 example with diagnosis, constraints, consumer map, acceptance tests, risks, PII scope, graders, and receipts.

This provides strong post-hoc containment, but it is not yet a semantic intake classifier. A small authorization bypass, irreversible state transition, or PII leak can remain Gear 1 if it avoids named paths. Conversely, a mechanically large safe rewrite can become Gear 3 solely from churn.

### Rule 8 and autonomous authority

Rule 8 says that three red rounds for the same cause suspend the PR into `PENDING-ARMS`; a fix-of-fix may go only one level deep, after which the surface must be specified rather than patched again (`CLAUDE.md`). This converts repeated correction into evidence of an inadequate specification.

`AUTONOMOUS_OPS.md` grants Level-2 lifecycle authority but says certification older than 30 days should fall back conservatively. Its internal recertification date is 2026-07-19—41 days before this report—so the written contract currently requires either recertification or conservative fallback (`AUTONOMOUS_OPS.md`). That is an intake authority issue, not merely administrative freshness.

## 2. **Scars & ledger evidence in this area**

| Evidence | Finding | Intake implication |
|---|---|---|
| Superscar #6 | Phantom paths, invented file lines, stale ground truth, and blind reviewer agreement recur as anti-hallucination failures (`.claude/rules/cicatrix-superscar.md`). | Grounding must carry machine-verifiable provenance, not a prose claim that files were read. |
| W113 | A correction to one false research claim introduced three new false replacements; the work reached a fourth round despite 31 objections, 29 valid, and none waived (`.claude/rules/cicatrix-scars.md`). | Corrections need fresh acceptance and specification, not reduced scrutiny because they are “fixes.” |
| W125 | Shared root evidence paths collided across work; five PRs accumulated 11 merge commits, and a foreign field entered outside the expected markers (`.claude/rules/cicatrix-scars.md`). | Intake artifacts need per-task identity and ownership, not shared filenames. |
| W109 | A guard judged location/proxy evidence rather than the actual protected entity (`.claude/rules/cicatrix-scars.md`). | Risk classification must test semantics and consumers, not only filenames or substrings. |
| PENDING-ARMS | A Gear-3 gate caught a CI bootstrap that had dropped a production constraint even though tests were green (`.claude/skills/modus/PENDING-ARMS.md`). | Green execution is not equivalent to a complete acceptance contract. |
| AMENDMENTS | A 44-hour plus 31-hour work period produced 180 PRs, 8.6M tokens, and roughly ten business commits; one PR took 14 commits, 11 rounds, and about six hours (`.claude/skills/modus/AMENDMENTS.md`). | Triage itself needs a stop-loss; “more panel” is not the cure for a poorly specified surface. |
| AMENDMENTS | Other rows record reasoning from nonexistent remembered paths, late Gear-3 discovery, three wrong theories before environment comparison, and four pushes that destroyed the acceptance metric (`.claude/skills/modus/AMENDMENTS.md`). | Grounding, environment identity, and acceptance invariants must be compiled before construction. |

### Measurements

**Triage/gear amendments.** The amendments file contains 33 dated rows. Under a deliberately narrow definition—an entry whose primary failure was wrong gear or triage rather than a downstream implementation defect—one row qualifies: 1/33, or 3.0% (`.claude/skills/modus/AMENDMENTS.md`). This is not evidence of a 3% mis-triage rate; the file has no mandatory typed failure taxonomy, so misfires embedded in other rows are not countable.

**Gear overrides.** There are 38 repository evidence briefs declaring Gear 3; none carries a nonempty top-level `gear_override`: 0/38. This says the sampled packs did not use the explicit over-gear escape hatch. It does not prove that all 38 were correctly geared. The linter itself records a separate audit in which 65% of sampled changes declared Gear 3 while only 70% dispatched graders (`scripts/evidence_pack_lint.py`).

**Fix-of-fix proxy.** Git history for 2026-08-15 through 2026-08-28 yielded 864 first-parent, PR-like merges. A conservative title heuristic flagged 59—6.8%—when the title referenced an earlier PR before its terminal merge number or used explicit correction language such as `post-refuter`, `fix-of-fix`, repair/retraction of previous work, “shipped red,” “left broken,” or “again.” This is a lower-bound merge-history proxy, not a semantic PR audit: the snapshot lacked usable GitHub PR metadata, and unrelated follow-ups can match while quietly corrective PRs can evade it.

The evidence supports two simultaneous conclusions. Rule 8 is based on genuine pain, not aesthetics; and its current prose form has not yet converted repeated failures into reliably measurable specification debt.

## 3. **World SOTA survey**

| System or practice | Primary source | Mechanism | Published effect | Transferability |
|---|---|---|---|---|
| GitHub Spec Kit | [Official documentation](https://github.github.com/spec-kit/) | Intent-driven Specify → Plan → Tasks → Implement workflow, templates, checklists, and cross-artifact analysis. | No causal productivity metric published. | Strong fit for contract-first structure; Nuzantara should add evidence provenance, PII, gear, appetite, and kill criteria rather than copy its generic templates. |
| Kiro Specs | [Official documentation](https://kiro.dev/docs/) | Requirements, design, and task artifacts; separate bug-fix specification flow; steering and hooks keep intent present during execution. | No public causal effect measurement. | Useful shape for ordinary Gear-2 work, but cloud/tool assumptions require CLI-only and local-sovereignty adaptation. |
| OpenSpec | [Official schema](https://openspec.dev/docs/schemas/spec-driven) | Proposal, specs, design, and tasks form a dependency graph; requirements require behavioral scenarios and validation rejects empty deltas. | No published outcome metric. | Best lightweight external model for a machine-lintable intake receipt and behavior deltas. |
| Amazon Working Backwards | [AWS DevOps Guidance](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/devops-guidance/devops-guidance.pdf) | PR/FAQ begins with customer value, adoption, use cases, FAQs, and internal alignment before implementation. | Guidance associates it with fewer errors and faster delivery but publishes no isolated causal number. | Product mandates should retain customer/problem/metric framing, while small operational changes should use a smaller receipt. |
| Shape Up | [Basecamp, “Principles of Shaping”](https://basecamp.com/shapeup/1.1-chapter-02) | Fixed appetite, shaped problem, boundaries, rabbit holes, pitch, betting, and the ability to shelve unready work. | No controlled quantitative result. | Appetite and “do not bet unshaped work” directly strengthen gear ceilings and Rule 8 suspension. |
| Gherkin/BDD | [Cucumber reference](https://cucumber.io/docs/gherkin/reference/) | Given/When/Then examples turn behavior into executable, stakeholder-readable acceptance. | No global causal metric; the artifact is executable by design. | Excellent for journey red-first and failure/recovery cases, provided scenarios reference real tests rather than becoming prose theater. |
| Claude Code workflow | [Anthropic engineering guidance](https://www.anthropic.com/engineering/claude-code-best-practices) | Explore relevant files, plan, implement, and verify; task descriptions identify files, constraints, and success criteria. | No controlled effect reported. | Closely aligned with Stadio Zero, but Nuzantara’s scars justify stronger current-turn provenance and a deterministic receipt. |
| OpenAI Codex practice | [OpenAI guide](https://openai.com/business/guides-and-resources/how-openai-uses-codex/) | Well-scoped issue-like prompts include component, files, documentation, and target behavior; ask-mode supports planning before implementation. | OpenAI reports fewer errors qualitatively, without a public causal percentage. | Fits Gear-1/2 scoped work and the ≤400-line concern rule; no substitute for owner-boundary or PII classification. |
| Google design review | [Google Research, ASE 2023](https://research.google/pubs/improving-design-reviews-at-google/) | Structured automation targets reviewer assignment and review latency while preserving human design judgment. | Across 141,652 approved documents and 41,030 users, median approval time fell 25%. | Nuzantara cannot copy large-team review, but can automate intake completeness and route only true owner decisions to Zero. |
| ClarifyGPT | [ACM FSE 2024](https://doi.org/10.1145/3660810) | Detect ambiguity from inconsistent generated programs, ask targeted questions only for ambiguous tasks, then refine requirements. | GPT-4 Pass@1 rose 70.96%→80.80%; five-benchmark averages rose 62.43%→69.60% for GPT-4 and 54.32%→62.37% for ChatGPT. | Proves unconditional “never ask” is technically weak. For this organism, clarification should be restricted to material, irreversible, or owner-only ambiguity. |
| SpecFix | [ASE 2025 preprint](https://arxiv.org/abs/2505.07270) | Differentially samples program interpretations, measures semantic entropy/example consistency, and minimally repairs requirements. | Overall Pass@1 +4.3%; modified requirements +33.66%; cross-model transfer +9.6%. | Particularly suitable for acceptance examples: use the fleet to expose divergent interpretations before asking the owner. |
| Industrial ambiguity detection | [Industrial study](https://www.es.mdh.se/pdf_publications/7221.pdf) | Retrieves domain-relevant few-shot examples and produces ambiguity classification plus explanation. | Ten-shot prompting improved classification 20.2% over zero-shot; eight experts rated explanations 3.84/5. | The scar corpus can supply sovereign, domain-specific demonstrations, with only abstracted non-PII examples entering shared artifacts. |
| TLA+ at AWS | [Amazon Science](https://www.amazon.science/publications/how-amazon-web-services-uses-formal-methods) | Executable state models and exhaustive model checking expose distributed-system behaviors conventional tests miss. | AWS reports use on critical services since 2011; the paper is experiential rather than a single controlled percentage. | Apply selectively to irreversible state machines, migrations, queues, and authorization—not routine features. |
| Kubernetes issue triage | [Kubernetes contributor guide](https://www.kubernetes.dev/docs/guide/issue-triage/) | Machine labels encode kind, priority, ownership, evidence needs, and follow-up status; unresolved reports receive explicit information and time-bound states. | No causal defect metric published. | PENDING-ARMS and amendments need comparable typed states so triage debt can be measured rather than grepped. |

### What matters most

First, external spec frameworks agree that requirements must decompose into behavioral artifacts and tasks, but they usually stop at artifact presence. Nuzantara’s “artifact exists only if a gate consumes it” principle is stronger—if it becomes mechanically true.

Second, ClarifyGPT and SpecFix demonstrate that ambiguity is observable through divergent program behavior. This offers a better reconciliation of the repository’s conflicting language rules: generate discriminating examples first, infer when evidence resolves them, and ask only when materially different interpretations remain.

Third, Google shows that structuring the review intake—not merely adding reviewers—can reduce latency by 25%. For a solo owner, the transfer is to minimize owner interrupts by compiling complete decision packets.

Fourth, AWS formal methods show where natural-language acceptance reaches its limit. Formalization should be triggered by state-space and irreversibility, not by code size alone.

## 4. **Position vs SOTA**

| Sub-dimension | Position | Evidence and judgment |
|---|---|---|
| Grounding doctrine | **AHEAD** | Stadio Zero combines current-turn file proof, scars, reuse, PII, and falsifiable acceptance (`.claude/commands/stadio-zero.md`). Most surveyed agent guidance asks for context but does not require provenance. |
| Grounding enforcement | **BEHIND** | The reference hooks are warn-only or transcript-marker-based, and runtime copies are outside the repository (`infra/claude-hooks/stadio_zero_nudge.py`, `infra/claude-hooks/premise_gate.py`, `infra/claude-hooks/README.md`). |
| Cost-aware triage | **AHEAD conceptually** | Modus has both a risk floor and deliberation ceiling, plus explicit council economics (`.claude/skills/modus/SKILL.md`). No surveyed spec framework couples specification depth to fleet cost this explicitly. |
| Semantic risk detection | **BEHIND** | The hard floor operates after a diff and uses churn/path hot zones (`scripts/evidence_pack_lint.py`). It cannot recognize small semantic hazards or premise uncertainty before editing. |
| Product specification | **AHEAD in design, BEHIND in adoption** | The five artifacts cover intent through operations and demand red-first journeys (`docs/factory/ASSEMBLY-LINE.md`), yet the same document reports 56% unreproducible work and admits incomplete enforcement. |
| Ambiguity management | **BEHIND** | `CLAUDE.md` and `karpathy-discipline` conflict. ClarifyGPT and SpecFix supply measurable mechanisms for selectively resolving ambiguity. |
| Failure stop-loss | **AHEAD in doctrine, BEHIND mechanically** | Rule 8 is empirically motivated, but the 6.8% corrective-chain proxy and W113 show the suspension transition is not dependable (`CLAUDE.md`, `.claude/rules/cicatrix-scars.md`). |
| Formal critical-path specifications | **BEHIND** | Journey and contract artifacts are rich, but the verified intake corpus contains no risk-triggered model-checking policy comparable to AWS’s practice. |
| Owner-fit and autonomy | **AHEAD structurally, currently ambiguous** | Mandates isolate owner switchboard decisions and permit autonomous dark work (`docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`), but the autonomy recertification has exceeded its written interval (`AUTONOMOUS_OPS.md`). |
| Triage telemetry | **BEHIND** | AMENDMENTS and PENDING-ARMS are rich narrative stores but lack a mandatory typed taxonomy, preventing reliable precision, recall, recurrence, or cost measurement. |

## 5. **Beyond-SOTA recommendations**

The ranking uses expected impact × confidence divided by implementation cost. “Beyond SOTA” is scoped to the surveyed systems: no surveyed system combines the listed mechanisms.

### 1. Dual-phase Gear Compiler

**What.** Compute a semantic gear prior before the first edit from irreversibility, PII, owner authority, consumer count, state-space, uncertainty, and scar similarity. Recompute the existing diff-based posterior in CI. The final floor is the maximum; the ceiling applies only when both stages classify the task as cheap.

**Why it beats SOTA.** It composes Nuzantara’s scars and fleet economics with deterministic diff risk. External spec tools structure work but do not reconcile pre-edit semantic risk with a post-edit floor and a deliberation ceiling.

**Cost and gear.** 18–26 engineering hours, flat-subscription tokens only. Gear 3 for classifier design; Gear 2 for a shadow-only first PR.

**Risk.** Superscar #9, schema/proxy drift; #3, substring guards masquerading as semantics.

**Metric.** Audit 100 consecutive changes: severe-risk recall 100%, under-geared escape rate below 1%, manual overrides below 15%, and Gear-3 share reduced from the observed 65% to a calibrated 25–35% without increased escaped findings.

**Kill criterion.** Stop deployment if any known severe case is classified Gear 1, or if override rate remains above 15% after two calibration cycles.

**First PR.** `feat(intake): add shadow semantic gear prior`; new `scripts/intake_gear_shadow.py`, tests, and `docs/specs/intake-gear-v1.md`; one concern, ≤400 net lines, no CI blocking.

### 2. Evidence-bearing Intake Receipt

**What.** Compile each nontrivial mandate into a task-scoped receipt containing literal mandate, chosen assumption, rejected interpretations, verified `path@blob`, PII classification, consumers, acceptance probes, appetite, non-goals, owner-only decisions, kill criterion, provisional gear, and expiry.

**Why it beats SOTA.** Spec Kit/OpenSpec structure requirements; this adds anti-hallucination provenance, sovereignty, operating authority, scar evidence, and measurable appetite in one gate-consumed artifact.

**Cost and gear.** 16–24 hours; Gear 3 design, Gear 2 implementation.

**Risk.** Superscar #6 if provenance can be invented; #2 if receipt presence is mistaken for consumption; #9 if the schema forks.

**Metric.** Zero phantom paths in a 100-receipt audit; 100% load-bearing claims resolve to the recorded blob; time-to-first-valid-spec down 40%; fewer than 5% expired receipts reaching build.

**Kill criterion.** Remove any field not consumed by a named gate after 30 tasks; abandon the format if median preparation exceeds 10% of task appetite without reducing rework.

**First PR.** `feat(intake): define and lint intake receipt v1`; new schema, `scripts/intake_receipt_lint.py`, and unit tests, ≤400 lines.

### 3. Rule-8 Specification-Debt Circuit Breaker

**What.** Fingerprint red causes by surface, invariant, and failing probe. Three same-cause reds or a correction depth above one transitions the work to `SUSPENDED_SPEC_REQUIRED`, emits one typed PENDING-ARMS item, and requires a new failing acceptance case before resumption.

**Why it beats SOTA.** Shape Up can shelve unshaped work, and issue trackers can label it; this binds repeated machine evidence to an automatic specification transition and preserves the causal chain.

**Cost and gear.** 12–20 hours; Gear 2.

**Risk.** Superscar #3 if fingerprinting is substring-based; #2 if the suspension record is emitted but does not block another correction.

**Metric.** Corrective-chain proxy from 6.8% to below 2%; same-cause round p95 at three; zero fourth-round continuations; false suspension below 10%.

**Kill criterion.** Return to warn-only if false suspensions exceed 10% across 50 cases or developers bypass more than 5% without a new specification.

**First PR.** `feat(harness): shadow repeated-cause specification debt`; new `scripts/spec_debt_gate.py` and fixture-based tests, ≤350 lines.

### 4. Artifact Consumption Graph

**What.** Give product promises, journeys, contracts, tests, probes, and kill criteria stable IDs. Require each load-bearing node to have a downstream consumer and each verification node to point back to intent. Only relevant artifacts are required.

**Why it beats SOTA.** OpenSpec provides artifact dependencies and BDD provides executable scenarios; this creates a full intent-to-live-proof graph across the five-artifact factory.

**Cost and gear.** 24–36 hours; Gear 3.

**Risk.** Superscar #2, “exists equals armed”; #9, identifier/schema drift.

**Metric.** Unconsumed load-bearing fields at zero; over 90% of product PRs possess a red journey before implementation; unreproducible product changes fall from the recorded 56% to below 10%.

**Kill criterion.** Simplify the graph if maintaining links exceeds 15% of product appetite or more than 10% of links are stale after two releases.

**First PR.** `feat(factory): link journey acceptance IDs to consuming tests`; update `docs/factory/ASSEMBLY-LINE.md`, add one schema/linter and fixtures, ≤400 lines.

### 5. Material-Ambiguity and Authority Protocol

**What.** Replace “always infer” versus “always ask” with a decision table:

- generate two discriminating behavioral examples;
- if repository evidence eliminates one interpretation, proceed;
- if interpretations differ materially but the choice is reversible, record the assumption and proceed;
- if irreversible, PII-sensitive, outward-publishing, credential-dependent, or a business decision, route a minimal `needs-ruling` packet to Zero.

**Why it beats SOTA.** ClarifyGPT asks targeted questions and SpecFix repairs from behavioral distributions. Nuzantara can additionally incorporate reversibility, Legge-5 authority, and owner-interruption cost.

**Cost and gear.** 6–10 hours; Gear 2.

**Risk.** Superscar #6 if invented evidence resolves ambiguity; #3 if a keyword list replaces behavioral comparison.

**Metric.** Unnecessary clarification rate below 5%; assumption-caused rework below 2%; 100% of owner-only decisions explicitly routed; acceptance Pass@1 before/after on a 30-task ambiguity corpus.

**Kill criterion.** Revert if silent wrong assumptions increase over baseline or owner interruptions do not fall by at least 30%.

**First PR.** `fix(doctrine): unify ambiguity and owner-boundary intake`; modify only `CLAUDE.md`, `.claude/skills/karpathy-discipline/SKILL.md`, and `.claude/commands/stadio-zero.md`, ≤200 lines.

### 6. Typed Triage Telemetry

**What.** Record prior gear, posterior gear, override reason, ambiguity class, intake duration, token cost, lead time, red rounds, final outcome, and superscar family. Generate a monthly confusion matrix.

**Why it beats SOTA.** The organism uniquely possesses a large scar and amendment corpus, but currently cannot use it as supervised triage data.

**Cost and gear.** 8–12 hours; Gear 2.

**Risk.** Superscar #9 through taxonomy drift; #2 through logs that no review consumes.

**Metric.** 100% of Gear-2/3 work has a typed outcome; prior/posterior disagreement and under-gear recall become calculable; untyped AMENDMENTS rows fall from 100% to zero for new entries.

**Kill criterion.** Remove any field unused in a monthly calibration decision after two cycles.

**First PR.** `feat(modus): add typed triage outcome schema`; schema, append helper, fixtures, and aggregate command, ≤400 lines.

### 7. Selective Executable Formalization

**What.** Trigger Given/When/Then plus a small state/property model for irreversible migrations, authorization, durable queues, and multi-consumer state machines. Routine features retain ordinary acceptance tests.

**Why it beats SOTA.** It connects AWS-style model checking to the Gear Compiler instead of applying formal methods indiscriminately.

**Cost and gear.** 20–40 hours for one pilot; Gear 3.

**Risk.** Superscar #2 if a model is never run; #9 if it diverges from implementation.

**Metric.** At least one pre-code counterexample or killed behavioral mutant in the pilot; formalization below 15% of appetite; every modeled property mapped to a test or live invariant.

**Kill criterion.** Do not expand if two pilots find no counterexample and exceed the 15% appetite budget.

**First PR.** `docs(spec): define formalization trigger and one executable pilot`; one critical state machine, its runner, and acceptance fixtures, ≤400 lines.

## 6. **90-day roadmap + first PRs**

| Wave | Outcome | First PRs and acceptance |
|---|---|---|
| **Days 0–30: make intake observable** | Resolve language conflict, introduce receipt v1, run semantic gear classification in shadow mode, start typed telemetry. | **PR 1:** `fix(doctrine): unify ambiguity and owner-boundary intake`; three doctrine files, ≤200 lines, Gear 2; acceptance: the same decision table is rendered by all three. **PR 2:** `feat(intake): define and lint intake receipt v1`; new schema/linter/tests, ≤400 lines, Gear 2; acceptance: missing provenance, PII, acceptance, or expiry fails fixtures. **PR 3:** `feat(intake): add shadow semantic gear prior`; ≤400 lines, Gear 2; acceptance: known hot semantic fixtures classify at their expected minimum. |
| **Days 31–60: bind artifacts to consequences** | Shadow Rule-8 fingerprints, introduce stable journey/acceptance IDs, prove test consumption, and compare semantic prior with CI posterior. | **PR 4:** `feat(harness): shadow repeated-cause specification debt`; ≤350 lines, Gear 2; acceptance: the third identical cause suspends, different causes do not. **PR 5:** `feat(factory): link journey acceptance IDs to consuming tests`; ≤400 lines, Gear 3; acceptance: an orphaned promise or test fails the linter. |
| **Days 61–90: calibrate and enforce** | Set thresholds from observed confusion matrices, enforce the proven subset, pilot formalization on one irreversible state machine, and remove fields with no consumer. | **PR 6:** `feat(ci): enforce calibrated intake floor`; ≤300 lines, Gear 3; acceptance: CI uses `max(semantic_prior, diff_posterior)` and reasoned overrides. **PR 7:** `docs(spec): add one executable critical-path model`; ≤400 lines, Gear 3; acceptance: at least one seeded invalid transition is rejected and its property maps to a runtime/test consumer. |

Day-90 review should publish four before/after numbers: under-gear escape rate, unnecessary Gear-3 rate, same-cause correction rate, and journey-before-build coverage. Enforcement should expand only where the shadow data supports it.

## 7. **Needs-ruling**

1. **Autonomous authority:** Zero must recertify `AUTONOMOUS_OPS.md` Level 2 or accept its written fallback, because its internal recertification date has exceeded 30 days.
2. **G0 versus dark work:** Zero must decide whether dark product construction may begin while a kill criterion remains “proposed,” or whether G0 requires signed metric, guardrails, and kill threshold before any build.
3. **Automatic suspension authority:** Zero must approve whether the Rule-8 circuit breaker may block further correction automatically and select the acceptable false-suspension budget.
4. **Formalization appetite:** Zero must set the maximum percentage of product appetite that may be spent on critical-path formal specification before the pilot is killed.

No other recommendation requires a business ruling; classifier fields, schema shape, test design, and rollout mechanics are engineering decisions.

## 8. **§Meta-pattern**

The single defective belief is:

> If the correct doctrine or artifact exists, the task has been grounded and specified.

That belief generates both failure directions. Under-gearing occurs when a warning, file path, green test, or filled evidence pack stands in for semantic proof. Over-gearing occurs when more documents, graders, or council seats stand in for a sharper falsifiable question.

The cure is to treat intake as a compiler, not a conversation ritual:

`mandate → competing interpretations → verified premises → authority/PII boundary → semantic gear prior → executable acceptance → consumed artifact graph → post-diff gear posterior → measured outcome`

Every transition must have a typed input, an independent consumer, and a before/after metric. Nuzantara’s asymmetry is that it already owns the necessary raw material: a scar corpus, cross-family seats, full-lifecycle sessions, always-on local machines, deterministic CI, and a stop-loss ledger. Beyond-SOTA practice comes from closing that loop, not adding more prose.

## 9. **Sources**

1. [GitHub Spec Kit documentation](https://github.github.com/spec-kit/) — living documentation, accessed 2026-08-29. Authoritative first-party definition of its intent-driven specification workflow.
2. [Kiro documentation](https://kiro.dev/docs/) — living documentation, accessed 2026-08-29. First-party description of Specs, steering, hooks, and bug-fix workflows.
3. [OpenSpec specification-driven schema](https://openspec.dev/docs/schemas/spec-driven) — living schema, accessed 2026-08-29. Canonical artifact dependency and behavioral-scenario contract.
4. [AWS Well-Architected DevOps Guidance](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/devops-guidance/devops-guidance.pdf) — living AWS guidance, accessed 2026-08-29. Primary source for Working Backwards and PR/FAQ practice.
5. [Ryan Singer, *Shape Up*: Principles of Shaping](https://basecamp.com/shapeup/1.1-chapter-02) — 2019; accessed 2026-08-29. Primary Basecamp account of appetite, pitches, boundaries, and shelving.
6. [Cucumber Gherkin Reference](https://cucumber.io/docs/gherkin/reference/) — updated 2026-08-27; accessed 2026-08-29. Canonical executable-specification syntax and semantics.
7. [Anthropic, “Claude Code: Best Practices for Agentic Coding”](https://www.anthropic.com/engineering/claude-code-best-practices) — 2025-04-18; accessed 2026-08-29. First-party agent workflow guidance.
8. [OpenAI, “How OpenAI Uses Codex”](https://openai.com/business/guides-and-resources/how-openai-uses-codex/) — accessed 2026-08-29. First-party evidence on scoping agent tasks and prompt context.
9. [Ziftci and Greenberg, “Improving Design Reviews at Google”](https://research.google/pubs/improving-design-reviews-at-google/) — ASE 2023; accessed 2026-08-29. Primary industrial study covering 141,652 approved documents.
10. [Mu et al., “ClarifyGPT”](https://doi.org/10.1145/3660810) — published 2024-07-12; accessed 2026-08-29. Peer-reviewed primary evidence for targeted ambiguity clarification.
11. [Jia et al., “Automated Repair of Ambiguous Natural Language Requirements”](https://arxiv.org/abs/2505.07270) — 2025-05-12; accessed 2026-08-29. Primary SpecFix paper with cross-model Pass@1 measurements.
12. [Bashir et al., “Requirements Ambiguity Detection and Explanation with LLMs: An Industrial Study”](https://www.es.mdh.se/pdf_publications/7221.pdf) — 2025; accessed 2026-08-29. Primary evaluation on three industrial requirements datasets.
13. [Newcombe et al., “How Amazon Web Services Uses Formal Methods”](https://www.amazon.science/publications/how-amazon-web-services-uses-formal-methods) — 2015; accessed 2026-08-29. Primary AWS account of TLA+ use on critical distributed systems.
14. [Kubernetes Issue Triage Guide](https://www.kubernetes.dev/docs/guide/issue-triage/) — living contributor documentation, accessed 2026-08-29. Canonical project process for typed, evidence-bearing issue states.