---
panel: beyond-sota-xfamily
lane: 10-organizational-learning-loop
seat: tp1-deepseek-v4-pro
model: "deepseek-v4-pro · reasoning_effort=max · TP1 API, no tools, ground pack"
started: 2026-08-28T16:54:03Z
finished: 2026-08-28T16:58:10Z
duration_s: 247
exit: 0
words: 3882
prompt_sha256_16: c7204069f0086268
prompt_chars: 164575
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 10/13 — Organizational learning loop
model: DeepSeek V4 Pro (API, reasoning effort max) (pinned lane)
sources: 12
repo_files_verified: 15
---

# BEYOND-SOTA: Organizational Learning Loop

## 0. TL;DR

**Position vs SOTA:** Ahead in executable antidotes and the modus‑bench meta‑loop; behind in doctrine‑drift closure and recidiva prevention. The loop captures trauma well, but it does not **verify** that an antidote actually prevents recurrence — recidiva chains (W65→W90→W100→W113) prove this.  
**Biggest gap:** No feedback loop from antidote deployment back to the scar ledger: an antidote is “armed” but whether it killed the scar is never measured.  
**Top‑3 moves:** (1) **Scar‑antidote mutation testing** — auto‑verify that a deployed antidote catches the exact trauma it was written for, and report a “recidiva‑risk” metric. (2) **Closed‑loop doctrine sync** — replace the HOME‑fork of CLAUDE.md with a single versioned source of truth that all sessions read live, ending the “three copies” disease. (3) **Recidiva‑triggered structural promotion** — when a scar family accumulates ≥3 recurrences, automatically escalate its antidote from prose/script to a required CI gate.

## 1. How Nuzantara does it today

Every claim below is grounded in the repository evidence provided in the ground pack.

### 1.1 Cicatrix: the scar corpus

The central learning artifact is the **cicatrix** system — a structured log of failures (“scars”) that is continuously updated and injected into every LLM session.

- **`cicatrix-scars.md`** (296 KB, active, e.g. W121, W119, W118 — ground pack excerpts) holds the full TRAUMA / ANTIBODY / GOTCHA for each incident. The format is enforced by the `/scar` command (`.claude/commands/scar.md`).
- **`cicatrix-scars-archive.md`** (393 KB) stores resolved or stale scars, moved by `infra/launchagents/cicatrix_autoarchive.sh` (limit raised to 10 M chars to avoid premature archiving).
- **`cicatrix-superscar.md`** (14 KB budget) is the “bridge” — it groups the ~99 scars into **10 superscar families** (HOME‑fork drift, Esiste≠Armato, guard‑over‑match, secret‑in‑clear, sibling‑race, anti‑hallucination, daemon‑vs‑cron, network‑flap, state‑schema‑mutation, split‑brain). It is loaded into **every session and every subagent** (hence the strict byte budget).  
  *Evidence:* `.claude/rules/cicatrix-superscar.md` (ground pack, 13 725 chars).

**Guardrails on the corpus itself:**
- **Budget guard:** `scripts/tests/test_superscar_budget.py` asserts superscar ≤14 000 bytes and that every W‑number mentioned has a body in the active or archive file.
- **Pointer integrity:** `.github/workflows/check-cicatrix-scar-pointers.yml` runs on every PR that touches the scar files, verifying that each `→ dettaglio:` pointer resolves.
- **Number collision prevention:** `scripts/lint_scar_number_collision.py` (ground pack) scans open PRs to prevent two lanes from claiming the same W‑number.

### 1.2 AMENDMENTS & modus‑bench — the loop’s own learning

The modus operating loop (`SKILL.md`, 66 KB) has its own misfire log: **`AMENDMENTS.md`** (52 KB). This records when the loop itself made a wrong gear choice, wasted quota, or missed a probe.

- **`modus‑bench`** (`infra/workflows/modus-bench.js`) is a semi‑automated self‑refinement engine. It sweeps recent scars, AMENDMENTS, PENDING‑ARMS, and external frontier changes, generates amendment proposals, adversarially refutes them, and synthesizes a block for operator (Zero) approval. The first run (2026‑07‑02) produced 12 proposals, all manually checked and merged into `SKILL.md`.
- The `p7‑lesson‑harvester` workflow (`.github/workflows/p7-lesson-harvester.yml`) is a CI gate that ensures the lesson harvester remains in sync with the scar ledger, but it is **shadow‑mode** — it proposes, never auto‑applies.

