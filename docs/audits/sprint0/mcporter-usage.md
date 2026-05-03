# mcporter usage audit + idle disable plan — Sprint 0 Track A3

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session (Claude Opus 4.7 1M)
**Reference:** brainstorm 2026-05-02 round 2 § "mcporter idle 200MB RAM"

## TL;DR

- mcporter is `0.7.3`, installed at `/Users/nuzantara/.npm-global/bin/mcporter`,
  configured in OpenClaw `tools.alsoAllow` and `tools.exec.safeBins`.
- mcporter exposes **13 servers** (per-server check at audit time):

  | server | tools | status |
  |---|---|---|
  | `nuzantara-mcp` | **124** | healthy |
  | `playwright` | 23 | healthy |
  | `filesystem` | 14 | healthy |
  | `nuzantara-mcp-advanced` | 13 | healthy |
  | `memory` | 9 | healthy |
  | `docker` | 8 | healthy |
  | `exa` | 8 | healthy |
  | `perplexity` | 4 | healthy (7.5s) |
  | `brave-search` | 2 | healthy |
  | `context7` | 2 | healthy |
  | `sequential-thinking` | 1 | healthy |
  | `vercel` | n/a | auth required |
  | `fetch` | n/a | offline |
  | **TOTAL distinct tools** | **208** | (briefing said 129; the gap is 4 servers added since round 1 — playwright, filesystem, memory, docker) |

- **Empirical 30-day usage** from `~/.openclaw/logs/gateway.log`: 952 lines
  matching `mcporter`, but only **13 distinct `mcporter call <server>.<tool>`
  calls** have ever fired:

  ```
   6  mcporter call nuzantara-mcp-advanced.check_fly_status
   5  mcporter call nuzantara-mcp.get_compliance_alerts
   4  mcporter call nuzantara-mcp.get_expiry_alerts
   3  mcporter call nuzantara-mcp.list_practices
   3  mcporter call nuzantara-mcp-advanced.check_system_health
   2  mcporter call nuzantara-mcp.read_shared_memory
   2  mcporter call nuzantara-mcp.check_health_detailed
   2  mcporter call nuzantara-mcp-advanced.get_fly_logs
   1  mcporter call nuzantara-mcp.list_clients
   1  mcporter call nuzantara-mcp.get_team_hours
   1  mcporter call nuzantara-mcp.get_client_stats
   1  mcporter call nuzantara-mcp.get_agents_status
   1  mcporter call nuzantara-mcp.chain_daily_ops_autopilot
  ```

  → **195 tools (94%) have NEVER been invoked**. Many of those were also
  blocked by exec-approval gating, so the real "intentional usage" is even
  lower than 13 distinct.

## RAM impact

mcporter loads each MCP server on the gateway side via stdio child processes
when the agent requests an introspection (`mcporter list`) or call. The
brainstorm estimate of "150–200MB saving" relies on Python/Node child
processes lingering. Empirical saving will need to be measured **after**
disabling idle servers (see "Verification" below). It's plausible: each
Python MCP server (nuzantara-mcp 124-tool tree) consumes 50–80MB resident
on Pro at warm-up.

## Recommended action: disable idle servers, NOT idle tools

mcporter doesn't expose a per-tool toggle — only a per-server one (an entry
in the user's `mcp.json` config). The `nuzantara-mcp` server has 124 tools
of which 13 have been used. Cannot prune those 13 from a 124-server-tools
manifest without forking the server.

So the practical knob is at the **server** layer:

| server | recommendation | reason |
|---|---|---|
| `nuzantara-mcp` | **keep** | 11/13 mcporter calls resolve here; core CRM/Intel/Content tooling |
| `nuzantara-mcp-advanced` | **keep** | 4/13 mcporter calls resolve here; Fly ops / system health |
| `filesystem` | **keep on demand** | not in the 13 calls but trivial cost (Node fs) and useful for ad-hoc Lobster runs |
| `memory` | **keep on demand** | mem MOS bridge, low cost |
| `docker` | **disable** | Nuzantara doesn't run Docker Desktop on Pro for prod; Docker Compose flows don't go through OpenClaw |
| `playwright` | **disable** | browser MCP runs from `mcp__claude-in-chrome__*` (CC) or `apps/nuzantara-mcp-browser/` (FastMCP) — duplicate |
| `perplexity` | **disable on Pro** | 7.5s startup latency, never invoked from OpenClaw |
| `brave-search` | **disable on Pro** | redundant with Gemini search via `ai-dispatch` |
| `context7` | **disable on Pro** | only useful from interactive Claude Code sessions, not OpenClaw automations |
| `sequential-thinking` | **disable on Pro** | conversational tool, useless for cron-style |
| `exa` | **disable** | duplicate of brave/perplexity tier |
| `vercel` | **leave broken** | auth not configured; remove from mcp.json |
| `fetch` | **fix or remove** | offline; if intended to stay, fix the binary path; otherwise remove |

Net: **8 of 13 servers disabled**, retaining `nuzantara-mcp`,
`nuzantara-mcp-advanced`, `filesystem`, `memory` and keeping the actually-used
13-tool subset live. Estimated RAM saving 100–250MB on Pro.

## Application steps (manual on Pro post-merge)

mcporter reads its server registry from `~/.config/mcporter/mcp.json`
(NOT from OpenClaw config). The dry-run script
`scripts/openclaw-mcporter-toggle.sh` prints what each toggle would change.

```bash
# Read current (no edits):
ssh pro 'bash ~/Desktop/nuzantara/scripts/openclaw-mcporter-toggle.sh --list'

# Plan:
ssh pro 'bash ~/Desktop/nuzantara/scripts/openclaw-mcporter-toggle.sh --disable-idle --dry-run'

# Apply (after manual review):
ssh pro 'bash ~/Desktop/nuzantara/scripts/openclaw-mcporter-toggle.sh --disable-idle --apply'
# Then restart OpenClaw to re-snapshot:
ssh pro 'launchctl kickstart -k gui/501/ai.openclaw.gateway'
```

The `--disable-idle` flag operates strictly off the empirical
`mcporter call` log (i.e. servers with 0 invocations in the last 30 days
from `gateway.log`). It is intentionally NOT hard-coded so future audits
adapt to actual usage patterns.

## Verification (for the post-application step)

After disable, run:

```bash
ssh pro 'mcporter list 2>&1 | head -20'
ssh pro 'ps -axo pid,rss,command | grep -iE "(mcp|mcporter)" | grep -v grep'
ssh pro 'sleep 60 && grep "mcporter" ~/.openclaw/logs/gateway.log | tail -5'
```

Expected: server count drops from 13 to ~5; child-process count drops; no
gateway errors complaining about missing servers (logs should be silent
unless an agent specifically asked for a disabled server, in which case
`mcporter` returns a clean "server not configured" error).

## Out-of-scope today

- Per-tool gating *inside* `nuzantara-mcp` 124-tool manifest. Would need
  refactor `apps/nuzantara-mcp` to expose a per-tool registration toggle.
  Tracked as Sprint 1 follow-up if the Telegram menu still leaks too many
  commands after Sprint 0 is applied.
- mcporter v0.8 upgrade. Noted in OpenClaw upgrade plan (Track A4) — handled
  there, not here.

## References

- `~/.config/mcporter/mcp.json` (server registry)
- `~/.openclaw/logs/gateway.log` (mcporter invocation history; grep `mcporter call`)
- `scripts/openclaw-mcporter-toggle.sh` (dry-run/apply helper)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/06_openclaw_ecosystem_audit.md` § 14 "missed integrations"
