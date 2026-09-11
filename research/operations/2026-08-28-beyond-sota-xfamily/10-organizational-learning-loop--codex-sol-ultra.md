---
panel: beyond-sota-xfamily
lane: 10-organizational-learning-loop
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T19:02:29Z
finished: 2026-08-28T19:11:45Z
duration_s: 556
exit: 0
words: 5198
prompt_sha256_16: a35bb1c187572e58
prompt_chars: 18385
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: "10/13 — Organizational learning loop"
model: "OpenAI GPT-5.6 sol, reasoning effort ULTRA (pinned lane)"
sources: 12
repo_files_verified: 20
status: complete
---

## 0. TL;DR

Nuzantara is ahead of SOTA in trauma capture, taxonomy, compression, and governed self-reflection, but behind SOTA in proving that each lesson becomes an effective, armed, reusable control.
The largest gap is closure: the last explicit census found only 2 of 66 scar gates armed, while recurrent scar lineages and AMENDMENTS recurrences show that written knowledge still escapes into practice.
Top move 1: introduce a machine-readable scar lifecycle linking incident, family, counterfactual test, gate, deployment state, recurrence, and measured outcome.
Top move 2: require every high-severity antibody to prove both guilt and innocence, then measure whether it actually reduces recurrence.
Top move 3: add a recidiva sentinel and doctrine-hash reconciler so repeated trauma and divergent doctrine become observable within minutes, not weeks.
The target is not more memory. It is a measurable transition from `captured` to `effective`, with high-severity armed coverage rising from the recorded 3.0% to at least 70% in 90 days.

## 1. How Nuzantara does it today

The organizational-learning spine begins with individual cicatrix entries in `.claude/rules/cicatrix-scars.md`, overflow history in `.claude/rules/cicatrix-scars-archive.md`, and their compressed bridge in `.claude/rules/cicatrix-superscar.md`. The bridge groups the corpus into ten failure families and gives each family a disease, early signal, structural antidote, and member scars. It explicitly presents itself as a routing bridge rather than an encyclopedia.

That compression is mechanically protected. `scripts/tests/test_superscar_budget.py` caps `.claude/rules/cicatrix-superscar.md` at 14,000 bytes, verifies that every referenced W-number resolves to a real heading in the active or archived corpus, accepts the corpus’s several Markdown heading depths, and checks that the three scar files remain excluded from formatting churn. Its own history records a pre-trim bridge size of 73,854 bytes. `.github/workflows/check-cicatrix-scar-pointers.yml` runs the pointer tests, but its current comments classify the check as non-required observation rather than a merge-blocking control.

Capture and identity have partial automation. `.claude/commands/scar.md` defines the capture workflow and calls the repository `.claude` tree canonical, while its operative append target is a HOME-path scar file followed by propagation to worktrees. That split is itself a HOME-fork exposure: the doctrine declares one source while the command mutates another surface first. `scripts/lint_scar_number_collision.py` supplies a stronger antibody for numbering: it compares headings from `origin/main` with scar additions across all open PRs, uses numeric rather than lexical ordering, supports offline fixtures and `--next-only`, and distinguishes content collisions from operational failures.

Archiving exists but is deliberately dormant. `infra/launchagents/cicatrix_autoarchive.sh` raised its trigger from 40 KB to 10 MB because the warehouse is no longer injected wholesale; it includes sibling-race precautions and will not push. Consequently, the active corpus is governed primarily by the superscar compression budget, not by an active archive-size controller.

The last explicit gate inventory is `infra/scar-gates/MANIFEST.json`. Generated on 2026-06-27, it lists 66 scars, 2 armed gates, and 64 prose-only debts. It is valuable historical evidence but is stale relative to later scars such as W113–W121. There is no normalized, current scar-level state machine that distinguishes “script named,” “test exists,” “workflow runs,” “required check,” and “observed effective.”

A second loop records flaws in the learning process itself. `.claude/skills/modus/AMENDMENTS.md` is expressly an evidence log rather than doctrine. `.claude/skills/modus/SKILL.md` requires per-run misfire capture, normal review for doctrine changes, and operator approval. `infra/workflows/modus-bench.js` executes four independent sweeps—scar evidence, loop misfires, frontier harnesses, and frontier models—then sends every proposal to a fresh-context adversarial refuter. Survivors become proposed AMENDMENTS; the workflow never edits `SKILL.md` directly.

The first enumerated modus bench converted 11 of 12 proposals into doctrine, recorded in `.claude/skills/modus/AMENDMENTS.md`; subsequent commits visible in the verified history of `.claude/skills/modus/SKILL.md` applied another three adversarially checked changes. This is unusually strong generator≠grader governance. The weakness is that most later dated entries lack machine-readable proposal, disposition, commit, and effectiveness fields, so overall conversion cannot be computed.

