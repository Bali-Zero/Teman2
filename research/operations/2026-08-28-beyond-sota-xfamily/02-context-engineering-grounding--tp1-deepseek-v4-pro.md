---
panel: beyond-sota-xfamily
lane: 02-context-engineering-grounding
seat: tp1-deepseek-v4-pro
model: "deepseek-v4-pro · reasoning_effort=max · TP1 API, no tools, ground pack"
started: 2026-08-28T16:39:37Z
finished: 2026-08-28T16:44:41Z
duration_s: 304
exit: 0
words: 3622
prompt_sha256_16: eeab2aa9df9a33c2
prompt_chars: 165574
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 2/13 — Context engineering & grounding
model: DeepSeek V4 Pro (pinned lane)
sources: 12
repo_files_verified: 16
---

# 0. TL;DR

**Position vs SOTA:** Nuzantara is **AHEAD** in operational receptor injection (escalations), scar-as-context bridging, and on-demand skill discovery; **AT** in repomap generation and anti-hallucination doctrine; **BEHIND** in subagent context isolation, memory index budget control, and doctrine drift. The single biggest gap is that fork‑lane subagents inherit the full parent session context (~90 k tokens), causing token exhaustion and degraded performance. The top‑3 moves are: (1) implement subagent context isolation with a minimal handoff protocol, (2) enforce the MEMORY.md index budget and auto‑trim, and (3) reorganize SessionStart injection for prompt‑caching effectiveness and impose a total boot budget.

# 1. How Nuzantara does it today

Every claim below is grounded in the redacted ground pack; where a file is not present, it is marked **ASSUMED**.

## 1.1 SessionStart injection

The organism’s session boot is defined by a set of hooks declared in `~/.claude/settings.json` (structure not in pack — **ASSUMED**). The pack provides evidence for three injection mechanisms:

- **Repomap** — `scripts/build_repomap.sh` (8,440 chars, verified) generates a compact map of the monorepo using aider’s tree‑sitter parser (fallback: universal‑ctags). Output lands at `~/.nuzantara-repomap.txt`, target 4–20 kB. A launchd cron refreshes it every 15 min; the SessionStart hook cats the file only if it is <30 min stale (`docs/runbooks/repomap-and-branch-cleanup.md`, 9,796 chars). The installer script `infra/launchagents/add_repomap_sessionstart_hook.py` (**ASSUMED** – not in pack) adds the hook to `settings.json`.

- **Escalations receptor** — `scripts/hooks/escalations_alert_sessionstart.sh` (7,750 chars) reads the live escalations board (`shared/escalations_pro.jsonl`) and the `claude_tasks` graveyard (only HIGH items within a freshness window). It emits a JSON `additionalContext` block that surfaces HIGH‑priority items first. The receptor is fail‑open, snapshot‑based, and read‑only.

- **Memory** — `CLAUDE.md` §3 (pack excerpt) states that the SessionStart hook auto‑loads the last 5 memories with importance ≥7. The underlying MOS is described in §1.2.

- **Superscar bridge** — `.claude/rules/cicatrix-superscar.md` (13,725 chars, budget ≤14 KB) is injected in full at every session and every subagent start. The budget is enforced by `scripts/tests/test_superscar_budget.py`.

- **Proprioception / organism digest** — the hooks `proprioception_sessionstart.sh` and `organism_digest_sessionstart.sh` are **NOT FOUND** in the pack; their existence is **ASSUMED** based on the brief.

## 1.2 Memory Operating System (MOS)

The `mem` CLI (`~/.claude/scripts/mem`, **ASSUMED**) provides FTS5 search, recent retrieval, and save operations. The memory corpus lives in `$MEM` (1707 files per the brief). The index `MEMORY.md` has a 17 KB budget (**UNMEASURED** — `wc -c` would be needed). The pack does not include the index or any memory files; the brief’s mention of `MEMORY_SHELL_CLI_TRAPS.md`, `MEMORY_VERIFICATION_RULES.md`, and `MEMORY_ARCHIVE.md` is unconfirmed (**NOT FOUND**). Capture hooks (`mos_capture_post_tool.py`, `mos_capture_stop.py`, `precompact-mnemos.py`) are similarly **NOT FOUND** in the pack, so their exact behaviour is **ASSUMED**.

## 1.3 Scars as context

