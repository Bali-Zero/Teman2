# Claude skills snapshot

Authoritative copies of operator-written skills that live at
`~/.claude/skills/<name>.md` on Pro. Tracked here so changes go through
PR review and historical drift is visible.

## Why

Skills are loaded from `~/.claude/skills/` on the operator's machine.
That dir is NOT under git by default, so:

- A change there has no audit trail (who changed it, when, why).
- A change made on Pro is invisible to Mini until manually copied.
- A skill modification can subtly break a production cron run with no
  rollback path.

This dir is the single source of truth. The local skill MUST match the
git copy. CI workflow `.github/workflows/claude-skills-drift.yml` (TODO,
follow-up PR) compares them and fails if they diverge.

## Workflow

When iterating a skill locally:

1. Edit `~/.claude/skills/<name>.md` as usual.
2. Test in Claude Desktop.
3. Once stable, copy back: `cp ~/.claude/skills/<name>.md
   infra/claude-skills/<name>.md`.
4. Commit + PR.

When pulling in a teammate's PR that touched a skill:

1. `git pull` the PR.
2. `cp infra/claude-skills/<name>.md ~/.claude/skills/<name>.md` to apply
   the new version locally.

## Current snapshots

- `canva-apply.md` — applies the WR2 carousel pending JSON to the Canva
  master template, duplicates into the Carousel folder, persists the
  result. Updated 2026-05-10 to add Phase -1 (pre-validate) and
  `WR2_OUTPUT_ROOT` env var support.
