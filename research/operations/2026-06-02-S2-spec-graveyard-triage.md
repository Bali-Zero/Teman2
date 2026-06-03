---
date: 2026-06-02
domain: operations
title: S2 — Spec graveyard triage (11 pending specs)
client_case: none
sources:
  - research/operations/specs/*.md (11 named pending specs)
  - research/operations/2026-05-31-structural-debt-FROZEN.json (W38 rolsuper re-verification)
  - ~/.claude/settings.json (hooks, env, enabledPlugins — live ground-state)
  - .mcp.json (MCP server inventory)
  - .github/workflows/hot-zone-pr-gate.yml (L5.2 monitor-mode)
  - GitHub Dependabot alerts API (W39 CVE state)
machine: Air-M5 (balizero) thin-client
---

# S2 — Spec graveyard triage

**Orchestrator session** `agent/air-m5/docs/s2-spec-graveyard`, 2026-06-02.
Workflow fan-out: 11 assailant agents (1 per spec) verified spec-claim vs shipped-disk-reality.
Orchestrator independently spot-checked the load-bearing DEAD/NEEDS-ANTONELLO claims.

## Headline

**0 EXECUTE-NOW.** Every pending spec resolves to archive, owner-sign-off, or re-design.
No autonomous code execution is warranted by this triage.

| # | Spec | Verdict | One-line |
|---|---|---|---|
| 1 | W38 backend_rag_v2 nosuperuser | **NEEDS-ANTONELLO** | Bomb #1 by blast radius, STILL live; prod security write |
| 2 | W39 dependabot-cve-triage | **DEAD** | All 8 alerts resolved on GitHub prod; npm overrides shipped |
| 3 | T3.5 session-start-consolidation | **RE-SPEC** | Merge plan stale vs 14-entry M5 layout; HIGH risk if blind |
| 4 | T3.6 tool-search auto:10 | **RE-SPEC** | A/B methodology stale; blind env flip violates spec's own gate |
| 5 | L5.1 worktree-enforcement | **DEAD** | Hooks live + registered; superseded by iter2 + L5.2 |
| 6 | L5.1-iter2 worktree-enforcement | **DEAD** | Enforce-mode hooks shipped; W62 cleanup closed by PR #925 |
| 7 | L5.2 server-side-enforcement | **NEEDS-ANTONELLO** | Workflow in monitor-mode; flip-to-enforce = prod branch-protection write |
| 8 | T2.4 vercel-mcp | **DEAD** | Functional intent shipped via claude.ai marketplace Vercel MCP |
| 9 | R1 claude-mem-3layer | **DEAD** | claude-mem disabled; semantic gap closed via MOS+Qdrant |
| 10 | R2 exa-mcp-oauth | **NEEDS-ANTONELLO** | Interactive OAuth + paid-API policy check |
| 11 | R4 experimental-agent-teams | **DEAD** | Flag live, pilot done, adoption is current operating mode |

**Tally:** 6 DEAD · 3 NEEDS-ANTONELLO · 2 RE-SPEC · 0 EXECUTE-NOW.

## W38 re-verification (mission-mandated)

The mission required confirming `backend_rag_v2 rolsuper=t` is STILL true. The live
postgres-nuzantara MCP was **unreachable from this M5 thin-client** (error `-32603` on a
trivial `SELECT current_user`; M5 has no local PG and the Fly read-only role is not reachable —
consistent with the SessionStart warning `compliance-ops: CRM backend unreachable`).

Authoritative fallback: the **2026-05-31 S4 audit** (`research/operations/2026-05-31-structural-debt-FROZEN.json`,
commit `4729bbb9b`) verified `backend_rag_v2 rolsuper=true` **twice** via the postgres-nuzantara
MCP read-only, just two days ago. The demotion was never applied (no `NOSUPERUSER` in
`migrations_v2/`), and the Stage B `ADMIN_DATABASE_URL` code split is absent from the entire
backend. **The bomb is LIVE.** Verdict: **NEEDS-ANTONELLO, DO-NOT-EXECUTE** (per hard rule).
The W38 spec has been annotated with this 2026-06-02 re-verification note.

## NEEDS-ANTONELLO — owner sign-off required

- **W38** — `ALTER ROLE backend_rag_v2 NOSUPERUSER` is an irreversible-class prod security write
  touching every backend service via `DATABASE_URL`. Stage B (`ADMIN_DATABASE_URL` split) not yet
  coded. Ranked #1 armed bomb by blast radius (DB-host RCE / `DROP DATABASE` if app secret leaks).
- **L5.2** — `hot-zone-pr-gate.yml` is live but in monitor-mode (6× `continue-on-error: true`, not
  in `required_status_checks`), so the HUSKY=0/`--no-verify`/direct-push bypass it set out to close
  is NOT blocked server-side. Flipping to enforce + Phase 1 bot privilege downgrade + Phase 3
  branch-protection writes are all prod GitHub API writes governed by the spec's own empirical gates
  (<5% false-positive, 48h observation).
- **R2** — Exa MCP needs (1) an interactive browser OAuth grant an autonomous agent cannot click
  through, and (2) a paid-API HARD-RULE clearance — Exa is not in the sanctioned subscription
  arsenal, and an on-disk `EXA_API_KEY=9e54...` (in `settings.local.json`, serving a now-deleted
  `agents/01_grok_scraper.py`) is exactly a per-token paid key. **Side cleanup (any outcome):** scrub
  the stale `mcp__exa__*` allowlist entries and the leaked `EXA_API_KEY` from `settings.local.json`.

## RE-SPEC — obsolete plan, needs fresh design

- **T3.5** — The 13→6 SessionStart consolidation plan was designed against a content-category layout.
  The live layout is **14 entries** (one MORE than baseline), dominated by operational maintenance
  script-calls (`log-rotate`, `memory-leak-check`, `mcp-cleanup`, `nuz-sync-check`, repomap-inject,
  `agent_workspace_setup`) that the 6-block taxonomy never addresses. Editing this file breaks every
  session bootstrap; executing the stale plan would silently drop load-bearing hooks. **HIGH risk.**
- **T3.6** — The `auto:5 → auto:10` A/B targets `~/.zshenv`, but the var has since moved to
  `~/.claude/settings.json`. The spec's decision gate requires a ≥10% subagent-dispatch delta from a
  3-session measurement it itself names as Antonello-driven-over-time, and explicitly flags
  "altering the threshold without an A/B baseline" as the anti-pattern. A blind flip violates the
  spec's own contract.

## DEAD — archive (work shipped or problem gone)

All six independently spot-checked by the orchestrator (not just subagent grep):

- **W39** — 8/8 Dependabot alerts resolved on GitHub prod (3 npm `fixed` 2026-05-22, 5 pip
  `dismissed`); 3 npm overrides present in `package.json` + resolved in lock; WONT-FIX
  justifications re-verified (0 direct `transformers`/`ecdsa` imports, JWT=HS256).
- **L5.1 / L5.1-iter2** — `worktree_isolation.py` + `worktree_file_write_check.py` live + registered;
  `scripts/worktree_gc_universal.py` (PR #925) closed the W62/W63 broker-cleanup gap. Residuals are
  cosmetic/redundant.
- **T2.4** — `mcp__claude_ai_Vercel__*` verified live 2026-05-22 (list_teams=nuzantara-2026, 7
  projects); Step-6 memory updated; the project-local `mcp__vercel__*` it proposed is redundant, and
  git-push auto-deploy further lowers MCP value.
- **R1** — `claude-mem@thedotmack=false` (disabled), zero hook integration; the semantic-L3 gap was
  closed by `qdrant@qdrant=true` (MOS+Qdrant) + MOS+ auto-capture. Evaluated and rejected.
- **R4** — `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` live; successful pilot captured
  (`project_pilot_cross_llm_agent_teams_2026_05_13.md`); this very triage runs under the team harness.

## Method note

- Fan-out: `Workflow` 11 assailant agents (general-purpose), schema-forced structured verdicts.
- Adversarial Codex phase (risk-check on EXECUTE-NOW) was **correctly skipped**: 0 EXECUTE-NOW
  candidates emerged, so there was nothing to attack.
- Anti-hallucination: orchestrator re-verified L5.1/L5.1-iter2/R1/R4 plugin+hook state and L5.2
  monitor-mode count THIS session, not trusting subagent grep alone for the archival decision.
- Full per-spec evidence: `research/operations/S2-spec-graveyard-FROZEN.json`.

## Not triaged (out of scope)

The `specs/` directory holds ~46 files. This triage covered only the 11 genuinely-pending specs the
S2 mission named. Deliberately excluded: orchestration-machinery for the already-executed 2026-05-21
wave (`G0`–`G4` gates, `T-1`/`T-2` backup, `WAVE-MINUS-1`, `_panel-*.json`); shipped `T1.x`/`T2.x`/
`T3.2`/`T3.3`/`T3.4` hooks/skills/MCP (confirmed live this session); and separate product specs
(WA-team-inbox, chat-data-intelligence, wr2-canva-actuator). `R3` is already marked KILLED.
