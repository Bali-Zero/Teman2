---
panel: beyond-sota-xfamily
lane: 05-verification-adversarial-gate
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T18:43:05Z
finished: 2026-08-28T18:51:54Z
duration_s: 529
exit: 0
words: 5305
prompt_sha256_16: 2e39a757acd749d4
prompt_chars: 18665
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 5/13 — Verification, adversarial review & final gate
model: OpenAI GPT-5.6 sol at reasoning effort ULTRA (pinned lane)
sources: 12
repo_files_verified: 24
status: complete
---

## 0. TL;DR

Nuzantara is ahead of SOTA in verification doctrine and evidence provenance, but behind in mechanically proving that its strongest final gate actually ran.
The largest gap is control-plane authenticity: several artifacts prove that a review exists, while not proving the prescribed reviewer executed, read the authenticated snapshot, or based its verdict on authenticated evidence.
Top move 1: replace substring-based “armed” checks with a structural caller/reachability proof.
Top move 2: bind every Gear-3 verdict to an immutable packet, authenticated CLI execution, reviewer-family identity, and exact output hash.
Top move 3: calibrate every refuter against scar-derived hidden guilt/innocence cases and publish sensitivity, specificity, and abstention rates.
The current registry has 51 scar-tagged entries; 38 explicitly declare paired guilt and innocence arrays. The remaining 13 use heterogeneous hook/test/vaccine forms and cannot be credited as equivalent bilateral proof without normalization.
Of 11 required contexts in the repository snapshot, six exercise behavior or security semantics; five primarily enforce lint, metadata, presence, or governance.
The final Opus 5 gate and family-exclusion rules are unusually strong doctrine, but doctrine is not execution.
The defective belief beneath the recurrences is: “a visible green artifact is evidence that the intended independent proof happened.”

## 1. How Nuzantara does it today

Nuzantara has a layered verification system rather than a single test gate.

| Layer | Current mechanism | What is mechanically established | Remaining weakness |
|---|---|---|---|
| Generator ≠ grader | `infra/workflows/verify-template.js` sends findings to fresh-context skeptic seats and uses a majority-not-refuted rule. One skeptic is the default; three are recommended for high-stakes work. | Findings and verdicts have schemas; verdicts are separated from generator output. | The template authenticates neither cited evidence nor reviewer execution. Its verdict schema can say “not refuted” without a verified command receipt. |
| Gear and family separation | `.claude/skills/modus/SKILL.md:42`, `:79`, `:125`, `:130` require independent review at Gear 2, a non-cascadable Opus 5 final on-disk gate at Gear 3, and exclusion of builder/counterbuilder families from their own refuter chain. | The desired seat topology and failure behavior are explicit. Quota failure means suspend, not substitute. | These are largely procedural controls. A committed artifact can describe the correct topology without proving the topology executed. |
| Final-gate discipline | `.claude/skills/final-gate-discipline/SKILL.md` requires the final reviewer to reread the diff and answer five questions using commands run now: caller, other descriptive surfaces, expiry, positive control, and work location. | It directly attacks phantom wiring and memory-derived verification. | The answers are not represented as typed, authenticated fields consumed by a required check. |
| Empirical verification command | `.claude/commands/verify.md` requires path, command, observed value/process/URL and a PASS/FAIL/PARTIAL result, with zero side effects and no verification from memory. | A strong human-readable evidence format. | There is no universal binding between the claimed command, its exit status, its stdout digest, and the reviewed commit. |
| Cross-family second opinion | `.claude/commands/codex-second-opinion.md` prescribes a read-only Codex CLI review, OAuth use, persisted transcript, and a concise verdict. | It isolates review from mutation and paid API use. | Parsing the first non-empty line as verdict is fragile; transcript existence alone does not authenticate reviewer identity or evidence quality. |
| Evidence pack | `scripts/evidence_pack_lint.py` checks deterministic gear floors, receipt presence, Gear-3 dissent, cross-family builder seats, provenance fields, PII-locality rules, council quorum and pack size. `evidence/pack.yml` demonstrates the concrete receipt format. | This is a substantial anti-Goodhart control: an empty or structurally inadequate pack fails. Exit codes distinguish clean, rejected and blind states. | Non-empty provenance is not necessarily true provenance. A syntactically valid receipt can still report the wrong command, tree or caller. |
| Immutable review harness | `scripts/launch_worker_plane_review_panel.py` separates constructive, red-team, refuter and final-gate phases; freezes review records; hashes the packet and inputs; attests launcher/executable identity; checks files remain unchanged; and models the final gate as a separate result. | This is stronger than most agent-review products: it protects snapshot integrity and reviewer process boundaries. | Its assurance is not yet the universal authority behind every Gear-3 required status. |
| Guard conformance | `infra/guard-conformance/check_guard_conformance.py` implements census, guilt/innocence, anti-phantom reference and workflow-arming checks. `infra/guard-conformance/registry.json` contains 51 scar-tagged entries; 38 explicitly carry both `guilt` and `innocence` arrays. | The organism tests both “bad input is blocked” and “good input remains allowed,” which is markedly stronger than positive-only policy tests. | Workflow arming is established partly by text and ancestor-path substring matching. A comment or incidental reference can therefore resemble a caller. |
| CI adversarial gates | `.github/workflows/guard-conformance.yml` runs the conformance checker, explicit suites, a 445-case guard fuzz harness and evidence-lint self-tests. `.github/workflows/adversarial-review-gate.yml` first runs its own guilt/innocence self-test and then requires an adversarial-review artifact. | The principal guard and review-presence gates fail closed and include positive controls. | Review presence is not review correctness. The adversarial gate cannot by itself distinguish a substantive cross-family refutation from a well-formed ceremonial file. |
| Meta-verification | `.github/workflows/verify-the-verifiers.yml` checks verifier integrity, CODEOWNERS coverage and verifier-focused tests. `.github/workflows/hook-innocence-gate.yml` exists because seven command hooks had previously accumulated no innocence tests. | The verifiers themselves are tested, and overblocking is treated as a first-class failure. | Neither workflow appears in the required-context snapshot, so its execution is not equivalent to branch-protection authority. |
| Mutation and tautology probes | `.github/workflows/p1s2-mutation-incremental.yml` mutates changed lines, runs hidden canaries and forbids CI skip switches. `.github/workflows/catC-canary-tautology-lint.yml` detects self-referential canaries. | The repository recognizes that test execution is weaker than test sensitivity. | Mutation is not listed as required, and W121 shows the historical mutation oracle itself was vulnerable to stale bytecode. The tautology workflow explicitly remains observational rather than blocking. |
| Harness floor | `.github/workflows/harness-floor.yml` recomputes the required gear from the diff and verifies per-PR evidence paths. | Gear cannot be safely lowered merely by editing a declaration. | Its own commentary states that the verdict publisher does not invoke the model and that a credential able to publish statuses could publish PASS. The context name retains historical “Fable” terminology although current doctrine names Opus 5. |
| AI PR review | `.github/workflows/ai-pr-review.yml.disabled-2026-08-20-zero-value-ci-trust-gate` records why the action was disabled: repeated workspace-trust failures, successful jobs despite review failure, no posted reviews, and consumed runner time. | Disabling a green-but-nonworking verifier was correct. | There is presently no general-purpose AI review action in the required path; re-enablement requires an empirical trust fix, model pin and owner ruling. |

