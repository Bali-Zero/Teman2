---
panel: beyond-sota-xfamily
lane: 03-architecture-decision-making
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T18:35:14Z
finished: 2026-08-28T18:43:05Z
duration_s: 471
exit: 0
words: 5285
prompt_sha256_16: 168c635026c47cef
prompt_chars: 17578
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 3/13 — Architecture & design decision-making
model: OpenAI GPT-5.6 sol (pinned lane)
sources: 15
repo_files_verified: 20
status: complete
---

## 0. TL;DR

Nuzantara is **AHEAD of SOTA in architectural deliberation doctrine and biological constraint modeling, but BEHIND in turning decisions into canonical, executable, revisitable state**.
The largest gap is not lack of analysis: it is the discontinuity between 733 research artifacts, sparse canonical decision records, 170 registered organs, and the checks that actually govern change.
Its conditional heterogeneous council is stronger than generic LLM debate, but conflicting doctrine still makes the same council both “mandatory” and “only when justified.”
Top move 1: introduce a typed Architecture Decision Genome linking rationale, organs, laws, scars, metrics, and fitness functions.
Top move 2: calibrate the council gate empirically against confirmed finding yield per token, using blind cross-family evidence rather than agreement.
Top move 3: make decision expiry and supersession event-driven, so stale architecture cannot continue presenting itself as current truth.
The governing correction is: **an architecture report is evidence; architecture exists only when a decision changes executable constraints and remains connected to live outcomes.**

## 1. How Nuzantara does it today

### 1.1 The intended decision loop is unusually strong

The repository-local `sota-architecture-loop` defines an eight-stage lifecycle: frame the decision, ground it externally, reason from constraints, convene a council only when justified, decide with a falsifiable metric, execute, verify empirically, and capture the result. Its council gate requires all three of:

1. divergent priors could materially change the answer;
2. the cost of error is roughly more than fifteen times the council cost;
3. genuine parallel breadth exists.

It also correctly forbids consensus as the objective: proponents, constructive critics, and red-team seats produce falsifiable claims, while empirical evidence closes the decision. This is better than “ask several models and average them.” Evidence: `.claude/skills/sota-architecture-loop/SKILL.md`.

`modus` embeds the same idea into Gear selection. Gear 1 is mechanical; Gear 2 is normally one primary reasoner plus one adversarial review; Gear 3 permits architectural analysis but does not automatically authorize a council. Its anti-sperpero rule prefers one stronger agent with more reasoning budget unless at least three independent lanes exist. It also describes a deterministic ceiling preventing tiny diffs from claiming Gear 3 or several graders without an override. Evidence: `.claude/skills/modus/SKILL.md`.

The DESIGN stage requires a durable specification, alternatives or uncertainty, and a falsifiable success metric. Panel findings are only leads until independently re-grounded. The CAPTURE stage routes substantial work into research capture and loop failures into `AMENDMENTS.md`. Evidence: `.claude/skills/modus/SKILL.md`.

### 1.2 Council policy is internally contradictory

Three live doctrine surfaces disagree:

- The architecture loop and `modus` say the council is conditional on the three-part economic gate: `.claude/skills/sota-architecture-loop/SKILL.md`; `.claude/skills/modus/SKILL.md`.
- `CLAUDE.md:174` declares a “4-LLM panel mandatory pre-approval” for every architectural specification and critical pre-deploy path.
- `SYMBIOSIS.md:284` still describes confrontation as “not implemented,” despite later council workflows and specimens.
- `CLAUDE.md:120` describes the final gate at `max`, while `CLAUDE.md:130` says `xhigh` is the default and `max` is opt-in.

This is not cosmetic drift. A future session can obey any one of these texts and appear compliant while making a different cost and governance decision.

The advertised council composition is heterogeneous and asymmetric: Gemini as constructive researcher, Codex as red-team, Kimi as refuter, an optional NotebookLM verifier, followed by a sequential on-disk adjudicator. That is directionally excellent. However, the ledger says the worker-plane validator still encodes a retired three-route council and lacks a final-gate receipt validator; the entry remains open at `.claude/skills/modus/PENDING-ARMS.md:721`. The distinction is therefore “designed council” versus “fully verified council mechanism.”

### 1.3 SYMBIOSIS laws operate as architectural constraints

`SYMBIOSIS.md` makes architectural design answer five questions: location in the organism, agentic role, respect for prior learning, present improvement, and measurable future effect. Its load-bearing laws include CLI-only LLM access, PII-output minimization, event-driven durability, graceful degradation, local sovereignty, Zero as final authority, and “numbers first.” Structural decisions must pass through Zero, and an unmeasured improvement remains a hypothesis (`SYMBIOSIS.md:271-273`).

