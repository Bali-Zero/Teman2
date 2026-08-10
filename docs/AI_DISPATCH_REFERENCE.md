# AI Dispatch System — Full Reference

> Extracted from CLAUDE.md (pre-T2.7 §16) on 2026-03-31 to reduce context window load.
> Quick reference remains in CLAUDE.md §5 (Agent/LLM Routing & Bans) post-T2.7 refactor 2026-05-23. This file has full details.
> Operational status refreshed 2026-08-11. When the dispatcher does not pin or
> verify a model, this reference names the selecting config rather than claiming
> a model that may differ by host or account.

## 3-Tier Taxonomy (v3.1, 2026-03-25)

### AGENTS — Autonomous runtimes, dispatchable via ai-dispatch.sh

| Agent                                   | Role                                                     | Dispatch Command                           |
| --------------------------------------- | -------------------------------------------------------- | ------------------------------------------ |
| **Claude Code (account/config model)**  | Il Re — orchestrates, synthesizes, decides, executes     | Direct (IS the orchestrator)               |
| **Antigravity Gemini (topology model)** | Il Consigliere — bounded, read-only analysis             | `explore`, `search`, `redteam`, `gemini-*` |
| **Codex CLI (active config/profile)**   | Il Soldato — sandbox kernel-level                        | `sandbox`, `codex-*`                       |
| **Claude CLI (account/config model)**   | Il Giudice — review, redteam, read-only                  | `claude-review`, `claude-redteam`          |
| **Topology reasoner**                   | Required chain in `FLEET_TOPOLOGY.json`; adapter unarmed | Legacy `reasoning` door is retired         |
| **Aider**                               | Installed canary only; provider routes are retired       | `aider-*` fails closed                     |

### SERVICES — Stateless tools, called by orchestrator directly

| Service        | Role                             | Commands                            |
| -------------- | -------------------------------- | ----------------------------------- |
| **NotebookLM** | L'Oracolo — citations grounded   | `oracolo`, `oracolo-nb`, `research` |
| **GWS CLI**    | Il Segretario — Google Workspace | Direct from Claude Code             |
| **OCR**        | Scanner — text extraction        | MCP `mcp__ocr-tesseract__*`         |
| **Websearch**  | Deep web search + content        | `websearch`                         |
| **Canva**      | Design automation                | MCP `mcp__claude_ai_Canva__*`       |
| **GitKraken**  | Git workflow intelligence        | MCP `gk mcp`                        |

### PIPELINES — Scheduled/triggered, NOT dispatchable

| Pipeline              | Schedule/Trigger                 |
| --------------------- | -------------------------------- |
| **Core Guardian V3**  | every 3h (OpenClaw)              |
| **Intel Scraper**     | 03:00 WITA (Pro OpenClaw)        |
| **War Room**          | manual (Claude Code + Canva MCP) |
| **SEO Guardian**      | manual (`audit_geo_aeo()`)       |
| **NLM Daily Refresh** | 04:30 WITA (Pro OpenClaw)        |

## Dispatch Patterns

1. **SERIAL**: Claude→Gemini analyzes→Claude decides→Codex executes→Claude validates
2. **PARALLEL**: `./scripts/ai-dispatch.sh parallel explore:"q1" search:"q2"` → Claude synthesizes
3. **RED TEAM** (mandatory pre-deploy): `redteam "solution"` → If issues: revise. If clean: deploy.
4. **MIGRATION**: `codex-migrate "desc"` → Generates and tests upgrade+downgrade in sandbox
5. **REGULATORY**: `search "KBLI 2025"` → Gemini Google Search grounded with sources
6. **REASONING**: follow `FLEET_TOPOLOGY.json`'s `role_chains.reasoner`.
   The legacy `reasoning` command exits `2` and performs no provider call.
   `verified_generator.py` therefore stops before generation by default; only
   an explicit `--skip-reasoning` accepts running without that layer.

## GitKraken MCP — Usage Rules

| Situation        | GitKraken Tool                     | Instead of                 |
| ---------------- | ---------------------------------- | -------------------------- |
| Committing       | `gitlens_commit_composer`          | `git add` + `git commit`   |
| Outstanding PRs  | `gitlens_launchpad`                | `gh pr list`               |
| Start from issue | `gitlens_start_work`               | `git checkout -b`          |
| Review PR        | `gitlens_start_review`             | Manual checkout            |
| Create PR        | `pull_request_create`              | `gh pr create`             |
| PR details       | `pull_request_get_detail/comments` | `gh pr view`               |
| Assigned issues  | `issues_assigned_to_me`            | `gh issue list --assignee` |
| Blame            | `git_blame`                        | `git blame` bash           |

## Security

- Gemini: `--sandbox --approval-mode plan` → read-only. NEVER writes.
- Codex: `--sandbox read-only` or `workspace-write`. NEVER `--dangerously-bypass`.
- Off-limits files: `zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`
- Output: every command saves to `./ai-dispatch-output/` with metrics (structured JSON)
- Cache: explore/search cached 24h. Redteam/sandbox never cached.

## Fallback

- Gemini timeout (>120s): retry with simplified prompt
- Codex timeout (>180s): retry, then execute yourself with caution
- Rate limit: report to user, retry after daily reset
- Retired route (`reasoning` or `aider-*`, exit `2`): do not silently degrade.
  Use an armed topology chain or make the omission an explicit operator choice.

## Federation Protocol

- **Fleet nodes**: Pro, Air-M5, and Mini-Pro2. This parity audit targets Pro and
  Air-M5; Mini-Pro2 remains a host-specific lane. Peer SSH is for diagnostics
  and bounded probes.
- **Auth checks**: `status-auth` is deliberately local-only and checks the
  selected binary in one effective local security context. Run it locally on
  each host. It does not enumerate profiles/accounts, attest account
  distinctness, or treat an SSH session as equivalent to the interactive macOS
  session; `--fleet --check-auth` therefore fails closed.
- **Git authority**: GitHub `origin` is canonical for both hosts. Never sync through
  a remote that targets another host's ephemeral `.worktrees/<task>` path.
- **Branch safety**: use task branches/worktrees and preserve dirty peer worktrees;
  do not force either host's active branch to `main` merely to claim alignment.
- **Instructions**: `CLAUDE.md` and other tracked instructions converge through
  reviewed Git commits, not credential or home-directory copying.
- **A2A Plan**: pilot with Damar — Gemini CLI agent per team member, Claude Code supervisor