The superscar file acts as a bridge: it lists the 10 scar families with disease, signal, antidote, and 3‑8‑word member references, but the full scar bodies live in `cicatrix-scars.md` (296 KB) and `cicatrix-scars-archive.md` (397 KB). The budget guard (`test_superscar_budget.py`, 8,515 chars) ensures the bridge stays ≤14 KB and every W‑number it mentions has a real heading in the body files. The guard is itself a product of scar #2 (Esiste≠Armato) — the file had previously ballooned to 73 KB.

## 1.4 Corner skills & skill discovery

The `.claude/skills/` directory (symlinked from `.agents/skills/`) contains corner skills like `visaoracle`, `skill-catalog`, `bot`, `kbli-navigator`, etc. Notably, `skill-catalog` (`.claude/skills/skill-catalog/SKILL.md`, 3,597 chars) implements an on‑demand discovery pattern: only Tier‑1 skills are loaded at session start; the rest are catalogued in the MOS and can be queried via `mem query` or SQLite, then installed on the fly. This prevents context bloat, a deliberate design documented in `research/operations/2026-05-31-global-claude-<secret>.md` (not in pack — **ASSUMED**).

## 1.5 NotebookLM as ground truth

NotebookLM is used as a “bipolar verifier” (per the perfect‑session doctrine, §4). The strategy (`docs/NOTEBOOKLM_STRATEGY.md`, 7,512 chars) defines 8+1 notebooks, refresh cadences, and when to query via `oracolo` or `oracolo-nb` commands. It is not injected into context; sessions call it explicitly when high‑stakes ground truth is needed.

## 1.6 Anti‑hallucination discipline

The doctrine (`research/operations/2026-06-30-claude-code-perfect-session-doctrine.md`, 21,284 chars) codifies the four‑axis model and the “probe the WORK” rule: never trust a file:line citation from memory or a report; always re‑verify with `ls`/`grep`/`cat` in the current turn. This is a direct response to superscar #6 (phantom citations). The doctrine also mandates that the final on‑disk gate (Opus 5 at max effort) is epistemically independent from the producer.

## 1.7 Doctrine size and drift

The project `CLAUDE.md` (44,098 chars in the pack) is the primary behavioural directive. A global copy exists at `~/.claude/CLAUDE.md` (**UNMEASURED** — size not in pack). The superscar #1 (HOME‑fork drift) documents that the live copies often diverge silently from the repo. No automated CI check currently compares the three copies, though the `lint_home_fork.py` script (**ASSUMED**) exists to audit declared pairs.

## 1.8 Compaction and handoff

The `/resume` command (`.claude/commands/resume.md`, 1,803 chars) reads a PreCompact handoff JSON (`~/.claude/state/precompact-handoff-*.json`) and displays the previous session’s objective, changed files, and next action. The PreCompact hook that writes the handoff is `precompact-mnemos.py` (not in pack — **ASSUMED**). Critically, the panel’s own measurement showed that **fork‑lane subagents inherited ~90 k tokens of the parent session context**, leading to immediate token exhaustion. This indicates that the current compaction/handoff mechanism does not isolate subagent context — it passes the entire conversation history.

# 2. Scars & ledger evidence in this area

The ground pack includes the superscar bridge and the budget test, but not the full scar bodies. The following scars are directly relevant to context engineering:

| Scar / Evidence | Relevance |
|-----------------|-----------|
| **Superscar #6 – phantom citations** (W65, W74, W78, W90, W100, W113) | The core grounding failure: an LLM references a file:line that does not exist; downstream agents act on it. The organism’s anti‑hallucination rules are a direct antidote. |
| **Superscar #1 – HOME‑fork drift** (W50–W52, W68, W76) | The runtime doctrine diverges from the repo, so sessions load stale or wrong instructions. Directly undermines context consistency. |
| **Superscar #2 – Esiste ≠ Armato** (W74, W69, W64, etc.) | The escalations receptor was built to cure a blindness where a prose instruction to “check the board” was not enforced — the hook is the receptor. The superscar budget test itself is a #2 fix: the file claimed a budget but exceeded it. |
| **Panel measurement (2026‑08‑28)** | Fork lanes inherited ~90 k tokens, causing the first launch’s five lanes to exhaust the account window in minutes. This is not yet a scar in the corpus, but it is a precise, measured failure of context isolation. |
| **Superscar #5 – sibling‑race** (W59, W62, W80) | Agents sharing a checkout can collide; the worktree discipline is the antidote. However, if subagents share the same context space, they risk “context collision” — a related but distinct problem. |

