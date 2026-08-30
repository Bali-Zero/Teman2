---
date: 2026-08-28
domain: operations
part: X3 ai-native-engineering-os
scope: the meta-layer that makes AI sessions the operator — skills, agents, rules/scars, hooks, memory (MOS), council/gate doctrine, MCP tool surface, fleet mailbox
sources:
  - https://www.anthropic.com/engineering/multi-agent-research-system
  - https://cognition.com/blog/dont-build-multi-agents
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://arxiv.org/abs/2501.13956
  - https://arxiv.org/abs/2310.08560
  - https://arxiv.org/abs/2305.16291
  - https://arxiv.org/abs/2303.11366
  - https://arxiv.org/abs/2407.16741
  - https://arxiv.org/html/2511.03690v1
  - https://factory.ai/news/software-factory
  - https://arxiv.org/abs/2410.21819
  - https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
  - https://arxiv.org/abs/2505.20411
  - https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them
  - https://arxiv.org/html/2608.01955v1
status: DONE
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# X3 — AI-Native Engineering OS

## Anatomy (as measured)

All paths relative to the worktree pinned at `origin/main 11a3c89a2e`; every count below was produced by a command run against that tree during this lane.

**Skills.** `.claude/skills/` holds 16 skills (10 local directories + 6 symlinks into `.agents/skills/`, the cross-agent Tier-A store), totalling 10,028 lines of SKILL.md. They split into two species: *method skills* (modus 280 lines, sota-architecture-loop 158, karpathy-discipline 91, reuse-first 132, final-gate-discipline 82, pipeline-ship 201, agent-session-discipline 126, skill-catalog 56, workflow 198) and *corner skills* — live shared context per business vertical (kbli-navigator 3,486 lines, bot 1,897, visaoracle 1,581, intake 677, secondhome 425, wr2 386, slhs 252). Corner skills are effectively versioned project memory: verified truths, owner rulings, live state, "blood-bought rules." `.claude/agents/` holds 19 agent definitions (+README) — 9 WR2 editorial specialists, plus backend-verifier, frontend-browser, mcp-health, spalla-review, regulatory-watcher, ledger-writer, lint-fixer, log-triage, docs-sync, fixture-gen, i18n-sync, catalog-meta.

**Master loop.** `modus` (`.claude/skills/modus/SKILL.md:33-84`) is the operating system proper: TRIAGE into 3 gears, then 9 stages (GROUND → DESIGN → BUILD → VERIFY → SHIP+ARM → PROVE-LIVE → ALIGN-FLEET → CLEAN → CAPTURE). Two design decisions stand out against industry practice: (a) every stage row carries a **PROBE column** — what *proves* the stage, not what claims it (e.g. PROVE-LIVE: "A producer's own log/counter is STILL a proxy… prove by the DOWNSTREAM state-delta", SKILL.md:81) — and (b) a **"Scars killed" column** binding each stage to the named historical failures it exists to prevent. Cost control is doctrinal, not vibes: the council fires only if three conditions hold (divergent priors ∧ error cost >15× tokens ∧ parallel breadth, SKILL.md:50-52), and a gear *ceiling* lint (`compute_ceiling()` in `scripts/evidence_pack_lint.py`, referenced at SKILL.md:63-68) fails a docs-only diff that declares Gear 3.

