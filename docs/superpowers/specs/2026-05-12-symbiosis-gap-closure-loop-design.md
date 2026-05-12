# SYMBIOSIS Gap-Closure Loop — Design Spec

**Date**: 2026-05-12
**Owner**: Antonello (Zero)
**Branch**: `feat/symbiosis-loop-2026-05-12`
**Mode**: Autonomous L2, mixed (docs default, code only with DeepSeek devils-advocate PASS)
**Wall-clock cap**: 3h
**Tri-panel verdict**: PASS (after empirical fact-check of briefing)

## Context

Symbiosis organism (cell-core + organism + genoma) is live H24 on Pro:

- 19 LaunchAgent attivi (supervisor + bridge + cell + observatory + heartbeat + 14 di contorno)
- 118 organi enrolled in `organs_registry.yaml` (target ≥100 SUPERATO)
- Redis stream `organism:events`: 3721 entries, consumer lag 0
- Cell observatory pulse #620 at 01:01:15 WITA, 1146 green / 3 yellow / 5 red ultime 24h
- SYMBIOSIS.md status table: 4/8 pilastri live, 1 quarantined (Consiglio), 1 design-hypothesis (Sogno), 2 partial (HGT FASE 3 incompleta, Simbiosi Fase 1)

5 documented gaps verified empirically by tri-panel (Claude Opus 4.7 + Gemini 3.1 Pro + DeepSeek Reasoner devils-advocate, 2026-05-12 01:20–01:45 WITA).

## The 5 gaps (reframed after fact-check)

### Gap 1 — Cell families silenti (cell_observatory_emit not set)

**Root cause empirically confirmed**:

- `packages/cell-core/cell_core/pulse.py:265` has emit hook `if observatory.is_enabled(): asyncio.create_task(observatory.emit_pulse_observed(...))`
- `observatory.is_enabled()` reads `CELL_OBSERVATORY_EMIT` env var
- Only `~/Library/LaunchAgents/com.cell.organism.plist` sets `CELL_OBSERVATORY_EMIT=true`
- seo-cell + mata-garuda runner plists: env var ABSENT → emit no-op
- seo_cell + mata_garuda/cells/sentinel_cell.py use `cell_core.PulseLoop` (verified: 16 imports of `cell_core.*` in seo_cell)

**MVA**: doc + plist source patches in `infra/launchagents/` repo (NOT live `~/Library/LaunchAgents/` — chmod 0444 hardened)
**Code change**: limited to env block in repo-level plist source files
**Refusal**: NO `launchctl bootout/bootstrap` autonomously. User runs manual kickstart after PR merge.
**Success criterion**: PR opened with repo-level plist patches + doc explaining manual kickstart procedure. CI green.
**Devils-Advocate veto trigger**: BLOCK if the doc suggests `launchctl` commands without explicit user approval gate.

### Gap 4 — Ghost MEMORY.md entry (`research/tst/2026-05-10-actual-architecture.md`)

**Reality**: file NEVER committed in any branch (`git log --all -- research/tst/` returns 0). Probably written via Write tool in 11-mag session, lost in branch-hijack scar before commit. MEMORY.md entry is a ghost reference.

**MVA**: edit MEMORY.md to:
(a) remove ghost line `2026-05-10 organism-architecture tst-actual-architecture → [research/tst/2026-05-10-actual-architecture.md] ...`
(b) write replacement reflection doc `~/Desktop/nuzantara/research/symbiosis/2026-05-12-tst-empirical-architecture.md` reconstructing what we DO know from disk (pulse.py:265-266, observatory.py:55-127, organism:events stream, organs_registry.yaml 118 entries)
**Refusal**: NO fabricating the original file with same date/name (would be hallucination). The replacement doc has explicit `replaces_ghost_entry: true` frontmatter.
**Success criterion**: MEMORY.md ghost line removed, new reflection doc committed under different name.
**Devils-Advocate veto trigger**: BLOCK if new doc contains content not verifiable from current disk state.