This is stronger than a conventional principles page because several laws have migrated into executable controls. Yet the file itself labels important elements as design hypotheses, which is healthy: it does not pretend every organism metaphor is already proven.

### 1.4 The organism has a real structural vocabulary

The verified registry contains **170 organs** across 2,733 lines. Records express runtime, type, expected heartbeat, owner module, dependencies, recovery action, severity, and cicatrix references: `apps/organism/organism/organs_registry.yaml`.

The organ-conformance cortex defines ten reusable “genes”: registry membership, heartbeat, HOME-pair discipline, node guards, kill switches, hardened headless spawning, ledger integration, KeepAlive sanity, fail-visible behavior, and singleton enforcement. This is a meaningful step beyond static diagrams because it expresses architectural invariants as inspectable traits. However, **135 plist entries remain grandfathered**, so the gene system is an incremental migration rather than complete conformance: `infra/organ-conformance/genes.json`.

`INDEX.md` provides the human atlas and explicitly treats quantitative state as generated rather than manually frozen. It also names SYMBIOSIS, VADEMECUM, INDEX, CLAUDE, and the scar corpus as the five governing books (`INDEX.md:133`). Its last manual revision is dated 2026-07-02 (`INDEX.md:4`), exposing the maintenance cost of a prose atlas.

`docs/LIVING_ARCHITECTURE.md` is extensive but its verified heading structure is predominantly generated endpoint and service inventory. It is valuable operational documentation, not yet a single C4-like dependency model connecting system, container, organ, runtime, decision, and fitness-test views.

The federation orchestrator implements a classify/checkpoint/dispatch/assemble/review/output graph and maps tasks to specialist surfaces: `scripts/federation_orchestrator.py`. It is an execution substrate, not the authoritative architectural decision ledger.

### 1.5 Decision capture is research-heavy and canon-light

The snapshot inventory returned:

- `docs/adr/`: 1 file
- `docs/decisions/`: 1 file
- `docs/specs/`: 5 files
- `research/operations/`: 618 files
- `research/design/`: 115 files

`docs/ARCHITECTURE_DECISION_RECORDS.md` contains eleven inline ADRs, but it is a single historical document rather than a record-per-decision lifecycle. Its decisions do not consistently expose current owner, review trigger, expiry, supersession relationship, linked organ, or executable fitness function.

The ratio is therefore not “733 bad reports versus two good decisions”; that would be semantically unfair. It is an artifact-routing signal: Nuzantara is exceptionally capable at generating analysis, while canonical decision state is sparse and fragmented.

The fresh case-code dossier is a good specimen of current practice. It grounds claims to live files, selects “journey rather than order” as the governing abstraction, identifies clock and allocation semantics, and subjects the design to two cross-family adversarial seats. It records 20 unique findings, of which 17 were applied and three rejected with reasons: `research/design/2026-08-28-case-code-design.md`. What it still lacks is a machine-readable decision status, expiry, linked organs, alternatives matrix, baseline fitness measurement, and a trigger for later re-evaluation.

The universal conductor design is similarly advanced: typed intermediate representations, capability evidence, signed receipts, immutable hashes, and explicit latency and coverage targets. It also admits that implementation has not caught up with doctrine: `research/operations/2026-08-21-universal-conductor-control-plane-design.md`.

The May architecture synthesis shows a healthier full loop: worktrees, Redis leases, merge-queue discipline, and repository maps progressed from council synthesis into implementation; subsequent W62/W63 failures then refined the design. Its own report had to be recreated after accidental deletion, demonstrating that even high-quality architectural knowledge can lack durable lifecycle protection: `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`.

### 1.6 Reuse-first is explicit

Before non-trivial construction, `reuse-first` requires decomposition into bricks, internal and external search, license review, maturity assessment, and classification as copy, fork, pattern, library, or genuinely new work. It also requires adaptation for local sovereignty, PII boundaries, and prohibited paid paths: `.claude/skills/reuse-first/SKILL.md`.

That is good architectural economics. The missing connection is enforcement: a decision record does not yet have a required provenance field proving which reuse candidates were evaluated and why they were rejected.

## 2. Scars & ledger evidence in this area

### 2.1 Agreement has repeatedly failed as a truth signal

Superscar family #6 is the central architectural scar: anti-hallucination blindness. Its lineage is explicit—W65 “the refuter also hallucinates,” W90 “ground truth ages,” W100 “agreement also lies,” and W113 “the correction itself lies”: `.claude/rules/cicatrix-superscar.md`.

