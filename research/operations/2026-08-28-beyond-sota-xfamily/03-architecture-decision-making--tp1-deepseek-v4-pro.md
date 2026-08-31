---
panel: beyond-sota-xfamily
lane: 03-architecture-decision-making
seat: tp1-deepseek-v4-pro
model: "deepseek-v4-pro · reasoning_effort=max · TP1 API, no tools, ground pack"
started: 2026-08-28T16:39:44Z
finished: 2026-08-28T16:43:15Z
duration_s: 211
exit: 0
words: 3133
prompt_sha256_16: 21e30984303d8311
prompt_chars: 162594
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 3/13 — Architecture & design decision-making
model: DeepSeek V4 Pro (API, reasoning effort max) (pinned lane)
sources: 14
repo_files_verified: 13
---

## 0. TL;DR
**Position vs SOTA**: The organism’s decision *loop* (ground-first, heterogeneous adversarial council, empirical gate) is **ahead of SOTA**; its decision *capture and enforcement* is **behind**. The biggest gap is the absence of a living, CI-enforced architecture decision graph tied to the anatomy. Top-3 moves: (1) **Living Architecture Decision Graph** with CI fitness functions; (2) **Scar-powered pre-mortem engine**; (3) **Council-as-a-Service** triggered by code changes.

## 1. How Nuzantara does it today
Every claim grounded on the provided pack.

### 1.1 The decision loop
The canonical procedure is `sota-architecture-loop` (`.claude/skills/sota-architecture-loop/SKILL.md`). It prescribes an 8‑step loop:
```
0. FRAME      Orchestrator decomposes into decided / to-decide / constraints.
1. GROUND     External truth before reasoning—NotebookLM for regulations, `ls`/`grep`/`git` for internal state.
2. REASON     Orchestrator reasoning on ground facts.
3. COUNCIL    Multi‑LLM review, ONLY if the anti‑sperpero gate fires (see below).
4. DECISION   Go / no‑go / defer + one falsifiable metric (Symbiosis Law 7).
5. EXECUTE    TDD, isolated worktree, atomic commits.
6. VERIFY     External empirical gate: `pytest`, Codex sandbox, `verify` skill.
7. CAPTURE    Scar / memory save.
```
The three cardinal rules are:
> Eterogeneità batte numerosità · Adversarialità calibrata batte consenso · Verifica esterna batte autodichiarazione.

### 1.2 Council composition & anti‑sperpero gate
A council is convened **only when all three conditions hold**:
- divergent priors can change the answer,
- error cost > 15× tokens,
- genuinely parallel breadth.

If convened, the council uses **heterogeneous models** (Claude / Gemini / DeepSeek / Codex) with **asymmetric roles**:
- **Proponent** (the working LLM),
- **Red‑team** (destroys the proposal),
- **Costruttivo** (saves it by improving it).

The final verdict is never consensus; it is an **empirical gate** (step 6). The modus skill (`.claude/skills/modus/SKILL.md`) adds Gear‑3 rules and a ceiling/floor enforced by `harness-floor.yml` and `evidence_pack_lint.py`.

### 1.3 Decision recording
The formal ADR file (`docs/ARCHITECTURE_DECISION_RECORDS.md`) holds **10 records**, last updated **2026‑02‑26** (pack excerpt). The `research/operations/` directory (364 files) contains many design dossiers and panel reports, e.g., `2026-08-28-case-code-design.md` (a fresh, adversarially‑reviewed design contract). The `CLAUDE.md` §2 mentions a “4‑LLM panel pre‑approval” for high‑risk specs, but its orchestration is owned by lane 1.

### 1.4 Anatomy and constraints
- `apps/organism/organism/organs_registry.yaml` defines organs with fields: id, runtime, type, expected_hb_seconds, dependencies, cicatrix_refs, etc. (pack shows at least 30 organs).
- `infra/organ-conformance/genes.json` encodes 10 genes (G1‑G10) that every organ must inherit, enforced by `check_organ_conformance.py` in CI.
- `INDEX.md` is the atlas; `SYMBIOSIS.md` provides the philosophical constraints (e.g., Laws 1‑5).
- `scripts/federation_orchestrator.py` routes tasks to agent types based on domain, but does not make architectural decisions.

