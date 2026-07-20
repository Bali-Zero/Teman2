# `.claude/agents/` — project-level lane aggregators

This directory holds **project-level, git-tracked** subagent definitions. They ship with the
repo and reach every checkout (Pro, Mini-Pro2, Air-M5, CI, any future clone) on the next
`git pull` — no per-machine copy-and-drift.

## Why this exists (cicatrix family #1 — HOME-fork drift)

The 4 lane aggregators below (`backend-verifier`, `frontend-browser`, `mcp-health`,
`spalla-review`) originated as `~/.claude/agents/*.md` — user-global, machine-local files (see
`research/operations/specs/T3.3-6-named-subagent-lanes.md`). That is exactly the shape of the
**HOME-fork** cicatrix family: a copy in `$HOME` that silently diverges from the repo's
source of truth, per-machine, with no sync mechanism. This directory is the antidote: the repo
is the SSOT, and `git pull` is the sync mechanism.

## Precedence (official, per current subagent docs)

When a subagent name resolves, Claude Code applies this precedence, highest first:

1. Managed (org-provisioned)
2. `--agents` CLI flag (session override)
3. `.claude/agents/` — **this directory** (project-level, git-tracked)
4. `~/.claude/agents/` (user-level, machine-local)
5. Plugin-provided agents

**A project-level file here wins over a same-named file under `~/.claude/agents/` on any
machine.** That is the point: once these 4 files exist here, they are the definitions that
fire everywhere, regardless of what a given machine's HOME copy still says.

## On-machine dedup required (PENDING-ARMS)

Because precedence only *shadows* the HOME copies rather than deleting them, any machine that
still has `~/.claude/agents/{backend-verifier,frontend-browser,mcp-health,spalla-review}.md`
on disk is carrying dead weight that can drift unnoticed and confuse a future audit ("which
copy is actually running?" — cicatrix family #2, "esiste ≠ armato"). Removing those files is an
**on-machine action** (Pro / Mini-Pro2 / Air-M5), not something this PR can do from a repo
checkout — it is tracked as a PENDING-ARMS ledger entry (`.claude/skills/modus/PENDING-ARMS.md`)
until an operator/session on each machine confirms the HOME copies are gone and the repo copies
are what's live.

## Convention

**New project-level agents are born here, never in `~/.claude/agents/`.** A new lane aggregator
or workflow agent that should be available on every checkout gets its `.md` file added to this
directory in the same PR that introduces it. `~/.claude/agents/` stays reserved for genuinely
machine-local experiments that are not (yet) meant to fleet-sync.

## The 4 lane aggregators

| Lane            | Agent               | When to dispatch                                                          |
| --------------- | ------------------- | -------------------------------------------------------------------------- |
| Backend verify  | `backend-verifier`  | Health check, pytest, Fly deploy audit — read-only                        |
| Frontend QA     | `frontend-browser`  | Post-deploy screenshot, brand/console check — read-only                   |
| MCP health      | `mcp-health`        | Verify configured MCP servers reachable end-to-end, not just listed        |
| Code review     | `spalla-review`     | PR review, constructive (vs `devils-advocate`, adversarial)                |

All four: `tools` whitelist + explicit `disallowedTools: Edit, Write, MultiEdit, NotebookEdit`
(declaration is not enforcement — the antibody from the T3.3 scar is to pair the whitelist with
an explicit denylist), `model: sonnet`, `maxTurns: 40` as a defensive cap, and `memory: project`.
None of them may run `git add`/`commit`/`push`/`checkout`/`stash` — verification lanes observe,
they do not mutate.

## `memory: project` and `.claude/agent-memory/<name>/`

Each of these agents uses `memory: project`, which the harness persists to
`.claude/agent-memory/<name>/` — **git-tracked**, so cross-session learnings for a lane travel
with the repo instead of living (and dying) on one machine's disk. If a given agent's memory
file grows large, curate it the same way `MEMORY.md` is curated elsewhere in this project: only
the first ~200 lines / ~25KB get injected at session start, so keep the load-bearing facts near
the top and prune what's stale.