W100 is decisive empirical evidence. A same-family extractor and verifier certified eight items clean; cross-family, independently grounded review overturned **seven of those eight**. The eventual lot was 13/13 problematic. High internal agreement measured shared representation, not truth. The cure was not “more debate rounds,” but a different family re-extracting from different raw material rather than reviewing the original dossier: `.claude/rules/cicatrix-scars.md:760-772`.

W113 records four adversarial rounds in which replacement claims introduced while retracting an error escaped attention. The lane generated 31 objections, 29 confirmed, before the correction itself became reliable. This proves that “reviewed several times” is not a stable architectural property unless each new claim re-enters the evidence boundary: `.claude/rules/cicatrix-scars.md:934-955`.

### 2.2 The learning system lacks native unlearning

The W78 governance scar states that an incorrect or stale scar can be injected into every later agent without expiry, contradiction detection, or formal retraction. Its proposed remedies—`verified_on`, expiration, RETRACT state, and contradiction linting—were recorded as not yet shipped in that scar block: `.claude/rules/cicatrix-scars.md:274-301`.

The same defect applies to architecture decisions. Static ADR status values are insufficient when conclusions are copied into skills, laws, registries, prompts, and gates. Retiring the source document does not retract all derived constraints.

### 2.3 Designed does not mean armed

Superscar #2, “Esiste ≠ Armato,” applies directly to decision machinery. A council specification, validator, or final-gate stub can exist while no runtime path proves it works. The open worker-plane entry records precisely that gap: retired seat topology in the validator and no final-gate receipt validation (`.claude/skills/modus/PENDING-ARMS.md:721`).

The organ genes partly cure this class, but 135 grandfathered exceptions show how architectural controls can remain aspirational for a long tail: `infra/organ-conformance/genes.json`.

### 2.4 The anti-sperpero gate has failed in practice

`AMENDMENTS.md:90` records two sessions whose mandate was to reduce token waste and accelerate coding. They ran for **44 and 31 hours**, opened **180 PRs**, spent **8.6 million output tokens**, and produced roughly **ten business commits**. The amendment’s conclusion is architectural: the meta-work should have been Gear 2 with a stop-loss, not Gear 3 with an open council.

This is the clearest verified case of councils or panel-like meta-process being used where the later anti-sperpero rule says it should not have been. The ledger provides one explicit aggregate incident, not enough evidence to claim a general incidence rate. The system currently records spectacular misfires, not a denominator of all council-eligibility decisions.

A separate open ledger row says the deterministic gear floor had no effective ceiling, so a floor-1 change could still pay for a council, external refuters, an Evidence Pack, and high reasoning effort. Its proposed target is at most 0.2 external-seat calls per floor-1 PR: `.claude/skills/modus/PENDING-ARMS.md:1156`.

### 2.5 The amendment loop itself has gone silent

`AMENDMENTS.md:96` says the file recorded zero entries across 24–26 August, repeating a failure it had already identified. The corrective insight is exact: capture is not learning until a receptor consumes it. This mirrors the architectural decision problem—writing a report is not a state transition.

### 2.6 Panels can promote unsupported numbers

The five-seat product-factory panel later found that a “70% + 15% bugs” claim had been promoted without a source. It also remeasured a docs-only PR rate as 39/100 rather than the brief’s 56/100 and found several proposed rules unmechanized: `research/operations/2026-08-24-product-factory-procedure-5-seat-panel.md`.

The Garuda joint analysis gives the complementary lesson: 202 passing Python tests and an RC0 did not detect cross-language joint defects because the TypeScript consumer was absent from CI. Nine hand-maintained mirrors were identified as the structural disease: `research/operations/2026-08-24-garuda-voa-the-defects-were-in-the-joint.md`.

The architecture lesson is consistent: evidence must cross the same boundary as the real consumer.

### 2.7 Memory evidence was intentionally excluded

The lane brief referenced memory files outside the snapshot. Access to those paths was explicitly prohibited, so no memory bodies were read and no memory-derived decision count is claimed. Repository copies, scars, ledgers, and research artifacts were used instead.

## 3. World SOTA survey