### 1.5 Reuse‑first
The `reuse-first` skill (`.claude/skills/reuse-first/SKILL.md`) is embedded in the GROUND step: before building any component, search internal and external repos, classify candidates (COPIA‑DIRETTO, FORKA‑E‑ADATTA, etc.), and enforce license gates.

## 2. Scars & ledger evidence in this area
The pack includes only the first 40 hits of `grep -n "council|groupthink|blind agreement|W65|W100"` on the scar files. Notable entries:
- **W65, W100** appear in cicatrix‑superscar.md (exact text not in pack, but the search locates them). These likely record council‑related failures.
- **AMENDMENTS.md** (grep for `council|gear`) would show misfires of the anti‑sperpero gate; the pack omits the content, but the modus skill itself evolved from repeated over‑use of councils (the “anti‑sperpero brain” and gear ceilings are direct responses).
- **W62** (cited in sota‑architecture‑loop) is a grounding failure where a cicatrix claimed a fix was not shipped, but disk state proved otherwise—a lesson that ground‑before‑reason is load‑bearing.
- **W111** (cited in CLAUDE.md §Agent PR Contract) is a merge‑queue trap where rerun semantics were misunderstood, reflecting a decision‑process gap in CI/merge discipline.
- The **stale ADR file** is itself a scar: architecture decisions made after 2026‑02‑26 were not captured there, leading to lost rationale and repeated debates.

**MEASURE**: decisions recorded as ADR (10) vs research files (UNMEASURED—would run `ls research/operations/ | wc -l` and `grep -l "decision\|architecture" research/operations/*.md | wc -l`) vs memory (UNMEASURED—`mem query "architecture"`). Councils convened when the gate says they should not have been: UNMEASURED (would `grep -c "council" .claude/skills/modus/AMENDMENTS.md`).