**Scar system (cicatrix).** Three files: `cicatrix-superscar.md` (252 lines — the "bridge": 10 families + orphans, each with malattia / early-signal / structural antidote / member list), `cicatrix-scars.md` (1,517 lines, 73 entry headers) and `cicatrix-scars-archive.md` (3,197 lines, 95 headers) — ~130 W-numbered traumas in total. Three properties make this more than a lessons-learned folder: (1) the superscar file is **injected into every session and every subagent**, and its size is **CI-enforced** (≤14KB byte budget + completeness check — every W-number cited must have a body — `scripts/tests/test_superscar_budget.py`, verified on disk); (2) **six of ten families carry an executable antidote**, all verified present: `scripts/lint_home_fork.py` (#1), `scripts/pending_arms_report.py` (#2), `infra/guard-conformance/check_guard_conformance.py` + `registry.json` (#3 — a censused guard without guilt+innocence tests fails CI), `scripts/secrets_permissions_audit.py` (#4), `scripts/lint_plist_keepalive.py` (#7), `scripts/branch_graveyard_cleanup.sh::content_on_main()` (#9); (3) scars are *compressed upward* — bodies stay in the scar files, families carry 3-8-word member lines, so the always-injected context cost is bounded by construction.

**Self-model of the loop.** `.claude/skills/modus/AMENDMENTS.md` (96 lines) is the loop's own scar file — append-only `date | what misfired | evidence | proposed change` entries, explicitly an *evidence log, not live doctrine* (nothing executes from it; changes reach SKILL.md only via operator-approved PR, SKILL.md:237-253). Its honesty is the remarkable part: the 2026-08-22 entry measures that two sessions mandated to "cut token waste" ran 44h+31h, opened 180 PRs, spent 8.6M output tokens and shipped ~10 business commits; the 2026-08-26 entry records that the file itself logged zero entries for a second time across a window it should have covered, and names the cure (receptor-live mandate) with a kill criterion. `PENDING-ARMS.md` (1,495 lines) is the W81 "built ≠ armed" ledger — 54 open items at measurement — with `scripts/pending_arms_report.py` alarming lines open >48h and a CI strict-phantom gate rejecting any bare `operator` owner.

**Adversarial verification.** `infra/workflows/verify-template.js` (189 lines) encodes generator≠grader as a runnable artifact: gather N angles → independent skeptics per finding on fresh context ("Default to refuted=true when uncertain", line 137) → majority-not-refuted survival (line 149) → synthesize survivors only. The finding schema forces `claim / evidence / source / confidence` with `"INFERENCE"` as an honest source value (lines 69-97). `FLEET_TOPOLOGY.json` (v1.4, 465 lines) is the SSOT for who judges whom: 5 account families (anthropic/openai/google/moonshot/alibaba), 11 role chains, and 9 invariants — the final on-disk gate (Opus 5, rotating 4 Anthropic accounts) "never cascades to a weaker model"; PII lanes are local-only with "QUEUE. NEVER cloud." on exhaustion; "No external seat ever merges or deploys"; refuter chains enforce **family-exclusion** (a family that built on a task is excluded from its own refuter chain, 2-family quorum required, PROBATION seats never count).

**Hooks.** `~/.claude/hooks/` holds ~25 active Python/shell hooks — worktree_isolation, stop_verify, subagent_stop_verify, guardrails-static, host_boundary, model_routing_gate, orchestrate_gate, premise_gate, seam_verify, mailbox_inject, precompact-mnemos, stadio_zero_nudge, dispatch_nudge, mos_capture_* — the enforcement layer for the doctrine "if a critical rule is violable, write a hook" (repo CLAUDE.md §7). The same listing shows ~30 `.bak-*` fossils, 23 of them for `worktree_isolation.py` alone — measured evidence that the control plane is hand-patched in place, outside git (see Honest state).

**Memory (MOS).** `~/.claude/projects/-Users-balizero-nuzantara/memory/` holds 1,714 files. Architecture: one fact per file with frontmatter; a load-bearing index `MEMORY.md` (ruled target ~17KB, priority-ordered so "the cut falls at the BOTTOM") auto-injected each session; 10+ themed sub-indexes (`MEMORY_VERIFICATION_RULES.md` 76.6KB/43 rules, `MEMORY_MERGE_QUEUE_TRAPS.md` 21.8KB/19 traps, `MEMORY_SHELL_CLI_TRAPS.md` 15.5KB/21 traps…); an FTS5-backed CLI (`mem query/save/entities`); and an index-line discipline ("a correction only in the BODY is dead — update the index line in the same turn"). This is a hand-built hierarchical memory with explicit eviction policy and recall-path engineering.

**Tool surface & doctrine.** `apps/nuzantara-mcp/nuzantara_mcp/tools/` registers **162 `@mcp.tool` functions across 29 modules** (crm, drive, pricing, legal, intel, workflows…; the "115 tools" figure circulating in doctrine is stale), plus separate `nuzantara-mcp-advanced` and `nuzantara-mcp-browser` servers and `apps/team-agent` (bridge / mcp-wrapper / onboarding). CI-side, 12+ gate workflows exist (`harness-floor.yml`, `immune-enforcement.yml`, `adversarial-review-gate.yml`, `hook-innocence-gate.yml`, `hot-zone-pr-gate.yml`, `merge-gate-integrity-watch.yml`, `zantara-core-edit-gate.yml`…). `SYMBIOSIS.md` (304 lines) supplies the biological doctrine: cell-core PulseLoop (sense→think→act→reflect→dream→mature), a Genome table with `record_skill()` on success, epigenetic `silence_stale_skills()` (decay, never delete) and `inherit_genome()` with confidence decay ×0.9 at fork — a Voyager-style skill library designed before most of the industry shipped one.

## Honest state vs. SOTA

**Genuinely ahead of industry practice:**

1. **The cicatrix system has no public peer that I could find.** Published "lessons learned" practice stops at postmortem documents; Nuzantara compresses ~130 traumas into 10 CI-budgeted families injected into *every* agent context, with executable antidotes for 6/10 families. The closest academic analogue (Reflexion's verbal episodic memory) is per-task and ephemeral; this is organizational, permanent, and enforced.
2. **Generator≠grader as culture, not tip.** Family-exclusion across five vendor families, refuter quorum rules, "even the refuter hallucinates" (W65) with a designed second catch at the final gate, and a runnable workflow artifact — this goes beyond the "use a different model as judge" heuristic in the literature, which rarely handles the judge's own failure modes.
3. **Meta-honesty with measurement.** AMENDMENTS entries that quantify the loop's own waste (8.6M tokens → ~10 business commits) and record their own recording failures are rare anywhere; most self-improving-agent literature reports only successes.

**Theater and disease, measured:**

1. **The meta-work loop is the system's dominant pathology.** 195 merged PRs in 3 days with 27/200 commits existing only to correct a previous commit's claim (repo CLAUDE.md, Agent PR Contract rule 8); a 1-file hook fix consuming 14 commits/11 adversarial rounds/~6h (PR #4547). The immune system attacks its own body: verification machinery generates much of the work it verifies.
2. **Dead gates advertised as live.** The Layer-2 AI-review Action failed its trust gate on ~100/100 runs over ~30h while doctrine credited it with review coverage, before being disabled with the post-mortem in the filename (`ai-pr-review.yml.disabled-2026-08-20-zero-value-ci-trust-gate`). Scar family #2 ("Esiste ≠ Armato") is simultaneously the best-documented family and the most-recurring — 30+ members and counting.
3. **The control plane is outside version control.** `~/.claude/hooks/` — the enforcement layer itself — lives in $HOME, hand-patched (23 `.bak` generations of one file), which is precisely scar family #1 (HOME-fork drift) applied to the organ that enforces the scars. Doctrine acknowledges it as operator-only by design; the .bak archaeology shows the cost of that design.
4. **Capture is the weakest stage.** AMENDMENTS went silent twice across exactly the windows with the most activity; the ledger's 54 open lines include items whose age measures time-since-written, not time-the-gap-existed (2026-07-26 entry). The system writes rules faster than it arms receptors — its own retro (11-agent workflow `wf_eb832a9d-0ec`) found 22 proposed new gates shared one shape: convert existing prose into a check at an existing door, never new ceremony.
5. **No evaluation harness for the OS itself.** There is no golden-task regression suite: a change to modus, a hook, or a routing chain ships with adversarial review but with no *measured* before/after on a fixed task set. `modus-bench` sweeps scars and changelogs; it does not replay tasks.
6. **Memory index bloat is beginning.** `MEMORY_LATEST_WORK.md` at 359KB is a landfill by construction; the 17KB discipline holds only for the top index.

## Deep research: the world's best

**Orchestration topology — the Anthropic/Cognition axis.** The two poles of 2025-26 practice: Anthropic's multi-agent research system (orchestrator-worker, parallel subagents, ~90% improvement over single-agent on parallelizable research, at ~15× token cost) and Cognition's "Don't Build Multi-Agents" (parallel subagents without shared context make conflicting decisions; prefer a single-threaded agent with full traces + compaction, especially for coding). Anthropic's own follow-up concedes the synthesis: multi-agent wins only when the task decomposes into *independent read-heavy* strands; coding is tightly interdependent and mostly does not. Nuzantara's doctrine already sits at this synthesis point — "Fan-out for READS, funnel-in for WRITES" and "coding barely parallelizes (Anthropic/Cognition)" are literally in `modus` SKILL.md:53-58, and the ≈15× council-cost figure appears verbatim in the anti-sperpero rules. Notably, the AMENDMENTS entries of 2026-07-14/08-08 (parallel lanes serializing on a shared pre-push lock; wave sizing by lock capacity, not task readiness) rediscovered Cognition's core argument empirically, from the infrastructure side.

**Context engineering.** Anthropic's "Effective context engineering for AI agents" names the design goal — *the smallest set of high-signal tokens that maximizes the likelihood of the desired outcome* — and three mechanisms: compaction, structured note-taking persisted outside the window, and sub-agent isolation of dirty context. Nuzantara implements all three natively (precompact-mnemos hook + `resume` skill; PENDING-ARMS/ledger files as structured notes; read-lane subagents), and adds one the post does not: a **CI-enforced byte budget on always-injected context** (superscar ≤14KB with completeness checking). That is context engineering as a *tested invariant* rather than a guideline — ahead of the published pattern.

**Agent memory systems.** The production frontier is converging on hybrid vector+graph stores with explicit temporal semantics: MemGPT/Letta introduced OS-style paged memory tiers with self-editing memory (arXiv:2310.08560); Zep's Graphiti engine (arXiv:2501.13956) builds a *temporally-aware* knowledge graph where every fact carries validity intervals, so a superseded fact is structurally invalidated rather than merely contradicted by a newer document. Nuzantara's MOS is architecturally distinctive — a human-legible, git-diffable, priority-ordered index hierarchy with FTS5 — and its recall-path engineering (index-line discipline, "the cut falls at the bottom") is genuinely sophisticated. What it lacks is exactly what Zep automates: **structural staleness**. The system compensates with prose rules ("memories reflect what was true when written; verify before recommending") and manual archive sweeps — a human-process patch for a missing data-model feature, and W90 (the ground-truth verifier serving a stale snapshot) is the scar that proves the cost.

**Skill libraries and self-improvement.** Voyager (arXiv:2305.16291) established the pattern: an ever-growing library of *executable, self-verified* skills, retrieved before reasoning from scratch, grown by an automatic curriculum. Reflexion (arXiv:2303.11366) established verbal self-reflection stored in episodic memory — and its known plateau, which SYMBIOSIS.md:44 cites explicitly ("plateau al 45-50%; when the Council exists, reflection becomes multi-agent"). Nuzantara has both halves *designed* (cell-core Genome with record_skill/epigenetic silencing/inheritance; WR2/WR3 reflexion-synth weekly crons) but the load-bearing skill store in daily use — `.claude/skills/` — is prose, not executable; the closest thing to Voyager's verified-executable skills is the cicatrix *antidote scripts*, which is why 6/10 families having one matters. The bench→refuter→operator-gated-PR pipeline for changing modus is a governance answer to the "self-improving agents drift" problem that the academic literature (e.g. metacognitive-learning critiques of static self-improvement) mostly leaves open.

**Software-agent platforms.** OpenHands (arXiv:2407.16741; SDK paper arXiv:2511.03690) contributes two patterns: an **AgentController that enforces budget/iteration constraints outside the agent's own judgment**, and a **stateless, event-sourced architecture** where the event log is the replayable ground truth of what happened. Factory.ai's "software factory" thesis adds enterprise context unification (GitHub/Linear/Sentry → a persistent organizational memory feeding every droid) and "delegation with control" — agents show their work so humans stay in the outer loop. Nuzantara's equivalents are file-ledgers rather than event logs (grep-able but not replayable; the 2026-08-08 AMENDMENTS cluster about background pushes reporting an `echo`'s exit code is a symptom of non-event-sourced state), and its harness-floor/gear system is an *external* budget controller comparable to OpenHands' AgentController — with the notable difference that Nuzantara's floor is computed from the diff and CI-recomputed, i.e. non-gameable by the agent, which OpenHands does not attempt.

**Verification and LLM-as-judge.** The research record is unambiguous that judges are biased instruments: self-preference bias correlates measurably with a model's ability to *recognize its own output* (arXiv:2410.21819), plus position and verbosity biases; standard mitigations are rubrics, ordering randomization, and ensembles. Nuzantara's family-exclusion rule is a stronger structural mitigation than anything in the mitigation literature — it removes the *training-prior family*, not just the instance, from judging its own work. The system also already treats verdicts as leads with an expected 30-40% false-sick rate (SKILL.md:267) — but that number is folklore, not measurement (see Recommendations). On benchmarks: OpenAI publicly stopped reporting SWE-bench Verified for contamination; harness choice alone moves a model's score by up to ~8 points (62.3→70.2%); ~31% of instances have weak test oracles (SWE-rebench, arXiv:2505.20411). The field's conclusion — *public benchmarks mismeasure; build decontaminated internal task suites* — is precisely the instrument Nuzantara lacks for its own operating system.

**Self-healing operations.** The 2025-26 AIOps literature (e.g. LLM-ARF; agentic self-healing pipelines, arXiv:2608.01955) converges on: deterministic rules for *known* failure classes, LLM reasoning reserved for *novel* diagnosis, a risk-aware policy layer deciding what may auto-execute, and human checkpoints at governance boundaries. Nuzantara's A1-A4 rings + operator-gated remediation + the honest "this is self-healing, NOT recursive self-improvement" framing (verify-template.js:4-10) match this shape almost exactly — and the cicatrix families are, in AIOps terms, a hand-built failure-mode taxonomy that most production platforms never formalize.

## Gap table

| Dimension | SOTA reference | Nuzantara today | Gap |
|---|---|---|---|
| Institutional failure memory | Postmortem docs; Reflexion (per-task) | 130 scars → 10 CI-budgeted families, injected everywhere, 6/10 with executable antidote | **Ahead** — no public peer |
| Adversarial verification | LLM-as-judge + different-model heuristic; bias lit | Family-exclusion, 2-family quorum, refuter-of-refuter, runnable verify-template | **Ahead**, but refuter precision unmeasured |
| Context engineering | Anthropic compaction/notes/sub-agents | Same three + CI-enforced byte budget on injected context | **Ahead** on enforcement |
| Orchestration topology | Anthropic orchestrator-worker vs Cognition single-thread | Read-fanout/write-funnel synthesis; non-gameable gear floor+ceiling | **At parity** (converged independently) |
| Budget control | OpenHands AgentController (budget/iterations) | Gear system, anti-sperpero gates, effort routing | At parity; floor is non-gameable (better), but enforcement is partly prose |
| Agent memory data model | Zep temporal KG (validity intervals); Letta paged tiers | File+FTS5 hierarchy, hand-curated indexes, prose staleness rules | **Behind** on structural staleness/invalidation |
| Skill library | Voyager executable, self-verified, curriculum-grown | Prose skills + designed-but-partially-armed Genome; antidote scripts as the real executable layer | **Behind** on executable promotion path |
| Eval harness for the OS itself | Internal decontaminated task suites (post-SWE-bench-Verified consensus) | modus-bench (scar/changelog sweep, no task replay); no golden tasks, no regression metric | **Behind** — biggest measurable gap |
| Event-sourced state | OpenHands stateless/event-sourced SDK | Prose ledgers (PENDING-ARMS 1,495 lines), grep-based reconciliation | **Behind** on replayability/verify automation |
| Meta-work economics | Not measured anywhere publicly | Measured once (8.6M tokens → ~10 commits), not yet a standing metric | **Ahead** on honesty, behind on instrumentation |

## Recommendations — reach SOTA

**R1 (P0) — Build the golden-task eval harness for the operating loop.** The industry consensus after SWE-bench Verified's fall is that serious shops run *internal, decontaminated* task suites. Nuzantara changes its own OS (modus, hooks, routing chains) with adversarial review but zero task replay. Concretely: 15-25 frozen tasks (a Gear-1 fix, a Gear-2 feature with a planted bug, a Gear-3 audit with known findings, a scar-family trap each for #1/#2/#3/#9), run monthly and on every modus/hook/gate change, scoring: task success, token cost, PR rounds, false-refutation count. Reuse `infra/workflows/` + modus-bench as the runner — no new infrastructure. *Acceptance metric:* baseline published within 30 days; every SKILL.md/hook change PR carries a bench delta; correction-commit ratio (the 27/200 measure, recomputed by script over rolling 14 days) falls below 8% within 90 days — falsifiable because the script either exists and prints the number or it doesn't.

**R2 (P0) — Version the control plane.** `~/.claude/hooks/` is family #1 applied to the immune system: 23 `.bak` generations of `worktree_isolation.py`, zero git history. Move hook sources into the repo (e.g. `infra/hooks/`), install by symlink or sync script, and extend `scripts/lint_home_fork.py`'s declared-pairs list to cover every active hook. The operator-only *edit* boundary can survive (the sync step stays a human action); what changes is that drift becomes measurable. *Acceptance metric:* `lint_home_fork.py` covers 100% of active hooks; zero `.bak` files in `~/.claude/hooks/`; a deliberately drifted hook byte is caught by CI within one run.

**R3 (P1) — Add structural staleness to MOS (the Zep lesson, hand-rolled).** Add optional frontmatter `valid_until:` / `superseded_by:` to memory files and a sweeper (extend the existing archive discipline) that demotes expired facts out of index files automatically. This converts the prose rule "memories reflect what was true when written" into a data-model property, and directly attacks the W90 class (stale ground truth indistinguishable from fresh). *Acceptance metric:* ≥60% of `discovery`/`fact` memories carry temporal metadata within 60 days; a planted expired memory is auto-demoted from its index by the sweeper without human action.

**R4 (P1) — Make ledgers machine-verifiable (the OpenHands event-sourcing lesson, minimal form).** The 2026-07-26 AMENDMENTS entry already proposed `pending_arms_report.py --verify`: execute the mechanically-executable subset of `proof:` fields and flag lines whose criterion passes while still open. Ship it, and migrate new PENDING-ARMS entries to a structured line format (owner/proof/receptor as parseable fields — the parser-anchoring scar of 2026-07-26 shows the current format is already half-parsed, badly). *Acceptance metric:* `--verify` mode exists and auto-flags ≥5 of the current 54 open lines as closeable on first run (the 2026-07-26 manual pass found 3 — the tool must beat the hand).

**R5 (P2) — Arm the designed-but-dormant skill lifecycle.** SYMBIOSIS declares confidence decay, pruning, and inheritance for Genome skills; verify which of `record_skill`/`silence_stale_skills` actually execute in live organs, and either arm them or delete the doctrine (a rule that lies is worse than either option — the system's own 2026-07-25 ruling). *Acceptance metric:* a query of the Genome table shows non-zero skills recorded in the last 30 days, or the SYMBIOSIS section is amended to match reality.

## Recommendations — beyond SOTA

**B1 (P1) — Scar→antidote co-generation, enforced.** Nobody in industry has an enforced trauma→executable pipeline. Extend the superscar completeness test: every *new* family member must declare either an executable antidote (path to script/test) or an explicit `prose-only:<reason>` tag; CI fails a scar entry with neither. Target 10/10 families executable (today 6/10 — #5 sibling-race, #6 phantom-citation, #8 network-flap, #10 split-brain lack scripts). *Acceptance metric:* the superscar test gains the check; two of the four script-less families gain an executable antidote within 90 days.

**B2 (P0, cheap) — Tokens-per-business-outcome as a standing daily metric.** The 2026-08-22 measurement (8.6M output tokens → ~10 business commits) was a one-off autopsy. The receptor-live mandate's `seat_mix_report.py` scoreboard is the right vehicle: add a daily ratio of output tokens (and PR count) to *business-surface* commits (paths outside `.claude/`, `scripts/tests/`, ledgers, workflows). No published agentic system measures its own meta-work ratio continuously; this is the single number that makes the system's dominant pathology visible before it runs for 44 hours. *Acceptance metric:* the scoreboard publishes the ratio daily by Day 30; the mandate's own Day-90 kill criterion is honored if it doesn't.

**B3 (P1) — Measure refuter precision per seat, route by measurement.** The "expect 30-40% false-sick" figure in modus is folklore. Every refuter verdict already ends in a ground-truth disposition (the final gate re-verifies). Log `(seat, family, verdict, gate-outcome)` per refutation into a small table; after ~100 rows, publish per-seat precision/recall and let FLEET_TOPOLOGY chain *order* follow measured precision instead of ruling alone. This is the LLM-as-judge bias literature operationalized on a live PR stream — beyond anything published. *Acceptance metric:* ≥100 logged verdicts with dispositions within 60 days; at least one chain reordering (or an explicit ruled refusal) justified by the numbers.

**B4 (P2) — Curriculum-driven debt attack (Voyager's automatic curriculum, applied to ops).** PENDING-ARMS is drained by age and alarm; Voyager's insight is that *what to learn next* should be chosen for maximal capability gain. Let modus-bench rank open ledger lines by blast-radius (scar-family membership of the surface × consumer count) and emit a weekly "attack next" triple, so the 54-line backlog shrinks by expected-harm order, not chronology. *Acceptance metric:* the ranking exists and the weekly top-3 differs from the 3 oldest lines (proving it encodes something age doesn't); ledger line-count trend negative over 60 days.

## §Meta-pattern

One defective belief generates most findings on both sides of the ledger: **"the written artifact is the thing in force."** Where the system overcame this belief, it is ahead of the world — PROBE columns, executable antidotes, CI-enforced byte budgets, the built≠armed ledger, "green ≠ working." Where the belief persists, every pathology lives: doctrine credited a review gate that failed 100/100 runs; SYMBIOSIS declares a skill lifecycle nobody verified is running; AMENDMENTS is a capture organ that twice failed to capture; 54 armings are pending while new rules are written; hooks enforce doctrine while being themselves unversioned artifacts nobody diffs. The engineering-craft panel (2026-08-29) independently named the same meta-disease fleet-wide. The cure shape is also already known internally — the retro's own finding that every surviving proposal "converts an existing prose rule into a check at a door that already exists." Every recommendation above is that shape: no new ceremony, only receptors at existing doors.

## §Solo-operatore

Decisions only Zero can take:

1. **Control-plane boundary (R2).** Moving hook sources into the repo changes the deliberately operator-only `~/.claude/hooks/` boundary. The proposal keeps installs human-gated; whether that trade is acceptable is Legge-5.
2. **Eval-harness quota spend (R1).** Replaying 15-25 golden tasks monthly consumes real OAuth window; authorizing that standing spend (and its seat) is a business call.
3. **Receptor-live Day-90 kill criterion (B2).** The mandate self-declares suspension if the scoreboard isn't live with real deltas; only Zero can enforce or waive its own kill switch.
4. **Measured-precision routing (B3).** Today refuter chain order is ruled (2026-07-19, 2026-08-10). Letting a measured precision table reorder a ruled chain transfers a Legge-5 prerogative to an instrument; Zero must decide whether the instrument may outrank the ruling.
5. **SYMBIOSIS truth reconciliation (R5).** If the Genome lifecycle is dormant, choosing between arming it and deleting the doctrine is a strategy call about whether the cell-core biology metaphor remains a build target.

## Sources

1. Anthropic — How we built our multi-agent research system: https://www.anthropic.com/engineering/multi-agent-research-system
2. Cognition — Don't Build Multi-Agents: https://cognition.com/blog/dont-build-multi-agents
3. Anthropic — Effective context engineering for AI agents: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
4. Zep: A Temporal Knowledge Graph Architecture for Agent Memory (arXiv:2501.13956): https://arxiv.org/abs/2501.13956
5. MemGPT: Towards LLMs as Operating Systems (arXiv:2310.08560): https://arxiv.org/abs/2310.08560
6. Voyager: An Open-Ended Embodied Agent with Large Language Models (arXiv:2305.16291): https://arxiv.org/abs/2305.16291
7. Reflexion: Language Agents with Verbal Reinforcement Learning (arXiv:2303.11366): https://arxiv.org/abs/2303.11366
8. OpenHands: An Open Platform for AI Software Developers as Generalist Agents (arXiv:2407.16741): https://arxiv.org/abs/2407.16741
9. The OpenHands Software Agent SDK (arXiv:2511.03690): https://arxiv.org/html/2511.03690v1
10. Factory 2.0: From coding agents to software factories: https://factory.ai/news/software-factory
11. Self-Preference Bias in LLM-as-a-Judge (arXiv:2410.21819): https://arxiv.org/abs/2410.21819
12. OpenAI — Why SWE-bench Verified no longer measures frontier coding capabilities: https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
13. SWE-rebench: Automated Task Collection and Decontaminated Evaluation (arXiv:2505.20411): https://arxiv.org/abs/2505.20411
14. Claude blog — When to use multi-agent systems (and when not to): https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them
15. Agentic Self-Healing for Data & AI Pipelines (arXiv:2608.01955): https://arxiv.org/html/2608.01955v1