### Gap 3 — HGT FASE 4 HALT recovery spec

**Reality**: commit `68efc17e3` HALT premise was correct:

- `apps/crm-cell/crm_cell/hgt_publisher.py`: STUB (line 79 says "Sprint 4: call into self.\_hgt_stream.xadd(...)"); never writes to Redis. No `__main__`.
- `apps/bali-intel-scraper/backend/cell/hgt_publisher.py`: lib class. No `__main__`. `IntelScraperCellRunner` shelf-ready but not invoked by `scripts/run_intel_pipeline.py`.
- `HGTConsumer` wired in `mata_garuda/cells/sentinel_cell.py` BUT loaded sentinel cron uses different entry script bypassing cell layer.

**MVA**: doc `~/Desktop/nuzantara/research/symbiosis/2026-05-12-hgt-fase4-recovery-spec.md` listing 3 prereq tickets:

- TICKET A: implement `crm_cell/hgt_publisher.py` xadd call + `__main__` entry
- TICKET B: wire `IntelScraperCellRunner` into `scripts/run_intel_pipeline.py`
- TICKET C: switch sentinel cron entry script to one that goes through `mata_garuda/cells/sentinel_cell.py`
  **Refusal**: NO runtime activation of HGT. Doc-only.
  **Success criterion**: recovery spec committed with verifiable file:line refs.
  **Devils-Advocate veto trigger**: BLOCK if recovery spec recommends activation without all 3 prereqs done.

### Gap 2 — Consiglio v1 decision matrix (v2 OR kill)

**Reality**: PR #468 commit message confirms: "never produced a single deliberation: council.db was never created on either Pro or Mini, no log entries match council, the weekly LaunchAgent was meant for Air which was decommissioned before any cron landed". Code quarantined at `apps/mata-garuda/.disabled-2026-05-06/council/`. PR also lists 5 multi-LLM patterns already used that overlap Consiglio's function (wave-orchestrator, tri-LLM panel review, bipolar verifier, ad-hoc brainstorm, MOS auto-save).

**MVA**: doc `~/Desktop/nuzantara/research/symbiosis/2026-05-12-consiglio-v2-or-kill.md` — decision matrix:

- Column A: what Consiglio v1 promised (Pillar 4 Confronto)
- Column B: which existing pattern delivers each promise today
- Column C: gap (if any) — what's NOT covered by current patterns
- Verdict: KILL if column C is empty; v2 minimum-spec if column C lists ≥1 real gap
  **Refusal**: NO unquarantine without v2 spec. If verdict=KILL, write the kill rationale + suggest archival to `cicatrix-scars.md`.
  **Success criterion**: decision doc committed with verdict + 5-pattern overlap analysis.
  **Devils-Advocate veto trigger**: BLOCK if v2 spec is proposed but column C is empty/contrived.

### Gap 5 — 12+1 mata-garuda LaunchAgents double-firing (cleanup design)

**Reality**: cicatrix STRUCTURAL 2026-05-07 (in `cicatrix-scars.md`): 13 labels load simultaneously on Pro+Mini, both producing same heartbeat at same schedule. `wave1-pro-mini-dup-resolver.sh` exists but never invoked because Wave-1 catalogue assumed single-source plists. Blast radius per organ documented. Cleanup PR deferred.

**MVA**: doc `~/Desktop/nuzantara/research/symbiosis/2026-05-12-matagaruda-double-firing-cleanup-design.md`:

- per-organ decision (a) Pro-only, (b) Mini-only, (c) leader-election — with rationale (resource locality, external API tokens, Postgres locality)
- PR plan: which plists to remove on losing side
- resolver hardening proposal: extend `wave1-pro-mini-dup-resolver.sh` protected list to 13 labels
- CI test proposal: `apps/organism/tests/test_genome_no_active_active.py`
  **Refusal**: NO live `launchctl bootout` on either Pro or Mini. NO actual plist file deletion. Doc-only.
  **Success criterion**: cleanup design doc committed with per-organ decision table.
  **Devils-Advocate veto trigger**: BLOCK if any decision is "remove plist autonomously" rather than "draft PR for user review".