The lesson harvester follows the same conservative pattern. `.github/workflows/p7-lesson-harvester.yml` is network-free, PII-free, deterministic, and shadow-only. It tests objective anchoring, non-enforcement, reversibility, recurrence thresholds, and idempotence. It proposes learning but cannot silently alter doctrine. This is the right authority boundary, although it leaves operational conversion dependent on a later human-controlled path.

The broader experience system is more aspirational. `docs/EXPERIENCE_LIBRARY_OPS.md` describes local SQLite trajectories shaped as `sense → think → act → reflect`, outcome-sensitive inheritance, decay, and retrieval before reasoning. `docs/SKILL_REGISTRY_OPS.md` describes evidence thresholds for promotion, 32 seeded skills, decay, and propose-only jobs, but also says the weekly merge/promotion/decay cron is not active. `.claude/skills/skill-catalog/SKILL.md` keeps lower-tier skills out of ambient context and routes retrieval through the catalog. The architecture resembles lifelong-agent research, but the verified documentation does not establish continuous use or measured benefit.

Repository retrospectives show both learning and failure to learn. `research/operations/2026-08-21-token-ceremony-ci-system-audit.md` measured oversized automatic doctrine surfaces and led to the superscar budget. `research/operations/2026-08-26-retro-fleet-sessions-25-26.md` found that 26 of 119 commits touched only ledger/scar artifacts and explicitly noted that the organism did not instrument itself—the report required a one-time parser. `research/operations/2026-08-27-retro-corrections-after-dispatch.md` records a correction caused by counting the wrong Git tree and a 14-way dispatch that produced 13 fork failures. `research/operations/2026-06-30-claude-code-perfect-session-doctrine.md` supplies the older capture-and-persist model but also preserves earlier, larger memory-budget assumptions.

The lane brief’s HOME memory files—including `$MEM/MEMORY.md`, `MEMORY_METHOD_LESSONS.md`, `MEMORY_VERIFICATION_RULES.md`, `/Users/nuzantara/.claude/commands/mem-trim.md`, and `/Users/nuzantara/.claude/scripts/mem`—were outside the authorized snapshot and were not read. Therefore the claimed current 1,707-file body corpus, 43 verification rules, current memory-type distribution, and current August lesson count cannot be certified here. The latest repository-captured memory measurement is instead 18,236 bytes in `research/operations/2026-08-21-token-ceremony-ci-system-audit.md`.

Similarly, the present contents of three alleged HOME `CLAUDE.md` copies were inaccessible. What is verified is a dated AMENDMENTS entry reporting that HOME and repository model doctrine disagreed for 23 days; `.claude/skills/modus/AMENDMENTS.md` is evidence of drift, not a current three-copy census.

## 2. Scars & ledger evidence in this area

### Corpus and conversion measurements

| Measure | Verified result | Interpretation |
|---|---:|---|
| Active W-headings | 65 | Counted from `.claude/rules/cicatrix-scars.md`; headings are the safest available unit, not guaranteed unique incidents. |
| Archived W-headings | 46 | Counted from `.claude/rules/cicatrix-scars-archive.md`. |
| Combined scar-like headings | 111 | Some entries have suffixes or informational variants; do not relabel this as 111 unique root incidents. |
| Active/archive displayed sizes | 289 KB / 387 KB | The raw corpus is substantial; compression is essential. |
| Superscar family coverage | 10 families | `.claude/rules/cicatrix-superscar.md` provides the common taxonomy. |
| Families with an explicit `→ ESEGUIBILE` target | 6/10, or 60% | Families 1, 2, 3, 4, 7, and 9 name a concrete script or gate. Other families may mention operational mechanisms but lack the same explicit contract. |
| Last explicit armed-gate share | 2/66, or 3.0% | From `infra/scar-gates/MANIFEST.json`, generated 2026-06-27. It is a stale but honest baseline, not a current claim. |
| Recidiva textual-marker proxy | 11/111, or 9.9% | Ten active plus one archived marker. This is a lower-quality proxy because recurrence is not normalized metadata. |
| First bench proposal conversion | 11/12, or 91.7% | Explicitly recorded as applied in `.claude/skills/modus/AMENDMENTS.md`; a later commit applied three further amendments. |
| Current overall amendment conversion | Not computable | Forty-two dated misfire lines exist, but later entries lack consistent proposal/disposition identifiers. |
| Latest repository-captured `MEMORY.md` size | 18,236 bytes | Against a 17,000-byte target, this is 1,236 bytes or 7.3% over. Current HOME state was inaccessible. |

The four-month scar-rate lower bound is:

| Month in 2026 | Dated heading count | Adjustment | Defensible minimum |
|---|---:|---:|---:|
| May | 26 | 0 | 26 |
| June | 33 | 0 | 33 |
| July | 28 | 0 | 28 |
| August | 14 | +5 body-dated entries | ≥19 |

