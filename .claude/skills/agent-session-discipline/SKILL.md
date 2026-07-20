---
name: agent-session-discipline
description: Use at session start when working on a feature/fix that involves code changes. Creates an isolated worktree via L1 broker (scripts/agent_start.py) to prevent sibling-orphan stash and cross-agent collisions. Prerequisite for any commit/push workflow.
---

> **CANON**: repo `.claude/` (vendored 2026-07-17, PR process-toolkit SSOT) — shadows the `~/.claude/` HOME copy. Edit HERE, never in `$HOME`. Pro/Mini shadow it on `git pull`.

# Agent Session Discipline (L5.1)

## When to invoke

- User asks "implement X" / "fix Y" / "add feature Z"
- About to write code that will be committed
- After session start in main checkout (`cwd = ~/nuzantara`)
- When SessionStart hook surfaces "Strongly recommended before any git mutation OR file write"
- After observing high alive-AI-process count + sibling-orphan stash count

## What to do

### Step 1 — Pick a lane

From L1 allowlist (defined in `scripts/agent_start.py` KNOWN_LANES):

`wr2 wr3 infra docs db cicatrix-fix mouth intel cell organism mata-garuda backend-rag frontend ops`

If your task doesn't fit, use `ops` as fallback or `--allow-unknown-lane` flag.

### Step 2 — Generate task-id

Short kebab-case, ~3 words max. Examples:

- `kg-bridge-s16`
- `drive-metadata`
- `workflow-l5-1`
- `wa-copilot-fix-x`

Pattern: `^[a-z0-9][a-z0-9\-]{0,63}$` (lowercase, digits, dash).

### Step 3 — Create worktree

```bash
python scripts/agent_start.py --lane <lane> --task-id <task-id> --ttl-min 120
```

Output: `WORKTREE_READY ~/nuzantara/.worktrees/<lane>-<task-id>`

Effects:

- Branch `agent/<host>/<lane>/<task-id>` created from `--base-branch` (default `main`)
- Worktree mounted at the path
- Symlinks: `apps/backend-rag/.venv`, `apps/backend-rag/.env`, `node_modules/` (env-safe)
- `.agent-task.json` metadata file (task_id, lane, branch, host, created_at, ttl_minutes, pid)

### Step 4 — Use the worktree path

Bash tool resets cwd between calls. To work in worktree:

- **git commands**: use `git -C /path/to/worktree ...`
- **file paths**: use absolute paths starting with `~/nuzantara/.worktrees/<lane>-<task-id>/`
- **Don't** try to `cd` and persist — won't work

Verify periodically:

```bash
git -C ~/nuzantara/.worktrees/<lane>-<task-id> status --short
```

### Step 5 — Implementation workflow

In the worktree:

1. Read existing code, memory (`mem recent`), cicatrix (`grep` `.claude/rules/cicatrix-scars.md`)
2. Plan changes (use Plan tool if architectural, dispatch 4-LLM panel if cross-cutting)
3. Write/Edit files (all absolute paths starting with worktree path)
4. Test (pytest scope-relative)
5. Commit (`git -C <worktree> commit -m "feat(scope): subject"` with `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`)
6. Push (`git -C <worktree> push -u origin <branch>`)

### Step 6 — Session end

When task complete:

```bash
# Open PR
gh pr create --draft --base main --head agent/<host>/<lane>/<task-id> --title "..." --body "..."

# Release worktree (after merge)
python scripts/agent_start.py --release <task-id>
```

If WIP not yet committed:

```bash
git -C /path/to/worktree stash push -u -m "session-end-<task-id>-wip"
# (worktree stays alive until --release or --cleanup TTL expiry)
```

## Common pitfalls

| Pitfall                                         | Avoidance                                                                                               |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Forgetting to use `git -C`                      | Always prefix every git command with `-C /path/to/worktree`                                             |
| Writing to main checkout accidentally           | Use absolute paths starting with worktree path; PreToolUse hook will block otherwise                    |
| `cd /worktree && git ...` doesn't persist       | Bash tool resets cwd; use `git -C` instead                                                              |
| Husky pre-commit fails for missing node_modules | Symlink from main: `ln -sfn ~/nuzantara/node_modules ~/nuzantara/.worktrees/<wt>/node_modules`          |
| Husky pre-commit fails for typecheck            | Same: `ln -sfn ~/nuzantara/apps/mouth/node_modules ~/nuzantara/.worktrees/<wt>/apps/mouth/node_modules` |
| Prettier auto-formats .md commits               | Run `npx prettier --write <file>` BEFORE `git add` to avoid retry                                       |

## Emergency escape

When hooks block legitimate work:

```bash
export AGENT_WORKTREE_ENFORCEMENT=false  # disable for whole session
```

Use sparingly. The escape is logged in `/tmp/nuz_l5_1_blocks`.

## Reference

- L1 broker spec: `docs/runbooks/agent-worktree-broker.md`
- L2 lease spec: `docs/runbooks/redis-lease-registry.md`
- L5.1 spec: `research/operations/specs/L5.1-agent-worktree-enforcement-2026-05-25.md`
- Panel synthesis: `research/operations/specs/L5.1-panel-synthesis-2026-05-25.md`
- Hook code: `~/.claude/hooks/worktree_isolation.py` + `worktree_file_write_check.py`
- Cicatrix family: 2026-04-29 #1+#2, W50/W51/W52, sibling-orphan-2026-05-25-\*
