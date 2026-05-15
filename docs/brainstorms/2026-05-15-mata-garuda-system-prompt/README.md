# Eval: mata-garuda CLI `--system-prompt` → `--append-system-prompt` migration

**Date**: 2026-05-15
**Branch**: `eval/mata-garuda-system-prompt-cache-reuse-2026-05-15`
**Owner**: Zero
**Status**: 🟡 evaluation — no code change yet

## Context

User-global setting `~/.claude/settings.json:509` enables `excludeDynamicSystemPromptSections: true` (equivalent to CLI flag `--exclude-dynamic-system-prompt-sections`, default `false`). Effect: moves per-machine dynamic sections (cwd, env info, memory paths, git status) from the system prompt into the first user message → improves cross-session prompt-cache reuse.

Per Claude Code CLI help (verified 2026-05-15):

> Only applies with the default system prompt (ignored with `--system-prompt`).

## Audit results

Wrappers in the codebase that bypass the flag by using `--system-prompt`:

| Wrapper | Active? | Scope | Bypass |
|---|---|---|---|
| `apps/mata-garuda/mata_garuda/runtime/cli_runtime.py:59` (`CLI_CONFIGS["claude"]["system_flag"] = "--system-prompt"`) | ✅ 13 LaunchAgent `com.matagaruda.*` loaded | All mata-garuda agents | 🟠 Real |
| `scripts/zantara-gateway/claude_client.py:69` | ❌ No LaunchAgent, no process | Dormant code | 🟢 N/A |
| `scripts/wr2-external-bench-run.sh:91` | ✅ `com.balizero.wr2.external-bench.monthly` | Monthly bench | 🟢 Uses `--append-system-prompt`, not `--system-prompt` |

Active mata-garuda LaunchAgents (13):
- `watcher.daily`, `kg-linker`, `wr2-bridge.hourly`, `reg-alert.30min`
- `nlm-feeder-stream.hourly`, `nlm-expander.weekly`, `sentinel.hourly`
- `kita-feed.daily`, `weekly-digest`, `daily-briefing`, `public-channel`
- `wr-topic`, `invalidation-sweep`

Estimated invocations: ~50 `claude` subprocess calls/day across these agents.

## The trade-off

### Option A — Status quo (`--system-prompt`)

**Pros**:
- ✅ Each mata-garuda agent runs with ONLY its `GENOME.md` as system prompt — clean isolation
- ✅ Respects SYMBIOSIS Pillar 2 (OSINT blindato): no Nuzantara root context leaks into Mata Garuda agent reasoning
- ✅ GENOME.md is the single source of truth for agent behavior — predictable, auditable
- ✅ No risk of Claude Code's auto-loaded skills (superpowers, brainstorming, etc.) firing inside OSINT agent runs

**Cons**:
- 🔴 Bypasses `excludeDynamicSystemPromptSections` — ~3-8KB cache busted per invocation
- 🔴 At ~50 runs/day = ~150-400KB cache miss/day for mata-garuda alone
- 🔴 Loses cross-agent prompt-cache reuse (each agent type has its own GENOME → different system prompt anyway, but dynamic sections still get cached separately within each agent)

### Option B — Switch to `--append-system-prompt`

**Pros**:
- ✅ Honors `excludeDynamicSystemPromptSections` → cache reuse activated
- ✅ ~3-8KB/run saved in cache reads (Claude Code base prompt becomes the cached anchor)

**Cons**:
- 🔴 **Breaks isolation**: mata-garuda agents inherit Claude Code default system prompt (CLAUDE.md, MEMORY.md, hooks output, all loaded skills)
- 🔴 SYMBIOSIS Pillar 2 violation risk: Nuzantara root CLAUDE.md mentions team members, Bali Zero CRM context, Fly.io secrets — none should reach OSINT agent reasoning
- 🔴 Auto-loaded skills (e.g., `superpowers:using-superpowers`, `superpowers:brainstorming`) would fire inside watcher/kg-linker/etc. runs → unpredictable behavior, off-spec
- 🔴 GENOME.md was designed as standalone — appending to a 50KB+ default prompt changes the relative weight of instructions
- 🔴 `apps/mata-garuda/CLAUDE.md` explicitly forbids importing from `apps.mouth`, `apps.backend_rag`, etc. — but `--append-system-prompt` does exactly the metaphorical equivalent at prompt level

### Option C — Hybrid: keep `--system-prompt` BUT manually inline the dynamic sections we care about

**Approach**: extend `cli_runtime.py` to compose a richer system prompt that includes machine cwd / env if needed, but stays under mata-garuda control. Then the flag is irrelevant — we managed dynamic sections ourselves.

**Pros**: keeps isolation, optionally surfaces cwd/git/memory paths that mata-garuda agents would benefit from.

**Cons**: adds complexity. Most mata-garuda agents are self-contained (regulatory watcher, KG linker) and don't need cwd/git context. The benefit is marginal.

### Option D — Quantify before deciding

Run a 7-day cost telemetry on mata-garuda `claude` subprocess calls:
- Token usage per run (input cached vs uncached)
- Total cache hits / misses
- Wall-clock latency

Decision threshold: if cache miss cost <$0.50/month, status quo wins (isolation > marginal saving).

## Recommended path

**Default**: Option A (status quo). Isolation is structural to SYMBIOSIS Pillar 2 and OSINT blindato; cache reuse is a measurable but small win.

**Action**: add an inline comment in `cli_runtime.py:59` documenting *why* `--system-prompt` (not `--append-system-prompt`) is intentional, so future agents don't refactor for cache reuse.

**Escalate to Option B only if**: telemetry (Option D) shows >$5/month cache cost, AND a redesigned GENOME.md schema that explicitly handles the "Claude Code default + GENOME append" composition.

## Files referenced

- `apps/mata-garuda/mata_garuda/runtime/cli_runtime.py:55-73` — CLI_CONFIGS
- `apps/mata-garuda/CLAUDE.md` — SYMBIOSIS Pillar 2 enforcement
- `~/.claude/settings.json:509` — `excludeDynamicSystemPromptSections: true`
- `SYMBIOSIS.md` (repo root) — 8 leggi inviolabili, Pillar 2 OSINT blindato
- `~/.claude/CLAUDE.md` — global user instructions (would leak into mata-garuda if Option B chosen)

## Open questions

1. Does `--append-system-prompt` skip the auto-loaded skills (`using-superpowers`, etc.)? If yes, isolation risk is smaller than assumed. → **Test empirically before deciding.**
2. Can `excludeDynamicSystemPromptSections` be enabled per-invocation via env var, so it applies even with `--system-prompt`? → **Check Claude Code source / docs.**
3. Is the 13-LaunchAgent active-active Pro+Mini split (cf. cicatrix-scars line 213) about to halve invocation count? If yes, the cache-miss problem auto-resolves to ~25 runs/day before this PR even ships.

## Next step

Open GitHub issue tagging `@antonellosiano` for decision. Do NOT merge a code change on this branch until issue resolved.