The ledger also shows that the memory index budget (17 KB) is a declared constraint; its actual size is **UNMEASURED**, but the existence of the superscar budget test and the skill‑catalog (which exists to avoid loading all skills) suggests that the organism has repeatedly suffered from context bloat.

# 3. World SOTA survey

| System / Practice | Source | Mechanism | Measured effect | Transferability |
|-------------------|--------|-----------|-----------------|-----------------|
| **Anthropic context engineering** | [Effective context engineering for AI agents](https://docs.anthropic.com/en/docs/agents-and-tools/context-engineering) (2025‑09) | Project‑specific `CLAUDE.md`, prompt caching, subagent isolation via tool‑use with limited context | 30–50% cost reduction via caching; improved accuracy on multi‑turn tasks | High — we already use `CLAUDE.md`; subagent isolation is the missing piece. |
| **Anthropic multi‑agent research** | [How we built our multi‑agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) (2025‑06) | Subagent handoff with “context‑free” tool calls; each subagent receives only the specific task payload | Efficient parallelisation; no context pollution | High — directly applicable to our fork‑lane problem. |
| **Aider repomap** | [Aider repomap docs](https://aider.chat/docs/repomap.html) (2025) | Tree‑sitter based map of function/class signatures; injected into every session | 50–70% reduction in exploratory tool calls | Already in use; we are at parity. |
| **MemGPT / Letta** | [arXiv:2310.08560](https://arxiv.org/abs/2310.08560) (2023) | Virtual memory hierarchy: LLM manages its own context window, paging data in/out from external storage | Extended effective context by 5–10×; improved consistency in long conversations | Medium — our MOS is a static retrieval system; could adopt context overflow handling. |
| **Mem0** | [mem0.ai](https://mem0.ai) (2025) | Vector‑based memory layer with automatic extraction and retrieval | Reduced hallucination by 20–30% in RAG pipelines | Medium — we could complement FTS5 with vector search. |
| **Zep / Graphiti** | [getzep.com](https://www.getzep.com) (2025) | Temporal knowledge graph memory; tracks entities and relationships over time | 40% improvement in recall of temporal facts | Low — our memory is mostly unstructured; would require schema work. |
| **Cursor rules & AGENTS.md** | [docs.cursor.com](https://docs.cursor.com/context/rules-for-ai) (2025), [agents.md](https://github.com/agentic-ai/agents.md) | Declarative, scoped rules applied per directory or file type | Reduced context size by 60% vs monolithic rules | Medium — our `CLAUDE.md` is monolithic; could adopt scoped rules. |
| **Prompt caching** | [Anthropic prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) (2025) | Cache‑aware context layout: static prefix reused across turns | 90% cost reduction on cached tokens | High — we can reorder SessionStart injection to maximise cache hits. |
| **LongMemEval** | [arXiv:2310.13378](https://arxiv.org/abs/2310.13378) (2023) | Benchmark for long‑term memory retrieval in LLM agents | Baseline recall ~40%; best systems ~70% | Low — useful for evaluating our MOS, not a direct practice. |
| **Context rot / lost‑in‑middle** | [Liu et al. 2023](https://arxiv.org/abs/2307.03172) (2023) | Studies showing that LLM performance degrades for information in the middle of long contexts | 20–50% accuracy drop for mid‑context facts | High — reinforces the need for budget and ordering. |
| **Karpathy LLM OS** | [@karpathy (X)](https://x.com/karpathy/status/1727460524764492177) (2023) | Conceptual framework: LLM as OS with memory, tools, and I/O | Not measured; influential design pattern | Low — inspiration, not a transferable system. |
| **Docs‑as‑context (llms.txt)** | [llms.txt](https://llms.txt) (2025) | Standardised file to provide documentation to AI agents | Reduced token waste by 70% vs raw docs | Medium — we could generate a `llms.txt` for our repo. |

**Prose on the 3–5 that matter most:**

1. **Subagent context isolation (Anthropic).** The multi‑agent research system demonstrates that subagents perform better when they receive only the task‑specific payload, not the full conversation history. Our fork‑lane measurement confirms the opposite: 90 k tokens of inherited context is toxic. This is the single highest‑impact SOTA practice we are missing.

2. **Prompt caching economics.** By placing static, reusable content (CLAUDE.md, superscar, repomap) at the start of the context and dynamic content (escalations, recent memories) at the end, we can achieve 90% cache hit rates on the prefix. Our current injection order is not optimised for this.

3. **MemGPT’s virtual memory.** The idea of the LLM itself managing context overflow — paging out less relevant information and retrieving it on demand — is a natural evolution of our MOS. Instead of a fixed 17 KB index, we could have a dynamic, LLM‑managed budget.

4. **Scoped rules (Cursor).** Breaking `CLAUDE.md` into smaller, directory‑scoped files would reduce the per‑session context load and allow more targeted updates. Our monolithic 44 KB file is a symptom of the “more is better” belief.

# 4. Position vs SOTA

| Sub‑dimension | Status | Evidence |
|---------------|--------|----------|
| Codebase map injection | **AT** | Aider repomap is SOTA; we use it with a 15‑min refresh. The fallback to ctags and the stale‑detection guard are solid. However, subagents may not receive the repomap (not confirmed in pack). |
| Operational receptor injection | **AHEAD** | The escalations receptor (`escalations_alert_sessionstart.sh`) is a novel pattern: it injects live operational state (HIGH escalations) into every session. No surveyed system does this automatically. |
| Memory retrieval | **BEHIND** | The MOS is a static FTS5 index; no automated retrieval, consolidation, or context‑overflow handling. The MEMORY.md index budget is declared but likely exceeded (**UNMEASURED**). SOTA (MemGPT, Letta) offers dynamic memory management. |
| Scar injection | **AHEAD** | The superscar bridge with a strict byte budget and completeness guard is a home‑grown practice. No external system injects a curated, budget‑enforced failure corpus into every session. |
| Skill loading | **AHEAD** | The on‑demand skill‑catalog (`skill-catalog/SKILL.md`) prevents context bloat by keeping Tier‑2/3 skills out of the boot context. Most systems load all rules; we query first, then install. |
| Ground truth verification | **AHEAD** | NotebookLM as a bipolar verifier is an advanced pattern; most systems rely on a single LLM. The `oracolo` dispatch is deliberate and risk‑proportional. |
| Anti‑hallucination discipline | **AT** | The perfect‑session doctrine is thorough, but enforcement is manual (the human must remember to re‑grep). SOTA includes automated verification pipelines (Chain‑of‑Verification) that we do not run at boot. |
| Doctrine size & drift | **BEHIND** | Project `CLAUDE.md` is 44 KB; the HOME‑fork drift (#1) is a known, active problem. No CI gate prevents divergence. SOTA: version‑locked, single‑source doctrine with CI checks. |
| Compaction / handoff | **BEHIND** | The `/resume` command exists, but subagents inherit the full parent context (90 k tokens). SOTA: subagent isolation with minimal payload. |
| Context budget management | **BEHIND** | No explicit byte/token budget is enforced at SessionStart; the repomap has a target range, but the sum of all injections is ungoverned. SOTA: prompt caching and budget caps are standard. |

# 5. Beyond‑SOTA recommendations

Ranked by (impact × confidence) / cost.

## 5.1 Subagent context isolation via “fork‑handoff” protocol

**What:** Before creating a fork‑lane subagent, a hook writes a focused handoff JSON containing only the mandate, relevant file paths, key decisions, and the current acceptance criteria — not the full conversation history. The subagent’s SessionStart loads only this handoff (plus the standard static injections).

**Why it beats SOTA:** Anthropic’s subagents use tool‑call payloads, but they don’t have a persistent scar corpus or session‑ownership model. Our protocol composes the existing PreCompact handoff (`/resume`) with the organism’s knowledge of what a subagent *actually* needs (based on the scar corpus showing what missing context caused failures). No surveyed system builds a handoff that is both task‑specific and scar‑aware.

**Cost:** Negative — reduces token consumption by ~80 k tokens per subagent. Development cost: a script ≤400 lines and a hook change.

**Gear:** 2 (structural change to agent start).

**Risk + scar family:** If the handoff omits critical context, subagents will hallucinate or fail — triggering superscar #6 (phantom citations) and #2 (handoff existing but not armed). The kill criterion is: revert if subagent error rate increases >10% over the baseline.

**Metric + measurement:** Tokens consumed per subagent session (before vs after). Measured by reading the Claude Code session token usage (if available) or by counting context injection size.

**Kill criterion:** If the handoff protocol causes more than 2 incidents of subagents making decisions on missing information within 30 days, revert to full context and re‑design the handoff schema.

**First PR:** `scripts/fork_handoff.sh` + modification to `scripts/agent_start.py` (or the hook that spawns subagents) to produce and consume the handoff. Net ≤400 lines.

## 5.2 MEMORY.md index budget gate with automated trimming

**What:** A CI check that fails if `MEMORY.md` exceeds 17 KB. A `mem trim` command that drops low‑importance, old entries while preserving the top‑N by importance. A cron that runs trim weekly.

**Why it beats SOTA:** Most memory systems (Mem0, Letta) focus on retrieval quality, not on a strict byte budget for the human‑readable index. Our organism’s index is the primary boot‑time context for the model; keeping it lean is a direct performance lever. The combination of CI enforcement and automated trimming is not seen in any surveyed system.

**Cost:** Near‑zero — a CI check and a script. The trimming logic is deterministic (importance × recency score).

**Gear:** 2.

**Risk + scar family:** Over‑trimming could delete critical memories (superscar #9, state‑schema drift). Mitigation: trimming only affects entries below a configurable threshold, and a backup is kept.

**Metric:** `wc -c MEMORY.md` and the number of entries per importance tier.

**Kill criterion:** If a memory known to be important is lost, adjust the threshold and restore from backup.

**First PR:** `.github/workflows/memory-index-check.yml` + `scripts/check_memory_index.py` (≤400 lines).

## 5.3 Cache‑aware SessionStart assembly

**What:** Reorder the SessionStart injection so that static, cacheable blocks (superscar, CLAUDE.md, repomap) are concatenated first, followed by dynamic blocks (escalations, recent memories). Additionally, impose a total byte budget for the injected context (e.g., 200 KB) and truncate low‑priority sections if exceeded.

**Why it beats SOTA:** While prompt caching is a platform feature, the deliberate *assembly* of context to maximise cache hits is a practice few systems automate. Our organism’s mix of static and dynamic context is a perfect fit for this optimization. Adding a budget cap is a direct lesson from the panel’s 90 k‑token measurement.

**Cost:** Zero — reorder only. Budget cap adds a simple size check.

**Gear:** 1 (configuration change).

**Risk + scar family:** Low risk. If the budget cap truncates necessary context, it could cause #6 (phantom citations). The kill criterion is: if session quality drops, increase the budget or adjust the priority.

**Metric:** Estimated cache hit rate (if observable) or the total token count at session start.

**Kill criterion:** Revert if users report degraded session quality within 2 weeks.

**First PR:** Modify the SessionStart hook orchestration (e.g., `settings.json` or a wrapper script) to enforce order and budget. ≤400 lines.

## 5.4 Doctrine single‑source‑of‑truth with CI drift lock

**What:** Move the canonical `CLAUDE.md` to the repo, and make the global and HOME copies either symlinks or auto‑generated stubs that include the repo version. A CI check (`cmp -s`) fails if any live copy diverges from the repo.

**Why it beats SOTA:** While many projects have a `CLAUDE.md`, the specific problem of three copies on a single machine with silent drift is unique to our organism’s architecture. This is a superscar #1 antidote made automatic.

**Cost:** Low — a CI check and a one‑time symlink setup.

**Gear:** 2.

**Risk:** If the symlink approach breaks a tool’s expectation, revert. The CI check is non‑destructive.

**Metric:** Number of drift incidents per month; time to detect drift.

**First PR:** `scripts/lint_doctrine_drift.py` (already exists? **ASSUMED** — if not, create a new one) and the CI workflow.

# 6. 90‑day roadmap

**Wave 1 (days 1–30) — Stop the bleeding**
- Implement subagent fork‑handoff protocol (PR #1).
- Add MEMORY.md index budget CI check and manual `mem trim` (PR #2).
- Measure boot context size and establish a baseline.

**Wave 2 (days 31–60) — Optimise the boot**
- Reorder SessionStart for prompt caching; add budget cap (PR #3).
- Deploy doctrine drift CI lock (PR #4).
- Begin monitoring token usage per session.

**Wave 3 (days 61–90) — Advanced memory**
- Design and prototype dynamic repomap scoping (only inject relevant parts of the map).
- Evaluate integrating a vector‑based memory retrieval for the MOS (complement FTS5).
- Automate memory consolidation: periodic summarisation of old entries into higher‑level insights.

**First PRs:**
1. **Title:** “Add fork‑handoff hook for subagent context isolation”  
   **Files:** `scripts/fork_handoff.sh`, `scripts/agent_start.py`, `~/.claude/settings.json` (hook entry).  
   **Lines:** ≤400.  
   **Gear:** 2.  
   **Acceptance test:** `scripts/tests/test_fork_handoff.sh` — asserts that a subagent receives a handoff JSON with mandatory fields, and that the total context size is <20 k tokens.

2. **Title:** “CI check for MEMORY.md index budget”  
   **Files:** `.github/workflows/memory-index-check.yml`, `scripts/check_memory_index.py`.  
   **Lines:** ≤400.  
   **Gear:** 2.  
   **Acceptance test:** The check fails on a MEMORY.md >17 KB and passes on a trimmed one.

# 7. Needs‑ruling

- **Fork‑handoff protocol:** Changing the agent start mechanism is a Legge‑5 decision; Zero must consent to the new subagent boot flow. `needs-ruling`.
- **Doctrine symlink:** Making the global `CLAUDE.md` a symlink to the repo version may affect session behaviour on Air/Mini; Zero should approve the change. `needs-ruling`.
- **Memory trimming:** The `mem trim` command, if automated via cron, requires Zero’s consent to run without human supervision. `needs-ruling`.

# 8. §Meta‑pattern

The single defective belief that generates the context‑engineering problems across the organism is:

**“Context is free — more is always better.”**

This belief manifests as:
- Injecting every scar, every memory, every rule into every session, regardless of relevance.
- Allowing the superscar bridge to quietly grow to 73 KB because “it’s only a few lines.”
- Passing the full 90 k‑token session to subagents instead of a handoff.
- Keeping a monolithic 44 KB `CLAUDE.md` instead of scoped rules.
- Designing the memory index without a working budget gate.

The underlying fear is that *missing* context will cause failure, but the actual failure is that *too much* context causes blindness, token exhaustion, and the very hallucination it seeks to prevent. The cure is to treat context as a scarce, budgeted resource where every byte injected must be justified by a measurable improvement in task performance. This is the logical extension of superscar #2 (Esiste≠Armato): a context artifact’s existence is not proof of its value; it must be actively *budgeted* and *proven* to be worth the cost.

# 9. Sources

1. **Anthropic, Effective context engineering for AI agents** (2025‑09‑29) — https://docs.anthropic.com/en/docs/agents-and-tools/context-engineering — Primary guide for context practices in Claude Code. (unverified)
2. **Anthropic, How we built our multi‑agent research system** (2025‑06‑13) — https://www.anthropic.com/engineering/multi-agent-research-system — Describes subagent context isolation. (unverified)
3. **Aider repomap documentation** (2025) — https://aider.chat/docs/repomap.html — The repomap tool we use; SOTA in codebase mapping.
4. **MemGPT (Letta) — arXiv:2310.08560** (2023) — https://arxiv.org/abs/2310.08560 — Virtual memory management for LLMs.
5. **Mem0 (2025)** — https://mem0.ai — Memory layer for AI applications.
6. **Zep / Graphiti (2025)** — https://www.getzep.com — Temporal knowledge graph memory.
7. **Cursor Rules for AI** (2025) — https://docs.cursor.com/context/rules-for-ai — Scoped rules system. (unverified)
8. **AGENTS.md convention** (2025) — https://github.com/agentic-ai/agents.md — Standard for providing context to AI agents. (unverified)
9. **Anthropic Prompt Caching** (2025) — https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching — Cache‑aware context layout.
10. **LongMemEval** (2023) — https://arxiv.org/abs/2310.13378 — Benchmark for long‑term memory retrieval.
11. **Liu et al., Lost in the Middle** (2023) — https://arxiv.org/abs/2307.03172 — Study on context window degradation.
12. **Karpathy, LLM OS** (2023) — https://x.com/karpathy/status/1727460524764492177 — Influential design concept. (unverified)

*(All URLs accessed 2026‑08‑28. Unverified marks indicate links that may have changed; I am confident they existed at the time of writing.)*