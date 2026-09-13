# Agent worktree discipline — full detail (L5.1, 2026-05-25)

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.
> `AGENTS.md` §0.5 keeps the mandatory rule, the broker command and the kill switch.

**MANDATORY for any Codex session that mutates code in this repo.**

This repo is shared with 5+ Claude sessions + occasional Gemini agy on the same Pro machine. All processes default to `cwd=/Users/nuzantara/nuzantara` (main checkout). Concurrent file mutations have produced 32+ sibling-orphan stash in 24h. To prevent:

### Before any mutation

```bash
# Create dedicated worktree
python scripts/agent_start.py --lane <wr2|infra|backend-rag|ops|...> --task-id <slug>
# Output: WORKTREE_READY /Users/nuzantara/nuzantara/.worktrees/<lane>-<task-id>
cd <output-path>
# Now spawn codex exec HERE, not in main checkout
```

### For codex exec invocations

`codex exec` inherits cwd from spawner. Wrong pattern:

```bash
# Wrong (creates orphan in main):
codex exec --sandbox workspace-write "fix bug X"
```

Right pattern:

```bash
WT=$(python scripts/agent_start.py --lane infra --task-id codex-bug-x | tail -1)
cd "$WT" && codex exec --sandbox workspace-write "fix bug X"
```

### Hooks active

PreToolUse hook `~/.claude/hooks/worktree_isolation.py` blocks Claude Code Bash git ops in main checkout. `~/.claude/hooks/worktree_file_write_check.py` blocks Claude Code Edit|Write|MultiEdit in main. These hooks are CLAUDE-SIDE only — Codex CLI runs in its own sandbox and is NOT subject to them. **Discipline relies on Codex authors following this convention manually.**

### Kill switch

```bash
export AGENT_WORKTREE_ENFORCEMENT=false
```

Use only for emergency / hotfix / cicatrix-fix.

### Reference

- L1 broker: `docs/runbooks/agent-worktree-broker.md`
- L2 lease: `docs/runbooks/redis-lease-registry.md`
- L5.1 spec: `research/operations/specs/L5.1-agent-worktree-enforcement-2026-05-25.md`
- Panel synthesis: `research/operations/specs/L5.1-panel-synthesis-2026-05-25.md`

---