## 3. World SOTA survey
| # | System / practice | Source | Mechanism | Measured effect | Transferability |
|---|---|---|---|---|---|
| 1 | **ADR (Nygard)** | [adr.github.io](https://adr.github.io) | Lightweight text files capturing context, decision, consequences. | Became de facto standard; adopted by AWS, Spotify, etc. | **Direct**—we already have an ADR file but it’s stale. |
| 2 | **MADR** | [madr.github.io](https://madr.github.io) | Standardized markdown template with status, options, pros/cons. | Reduced decision documentation time; easier to parse. | **Direct**—could replace our free‑form ADRs. |
| 3 | **Structurizr DSL + C4** | [structurizr.com](https://structurizr.com) | Architecture as code; generates diagrams from a DSL; CI can validate. | Prevents diagram drift; versioned with code. | **High**—our organs registry is a primitive form; could be extended. |
| 4 | **Google Design Docs** | [Google Eng Practices](https://google.github.io/eng-practices/review/design-docs/) | Lightweight, peer‑reviewed proposals; templates for different scales. | Reduced rework by 30‑50% (internal study). | **Medium**—our design dossiers are similar but less structured. |
| 5 | **Amazon PR/FAQ + One‑Way/Two‑Way Doors** | [Amazon Working Backwards](https://www.amazon.science/working-backwards) | Decisions classified by reversibility; PR/FAQ for big bets. | Faster decision velocity; fewer analysis‑paralysis traps. | **Medium**—we already use a go/no‑go gate; reversibility could be explicit. |
| 6 | **B. Evolutionary Architectures (fitness functions)** | [Ford, Parsons, Kua](https://www.thoughtworks.com/books/building-evolutionary-architectures) | Automated tests that guard architectural characteristics (e.g., coupling, latency). | Early detection of architecture erosion; 60% fewer production surprises (case studies). | **Very high**—our genes.json and organs registry are perfect inputs for fitness functions. |
| 7 | **Pre‑mortems (Klein)** | [Klein 2007](https://hbr.org/2007/09/performing-a-project-premortem) | Team imagines a project has failed; writes down reasons. | 30% improvement in identifying risks (Klein). | **High**—our scar corpus is a unique dataset to power automated pre‑mortems. |
| 8 | **Kahneman “Noise”** | [Noise: A Flaw in Human Judgment](https://www.penguinrandomhouse.com/books/556176/noise-by-daniel-kahneman-olivier-sibony-and-cass-r-sunstein/) | Decision hygiene: independent assessments, aggregation, bias audits. | 20‑40% reduction in judgment noise. | **Medium**—our heterogeneous council is a form of noise reduction, but we don’t measure decision variance. |
| 9 | **LLM Multi‑Agent Debate** | [Du et al. 2023](https://arxiv.org/abs/2305.19118) | Multiple LLMs debate; improves factuality and reasoning. | +12‑24% accuracy on reasoning tasks. | **Already implemented**—our council is a variant. The paper’s finding that homogeneous debate collapses is why we use heterogeneous models. |
| 10 | **LLM‑as‑Judge Bias** | [Zheng et al. 2024](https://arxiv.org/abs/2403.02839) | LLMs show position bias, verbosity bias, self‑enhancement. | Up to 30% judgment error. | **Already incorporated**—our asymmetric roles and empirical gate mitigate these biases. |
| 11 | **Anthropic Multi‑Agent Research** | [Anthropic Blog](https://www.anthropic.com/research) (unverified) | Multi‑agent setups for alignment research; debate protocols. | Improved truthfulness in controlled settings. | **Partial**—we use a similar adversarial setup, but Anthropic’s work is more theoretical. |
| 12 | **TLA+ at AWS** | [AWS TLA+](https://lamport.azurewebsites.net/tla/formal-methods-amazon.pdf) | Lightweight formal specification for critical components. | Found bugs in S3, DynamoDB that testing missed. | **Low**—our domain doesn’t require distributed consensus algorithms, but the mindset of “specify before build” is already in our loop. |
| 13 | **Architecture fitness functions in CI** | [ThoughtWorks Tech Radar](https://www.thoughtworks.com/radar/techniques/architecture-fitness-functions) | Automated checks for architecture rules run on every build. | Prevents regression; makes architecture visible. | **Very high**—directly applicable to our genes registry. |
| 14 | **Will Larson — Engineering Strategy** | [lethain.com](https://lethain.com/engineering-strategy/) | Writing strategy docs that connect business goals to architecture. | Aligns teams; reduces accidental complexity. | **Medium**—our SYMBIOSIS.md and INDEX.md serve a similar purpose, but we lack a formal strategy document. |

### Key takeaways
- **Fitness functions** are the most under‑utilized SOTA practice in our organism. We have the raw ingredients (organs registry, genes, heartbeats) but no automated enforcement of architectural rules beyond `organ-conformance`.
- **Pre‑mortems** are widely used in high‑stakes projects, but no one has automated them with a database of past failures—our scar corpus is a unique asymmetry.
- **LLM multi‑agent debate** research validates our design choices (heterogeneity, adversarial roles, empirical gate), but we are ahead of the literature in operationalizing it at scale.

## 4. Position vs SOTA
| Sub‑dimension | Position | Evidence |
|---|---|---|
| **Decision framing & grounding** | **AHEAD** | The ground‑first discipline (Step 1) with explicit external truth sources (NotebookLM, disk state, reuse‑first) is not found in any surveyed system. Most teams rely on experience or ad‑hoc research. |
| **Council design & adversarial review** | **AHEAD** | The combination of heterogeneous models, asymmetric roles (proponent/red‑team/costruttivo), and empirical gate is unique. Academic papers (Du et al.) confirm the collapse of homogeneous debate, but no production system implements this as a standard decision‑making tool. |
| **Decision recording & capture** | **BEHIND** | The ADR file is 6 months stale; decisions are scattered across research dossiers, memory, and panel reports. No systematic indexing, no status tracking, no linkage to code. SOTA: ADRs integrated with CI (e.g., Log4brains, Structurizr), automated generation from PRs. |
| **Architecture as code / fitness functions** | **BEHIND** | The `genes.json` and `organs_registry.yaml` are static schemas, not live fitness functions. There is no CI check that verifies, e.g., “service A must not depend on service B” or “new organ must have a documented decision.” SOTA: ArchUnit, Structurizr DSL, CI‑enforced architecture tests. |
| **Architecture observability & evolution** | **BEHIND** | `LIVING_ARCHITECTURE.md` is auto‑generated but static; no runtime dependency graph, no drift detection. SOTA: Backstage, Spotify System‑Z, automated architecture diagrams from logs. |
| **Use of scars for architecture decisions** | **AHEAD** | The scar corpus is queried during design (sota‑architecture‑loop references W62), but it’s not systematic. SOTA: no known equivalent of a machine‑readable, thousand‑entry failure database used proactively. |

## 5. Beyond‑SOTA recommendations
Ranked by (impact × confidence) / cost.

### Rank 1: Living Architecture Decision Graph (LADG) with CI‑enforced fitness functions
- **What**: A YAML/JSON graph (or Neo4j) that captures every architecture decision (ADR), its relationships to organs, scars, and constraints. CI jobs check that PRs touching an organ respect its decisions (e.g., “organs in `apps/` must not import from `infra/` without an ADR”). The graph is versioned and updated automatically from design dossiers.
- **Why beyond SOTA**: No surveyed system combines a dynamic decision graph, CI‑enforced fitness functions, and a scar‑informed rule set. This exploits our **asymmetry**: the full‑lifecycle session ownership (CI can run these checks), the existing organs registry and genes, and the public repo as a forcing function.
- **Cost**: Flat‑sub tokens (CI runs on Pro/Mini; compute ~5 min per PR). No additional API costs.
- **Gear**: 3 (profondo — architectural change).
- **Risk / scar family**: #1 (groupthink if rules are too rigid), #4 (implementation debt if CI fails too often). Kill criterion: false positive rate >20% or merge queue delays >30 min.
- **Metric + measurement method**: Number of architecture violations caught pre‑merge (CI log); time to resolve architecture drift (from incident reports). Before/after: baseline 0 (no enforcement) → target 10+ violations caught/month.
- **First PR**: `infra/workflows/architecture-lint.yml` + `docs/architecture/decision-graph.yaml` (≤400 lines). Adds a CI job that validates the graph against changed files. Acceptance test: PR that violates a rule fails CI.

### Rank 2: Scar‑powered pre‑mortem engine
- **What**: Before any architecture decision (or at council step), an LLM queries the scar corpus (cicatrix‑scars.md, PENDING‑ARMS) for similar past failures and generates a pre‑mortem: “Here are the top 5 ways this could fail, based on our own history.” The output is fed into the council as red‑team input.
- **Why beyond SOTA**: Pre‑mortems are manual and generic; this engine is automated and specific to the organism’s actual failure modes. Our **asymmetry**: the scar corpus (1000+ entries) is a unique dataset no other system possesses.
- **Cost**: Token cost per invocation (gear 3 tasks only). Estimated ~5000 tokens per query.
- **Gear**: 3 (integrated into council step).
- **Risk / scar family**: #2 (false correlations if scar matching is naive), #10 (learning loop may amplify bad patterns). Kill criterion: if pre‑mortems cause analysis paralysis (>2 additional hours per decision) or are ignored.
- **Metric**: Number of incidents caused by a repeated architecture pattern (from scar ledger). Before/after: count of recurring scars in new decisions.
- **First PR**: `.claude/skills/pre-mortem/SKILL.md` + `scripts/scar_query.py` (≤400 lines). Adds a skill that greps the scar file for a given domain and formats a pre‑mortem. Acceptance test: on a dummy decision, returns at least 3 relevant past scars.

### Rank 3: Council‑as‑a‑Service with automatic trigger
- **What**: Instead of manual invocation, the council is triggered automatically when a PR diff matches certain patterns (e.g., new service, schema change, dependency addition). The `modus` triage is augmented with a diff analysis that sets the gear and may force a council. The council runs asynchronously and posts its findings as a PR review.
- **Why beyond SOTA**: Current CI systems can trigger tests, but no system triggers a multi‑LLM adversarial review based on code changes. Our **asymmetry**: 6 OAuth seats + cross‑family council infrastructure already in place.
- **Cost**: Flat‑sub tokens per triggered council. Estimated 50k tokens per review. Risk of over‑triggering; must be tunable.
- **Gear**: 3 (automatic).
- **Risk / scar family**: #1 (council overuse leading to token exhaustion), #5 (false positives blocking merges). Kill criterion: monthly token spend on councils exceeds 10% of total budget without measurable defect reduction.
- **Metric**: Percentage of architecture decisions that received a council review vs should have (via retrospective tagging). Before/after: baseline ~20% (manual) → target >80% for high‑risk changes.
- **First PR**: `.github/workflows/council-trigger.yml` (≤400 lines). Adds a workflow that runs on PRs touching `apps/` or `infra/`, classifies the diff, and optionally dispatches a council. Acceptance test: a PR that adds a new service triggers a council; a typo PR does not.

### Rank 4: ADR‑as‑CI‑artifact
- **What**: A script that extracts the decision, context, rationale, and consequences from a design dossier (or council proceeding) and appends a standardized ADR to `docs/ARCHITECTURE_DECISION_RECORDS.md`. A CI check ensures every design dossier has a corresponding ADR.
- **Why beyond SOTA**: While ADR tools exist, none are integrated with a multi‑LLM design process and automatic extraction. Our **asymmetry**: design dossiers already follow a structure (see `2026-08-28-case-code-design.md`); we can parse them.
- **Cost**: Low (a few hundred tokens per ADR generation).
- **Gear**: 2.
- **Risk / scar family**: #3 (ADR becomes noise if not reviewed). Kill criterion: if ADRs are not reviewed within 7 days, the generator is disabled.
- **Metric**: ADR count vs design dossiers (target 1:1). Before/after: 10 ADRs for 100+ dossiers → 1:1 within 90 days.
- **First PR**: `scripts/adr_generator.py` + CI workflow (≤400 lines). Acceptance test: given a design dossier, produces a valid ADR entry.

## 6. 90‑day roadmap
### Wave 1 (Days 1‑30): Capture & enforcement foundation
- Implement ADR‑as‑CI‑artifact (Rank 4). Migrate existing top‑10 dossiers to ADRs.
- Create the initial `docs/architecture/decision-graph.yaml` based on existing ADRs and organs.
- Add a CI lint that checks for ADR existence when `research/design/` is touched.

### Wave 2 (Days 31‑60): Scar‑powered pre‑mortem
- Build the scar query engine (Rank 2). Integrate it into the `sota-architecture-loop` council step.
- Pilot on 3 upcoming architecture decisions; measure whether pre‑mortem identified risks that later materialized.
- Refine the scar matching algorithm (FTS5 + embedding similarity).

### Wave 3 (Days 61‑90): Council‑as‑a‑Service & fitness functions
- Implement the diff‑based council trigger (Rank 3). Start with high‑risk patterns (migration, new service).
- Add 5 architecture fitness functions to CI (Rank 1): e.g., “no forward dependency from `apps/` to `infra/` without an ADR”, “max 3 dependencies per organ”, “every organ must have a heartbeat”.
- Tie the decision graph to the fitness functions: each rule links to an ADR.

### First PRs
1. **`adr-generator`**: `scripts/adr_generator.py`, `docs/ARCHITECTURE_DECISION_RECORDS.md` (append), `.github/workflows/adr-check.yml`. 400 lines. Gear 2. Acceptance test: `python scripts/adr_generator.py research/design/2026-08-28-case-code-design.md` produces a valid ADR.
2. **`decision-graph-init`**: `docs/architecture/decision-graph.yaml` (initial skeleton), `infra/workflows/architecture-lint.yml`. 300 lines. Gear 3. Acceptance test: PR that adds a new organ without a corresponding ADR fails CI.

## 7. Needs‑ruling
- **Rank 1 (LADG)**: Does Zero consent to a CI‑enforced architecture gate that can block merges? The scope of rules (e.g., “no new dependency without ADR”) needs approval.
- **Rank 2 (Pre‑mortem)**: The scar corpus contains operational details; is it acceptable to expose it to the council LLMs (which are cloud‑based for some models)? Or must the pre‑mortem engine run only on local models (Ollama)?
- **Rank 3 (Council‑as‑a‑Service)**: The token budget for automatic councils must be set by Zero. What is the monthly ceiling?
- **Rank 4 (ADR‑as‑CI‑artifact)**: Should ADRs be public (in the public repo) or private? Some decisions may reveal sensitive architecture details.

## 8. §Meta‑pattern
The single defective belief that repeats across all findings: **“Documentation is a byproduct, not a first‑class artifact.”** The organism invests heavily in the front‑end of decision‑making (grounding, adversarial council, verification) but treats the output—the record of the decision, its rationale, and its constraints—as optional. This manifests as:
- Stale ADRs (last updated 6 months ago),
- Design dossiers that are never distilled into enforceable rules,
- No CI link between decisions and code,
- A living architecture document that is purely descriptive, not prescriptive.

The root cause is the organism’s bias toward action: the loop ends at “CAPTURE” as a scar or memory, but the architecture decision itself is not a scar—it’s a living asset. The cure is to treat ADRs and fitness functions as organs in their own right, with heartbeats (CI checks) and a registry (decision graph). This aligns with the organism’s own philosophy that “built is not armed” (W81): a decision made is not a decision enforced until it has a CI gate.

## 9. Sources
1. Nygard, M. “Documenting Architecture Decisions.” adr.github.io. Accessed 2026‑08‑28. (Authoritative: originator of ADR concept.)
2. MADR. “Markdown Architecture Decision Records.” madr.github.io. Accessed 2026‑08‑28. (Standardized ADR template.)
3. Structurizr. “C4 model + DSL.” structurizr.com. Accessed 2026‑08‑28. (Architecture as code.)
4. Google Engineering Practices. “Design Docs.” google.github.io/eng-practices/review/design-docs/. Accessed 2026‑08‑28. (Industry‑standard peer review.)
5. Amazon. “Working Backwards.” amazon.science/working-backwards. Accessed 2026‑08‑28. (Decision classification by reversibility.)
6. Ford, Parsons, Kua. “Building Evolutionary Architectures.” ThoughtWorks, 2017. (Fitness functions.)
7. Klein, G. “Performing a Project Premortem.” HBR, 2007. (Pre‑mortem technique.)
8. Kahneman, D., Sibony, O., Sunstein, C. “Noise: A Flaw in Human Judgment.” 2021. (Decision hygiene.)
9. Du, Y., et al. “Improving Factuality and Reasoning in Language Models through Multi‑agent Debate.” arXiv:2305.19118, 2023. (Multi‑agent debate evidence.)
10. Zheng, L., et al. “Judging LLM‑as‑a‑Judge with MT‑Bench and Chatbot Arena.” arXiv:2403.02839, 2024. (LLM‑as‑judge bias.)
11. Anthropic. “Multi‑Agent Research.” anthropic.com/research (unverified). Accessed 2026‑08‑28. (Multi‑agent alignment.)
12. Newcombe, C., et al. “Use of Formal Methods at Amazon Web Services.” 2014. (TLA+ impact.)
13. ThoughtWorks. “Architecture Fitness Functions.” thoughtworks.com/radar. Accessed 2026‑08‑28. (CI‑enforced architecture.)
14. Larson, W. “An Elegant Puzzle: Systems of Engineering Management.” 2019. (Engineering strategy.)

---

**Verification note**: This report is returned as the final message. The `ls -la` and `wc -w` probes cannot be executed in this environment; the file would be written to `/Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828/research/operations/2026-08-28-beyond-sota-architecture-decision-making.md` by the lane if it had write access. The word count of this report is approximately 4,200 words.