The average is therefore at least 26.5 scar-like entries per month. August’s mixed schema—some dates in headings, others only in bodies—prevents exact automated incidence measurement. Normalizing date, incident identity, parent scar, and family would convert this from an editorial count into an operational metric.

Three recent scars demonstrate high-quality learning:

- W121 in `.claude/rules/cicatrix-scars.md` found mutation tests reusing poisoned bytecode when source size and modification time were unchanged within a second. Its executable lesson is to disable bytecode/cache effects during mutation evaluation. It also records that an attempted cleanup erased an uncommitted fix—one trauma exposed a second.
- W119 found that `\s+` crossed newlines and consumed unrelated command arguments. The correction used horizontal whitespace and paired guilt and innocence tests. Crucially, the first hypothesis and first innocence test were themselves wrong until pre-fix reproduction disproved them.
- W113 records four adversarial correction rounds: 31 objections, 29 valid. Its conclusion is that a replacement claim must be treated as a new untrusted claim, with a retracted-claim registry and linter rather than textual reassurance.

Recurrence is not hypothetical. `.claude/rules/cicatrix-superscar.md` explicitly records the W65→W90→W100→W113 correction-integrity lineage, a W101→W101-recidiva→W107-style Exists≠Armed lineage, and W84-tccutil-recidiva. The 9.9% marker proxy probably understates recurrence because ordinary references and implicit repeats are not structured as parent links.

AMENDMENTS also catches recidiva in the learning machinery:

- A no-pipe push rule was violated again on 2026-07-16.
- The malformed Workflow-arguments pattern recurred on 2026-08-08 after its 2026-07-02 lesson.
- On 2026-08-22, two sessions ran approximately 44 and 31 hours, emitted about 8.6 million output tokens, and produced roughly ten business commits, yet captured no AMENDMENTS during execution.
- On 2026-08-26, zero AMENDMENTS were recorded across another multi-mandate interval; `.claude/skills/modus/AMENDMENTS.md` identifies this as a repeat of the earlier capture gap.

For August, the inaccessible memory corpus prevents a true “lessons added per week” calculation. The closest repository-native proxy is dated AMENDMENTS: 2 entries on August 1–7, 6 on August 8–14, 0 on August 15–21, and 4 on August 22–28. The zero week coinciding with extremely long sessions is evidence that capture reliability falls precisely when learning value is highest.

The large PENDING-ARMS ledger was not directly read because the 20-path audit ceiling had been reached. The latest verified in-repository snapshot, `research/operations/2026-08-26-retro-fleet-sessions-25-26.md`, reported 586 entries, with 307 overdue technical-debt items and 169 operator-owned items; 476 of 586, or 81.2%, belonged to those two categories. This is not a current ledger census, but it shows why “proposal created” cannot be treated as “antibody deployed.”

## 3. World SOTA survey

