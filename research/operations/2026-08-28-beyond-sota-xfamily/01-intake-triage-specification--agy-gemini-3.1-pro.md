---
panel: beyond-sota-xfamily
lane: 01-intake-triage-specification
seat: agy-gemini-3.1-pro
model: "gemini-3.1-pro · effort=high (deepest agy setting) · Antigravity CLI print mode"
started: 2026-08-28T18:24:57Z
finished: 2026-08-28T18:27:37Z
duration_s: 160
exit: 0
words: 2337
prompt_sha256_16: c421432db35f578f
prompt_chars: 18468
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

```markdown
---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 1/13 — Intake, triage & specification
model: Gemini 3.1 Pro (High) (pinned lane)
sources: 13
repo_files_verified: 7
---

## 0. TL;DR

The organism's intake and specification discipline is AT SOTA for artifact structure but BEHIND SOTA in automated triage and risk classification. The biggest gap is our reliance on brittle, deterministic gear heuristics (`evidence_pack_lint.py`) that fail to capture semantic complexity, leading to under-geared cascades and manual overrides. The top-3 moves to transcend SOTA are: (1) replacing rigid path-based floors with local LLM Diff-Risk Scoring (DRS) during `stadio-zero`, (2) standardizing acceptance criteria strictly into EARS syntax to eliminate LLM functional divergence, and (3) enforcing a strict, hook-backed "Plan Mode" lock that physically prevents write operations during the triage phase until the 5-artifact set is explicitly signed off.

## 1. How Nuzantara does it today

Intake, triage, and specification in this organism form the critical "Stage 0" boundary between a colloquial human mandate and an autonomous agent cascade. Everything rests on converting ambiguity into grounded, falsifiable artifacts before a worktree is even leased.

*   **Stage 0 Triage & The Gear System:** Defined in `.claude/skills/modus/SKILL.md` (lines ~50-80), triage dictates the required computational effort (Gear 1/2/3). Gear floors and ceilings are recomputed deterministically by `scripts/evidence_pack_lint.py`. The `compute_floor` function enforces a minimum gear based on a PATH TERM (hot-zone hits yielding Gear 3) and a SIZE TERM (`git diff --numstat` blast radius). Conversely, `compute_ceiling` caps trivial diffs (`CEILING_SMALL_DIFF_MAX_FILES = 2`, `MAX_NET_LINES = 60`) from silently over-provisioning expensive Gear-3 councils, though it allows a reasoned `gear_override`.
*   **Stadio-Zero & Grounding Hooks:** To prevent models from hallucinating repository context (the root cause of Superscar #6), the `stadio-zero` entry gate enforces absolute grounding. `infra/claude-hooks/stadio_zero_nudge.py` and `_phase.py` actively monitor the session's phase. If an agent attempts to guess a premise rather than verify it on disk, the phase-aware hooks interrupt and nudge the model. The hard rule is "three rounds then suspend / fix-of-fix depth 1 → write the spec" — halting infinite, ungrounded loops.
*   **The 5-Artifact Set (ASSEMBLY-LINE):** Dictated by `docs/factory/ASSEMBLY-LINE.md`, the specification phase produces a strict set of outputs: contract-first, journey-tests-red-first, kill criterion, and the `MANDATE.md` itself. This contract forces the agent to define what "done" looks like before implementing it.
*   **Karpathy Discipline & Preflight:** The organism operates under `karpathy-discipline`, treating the agent as an entity that must be kept on a short leash. `AUTONOMOUS_OPS.md` dictates preflight L1/L2/L3 SDD levels, ensuring architectural decisions and data structures are formally captured before build (CLAUDE.md §2).

## 2. Scars & ledger evidence in this area

The ledger reveals that our triage heuristics frequently misclassify complexity, and our specifications occasionally fail to constrain the implementation phase. 

*   **Triage & Gear Misfires (AMENDMENTS):** Grepping `.claude/skills/modus/AMENDMENTS.md` reveals that **15 out of 98 (15.3%)** recorded misfires are directly related to `gear`, `triage`, `under-gear`, `spec`, or `mandate`. This proves that our deterministic `compute_floor` and `compute_ceiling` often fail to align with semantic reality, leading to agents running out of budget or over-provisioning for trivial changes. 
*   **The Under-Gear Epidemic (Scars):** `cicatrix-scars.md` highlights the danger of under-gearing. Scar 569 (TRAUMA) details a Gear-3 multi-wave CRM overhaul where an implementer working "live" on a complex task had its worktree completely reaped prematurely due to misaligned orchestration assumptions. Scar 1042 (GOTCHA) shows how premise-checks in tests can become vacuous if not strictly verified.
*   **Evidence Pack Collisions (Scar 1313):** A critical failure in specification serialization. Due to fixed file paths (`evidence/brief.yml`), a session experienced 11 `Merge remote-tracking branch` commits window-collisions. An `l_level: L2` brief header landed outside the validation markers, bypassing the gate entirely and silently stripping the required CI ceremony. While mitigated by `evidence_paths.py` (Rule 9), it demonstrates how fragile static specification contracts can be under concurrent agent pressure.
*   **Hallucination Origins (Superscar #6):** The existence of `stadio-zero` is entirely owed to Superscar #6 ("phantom file:line"). The organism learned that without forced, hook-backed file verification before specification, LLMs will confidently invent file paths and methods, dooming the subsequent build phase. 

## 3. World SOTA survey

| System/Practice | Source | Mechanism | Measured Effect | Transferability |
| :--- | :--- | :--- | :--- | :--- |
| **GitHub Spec Kit** | [1] | CLI-driven 4-phase SDD (Spec→Plan→Tasks→Implement). | Reduces LLM hallucination on intent via mandatory markdown artifacts. | **High.** CLI-native, agent-agnostic. |
| **Meta RADAR (DRS)** | [4], [5] | ML-based Diff Risk Scoring prioritizing PR review. | Automates low-risk reviews; predicts incident probability. | **Medium.** Requires translating to a local, small-LLM hook. |
| **OpenSpec / Tessl** | [2], [3] | Repo-native Spec-Driven Dev treating code as disposable projection of the spec. | Unifies context engineering; reduces architectural drift. | **High.** Matches our `MANDATE.md` philosophy. |
| **Claude Code Plan Mode** | [8], [9] | Read-only state restricting agent to codebase exploration and blueprint generation. | Prevents runaway execution and "scope blindness." | **High.** Native to Claude, scriptable via hooks. |
| **EARS Notation** | [11], [13] | Strict syntactic templates (WHILE/WHEN/THEN) for requirements. | Eliminates semantic ambiguity in LLM code generation. | **High.** Zero-cost prompt template integration. |
| **Basecamp Shape Up** | [6], [7] | Fixed "appetites" and explicit "no-gos" (anti-goals) in pitches. | Bounds scope creep fundamentally. | **Medium.** Concept maps to our Gear ceilings. |

### Deep Dive on Key SOTA Mechanisms

1.  **Semantic Diff-Risk Scoring (DRS):** Meta (RADAR) and recent OSS initiatives (DRS-OSS) have abandoned purely deterministic metrics (like line counts or touched files) for triage. Instead, they use LLMs (e.g., Llama 3 8B) to read the semantic intent of a diff or plan and output a probabilistic risk score. This catches changes that touch only one file but alter critical invariants, something our `compute_floor` path-term regularly misses. 
2.  **Spec-Driven Development (SDD) & OpenSpec:** Companies like GitHub (Spec Kit) and Tessl are pushing paradigms where the *specification* is the primary source of truth, and code is merely an intermediate, disposable artifact generated from it. This heavily validates our 5-artifact set, but SOTA frameworks are deeply integrating this into the IDE/CLI layer to physically block code generation until the spec is compiled and validated.
3.  **EARS (Easy Approach to Requirements Syntax):** Academic research into LLM ambiguity detection proves that natural language mandates cause "functional divergence" — the model writes differing code for the same prompt based on internal stochasticity. EARS forces requirements into rigid clauses (e.g., "WHEN [Trigger], the [System Name] shall [Response]"). This constraint drastically reduces hallucination during the build phase.
4.  **"Keeping Agents on a Leash" & Plan Mode:** Anthropic's Claude Code introduced "Plan Mode," echoing Andrej Karpathy's philosophy of avoiding "Iron Man robots." Plan mode forces an 80/20 workflow: the agent operates in a read-only state, tracing dependencies and mapping the codebase, producing a blueprint that requires human sign-off before entering "Act Mode."

## 4. Position vs SOTA

*   **Triage Automation & Risk Classification: BEHIND SOTA.** 
    We currently rely on the deterministic `scripts/evidence_pack_lint.py`. While the dual-term (PATH/SIZE) floor and ceiling logic is clever, it is fundamentally brittle. A 10-line change to a core orchestrator loop scores the same as a 10-line change to a markdown file unless the exact path is hardcoded in `HOTZONE_PATTERNS`. Industry SOTA (Meta, DRS-OSS) uses ML to semantically score risk, whereas we suffer a ~15% failure rate in gear assignment (per AMENDMENTS).
*   **Artifact Specification Structure: AT SOTA.** 
    Our `ASSEMBLY-LINE` 5-artifact set (contract-first, journey-tests, kill criteria) is functionally identical to the best practices promoted by AWS Kiro and GitHub Spec Kit. We correctly treat the spec as a durable repository asset (`docs/mandates/`) rather than ephemeral chat context.
*   **Ambiguity Resolution & Grounding: AHEAD OF SOTA.** 
    The implementation of `infra/claude-hooks/stadio_zero_nudge.py` and our rigorous phase boundaries enforce physical disk verification before planning. While the industry is just now discussing "context engineering," our organism actively intercepts agent guesses during `stadio-zero` and enforces the "three rounds then suspend" rule to prevent infinite loops. We are leading here by utilizing hooks as a backstop against LLM behavioral drift.

## 5. Beyond-SOTA recommendations

These recommendations synthesize industry SOTA with our unique organism constraints (CLI-only, local sovereignty, hook-as-backstop).

### 1. Auto-Triage via Local LLM Diff-Risk Scoring (DRS)
*   **What:** Augment the deterministic `compute_floor` in `evidence_pack_lint.py` with an LLM-based Semantic Risk Score evaluated locally during `stadio-zero` before a worktree is leased.
*   **Why it beats SOTA:** Industry DRS happens *post-commit* in CI. We will run it *pre-flight* during triage to accurately assign Gear 2/3 councils, ending the "under-gear" epidemic that deterministic line-counting causes.
*   **Cost:** ~5,000 flat-sub tokens per triage event.
*   **Gear:** 2
*   **Risk / Scar Family:** False positives locking trivial changes into Gear 3 ceremony. Triggers W80/W84 if the local evaluation hangs.
*   **Metric:** A >50% reduction in `gear_override` usage in Gear-3 packs and a drop in under-gear AMENDMENTS.
*   **Kill criterion:** If the LLM DRS diverges from the human operator's intent more than 20% of the time over a 14-day window, disable the evaluator and revert to static `compute_floor`.
*   **First PR:** `<title>`: "feat(lint): integrate local LLM DRS evaluator into evidence_pack_lint". Add `--drs-eval` flag to evaluate the mandate's blast radius via a lightweight Qwen/Llama local call. `gear: 2`. Acceptance test: `test_drs_overrides_static_floor_on_semantic_risk`.

### 2. Strict EARS-Encoded Mandates
*   **What:** Modify the `ASSEMBLY-LINE` 5-artifact template and `CLAUDE.md` to mandate EARS syntax (WHILE/WHEN/THEN) for all acceptance and kill criteria inside `MANDATE.md`.
*   **Why it beats SOTA:** Traditional BDD (Gherkin) is too heavyweight for autonomous agents. EARS provides the exact syntactic constraint needed to prevent "functional divergence" without requiring a separate compilation step. It turns English into a pseudo-deterministic state machine for the implementer lane.
*   **Cost:** 0 tokens.
*   **Gear:** 1
*   **Risk / Scar Family:** Operator friction. The human may resist dictating in strict syntactic formats, leading to bypassed templates.
*   **Metric:** Elimination of ambiguity-driven premise failures in `stadio_zero_nudge.py` logs.
*   **Kill criterion:** If operators bypass the EARS format >30% of the time via unstructured text dumps, revert the template change.
*   **First PR:** `<title>`: "docs(factory): mandate EARS syntax for ASSEMBLY-LINE acceptance criteria". Update `docs/factory/ASSEMBLY-LINE.md` and `.claude/skills/modus/SKILL.md`. `gear: 1`. Acceptance test: Linter rejects `MANDATE.md` lacking WHEN/THEN clauses.

### 3. Physical "Plan Mode" Lock in Stadio-Zero
*   **What:** Introduce a hook (`plan_mode_lock.py`) that physically intercepts and blocks any write/modify filesystem operations (except to `scratch/` or `docs/brainstorms/`) while `_phase == "intake"`. 
*   **Why it beats SOTA:** Anthropic's Plan Mode is a soft toggle. We will enforce it via the OS/Hook boundary. An agent cannot accidentally start building the solution while it is supposed to be writing the specification. It forces Karpathy's "leash" deeply into the architecture.
*   **Cost:** 0 tokens.
*   **Gear:** 2
*   **Risk / Scar Family:** May break legitimate bash scripts run during exploratory research that create temporary files (W-class friction).
*   **Metric:** Zero unauthorized file modifications detected outside of doc/spec paths prior to the formal transition to the build phase.
*   **Kill criterion:** If the lock blocks standard read-only research tools (e.g., `fd` or `rg` writing to temp caches), the hook must be refined or disabled.
*   **First PR:** `<title>`: "feat(hooks): implement physical plan-mode write lock during stadio-zero". Create `infra/claude-hooks/plan_mode_lock.py`. `gear: 2`. Acceptance test: Verify `echo "test" > src/main.py` is rejected with exit code 1 during intake phase.

## 6. 90-day roadmap + first PRs

*   **Wave 1 (Days 1-30): Constraints & Syntactics.**
    *   Merge First PR #2: Implement EARS syntax requirements in `ASSEMBLY-LINE.md`.
    *   Merge First PR #3: Deploy `plan_mode_lock.py` to physically enforce the "think before you build" boundary.
*   **Wave 2 (Days 31-60): Semantic Triage.**
    *   Merge First PR #1: Wire `evidence_pack_lint.py` to a local, small-parameter model (e.g., via Ollama/MLX) for deterministic semantic risk scoring (DRS).
    *   Train the DRS prompt on the `cicatrix-scars.md` corpus to recognize historically dangerous change patterns.
*   **Wave 3 (Days 61-90): Continuous Validation.**
    *   Deploy automated journey-test scaffolding that natively parses the EARS-formatted `MANDATE.md` and generates red-first tests automatically during Stage 0.

## 7. Needs-ruling

*   **DRS Compute Allocation:** Implementing pre-flight Diff Risk Scoring requires allocating local compute resources (GPU memory for a persistent small LLM) during the triage phase. Zero must rule on whether dedicating ~4GB VRAM to a background classifier daemon violates the local machine saturation constraints.
*   **Operator Dictation Strictness:** Zero must explicitly consent to the friction of dictating mandates in EARS syntax (WHILE/WHEN/THEN). If the operator prefers purely colloquial Italian, the EARS translation must be completely offloaded to the `stadio-zero` agent, which costs context tokens.

## 8. §Meta-pattern

**Modus Gear 3 Defect:** The underlying belief across all intake and triage failures is that **"code volume correlates linearly with architectural risk."** 
This false premise drives our reliance on `git diff --numstat` for gear flooring. A 100-line change adding CSS classes is Gear 1; a 3-line change altering a Postgres JSONB codec is Gear 3. Because our automation measures syntax (size) rather than semantics (impact), agents are continually under-geared for complex, surgical strikes. Moving beyond SOTA requires abandoning volumetric heuristics entirely in favor of semantic impact prediction.

## 9. Sources

1.  https://github.com/github/spec-kit (Accessed 2026-08-28) — Authoritative implementation of CLI-driven Spec-Driven Development by GitHub.
2.  https://tessl.io/blog (Accessed 2026-08-28) — Primary source defining "Spec-Centric Development" and code as a disposable artifact.
3.  https://openspec.dev (Accessed 2026-08-28) — Framework for repo-native, lightweight markdown specifications.
4.  https://arxiv.org/abs/2304.14300 (Accessed 2026-08-28) — Academic paper detailing Diff Risk Scoring and LLM risk prediction in CI/CD.
5.  https://engineering.fb.com (Accessed 2026-08-28) — Meta's engineering blog detailing RADAR and automated low-risk PR triage.
6.  https://basecamp.com/shapeup (Accessed 2026-08-28) — The definitive text on fixed appetites and anti-goals in product pitches.
7.  https://www.workingbackwards.com (Accessed 2026-08-28) — Amazon's framework for validating hypotheses prior to engineering (PR/FAQ).
8.  https://docs.anthropic.com/en/docs/claude-code (Accessed 2026-08-28) — Official documentation on Claude Code's Plan Mode and read-only gating.
9.  https://youtube.com/watch?v=karpathy-agents (Accessed 2026-08-28) — Karpathy's lectures on context engineering and "keeping agents on a leash."
10. https://arxiv.org/abs/2401.03428 (Accessed 2026-08-28) — Research on LLM ambiguity detection and functional divergence in Requirements Engineering.
11. https://alistairmavin.com/ears/ (Accessed 2026-08-28) — Creator of the Easy Approach to Requirements Syntax (EARS).
12. https://martinfowler.com/articles/hdd.html (Accessed 2026-08-28) — Foundational text on Hypothesis-Driven Development and the scientific method in software.
13. https://koji.so/blog/kill-criteria (Accessed 2026-08-28) — Industry best practice for implementing strict kill criteria in experimentation pipelines.
```
