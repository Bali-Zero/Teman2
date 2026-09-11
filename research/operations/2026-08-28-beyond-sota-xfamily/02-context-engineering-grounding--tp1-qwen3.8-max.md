---
panel: beyond-sota-xfamily
lane: 02-context-engineering-grounding
seat: tp1-qwen3.8-max
model: "qwen3.8-max · enable_thinking · TP1 API, no tools, ground pack"
started: 2026-08-28T16:39:58Z
finished: 2026-08-28T16:47:20Z
duration_s: 442
exit: 0
words: 4648
prompt_sha256_16: 7142885ec337c344
prompt_chars: 165561
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
model: Qwen3.8 Max (pinned lane)
status: complete
sections_done: 0-9
sources: 16
repo_files_verified: 16
---

**Method note (anti-hallucination, stated up front):** this lane has NO shell/file/web access. Every repository claim below is grounded in the appended GROUND PACK (16 redacted excerpts). Pack-declared character counts are treated as size evidence and labelled *chars* (not bytes). Anything not supportable from the pack is marked **ASSUMED**; every uncomputable measure is **UNMEASURED** with the exact command. The SOTA survey is from model knowledge (no live fetch possible in this lane); uncertain URLs are marked `(unverified)`; “accessed 2026-08-28” means recalled-from-training, not fetched. The output file is returned as this message per the lane contract; I could not `ls -la`/`wc -w` it — verifier command: `ls -la /Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828/research/operations/2026-08-28-beyond-sota-context-engineering-grounding.md && wc -w $_`.

---

## 0. TL;DR

Position: **AT SOTA on injection architecture (hooks-as-receptors, budgeted scar injection, aider repomap) and AHEAD of every surveyed system on failure-memory-as-context; BEHIND on context telemetry, doctrine size control, and memory consolidation.**
Biggest gap: the organism has **no boot-time context receipt** — it discovers context overload only after it bites (superscar silently at 73,854 bytes; fork lanes inheriting ~90K tokens; a 135,221-char corner skill).
Top-3 moves:
1. **Boot-Manifest Tripwire** — CI+hook that measures every injected artifact against a declared byte budget and prints a one-line receipt per session (generalizes `test_superscar_budget.py`).
2. **HEAD/BODY split for corner skills** — visaoracle-class live-state files load a ≤8KB head; body on demand (−94% corner-open cost).
3. **Staleness-tagged injection** — every injected artifact carries `rev: origin/main-sha:content-sha`; SessionStart stamps `STALE(n)` when the checkout lags (kills the W76/stale-superscar class).

---

## 1. How Nuzantara does it today

Verification basis: GROUND PACK only. Files marked NOT FOUND in pack (`proprioception_sessionstart.sh`, `organism_digest_sessionstart.sh`, `MEMORY_*` bodies, `mos_capture_*.py`, `precompact-mnemos.py`, `.mcp.json`, `modus/SKILL.md`, the two `$MEM` discovery files) are cited only where pack-verified files reference them, and then as **ASSUMED**.

### 1.1 SessionStart receptor layer (BOOT organ)

The doctrine names the design principle: “a hook is a receptor; documentation is not” (`research/operations/2026-06-30-claude-code-perfect-session-doctrine.md`, §2 organ 1 BOOT, which lists “SessionStart hooks (15)”). The pack verifies one receptor in full and the injection path for two more:

- **Escalations receptor** — `scripts/hooks/escalations_alert_sessionstart.sh`: reads `shared/escalations_pro.jsonl` + `~/.agent/decisions/claude_tasks/`, surfaces HIGH-first, capped at 12 items, one-line NORMAL count. Deliberate engineering: hard 4s budget, fail-open (any error → exit 0), SNAPSHOT-not-graveyard (14-day freshness window over a “500+ file graveyard”), net-pending logic for an append-only JSONL (a resolved entry only closes pendings appended before the resolution ts), dedupe, kill-switch `ESCALATIONS_RECEPTOR_ENABLED=false`. Output is `hookSpecificOutput.additionalContext` JSON.
- **Repomap injection** — `docs/runbooks/repomap-and-branch-cleanup.md`: a SessionStart hook in `~/.claude/settings.json` (catch-all bucket) cats `~/.nuzantara-repomap.txt` **only if <30 min stale**; installer `infra/launchagents/add_repomap_sessionstart_hook.py` (idempotent, marker-guarded). Contents of `settings.json` itself: **UNMEASURED** (not in pack) — verify: `python3 -c "import json;d=json.load(open('/Users/nuzantara/.claude/settings.json'));print(json.dumps(d.get('hooks',{}),indent=1)[:4000])"`.
- **Proprioception + organism digest receptors** — named in the lane brief; files NOT FOUND in pack → existence and output size **ASSUMED**.
- **Memory auto-load** — `CLAUDE.md` §3: “SessionStart hook auto-loads last 5 memories (importance ≥7)” — verified as doctrine; the implementing hook code is not in pack (**ASSUMED** mechanism).

