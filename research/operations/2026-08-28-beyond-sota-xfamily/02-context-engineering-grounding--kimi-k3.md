---
panel: beyond-sota-xfamily
lane: 02-context-engineering-grounding
seat: kimi-k3
model: "kimi-code/k3 · Kimi CLI print mode (tools)"
started: 2026-08-28T18:24:50Z
finished: 2026-08-28T18:31:46Z
duration_s: 416
exit: 0
words: 3979
prompt_sha256_16: 5d8d1f951089dd48
prompt_chars: 18779
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

• I'll ground in the repo first: locate the context-engineering machinery (hooks, memory, skills, doctrine) inside this snapshot.

• Repo grounding is solid. Moving to the web SOTA survey now.

• All grounding and survey work is done. Delivering the report as my final message.

  ---

  ---
  date: 2026-08-28
  domain: operations
  panel: beyond-sota-2026-08-28
  part: 2/13 — Context engineering & grounding
  model: Moonshot Kimi K3 (pinned lane, Kimi CLI)
  sources: 12
  repo_files_verified: 25
  status: complete
  ---

  # Lane 2 — Context engineering & grounding: what a session knows at turn 1

  **Access note (binding constraint).** This lane runs inside a read-only snapshot (`…/scratchpad/panel/xsnap_clean`). Everything under `$HOME` — `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, `~/.claude/scripts/mem`, the MOS capture hooks, `~/.nuzantara-repomap.txt`, and the entire `MEM:` memory directory (1707 files, `MEMORY.md` index, the two named discovery memories) — is **unavailable**. Where the brief references them I say so and use the repository's own vendored copies, hook source code, and the measured numbers those files themselves recorded. No file was written; per lane instructions the deliverable is this message, so the protocol's post-write `ls`/`wc` probe is not applicable.

  ## 0. TL;DR

  Nuzantara is **AHEAD of SOTA on enforced context budgets** (CI-armed byte caps on injected doctrine — nobody else does this) and on **scars-as-context**, but **BEHIND on memory architecture** (FTS5 keyword recall vs. the field's temporal knowledge graphs), **BEHIND on doctrine consistency** (three diverging copies of the same law), and **BEHIND on measurement** (no recall evaluation of anything injected; the field now has LongMemEval and Chroma's context-rot numbers). Biggest gap: injected context is treated as ground truth while the organism's own scar corpus proves it is routinely stale, truncated, or divergent — and nothing measures whether any of it is actually read. Top-3 moves: (1) a CI-enforced **total boot-context budget with a per-source "context bill"** (extend the superscar/MEMORY.md pattern to the whole injection surface); (2) **doctrine federation** — one canonical source compiled to all machine copies with sha256 parity in CI (cures superscar #1's doctrine variant, 23-day measured drift); (3) a **LongMemEval-style recall bench for MOS + injected doctrine** so "is it known?" becomes a number, not a hope.

  ## 1. How Nuzantara does it today (verified on disk)

  **SessionStart injection — project layer.** `.claude/settings.json:9-27` registers three SessionStart hooks: `scripts/hooks/escalations_alert_sessionstart.sh`, `proprioception_sessionstart.sh`, `organism_digest_sessionstart.sh`. All three share one design contract, verified in their headers: **fail-open, hard time budget (4s/6s via SIGALRM, `proprioception_sessionstart.sh:37`), never-silent "anti-calm-liar" output** — even all-quiet prints a heartbeat so silence means exactly one thing (not armed). Outputs are line-capped snapshots (escalations: HIGH-first, 14-day freshness window; proprioception: top-4 divergences + explicit "+N more" line, `proprioception_sessionstart.sh:118-123`). The proprioception hook embeds a hard-won grounding rule: every printed finding is labeled *"as of {ts} — re-verify before acting"* (`:111`), born from incident #44 where a cured divergence was read as live fact for days.

  **Repomap.** `scripts/build_repomap.sh` builds `~/.nuzantara-repomap.txt` via aider tree-sitter (ctags fallback), target 4–20KB / ~1–5K tokens (`build_repomap.sh:17`), cron-refreshed every 15 min, injected at SessionStart only if age <30 min (project `CLAUDE.md` §7bis, lines 188–195). The header itself records a measured failure: the ctags fallback once indexed minified webpack chunks, injecting **188KB of noise per session** instead of the 4–20KB target (2026-06-13 connectome audit).

  **Superscar as universal context.** `.claude/rules/cicatrix-superscar.md` (13,986 bytes — **14 bytes of headroom** against its budget) is injected into *every session and every subagent* (its own preamble, lines 12–14: "ciò che aggiungi lo paga tutta la flotta, per sempre"). The budget is CI-armed: `scripts/tests/test_superscar_budget.py` (`BYTE_BUDGET = 14_000`, plus a completeness tripwire that every cited W-number has a real body). This is the strongest context-discipline artifact in the repo.

  **MEMORY.md / MOS.** The index and bodies live outside the snapshot, but the repo contains their enforcement machinery: `.claude/hooks/memory_budget_gate.py` documents the harness's silent read cliff (24.4 KiB, empirically verified 2026-08-24 at 25,067 B "over" / 24,414 B "approaching") and that the index sat at **25.4 KB — already over the cliff, tail silently dropped, for an unknown period**. The gate refuses growth writes past the cliff (shrinking writes always allowed, fail-open on uncertainty, byte-accurate UTF-8, path-aware per superscar #1). Project `CLAUDE.md:94-108` defines the MOS CLI (`mem query/save/recent`, FTS5, importance tiers, mandatory proactive saves) and the routing rule "`mem` PRIMA di `notebook_query`". The MOS capture hooks (`mos_capture_*.py`, `precompact-mnemos.py`) and `mem` CLI itself are `$HOME`-only — unavailable; not vendored in the repo (infra/claude-hooks/ holds 20+ other hooks but no MOS capture), which is itself a finding (HOME-fork exposure, superscar #1).

  **Doctrine corpus, measured.** Project root: `CLAUDE.md` 44,523 B · `AGENTS.md` 37,243 B · `SYMBIOSIS.md` 38,435 B · `VADEMECUM.md` 21,459 B · `INDEX.md` 11,564 B. `docs/SYSTEM_BRIEF_FOR_AGENTS.md` 12,360 B exists specifically as the ground-truth brief for *external* agents. The global `~/.claude/CLAUDE.md` is unavailable, but its divergence from the project copy is measured fact (§2). Claude Code upstream loads `MEMORY.md` capped at 200 lines/25KB and CLAUDE.md up to 4 MiB (verified in vendor docs, §3) — so the project CLAUDE.md at ~11K tokens is within harness limits but far above Anthropic's own "under 200 lines" adherence guidance.

  **Corner skills as shared live state.** `.agents/skills/` holds 9 corners (bot, wr2, visaoracle, kbli-navigator, secondhome, subhi, bz-video-production, google-flow-video + README); five are symlinked into `.claude/skills/`. Verified pattern in `visaoracle/SKILL.md`: a "CURRENT HANDOFF (read first)" block, an ENFORCE-GATE with dated canonical ruling, LIVE STATE entries — these are mutable cross-session blackboards, the organism's closest thing to A-MEM's evolving notes. `.claude/skills/skill-catalog/SKILL.md` is the anti-bloat escape valve: only Tier-1 skills installed; everything else catalogued in MOS (`SKILL-CATALOG:` entries) and installed on demand — explicitly motivated by an "orchestration-decay 8→0" context-bloat regression. Notably it documents that FTS5 breaks on the hyphenated prefix itself — a measured limitation of keyword memory.

  **Compaction / handoff.** `.claude/commands/resume.md` (vendored canon, shadows `$HOME`) re-injects Mnemos precompact-handoff JSON post-compact, with a strict no-fabrication clause ("if no handoff file found → state so"). `.claude/skills/modus/SKILL.md` §STATE & RE-ENTRY (lines 88–106) is the doctrine: durable state in files not the window; three concrete receptor types; on wake "re-run a light GROUND — the disk may have moved while you slept"; `/cd` relocates without cache rebuild.

  **Anti-hallucination.** `CLAUDE.md:168-176` — never cite tool output not executed *this turn*; `infra/workflows/verify-template.js` makes refuter-on-fresh-context the default path. NotebookLM (8+1 curated notebooks, `docs/NOTEBOOKLM_STRATEGY.md`) is the bipolar ground-truth verifier.

  **Total boot tax (estimated, assumption stated).** Claude-side: project CLAUDE.md (44.5KB) + global CLAUDE.md (unknown; assume comparable, ~40KB) + superscar (14KB) + MEMORY.md (≤25KB, was over) + repomap (~8KB) + three hook outputs (~1–2KB) ≈ **~130KB ≈ 33K tokens ≈ 16% of a 200K window** — before turn 1. For non-Claude agents (Kimi/Codex), AGENTS.md (37KB) substitutes/duplicates. No single artifact measures or enforces this total.

  ## 2. Scars & ledger evidence

  - **Superscar #1 (HOME-fork), dominance 65–75% with #2/#5/#4** (`cicatrix-superscar.md:18`): the doctrine-copy variant is measured in `.claude/skills/modus/AMENDMENTS.md` (2026-07-25): global CLAUDE.md pinned `opus-4-8`/`sonnet-4-6` while the repo copy had moved to the Claude-5 roster — **two copies of the same law disagreed for 23 days**, and `mem query "opus 5"` returned zero hits while the live harness already ran Opus 5. The proposed cure (one canonical roster table, GROUND-stage divergence check) is ledgered, not armed.
  - **W76**: repomap built on a stale checkout — the injected map itself was a HOME-fork casualty (superscar #1 member).
  - **W90** (`cicatrix-scars.md:507`): the ground-truth verifier (NB-3) served a stale snapshot and "confirmed" pre-resolution numbers — *even the verifier is a lead*.
  - **W100**: same-family blind agreement certified 7 false-clean of 8 (54%) — agreement measured transcription fidelity, not truth. Directly relevant to context: a refuter on inherited context inherits the hallucination.
  - **W97 / proprioception #44 / W113**: display caps and snapshot assertions read as complete/live facts — injected context's truncation and staleness are recurring, measured failure modes. The organism's own pattern name: *"curato 1 wrapper su 5"*.
  - **AMENDMENTS 2026-08-23 (torn snapshot)**: a Kimi K3 refuter read a live worktree mid-edit and returned a fabricated CRITICAL finding — "indistinguishable in tone from a true finding." Cure adopted: refuters dispatched only against immutable `git archive <sha>` snapshots. This panel runs on exactly that cure.
  - **MEMORY.md over-cliff incident** (memory_budget_gate.py docstring): 25.4KB > 24.4KiB, tail silently dropped "for an unknown period" — the entries lost were the load-bearing workflow rules at the file's bottom. A commons-with-no-enforcement failure, now gated.
  - **The 188KB repomap noise incident** and the panel's own measurement — **fork lanes inheriting ~90K tokens of session context exhausted the account window in minutes** — are the two ends of the same disease: unbudgeted context.
  - **PENDING-ARMS** (grep-only per protocol): multiple rows show injected-context staleness being worked around by re-verification ritual ("All receptors re-executed fresh this turn, nothing recalled from context (W65/W90)" recurs verbatim across healer ticks — the discipline is practiced manually, not mechanized).

  ## 3. World SOTA survey

  | System / practice | Source | Mechanism | Measured effect | Transfer to this organism |
  |---|---|---|---|---|
  | Anthropic context engineering (compaction, note-taking, subagents, just-in-time retrieval) | anthropic.com, Sep 2025 | "Smallest set of high-signal tokens"; attention budget; hybrid CLAUDE.md-up-front + grep-on-demand | Qualitative; frames context rot as the constraint | Directly applicable; Nuzantara already embodies the hybrid but violates "smallest set" at boot (~130KB) |
  | Claude Code memory system (CLAUDE.md + auto memory, MEMORY.md 200 lines/25KB cap, path-scoped rules) | code.claude.com docs, accessed 2026-08-28 | Two-tier memory; index truncation; rules load on file-match; hooks for enforcement | The 25KB cliff Nuzantara hit is the documented design | Nuzantara's budget gate *exceeds* the vendor (they warn post-write; the gate refuses pre-write) |
  | Chroma Context Rot (18 models) | research.trychroma.com, Jul 2025 | Controlled input-length isolation; distractors; LongMemEval full-vs-focused | Performance degrades non-uniformly with length; focused ~300-token prompts beat 113K full history across all families | Justifies capping boot tax and preferring focused injection over full-history inheritance (the 90K fork failure) |
  | Lost-in-the-Middle | arXiv 2307.03172, Jul 2023 | Position-swap of relevant passage in multi-doc QA | U-shaped recall: beginning/end ≫ middle | Boot layout matters: load-bearing rules at the *bottom* of MEMORY.md were exactly the dropped ones |
  | Aider repo map | aider.chat/docs | tree-sitter signatures + graph-ranking (PageRank-ish) under `--map-tokens` budget (default 1K) | Industry-standard; Nuzantara's repomap *is* aider | AT parity; Nuzantara lacks aider's *dynamic relevance ranking* — its map is static, 15-min cron |
  | Cognition: "Don't Build Multi-Agents" | cognition.ai, Jun 2025 | Share full agent traces; actions carry implicit decisions | Argumentative, widely cited | In tension with context rot; Nuzantara's resolution (immutable snapshot + fresh-context refuter) is arguably *better than both* |
  | MemGPT / Letta | arXiv 2310.08560, Oct 2023 | OS-style virtual context: tiered memory, self-directed paging | Solved doc-analysis beyond window | MOS is the same idea hand-rolled (FTS5 + files), minus the agentic paging |
  | Mem0 | arXiv 2504.19413, Apr 2025 | Extract→consolidate→retrieve salient facts; graph variant | +26% LLM-judge over OpenAI memory; −91% p95 latency; −90% tokens vs full-context | Consolidation step is what MOS lacks: 1707 flat files, no dedup/evolution |
  | Zep / Graphiti | arXiv 2501.13956, Jan 2025 | **Temporal** knowledge graph over episodes; invalidation edges | 94.8% DMR (vs MemGPT 93.4%); +18.5% LongMemEval; −90% latency | Temporal invalidation is exactly the stale-injected-fact disease (W90, #44); Nuzantara has Postgres+Qdrant already |
  | A-MEM | arXiv 2502.12110, Feb 2025 | Zettelkasten: structured notes, dynamic links, memory *evolution* | SOTA on six models vs MemGPT/Mem0 baselines | Corner skills are proto-A-MEM notes; missing the automatic linking/evolution |
  | Generative Agents | arXiv 2304.03442, Apr 2023 | Recency×importance×relevance retrieval; reflection into higher-level memories | Ablation: each component critical | MOS has importance scoring; no reflection layer (lane 10 owns writing; lane 2 notes the *retrieval* lacks recency weighting) |
  | LongMemEval | arXiv 2410.10813, Oct 2024 | 500-question bench: extraction, multi-session, temporal, knowledge-update, abstention | Commercial assistants drop ~30% on sustained memory | The missing instrument: Nuzantara has zero recall measurement of MOS/injected doctrine |

  The three that matter most: **Chroma's context rot** (turns "keep context tight" from taste into measurement — focused 300-token contexts beat 113K full ones; directly indicts 90K fork-lane inheritance), **Zep/Graphiti** (temporal invalidation — a memory that knows it is stale — is the precise antidote to the W90/#44/W76 family), and the **Claude Code memory docs** (the vendor's own 25KB/200-line design confirms Nuzantara's measured cliff and shows the vendor stopping at a warning where Nuzantara already built a gate — evidence the organism is ahead on enforcement, behind on architecture).

  ## 4. Position vs SOTA

  | Sub-dimension | Position | Evidence |
  |---|---|---|
  | Enforced budgets on injected context | **AHEAD** | `test_superscar_budget.py` (14,000 B CI tripwire); `memory_budget_gate.py` (pre-write refusal vs vendor's post-write warning). No surveyed system CI-enforces context bytes |
  | Scars-as-context | **AHEAD** | 14KB superscar injected fleet-wide, 99+ measured failures compressed into 10 families with antidotes — no surveyed analog; closest is Anthropic's "curate examples from failure modes," done here at industrial scale |
  | Never-silent receptors / anti-calm-liar | **AHEAD** | three SessionStart hooks with explicit silence-is-broken contracts; Chroma/Anthropic don't address boot-receptor liveness at all |
  | Repomap | **AT** | literally aider's mechanism, but static (cron) vs aider's dynamic graph-ranked relevance; W76 staleness scar |
  | Compaction / handoff | **AT** | precompact-mnemos + `/resume` + modus re-GROUND doctrine ≈ Anthropic's compaction+notes prescription |
  | Skill discovery on demand | **AT/AHEAD** | tiered catalog queried via MOS beats "install everything"; Cursor/Copilot have no equivalent discovered in survey |
  | Memory architecture (MOS) | **BEHIND** | FTS5 keyword recall, no consolidation (Mem0), no temporal invalidation (Zep), no linking/evolution (A-MEM), no recency-weighted retrieval (generative agents); the hyphen-breaks-FTS5 note in skill-catalog is the canary |
  | Doctrine consistency across machines | **BEHIND** | 3 copies, 23-day measured divergence (AMENDMENTS 2026-07-25); superscar #1 is the dominant family at 65–75% |
  | Measured recall / context evaluation | **BEHIND** | zero LongMemEval-style measurement of anything injected; the 25.4KB-over-cliff incident was discovered by accident |
  | Subagent/fork context discipline | **BEHIND (self-measured)** | 90K-token fork inheritance exhausted the account window in minutes — Cognition's trace-sharing taken to the worst extreme; the immutable-snapshot cure (AMENDMENTS 2026-08-23) is adopted for refuters but not generalized |
  | Boot-context total budget | **BEHIND** | ~130KB/~33K tokens estimated, unmeasured as a whole; per-source budgets exist only for superscar and MEMORY.md |

  ## 5. Beyond-SOTA recommendations

  Ranked by (impact × confidence) / cost.

  **R1 — The Context Bill: one CI-enforced budget for the entire boot injection.** *What:* a manifest (`infra/context-budget.yaml`) declaring every injected source (CLAUDE.md global+project, superscar, MEMORY.md, repomap, each SessionStart hook's max output, AGENTS.md for external seats) with a per-source cap and a total cap (~60KB ≈ 15K tokens); a `scripts/lint_context_budget.py` computing actual bytes per machine, CI-armed like `test_superscar_budget.py`. *Why beyond SOTA:* every surveyed system budgets *one* artifact (aider's map-tokens, Claude Code's 25KB) — nobody budgets the *composition*, and Nuzantara is the only organism with the per-source enforcement muscle already built to extend. Exploits the hooks-as-backstop asymmetry. *Cost:* ~2 days, Gear 2, flat-sub only. *Risk:* superscar #2 (gate exists but unarmed) — mitigate by adding the check to an already-required CI context, never a new one (W69). *Metric:* boot bytes/session measured via hook-wrapped logger; before ≈130KB estimated unenforced → after ≤60KB enforced, breach = CI red. *Kill:* if measurement shows genuine need >80KB, the premise (context rot at these sizes) is wrong for this workload — publish the number instead. *First PR:* manifest + linter + tests, ≤350 lines.

  **R2 — Doctrine federation: one source of law, compiled copies, sha256 parity gate.** *What:* make the repo `CLAUDE.md` the single canonical text; the global and machine copies become *generated artifacts* (import shim or verbatim copy) refreshed on `git pull`; extend `scripts/lint_home_fork.py` (already sha256-ing 97 declared pairs, superscar #1's executable antidote) to cover the three doctrine copies plus the MOS capture hooks and `mem` CLI — which are currently `$HOME`-only and should be vendored like `resume.md` was (its header documents exactly this pattern: "Edit HERE, never in $HOME"). *Why beyond SOTA:* no surveyed system has three diverging copies of its law because no surveyed system is a 3-machine fleet running 5+ concurrent agent families; the fix composes two mechanisms the organism already trusts (vendored canon + home-fork lint). *Metric:* doctrine drift-days: 23 (measured) → 0 enforced; `lint_home_fork.py` declared pairs 97 → 97+N_doctrine. *Cost:* 1–2 days, Gear 2. *Risk:* #1 recidiva if a machine skips pull — the parity lint runs against `origin/main`, never local checkout (W106b lesson). *Kill:* none needed; pure consistency. *First PR:* vendor MOS scripts into `infra/claude-hooks/` + lint pairs, ≤300 lines.

  **R3 — Recall bench for injected context (LongMemEval-for-the-organism).** *What:* a `tests/context_recall/` harness: ~100 canary questions whose answers live in specific injected artifacts ("which family covers HOME-fork?", "what is the embedding model?", temporal ones: "which roster is current?"), run monthly by a cheap flat-sub seat against fresh sessions; score by artifact and by position (first/middle/last third of injection). *Why beyond SOTA:* LongMemEval measures chat assistants; nobody measures *their own doctrine injection* as a recall surface, and Nuzantara is uniquely able: the artifacts are versioned, the questions can be generated from the scar corpus, and the 6-seat fleet makes generator≠grader trivial. *Metric:* recall % per artifact per position; baseline expected to reproduce the U-curve and expose dead zones (the dropped MEMORY.md tail was discovered by accident — this makes discovery systematic). *Cost:* ~3 days + ~30 min/month compute, Gear 2, flat-sub. *Risk:* #2 (bench built, never scheduled) — arm it in the same PR as a cron + healer receptor line. *Kill:* if recall is ≥95% everywhere for 3 consecutive runs, the boot tax is healthy; reduce to quarterly. *First PR:* 40 hand-written canaries + runner + scoring, ≤400 lines.

  **R4 — Generalize the immutable-snapshot dispatch to every external seat, with a declared context budget per lane.** *What:* the AMENDMENTS 2026-08-23 freshness clause (refuter against `git archive <sha>`, never a live tree) becomes a dispatch-template field: every spawned lane declares `context_budget_tokens` and `context_source: snapshot|fresh|inherited`, with inherited >20K tokens requiring explicit justification. *Why beyond SOTA:* resolves the Cognition-vs-Chroma tension empirically — share *decisions and pointers* (Cognition principle 1) through a structured handoff artifact, not raw traces; the 90K fork failure is the measured cost of the alternative. No surveyed system makes context budget a first-class dispatch parameter. *Metric:* tokens-to-first-useful-action per lane; account-window exhaustion incidents (measured: minutes, this panel) → 0. *Cost:* 1 day, Gear 1–2. *Risk:* #3 (guard matches on token count, not on whether the handoff carries the right decisions) — pair with R3 canaries on handoff quality. *Kill:* if lanes with 20K caps show elevated re-dispatch rates, raise the cap and record it.

  **R5 — MOS v2: temporal validity + consolidation, reusing existing infra (needs-ruling on scope).** *What:* add `valid_from`/`valid_to`/superseded-by fields to MOS entries (the organism already runs bitemporal Postgres patterns elsewhere — see the PENDING-ARMS Research OS row), a nightly consolidation pass (Mem0-style dedup/merge) on a local model, and time-aware query expansion (LongMemEval's published optimizations). *Why beyond SOTA:* Zep proves temporal invalidation kills the stale-fact class that produced W90/#44/W76; doing it inside the existing FTS5+file stack, sovereign and flat-cost, is a composition none of the surveyed products targets (they're hosted services). *Metric:* stale-fact incidents recalled-as-current per quarter (W90-class): baseline ~4 identifiable in 2026 scars → target 0; memory corpus dedup ratio. *Cost:* 1–2 weeks, Gear 3 (architecture), local models only per hard rules. *Risk:* #9 (schema drift breaking 1707 existing files) — migrate read-compatibly, dual-read. *Kill:* if consolidation precision <90% on a 100-entry human-audited sample, stay at v1 + R3 measurement only.

  ## 6. 90-day roadmap + first PRs

  **Wave 1 (days 1–30) — measure and fence.** PR-A: "Context bill: manifest + linter + CI wiring" (files: `infra/context-budget.yaml`, `scripts/lint_context_budget.py`, `scripts/tests/test_context_budget.py`, one-line add to an existing required workflow; ~350 lines; Gear 2; acceptance: CI fails when any declared source exceeds cap or total >60KB, proven with a synthetic over-size fixture). PR-B: "Doctrine federation: vendor MOS scripts + extend home-fork lint" (`infra/claude-hooks/mos_*.py` vendored, `scripts/lint_home_fork.py` pairs +N; ~300 lines; Gear 2; acceptance: deliberate drift on a test pair produces exit 1 in CI). PR-C: "Dispatch context-budget field + immutable-snapshot default" (`infra/workflows/verify-template.js` + dispatch docs; ~150 lines; Gear 1; acceptance: a refuter spawned through the template receives an archive path, never a worktree path).

  **Wave 2 (days 31–60) — instrument recall.** PR-D: the R3 canary bench (40 questions + runner + scoring + cron arming + healer receptor line; ~400 lines; Gear 2; acceptance: first monthly run produces per-artifact per-position recall numbers committed to `research/operations/`). Use the results to reorder boot layout (load-bearing rules out of the middle — lost-in-the-middle is measured science, not taste).

  **Wave 3 (days 61–90) — memory architecture decision.** Gate on Wave-2 numbers: if recall <80% on temporal canaries, PR-E = MOS v2 schema + consolidation pilot (Gear 3, the only wave needing architecture review); else defer MOS v2 and bank the win.

  ## 7. Needs-ruling

  - **R5 scope/cost** (MOS v2): touches the organism's memory substrate; Gear 3 by the fleet rules; Zero decides GO.
  - **Publishing the context-budget methodology** (R1/R3 results) as outward content: Legge 5 — owner publishes, never the session.
  - None of Waves 1–2 requires credentials, GUI, or physical action; all are repo-internal and flat-sub.

  ## 8. §Meta-pattern

  One defective belief generates nearly every finding in this lane: **"if it is in context, it is known, current, and read."** The scar corpus is the refutation, repeated at every layer of the same shape: context can be *divergent* (three CLAUDE.md copies, 23 days; W76 repomap on a stale checkout), *silently truncated* (MEMORY.md tail, W97 display caps, the 188KB noise injection), *stale-but-fresh-looking* (#44's 4.6h-old divergence read as live; W90's verifier snapshot), *inherited past usefulness* (90K fork lanes; W100's blind agreement), or *present but unenforced* (advisory checks, prompt-level rules vs hooks). The organism's own doctrine already names the cure — "documentazione non è un recettore; un hook sì" (`CLAUDE.md:186`) and "mai citare output di un tool senza averlo eseguito in QUESTO turn" (`CLAUDE.md:170`) — but applies it piecemeal, one wrapper of five at a time. The beyond-SOTA move is to lift that principle from ritual to mechanism: every injected byte gets a budget (R1), a single source (R2), a freshness marker, and a measured recall (R3). The world is currently debating *what* to put in context; this organism is positioned to be the first to *prove*, continuously, that its context is true.

  ## 9. Sources

  1. [Effective context engineering for AI agents — Anthropic Applied AI](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — accessed 2026-08-28. The field's canonical framing: attention budget, compaction/note-taking/subagents, just-in-time retrieval.
  2. [Claude Code memory docs](https://code.claude.com/docs/en/memory) — accessed 2026-08-28. Vendor ground truth for the 200-line/25KB MEMORY.md cap, CLAUDE.md load semantics, and the "warning not gate" design Nuzantara exceeds.
  3. [Context Rot: How Increasing Input Tokens Impacts LLM Performance — Chroma](https://research.trychroma.com/context-rot) — accessed 2026-08-28. 18-model controlled study; focused-vs-full LongMemEval gap is the quantitative case against context inheritance.
  4. [Lost in the Middle — Liu et al.](https://arxiv.org/abs/2307.03172) — accessed 2026-08-28. U-shaped positional recall; governs boot-layout ordering.
  5. [Aider repo map docs](https://aider.chat/docs/repomap.html) — accessed 2026-08-28. The mechanism Nuzantara's repomap borrows, including the dynamic graph ranking Nuzantara lacks.
  6. [Don't Build Multi-Agents — Cognition](https://cognition.ai/blog/dont-build-multi-agents) — accessed 2026-08-28. "Share full traces" principle — the counter-position this organism's 90K fork failure stress-tests.
  7. [MemGPT](https://arxiv.org/abs/2310.08560) — accessed 2026-08-28. OS-style tiered virtual context; the conceptual ancestor of MOS.
  8. [Mem0](https://arxiv.org/abs/2504.19413) — accessed 2026-08-28. Extract-consolidate-retrieve; +26% judge score, −91% p95 latency, −90% tokens vs full-context — quantifies what consolidation buys.
  9. [Zep / Graphiti](https://arxiv.org/abs/2501.13956) — accessed 2026-08-28. Temporal knowledge-graph memory with invalidation; the antidote class for stale-injected facts.
  10. [A-MEM: Agentic Memory](https://arxiv.org/abs/2502.12110) — accessed 2026-08-28. Zettelkasten linking + memory evolution; the formal version of what corner skills do by hand.
  11. [Generative Agents — Park et al.](https://arxiv.org/abs/2304.03442) — accessed 2026-08-28. Recency×importance×relevance retrieval; ablation-proven components.
  12. [LongMemEval](https://arxiv.org/abs/2410.10813) — accessed 2026-08-28. The five-ability memory benchmark (~30% drop for commercial assistants); template for R3's canary bench.

  *Repo verification: 25 paths probed on disk this session (settings.json, 4 hook scripts, build_repomap.sh, superscar + test, memory_budget_gate.py, skill-catalog, modus SKILL/AMENDMENTS/PENDING-ARMS, resume.md, visaoracle corner, CLAUDE.md sections, doctrine byte-sizes, NOTEBOOKLM_STRATEGY, infra/claude-hooks inventory, .agents/skills inventory, git HEAD 11a3c89a2). `$HOME`/MEM items explicitly unavailable as stated in the access note.*