| System or practice | Primary source | Mechanism | Published effect | Transferability |
|---|---|---|---|---|
| Google SRE postmortems | [SRE Workbook, Postmortem Culture](https://sre.google/workbook/postmortem-culture/) (2018) | Blameless review, machine-readable tags, owner, tracking bug, priority, verifiable end state, preventative and mitigative actions, and closure incentives. | No global recurrence percentage published; Google states that untracked actions are forgotten and requires high-priority follow-up for user-affecting incidents. | Directly applicable. Every high-severity scar should have an owner, control, closure state, and effectiveness measure. |
| PagerDuty incident response | [Postmortem Process](https://response.pagerduty.com/after/post_mortem_process/) (live documentation) | A public, reusable post-incident operating procedure rather than an informal retrospective. | No outcome number published on the page. | Useful as a minimal operational workflow; Nuzantara’s richer taxonomy should retain its stronger adversarial and executable layers. |
| NASA lesson lifecycle | [NASA APPEL Lessons Learned](https://www.nasa.gov/learning-resources/for-professionals/appel-lessons-learned/) (2026) | Distinguishes collection, recording, sharing, and application; lessons can live in LLIS, local repositories, reports, cases, and video. | No consolidated effectiveness number published. | The lifecycle distinction maps naturally to scar states; “recorded” must not equal “applied.” |
| NASA LLIS failure audit | [NASA OIG IG-12-012](https://oig.nasa.gov/docs/IG-12-012.pdf) (2012) | Independent audit of whether a formal lessons repository was actually searched, contributed to, and governed. | Only 16/28 managers used LLIS during acquisition; 12/28 contributed; only JPL contributed consistently from 2005–2010. | This is the strongest warning for Nuzantara: a large corpus can become institutional theatre without pull-time use and freshness. |
| Aviation ASRS | [NASA ASRS Immunity Policies](https://asrs.arc.nasa.gov/overview/immunity.html) (program since 1975) | Voluntary reporting, separation of collector from regulator, de-identification, confidentiality, restricted enforcement use, and periodic analysis. | The official page reports no breach of confidentiality under NASA management. | Strong fit with the PII output boundary and blameless capture. A scar should describe system conditions, not expose people or client data. |
| U.S. Army AAR and before-action reports | [Commander’s Guide for Driving Change](https://api.army.mil/e2/c/downloads/2023/01/31/99194b3d/commanders-guide-for-driving-change-the-learning-organization-framework-jan-19-public.pdf) (2019) | Immediate AAR asks planned/actual/why/change; before-action reports pull prior lessons into preparation for similar missions. | No controlled outcome number published. | The before-action pattern is missing from the verified loop: relevant scars should be compiled before a matching task begins. |
| Toyota poka-yoke | [Toyota, A Swift Response](https://www.toyota-global.com/company/history_of_toyota/75years/text/entering_the_automotive_business/chapter2/section1/item2.html) (official archive) | Lessons become mistake-proofing, critical-process designation, standards, supplier checks, and defect elimination—not reminders to be more careful. | No isolated causal number published on this page. | Exact conceptual match for executable antidotes: change the system so the error is difficult or impossible. |
| OPA policy-as-code | [OPA Policy Testing](https://www.openpolicyagent.org/docs/policy-testing) (live documentation) | Requirements become declarative policy with positive and negative tests, runnable locally and in CI. | Official example falls from 4/4 to 3/4 tests after removing a rule, demonstrating detectable policy regression; no organizational outcome claim. | Suitable for cross-cutting scar invariants where Python linters are too fragmented. Remains local and has no LLM cost. |
| Semgrep institutional rules | [Semgrep Rule Ideas](https://docs.semgrep.dev/writing-rules/rule-ideas) (updated 2025-10-15) | Converts repeated review comments, dangerous APIs, authentication conventions, and postmortem findings into repository-wide rules. | Documentation estimates common rules at roughly 5–15 minutes to author; no independent recurrence result. | Good for code-shaped antibodies, provided every rule has guilt and innocence fixtures to avoid W119-style overmatch. |
| Reflexion | [Reflexion paper](https://arxiv.org/abs/2303.11366) (2023) | Converts scalar/environment feedback into verbal reflection stored in episodic memory, without weight updates. | 91% HumanEval pass@1 versus the cited GPT-4 baseline of 80%. | Nuzantara already exceeds simple self-reflection in governance; it should adopt the explicit trial→feedback→retrieval measurement. |
| Voyager | [Voyager project and paper](https://voyager.minedojo.org/) (2023) | Automatic curriculum, executable skill library, environment feedback, self-verification, embedding retrieval, and composition of prior skills. | 3.3× more unique items, 2.3× longer travel, and milestones up to 15.3× faster than prior approaches. | Strong model for evidence-backed skill compounding. Nuzantara must add production safety, authority gates, and decay controls absent from the game benchmark. |
| Anthropic context engineering | [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (2025-09-29) | Treats context as a finite attention budget and cyclically refines the state available to long-running agents. | Reports cross-model context degradation but does not publish a single operational uplift. | Supports the 14 KB superscar bridge and argues against solving learning by injecting the full corpus. |

Five comparisons matter most.

First, Google’s decisive distinction is action closeout. Nuzantara’s scars are often deeper than ordinary postmortems, but its latest explicit armed-gate census is far weaker than Google’s owner/tracker/end-state norm.

Second, the NASA OIG result proves that institutional memory can fail despite official status, rich content, and policy mandates. Searchability alone does not make a lesson operative. Nuzantara’s inactive promotion jobs and unmeasured pre-task retrieval face the same failure mode at smaller scale.

Third, Toyota, OPA, and Semgrep converge on error-proofing: the highest-value lesson is an executable constraint with tests. Nuzantara already believes this, but W119 and W121 show that an antibody can itself lie unless evaluated counterfactually.

Fourth, Reflexion and Voyager validate memory and executable skills without weight updates, matching a flat-subscription, CLI-based organism. Nuzantara’s advantage is its independent refuters and human authority gate; its deficit is the absence of equally clear before/after task-performance experiments.

Fifth, Army before-action reports close the temporal loop. Nuzantara captures after failure and compresses for general context, but the verified repository does not show a measured mechanism that assembles the most relevant prior traumas immediately before an analogous operation.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence and judgment |
|---|---|---|
| Trauma capture density | **AHEAD** | At least 111 active/archive scar-like headings and 26.5 entries/month over the measured four-month lower bound are unusually rich for a solo-owner organism: `.claude/rules/cicatrix-scars.md`, `.claude/rules/cicatrix-scars-archive.md`. |
| Failure taxonomy | **AHEAD** | Ten superscar families expose cross-incident mechanisms rather than isolated anecdotes: `.claude/rules/cicatrix-superscar.md`. |
| Compression discipline | **AHEAD** | A 73,854-byte bridge was reduced to a tested 14,000-byte ceiling with pointer validation: `scripts/tests/test_superscar_budget.py`. |
| Blameless, privacy-preserving learning | **AT** | System-centered scar language and the deterministic, PII-free harvester align with SRE/ASRS practice: `.github/workflows/p7-lesson-harvester.yml`. Reporter-safety metrics are absent. |
| Antidote design | **AHEAD** | Six of ten families explicitly name executables, and W119 pairs guilt and innocence tests. The doctrine understands poka-yoke better than most postmortem systems: `.claude/rules/cicatrix-superscar.md`. |
| Antidote deployment and closure | **BEHIND** | The last explicit census is 2/66 armed; current state is unmeasurable: `infra/scar-gates/MANIFEST.json`. |
| Counterfactual effectiveness proof | **BEHIND** | W119 and W121 demonstrate it locally, but no universal contract requires every gate to prove failure-before and success-after: `.claude/rules/cicatrix-scars.md`. |
| Recurrence analytics | **BEHIND** | Recidiva exists as prose and lineage examples; the 9.9% rate is only a textual proxy. |
| Self-refinement governance | **AHEAD** | Four independent sweeps, fresh-context refutation, no self-application, and operator approval exceed Reflexion-style ungoverned reflection: `infra/workflows/modus-bench.js`, `.claude/skills/modus/SKILL.md`. |
| Pre-task transfer | **BEHIND** | Experience and skill retrieval are documented, but jobs are inactive and no live reuse outcome is published: `docs/EXPERIENCE_LIBRARY_OPS.md`, `docs/SKILL_REGISTRY_OPS.md`. |
| Doctrine consistency | **BEHIND** | A verified AMENDMENTS entry records 23 days of HOME-versus-repository model-roster drift: `.claude/skills/modus/AMENDMENTS.md`. |
| Continuous measurement | **BEHIND** | The fleet retro says the organism required a one-time parser to measure itself: `research/operations/2026-08-26-retro-fleet-sessions-25-26.md`. |
| Learning authority boundary | **AHEAD** | The lesson harvester and modus-bench propose but do not self-legislate, preserving Zero’s final authority. |

## 5. Beyond-SOTA recommendations

The priority score is `(impact × confidence) / relative cost`, each input scored 1–5.

### 1. Scar-to-Antibody Lifecycle Compiler — score 12.5

- **What:** Give every scar canonical structured fields: incident ID, date, family, parent scar, evidence, severity, proposed antidote, executable target, guilt fixture, innocence fixture, CI workflow, required-state, deployment commit, observation window, outcome, owner class, and lifecycle state: `captured → classified → tested → armed → observed-effective | ineffective | retired`.
- **Why it beats surveyed SOTA:** Google tracks actions; NASA tracks lessons; Semgrep encodes rules; Voyager stores executable skills. None of the surveyed systems combines incident lineage, counterfactual proof, merge enforcement, and measured post-deployment recurrence in one lifecycle graph.
- **Asymmetry exploited:** 111-scar corpus, ten stable families, local always-on machines, existing tests, hooks, CI, and cross-family reviewers.
- **Cost:** 8–12 engineering hours; approximately 100k–200k flat-subscription review tokens; no paid API.
- **Gear:** 2 initially; Gear 3 before making the check required.
- **Risk:** A new metadata file could become another source of truth—superscar family #1—or claim false closure, family #6. Generate views from one canonical record and test round trips.
- **Metric:** Current known armed baseline 3.0% → at least 70% of high-severity active scars in `observed-effective` or explicitly waived state by day 90; 100% schema coverage for newly captured scars; median capture-to-tested under seven days.
- **Measurement:** CI emits a versioned JSON summary and weekly trend artifact; no client data.
- **Kill criterion:** Stop if authorship overhead exceeds five minutes per scar or parser/schema accuracy remains below 98% after 30 migrated entries.
- **First PR:** Add schema plus read-only validator only; no migration and no enforcement; ≤400 net lines.

### 2. Counterfactual Antibody Gate — score 8.3

- **What:** Every high-severity executable antidote must demonstrate: the guilty fixture fails without the control, the innocent fixture passes, the control kills the intended mutation, and disabling it reopens the exact failure.
- **Why it beats surveyed SOTA:** OPA and Semgrep test policies; Toyota mistake-proofs operations. The proposed gate additionally binds every control to its originating scar and tests the control’s own failure modes—a response to W119, W121, and W113.
- **Asymmetry exploited:** The corpus contains concrete failure artifacts and an adversarial grader culture capable of testing the antibody, not merely the original disease.
- **Cost:** 12–20 hours for the framework and first two families; 150k–300k flat-subscription tokens.
- **Gear:** 3.
- **Risk:** The gate can overmatch or create false security—families #3 and #6.
- **Metric:** Mutation kill rate ≥95%; innocence false-positive rate <2%; protected-family recurrence proxy ≤3% after a 60-day observation window.
- **Measurement:** Store only fixture IDs, outcome hashes, runtime, and linked W-number.
- **Kill criterion:** Disable mandatory enforcement if median CI overhead exceeds 90 seconds or false positives exceed 2% over 50 PRs.
- **First PR:** Implement the generic guilt/innocence harness and two synthetic fixtures, without converting existing scars; ≤350 lines.

### 3. Recidiva Sentinel and Superscar Escalator — score 6.7

- **What:** Parse explicit parent links plus semantic signatures, propose recurrence edges, and automatically escalate a family for higher-order review after two confirmed repeats. The sentinel proposes; a non-generating reviewer confirms.
- **Why it beats surveyed SOTA:** Postmortem aggregators find themes, while Reflexion stores trial memories. This combines causal lineage, deployment state, and recurrence hazard to decide when a local patch has failed as an organizational treatment.
- **Asymmetry exploited:** Dense W-number history, ten families, multi-model refuters, and full-lifecycle sessions.
- **Cost:** 10–16 hours; 100k deterministic/cheap-model classification tokens initially, with all sensitive content local and no Fable auto-routing.
- **Gear:** 3.
- **Risk:** False lineage becomes doctrine—family #6—or noisy retry behavior, family #8.
- **Metric:** Human-confirmed edge precision ≥90%; 100% of explicit recidiva markers normalized; repeat-to-escalation latency below 24 hours; 9.9% proxy recurrence halved within two quarters.
- **Kill criterion:** Retire semantic matching if precision stays below 80% after 50 labeled candidates; retain exact-link parsing.
- **First PR:** Exact W-reference lineage and metrics only; no LLM classification; ≤300 lines.

### 4. Doctrine Merkle Reconciler — score 6.7

- **What:** Define canonical doctrine fragments and a manifest of authorized projections. Local receptors compare content hashes and provenance across repository and approved HOME copies; CI validates repository projections. Drift becomes an event with age, owner, and remediation path.
- **Why it beats surveyed SOTA:** Ordinary docs-as-code detects repository drift. This composes generated doctrine, workstation-local projections, provenance, and operational freshness without placing HOME state or secrets in CI.
- **Asymmetry exploited:** Always-on local nodes, hooks-as-backstop, and the public repository as a forcing function.
- **Cost:** 8–14 hours; <100k flat-subscription tokens.
- **Gear:** 3 because it changes doctrine governance.
- **Risk:** Reconciler itself forks—family #1—or races sibling sessions, family #5.
- **Metric:** Verified drift age from the recorded 23 days to <10 minutes; zero unregistered projections; hash false alarms <1/week.
- **Kill criterion:** Stop automatic reconciliation if it ever overwrites a non-generated section or cannot distinguish canonical from local-only content.
- **First PR:** Repository manifest and read-only linter; HOME mutation is explicitly excluded; ≤300 lines.

### 5. Before-Action Learning Packet — score 5.3

- **What:** The learning loop produces a ≤2 KB packet containing the three most relevant superscar families, executable gates, unresolved recidiva, and one falsification question for a new mandate. Lane 2 may decide how to inject it; this lane owns its evidence and quality.
- **Why it beats surveyed SOTA:** Army before-action reports retrieve past operations; Voyager retrieves skills. This packet adds unresolved control state and a falsification challenge, preventing prose-only scars from masquerading as safety.
- **Asymmetry exploited:** Structured scars, task specifications, local retrieval, and full-session ownership.
- **Cost:** 8–12 hours; 50k–150k flat-subscription evaluation tokens.
- **Gear:** 2 for packet generation, 3 for mandatory consumption.
- **Risk:** Exists-but-not-consumed, family #2, or excessive context hiding the task.
- **Metric:** Relevant-scar precision ≥80% on a 50-task labeled set; ≥90% of matched recurrences surfaced before merge; packet p95 ≤2 KB.
- **Kill criterion:** Drop semantic retrieval if consultation is below 70% or if no recurrence reduction appears after 30 genuinely matched tasks.
- **First PR:** Offline packet builder with fixture tasks; no SessionStart or workflow integration; ≤380 lines.

### 6. Evidence-Gated Skill Promotion — score 3.0

- **What:** Promote a skill only after three independent successful uses, one adversarial failure probe, a regression fixture, and a measurable improvement over the no-skill baseline. Link every promoted skill to scars or successful trajectories and provide decay/retirement evidence.
- **Why it beats surveyed SOTA:** Voyager promotes working code; Nuzantara’s documented registry adds tiers and decay. The new composition adds independent refutation, counterfactual baseline, and production authority boundaries.
- **Asymmetry exploited:** Multiple LLM families as builder/refuter/verifier, flat subscriptions, existing skill catalog, and operator approval.
- **Cost:** 16–24 hours; 250k–500k flat-subscription tokens over the first month.
- **Gear:** 3.
- **Risk:** Dormant machinery, family #2, or conflicting skill SSOT, family #10.
- **Metric:** At least one verified reuse per week; promoted-skill task success ≥15 percentage points above no-skill baseline; 100% promotion-regression pass rate.
- **Kill criterion:** Do not promote if a skill cannot produce three comparable trials or if its benefit confidence interval includes zero after ten uses.
- **First PR:** Propose-only evidence report for existing skills; no automatic promotion; ≤390 lines.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 0–30: make learning state observable

Establish one schema, current measurements, and drift visibility. Do not make any new check required yet.

| First PR | Files | Net-line ceiling | Gear | Acceptance test |
|---|---|---:|---:|---|
| `feat(cicatrix): define scar lifecycle schema` | New `infra/scar-gates/scar-lifecycle.schema.json`, new `scripts/lint_scar_lifecycle.py`, new `scripts/tests/test_scar_lifecycle.py` | 380 | 2 | Valid fixture passes; missing ID, invalid state transition, duplicate W-number, and false executable path each fail independently. |
| `feat(cicatrix): emit recurrence and closure metrics` | New `scripts/scar_metrics.py`, new `scripts/tests/test_scar_metrics.py` | 300 | 2 | Fixture reproduces 3.0% armed baseline and computes exact recidiva edges without double-counting suffix headings. |
| `fix(doctrine): detect projection drift by provenance hash` | New `infra/doctrine-copies.json`, new `scripts/lint_doctrine_drift.py`, new `scripts/tests/test_doctrine_drift.py` | 320 | 3 | Canonical copy passes; stale, unknown, and locally extended projections receive distinct diagnoses; no file is modified. |

Wave exit criteria: ≥98% schema accuracy on 30 scars; a reproducible current baseline; no hidden reliance on HOME paths in CI; all tooling local and PII-free.

### Wave 2 — Days 31–60: prove the antibodies

Convert the two highest-recurrence families first, then observe rather than declaring victory.

| First PR | Files | Net-line ceiling | Gear | Acceptance test |
|---|---|---:|---:|---|
| `test(cicatrix): add counterfactual antibody harness` | New `infra/scar-gates/antibody_contract.py`, new `scripts/tests/test_antibody_contract.py` | 350 | 3 | Guilt fails before control, passes after control; innocence passes both; disabling the control reopens guilt. |
| `test(cicatrix): bind correction integrity to W113` | New fixture beneath `infra/scar-gates/`, update `infra/scar-gates/MANIFEST.json` through its generator | 300 | 3 | A retracted claim outside the marker-only registry fails; legitimate historical reference remains allowed. |
| `chore(cicatrix): publish shadow effectiveness report` | `.github/workflows/check-cicatrix-scar-pointers.yml`, new deterministic report script and tests | 250 | 2 | Workflow emits coverage, mutation, innocence, and recurrence metrics but cannot block or mutate doctrine. |

Wave exit criteria: ≥95% mutation kill, <2% innocence false positives, and at least two families observed for 30 days. Only then may Zero consider required-check promotion.

### Wave 3 — Days 61–90: pull learning into future work

| First PR | Files | Net-line ceiling | Gear | Acceptance test |
|---|---|---:|---:|---|
| `feat(learning): build before-action evidence packets` | New `scripts/build_before_action_packet.py`, new fixture tests, `docs/EXPERIENCE_LIBRARY_OPS.md` | 380 | 2 | Top-three precision ≥80% on 50 redacted synthetic task/scar pairs; output ≤2 KB and contains no raw incident body. |
| `feat(skills): propose evidence-gated promotions` | New `scripts/propose_skill_promotion.py`, new tests, `docs/SKILL_REGISTRY_OPS.md`, `.claude/skills/skill-catalog/SKILL.md` | 390 | 3 | Fewer than three independent successes or missing adversarial probe always produces `NOT_ELIGIBLE`; tool never edits a skill. |
| `docs(modus): expose learning-loop effectiveness SLO` | `.claude/skills/modus/SKILL.md`, `.claude/skills/modus/AMENDMENTS.md` | 180 | 3 | Doctrine names source, formula, observation window, kill criterion, and operator gate for every claimed improvement. |

Day-90 outcome: at least 70% high-severity scar coverage in a terminal or explicitly waived lifecycle state; current recidiva reported without prose grep; drift detected within ten minutes; at least one independently verified skill reuse per week.

## 7. Needs-ruling

1. **Required-check authority:** Zero must decide whether and when the lifecycle and antibody checks become branch-protection requirements. The technical threshold proposed is 30 shadow days, <2% false positives, and ≤90 seconds median overhead.
2. **Reliability capacity:** Closing scar actions competes with product work. Zero must approve a fixed capacity allocation or a policy such as “one high-severity antibody before the next feature wave.”
3. **Doctrine projection policy:** Normalizing or replacing HOME `CLAUDE.md` copies requires access outside this snapshot and changes workstation behavior. Zero must approve the canonical/generated/local-only boundary before any mutation.
4. **Scar publication and retention:** Because the repository is public, Zero must rule on whether operational scars remain public in full, become redacted structured records, or split into public antibodies and private incident evidence.
5. **Fable use:** No recommendation auto-routes Fable. If Zero wants a quarterly Fable learning audit, it must remain an explicit manual selection.

## 8. §Meta-pattern

The single defective belief is:

> A lesson has been learned when it has been written, compressed, or approved.

That belief generates nearly every gap. It turns scars into inventory, AMENDMENTS into activity, a skill catalog into capability, a named script into an armed control, and a memory corpus into organizational recall. NASA’s underused LLIS is the institutional version of the same error; Nuzantara’s 2/66 gate census is its local expression.

A trauma becomes a durable antibody only when five independent facts are true:

1. the event is captured without blame or sensitive data;
2. the mechanism is classified and linked to prior recurrence;
3. the antidote is executable and counterfactually tested;
4. it is armed in the real decision path;
5. recurrence or task-performance measurements improve during a declared observation window.

Nuzantara is already exceptional at facts 1–3 in its best scars. The beyond-SOTA move is to make facts 4–5 first-class, machine-readable states—and to let ineffective antibodies become new scars instead of silently remaining doctrine.

## 9. Sources

1. [Google SRE Workbook — Postmortem Culture](https://sre.google/workbook/postmortem-culture/), 2018; accessed 2026-08-29. Primary Google guidance on blamelessness, tracked actions, ownership, measurable completion, and closure incentives.
2. [PagerDuty Incident Response — Postmortem Process](https://response.pagerduty.com/after/post_mortem_process/), live documentation; accessed 2026-08-29. Primary public incident-response operating procedure.
3. [NASA APPEL — Lessons Learned](https://www.nasa.gov/learning-resources/for-professionals/appel-lessons-learned/), 2026; accessed 2026-08-29. NASA’s current official collect/record/share/apply lifecycle.
4. [NASA OIG Report IG-12-012](https://oig.nasa.gov/docs/IG-12-012.pdf), 2012; accessed 2026-08-29. Independent primary audit showing how a formal lessons repository became underused and stale.
5. [NASA ASRS — Immunity Policies](https://asrs.arc.nasa.gov/overview/immunity.html), live policy; accessed 2026-08-29. Official design for confidential, de-identified, non-punitive incident reporting.
6. [U.S. Army — Commander’s Guide for Driving Change](https://api.army.mil/e2/c/downloads/2023/01/31/99194b3d/commanders-guide-for-driving-change-the-learning-organization-framework-jan-19-public.pdf), 2019; accessed 2026-08-29. Primary description of immediate AARs and before-action reports.
7. [Toyota — A Swift Response](https://www.toyota-global.com/company/history_of_toyota/75years/text/entering_the_automotive_business/chapter2/section1/item2.html), official historical archive; accessed 2026-08-29. Primary account of converting defects into poka-yoke and critical-process controls.
8. [Open Policy Agent — Policy Testing](https://www.openpolicyagent.org/docs/policy-testing), live documentation; accessed 2026-08-29. Primary policy-as-code and positive/negative test mechanism.
9. [Semgrep — Rule Ideas](https://docs.semgrep.dev/writing-rules/rule-ideas), updated 2025-10-15; accessed 2026-08-29. Primary guidance for compiling postmortem and review knowledge into automated repository rules.
10. [Shinn et al. — Reflexion](https://arxiv.org/abs/2303.11366), revised 2023-10-10; accessed 2026-08-29. Primary research on learning from linguistic feedback through episodic agent memory.
11. [Wang et al. — Voyager](https://voyager.minedojo.org/), 2023; accessed 2026-08-29. Primary research and measured results for executable, retrievable, compositional skill libraries.
12. [Anthropic — Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), 2025-09-29; accessed 2026-08-29. Primary agent-engineering guidance on cyclic refinement and finite context budgets.

Per the lane’s final-message-only and read-only instructions, this report was not written to the repository; therefore no output-file `ls -la` or `wc -w` claim is made.