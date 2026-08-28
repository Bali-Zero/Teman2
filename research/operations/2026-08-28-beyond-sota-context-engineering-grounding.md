---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 2/13 — Context engineering & grounding
model: claude-fable-5 (pinned lane)
sources: 16
repo_files_verified: 41
status: complete
sections_done: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
adversarial_review: codex
model_selection: "manual — Zero's order of 2026-08-28 for this one panel; pinned by the orchestrating session, not routed by any script, cron or doctrine (Fable 5 has no automated role, ruling 2026-08-20)"
---

# Beyond-SOTA 2/13 — Context engineering & grounding

## §0 — TL;DR

Position: the **write side of grounding is ahead of everything surveyed** (a typed, integrity-linted,
family-compressed scar corpus; staleness-honest live receptors; hook-automated capture) while the
**read side is behind** — delivery is unbudgeted, unmeasured, and just silently exploded.
Biggest gap, measured in this lane's own context: the auto-injected surface **5×'d in seven days to
774,156 B ≈ 190–220K tokens** (the full scars body AND the "never auto-loaded" archive now inject);
the only armed budget guards 14 KB of it (1.8%), so every session now *boots* at the edge of Chroma's
measured context-rot zone (~300–400K on 1M-window models; the org already averaged 290K).
Top-3 moves: **(1)** re-cold-storage the scar bodies + arm a read-side **attestation** of what
sessions actually receive (774 KB → ≤120 KB; catches harness-behavior drift no repo diff can show);
**(2)** build **ScarBench** (recall benchmark derived from the corpus itself), then a **JIT
scar-retrieval hook** — Mem0-class retrieval-over-injection (3-4× token savings) applied to a failure
corpus nobody else has; **(3)** unify per-seat memory and automate mandate-keyed recall at TRIAGE —
today a headless seat lane can reach **0 of the 1,681** memory files.
Meta-pattern: *written ≠ read* — every guardian watches the artifact, none watches the delivery.

## §1 — How Nuzantara does it today (grounded)

Every claim below was verified on disk in this session (`wc -c`, `ls`, `grep`, `sed -n`), or observed
directly in this lane's own injected context — which is itself a live specimen of the mechanism under
study.

### 1.1 The layered injection at turn 1

A session opens with a **stack of injected context**, assembled from four sources:

**(a) Doctrine files (claudeMd assembly).** Measured today:

| Component | Bytes | Path |
|---|---|---|
| Global CLAUDE.md | 22,795 | `/Users/nuzantara/.claude/CLAUDE.md` |
| Project CLAUDE.md | 44,523 | `CLAUDE.md` (repo root) |
| Superscar bridge | 13,986 | `.claude/rules/cicatrix-superscar.md` |
| Active scars | 296,243 | `.claude/rules/cicatrix-scars.md` |
| Scars archive | 396,609 | `.claude/rules/cicatrix-scars-archive.md` |
| **Total observed injected** | **774,156 B ≈ 190–220K tokens** | (3.5–4 B/token, mixed IT/EN) |