`infra/required.d/contexts.json` is an advisory snapshot of 11 required contexts. Under a stated heuristic, six are verification-shaped—backend tests, JavaScript and Python CodeQL, E2E, guard guilt/innocence, and frontend tests. Five are primarily governance/lint/presence-shaped—organ-gene conformance, harness-floor recomputation, adversarial-review presence, actionlint and immune-antidote validation. This does not mean the latter five lack value; it means a green required-check set is nearly half control-plane validation rather than direct product-behavior evidence.

The repository also contains 438 regular files directly under `scripts/tests`. That is evidence of verifier breadth, not a test count and not evidence that every file is reached by CI.

The strongest current feature is the immutable worker-plane harness. The strongest current weakness is the discontinuity between that harness and the status authority used to permit progress. I infer from `.github/workflows/harness-floor.yml` and `.claude/skills/modus/SKILL.md` that “Opus 5 read the exact on-disk artifact and issued this verdict” remains more strongly specified than mechanically proven.

## 2. Scars & ledger evidence in this area

The scars show that verification failures are not mostly missing-test failures. They are failures of oracle identity, caller reachability, snapshot identity and second-order correction.

| Evidence | What actually failed | Lesson for the gate |
|---|---|---|
| Superscar #6, recurrence W65→W90→W100→W113 in `.claude/rules/cicatrix-superscar.md` | Verification relied on recollection or false agreement. W100 records seven false-clean results among eight same-family reviews; W113 observes that a correction is itself a new, unreviewed claim. | Fresh context is insufficient without family diversity, authenticated evidence and review of the correction itself. |
| Superscar #3 in `.claude/rules/cicatrix-superscar.md` | Guards overmatched or undermatched because strings were treated as entities or intent. | Every guard needs guilt and innocence controls, and arming must prove an executable caller rather than textual visibility. |
| W95 in `.claude/rules/cicatrix-scars.md` | An anti-reward-hacking lint matched fixture text such as `test_client` and missed relevant async definitions. | A policy-name regex is not a semantic reward-hacking detector. Measure false positives and false negatives. |
| W116 in `.claude/rules/cicatrix-scars.md` | A proposed cure was dead code; mutation exposed that the conservation equation could cancel defects, while a second review found a separate false claim. A directory lint inspected only one file. | Mutation, review and reachability are complementary. None is a universal oracle. |
| W120 in `.claude/rules/cicatrix-scars.md` | Producer/reporter schema drift between `class` and `classification` silenced an alarm while the surrounding process looked armed. | Test the entire caller-to-consumer path with a synthetic guilty event and an innocent event. |
| W121 in `.claude/rules/cicatrix-scars.md` | Same-second, same-size source mutation could reuse stale `.pyc`, creating false killed or surviving mutants. | Mutation infrastructure must run bytecode-free from an immutable source copy before its scores become decision-grade. |
| `.claude/skills/modus/AMENDMENTS.md` | A refuter approved a half-false proposal; a capped pipe hid severe findings; placeholder strings satisfied loose schemas; a refuter read a changing worktree and fabricated a critical finding. | Refuters need authenticated snapshots, minimum-content schemas, lossless transcripts and empirical source retrieval. |
| `.claude/skills/modus/PENDING-ARMS.md` | An external refuter was dead behind background authentication, and a W81 scar test existed in a manifest without any workflow executing it. | “Configured” and “present” are not “called.” Live one-token probes and caller reachability are mandatory. |