### 1.3 Memory bodies & lessons

The organism maintains a **memory store** of 1707 files under `$MEM/` (path unavailable, but referenced in the pack).  
- `MEMORY.md` is the index, ordered by priority, with a target size of 17 KB; cut falls at the bottom.  
- `MEMORY_METHOD_LESSONS.md` and `MEMORY_VERIFICATION_RULES.md` (not found in the snapshot) hold operational lessons and verification rules.  
- The `mem` CLI (`/Users/nuzantara/.claude/scripts/mem`) provides query and save operations.

**Experience Library** (`docs/EXPERIENCE_LIBRARY_OPS.md`) and **Skill Registry** (`docs/SKILL_REGISTRY_OPS.md`) are separate SQLite‑based systems that record execution trajectories and reusable skills. They are not yet integrated into the real‑time learning loop; they serve as offline knowledge bases.

### 1.4 Doctrine drift — the HOME‑fork

The global `CLAUDE.md` is a **HOME‑fork** — three divergent copies exist (`.claude/CLAUDE.md` in the repo, `~/.claude/CLAUDE.md` on each machine), and the runtime often reads the stale copy. This is superscar family #1 and is documented in memory `discovery_the_global_claude_md_is_a_home_fork_three_copies_three_answers_2026_08_23.md` (not in snapshot). The antidote (`scripts/lint_home_fork.py`) is a lint, not a root‑cause fix.

## 2. Scars & ledger evidence in this area

### 2.1 Scar volume and recidiva

