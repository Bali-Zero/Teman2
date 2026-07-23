# `.agents/skills/` — CANONICAL skill store (cross-agent)

This directory is the **single source of truth** for all Tier-A skills (pure
knowledge/procedure, tool-agnostic): the live corners (`bot`, `wr2`,
`kbli-navigator`, `visaoracle`, `subhi`, …) and any skill meant to be shared
across agent CLIs (Claude Code, Kimi Code, Codex CLI, Gemini/agy, …).

## Rules

1. **Edit skills HERE, never in a tool-specific copy.** Tool directories
   (`.claude/skills/`, `~/.claude/skills/`, `~/.agents/skills/`) contain
   *symlinks* to this store, not copies. If you find a real file where a
   symlink should be, it is drift — fix it before editing.
2. **Keep bodies tool-agnostic.** No references to a specific CLI's mechanics:
   no `/slash-commands`, no "use the Workflow tool", no tool names in
   instructions. Tool-specific glue (hooks, slash commands, subagent
   definitions, orchestration playbooks like `workflow`) stays in the owning
   tool's directory (Tier B) and is NOT shared.
3. **Corners carry LIVE STATE** — update the live-state section in the same
   commit as the work it describes. One copy = one truth; a stale corner is
   worse than no corner.
4. New shared skill → create it here, then symlink it into the tool dirs that
   need it. New tool-specific skill → create it in that tool's dir, not here.

## Layout

- `.agents/skills/<name>/SKILL.md` — canonical content (this store)
- `.claude/skills/<name>` → symlink to `../../.agents/skills/<name>` (Claude Code)
- `~/.agents/skills/<name>` — user-level canonical store (same rules)
- `~/.claude/skills/<name>` → symlink to `~/.agents/skills/<name>`

Established 2026-07-23 (skill-unification lane). Backup of the pre-unification
copies: `~/backups/skill-unification-2026-07-23/`.