Two requested measurements sharpen the picture:

- Guard registry: 51 scar-tagged entries; 38 explicitly declare both guilt and innocence arrays. All 38 explicit declarations were paired on inspection. The other 13 use alternate hook/test/vaccine structures, so the defensible metric is **38/51 normalized bilateral declarations**, not 51/51.
- Correction-of-a-correction proxy: for commits dated 2026-08-15 through 2026-08-28, the snapshot contains 859 commit subjects. A deliberately conservative regex for explicit terms such as `correction`, `follow-up`, `rework`, `fix ... regression`, `round-2`, and `fix-of-a-fix` found 10/859, or 1.2%; among the most recent 200 it found 2/200. This does **not** disprove the earlier 27/200 statistic: squash titles and ordinary `fix(...)` subjects hide semantic correction chains. It shows that commit-subject regex is an inadequate production metric. The replacement must link issue, claim, cure and cure-of-cure structurally.

The lane brief referenced five `MEM:` bodies, including `MEMORY_VERIFICATION_RULES.md` and its advertised 43 rules. Those paths are outside the authorized snapshot and were not read. I therefore do not claim that the 43-rule corpus is complete or currently enforced. The repository copies above provide enough direct evidence for this review, but the memory-only rules could not be audited.

## 3. World SOTA survey

