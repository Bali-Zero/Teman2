# v2 Subdomain Rollout — Master Plan

> **Spec source:** `docs/superpowers/specs/2026-04-17-v2-subdomain-rollout-design.md`
> **Status:** master index of 4 sub-plans (each is independently shippable)
> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans.

**Goal:** Portare v2 design + funnel SOTA + matter-first portal + inbox-first workspace sui 11 target subdomain/route di balizero.com in 5 sprint.

**Architecture:** 3-layer con persona-theme distinte. `packages/core` è il cuore: NavShell/ThemeProvider sono già architetturalmente SOTA (verificato 2026-04-17), basta aggiungere componenti di dominio e adottarli. Cross-funnel session via nuovo cookie `bz_session` e table `funnel_sessions` generalizzata da `visa_oracle_sessions`.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind, FastAPI, PostgreSQL (Alembic), Qdrant, Vercel, Fly.io. `@balizero/core` workspace package.

---

## Sub-plans

Execute in order. Each blocks the next.

| #   | Sub-plan                | File                                     | Duration | Output                                                                                   |
| --- | ----------------------- | ---------------------------------------- | -------- | ---------------------------------------------------------------------------------------- |
| 1   | **Foundation** (S1)     | `2026-04-17-v2-rollout-01-foundation.md` | 3gg      | 8 componenti `@balizero/core`, 2 migration Alembic, session-bridge, ical/wa utils        |
| 2   | **L1 Funnel Hub** (S2)  | `2026-04-17-v2-rollout-02-funnel-hub.md` | 5gg      | visa port + kbli port + **tax.** nuovo + property nuovo + homepage link fix              |
| 3   | **L2 Client App** (S3)  | `2026-04-17-v2-rollout-03-client-app.md` | 4gg      | 3 hero cards, MatterCard, WA push, family, bundle audit                                  |
| 4   | **L3 Team Ops** (S4+S5) | `2026-04-17-v2-rollout-04-team-ops.md`   | 7gg      | inbox-first, Cmd+K, ContextPanel, Prime toggle, cleanup satellite, analytics funnel-view |

---

## Execution order & worktree strategy

- **Sub-plan 1 (foundation):** worktree isolato `.worktrees/v2-foundation` — non tocca nessun subdomain in prod, solo `packages/core` + migrations + tests.
- **Sub-plans 2/3/4:** ogni sub-plan in worktree suo — `v2-funnel-hub`, `v2-client-app`, `v2-team-ops`. Merge a main solo dopo review + QA browser.
- **Rollback:** ogni sub-plan è indipendente. Se sub-plan 2 va male, L1 resta v1 e L2/L3 non sono toccati.

## Review checkpoints

Dopo ogni sub-plan:

1. `PYTHONPATH=. pytest backend/tests/` — tests green
2. `npm run typecheck -w apps/mouth` — 0 errori
3. Browser QA `mcp__claude-in-chrome__*` (3 persona-theme screenshots)
4. Lighthouse 95+ L1, 85+ L2/L3
5. Federation review: `./scripts/ai-dispatch.sh codex-review` sul diff

## Off-limits (respect in every sub-plan)

- `zantara_core.py` (prompt SSOT)
- `fly.toml` · `.env*` · `alembic/env.py`
- `backend/app/dependencies.py` senza `codex sandbox` pre-check

## Start

```bash
# worktree per foundation sub-plan
cd ~/Desktop/nuzantara
git worktree add .worktrees/v2-foundation -b v2-foundation main
cd .worktrees/v2-foundation
# open docs/superpowers/plans/2026-04-17-v2-rollout-01-foundation.md
```