All five arrived **in full** in this lane's context, labeled "project instructions". This is the
single most important measurement of this report: the 2026-08-21 token-ceremony audit
(`research/operations/2026-08-21-token-ceremony-ci-system-audit.md` §3, R-CTX, "confirmed on the
reader's own system prompt") measured the static boot tax at **~148–155 KB ≈ 42–44K tokens** across
four components — global CLAUDE.md, project CLAUDE.md, superscar, MEMORY.md — with the scars body and
archive *not* in the prompt. Seven days later the injected surface is **~5× larger**: the harness now
loads the whole `.claude/rules/` directory. The archive's own header still promises "not auto-loaded
per session" (verified at `.claude/rules/cicatrix-scars-archive.md:3`) and the active file still cites
a "40k-char auto-load threshold" — 296 KB is 7.4× over it. Nothing alarmed, because the only armed
guardian of the boot tax is `scripts/tests/test_superscar_budget.py` (`BYTE_BUDGET = 14_000`, line 47),
which watches **one file currently at 13,986 bytes (14 bytes of headroom)** — i.e. ~1.8% of the
payload it believes it is bounding. The ceremony that trimmed the superscar from 70,970 B to under
14,000 B recovered ~15 KB while 693 KB walked in unwatched.

**(b) Global SessionStart hooks** (`/Users/nuzantara/.claude/settings.json`, hooks block extracted
structurally): 15 SessionStart commands — machine check, `mcp-cleanup.sh`, MOS recent-memories
(`mos-db` SQL "Recent memories"), a 14-day lessons cutoff, `tmux-briefing.sh`, `nuz-sync-check.sh`,
`symbiosis-core.sh` (819 B, verified: greps the 8 SYMBIOSIS Laws + the 5 build questions out of
`SYMBIOSIS.md` at boot — compression by extraction, not summarization), an `AUTONOMOUS_OPS.md`
staleness probe, `active-context-read.sh`, `log-rotate.sh`, `memory-leak-check.sh`, the **repomap
inject** (gated on file age < 30 min), `agent_workspace_setup.py`, and an organism alert shim.

**(c) Project SessionStart receptors** (`.claude/settings.json` in-repo, `${CLAUDE_PROJECT_DIR}`
paths — verified): exactly three — `scripts/hooks/escalations_alert_sessionstart.sh` (7.8 KB; the
escalations board, HIGH-first, explicitly "SNAPSHOT, not graveyard"),
`scripts/hooks/proprioception_sessionstart.sh` (7.0 KB; boundary divergences with **age stamps and
"re-verify before acting"** on every line — the injection admits its own staleness), and
`scripts/hooks/organism_digest_sessionstart.sh` (3.3 KB; regulatory deltas 24h, seat/organ health,
main landings). These three fired in this lane; the fifteen global ones did not (see 1.2).

**(d) Live state files.** `~/.nuzantara-repomap.txt`: 42,846 B, rebuilt 15-minutely by cron
(`scripts/build_repomap.sh`, aider-style ctags fallback post-W76). The script's own band is "target
4-20kB", WARN at >30 KB (`build_repomap.sh:230-234`) — **the live file is over its own warn threshold
right now**, and per family W55 the warn goes to a stderr log nobody reads (W76 recidiva-lite, see §2).

### 1.2 Per-seat config isolation — and what a headless lane actually knows

W132 (landed on main today, #5176: "pin `claude -p` children to a sterile config dir") means headless
children run under a per-seat `CLAUDE_CONFIG_DIR`. Measured on this lane's own seat dir
(`~/.claude-antozero`): `settings.json` is **67 bytes**, there is **no CLAUDE.md**, and the project
memory directory contains **0 files**. Consequences, observed live:

- **Repo-tracked context survives seat isolation**: CLAUDE.md chain, `.claude/rules/*`, project
  hooks, corner skills — all arrived.
- **HOME-tracked context does not**: no repomap injection, no MOS recent-memories, no symbiosis-core,
  no lessons cutoff — none of the 15 global hooks fired. And the memory system is **entirely absent**:
  the harness offered this lane a memory directory that is empty
  (`~/.claude-antozero/projects/.../memory/` = 0 files) while the real corpus (1,681 files) lives
  under `~/.claude/projects/`. A memory this lane writes lands in a shadow no interactive session
  reads. Anti-hallucination discipline still arrives (it lives in CLAUDE.md §6), but *recall* does not.

This split is the cleanest statement of the architecture: **grounding that lives in the repo is
fleet-invariant; grounding that lives in `$HOME` is per-machine, per-seat, and silently divergent**
(superscar family #1 applied to context itself — see §2).

### 1.3 The memory system (MOS)

Three storage layers plus capture:

- **File corpus**: 1,681 `.md` files in `~/.claude/projects/-Users-nuzantara-nuzantara/memory/`
  (measured; the panel brief said 1,707). By prefix: `discovery_` 546, `lesson(s)_` 265, `decision_`
  161, `project_` 83, `reference_` 70, `feedback_` 57, `fact_` 39, `unresolved_` 11 — discoveries
  outnumber decisions 3.4:1; the corpus is primarily *measured world-facts*, not preferences.
- **The index**: `MEMORY.md`, 18,304 B / 81 lines, 51 of them carrying `](` links (63% pointer-bearing;
  the rest are rule-lines). Header states the contract: "1 riga/voce, dettaglio nel `.md`", priority
  order = "il taglio cade in FONDO", and a **ruled ~17 KB target (Zero, 14/8)** — the index is 7.7%
  over its own ruling today. Overflow bodies exist and are pointed to, not inlined:
  `MEMORY_SHELL_CLI_TRAPS.md` (15,508 B, "21 trappole"), `MEMORY_VERIFICATION_RULES.md` (76,630 B),
  `MEMORY_ARCHIVE.md` (111,567 B). A dedicated repair command exists for index overflow
  (`/Users/nuzantara/.claude/commands/mem-trim.md` — "diagnose + fix MEMORY.md silent-truncation
  overflow (issue #40614)", dry-run default, operator-gated apply).
- **The database**: `~/.claude/memory.db` (SQLite + FTS5) behind the `mem` CLI
  (`~/.claude/scripts/mem`: `query|save|entities|recent|sessions|stats`), with an **F3 semantic
  route**: `mem query "…" --semantic` execs a Qdrant + bge-m3 search instead of FTS5 (verified in the
  CLI source, lines 19-26). Doctrine orders `mem` BEFORE `notebook_query` (project CLAUDE.md §3).
- **Capture is hook-automated, not volitional**: `mos_capture_post_tool.py` (PostToolUse — appends raw
  tool observations to memory.db with a `check_sensitivity()` gate, line 77), `mos_capture_stop.py`
  (Stop), `mos_capture_session_end.py` (SessionEnd). The Stop path also runs `stop_verify.py` (blocks
  ending with dirty git + no intent marker) and `seam_verify.py`.

### 1.4 Compaction & handoff

- **PreCompact** fires three hooks: `alzheimer-hook.sh`, `precompact-transcript-backup.sh`, and
  `precompact-mnemos.py` (parses the transcript JSONL into a handoff — `parse_transcript_jsonl()` at
  line 29). **PostCompact** re-injects: `cat` of the project CLAUDE.md ("Context compacted.
  Re-loading critical context").
- **`/resume`** (`.claude/commands/resume.md`, vendored in-repo as CANON shadowing the HOME copy):
  read-only, zero side effects, always prints the recent-sessions list first (operator preference
  2026-05-30), refuses to fabricate when no handoff exists.
- **modus §STATE & RE-ENTRY** (`.claude/skills/modus/SKILL.md:88`) is the doctrine: durable state
  lives in files, never in the window; a "durable receptor" is one of exactly three concrete
  mechanisms (PENDING-ARMS line / SessionStart hook / harness background task — with the measured
  caveat that background shells get auto-reaped under memory pressure); **on wake, emit a dense recap
  and re-run a light GROUND because "the disk may have moved while you slept"**; a receptor whose
  healthy output is silence must expose a self-probe, because silence and death are indistinguishable.

### 1.5 Corners, skills, and skill discovery

`.claude/skills/` holds 16 entries: 11 real directories + 5 symlinks into `.agents/skills/` (bot,
kbli-navigator, secondhome, visaoracle, wr2 — verified `ls -la`). The symlinked five plus intake/slhs
are **corners**: living shared-state documents, not instructions. The bot corner's header states the
contract verbatim: "Update §1 LIVE STATE whenever it changes — this corner is only useful if it stays
true." The visaoracle corner shows the maturity of the pattern: its header *demotes its own previous
handoff artifact* ("`CURRENT_STATE.md` is a SUPERSEDED 2026-08-15 snapshot … kept as archaeology")
and redirects readers to the in-file LIVE STATE. Corners are the organism's answer to cross-session,
cross-machine shared working memory: repo-tracked, therefore fleet-invariant and PR-reviewable.

Skill discovery is deliberately two-tier (`.claude/skills/skill-catalog/SKILL.md`): only Tier-1
skills are installed ("Claude Code loads ALL installed skill descriptions into context at session
start. To avoid context bloat (the orchestration-decay 8→0 regression), only Tier-1 skills + a
curated few are installed"); everything else lives in the MOS catalog, searchable on demand — with
the documented FTS5 gotcha that the hyphen in `SKILL-CATALOG` breaks prefix queries (query by domain).

### 1.6 Ground truth & anti-hallucination

- **NotebookLM as bipolar verifier**: `docs/NOTEBOOKLM_STRATEGY.md` (AI Ultra tier, 600
  sources/notebook) + `docs/NOTEBOOKLM_CAPABILITY_MATRIX.md` — the matrix practices *dated
  stale-checks on itself* ("Stale-check: 2026-04-25 … outdated references flagged below"). The MCP
  wiring is machine-local by design: `.mcp.json` is absent from the worktree and was removed from
  tracking (`git log`: "remove .mcp.json from tracking") — correct hygiene for a public repo.
- **Anti-hallucination is doctrine with teeth**: CLAUDE.md §6's five rules (never cite un-executed
  tool output; the context buffer is not authoritative; re-run the tool now) plus the lived
  discipline visible in the ledger — a healer run this week closes with "All receptors re-executed
  fresh this turn, nothing recalled from context (W65/W90)" (`.claude/skills/modus/PENDING-ARMS.md`,
  2026-08-25 row). Grounding probes themselves are audited for lying: the TCC discovery
  (`discovery_glob_over_a_tcc_protected_directory_returns_empty_not_an_error_2026_08_21.md`) proves
  three probes on the same object disagree (`ls -ld` OK, glob "no matches", `ls -1` "Operation not
  permitted") — so "0 files" ≠ "clean", and MEMORY.md carries that warning in its top block.

### 1.7 Doctrine drift across machines

The global CLAUDE.md is **three per-machine copies with no lint**
(`discovery_the_global_claude_md_is_a_home_fork_three_copies_three_answers_2026_08_23.md`): on
2026-08-23 the three copies gave three different seat counts — "QUAD" (Pro), "QUAD" (Mini, byte-identical),
"TRE" (M5) — and reality was six. The memory's verdict: "una correzione applicata a una sola copia
diventa una terza versione, non una cura." The mitigation today is conventional (a sha-pinned
canonical block, `fd8c67757e6a56ff`, plus "apply to all three in the same turn" written into the file
itself). `scripts/lint_home_fork.py` covers 97 declared *executable* pairs — doctrine files are not
pairs, because the file has no in-repo authoritative copy to compare against. The superscar bridge
even warns readers **the bridge itself may be stale** on machines whose checkout is deliberately held
back ("il riferimento è `git show origin/main:<path>`").

### 1.8 The measured economics (why this all matters)

From the 2026-08-21 audit (§3, measured over 140 sessions / 7 days on M5): 9.10B cache-read tokens vs
31.9M output; the ~45K-token doctrine prefix accounted for ≈1.4B (~15%) of all cache reads; **0
sidechains in 264 transcripts** — every one of 415 subagent dispatches re-paid the boot prefix
(~19M of 258M cache-creation tokens); average context 290K = "the documented context-rot zone". The
audit's own conclusion: the boot tax is "primarily a context-room and quality lever … not a quota
lever" (cache reads are discounted). With today's measured 190–220K-token injection, a session now
**starts at or beyond an entire standard 200K window before the first user token** — survivable only
on 1M-context models, and squarely inside the rot zone the audit warned about.

## §2 — Scars & ledger evidence in this area

The scar corpus is unusually rich here because *context is the substrate every failure passes
through*. Grouped by what they prove:

**The injected context itself decays or lies (family #2 applied to receptors):**
- **W76** — the repomap SessionStart inject degraded to 188 KB of minified webpack symbols (~45K junk
  tokens poisoning *every* session); aider silently vanished, ctags fallback had no `.next` excludes,
  and the >30 KB WARN "scattava a ogni run da giorni, su stderr, ignorato" (family W55: signal emitted
  ≠ signal seen). **Recidiva-lite measured today**: the live file is 42,846 B, again over the 30 KB
  warn band its own script declares (`build_repomap.sh:234`).
- **W120** — the organism digest (an injected SessionStart receptor) read key `classification` where
  the reporter emits `class`: the pending-arms-overdue alarm was **silently zero for its entire
  life** over a ledger carrying 280 overdue rows. "Un allarme che non suona è indistinguibile da un
  mondo sano." The cure re-keys on `counts.*` and *says* when entries and counts disagree.
- **W84-tcc-dead / TCC glob discovery** — grounding probes can lie by returning empty instead of
  erroring; three probes on the same path disagree. Grounding must use the probe that *says the truth*.

**The doctrine/context files are a HOME-fork (family #1 applied to documents):**
- The 3-copies global CLAUDE.md discovery (2026-08-23) — three machines, three answers, all wrong,
  injected into every session of every machine, no lint possible (no authoritative copy).
- **W106b** — the twin freshness guardians compared live copies against the *local checkout* and
  prescribed "realign live from repo" when the checkout was 144 commits behind: the reference itself
  was the proxy. Antidote: attribute staleness against `origin/main`, never the checkout — the same
  rule the superscar bridge now prints about itself.
- **W109** GOTCHA — a merged cure wasn't live because the cron ran a HOME copy of the wrapper; the
  fix was killing the fork, not maintaining it.

**Scars-as-context needs integrity gates on its own text (families #3/#6):**
- **W112** — Prettier, an unwatched *writer*, corrupted scar records inside the injected bridge
  (`bz:log-anomaly:*` → `bz:log-anomaly:_`, identifiers losing leading underscores) — and the
  pre-commit gate made writing the *correct* prose uncommittable. Antidote: `.prettierignore` on the
  three cicatrix files; the duplicate record in the un-mangled file was the tripwire.
- **W113** — the phrase written *while retracting* a claim is a new unreviewed claim; four
  adversarial rounds all aimed at the withdrawn text, none at its replacement. Antidote: the
  retracted-claims registry (`infra/retracted-claims/registry.json` + `scripts/lint_retracted_claims.py`,
  marker-only absolution `RETRACTED[<claim-id>]`, armed on every PR outside path filters).
- **Superscar #6 lineage** W65→W90→W100→W113: the refuter hallucinates → the ground truth ages
  (NB-3 confirming pre-resolution numbers with the voice of authority) → same-family agreement
  certifies 7/8 false-cleans → the correction itself lies. This lineage *is* the reason the
  anti-hallucination rules exist and keep tightening.
- **META 2026-06-05 / W74** — a 13-agent autopsy cited three file:line references that never existed;
  the standing rule since: report citations are LEADS, re-verify every load-bearing path in-turn.

**Index/budget saturation is a recorded failure mode, not a hypothetical:**
- **W130 (maintenance note)** — a new scar could not add its one-line index entry: the superscar file
  was at 13,963/14,000 bytes ("la saturazione dell'indice è essa stessa un reperto"). Today: 13,986/14,000
  — **14 bytes of headroom**; the next scar family membership line will not fit without a prune.
- **MEMORY.md issue #40614** — silent truncation at the 200-line cap; the `/mem-trim` command exists
  specifically because the index has historically overflowed and truncated *silently*.
- The 2026-08-21 token ceremony itself is ledger evidence: the trim moved W-numbers' bodies out of
  the bridge (W88, W101, W106b, W107 etc. carry "spostato verbatim … durante il trim boot-tax"
  reference lines) — the organism has already once paid a full Gear-3 ceremony to reclaim boot tokens,
  and the surface then quintupled through an unwatched channel within a week.

**Compaction/handoff:** zero recorded compaction-loss scars in the active file (grep "compaction" =
0 hits in scar bodies) — the PreCompact triple + `/resume` + modus re-entry discipline has, so far,
kept compaction out of the scar corpus. The nearest relative is **W80/W91-family** (worktree reaped
under a live session — state loss *around* the session, not in it) and the protocol's own genesis
fact: two panel launches died on seat windows leaving **nothing** on disk, which produced §4bis
(write-early/append-often) — a handoff discipline born from a fresh wound this very day.

**PENDING-ARMS as receptor:** the ledger is 2.2 MB / 1080 entries and is reconciled at TRIAGE by
doctrine; W120 proved the *digest* of it can disarm silently; the 2026-08-25 healer row shows the
working posture (re-execute receptors fresh, cite W65/W90, leave sibling work dirty).

## §3 — World SOTA survey

| # | System / practice | Source (date) | Mechanism | Measured effect | Transfer to this organism |
|---|---|---|---|---|---|
| 1 | Anthropic — Effective context engineering | anthropic.com/engineering (Sep 2025) | Context as finite "attention budget": compaction, structured note-taking, sub-agent isolation, just-in-time retrieval via lightweight identifiers | Framing doc; Claude Code compaction preserves decisions/bugs, discards stale tool output | Directly — the harness in use IS this stack; Nuzantara already runs compaction hooks + notes (ledger/corners); JIT is the missing piece for scars |
| 2 | Chroma — Context Rot | trychroma.com/research/context-rot (Jul 2025) | 18 models on extended-NIAH: performance degrades non-uniformly with input length; distractors and structure matter | Degradation observable from ~300–400K tokens on 1M-window models; "effective window ≪ advertised" | Critical: sessions average 290K (audit §3) and now BOOT at 190–220K — the organism lives inside the measured rot zone |
| 3 | Manus — Context engineering lessons | manus.im/blog (Jul 2025) | KV-cache hit rate as the #1 production metric; stable append-only prefix; file system as "ultimate context"; todo.md recitation against goal drift | ~100:1 input:output ratio in production; timestamp in prefix = full cache invalidation | Prefix stability already holds (static doctrine); recitation ≈ modus recap blocks; file-system-as-context ≈ corners/ledger — validated convergence |
| 4 | ETH Zürich — Evaluating AGENTS.md | arXiv:2602.11988 (Feb 2026) | AGENTBENCH: 138 real tasks × {no file, LLM-written, developer-written context file} | Context files do **not** generally improve success; **+20% inference cost**; "describe only minimal requirements" | The strongest counter-evidence to a 774 KB injection; demands an ablation — but their files are how-to instructions, not failure corpora or fleet coordination |
| 5 | Cognition — Don't Build Multi-Agents + update | cognition.com/blog (Jun 2025; update Dec 2025) | Share full agent traces, not summaries; single-threaded writes; context engineering as the reliability core | Position paper; updated: multi-agent works when "writes stay single-threaded" | Matches the 0-sidechain finding (parent re-reads subagent work inline) and the conductor pattern; validates full-trace handoffs |
| 6 | Aider — repository map | aider.chat/docs/repomap.html (2023-2025) | tree-sitter symbol graph + PageRank, truncated to a hard token budget (default **1K tokens**) | "Significantly higher edit accuracy" vs naive inclusion (aider benchmarks) | Already adopted (build_repomap.sh is aider-derived) — but budget enforcement was lost in the W76 fallback; aider budgets 1K where Nuzantara ships ~12K |
| 7 | Mem0 | mem0.ai/research (2025-2026) | Extract-then-retrieve memory layer vs full-context | LoCoMo 92.5, LongMemEval 94.4 at **3-4× lower token cost** than full-context | The measured argument for retrieval-over-injection — the exact inversion Nuzantara needs for scars |
| 8 | Zep / Graphiti | arXiv:2501.13956 (Jan 2025) | Temporal knowledge graph; edges carry validity intervals (fact aging) | Zep 63.8% vs Mem0 49.0% on temporal reasoning (GPT-4o) | Fact-aging = W90's lesson formalized; `valid_until` frontmatter exists in golden corpus but not in memory files |
| 9 | Letta (MemGPT) | arXiv:2310.08560 (Oct 2023) | OS-style memory hierarchy: self-editing core blocks + paged external storage | Foundational; tiered model adopted industry-wide | MEMORY.md index + overflow bodies + archive IS a manual MemGPT hierarchy; missing: self-editing under a hard cap enforced at write time |
| 10 | A-MEM | arXiv:2502.12110 (NeurIPS 2025) | Zettelkasten: notes with keywords/tags that actively link to existing notes on insert | Outperforms flat vector stores on non-obvious connections | The `[[name]]` linking convention in memory frontmatter is exactly this — done by hand; linking is not enforced or exploited at retrieval |
| 11 | Generative Agents | arXiv:2304.03442 (UIST 2023) | Memory stream scored by recency × importance × relevance; periodic reflection synthesizes abstractions | Foundational retrieval formula | MOS stores importance (1-10) but retrieval uses FTS5/semantic only — no recency/importance-weighted ranking at recall |
| 12 | AGENTS.md standard | agents.md; OpenAI+Google+Cursor (Aug 2025) | One predictable project-scoped context file | >60K repos, >20 tools by Dec 2025 | Nuzantara predates and exceeds it (CLAUDE.md chain + corners); risk is the opposite tail — maximalism, per #4 |
| 13 | llms.txt | llmstxt.org (Sep 2024) | Curated docs-index for LLM consumption | ~10% adoption (SE Ranking, 300K domains) | Marginal; the internal analogue (INDEX.md as atlas) already exists |
| 14 | Anthropic prompt caching | platform.claude.com docs (2024-2026) | Cache reads 0.1× base input; writes 1.25×/2×; TTL refreshes on read; cache reads excluded from rate limits | 90% steady-state discount; ~5× throughput multiplier at 80% hit rate | Explains why the boot tax is a context-room lever, not a quota lever (audit already concluded this); per-seat sterile dirs keep prefixes stable per seat |

**The five that matter most.**

**Chroma's context-rot curve is the physics this lane's headline number collides with.** Degradation
on 1M-window models becomes observable around 300–400K tokens — and is worse in the presence of
distractors, which is precisely what 700 KB of narrative scar prose is for a session doing, say, a
CSS fix. The organism's own audit named 290K average context "the documented context-rot zone" a week
before the injection quintupled. The question is no longer whether the boot tax costs quota (caching
makes it cheap) but whether it costs *accuracy* — Chroma says yes, non-uniformly, and invisibly.

**The ETH AGENTS.md evaluation is the only controlled experiment in this survey, and it points the
knife at this organism's proudest artifact.** Across LLMs and agents, repository context files did
not raise success rates and raised cost ~20%; unnecessary *requirements* made tasks harder. Two
honest readings coexist: (a) Nuzantara's injection is not a how-to file — it is failure memory
(scars), fleet coordination (rulings, seat maps), and live state (receptors), none of which
AGENTBENCH's niche-repo tasks exercise; (b) nobody has ever ablated THIS corpus either, and the
belief that 700 KB of scars at boot prevents recidiva is exactly the kind of belief the organism's
own Law 7 ("no metric = not an improvement") refuses elsewhere. Both readings lead to the same move:
measure it (§5, R6).

**Manus supplies the production-economics frame.** KV-cache hit rate as the #1 metric, stable
append-only prefixes, and recitation-at-the-tail are all already true here (static doctrine prefix;
modus recap blocks). Where Manus diverges is discipline of *size*: Manus treats every prefix token as
paid attention; Nuzantara treats prefix tokens as free because they cache. Caching makes them cheap
on the meter and expensive in the attention budget — the Chroma point again, from the builder's side.

**Mem0/Zep/A-MEM define the retrieval-memory SOTA the MOS already resembles — except at the load
path.** The organism's write side is arguably ahead (typed corpus, importance scores, `[[links]]`,
retraction lint, integrity gates); its read side is behind: recall is volitional (`mem query`),
the SessionStart top-5 fires only for interactive sessions on the primary config dir, ranking
ignores recency/importance at query time, and nothing measures recall quality (no LongMemEval
analogue). Zep's temporal edges formalize what W90 taught in blood: a fact's validity interval is
part of the fact.

**Anthropic's own stack is the convergent baseline** — compaction, sub-agent isolation, JIT
retrieval, and (per the Claude Code memory docs) a native auto-memory with a MEMORY.md index: the
platform has been converging on the MOS design. The differentiator that remains is not mechanism but
*content*: no surveyed system injects a CI-budgeted, family-compressed, integrity-linted failure
corpus with staleness-honest live receptors. That is the asset to protect while fixing its delivery.

## §4 — Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Injection-surface budgeting | **BEHIND** | 774,156 B observed injected vs Anthropic's "smallest set of high-signal tokens"; only 13,986 B (1.8%) under an armed budget (`test_superscar_budget.py`); the surface 5×'d in 7 days with zero alarms; ETH (arXiv:2602.11988) measured context files at +20% cost, no median gain |
| Scars-as-context (institutional failure memory) | **AHEAD** | No surveyed system has anything like it: 99 scars → 10 compressed families in a CI-budgeted bridge, W-number grep protocol, `.prettierignore` integrity (W112), retracted-claims lint on every PR (W113), executable antidotes named per family. Anthropic/Manus/Cognition inject instructions; nobody injects *measured failures with antibodies* |
| Live-state receptors at boot | **AHEAD** | proprioception/escalations/organism digests carry **age stamps + "re-verify before acting"** (`scripts/hooks/proprioception_sessionstart.sh`, observed live) — staleness-honest injection appears in no surveyed system; W120 proved the family needs guarding, and got it |
| Repomap | **AT design / BEHIND enforcement** | aider-derived (SOTA mechanism, `build_repomap.sh`) but 42,846 B live vs its own 30 KB warn and aider's 1K-token default; warn is stderr-only (W55 class); W76 already proved this exact failure once |
| Memory write-side (capture, typing, integrity) | **AHEAD** | 1,681 typed files, importance scores, `[[links]]` (A-MEM's Zettelkasten by hand), hook-automated capture with sensitivity gate, `/mem-trim` repair, retraction registry — richer than Mem0/Letta write paths |
| Memory read-side (recall into context) | **BEHIND** | Recall is volitional (`mem query`) or top-5-at-boot (interactive only; absent for seat lanes — measured 0 memory files reachable in this lane); no recency×importance×relevance ranking (Park 2023); no LongMemEval-style recall measurement; Mem0 shows 3-4× token savings from retrieval-over-injection — the exact inversion scars need |
| Fact aging / temporal validity | **BEHIND (design known, unapplied)** | Zep/Graphiti carry validity intervals on edges; here `valid_until` exists in the golden corpus but memory files have no expiry; W90 (ground truth ages) is a scar, not yet a schema field |
| Compaction & handoff | **AT → AHEAD** | PreCompact triple + PostCompact reinject + `/resume` + modus §STATE & RE-ENTRY ≥ Anthropic's compaction baseline; **zero compaction scars in the corpus** (grep verified); §4bis write-early protocol was added the same day two launches died — the loop learns |
| Doctrine fleet-invariance | **BEHIND (known, measured, unfixed)** | Global CLAUDE.md = 3 unlinted per-machine copies ("three copies, three answers", 2026-08-23); per-seat config dirs have no CLAUDE.md and empty memory (measured); `lint_home_fork.py` covers executables only |
| Cache-aware layout | **AT** | Stable static prefix by construction (Manus's rule); audit already priced it (≈15% of 9.1B cache reads); per-seat dirs keep prefixes stable per seat; caching correctly understood as not-a-quota-lever |
| Ground-truth verification discipline | **AHEAD** | "All receptors re-executed fresh this turn, nothing recalled from context (W65/W90)" as working posture; probe-the-probe culture (TCC discovery: three probes, one truth); NotebookLM capability matrix stale-checks itself. No surveyed lab publishes an equivalent discipline |
| Skill/context discovery | **AT** | Two-tier skill catalog (installed Tier-1 + MOS-searchable rest) matches Anthropic's JIT principle; corners = repo-tracked shared working memory ≈ Manus file-system-as-context, with LIVE STATE contracts |

The shape is consistent: **write-side and discipline AHEAD, read-side and budgets BEHIND.** The
organism built the world's richest grounding corpus and then let the delivery mechanism drift into
exactly the regime (full-text, unbudgeted, distractor-heavy, rot-zone) that the 2025-26 measurement
literature warns against — while its own guardians watched single files instead of the surface.

## §5 — Beyond-SOTA recommendations (ranked by impact × confidence / cost)

**R1 — Context-delivery ATTESTATION + scar re-cold-storage** *(the emergency, and the novel frame)*
- **What**: (a) Move `cicatrix-scars.md` + `cicatrix-scars-archive.md` out of the auto-injected
  `.claude/rules/` into `docs/scars/` (grep targets, loaded on demand; the 14 KB superscar bridge
  stays injected and keeps its budget). (b) Arm a **read-side attestation**: a CI test that assembles
  the exact set of files the harness injects (global CLAUDE.md + project CLAUDE.md + every
  `.claude/rules/*.md`) and asserts the TOTAL ≤ 120 KB; plus a SessionStart self-probe line that
  prints the byte-sum a live session actually received, so drift is visible in every transcript.
- **Why beyond SOTA**: budgets-per-file exist everywhere; **attesting what sessions actually receive**
  (delivery, not artifact) exists nowhere surveyed — and it is the antidote to the meta-pattern in §8.
  It exploits three organism asymmetries: hooks-as-backstop, CI-armed doctrine, and the fact that a
  harness update silently 5×'d the surface *without any repo diff* — only read-side attestation can
  catch that class.
- **Cost**: ~4h, Gear 2. **Risk**: family #3 (over-match — sessions that legitimately need a scar body
  now must grep; mitigated: `scar query`/grep workflow already exists and is doctrine); family #9
  (path drift — `scar` skill, `lint_scar_number_collision.py`, `test_superscar_budget.py`
  completeness-check all reference the old paths and must be repointed in the same PR).
- **Metric**: bytes injected at turn 1: **774,156 → ≤120,000** (measured by the attestation probe);
  boot tokens ~200K → ~30K; subagent spawn cost drops identically. **Kill criterion**: if scar
  recidiva rate (same W-family re-biting within 30 days) rises above the trailing 3-month baseline in
  the 60 days after the move, re-inject the active file and go to R2 first.
- **First PR**: `chore(context): re-cold-storage scar bodies + boot-tax attestation` — `git mv` two
  files, repoint 4 tools, add `scripts/tests/test_injected_surface_budget.py` (~120 lines).

**R2 — A JIT scar-retrieval organ** *(retrieval-over-injection for failure memory)*
- **What**: a UserPromptSubmit hook that FTS5/semantic-matches the mandate text (and, at TRIAGE, the
  named hot files) against the scar corpus + memory corpus, and injects only the top-k matching
  W-bodies/memory bodies (k≈3, ~6 KB) with their `Reference:` lines. The superscar bridge remains the
  always-on compression layer; full bodies arrive only when relevant.
- **Why beyond SOTA**: composes Mem0-class retrieval (92.5 LoCoMo at 3-4× lower token cost) with a
  corpus **no one else has** — typed failures with executable antidotes. Anthropic's JIT principle
  applied to institutional scar tissue rather than code files. Nothing surveyed retrieves *failure
  memory* by mandate similarity.
- **Cost**: ~2 days, Gear 3 (touches every session's context path). **Risk**: family #3 over/under-match
  (a scar not retrieved = silent under-match — this is why R3's benchmark gates it); family #2 (the
  retriever itself must have a self-probe; W120 lesson: it must NAME what it searched and how many
  candidates it saw, so silence ≠ health).
- **Metric**: scar-citation precision/recall on R3's benchmark ≥ full-injection baseline, at ≤10 KB
  injected vs ~700 KB. **Kill criterion**: recall on R3 falls >10 points below the full-injection
  baseline after two tuning rounds → keep bridge-only + grep doctrine.
- **First PR**: `feat(context): scar-recall hook (shadow mode)` — logs what it WOULD inject for 2
  weeks without injecting (shadow-first, per ship-dark doctrine), ~250 lines.

**R3 — ScarBench: an internal recall benchmark derived from the corpus itself**
- **What**: for each of ~99 scars, auto-derive a query from its TRAUMA paragraph (and from the
  original incident's mandate where the ledger has it); gold = its W-number + family. Evaluate any
  context configuration (full-injection / bridge-only / JIT top-k / `scar query`) on
  recall@k + citation precision. Same harness doubles as a LongMemEval-style eval over the 1,681
  memory files (query = the discovery's own `description:` line; gold = the file).
- **Why beyond SOTA**: LongMemEval/LoCoMo benchmark *conversational* memory; **nobody benchmarks
  organizational failure-memory recall** — and this organism is uniquely positioned because its corpus
  is already typed, dated, family-indexed, and integrity-linted. It converts the ETH AGENTS.md
  finding from a threat into an instrument: measure whether OUR context files earn their tokens.
- **Cost**: ~1 day, Gear 2. **Risk**: family #6 (the benchmark's own gold can be wrong — derive
  queries mechanically from TRAUMA text, never hand-write plausible ones); reward-hacking class (a
  retriever tuned on ScarBench overfits — hold out the 20 newest scars).
- **Metric**: the benchmark existing IS the metric (0 → 1 measurement capability); first
  before/after: full-injection vs bridge-only recall delta, published in the R1 kill-criterion
  decision. **Kill criterion**: if mechanically-derived queries prove degenerate (recall@1 > 95% for
  trivial lexical overlap), switch gold to held-out incident mandates only.
- **First PR**: `feat(eval): scarbench v0 — corpus-derived recall eval` (~300 lines incl. fixtures).

**R4 — Read-side memory automation + per-seat memory unification**
- **What**: (a) make memory recall non-volitional at TRIAGE: modus GROUND already *says* "memory-hits"
  — arm it as a hook that runs `mem query` (FTS5 + semantic) on the mandate and prints the top hits
  with their `type:` and date; (b) unify seat memory: point every seat config dir's
  `projects/<proj>/memory` at the canonical corpus (symlink or launcher env), read-only for headless
  lanes if write-attribution is unsolved.
- **Why beyond SOTA**: Claude Code's native auto-memory and Mem0 both automate *capture*; automated
  *recall keyed to the mandate at session start* with typed, dated results is not in any surveyed
  default stack. The seat unification fixes a measured 0-of-1,681 reachability hole no one else even
  has the topology to hit.
- **Cost**: ~1 day, Gear 2. **Risk**: family #1 (the symlink IS a home-fork mechanism — declare the
  pairs in `infra/home-fork/declared-pairs.json` so the lint owns them); W132 regression risk (the
  sterile dir was a deliberate cure — unify MEMORY only, never session state; needs-ruling, §7).
- **Metric**: % of sessions whose first 10 turns cite ≥1 memory file (baseline measurable from
  transcripts; target +30 points); phantom-citation incidents (family #6) not increased.
- **Kill criterion**: if injected memory hits push median boot past the R1 budget, cap k or demote to
  pointer-only lines.

**R5 — Doctrine SSOT: de-fork the global CLAUDE.md**
- **What**: move fleet-invariant content of `~/.claude/CLAUDE.md` (22,795 B × 3 machines) into a
  repo-tracked `doctrine/global.md` injected via the project chain; leave a ≤2 KB per-machine stub
  (machine identity, paths, TCC facts only). Declare the stub trio in the home-fork lint.
- **Why beyond SOTA**: not novel mechanically (SSOT is table stakes) — novel in that no surveyed
  system has even *diagnosed* doctrine-as-home-fork ("three copies, three answers", 2026-08-23
  memory); this closes the last unlinted context surface and makes doctrine PR-reviewable, which the
  public-repo-as-forcing-function asymmetry rewards.
- **Cost**: ~4h + one fleet-align turn, Gear 2. **Risk**: family #1 by construction (the stub is a
  declared fork; the lint owns it); PII/cost rules in the global file must be audited for
  public-repo fitness before the move (some content may need to stay machine-local — that residue IS
  the stub).
- **Metric**: unlinted doctrine bytes across fleet: 22,795×3 → ≤2,000×3; "three-answers" incident
  class → structurally impossible for moved content. **Kill criterion**: if >30% of the file proves
  unpublishable (secrets-adjacent), keep a private git repo for doctrine instead — SSOT matters more
  than publicity.

**R6 — Temporal validity on grounding artifacts** *(Zep's edge, applied to doctrine)*
- **What**: add `verified_on:` / `valid_until:` frontmatter to memory files and receptor outputs;
  the recall path (R2/R4) prints age and flags expired facts ("stale — re-verify") the way
  proprioception already stamps its lines; a weekly probe lists expired high-importance memories.
- **Why beyond SOTA**: Graphiti ages *graph edges*; nothing surveyed ages *injected doctrine and
  failure memory* with an enforcement path. W90 and W106 are the measured cost of not having it; the
  proprioception hook already proved the UX ("as of 20:32, 2.7h ago — re-verify before acting").
- **Cost**: schema + lint ~1 day, backfill incremental, Gear 2. **Risk**: W129 class (calendar-driven
  reds) — expiry must *flag*, never *fail*, in CI paths.
- **Metric**: % of `discovery_`/`fact_` files carrying `verified_on` (0% → 60% in 90 days); stale-fact
  incidents (W90 class) recurrence. **Kill criterion**: if flags are ignored for 30 days (measured
  zero re-verifications triggered), the field is theater — stop backfilling, fold into R2 ranking
  signal only.

*(Micro-fix, fold into R1's wave: repomap hard-cap — truncate by rank to ≤20 KB in
`build_repomap.sh` instead of warning on stderr; 42,846 B → ≤20,480 B, W76-recidiva closed for good.)*

## §6 — 90-day roadmap

**Wave 1 (days 0–14) — stop the bleeding, gain eyes.**
1. PR-1 `chore(context): scar re-cold-storage + injected-surface attestation` (R1) — `git mv` the two
   scar bodies to `docs/scars/`, repoint `scar` skill / `lint_scar_number_collision.py` /
   `test_superscar_budget.py` completeness-grep / superscar footer pointers, add
   `scripts/tests/test_injected_surface_budget.py` (assembles the exact auto-load set, asserts
   ≤120 KB, and pins the *membership list* so a new rules file must be budgeted to enter). Gear 2,
   ~350 lines. **Acceptance**: fresh session transcript shows the attestation line with total
   ≤120 KB; `scar query W76` still resolves.
2. PR-2 `fix(repomap): rank-truncate to hard 20 KB cap` — replace the stderr warn with in-generator
   truncation; proprioception gains a `repomap_size` probe. Gear 1, ~60 lines. **Acceptance**:
   `wc -c ~/.nuzantara-repomap.txt` ≤ 20,480 after next cron tick; probe goes red if not.
3. PR-3 `feat(eval): scarbench v0` (R3). Gear 2, ~300 lines. **Acceptance**: one table in the PR body
   — recall@3 for {full-injection, bridge-only, grep-cascade} on the 99-scar set; numbers feed the
   R1 kill-criterion review at day 30.

**Wave 2 (days 15–45) — retrieval replaces injection.**
4. PR-4 `feat(context): scar-recall hook, shadow mode` (R2) — logs candidates per mandate, injects
   nothing yet. **Acceptance**: 2 weeks of shadow logs; recall vs ScarBench ≥ bridge-only + grep.
5. PR-5 `feat(context): mandate-keyed memory recall at TRIAGE` (R4a). **Acceptance**: transcript
   sample shows typed, dated memory hits in turn 1-3 of ≥80% of non-trivial sessions.
6. PR-6 `chore(fleet): seat memory unification (read-only)` (R4b) — after the §7 ruling.
   **Acceptance**: `ls` of a seat lane's memory path returns the canonical corpus; W132 sterility
   properties re-verified (no session-state bleed).
7. Day-30 review: flip scar-recall from shadow to live if ScarBench holds; else keep bridge-only.

**Wave 3 (days 46–90) — SSOT and time.**
8. PR-7 `docs(doctrine): global CLAUDE.md → repo SSOT + per-machine stubs` (R5) + same-turn fleet
   align on all three machines. **Acceptance**: `sha256` of the three stubs registered in the
   home-fork lint; moved content byte-identical from any machine's injection.
9. PR-8 `feat(mos): verified_on/valid_until schema + weekly expiry probe` (R6). **Acceptance**: lint
   accepts both stamped and legacy files; expiry FLAGS, never fails CI; first weekly report lists
   expired high-importance facts.
10. Day-90 re-measure the §1 table end-to-end (the attestation makes this a one-command probe):
    boot bytes, rot-zone margin, ScarBench trend, recidiva rate — publish as the successor to the
    2026-08-21 ceremony audit.

## §7 — Needs-ruling (Legge 5)

1. **The context budget itself** (R1): how much of every window doctrine may spend is a business
   trade-off between safety (scars visible) and capability (context room). The 120 KB proposal is a
   recommendation; the number is Zero's to set — precedent: the ~17 KB MEMORY.md target was
   explicitly ruled (14/8), and the 2026-08-20/25 Fable rulings show injection-adjacent choices are
   Zero's domain.
2. **Seat memory unification** (R4b): W132's sterile config dir was a deliberate cure landed today;
   re-sharing the memory subtree across seats partially reverses it. Needs an explicit ruling that
   MEMORY (not session state) may be shared fleet-wide, and whether headless lanes may WRITE or only
   READ.
3. **Publishing the global CLAUDE.md content** (R5): moving it into the public repo makes doctrine
   world-readable. Content audit may surface lines Zero prefers private (seat economics, org names);
   the private-doctrine-repo fallback in R5's kill criterion is likewise a business choice.

## §8 — Meta-pattern (Gear 3)

Every finding in this report is one defective belief wearing different clothes: **"what we wrote is
what they read."** The archive header says "not auto-loaded" while it loads in full; the superscar
budget guards 1.8% of the payload it thinks it bounds; the repomap warns into a log nobody reads
(W76, again, today); the organism digest read a key its producer never emitted (W120); three copies
of the global doctrine each said something different and every session believed its own (2026-08-23);
the harness offered this lane a memory directory with nothing in it; MEMORY.md truncates silently at
a line cap (#40614). In every case the guardian, the budget, or the promise is attached to the
**artifact** (a file, a header, a warn), while the failure lives in the **delivery** (what a real
session actually received at turn 1). This is superscar family #2 — esiste ≠ armato — specialized to
context: *written ≠ read*. The antidote-class is single: measure the READ side. That is what this
lane did by hand (its own context was the instrument), what R1 automates (attestation of the
delivered surface), what R3 makes continuous (does the corpus actually surface when needed?), and
what R6 timestamps (is what they read still true?). The organism already knows this antidote in
other tissues — proprioception stamps its own age, the healer "re-executes receptors fresh, nothing
recalled from context" — it has simply never pointed that discipline at the context pipeline itself.
The deepest version: an organism whose defining asset is written memory must treat *delivery of that
memory* as a monitored organ, not as a property of files.

## §9 — Sources (all accessed 2026-08-28)

1. Anthropic — *Effective context engineering for AI agents* (Sep 2025) — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — the harness vendor's own doctrine: attention budget, compaction, sub-agents, JIT retrieval.
2. Chroma — *Context Rot: How Increasing Input Tokens Impacts LLM Performance* (Jul 2025) — https://www.trychroma.com/research/context-rot — 18-model controlled study; the degradation-onset numbers this report's headline collides with. Replication toolkit: https://github.com/chroma-core/context-rot
3. Yichao "Peak" Ji, Manus — *Context Engineering for AI Agents: Lessons from Building Manus* (Jul 2025) — https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus — production agent economics: KV-cache hit rate, stable prefixes, file-system-as-context, recitation.
4. Gloaguen et al., ETH Zürich / LogicStar — *Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?* (Feb 2026) — https://arxiv.org/abs/2602.11988 — the only controlled experiment on repo context files: no median gain, +20% cost.
5. Cognition — *Don't Build Multi-Agents* (Jun 2025) — https://cognition.com/blog/dont-build-multi-agents — context-sharing principles: full traces, not summaries.
6. Cognition — *Multi-Agents: What's Actually Working* (Dec 2025) — https://cognition.com/blog/multi-agents-working — the update: multi-agent works when writes stay single-threaded.
7. Aider — *Repository map* docs + *Building a better repository map with tree-sitter* (Oct 2023, maintained) — https://aider.chat/docs/repomap.html — the origin of the organism's repomap design; PageRank + hard token budget.
8. Mem0 — research & benchmark page (2025-26) — https://mem0.ai/research — LoCoMo 92.5 / LongMemEval 94.4 at 3-4× lower token cost; the retrieval-over-injection number.
9. Rasmussen et al., Zep — *Zep: A Temporal Knowledge Graph Architecture for Agent Memory* (Jan 2025) — https://arxiv.org/abs/2501.13956 — temporal validity intervals on facts; the formalization of W90's lesson.
10. Packer et al. — *MemGPT: Towards LLMs as Operating Systems* (Oct 2023) — https://arxiv.org/abs/2310.08560 — the tiered-memory paradigm MEMORY.md + overflow bodies re-implement manually.
11. Xu et al. — *A-MEM: Agentic Memory for LLM Agents* (NeurIPS 2025) — https://arxiv.org/abs/2502.12110 — Zettelkasten linked notes; the `[[name]]` convention, done by machine.
12. Park et al. — *Generative Agents: Interactive Simulacra of Human Behavior* (UIST 2023) — https://arxiv.org/abs/2304.03442 — recency × importance × relevance retrieval + reflection; the ranking MOS recall lacks.
13. AGENTS.md — open specification (Aug 2025; >60K repos, >20 tools by Dec 2025) — https://agents.md — the industry convention Nuzantara's CLAUDE.md chain predates and exceeds.
14. Answer.AI / Jeremy Howard — *The /llms.txt file* (Sep 2024) — https://llmstxt.org — docs-as-context convention; ~10% adoption per SE Ranking's 300K-domain study.
15. Anthropic — *Prompt caching* platform docs (2024-26) — https://platform.claude.com/docs/en/build-with-claude/prompt-caching — 0.1× cache reads, TTL-refresh-on-read, cache reads excluded from rate limits: why the boot tax is an attention problem, not a quota problem.
16. Claude Code docs — memory hierarchy (CLAUDE.md scopes, auto-memory, MEMORY.md index; subagent context separation) — https://code.claude.com/docs/en/memory — the platform's native convergence toward the MOS design.

## Adversarial review

Blind cross-family review (generator ≠ grader), 2026-08-29. The refuters received the full document and the panel's hard rules, nothing else; path existence had already been verified on disk by the orchestrator's gate, so they attack logic, numbers, rule-compliance and the SOTA claims. Dispositions by the orchestrator (claude-fable-5, Zero's manual selection): **survives** = recorded as a standing caveat, not fixed in this PR; **rejected** = the objection misreads the document or the rules (reason given); **accepted** = fixed in the text.
Tally: 8 raised · 4 survive · 1 rejected · 3 accepted.

**Reviewer: `codex`** — OpenAI GPT-5.6 sol at effort high via Codex CLI (read-only sandbox on the repo snapshot). 8 raised.

| # | sev | objection (refuter's words) | disposition |
|---|---|---|---|
| 1 | HIGH | "model: claude-fable-5 (pinned lane)" — A pinned panel lane implies scripted routing unless manual selection is evidenced; none is. That conflicts directly with the manual-only Fable rule. | rejected — the lane ran under Zero's explicit manual order for this one panel (2026-08-28: "lancia per ognuna un fable 5 max effort"), pinned by the orchestrating session, not by any script, cron or doctrine; the frontmatter now carries `model_selection:` stating this |
| 2 | HIGH | "logs what it WOULD inject for 2 weeks without injecting" — Shadow logs and later transcript injection lack mandatory redaction or sensitivity gates, so mandate-linked memory content could persist, violating the PII/OSINT output boundary. | survives — valid: any shadow-log or transcript-side attestation must pass a redaction gate before persisting; recorded as a constraint on R1's build PR |
| 3 | HIGH | "PR-1 `chore(context): scar re-cold-storage + injected-surface attestation` (R1)" — R1’s 120 KB budget is explicitly needs-ruling, yet the roadmap schedules implementation unconditionally. R5 repeats this mistake with public doctrine migration. | accepted — the 120 KB figure is a §E ruling; the INDEX's F1 now reads '≤ the ruled budget' and the roadmap's PR-1 is conditional on it |
| 4 | HIGH | "a CI test that assembles the exact set of files the harness injects" — CI reconstructs expected files; it cannot observe the delivered prompt or hidden harness behavior. A SessionStart byte-sum has the same limitation, so this cannot catch the claimed no-repo-diff drift. | survives — valid: a CI reconstruction cannot observe the delivered prompt; the receptor must read the session-side transcript, which is what the INDEX's move #1 now calls 'read-side attestation' |
| 5 | MED | "Seven days later the injected surface is ~5× larger" — The earlier baseline includes MEMORY.md but excludes both scar bodies; the new total does the reverse. These are different surfaces, so the 5× temporal comparison is invalid. | survives — the two surfaces are not identical; the 5× figure is directional until re-measured on one definition |
| 6 | MED | "a headless seat lane can reach 0 of the 1,681 memory files" — The report itself reads and counts the canonical corpus, disproving zero reachability. What was measured is zero seat-local or auto-loaded files, not zero accessible files. | accepted (wording) — the measurement is zero seat-local/auto-loaded files, not zero accessible files |
| 7 | MED | "squarely inside the rot zone" — The cited onset is 300–400K tokens, while boot is estimated at 190–220K and historical average at 290K. That is approaching the lower bound, not squarely inside it. | accepted (wording) — 'approaching the onset' is the supportable phrase; 'squarely inside' overstated it |
| 8 | MED | "the benchmark existing IS the metric" — Existence is not a correctness metric. TRAUMA-derived queries risk copying lexical answers from their gold scars, while model, trials, scoring protocol, and contamination controls remain unspecified. | survives — ScarBench needs a scoring protocol and contamination controls before its existence counts as a metric |

Refuter's verdict: I would not let this report stand as evidence until delivery is measured externally, comparisons use identical surfaces, hard-rule violations are removed, and ScarBench is independently validated.