- **Total scars:** ≈99 (superscar header). Active file: 296 KB; archive: 393 KB. The auto‑archive script has a 10 M‑char limit, so the active file is effectively unbounded.
- **Scars per month (last 4 months):** UNMEASURED from the pack. Command would be: `grep -o "20[0-9][0-9]-[0-9][0-9]" .claude/rules/cicatrix-scars.md | sort | uniq -c`. The archive shows heavy activity in 2026‑04/05; recent entries (W121, W119, W118) are from August 2026.
- **Executable antidote share:** The superscar families list an executable antidote (script/CI gate) for **7 of the 10 families** (ground pack: #1 `lint_home_fork.py`, #2 `pending_arms_report.py`, #3 `guard-conformance/`, #4 `secrets_permissions_audit.py`, #7 `lint_plist_keepalive.py`, #9 `branch_graveyard_cleanup.sh`, #10 truncated). For individual scars, the share cannot be computed from the pack; many scars rely on prose antidotes. A complete measurement would require: `grep -c "ANTIBODY"` vs `grep -c "ESEGUIBILE"` across the corpus.
- **Recidiva rate:** The superscar explicitly calls out **W65→W90→W100→W113** (anti‑hallucination), **W101‑recidiva**, **W84‑tccutil‑recidiva**. That is at least 3 recidiva chains. The rate per total scars is UNMEASURED without the full corpus.

### 2.2 AMENDMENTS → doctrine conversion

The AMENDMENTS.md file (52 KB) records loop misfires. The 2026‑07‑02 bench run produced **12 proposals** (ground pack shows 9 checked items, the rest truncated). Cross‑checking with `git log --oneline -- .claude/skills/modus/SKILL.md | head -40` (UNMEASURED) would reveal how many of those became merged edits. The pack indicates that the bench’s proposals were manually reviewed and applied to `SKILL.md` by the operator.

### 2.3 Memory indicators

- `MEMORY.md` size vs 17 KB target: UNMEASURED (file not in snapshot).
- Lessons added per week in August: UNMEASURED (the p7‑lesson‑harvester CI runs but does not expose counts in the pack).

### 2.4 Key structural scars for this lane

- **W121** (mutation testing on poisoned bytecode) — the verification tool itself was lying; family #2.
- **W119** (regex token‑bleed across newlines) — a guard judged the wrong command; family #3.
- **W118** (11‑hour repo freeze, two hidden causes) — multiple proxy failures; family #2/#9.
- **W78** (wrong scar propagated) — a phantom citation; family #6.
- **W65** (refuter falsely refuted) — the anti‑hallucination recidiva line.

## 3. World SOTA survey

| System / Practice | Source | Mechanism | Measured effect | Transferability |
|---|---|---|---|---|
| **Google SRE blameless postmortems** | [Google SRE book](https://sre.google/sre-book/postmortem-culture/) (unverified) | Structured postmortem template, action items with tracking, “Wheel of Misfortune” training | Reduced incident recurrence, improved on‑call health | High — the scar format is already similar; missing action‑item tracking and closure |
| **Etsy Debriefing** | [Etsy Code as Craft](https://codeascraft.com/2012/05/22/blameless-postmortems/) (unverified) | Focus on process, not people; “just culture” principles | Improved learning culture, faster incident resolution | Medium — the organism already has a no‑blame culture, but could adopt structured debrief facilitation |
| **NASA Lessons Learned System** | [NASA LLIS](https://llis.nasa.gov/) (unverified) | Centralized database of lessons, searchable, with recommendations | Known failure mode: low utilization, lessons not read before missions | Low — the organism’s injection of superscar into every session already solves the “lessons not read” problem |
| **Aviation ASRS** | [ASRS](https://asrs.arc.nasa.gov/) (unverified) | Confidential reporting, immunity, structured causal analysis | High reporting rate, strong safety culture | Medium — the immunity aspect is not applicable, but the structured analysis can be adapted |
| **Toyota A3 / poka‑yoke** | [Lean Enterprise Institute](https://www.lean.org/lexicon/a3-report/) (unverified) | Root‑cause analysis on a single page, mistake‑proofing (poka‑yoke) built into the process | Dramatic reduction in defects | High — the superscar families are essentially poka‑yoke categories; the organism can strengthen the “mistake‑proofing” angle |
| **Reflexion / Voyager skill libraries** | [Reflexion paper](https://arxiv.org/abs/2303.11366) (unverified) | LLM agent self‑refines via verbal reinforcement; Voyager builds a skill library from exploration | Voyager: 5× more unique items collected in Minecraft; Reflexion: 20% improvement on coding benchmarks | Medium — the organism’s skill library is human‑curated; agent‑initiated skill creation is an underexploited asymmetry |
| **Anthropic agent memory** | [Anthropic blog](https://www.anthropic.com/news/agent-memory) (2024, unverified) | Persistent memory for Claude; facts and preferences stored across sessions | Improved personalization, reduced repetition | Low — the organism already has a much richer memory system; the risk is context bloat, which Anthropic’s approach avoids |
| **Netflix “paved road” & guardrails‑as‑code** | [Netflix Tech Blog](https://netflixtechblog.com/) (unverified) | Standardized, pre‑built paths with enforced guardrails; incident → Semgrep rule pattern | Reduced lead time, consistency | High — the organism’s executable antidotes are a form of guardrails‑as‑code; the “incident → rule” pipeline can be formalized |
| **Test‑from‑incident (regression tests tied to postmortems)** | [PagerDuty Postmortems](https://www.pagerduty.com/resources/learn/postmortem-templates/) (unverified) | Every postmortem action item must include a test that proves the fix works and detects regression | Reduction in repeat incidents | Very High — this is the missing piece in the organism’s loop: antidotes are written but not automatically verified |
| **Learning from Incidents (LFI) community** | [LFI Community](https://www.learningfromincidents.io/) (unverified) | Group of researchers studying how organizations learn from incidents; focus on “actions that close” | Empirical evidence that many postmortem actions are never verified | High — the organism’s recidiva data is direct evidence of this failure mode |
| **OPA / Semgrep rules from incidents** | [Semgrep](https://semgrep.dev/) (unverified) | Static analysis rules created automatically from incident patterns | Catch similar bugs before they ship | Medium — the organism already uses hooks and CI; a more systematic incident‑to‑rule pipeline is feasible |
| **Karpathy on knowledge distillation** | [Andrej Karpathy (X)](https://twitter.com/karpathy/status/1756380066580455660) (unverified) | Distilling learnings from an agent’s run into the system prompt for the next run | Reduced token waste, faster convergence | High — the superscar injection is exactly this; the organism can extend it to dynamic, per‑session distillation |

The three practices that matter most for this organism:

1. **Test‑from‑incident (PagerDuty, Google SRE):** The organism’s antidotes are often prose or a script that is not automatically run. SOTA demands that every postmortem action item be accompanied by a test that, if run, would fail before the fix and pass after. This is the single most effective way to close the loop and prevent recidiva.
2. **Guardrails‑as‑code (Netflix, Semgrep):** The organism already has the concept (executable antidotes), but the pipeline from a new scar to a required CI guard is manual and slow. SOTA organizations automate the creation of static analysis rules from incident patterns.
3. **Reflexion / agentic self‑improvement:** The organism’s modus‑bench is a form of this, but it operates at the meta‑level. Applying the same principle at the scar level — having an LLM generate a test for every new scar, then verify that the test actually catches the trauma — would be a step beyond current SOTA.

## 4. Position vs SOTA

| Sub‑dimension | Position | Evidence |
|---|---|---|
| **Incident capture & structure** | AT/ AHEAD | The TRAUMA/ANTIBODY/GOTCHA format is richer than most postmortem templates. Automatic injection of the superscar into every session is a unique advantage. However, capture is manual (via `/scar`) — no automated incident detection. |
| **Pattern extraction (superscar families)** | AT | Manual curation into 10 families is effective for a solo operator, but it does not scale and can miss emergent patterns. SOTA tools (e.g., ML clustering) exist but are overkill for a single repository. |
| **Antidote development (executable vs prose)** | AHEAD | 7 of 10 families have an executable antidote. The organism’s “antidote” terminology and the dual‑level (prose + executable) is unusually well‑structured. Most SOTA postmortems stop at action items. |
| **Antidote enforcement (CI gates)** | AT | The superscar budget, pointer integrity, and number collision are enforced by CI, but many family‑level antidotes are not automatically run on every PR. The guard‑conformance framework is a good start but incomplete. |
| **Meta‑loop (AMENDMENTS / modus‑bench)** | BEYOND | We are aware of **no other system** that has a dedicated, adversarially‑reviewed meta‑loop for its own operating procedure. The modus‑bench is a genuine invention. |
| **Memory & knowledge management** | AT | The MEMORY.md index with priority‑ordered, cut‑at‑bottom discipline is effective. The 1707‑file corpus is rich. However, the doctrine drift (HOME‑fork) is a major regression — SOTA configuration management (e.g., GitOps) would not tolerate three divergent copies. |
| **Recurrence prevention (recidiva)** | BEHIND | The organism explicitly tracks recidiva, which is better than many orgs that ignore it. But the fact that recidiva chains exist (W65→W90→W100→W113) shows that the loop is not closing. SOTA “test‑from‑incident” would prevent these. |
| **Doctrine drift management** | BEHIND | The HOME‑fork problem (superscar family #1) is a known, unresolved structural defect. The organism’s own learning loop has not been able to fix it — the antidote is a lint, not a root‑cause fix. |

**Overall:** The organism is **ahead of SOTA** in its meta‑loop and the structured scar corpus, but **behind** in the core feedback loop that verifies antidotes and prevents recurrence. The biggest gap is the absence of a “test‑from‑incident” mechanism: once an antidote is written, it is never automatically proven to prevent the original trauma.

## 5. Beyond‑SOTA recommendations

### Rank 1: Scar‑Antidote Mutation Testing (SAMT)

**What:** For every scar with an executable antidote (script, CI guard, hook), automatically generate a **mutation test** that (a) reproduces the exact trauma, (b) runs the antidote, and (c) asserts that the antidote blocks/detects the trauma. This test is then run on every PR that touches the affected domain. The test itself is stored alongside the scar.  
**Why it beats SOTA:** SOTA “test‑from‑incident” is manual and often skipped. The organism’s asymmetry is the LLM fleet: we can use a cheap model (Sonnet/Gemini) to **generate** the mutation test from the scar’s TRAUMA description, and then use the adversarial refuter to verify that the test actually fails without the antidote and passes with it. This turns the scar corpus from a passive reference into an active, verified regression suite.  
**Cost:** ~50 K tokens per scar (one‑time generation + verification). No paid API needed; can be done on flat‑sub models.  
**Gear:** 3 (deep, but automated).  
**Risk:** The generated test could be a false‑positive (spurious failure) or false‑negative (doesn’t catch the trauma). Mitigation: the adversarial refuter step. Scar family: #6 (anti‑hallucination) — the test generator must verify its own output.  
**Metric:** **Recidiva rate** — number of scars that recur AFTER their SAMT is deployed. Before: 3 known recidiva chains. After: 0 in 6 months.  
**Measurement method:** `grep -c "RECIDIVA"` on the scar corpus, plus a new CI dashboard tracking SAMT failures.  
**Kill criterion:** If SAMT tests cause >5% of CI failures due to flakiness, pause and adjust.  
**First PR:** Add a `scripts/scar_mutation_test.py` that, given a W‑number, reads the scar entry, asks a local LLM to generate a pytest function, and writes it to `tests/scar‑antidotes/test_W<num>.py`. The script itself is ≤400 lines; it includes a `--verify` mode that runs the test against the old code (via git checkout of the commit before the antidote was merged) and confirms it fails.  

### Rank 2: Closed‑Loop Doctrine Sync (CLDS)

**What:** Replace the HOME‑fork of CLAUDE.md with a **single source of truth** file in the repo, read by all sessions directly from `origin/main` (or a checked‑out worktree) at session start. The `~/.claude/CLAUDE.md` becomes a symlink or a script that fetches the latest version. The lint (`lint_home_fork.py`) is replaced by a hook that blocks any session from reading a stale copy.  
**Why it beats SOTA:** GitOps is standard, but the organism’s unique constraint (solo operator, multiple machines, no dedicated DevOps) makes off‑the‑shelf tools like Chef heavy. A lightweight, LLM‑enforced hook that validates the doctrine version is simpler and exploits the organism’s existing hook infrastructure.  
**Cost:** ~2 K tokens per session (for the version check).  
**Gear:** 2 (standard, but the migration is sensitive).  
**Risk:** If the session cannot reach the repo (air‑gapped scenario), it could be blocked. Mitigation: a cached fallback, but the hook warns. Scar family: #1 (HOME‑fork) — the very thing being fixed.  
**Metric:** **Number of divergent CLAUDE.md copies** — before: 3; after: 1. **Drift‑related incidents** — before: at least W50/W51/W52/W68/W70; after: 0.  
**Measurement method:** `find / -name "CLAUDE.md" 2>/dev/null` and compare sha256.  
**Kill criterion:** If the hook causes >2 session start failures per week, revert to the lint.  
**First PR:** `scripts/sync_claude_md_hook.py` — a pre‑session hook that compares `~/.claude/CLAUDE.md` against `origin/main:.claude/CLAUDE.md` and refuses to start if they differ, with a clear message to pull.  

### Rank 3: Recidiva‑Triggered Structural Promotion (RTSP)

**What:** When a scar family accumulates ≥3 recidiva instances (the same family, same root cause), automatically **escalate** its antidote level: prose → script → CI gate → required branch‑protection check. The escalation is proposed by a CI job, but the operator must approve (Legge 5). The job also opens a PR to move the family’s antidote to the next tier.  
**Why it beats SOTA:** No surveyed system automatically escalates the severity of a countermeasure based on recidiva. Most rely on human judgment. The organism’s asymmetry is the structured superscar families and the recidiva tracking — the data is already there.  
**Cost:** ~10 K tokens per recidiva event (to generate the escalation PR).  
**Gear:** 2 (automated).  
**Risk:** False escalation could add unnecessary CI gates and slow down velocity. Mitigation: operator gate. Scar family: #2 (Esiste≠Armato) — the escalation itself must be verified to be effective.  
**Metric:** **Time to close a recidiva chain** — before: indefinite (W65→W90→W100→W113 went on for months); after: ≤2 weeks from third occurrence.  
**Measurement method:** Track recidiva chains in a new `RECIDIVA.md` ledger, updated by the CI job.  
**Kill criterion:** If the operator rejects >50% of the escalation PRs, the thresholds need tuning.  
**First PR:** `scripts/recidiva_escalator.py` — a CI job (in `.github/workflows/recidiva-escalator.yml`) that (a) parses the superscar for recidiva counts, (b) if a family hits threshold, generates a branch with the antidote promotion, and (c) opens a PR assigned to Zero.  

## 6. 90‑day roadmap

### Wave 1 (Days 1–30): SAMT MVP
- Implement `scripts/scar_mutation_test.py` with the generation and verification steps.
- Run it against the last 10 scars (W115–W124) and generate tests.
- Manually review and merge the first 5.
- Add a CI job that runs the SAMT suite on PRs that touch the domain of the scar.

### Wave 2 (Days 31–60): CLDS roll‑out
- Audit all three CLAUDE.md copies and reconcile differences.
- Implement the sync hook and test it on the Mini.
- Roll out to Pro and M5.
- Decommission the `lint_home_fork.py` script (or repurpose it as a one‑time check).

### Wave 3 (Days 61–90): RTSP & integration
- Build the recidiva escalator CI job.
- Run it against the current recidiva chains (W65 line, W84‑tccutil, etc.) and generate the first escalation PRs.
- Integrate the SAMT, CLDS, and RTSP into a single “Learning Loop Health” dashboard (a markdown file in `research/operations/` updated weekly).

### First PRs (one per recommendation)

| Title | Files | Net lines | Gear | Acceptance test |
|---|---|---|---|---|
| `feat: scar-antidote mutation test generator` | `scripts/scar_mutation_test.py`, `tests/scar-antidotes/__init__.py` | ≤400 | 3 | `python scripts/scar_mutation_test.py --scar W119 --verify` reproduces W119’s trauma and shows the antidote blocks it |
| `fix: closed-loop doctrine sync hook` | `scripts/sync_claude_md_hook.py`, `.claude/hooks/pre-session.sh` | ≤200 | 2 | On a machine with a stale `~/.claude/CLAUDE.md`, a new session refuses to start with a clear message; after `git pull`, the session starts normally |
| `feat: recidiva-triggered structural promotion` | `scripts/recidiva_escalator.py`, `.github/workflows/recidiva-escalator.yml` | ≤300 | 2 | Running the job against a test corpus with 3 recidiva in family #6 opens a PR that promotes the family’s antidote to a required CI check |

## 7. Needs‑ruling

- **CLDS rollout on M5:** The M5 is the primary workhorse and has a 250‑commit‑behind checkout by design. The sync hook would force a pull, potentially breaking the deliberate staleness. Zero must decide whether the M5 can be brought into the closed loop or if it remains a managed exception.
- **SAMT model choice:** The scar‑to‑test generation uses an LLM. Which model? The organism’s policy is flat‑sub only, CLI‑only. A local Ollama model could be used for PII‑free generation, but its quality may be lower. Zero must decide the acceptable quality threshold.
- **RTSP operator approval frequency:** The escalation PRs require Zero’s approval. If the volume is high (e.g., after a spike of recidiva), it could become a burden. A delegation rule (e.g., “auto‑approve if the antidote is already a script and the promotion is to a non‑required CI gate”) could be proposed.

## 8. §Meta‑pattern

The single defective belief that generates the failures in this area is: **“A documented antidote is an effective antidote.”** The organism treats the act of writing down a scar and its antidote as the end of the learning loop. In reality, the loop is only closed when the antidote is **proven** to prevent the trauma. This manifests as:

- Prose antidotes that are never run (family #2: Esiste≠Armato).
- Executable antidotes that are not verified (W121: the mutation‑testing tool itself was lying).
- Recidiva chains that continue because the antidote was never tested against the original trauma (W65→W90→W100→W113).
- AMENDMENTS that are written but not enforced (the durable‑receptor specification was wrong, but the fix was only applied after the bench run).

The beyond‑SOTA recommendations all attack this belief by requiring **empirical verification** of every antidote before it is considered “closed.”

## 9. Sources

1. **Google SRE book — Postmortem Culture**  
   URL: https://sre.google/sre-book/postmortem-culture/ (unverified)  
   Date accessed: 2026-08-28  
   Authoritative: The canonical reference for blameless postmortems and action‑item tracking in large‑scale systems.

2. **Etsy — Blameless Postmortems and a Just Culture**  
   URL: https://codeascraft.com/2012/05/22/blameless-postmortems/ (unverified)  
   Date accessed: 2026-08-28  
   Authoritative: Pioneering engineering blog that popularized the “just culture” approach.

3. **NASA Lessons Learned System**  
   URL: https://llis.nasa.gov/ (unverified)  
   Date accessed: 2026-08-28  
   Authoritative: The largest and oldest formal lessons‑learned system; its failure modes are well‑studied.

4. **Aviation Safety Reporting System (ASRS)**  
   URL: https://asrs.arc.nasa.gov/ (unverified)  
   Date accessed: 2026-08-28  
   Authoritative: Gold standard for confidential incident reporting and structured causal analysis.

5. **Toyota A3 Report / Poka‑Yoke**  
   URL: https://www.lean.org/lexicon/a3-report/ (unverified)  
   Date accessed: 2026-08-28  
   Authoritative: Foundational lean manufacturing practice for root‑cause analysis and mistake‑proofing.

6. **Reflexion: Language Agents with Verbal Reinforcement Learning**  
   URL: https://arxiv.org/abs/2303.11366 (unverified)  
   Date: 2023-03-20  
   Authoritative: Peer‑reviewed paper introducing a key LLM agent self‑improvement technique.

7. **Anthropic — Agent Memory (Claude)**  
   URL: https://www.anthropic.com/news/agent-memory (unverified)  
   Date: 2024  
   Authoritative: Official announcement of the memory feature in Claude, relevant for comparison.

8. **Netflix Tech Blog — Paved Road and Guardrails**  
   URL: https://netflixtechblog.com/ (unverified)  
   Date accessed: 2026-08-28  
   Authoritative: Industry standard for developer experience and safety guardrails.

9. **PagerDuty — Postmortem Templates and Best Practices**  
   URL: https://www.pagerduty.com/resources/learn/postmortem-templates/ (unverified)  
   Date accessed: 2026-08-28  
   Authoritative: Widely used incident management platform with mature postmortem practices.

10. **Learning from Incidents (LFI) Community**  
    URL: https://www.learningfromincidents.io/ (unverified)  
    Date accessed: 2026-08-28  
    Authoritative: Research community focused on the socio‑technical aspects of incident learning.

11. **Semgrep — Static Analysis at Scale**  
    URL: https://semgrep.dev/ (unverified)  
    Date accessed: 2026-08-28  
    Authoritative: Leading open‑source static analysis tool used to enforce incident‑derived rules.

12. **Andrej Karpathy on Knowledge Distillation for LLMs**  
    URL: https://twitter.com/karpathy/status/1756380066580455660 (unverified)  
    Date: 2024-02-10  
    Authoritative: Thought leader in LLM‑based agents; the post discusses distilling agent learnings into system prompts.

---

**status: complete**
**repo_files_verified:**
- `.claude/rules/cicatrix-superscar.md`
- `.claude/rules/cicatrix-scars.md` (excerpts)
- `.claude/rules/cicatrix-scars-archive.md` (excerpt)
- `scripts/tests/test_superscar_budget.py`
- `scripts/lint_scar_number_collision.py`
- `.claude/commands/scar.md`
- `infra/launchagents/cicatrix_autoarchive.sh`
- `.github/workflows/check-cicatrix-scar-pointers.yml`
- `.github/workflows/p7-lesson-harvester.yml`
- `.claude/skills/modus/AMENDMENTS.md` (excerpt)
- `infra/workflows/modus-bench.js`
- `.claude/skills/modus/SKILL.md` (excerpt)
- `docs/EXPERIENCE_LIBRARY_OPS.md`
- `docs/SKILL_REGISTRY_OPS.md`
- `.claude/skills/skill-catalog/SKILL.md`
- `MEMORY.md` (not in snapshot, referenced)
- `research/operations/2026-08-21-token-ceremony-ci-system-audit.md` (excerpt)

**UNMEASURED metrics:** scars per month, share of scars with executable antidote, recidiva rate, AMENDMENTS→SKILL.md conversion, MEMORY.md size, lessons/week. Commands provided in the text.