| System or practice | Primary source | Mechanism | Published effect | Transferability |
|---|---|---|---|---|
| Nygard ADRs | [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions), 2011 | Small, immutable records containing context, decision, status, and consequences | No controlled effect; optimizes for records that remain readable and updateable | Directly transferable; Nuzantara should use one typed record per structural decision |
| MADR | [MADR decision](https://adr.github.io/madr/decisions/0000-use-markdown-architectural-decision-records.html), living standard | Adds options, pros/cons, confirmation and structured metadata to lightweight ADRs | No controlled production effect | Better starting schema than a bespoke prose format |
| Google design docs | [Software Engineering at Google, Documentation](https://abseil.io/resources/swe-book/html/ch10.html), 2020 | Goals, trade-offs, alternatives and specialist review before implementation; review again before launch | Google publishes practice, not a causal effect size | Strong transfer, but specialist human review must become deterministic checks plus targeted seats for a solo owner |
| Rust RFCs | [Rust RFC Book](https://rust-lang.github.io/rfcs/), living process | Controlled path for substantial change, open rationale, stakeholder discussion and explicit disposition | No controlled effect | Useful for public, cross-cutting decisions; excessive for reversible local choices |
| Amazon one-/two-way doors | [2015 shareholder letter](https://ir.aboutamazon.com/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF), 2015 | Process weight follows reversibility: irreversible decisions escalate, reversible ones decentralize | No controlled effect | Maps naturally to Gear and council economics |
| C4 | [Official C4 model](https://c4model.com/), living | Hierarchical system, container, component and code abstractions | No controlled effect | Use system/container/organ/runtime views; do not replace the live organ registry |
| Structurizr | [Why architecture “as code”](https://docs.structurizr.com/as-code), living | One versioned model generates several views and supports drift checks | No controlled effect | Highly transferable because agents can consume and diff plain-text models locally |
| arc42 | [arc42 overview](https://arc42.org/overview/), current; method since 2005 | Goals, constraints, context, strategy, runtime, deployment, decisions, quality scenarios and risks | Broad adoption claimed; no causal effect | Use as a completeness map, not another 12-section mandatory ceremony |
| Evolutionary architecture | [Fitness function-driven development](https://www.thoughtworks.com/en-us/insights/articles/fitness-function-driven-development), 2019 | Converts architectural qualities into tests and continuous feedback | No controlled organization-wide effect published | Essential bridge from SYMBIOSIS laws and decisions into CI/runtime evidence |
| AWS Well-Architected | [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html), living | Periodic review questions across six quality pillars | No causal effect in the framework | Transfer the review structure; reject AWS-specific service prescriptions where local sovereignty governs |
| TLA+ at AWS | [How AWS uses formal methods](https://www.amazon.science/publications/how-amazon-web-services-uses-formal-methods), 2015 | Lightweight specification and model checking before implementing critical distributed designs | Seven teams reported use and subtle design bugs found; no controlled comparison | Use selectively for leases, outboxes, merge state, singleton ownership and recovery protocols |
| Multi-agent debate | [Du et al.](https://arxiv.org/abs/2305.14325), 2023 | Multiple model instances propose, inspect and revise reasoning over several rounds | Reported factuality and reasoning gains on studied tasks | Useful evidence that challenge can help; same-model debate does not solve shared blind spots |
| Expert debate with weak judges | [Khan et al.](https://arxiv.org/abs/2402.06782), 2024 | Opposing expert debaters expose evidence for a weaker model or human judge | Model judges: 76% vs 48%; human judges: 88% vs 60% | Supports asymmetric proponent/refuter roles, but requires preserved evidence and an adjudicator |
| Anthropic multi-agent research | [Engineering report](https://www.anthropic.com/engineering/multi-agent-research-system), 2025 | Lead agent delegates independent search paths to parallel workers with explicit breadth control | 90.2% better than single Opus 4 on an internal research evaluation; roughly 15× chat tokens; up to 90% time reduction on complex research | Confirms Nuzantara’s anti-sperpero gate: parallelism helps broad tasks but is economically wrong by default |
| MAST | [Cemri et al.](https://arxiv.org/abs/2503.13657), 2025 | Taxonomy of 14 failure modes across system design, inter-agent misalignment, and verification/termination | Empirical trace taxonomy, not an intervention effect | Directly supports receipts, explicit roles, termination tests and decision-level failure classification |

### The five most important transfers

**ADRs plus fitness functions:** ADRs preserve why; fitness functions preserve whether the reason remains true. Neither alone is sufficient. Nuzantara already has richer raw material than most organizations—laws, organs, genes and scars—but lacks the binding record between them.

**Architecture as code:** C4/Structurizr supplies a model/view distinction that the current atlas lacks. The right adoption is not hand-drawing the entire monorepo. It is generating a small, queryable model from authoritative registries and decisions.

**Reversibility-weighted governance:** Amazon’s door model explains what the current council gate is trying to achieve. The unresolved contradiction is that `CLAUDE.md` still applies heavyweight pre-approval categorically.

**Formal methods as a scalpel:** AWS did not apply TLA+ to every service choice. Nuzantara should use it only where concurrency, state transition, recovery, or ownership produces counterexamples ordinary prose cannot expose.

**Debate economics and failure evidence:** Anthropic demonstrates the performance ceiling and the approximately 15× token cost; MAST explains structural failures; Khan shows that opposed arguments can assist a weaker judge. Nuzantara’s W100 adds the missing operational qualification: family diversity is insufficient unless the seats also inspect independent evidence.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence and judgment |
|---|---|---|
| Decision framing and grounding | **AHEAD** | The eight-stage architecture loop combines external grounding, explicit no-go/defer outcomes, falsifiable metrics and empirical closure: `.claude/skills/sota-architecture-loop/SKILL.md`. It is more rigorous than a basic ADR or design-doc template. |
| Reversibility/cost-based process | **AT, doctrinally; BEHIND, operationally** | The conditional council gate resembles Amazon’s door logic, but `CLAUDE.md:174` still makes panels categorical and `AMENDMENTS.md:90` records an extreme meta-work overspend. |
| Council composition | **AHEAD conceptually** | Heterogeneous asymmetric seats, no consensus objective, blind re-grounding and sequential adjudication go beyond ordinary same-model debate. W100 proves why. |
| Council calibration | **BEHIND** | There is no verified denominator of eligible decisions, council invocations, confirmed unique findings, or escaped defects. The strongest evidence is incident-based. |
| Canonical decision recording | **BEHIND** | Eleven inline ADRs and two sparse decision directories coexist with 733 research artifacts. Records lack uniform expiry, owner, supersession, organ links and confirmation functions. |
| Architecture as code | **BEHIND** | Registries are machine-readable, but the verified architecture document is primarily endpoint inventory and the atlas is manual. There is no observed unified model generating stakeholder-specific views. |
| Executable constraints | **AHEAD in concept; AT in coverage** | Ten organ genes turn architecture into checks, which is strong. The 135 grandfathered entries prevent an “ahead” verdict on coverage: `infra/organ-conformance/genes.json`. |
| Evolution and revisitation | **BEHIND** | W78 identifies no native expiry/retraction mechanism. Current research and scars can remain authoritative after their evidence ages. |
| Reuse-first economics | **AT** | Internal/external search, license gates and adaptation rules are explicit: `.claude/skills/reuse-first/SKILL.md`. Decision artifacts do not yet prove the search occurred. |
| Research OS | **AHEAD in production, BEHIND in promotion** | Research volume, adversarial specimens and correction histories are exceptional. Promotion from report → decision → gene/test → retirement is not one typed state machine. |
| Lightweight formal methods | **BEHIND the surveyed frontier** | The verified architecture corpus contains sophisticated state-machine prose, but no verified formal model or model-checking receipt. This is a corpus-bounded finding, not a claim that none exists anywhere in the repository. |
| Solo-owner suitability | **AHEAD in intent, AT in practice** | The design correctly protects Zero’s business authority while delegating technical reasoning. Conflicting doctrine and document volume still make the owner’s effective choice harder to see. |

## 5. Beyond-SOTA recommendations

All recommendations preserve CLI-only subscription access, the PII-output boundary, local sovereignty, the prohibition on automatic Fable routing, and Zero’s authority over structural or business rulings. Scores use `(impact 1–5 × confidence) / cost 1–5`.

### 1. Architecture Decision Genome — score 2.25

**What:** Create one typed record per structural decision with: stable ID; state; owner; door type; governing laws; alternatives; rejected reasons; affected organs; scar risks; evidence hashes; baseline; target; fitness functions; council receipt; expiry/revisit triggers; supersedes/superseded-by; implementation and live-proof links.

**Why beyond SOTA:** ADRs, C4, fitness functions, formal specifications and organ registries exist separately in the survey. None of the surveyed systems combines them with a longitudinal scar corpus and an agent-consumable decision graph.

**Cost:** 16–24 engineering hours; deterministic tooling; optional flat-subscription review only. **Gear:** 3 for schema adoption, then Gear 1 for linting.

**Risk:** schema bureaucracy or write-only metadata—superscars #2 and #9. A model-filled record could manufacture evidence—#6.

**Metric:** Baseline is the current scattered inventory. By day 90, 100% of new Gear-3 structural changes must reference a decision ID; at least 80% must link a runnable fitness function; retrieval of “why does organ X work this way?” should succeed in under one minute on a 20-question corpus.

**Kill criterion:** Stop mandatory rollout if, after ten real decisions, median authoring overhead exceeds 30 minutes or fewer than half of fields are consumed by a gate, renderer, or receptor.

**First PR:** `feat(architecture): add shadow decision-record schema and linter`; new `infra/architecture-decisions/schema.json`, new `scripts/lint_architecture_decisions.py`, new focused tests; ≤350 net lines; warning-only.

### 2. Evidence-Calibrated Council Gate — score 1.91

**What:** Every architectural choice logs a cheap eligibility receipt: expected loss, reversibility, independent breadth, chosen seats, evidence independence, token/time use, unique findings, confirmed findings, and final disposition. Shadow-sample some rejected councils with a second seat to estimate false negatives.

**Why beyond SOTA:** Anthropic measures aggregate multi-agent benefit and cost; debate papers measure task accuracy. Nuzantara can calibrate heterogeneous council economics against its own scar outcomes and flat-subscription fleet—an asymmetry the surveyed systems do not possess.

**Cost:** 12–20 hours plus 30 real decisions of observation; subscription tokens only. **Gear:** 2 for instrumentation, 3 for changing the threshold.

**Risk:** optimizing for finding count encourages verbose false positives (#6); dead seats make the receipt falsely complete (#2); shared evidence reproduces W100.

**Metric:** Confirmed, unique severity-weighted findings per 100,000 output tokens; council reversal rate; false-negative rate from the 20% shadow sample; time-to-decision. Target: double confirmed finding yield relative to the documented meta-work baseline, council use below 30% of structural decisions, and no increase in escaped P1 architectural defects.

**Kill criterion:** If 30 decisions show no statistically useful separation between gate-approved and gate-rejected cases, retain the simple three-condition gate and delete the calibration layer.

**First PR:** `feat(modus): emit shadow council-eligibility receipts`; new schema and deterministic recorder only, no routing change; ≤300 lines.

### 3. Decision Receptor and Unlearning Protocol — score 1.53

**What:** Treat decisions as event-driven state. Changes to a linked organ, law, dependency contract, baseline metric, or scar family open a `REVIEW_DUE` transition. Retractions propagate to derived rules; expired decisions lose “current” status until revalidated.

**Why beyond SOTA:** ADR status and periodic review are known. The novel composition is automatic re-entry driven by organ and scar events, with provenance through every derived constraint.

**Cost:** 20–30 hours over two PRs. **Gear:** 3.

**Risk:** noisy invalidations (#3 guard over-match), dead receptors (#2), or incorrect supersession edges (#9).

**Metric:** Baseline: no uniform expiry/retraction. Target: 100% of migrated decisions have a revisit trigger; median trigger-to-disposition under 48 hours; zero active decisions past expiry; mutation tests prove a changed linked organ opens review and an unrelated organ does not.

**Kill criterion:** If over 25% of alerts are false positives across 30 triggers, disable automatic opening and retain a daily digest until trigger precision reaches 90%.

**First PR:** `feat(architecture): add expiry and supersession states`; schema plus deterministic state-transition tests, ≤300 lines; no daemon yet.

### 4. Organ-to-Decision Impact Compiler — score 1.00

**What:** Compile the organ registry, decision graph and dependency relations into affected-consumer and required-gate manifests. Produce C4-like views from the model; do not maintain another hand-written atlas.

**Why beyond SOTA:** Structurizr generates views from a model, while Nuzantara’s registry carries runtime recovery, severity and scar genes. Joining those with decision and evidence edges produces a risk-aware living architecture unavailable in the surveyed systems.

**Cost:** 30–45 hours in incremental slices. **Gear:** 3.

**Risk:** generated state becomes stale or uses a proxy for truth (#9); per-machine copies drift (#1); broad dependency matching overfires (#3).

**Metric:** On 20 historical structural changes, affected-organ recall and precision must each reach at least 0.85. By day 90, 90% of high-severity organs should link to at least one active decision and one proof.

**Kill criterion:** If a curated 20-change corpus cannot reach 0.75 precision and recall without manual exceptions, stop CI enforcement and keep the compiler as an exploratory view.

**First PR:** `feat(organism): validate optional decision references`; extend the existing registry contract with optional `decision_refs` and seed only three high-severity examples; ≤250 lines.

### 5. Counterexample Escrow for Critical State Machines — score 0.82

**What:** For leases, outboxes, singleton ownership, merge states and recovery protocols, store a small formal model, any discovered counterexample trace, the resulting decision amendment, and the executable regression fitness function as one evidence chain.

**Why beyond SOTA:** AWS demonstrates formal modeling; evolutionary architecture demonstrates fitness functions. The extra step is preserving model-checker counterexamples as durable scars that automatically constrain later implementations and re-open the governing decision when assumptions change.

**Cost:** 24–40 hours for the first model, then 4–8 hours per eligible design; no external API. **Gear:** 3, only for one-way-door concurrency decisions.

**Risk:** formal-method theater without an implementation link (#2), model and code sharing a false assumption (#6/#114 lineage), state schema drift (#9).

**Metric:** Model at least three critical protocols in 90 days; every counterexample must bind to a regression test. Measure states explored, counterexamples found before implementation, and post-implementation invariant escapes.

**Kill criterion:** If five eligible designs produce neither a counterexample nor a changed implementation decision, suspend the practice and retain prose plus property-based tests.

**First PR:** `docs(architecture): add one executable lease model experiment`; one model, one README, one invocation test, ≤400 lines. It remains experimental until it changes or validates a live decision.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 0–30: establish canonical decision truth

1. Obtain the rulings in section 7.
2. Land the shadow Decision Genome schema and linter.
3. Inventory the eleven inline ADRs and select five still-load-bearing decisions for migration.
4. Record baselines: decision authoring time, council invocations, token/time consumption, confirmed findings, linked organs, and available fitness functions.
5. Reconcile only the directly contradictory council prose; do not rewrite the broader doctrine.

| First PR | Files | Limit / gear | Acceptance test |
|---|---|---|---|
| `feat(architecture): add shadow decision-record schema and linter` | New `infra/architecture-decisions/schema.json`; new linter and focused tests | ≤350 lines; Gear 2 | Valid fixture passes; missing state, metric or supersession target fails; existing repository remains warning-only |
| `docs(architecture): migrate five active decisions` | New records under `infra/architecture-decisions/records/`; pointers from `docs/ARCHITECTURE_DECISION_RECORDS.md` | ≤400 lines; Gear 2 | Each record resolves its evidence and affected paths; no substantive ruling is silently changed |
| `docs(modus): reconcile council eligibility doctrine` | `.claude/skills/modus/SKILL.md`, `.claude/skills/sota-architecture-loop/SKILL.md`, `CLAUDE.md`, `SYMBIOSIS.md` | ≤200 lines; Gear 3; needs ruling | A deterministic text test finds one canonical eligibility rule and one final-gate effort default |

### Wave 2 — Days 31–60: connect decisions to work

1. Emit shadow council-eligibility and outcome receipts.
2. Add optional `decision_refs` to three high-severity organs.
3. Add expiry, supersession, and `REVIEW_DUE` state transitions.
4. Build a 20-change impact corpus from historical architecture changes.
5. Run one formal-model experiment on a stateful protocol.

| First PR | Files | Limit / gear | Acceptance test |
|---|---|---|---|
| `feat(modus): emit council outcome receipts` | New receipt schema/recorder; targeted tests | ≤300 lines; Gear 2 | Same input produces byte-stable receipt; unavailable seat is declared, never counted as participation |
| `feat(organism): validate decision references` | `apps/organism/organism/organs_registry.yaml`, `infra/organ-conformance/genes.json`, focused validator tests | ≤300 lines; Gear 3 | Broken decision ID fails; valid ID resolves; unrelated organs remain unaffected |
| `feat(architecture): add decision review transitions` | Decision schema, transition module, tests | ≤350 lines; Gear 3 | Expiry and superseded evidence open review; unrelated changes are an innocence control |

### Wave 3 — Days 61–90: enforce only proven value

1. Evaluate 30 council decisions and set thresholds from observed yield.
2. Turn the decision linter from warning to blocking only for declared hot zones.
3. Generate system/container/organ/risk views from the model.
4. Publish a compact owner dashboard: active one-way doors, pending rulings, review-due decisions, broken fitness functions and recent reversals.
5. Retire fields or gates that have no consumer.

| First PR | Files | Limit / gear | Acceptance test |
|---|---|---|---|
| `feat(architecture): compile organ impact manifest` | New compiler and 20-case corpus | ≤400 lines; Gear 3 | Precision and recall each ≥0.85 on the pinned corpus |
| `ci(architecture): require active decision on hot-zone structural changes` | Existing gate configuration plus focused test fixtures | ≤250 lines; Gear 3 | Guilt case without decision fails; ordinary reversible change passes |
| `feat(architecture): render owner decision digest` | New deterministic renderer over decision records | ≤300 lines; Gear 2 | No PII; shows active/review-due/ruling-required states; snapshot is reproducible |

Day-90 success is not “all PRs merged.” It is: at least ten live decisions in the graph, eight with executable fitness functions, three linked formal/behavioral counterexamples, 90% impact precision/recall on the corpus, and measured council yield better than the pre-roadmap baseline.

## 7. Needs-ruling

1. **Council authority:** choose one canonical rule: conditional three-part economic gate, or mandatory panel for every architecture specification. Recommendation: conditional gate, with mandatory sequential final review only for declared one-way-door decisions.

2. **Canonical decision authority:** approve `infra/architecture-decisions/records/` as the machine-readable authority, with research documents retained as evidence rather than competing current truth. This changes repository governance and therefore requires Zero.

3. **Automated retirement boundary:** decide whether expiry may automatically mark a decision `REVIEW_DUE` while only Zero can mark structural decisions `SUPERSEDED`. Recommendation: automatic review opening, never automatic business or structural replacement.

No credential, GUI, physical-machine, publication, or client-data ruling is required for the proposed shadow instrumentation.

## 8. §Meta-pattern

The single defective belief is:

> **If enough intelligent text surrounds a choice, the architecture has been decided.**

It generates the research/decision imbalance, mandatory councils, correction chains, stale laws, manual atlases, and controls that exist without being armed. Nuzantara’s own strongest artifacts already refute it: W100 shows agreement is not truth; W113 shows review count is not closure; the organ genes show prose is not conformance; `AMENDMENTS.md` shows capture is not learning.

The replacement belief should be:

> **A structural decision is a typed, reversible-or-escalated state transition whose rationale, affected anatomy, empirical fitness and revisitation trigger remain connected for its entire lifetime.**

That shift preserves Nuzantara’s exceptional deliberative intelligence while making it cheaper, falsifiable, locally sovereign and capable of unlearning.

## 9. Sources

1. [Michael Nygard, “Documenting Architecture Decisions”](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) — 2011-11-15; accessed 2026-08-29. Original primary description of lightweight ADRs.
2. [MADR, “Use Markdown Architectural Decision Records”](https://adr.github.io/madr/decisions/0000-use-markdown-architectural-decision-records.html) — living MADR 4 documentation; accessed 2026-08-29. Maintainers’ canonical structured ADR decision.
3. [Software Engineering at Google, “Documentation”](https://abseil.io/resources/swe-book/html/ch10.html) — 2020; accessed 2026-08-29. Google’s primary account of design-document practice.
4. [The Rust RFC Book](https://rust-lang.github.io/rfcs/) — living process; accessed 2026-08-29. Canonical controlled-change process for Rust.
5. [Amazon 2015 Letter to Shareholders](https://ir.aboutamazon.com/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF) — 2015; accessed 2026-08-29. Primary source for one-way and two-way door decisions.
6. [The C4 Model](https://c4model.com/) — living official documentation; accessed 2026-08-29. Creator-maintained hierarchical architecture model.
7. [Structurizr, “Why as code?”](https://docs.structurizr.com/as-code) — living official documentation; accessed 2026-08-29. Primary explanation of model-as-code and generated views.
8. [arc42 Overview](https://arc42.org/overview/) — current template, method in use since 2005; accessed 2026-08-29. Official architecture-documentation and quality-goal framework.
9. [Thoughtworks, “Fitness function-driven development”](https://www.thoughtworks.com/en-us/insights/articles/fitness-function-driven-development) — 2019-01-11; accessed 2026-08-29. Primary practitioner account of executable architectural qualities.
10. [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html) — living official framework; accessed 2026-08-29. Canonical AWS architecture-review mechanism.
11. [Newcombe et al., “How Amazon Web Services Uses Formal Methods”](https://www.amazon.science/publications/how-amazon-web-services-uses-formal-methods) — 2015; accessed 2026-08-29. Primary industrial report on TLA+ at AWS.
12. [Du et al., “Improving Factuality and Reasoning in Language Models through Multiagent Debate”](https://arxiv.org/abs/2305.14325) — 2023-05-23; accessed 2026-08-29. Original multi-agent debate study.
13. [Khan et al., “Debating with More Persuasive LLMs Leads to More Truthful Answers”](https://arxiv.org/abs/2402.06782) — 2024-02-09; accessed 2026-08-29. Primary weak-judge/expert-debate experiment.
14. [Anthropic, “How we built our multi-agent research system”](https://www.anthropic.com/engineering/multi-agent-research-system) — 2025-06-13; accessed 2026-08-29. Primary production report with quality, latency and token measurements.
15. [Cemri et al., “Why Do Multi-Agent LLM Systems Fail?”](https://arxiv.org/abs/2503.13657) — 2025-03-17; accessed 2026-08-29. Primary empirical MAST failure taxonomy.