## Execution order

**1 → 4 → 3 → 2 → 5**

Rationale:

- Gap 1 first: highest empirical certainty (root cause known), code change is repo-level only
- Gap 4 second: quick win (ghost line removal + reflection doc), pure docs
- Gap 3 third: doc with verifiable file:line refs from disk
- Gap 2 fourth: doc with decision matrix against 5 known multi-LLM patterns
- Gap 5 last: doc with per-organ decision table; longest analysis surface

## Loop guard-rails

1. **Branch**: `feat/symbiosis-loop-2026-05-12` (created 2026-05-12 01:55 WITA, this commit)
2. **WIP commits**: every step ends with `git add -A docs/superpowers/specs/ research/symbiosis/ MEMORY.md infra/launchagents/ apps/ packages/` (scope-limited) + commit + push within 30s
3. **Telegram alerts**: `~/.claude/scripts/hotfix-notify.sh` on each step start, each commit, each BLOCK (best-effort, non-blocking)
4. **DeepSeek devils-advocate** at end of EACH step before commit:
   - Input: the artifact produced in the step + the briefing
   - Verdict: PASS / NEEDS_FIX / BLOCK
   - On BLOCK → loop stops, summary written
   - On NEEDS_FIX → 1 retry with feedback, then escalate
5. **Auto-stop triggers**:
   - DeepSeek BLOCK verdict (any step)
   - pytest red (only step 1 — code change)
   - 3h wall-clock cap reached (start = first commit on branch)
   - User-supplied STOP via memory or filesystem signal
6. **Plist hardening**: NO writes to `~/Library/LaunchAgents/com.*.plist` (chmod 0444). Only writes to `infra/launchagents/com.*.plist` repo sources
7. **Branch hijack mitigation**: WIP commit + push within 30s of artifact creation
8. **Final summary**: `~/Desktop/nuzantara/research/symbiosis/2026-05-12-loop-summary.md` with per-step verdict + commits + remaining work + Telegram notify

## Out of scope

- Live `launchctl` mutations (`bootstrap`, `bootout`, `kickstart -k`)
- Anything affecting production Fly.io (RAG backend, Postgres)
- Anything affecting Vercel frontends
- mata-garuda `.disabled-2026-05-06/council/` un-quarantine (covered by Gap 2 decision doc)
- HGT runtime activation (covered by Gap 3 recovery spec)
- Removing mata-garuda double-firing live plists (covered by Gap 5 cleanup design)

## Tri-panel artifacts

Brainstorm raw outputs persisted at:

- `/tmp/symbiosis-roadmap-brainstorm-2026-05-12/00_briefing.md`
- `/tmp/symbiosis-roadmap-brainstorm-2026-05-12/01_claude_response.md`
- `/tmp/symbiosis-roadmap-brainstorm-2026-05-12/02_gemini_response.md`
- `/tmp/symbiosis-roadmap-brainstorm-2026-05-12/03_deepseek_response.md`

After loop completion these are archived to `~/Desktop/nuzantara/docs/audits/2026-05-12-symbiosis-roadmap-brainstorm/`.

## References

- `SYMBIOSIS.md` (root) — 8 pilastri + 7 leggi
- `VADEMECUM.md` (root) — operative checklist
- `docs/SYMBIOSIS_TURNON_PLAN.md` — 4-fase plan 2026-05-06
- `apps/organism/organism/organs_registry.yaml` — 118 organi (Innervation Genoma)
- `.claude/rules/cicatrix-scars.md` — STRUCTURAL scars (branch hijack, plist corruption, EventBus outbox, 12+1 active-active, etc.)