### 1.2 Repo map (structural grounding)

`scripts/build_repomap.sh`: aider tree-sitter `--show-repo-map` (pinned pyenv binary, `--map-tokens 1024`, `--no-gui --no-browser`, 180s timeout) with universal-ctags JSON fallback (top-100 files by symbol count, ≤15 names/kind, tests excluded). Output `~/.nuzantara-repomap.txt`, target **4–20kB** (~1–5k tokens), warn <1kB or >30kB, 15-min refresh via `com.nuzantara.repomap.15min` launchd. Kill-switch `REPOMAP_ENABLED=false`. Explicit scar-driven excludes (`.next`, `dist`, `*.min.js`…) after the “2026-06-13 connectome audit: ctags fallback indexed minified webpack chunks, **188kB of noise injected into every session** instead of the 4–20kB target” (W64 lineage). The runbook claims “saves ~50 exploratory tool calls per cold session” over the 82,970-file / 33-app monorepo.

### 1.3 MOS — memory operating system

`CLAUDE.md` §3 defines: `mem` CLI (`recent`/`query` FTS5/`save`/`entities`/`sessions`/`stats`), proactive-save obligation (decision 8–10, discovery/fact 7–8, unresolved 5–6, “NON chiedere all'utente. Salva e basta”), and the rule `mem` PRIMA di `notebook_query`. Corpus: **1,707 files** under `$MEM` with `MEMORY.md` as index at a stated **17 KB budget** (lane brief). Index file, CLI script, capture hooks (`mos_capture_post_tool.py`, `mos_capture_stop.py`, `precompact-mnemos.py`) NOT FOUND in pack → **ASSUMED** as existing per brief.
**UNMEASURED** (exact commands):
- index vs budget: `wc -c "$MEM/MEMORY.md"`
- files by type prefix: `ls "$MEM" | awk -F_ '{print $1}' | sort | uniq -c | sort -rn`
- pointer-vs-content share: `grep -cE '\]\(|\.md\)' "$MEM/MEMORY.md"` vs `wc -l < "$MEM/MEMORY.md"`

### 1.4 Scars-as-context

`.claude/rules/cicatrix-superscar.md` (13,725 chars in pack): 10 families, “PONTE, non enciclopedia”, **injected to every session AND every subagent**, budget **≤14KB** armed by `scripts/tests/test_superscar_budget.py` — a triple guard: (1) byte budget 14,000; (2) completeness: every `W\d+[a-z]?` token must resolve to a `##/###/####` heading in `cicatrix-scars.md` or `-archive.md`; (3) all three scar files must be `.prettierignore`d (W112 corruption scar). The header itself carries a context-engineering warning: on machines deliberately held behind (M5, “centinaia di commit”), **the injected copy and the copy `scar` reads are both stale**; the authority is `git show origin/main:<path>`.

### 1.5 Doctrine layer and its drift

Measured from pack: project `CLAUDE.md` = **44,098 chars**; `SYMBIOSIS.md` = **38,155 chars**; `docs/AI_ONBOARDING.md` = 15,620 chars (on-demand, not boot); `docs/SYSTEM_BRIEF_FOR_AGENTS.md` = 12,214 chars (external-agent brief). Project CLAUDE.md visibly carries amendment layering (§5 routing amended 2026-07-02 → 07-25 → 08-14 → 08-19 → 08-20 rulings stacked in one section). Global `/Users/nuzantara/.claude/CLAUDE.md`: NOT in pack → **UNMEASURED** (`wc -c /Users/nuzantara/.claude/CLAUDE.md`). The hot-file list names the recorded discovery `discovery_the_global_claude_md_is_a_home_fork_three_copies_three_answers_2026_08_23.md` — file NOT FOUND in pack; its title plus superscar #1 members (W50/W51/W52, W76, W106b) ground the claim: **three machine copies of the global doctrine have produced three different answers** (content beyond title **ASSUMED**).

### 1.6 Corner skills and skill discovery

`.agents/skills/` lists 9 entries (README, bot, bz-video-production, google-flow-video, kbli-navigator, secondhome, subhi, visaoracle, wr2). `.claude/skills/visaoracle/SKILL.md` = **135,221 chars**: mission, ENFORCE-GATE with 7 preconditions, “Established truths (GROUND 2026-07-17, scout-verified file:line)”, and an append-only **LIVE STATE** section (“update on every state change — whoever changes state updates this section”). `.claude/skills/skill-catalog/SKILL.md` is the anti-bloat organ: “Claude Code loads ALL installed skill descriptions into context at session start. To avoid context bloat (the orchestration-decay 8→0 regression), only Tier-1 skills + a curated few are installed”; Tier-3 lives in the MOS catalog (`SKILL-CATALOG:` prefixed FTS5/LIKE rows), installed on demand, “NEVER pre-install Tier 2/3 in bulk”.

### 1.7 NotebookLM as ground truth

`docs/NOTEBOOKLM_STRATEGY.md`: 8+1 notebooks; NB-1 (Codebase & Architecture, 35 sources) refreshed daily 04:30 WITA by `scripts/nlm_nb1_daily_refresh.py` (diff-driven bundle regeneration); **“NB-9 is NEVER mixed into NB-1”** (web research would drown code truth); oracolo triggers codified (>2 modules touched → consult NB-1 before planning; RAG score <0.60 → domain notebook). `docs/NOTEBOOKLM_CAPABILITY_MATRIX.md`: measured query quality (2,500-word answer, 32 inline citations, 10 sources), cross-notebook federation, and an observed **honest abstention** (“this isn't in my sources”). The matrix also demonstrates self-grounding hygiene: stale references to the dismantled federation PoC are flagged, not silently kept.

### 1.8 Anti-hallucination + compaction/handoff

Anti-hallucination is superscar family #6: “mai costruire su un path citato senza `find`/`ls`/`cat` in QUESTO turno. Anche il refuter allucina (W65)” — lineage W65→W90→W100→W113. Compaction: `.claude/commands/resume.md` — zero-side-effect command; prints last 12 sessions (`resume-session-list.py`), locates newest `~/.claude/state/precompact-handoff-*.json`, renders a fixed schema (Session ID, Timestamp, Objective, Changed files, Verified commands, Risks, Next action), and **requires explicit y/n before any action**; anti-patterns named (merging multiple handoffs, auto-executing, deleting the handoff). The PreCompact writer (“T2.5”) is referenced but NOT FOUND in pack (**ASSUMED**).

### 1.9 Boot-injection budget — measured estimate (MEASURE items)

| Component | Size | Status |
|---|---|---|
| Project `CLAUDE.md` | 44,098 chars | MEASURED (pack) |
| `.claude/rules/cicatrix-superscar.md` | 13,725 chars (budget ≤14,000 B) | MEASURED (pack) |
| Repomap | target 4–20kB, typical 5–10kB | MEASURED band (runbook); live size **UNMEASURED**: `wc -c ~/.nuzantara-repomap.txt` |
| Escalations receptor output | ≤~1.5KB worst case (12×80-char + framing) | MEASURED bound (code) |
| Last-5-memories inject | ASSUMED ≤2KB | **ASSUMED** (CLAUDE.md §3) |
| Global CLAUDE.md, `MEMORY.md`, symbiosis-core, proprioception, organism digest | unknown | **UNMEASURED** |

Partial sum of measured parts ≈ **61–69KB ≈ ~15–17K tokens (≈4 chars/tok) ≈ 8% of a 200K window**; true total likely higher once the five UNMEASURED components land. Composite command: `wc -c /Users/nuzantara/.claude/CLAUDE.md CLAUDE.md .claude/rules/cicatrix-superscar.md "$MEM/MEMORY.md" ~/.nuzantara-repomap.txt` + dry-run each SessionStart hook and `wc -c` its stdout. Contrast: one full corner-skill load (visaoracle, 135,221 chars ≈ 34K tokens) costs ~2× the entire measured boot prefix; the panel's first launch inherited **~90K tokens** of session context per fork lane (brief).

---

## 2. Scars & ledger evidence in this area

| Evidence | What bit | Recurred? |
|---|---|---|
| Superscar relapse (test docstring, 2026-08-21 audit) | `cicatrix-superscar.md` measured **73,854 bytes** while claiming “~2k token” — the bridge secretly carried full TRAUMA/ANTIBODY bodies; paid by every session+subagent | Yes — the file exists to cure family #2 and relapsed into it |
| W64 (in `scripts/build_repomap.sh`) | ctags fallback indexed minified webpack chunks → **188kB of noise injected every session** vs 4–20kB target | Yes — fixed by excludes; fallback quality-drop logging added (“esistere ≠ armato”) |
| W76 (superscar #1 member) | repomap built over a **stale checkout** → sessions grounded in a map of a repo that no longer exists | Yes — superscar header now warns its own injected copy can be STALE on M5 |
| META 2026-06-05 (family #6) | 13-agent autopsy found **3 phantom file:line** citations propagated into plans | Yes — W65 refuter false-refutes, W78 wrong-scar-propagated |
| W90 → W100 → W113 | ground-truth verifier served a stale snapshot; blind agreement produced **7 false-clean of 8**; then “la correzione stessa mente” | Yes, 4-generation lineage |
| `docs/AI_ONBOARDING.md` DOCSYNC note | hardcoded quick numbers drifted **2–2.6× wrong** (88→158 routers, 244→635 services, 385→1104 tests, 7→4 channels) “because nothing gated them” — cured by machine-verified DOCSYNC line | Yes — W86 (DOCSYNC stale rejects innocent PR), W88 (content-not-SHA) |
| skill-catalog SKILL.md | “orchestration-decay **8→0 regression**” from loading all skill descriptions into context | Prevented-recurrence organ exists |
| Memory titles (hot-file list; bodies NOT FOUND in pack — title-level evidence only) | `discovery_the_global_claude_md_is_a_home_fork_three_copies_three_answers_2026_08_23`; `discovery_glob_over_a_tcc_protected_directory_returns_empty_not_an_error_2026_08_21` (silent-empty grounding trap) | Yes — superscar #1 dominance 65–75% with #2/#5/#4 |
| Panel first launch (brief) | 5 fork lanes inherited **~90K tokens** each and exhausted the account window in minutes | First occurrence; fixed by pinned fresh-context lanes + ground packs |

`PENDING-ARMS.md` (2.2MB, 1,080 rows) and `AMENDMENTS.md` (52KB) are not grep-able from this lane: **UNMEASURED** — `grep -n -i "context\|compaction\|stale\|repomap\|memory index" .claude/skills/modus/PENDING-ARMS.md | head -40` and same on `AMENDMENTS.md`.

**Pattern:** every row is the same shape — *an artifact present in context was treated as current, complete, and sized as claimed*. Staleness/bloat recurred across four generations (W76 → DOCSYNC drift → superscar relapse → fork inheritance), each time discovered post-hoc, each time cured locally (excludes, DOCSYNC line, byte test, fresh context) without a general instrument.

---

## 3. World SOTA survey

Survey method: no web tools in this lane; citations are from model knowledge with confident URLs; uncertain ones `(unverified)`; all “accessed 2026-08-28” = training recall. The organism's own doctrine (`research/operations/2026-06-30-claude-code-perfect-session-doctrine.md`) already cites sources 1, 2, 5, 6, 12, 13 — the frontier is read here; the gap is instrumentation, not awareness.

| # | System / practice | Source (date) | Mechanism | Measured effect (published) | Transfer here |
|---|---|---|---|---|---|
| 1 | Anthropic “Effective context engineering for AI agents” | anthropic.com/engineering/effective-context-engineering-for-ai-agents (2025-09) | Compaction, sub-agent context isolation, structured note-taking, just-in-time retrieval | Qualitative; design rules | Direct — codifies what /resume and ground packs improvise |
| 2 | Anthropic multi-agent research system | anthropic.com/engineering/built-multi-agent-research-system (2025-06) | Lead agent + parallel subagents; “context is a scarce resource”; token = coordination cost | ~90.2% improvement vs single-agent on internal research eval (as reported) | Direct — panel/fleet already shaped this way |
| 3 | Claude Code memory / CLAUDE.md + auto-compact | docs.claude.com/en/docs/claude-code/memory (2025–26) | CLAUDE.md as curated memory; `/compact`; auto-compaction thresholds | n/a | Organism exceeds it (hooks, budgets) but lacks its one missing piece: measurement |
| 4 | Cognition “Don't Build Multi-Agents” | cognition.ai/blog/dont-build-multi-agents (2025-06-12) | Full-context sharing; actions encode implicit decisions; context as decision graph | Qualitative | Explains why fork-lane inheritance of 90K tokens poisoned lanes — decisions without their rationale |
| 5 | MemGPT → Letta | arxiv.org/abs/2310.08560 (2023-10); letta.com/blog/sleep-time-compute (2025) `(unverified)` | Virtual context management: self-edited paging between main/external context; sleep-time consolidation | Letta reports +13–18% accuracy, ~5× compute reduction for sleep-time compute (also quoted in `SYMBIOSIS.md`) | CLI-only consolidation pass (R5); organism already cites it |
| 6 | Mem0 | arxiv.org/abs/2504.19413 (2025-04) | Extract→update pipeline over episodic memory; ADD/UPDATE/DELETE/NOOP decisions | ~26% relative accuracy gain over OpenAI memory on LOCOMO; ~91% lower p95 latency vs full context (approx.) | MOS has capture+FTS5 but no update/consolidation semantics |
| 7 | Zep / Graphiti | arxiv.org/abs/2501.13956 (2025-01) | Temporal knowledge graph of episodes; validity intervals | ~94.8% DMR accuracy; ~18.5% gain over MemGPT on LongMemEval (approx.) | Overkill for 1,707 files, but the “facts have validity windows” idea maps to staleness tags |
| 8 | A-MEM | arxiv.org/abs/2502.12110 (2025-02) | Zettelkasten-style dynamic linking; notes reorganize memory on arrival | Benchmark gains over Mem0 on LongMemEval subsets | `supersedes:` links in MOS (R5) |
| 9 | LongMemEval | arxiv.org/abs/2410.10813 (2024-10) | 500-question eval of 5 memory abilities (incl. knowledge updates, temporal reasoning) | Commercial assistants degrade up to ~30% in long-history settings | Template for the organism's own 20-question memory eval (R5) |
| 10 | LoCoMo | arxiv.org/abs/2402.17753 (2024-02) | Very-long multi-session conversational memory benchmark | RAG baselines far below full-context on multi-hop | Same |
| 11 | Lost in the Middle | arxiv.org/abs/2307.03172 (2023-07, TACL 2024) | U-shaped attention: middle of long context is under-used | Robust across models | Injection ORDER matters: rules at head/tail, snapshots middle/last |
| 12 | Chroma “Context Rot” | research.trychroma.com/context-rot (2025-07) | Performance degrades with input length even on trivially answerable tasks; redundancy amplifies | Cross-model empirical | Byte budgets are not bureaucracy — every injected byte taxes every turn |
| 13 | Aider repo map | aider.chat/docs/repomap.html (2024–26) | Tree-sitter symbols + PageRank selection under a token budget | n/a | Organism already runs it (1.2) — AT SOTA by construction |
| 14 | AGENTS.md convention | agents.md (2025) | Cross-tool standard for agent instructions | Ecosystem adoption | Validates CLAUDE.md-as-doctrine; no drift control either |
| 15 | llms.txt | llmstxt.org (2024-09) | Markdown-first docs surface for LLM consumption | Adoption across doc ecosystems | Validates SYSTEM_BRIEF_FOR_AGENTS.md approach |
| 16 | Anthropic prompt caching | docs.claude.com/en/docs/build-with-claude/prompt-caching (2024–26) `(unverified)` | Stable prefix → cache; TTL windows; read ≪ write ≪ base cost | Up to ~90% cost/latency reduction on cache reads | Flat-subscription world: benefit is latency/throughput, not $; layout still matters |

**The five that matter most.** (1)+(2) Anthropic's context engineering pair names exactly this lane's object — context as a budgeted, compactable, isolable resource — and both recommend *measurement-driven* compaction and subagent isolation; the organism practices both manually (ground packs, /resume) but does not meter either. (4) Cognition's decision-graph framing explains the panel's own measured failure: inheriting 90K tokens transmits conclusions stripped of the decision graph that justified them — fresh context plus a curated ground pack is the correct dual. (6)/(7) Mem0 and Zep show the frontier memory loop is **extract → update → validity-window**, not append-and-index; MOS stops at append-and-index. (12)+(11) Context rot and lost-in-the-middle convert “doctrine size” from aesthetics into a performance law: injected bytes are a per-turn tax and position inside the window changes compliance — which is why the 44KB CLAUDE.md and the unmeasured prefix order are concrete risks, not style issues.

---

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| SessionStart live-state injection (receptors) | **AHEAD** | `escalations_alert_sessionstart.sh`: fail-open, 4s budget, snapshot-not-graveyard, net-pending dedupe — surveyed systems ship static instruction files, not live board receptors |
| Repo structural map | **AT** | aider repomap with freshness gate (<30 min), byte band, noise scar fixed (W64, 188kB→4–20kB) |
| Failure-memory as context | **AHEAD** | Budgeted superscar (≤14KB) + CI completeness test injected to every session AND subagent — no surveyed equivalent |
| Skill discovery economics | **AHEAD** | `skill-catalog`: MOS-catalogued Tier-3, install-on-demand, anti-sprawl rule; measured disease it prevents (8→0 decay) |
| Ground-truth oracle usage | **AHEAD (practice)** | NB-1/NB-9 isolation, daily diff-driven refresh, bipolar-verifier role, observed honest abstention — tool is third-party, discipline is own |
| Anti-hallucination doctrine | **AT** | Family #6 antidote + stadio-zero GROUND organ are frontier-grade; enforcement is prose + honor system (no automated citation re-check in pack) |
| Compaction / handoff | **AT** | Structured handoff schema + explicit-confirm `/resume`; manual, unmeasured; behind Letta-style automated VCM |
| Episodic memory quality | **BEHIND** | FTS5 + importance flags; no extract/update/consolidation semantics (Mem0/Zep), no validity windows; SYMBIOSIS Pilastro 5 “dream” explicitly an unimplemented hypothesis |
| Doctrine size & drift | **BEHIND** | 44,098-char project CLAUDE.md with **no byte budget** (only superscar has one); three-copy divergence scarred (#1; “three copies three answers” memory); amendment layering visible in §5 |
| Context telemetry | **BEHIND** — biggest gap | No boot receipt anywhere in pack; every overload was discovered post-hoc (73,854B superscar; 188kB repomap; 90K fork inheritance; 135KB corner skill) |
| Cache/placement-aware layout | **BEHIND / UNMEASURED** | No evidence in pack of volatility-ordered prefix or cache-stability design |
| Subagent context isolation | **AT, improvised AHEAD** | Redacted size-capped ground packs + pinned fresh context beat naive fan-out; not yet codified into tooling |

---

## 5. Beyond-SOTA recommendations (ranked by impact × confidence / cost)

### R1 — Boot-Manifest Tripwire (context receipt + CI byte budgets)
**What:** a meta-hook + CI test that computes the full SessionStart prefix (global+project CLAUDE.md, SYMBIOSIS core, superscar, MEMORY.md index, repomap, last-5 memories, receptor outputs), writes a one-line receipt into the session (“BOOT 71.2KB ≈ 17.8K tok | 8.9% window | all budgets OK”) and appends to a ledger; CI fails when any injected artifact exceeds its declared budget (superscar ≤14KB exists; add CLAUDE.md ≤48KB, MEMORY.md ≤17KB, repomap ≤30KB, corner-skill heads ≤8KB).
**Why it beats SOTA:** every surveyed system *advises* budgets (Anthropic 2025-09); none *meters the whole boot prefix with CI enforcement*. Generalizes the organism's own proven pattern (`test_superscar_budget.py`).
**Cost:** ~1 day flat-sub tokens, ≤400 lines. **Gear:** 2.
**Risk:** family #2 (receipt green, nobody reads → alarm must fire on breach, not log), #3 (budget checks must test content hash, not name substring). **Metric:** boot bytes p50/p95 per session; budget-breach count in CI (before: 3 post-hoc discoveries in 4 months; target: 0 undetected). Method: ledger parse + `wc -c` spot audits.
**Kill criterion:** breach alarm fires >3×/week with no actionable fix → demote to weekly digest.
**First PR:** `scripts/tests/test_context_boot_budget.py` + `scripts/context_boot_manifest.py`.

### R2 — HEAD/BODY split for corner skills (live-state lazy loading)
**What:** mandate: corner `SKILL.md` ≤8KB head (mission, gates, latest LIVE-STATE handoff block, “read BODY before any ENFORCE-class action”); append-only `LIVE-STATE.md` body loaded on demand; byte test in CI.
**Why it beats SOTA:** surveyed RAG-over-docs systems retrieve chunks; none enforces an append-only live-state contract with a CI-tested head/body boundary.
**Cost:** hours. **Gear:** 2.
**Risk:** #6 — a session acts on head alone where body was required (mitigate: head must list every gate whose satisfaction lives in body, as visaoracle's 7-precondition ENFORCE-GATE already does). **Metric:** corner-open context cost: before 135,221 chars (≈34K tok); after ≤8KB head (≈2K tok) −94%; count of “head insufficient” scars (target 0).
**Kill criterion:** two recurrences of head-insufficiency → raise head budget or abandon split.
**First PR:** visaoracle split: `.claude/skills/visaoracle/SKILL.md` (head) + `.claude/skills/visaoracle/LIVE-STATE.md` (body, verbatim move).

### R3 — Staleness-tagged injection (authority receipt)
**What:** every injected artifact emits `rev: <origin/main sha>:<content sha256[:12]>`; SessionStart compares against `git rev-parse origin/main` and stamps `STALE(n commits behind — authority: git show origin/main:<path>)`. Superscar already documents this failure in prose; this makes it a receptor.
**Why it beats SOTA:** doctrine Axis 2 (authority/canonicality) as a stamped receipt — no surveyed memory system handles *deliberate multi-machine checkout lag*, an asymmetry unique to this organism.
**Cost:** ≤1 day. **Gear:** 2.
**Risk:** #9 (header schema drift) → parser test; #2 if stamps ignored → pair with R1 receipt. **Metric:** scars mentioning stale-injected context (W76-class): before ≥3 in corpus; target 0 in 90 days.
**Kill criterion:** stamps ignored in 2 observed sessions (AMENDMENTS row) → escalate to hard block on stale superscar.
**First PR:** `scripts/hooks/inject_rev_check.sh` + unit tests with a synthetic behind-checkout.

### R4 — Ground-pack contract for fork lanes (codified isolation)
**What:** `scripts/ground_pack.py --lane <slug> --hot <files> --budget 150000` builds redacted, size-capped packs with explicit `NOT FOUND in snapshot` markers (this panel's exact mechanism), and bans raw-transcript inheritance for panels/forks.
**Why it beats SOTA:** Anthropic recommends subagent isolation; Cognition explains why inherited context poisons; the organism measured the failure (~90K tokens, window dead in minutes) and hand-rolled the fix — codification makes it fleet-reproducible.
**Cost:** hours. **Gear:** 2.
**Risk:** redaction drops a hot file → keep NOT FOUND markers + pack manifest (already present). **Metric:** lane turn-1 tokens (before ~90K inherited; after ≤ budget/4 ≈ 36K tok); lane completion rate.
**Kill criterion:** two lane stalls on the same missing file class → widen default hot-file set.
**First PR:** `scripts/ground_pack.py` with manifest + redaction rules.

### R5 — Volatility-ordered, cache-aware boot prefix
**What:** order injection by volatility — stable doctrine first (SYMBIOSIS core, CLAUDE.md), superscar second, MEMORY index third, live snapshots last (repomap, escalations) — freeze the stable prefix across sessions; A/B on modus-bench before adopting.
**Why it beats SOTA:** labs publish cache guidance and position effects separately; no surveyed agent OS composes both into an enforced layout.
**Cost:** hours + bench runs. **Gear:** 3.
**Risk:** reordering changes compliance (context rot placement) → bench-gated; #2 if cache metric is claimed without probe. **Metric:** prefix cache-hit share across consecutive same-machine sessions — **UNMEASURED** today: parse Claude Code session logs for cache_read tokens (`grep -i "cache" ~/.claude/projects/*/*.jsonl | head` — exact schema **ASSUMED**); target ≥60% stable-prefix hit; modus-bench delta ≤0.
**Kill criterion:** bench drops >5% → revert order.
**First PR:** reorder hook outputs + manifest annotation (depends on R1).

### R6 — MOS consolidation pass (Mem0-style extract/update, CLI-only)
**What:** nightly consolidator (`claude --print`, CLI-only per SYMBIOSIS Law 1) over recent `$MEM` bodies: proposes merges/supersedures as `supersedes:` links, silences (never deletes — genome pattern), gated by a 20-question self-built LongMemEval-style eval; diff-reviewable, reversible.
**Why it beats SOTA:** composes Mem0 update semantics + Letta sleep-time consolidation with something no surveyed system has: an eval harness made of the organism's own scar corpus and modus-bench.
**Cost:** highest of the six (tokens + eval authoring). **Gear:** 3.
**Risk:** consolidation amplifies errors (SYMBIOSIS cites 8.6× divergence) → human-gated apply for wave 1; #9 schema drift on memory headers. **Metric:** eval accuracy before/after; MEMORY.md bytes vs 17KB budget; active-corpus size (before: 1,707 files — prefix distribution **UNMEASURED**, command in §1.3).
**Kill criterion:** eval accuracy drops or one recidiva traced to a merge → halt consolidator, keep capture.
**First PR:** eval fixture (20 Q/A grounded in scars) + dry-run consolidator emitting diffs only.

---

## 6. 90-day roadmap + first PRs

**Wave 1 (days 0–30) — meter the boot:** R1 (budgets + receipt) and R2 (visaoracle head/body split). Measure baseline: full §1.9 command set, record prefix bytes per machine (M5 vs Pro vs Mini — path-awareness matters, superscar #1).
**Wave 2 (days 31–60) — tag authority, codify isolation:** R3 (rev stamps), R4 (`ground_pack.py`, used by the next panel for real), R5 experiment behind modus-bench.
**Wave 3 (days 61–90) — consolidate memory:** R6 pilot on one prefix family (e.g. `discovery_*`), eval-gated; retro against the §2 recurrence table: zero new stale/bloat scars is the pass condition.

| PR | Title | Files (≤400 net lines) | Gear | Acceptance test |
|---|---|---|---|---|
| 1 | Boot budget tripwire | `scripts/tests/test_context_boot_budget.py`, `scripts/context_boot_manifest.py` | 2 | Test FAILS when any injected artifact exceeds budget (seed oversized fixture); manifest JSON prints sum + per-file bytes |
| 2 | visaoracle HEAD/BODY split | `.claude/skills/visaoracle/SKILL.md`, `LIVE-STATE.md`, byte test | 2 | head ≤8KB; ENFORCE-GATE 7 preconditions verbatim in head; body = verbatim move (diff-empty content check) |
| 3 | Injection rev stamps | `scripts/hooks/inject_rev_check.sh` + tests | 2 | Synthetic behind-checkout → `STALE(n)` emitted; at-origin → no stamp |
| 4 | Ground-pack builder | `scripts/ground_pack.py` | 2 | Regenerates a sample lane pack ≤150K chars with NOT FOUND markers and manifest |
| 5 | Memory eval fixture | `scripts/tests/memory_eval/*.md` + runner | 3 | 20 Q/A each grounded to a scar W-number; runner exits non-zero below baseline |

---

## 7. Needs-ruling (Legge-5 only)

1. **PROD posture for NotebookLM as codebase ground truth (NB-1):** Law 2's DEV-phase suspension permits cloud tooling now; whether NB-1 (which ingests codebase bundles daily) remains acceptable after go-live, or must migrate to a Pro-bound mirror, is Zero's business decision.
2. **Doctrine canonicity:** which copy of the global CLAUDE.md (HOME vs repo-vendored vs per-machine) is the single authority sessions must obey — the “three copies, three answers” state needs an ownership ruling, not just a lint.
3. **Seat/window economics:** any spend beyond flat subscriptions to buy context capacity (extra seats, larger-window models) for panel work is Zero's. *(TCC grants for hook file access remain operator-only by category — the TCC-glob-empty scar shows silent failures there.)*

---

## 8. §Meta-pattern (modus Gear 3)

One defective belief generates every finding in this lane: **“injected (or existing) ⇒ present, current, and sufficient.”** Its incarnations: the superscar at 73,854 bytes claiming ~2k tokens (present ≠ sized); repomap over a stale checkout and the stale-superscar warning (present ≠ current); DOCSYNC numbers drifting 2–2.6× (present ≠ true); phantom file:line across the W65→W90→W100→W113 lineage (cited ≠ present); the 135KB corner skill and 90K-token fork inheritance (available ≠ relevant). The organism's own doctrine already names the cure for artifacts in general — *existence is not verified liveness* — but has not yet applied it to **the context itself**. The single move that collapses the pattern: treat every injected byte as a claim that carries a receipt — size budget (R1), freshness rev (R3), relevance manifest (R2/R4). Context is evidence, not inheritance.

---

## 9. Sources

All external sources recalled from training knowledge in-lane (no fetch capability); accessed 2026-08-28. Uncertain URLs marked `(unverified)`.

1. Anthropic Engineering — *Effective context engineering for AI agents* (2025-09-29). https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — the canonical framing of context as budgeted resource; compaction/isolation/just-in-time patterns.
2. Anthropic Engineering — *How we built our multi-agent research system* (2025-06-13). https://www.anthropic.com/engineering/built-multi-agent-research-system — subagent context isolation economics; multi-agent ~90.2% gain claim.
3. Anthropic — *Claude Code best practices*. https://www.anthropic.com/engineering/claude-code-best-practices — CLAUDE.md-as-memory practice baseline.
4. Anthropic Docs — *Claude Code memory*. https://docs.claude.com/en/docs/claude-code/memory — native memory/compaction semantics this lane positions against.
5. Cognition (Walden Yan) — *Don't Build Multi-Agents* (2025-06-12). https://cognition.ai/blog/dont-build-multi-agents — full-context sharing; actions as implicit decisions; explains fork-inheritance poisoning.
6. Packer et al. — *MemGPT* (2023-10). https://arxiv.org/abs/2310.08560 — virtual context management; self-editing memory.
7. Letta — *Sleep-time compute* (2025). https://www.letta.com/blog/sleep-time-compute `(unverified)` — consolidation accuracy/compute numbers (independently quoted in `SYMBIOSIS.md`).
8. Mem0 team — *Mem0: scalable long-term memory* (2025-04). https://arxiv.org/abs/2504.19413 — extract→update memory pipeline; LOCOMO gains.
9. Zep/Graphiti (2025-01). https://arxiv.org/abs/2501.13956 — temporal knowledge-graph memory; LongMemEval results.
10. A-MEM (2025-02). https://arxiv.org/abs/2502.12110 — dynamic Zettelkasten linking for agentic memory.
11. LongMemEval (2024-10). https://arxiv.org/abs/2410.10813 — 5-ability memory eval; long-session degradation figures; template for R6 eval.
12. LoCoMo (2024-02). https://arxiv.org/abs/2402.17753 — long conversational-memory benchmark.
13. Liu et al. — *Lost in the Middle* (2023-07; TACL 2024). https://arxiv.org/abs/2307.03172 — position effects inside long context.
14. Chroma — *Context Rot* (2025-07). https://research.trychroma.com/context-rot — length-driven degradation even on easy tasks; byte-tax justification.
15. Aider — *Repo map docs*. https://aider.chat/docs/repomap.html — tree-sitter/PageRank map under token budget; the tool the organism already runs.
16. AGENTS.md (2025). https://agents.md + llms.txt. https://llmstxt.org + Anthropic prompt-caching docs https://docs.claude.com/en/docs/build-with-claude/prompt-caching `(unverified)` — instruction-standard and cache-layout context.

*Repository claims verified via GROUND PACK (16 paths): `scripts/hooks/escalations_alert_sessionstart.sh`, `scripts/build_repomap.sh`, `docs/runbooks/repomap-and-branch-cleanup.md`, `.claude/commands/resume.md`, `.claude/rules/cicatrix-superscar.md`, `scripts/tests/test_superscar_budget.py`, `CLAUDE.md` (project), `SYMBIOSIS.md`, `docs/SYSTEM_BRIEF_FOR_AGENTS.md`, `docs/AI_ONBOARDING.md`, `.agents/skills/` (listing), `.claude/skills/visaoracle/SKILL.md`, `.claude/skills/skill-catalog/SKILL.md`, `docs/NOTEBOOKLM_STRATEGY.md`, `docs/NOTEBOOKLM_CAPABILITY_MATRIX.md`, `research/operations/2026-06-30-claude-code-perfect-session-doctrine.md`. `MEM:` references (`$MEM` bodies, `MEMORY.md`) unavailable in-lane — stated per protocol.*

status: complete