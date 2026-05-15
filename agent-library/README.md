# agent-library/

Operational snapshot of every agent in the Nuzantara stack: Claude Code
subagents, cross-tool agents (Cursor rules, Gemini skills), launchd crons
(agentic vs infra), and skill files.

## Files

| File | Purpose |
|---|---|
| `_generate-inventory.py` | Generator script — pure Python I/O, no network, no LLM, no secrets |
| `01-inventory.md` | Generated artifact — committed to git, **never hand-edited** |
| `README.md` | This file |

## When to regenerate

Regenerate manually after any of:

- New / renamed / removed file in `~/.claude/agents/*.md`
- New / removed `com.balizero.*.plist` in `~/Library/LaunchAgents/`
- New / removed `~/.claude/skills/*.md` with frontmatter
- New / removed `.cursor/rules/*.mdc` or `~/.gemini/skills/*.md`
- After a `git pull` that may have touched any of the above

There is **no autonomous cron** that regenerates this file — that's
intentional. Auto-regeneration on every commit would create noise; humans
decide when the snapshot is worth refreshing.

## How to regenerate

```bash
# From repo root
make inventory

# Or directly
python3 agent-library/_generate-inventory.py

# Dry-run (print to stdout, do not write file)
python3 agent-library/_generate-inventory.py --dry-run
```

Expected output: `Written: .../agent-library/01-inventory.md (NNNN bytes)`.
Runtime: ~1-2s on Pro.

## What the generator reads

- `~/.claude/agents/*.md` — Claude Code subagent frontmatter (skips `*.pre-T2`)
- `~/Library/LaunchAgents/com.balizero.*.plist` — launchd jobs (via `plutil -convert json`)
- `~/.claude/skills/**/*.md` — Claude skills with valid frontmatter
- `~/.gemini/skills/**/*.md` — Gemini skills
- `.cursor/rules/**/*.mdc` — Cursor rules (currently empty)

Cron scripts are classified **agentic** vs **infrastructure** by scanning
the first 30 lines for `\b(claude|gemini|nlm|codex|deepseek|ollama)\b`
(case-insensitive). No further content analysis — privacy + speed.

## Idempotency

Two consecutive runs produce a byte-identical artifact, provided no input
changes and they fall in the same minute (the header timestamp is
truncated to `%Y-%m-%d %H:%M`). The output ordering is deterministic:
all lists are pre-sorted.

## Drift section

The `## Drift warnings` section surfaces three classes of operational drift:

| Class | Meaning | Action |
|---|---|---|
| Missing YAML frontmatter | Agent .md without parseable frontmatter | Add `---\nname: ...\n---` header |
| Orphaned plists | Launchd label whose workload script is not on disk | Either disable plist or restore script |
| Stale agents (>90d mtime) | Agent .md unmodified for >90 days | Review whether still in use |

`_No drift detected._` means all three classes are empty.

## Refs

- Spec: `docs/superpowers/specs/2026-05-14-agent-library-inventory-design.md`
- Plan: `docs/superpowers/plans/2026-05-15-agent-library-inventory.md`