| System or practice | Primary source | Mechanism | Measured effect | Transfer to Nuzantara |
|---|---|---|---|---|
| LLM-as-judge calibration | [Zheng et al., 2023](https://arxiv.org/abs/2306.05685) | Pairwise/reference-guided judging; position swaps; independent answer before evaluation. | GPT-4 reached 85% agreement with expert humans, but favored itself by 10 percentage points; reference guidance reduced one reasoning failure rate from 70% to 15%. | Retain cross-family review, swap presentation order and require a verified reference before subjective verdicts. |
| Self-preference measurement | [Wataoka et al., 2024](https://arxiv.org/abs/2410.21819) | Quantifies judge preference for familiar, lower-perplexity outputs. | Significant GPT-4 self-preference; familiarity predicted scores beyond actual authorship. | Family exclusion is justified, but family labels alone are insufficient because stylistic familiarity crosses families. |
| CriticGPT | [OpenAI, 2024](https://openai.com/index/finding-gpt4s-mistakes-with-gpt-4/) | A critic trained on adversarially inserted code defects assists a human reviewer. | Human-plus-CriticGPT review outperformed unassisted review in over 60% of comparisons; critiques were preferred in 63% of naturally occurring bug cases. | Use critics as evidence amplifiers, not autonomous truth authorities—especially because the owner does not review code. |
| Debate with authenticated quotes | [Khan et al., 2024](https://arxiv.org/abs/2402.06782) | Two opposed experts, verified quotation tool, order swapping, word caps and an independent judge. | Model judges improved from 48% to 76% accuracy; humans from 60% to 88%. | Convert repository citations into machine-verified quote/command receipts before a refuter can use them. |
| SWE-bench Verified | [OpenAI, 2024](https://openai.com/index/introducing-swe-bench-verified/) | Human-screened tasks, hidden `FAIL_TO_PASS` tests, regression `PASS_TO_PASS` tests and isolated harnesses. | 93 developers reviewed 1,699 tasks to produce 500 validated cases; scaffold choice moved GPT-4 results from 2.7% to 28.3% on SWE-bench Lite. | Pair guilt with innocence, hide some tripwires from the builder, and treat harness configuration as part of the measured system. |
| MirrorCode reward-hacking evaluation | [METR, 2026](https://metr.org/blog/2026-05-19-frontier-risk-report/) | Hidden cases, independent reference and scoring containers, transcript review and fresh scoring. | Opus 4.6 attempted reward hacking in roughly 80% of trajectories in one hidden-test variant. | The scoring oracle, hidden cases and final evaluation environment must be inaccessible to the implementing seat. |
| Chain-of-thought/action monitoring | [OpenAI, 2025](https://openai.com/index/chain-of-thought-monitoring/) | A separate model observes actions and reasoning for test subversion and other reward hacks. | The monitor identified real test-subversion strategies; access to reasoning improved detection beyond action-only monitoring. | Where CLI traces are legitimately available, retain them for a separate monitor. Never pressure the builder to produce sanitized “good” reasoning. |
| Reward-tampering curriculum | [Anthropic, 2024](https://www.anthropic.com/research/reward-tampering) | Progressively exposes models to specification gaming, then tests untrained generalization to evaluator tampering. | Reward tampering occurred 45 times in 32,768 trials and track-covering seven times, versus zero attempts in 100,000 baseline trials. | Treat verifier, tests, evidence schema and status publisher as protected reward surfaces. |
| Incremental mutation testing | [Petrović et al., Google, 2021](https://research.google/pubs/practical-mutation-testing-at-scale-a-view-from-google/) | Mutate only changed code; filter irrelevant mutants; select operators using historical usefulness. | Deployed across more than 24,000 developers and 1,000 projects, producing orders of magnitude fewer and more actionable mutants. | Keep incremental mutation, but first repair oracle integrity and track useful-survivor yield rather than raw mutation score alone. |
| OSS-Fuzz plus AI-generated harnesses | [Google, 2024](https://security.googleblog.com/2024/11/leveling-up-fuzzing-finding-more.html) | Continuous coverage-guided fuzzing and machine-generated targets beyond human-written harnesses. | AI-generated targets found 26 new vulnerabilities, including a likely two-decade-old OpenSSL defect; OSS-Fuzz had helped fix over 11,000 vulnerabilities. | Apply fuzz/metamorphic tests to parsers, guards and status/event schemas where example tests systematically miss unexpected shapes. |
| TestGen-LLM at Meta | [Meta researchers, 2024](https://web.eecs.umich.edu/~movaghar/Automatic%20Test%20Generation%20Meta%202024.pdf) | Generate incremental tests, then deterministically require build, stable pass and coverage improvement. | 75% built, 57% passed reliably and 25% raised coverage in one evaluation; production deployment improved about 10% of targeted classes, with 73% of improvements accepted. | LLM-generated tripwires are useful only after deterministic stability and incremental-value filters. |
| TLA+ at AWS | [Newcombe et al., 2015](https://6826.csail.mit.edu/2020/papers/formal-methods-amazon.pdf) | Specify legal state-machine behaviors and correctness properties; model-check concurrency and faults before implementation. | AWS reported discovery of subtle design errors beyond feasible testing, although the paper gives no universal defect-rate figure. | Use selectively for gate, lease, status and evidence-state machines where interleavings make tests incomplete. |

Four results matter most.

First, judge diversity is necessary but not sufficient. Zheng and Wataoka show that a judge can be consistent and still prefer familiar style, position or its own family. Nuzantara’s family exclusion is directionally excellent, but it needs calibration cases and presentation randomization.

Second, Khan’s verified-quotation mechanism maps directly onto Nuzantara’s anti-hallucination law. A reviewer should not be allowed to cite arbitrary prose from a transcript. It should receive a machine-authenticated repository excerpt, command receipt or object hash.

Third, METR and OpenAI show that tests themselves become reward surfaces. A capable builder may special-case visible inputs, weaken the verifier or exploit the scoring environment. Separating builder, reference implementation and fresh scorer is more important than adding another visible lint.

Fourth, Google’s mutation and fuzzing programs win through selectivity and measured actionability. Nuzantara’s incremental mutation direction is correct; its next step is not “mutate more,” but to make mutation execution trustworthy and turn surviving mutants into durable invariants.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence and judgment |
|---|---|---|
| Generator ≠ grader doctrine | **AHEAD** | `infra/workflows/verify-template.js` plus `.claude/skills/modus/SKILL.md` encode fresh-context skepticism, family exclusion and a separate final adjudicator. Most commercial PR review stops at one advisory model. |
| Guard guilt and innocence | **AHEAD** | `infra/guard-conformance/registry.json` and `.github/workflows/guard-conformance.yml` make overblocking and underblocking co-equal failures. The normalized coverage is nevertheless only 38/51 explicit bilateral declarations. |
| Immutable evidence and reviewer packet | **AHEAD** | `scripts/launch_worker_plane_review_panel.py` hashes packets, freezes records, authenticates launchers and detects mutation. This approaches high-assurance build provenance rather than ordinary AI review. |
| Final-gate execution authority | **BEHIND** | Doctrine requires Opus 5 and no cascade, but `.github/workflows/harness-floor.yml` acknowledges that its publisher does not invoke the reviewer and that status authority is not uniquely bound to a real verdict. |
| Reviewer calibration | **BEHIND** | No verified repository surface reports per-seat sensitivity, specificity, abstention, position-swap instability or false-clean rate on a held-out control set. W100 proves this is consequential. |
| Caller/reachability proof | **BEHIND** | `check_guard_conformance.py` partly relies on workflow-text/path matching. That cannot establish executable reachability and conflicts with the organism’s own “a comment promising visibility is not a caller” lesson. |
| Mutation testing | **AT**, fragile | Incremental mutation and hidden canaries match Google’s scalable pattern, but `.github/workflows/p1s2-mutation-incremental.yml` is not required and W121 invalidates historical runs susceptible to stale bytecode. |
| Reward-hacking defense | **BEHIND** | W95 and W116 show regex and partial-directory monitors missed or misclassified behavior. No universal sealed scoring environment comparable to METR’s three-container design is evident. |
| Verification-shaped required checks | **AT** | Six of 11 required contexts directly exercise behavior/security; five validate governance, metadata or presence. The mix is defensible, but green status does not yet imply semantic completion. |
| Verifier self-testing | **AHEAD** | `verify-the-verifiers.yml`, the adversarial gate’s self-tests and guard fuzzing recognize that a verifier needs its own guilt/innocence proof. Required-context promotion remains incomplete. |
| AI-assisted PR review | **BEHIND**, honestly | The prior action produced zero usable review and was disabled with evidence. That is better than CI theater, but leaves no functioning general AI review gate. |
| Formal/property/metamorphic assurance | **BEHIND** | Tripwires and mutation exist, but no selective formal-verification policy or cross-surface differential oracle is visible for high-risk state machines. |
| Evidence-pack governance | **AHEAD** | `scripts/evidence_pack_lint.py` recomputes gear floors, requires dissent and rejects structurally empty proof. The next frontier is binding receipts to actual execution. |

Overall: **ahead in verification architecture, behind in verification epistemics**. Nuzantara has designed stronger roles and artifacts than most systems, but cannot yet quantify whether the judge is correct or prove that every green decision originated from the prescribed judge over the prescribed evidence.

## 5. Beyond-SOTA recommendations

The ranking uses `(impact × confidence) / implementation cost`, with 1–5 ordinal inputs. None of the individual primitives is novel; the proposed compositions are not present in the surveyed systems and exploit Nuzantara’s scar corpus, cross-family seats, immutable harness and full-lifecycle ownership.

### 1. Compile gate topology into executable reachability proof — score 12.5

**What:** Replace workflow substring matching with a structural graph: guard → test symbol → invoked command → workflow job → required context. Parse workflow steps and test collection metadata; reject comments, dormant files and non-executed ancestors. Every edge must have one guilty synthetic event and one innocent event.

**Why it beats SOTA:** Google mutation proves tests are sensitive; Nuzantara would additionally prove that each scar antidote is reachable from the actual merge authority. No surveyed system combines mutation, bilateral policy controls and required-check reachability into one graph.

**Cost / gear:** 2–3 engineering days, no paid API, Gear 2 implementation and Gear 3 review.

**Risk:** Superscar #3 if parsing over/undermatches; superscar #2 if the graph itself becomes an uncalled artifact.

**Metric:** Required guard reachability 100%; phantom-caller fixtures caught 100%; innocent workflow fixtures accepted 100%; zero text-only edges. Measure through a versioned fixture corpus.

**Kill criterion:** Stop if structural parsing cannot cover at least 95% of required workflows without more than 5% manual exceptions after two iterations.

**First PR:** `feat(verification): prove guard-to-required-context reachability`; modify `infra/guard-conformance/check_guard_conformance.py`, `infra/guard-conformance/registry.json`, and add one focused fixture test; ≤350 net lines.

### 2. Make the final verdict a cryptographic execution attestation — score 10.0

**What:** A Gear-3 PASS becomes valid only when accompanied by: reviewed commit SHA, packet SHA, diff SHA, exact CLI/model profile, reviewer-family identifier, executable identity, sandbox mode, start/end timestamps, exit status and verdict-output SHA. The required-status publisher accepts only this object from `scripts/launch_worker_plane_review_panel.py`.

**Why it beats SOTA:** Supply-chain attestations prove builders; LLM review tools emit comments; Nuzantara can combine both so a review verdict becomes a provenance-bound build artifact. This directly exploits the existing immutable harness.

**Cost / gear:** 3–4 days, one Opus 5 subscription call per actual Gear-3 gate, Gear 3.

**Risk:** Superscar #6 if attestation is mistaken for truth; superscar #2 if status publication bypass remains possible.

**Metric:** 100% of Gear-3 statuses validate against a unique authenticated run; zero publisher-only PASSes; p95 additional gate latency below 20 minutes.

**Kill criterion:** Revert mandatory enforcement if more than 2% of valid gates fail solely from attestation transport over the first 50 runs; retain audit-only logging while repairing transport.

**First PR:** `feat(harness): bind final verdict to authenticated reviewer execution`; modify `scripts/launch_worker_plane_review_panel.py`, add `infra/final-gate/attestation.schema.json`, and add a focused attestation test; ≤400 net lines.

### 3. Build a scar-derived reviewer calibration exchange — score 6.7

**What:** Convert historical scars into redacted, immutable microcases: real defect, plausible false accusation, corrected defect, and correction-that-introduces-a-defect. Keep labels hidden from the evaluated reviewer. Randomize ordering and stylistic presentation. Track sensitivity, specificity, abstention, calibration and family-conditioned false-clean rates.

**Why it beats SOTA:** CriticGPT calibrates on inserted defects; debate authenticates quotes; Nuzantara can calibrate several subscribed model families against its own measured failure ecology, including second-order correction failures. The scar corpus is the asymmetry no external product has.

**Cost / gear:** 4–6 days for the first 30 cases; approximately three flat-subscription reviewer calls per calibration batch; Gear 3.

**Risk:** Superscar #6 if labels are wrong; superscar #3 if lexical cues leak the answer.

**Metric:** Before promotion, sensitivity and specificity each ≥85% on at least 30 held-out cases; position-swap disagreement <10%; false-clean rate on correction cases <10%. Publish confidence intervals, not only point estimates.

**Kill criterion:** Suspend a seat from final adjudication if either sensitivity or specificity remains below 75% across two independent 30-case batches.

**First PR:** `feat(verification): add blind scar calibration schema and scorer`; add `infra/verification-calibration/schema.json`, a redacted five-case seed, and deterministic scorer tests; ≤350 net lines.

### 4. Add a reward-surface firewall and dual-channel monitor — score 5.3

**What:** Classify tests, verifier code, evidence schemas, workflow gates and status publishers as reward surfaces. For builder sessions, record attempted modifications and tool actions; at review, independently scan both trajectory actions and final diff. Evaluate in a fresh scoring environment with held-out metamorphic cases. Reasoning traces may be used only when the sanctioned CLI exposes them; the system must remain useful from actions alone.

**Why it beats SOTA:** OpenAI monitors reasoning and actions; METR seals the scorer; Anthropic studies reward tampering. The composition adds repository-native authority maps and scar-specific controls without requiring a paid API or universal access to private reasoning.

**Cost / gear:** 5–7 days, one fast subscribed monitor plus deterministic scanners per high-risk PR; Gear 3 for enforcement.

**Risk:** Superscar #3 from broad “test modification” alarms; superscar #6 if monitor silence is interpreted as proof of honest intent.

**Metric:** ≥95% detection on W95/W116-style and synthetic scorer-tampering cases, ≤5% false positives on legitimate test changes, and 100% fresh-scorer execution for reward-surface diffs.

**Kill criterion:** Keep advisory-only if false positives exceed 10% across 100 qualifying diffs or if the monitor adds more than 15 minutes p95 without catching any deterministic-scanner miss.

**First PR:** `feat(verification): classify and detect reward-surface changes`; add `infra/reward-surfaces/registry.json`, one deterministic diff classifier and bilateral tests; ≤300 net lines.

### 5. Convert mutation survivors into an invariant ladder — score 5.3

**What:** First make mutation bytecode-immune: immutable copy, `PYTHONDONTWRITEBYTECODE=1`, cache purge outside the measured tree and restoration from authenticated bytes. Then classify every surviving mutant as equivalent, missing example, missing property, missing differential oracle or world-model gap. A useful survivor must yield a durable tripwire or explicit abstention.

**Why it beats SOTA:** Google optimizes mutant actionability; Nuzantara can connect actionability to its scar and evidence systems, ensuring a survivor becomes organizational memory rather than a transient score.

**Cost / gear:** 3–5 days; local compute only; Gear 2 for routine changes, Gear 3 for the mutation driver.

**Risk:** Superscar #6 if mutation score is treated as correctness; W121 recurrence if cache isolation is incomplete.

**Metric:** Reproducibility 100% across three runs; mutation score ≥85% on changed critical lines; ≥15% of non-equivalent survivors produce a new invariant/property test; flaky mutant classification <1%.

**Kill criterion:** Disable blocking use if repeated runs disagree by more than two percentage points or any source hash changes during evaluation.

**First PR:** `fix(verification): make incremental mutation bytecode-immune`; modify `.github/workflows/p1s2-mutation-incremental.yml`, the existing mutation driver, and add a same-size/same-second regression fixture; ≤250 net lines.

### 6. Apply bounded formal and differential verification to gate state machines — score 3.0

**What:** Select only state machines whose failure can falsely authorize progress: final verdict publication, evidence-pack lifecycle, lease/lock ownership and guard activation. Specify legal transitions and invariants in a small model; pair this with differential tests between alternative implementations or readers.

**Why it beats SOTA:** AWS applies formal methods to distributed designs, but Nuzantara can couple model-checked authorization invariants with AI-generated counterexamples, cross-family refutation and scar ingestion.

**Cost / gear:** 1–2 weeks for the first state machine, local tooling, Gear 3.

**Risk:** Superscar #2 if specification and runtime drift; superscar #6 if the model is advertised as proving more than it covers.

**Metric:** All reachable authorization states satisfy “no PASS without authenticated verdict”; at least one historical or seeded race is found before adoption; correction-of-correction rate on the selected state machine falls 50% over 90 days.

**Kill criterion:** Stop expansion if the first model takes over 10 engineering days without finding a defect, clarifying an invariant or generating an executable test.

**First PR:** `docs(verification): specify final-verdict authorization state machine`; add one compact specification, model-check command and two counterexample fixtures; ≤400 net lines.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 0–30: prove execution, not visibility

- Land structural guard-to-workflow reachability.
- Normalize the 13 non-bilateral registry forms or explicitly classify them as exemptions.
- Repair mutation bytecode isolation.
- Introduce final-gate attestation in audit-only mode.
- Capture baseline metrics: phantom edges, reviewer latency, explicit guilt/innocence coverage, mutation reproducibility and publisher-only verdict count.

### Wave 2 — Days 31–60: calibrate adversaries

- Create at least 30 blind scar-derived calibration cases.
- Run every eligible reviewer family with order swaps.
- Publish sensitivity, specificity, abstention and correction-case false-clean rates.
- Add the reward-surface registry and deterministic action/diff scanner.
- Promote the authenticated final-gate attestation to required after 20 clean audit runs.

### Wave 3 — Days 61–90: enforce and generalize

- Add fresh-scorer held-out tripwires to reward-surface changes.
- Turn useful mutation survivors into property, metamorphic or differential tests.
- Promote `verify-the-verifiers` and the canary-tautology gate only after measured innocence behavior is acceptable.
- Model-check the final-verdict authorization state machine.
- Re-measure correction chains using structured claim/cure links rather than commit-subject regex.

| First PR | Files | Net-line cap | Gear | Acceptance test |
|---|---|---:|---:|---|
| `feat(verification): prove guard-to-required-context reachability` | `infra/guard-conformance/check_guard_conformance.py`, `infra/guard-conformance/registry.json`, focused fixture test | 350 | 3 | A workflow comment naming a test fails; a real invoked step passes; innocent unrelated workflow passes. |
| `fix(verification): make incremental mutation bytecode-immune` | `.github/workflows/p1s2-mutation-incremental.yml`, mutation driver, W121 regression fixture | 250 | 2 | Three same-size/same-second cycles produce identical source hashes and mutation verdicts with no `.pyc` provider. |
| `feat(harness): emit authenticated final-gate attestation` | `scripts/launch_worker_plane_review_panel.py`, new schema, focused tests | 400 | 3 | Wrong commit, packet, executable or verdict hash is rejected; the exact authenticated run is accepted. |
| `feat(verification): add blind scar calibration scorer` | new `infra/verification-calibration/` schema, seed cases and scorer | 350 | 3 | Swapped presentation preserves expected label; label leakage and empty evidence fail. |
| `feat(verification): classify reward-surface changes` | new reward-surface registry, scanner and bilateral tests | 300 | 3 | Disabling an assertion or weakening a status predicate is guilty; adding a legitimate regression test is innocent. |
| `docs(verification): specify verdict authorization invariants` | one state-machine specification and model-check fixture | 400 | 3 | The model rejects publisher-only PASS and accepts an authenticated, non-expired verdict exactly once. |

## 7. Needs-ruling

1. **Hidden-control policy:** Zero must decide whether locally held, redacted calibration labels and held-out scorer cases may remain outside the public repository. Public transparency and adversarial secrecy cannot both be maximized.
2. **Final-gate authority:** Zero must rule that no Gear-3 PASS is authoritative without the authenticated Opus 5 attestation, accepting suspension when that seat or subscription quota is unavailable.
3. **AI PR review spend:** Re-enabling `.github/workflows/ai-pr-review.yml.disabled-2026-08-20-zero-value-ci-trust-gate` requires consent for recurring flat-subscription token use after its workspace-trust mechanism and model pin are empirically demonstrated.
4. **Formal-method scope:** Mandatory modeling of authorization state machines adds latency. Zero must choose which business-critical surfaces justify that cost; the recommendation is verdict publication, evidence lifecycle and lease ownership only.

## 8. §Meta-pattern

The single defective belief is:

> If the proof artifact is visible and green, the intended independent proof must have happened.

That belief generates nearly every observed recurrence:

- a test file is mistaken for a workflow caller;
- a workflow reference is mistaken for executable reachability;
- a non-empty receipt is mistaken for authenticated evidence;
- same-family agreement is mistaken for independence;
- a mutation score is mistaken for a trustworthy oracle;
- a correction is mistaken for closure;
- an exit-zero review job is mistaken for an actual review;
- a status publisher is mistaken for the prescribed final judge.

The replacement belief should be:

> A gate exists only when an authenticated counterexample can traverse its real caller path, change the authoritative decision, and an innocent control can traverse the same path without being blocked.

That definition is stricter than current industry practice, measurable, and naturally composes Nuzantara’s strongest assets: bilateral guard tests, scars, cross-family seats, immutable packets and full-lifecycle session ownership.

## 9. Sources

1. [Zheng et al., “Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena”](https://arxiv.org/abs/2306.05685), 2023. Accessed 2026-08-29. Primary NeurIPS paper quantifying judge agreement and position, verbosity and self-enhancement biases.
2. [Wataoka et al., “Self-Preference Bias in LLM-as-a-Judge”](https://arxiv.org/abs/2410.21819), 2024. Accessed 2026-08-29. Primary experimental study of judge familiarity and self-preference.
3. [OpenAI, “Finding GPT-4’s mistakes with GPT-4”](https://openai.com/index/finding-gpt4s-mistakes-with-gpt-4/), 2024-06-27. Accessed 2026-08-29. Primary CriticGPT results on AI-assisted human review.
4. [OpenAI, “Introducing SWE-bench Verified”](https://openai.com/index/introducing-swe-bench-verified/), 2024-08-13. Accessed 2026-08-29. Primary methodology for human-validated tasks and hidden solution/regression tests.
5. [OpenAI, “Detecting misbehavior in frontier reasoning models”](https://openai.com/index/chain-of-thought-monitoring/), 2025-03-10. Accessed 2026-08-29. Primary evidence on monitoring coding-agent test subversion.
6. [METR, “Frontier Risk Report: February to March 2026”](https://metr.org/blog/2026-05-19-frontier-risk-report/), 2026-05-19. Accessed 2026-08-29. Primary agent-evaluation evidence on reward hacking and isolated scoring.
7. [Anthropic, “Sycophancy to subterfuge: Investigating reward tampering in language models”](https://www.anthropic.com/research/reward-tampering), 2024-06-17. Accessed 2026-08-29. Primary controlled study of specification gaming and evaluator tampering.
8. [Petrović et al., “Practical Mutation Testing at Scale: A View from Google”](https://research.google/pubs/practical-mutation-testing-at-scale-a-view-from-google/), 2021. Accessed 2026-08-29. Primary industrial study of incremental, filtered mutation testing.
9. [Google Open Source Security Team, “Leveling Up Fuzzing: Finding more vulnerabilities with AI”](https://security.googleblog.com/2024/11/leveling-up-fuzzing-finding-more.html), 2024-11-20. Accessed 2026-08-29. Primary OSS-Fuzz deployment results.
10. [Meta researchers, “Automated Unit Test Improvement using Large Language Models”](https://web.eecs.umich.edu/~movaghar/Automatic%20Test%20Generation%20Meta%202024.pdf), 2024. Accessed 2026-08-29. Primary TestGen-LLM production study.
11. [Newcombe et al., “How Amazon Web Services Uses Formal Methods”](https://6826.csail.mit.edu/2020/papers/formal-methods-amazon.pdf), 2015. Accessed 2026-08-29. Primary AWS account of production TLA+ use.
12. [Khan et al., “Debating with More Persuasive LLMs Leads to More Truthful Answers”](https://arxiv.org/abs/2402.06782), 2024. Accessed 2026-08-29. Primary ICML study of debate, verified quotations and judge-bias controls.