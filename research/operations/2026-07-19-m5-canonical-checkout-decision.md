---
date: 2026-07-19
domain: operations
adversarial_review: exempt-decision-memo
---

# Decision memo: canonical checkout for `.mcp.json` on Air-M5

> Author: Kimi (Air-M5) · Status: **AWAITING OPERATOR DECISION** (Legge 5 — this changes where every local agent's MCP servers run from)

## Problem (verified 2026-07-18/19)

Air-M5 has TWO live checkouts of the repo:

1. `/Users/balizero/nuzantara` — where Kimi/CLI sessions actually run (cwd of this session's worktrees, agent_start.py, git ops)
2. `/Users/balizero/Desktop/nuzantara` — where `.mcp.json` (both copies) points the MCP servers: `cwd`, `PYTHONPATH`, and per-app `.venv/bin/python` paths all reference `Desktop/nuzantara`

Consequences of the split:

- Code merged in one checkout does NOT affect the MCP servers until the other checkout is pulled (the servers import from `Desktop/nuzantara/apps/*`)
- `agent_start.py` worktrees live under the session checkout; the MCP servers read another tree entirely
- commit `b005f85998` (2026-07-16, "repoint the repo off ~/Desktop/nuzantara") suggests an earlier migration intent that never completed
- Every fleet doc (AGENTS.md R-tables) describes ONE canonical checkout per machine, M5's is ambiguous

Currently both checkouts sit at the same commit — the divergence is latent, not active. That is precisely when to fix it.

## Options

### A — Canonical: `/Users/balizero/nuzantara` (recommended)

Point everything (`.mcp.json` cwd/PYTHONPATH/venv paths, docs, habits) at the session checkout. Retire the Desktop one (archive it: `mv ~/Desktop/nuzantara ~/Desktop/nuzantara.ARCHIVED-2026-07-19` after a clean-diff check).

- Pros: single tree for sessions AND servers; matches how the other machines are documented (Pro: `~/nuzantara` + `~/nuzantara-deploy`); the Desktop copy becomes a museum, not a shadow
- Cons: any OTHER agent/session habitually cd-ing into Desktop/nuzantara must be told once; if a Desktop-side uncommitted WIP exists it must be diffed first (check `git status` there — currently clean per 2026-07-18 audit)

### B — Canonical: `~/Desktop/nuzantara`

Repoint sessions to the Desktop checkout instead.

- Pros: zero `.mcp.json` edits
- Cons: sessions+worktrees move; every doc that says "the repo" becomes ambiguous; Kimi's existing worktrees/leased state live under the other tree (86 worktrees, `agent_start.py` broker state) — materially worse

### C — Symlink one onto the other

- Cons: hides the problem under a filesystem trick; breaks the `git status` honesty of both; the fleet's home-fork lint would (correctly) flag it. Do not.

## Recommended execution (if A is chosen)

1. `git -C ~/Desktop/nuzantara status -s` → must be clean; `git log --oneline -1` must equal the session checkout's HEAD
2. Edit `.mcp.json` (M5 copy): replace all `/Users/balizero/Desktop/nuzantara` → `/Users/balizero/nuzantara` (cwd, PYTHONPATH, venv interpreters)
3. Verify per-app venvs exist at the new paths (`apps/nuzantara-mcp/.venv`, `-advanced/.venv`, `-browser/.venv`) — if absent, `python3 -m venv` + `pip install -e .` for the three servers (they're small)
4. Respawn one MCP session and prove an authed call (200 on `/api/crm/expiry-alerts` via the file-fallback key)
5. `mv ~/Desktop/nuzantara ~/Desktop/nuzantara.ARCHIVED-2026-07-19` (reversible, not deleted)
6. One line in AGENTS.md §0.1: the canonical M5 checkout is `/Users/balizero/nuzantara`

## Out of scope

Pro's layout (`~/nuzantara` + `~/nuzantara-deploy` dual-checkout for WR2, scar #1) is a deliberate, documented design — untouched.
