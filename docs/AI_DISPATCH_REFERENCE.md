# AI Dispatch System — Full Reference

> Extracted from CLAUDE.md §16 on 2026-03-31 to reduce context window load.
> Quick reference remains in CLAUDE.md §12. This file has full details.

## 3-Tier Taxonomy (v3.1, 2026-03-25)

### AGENTS — Autonomous runtimes, dispatchable via ai-dispatch.sh

| Agent                           | Role                                                 | Dispatch Command                           |
| ------------------------------- | ---------------------------------------------------- | ------------------------------------------ |
| **Claude Code (Opus 4.6)**      | Il Re — orchestrates, synthesizes, decides, executes | Direct (IS the orchestrator)               |
| **Gemini 3.1 Pro CLI**          | Il Consigliere — 1M ctx, read-only                   | `explore`, `search`, `redteam`, `gemini-*` |
| **Codex 5.4 CLI**               | Il Soldato — sandbox kernel-level                    | `sandbox`, `codex-*`                       |
| **Claude CLI (Opus 4.6)**       | Il Giudice — review, redteam, read-only              | `claude-review`, `claude-redteam`          |
| **DeepSeek R1 671b (API)**      | Il Pensatore — chain-of-thought reasoning            | `reasoning`                                |
| **Aider (OpenRouter/DeepSeek)** | Il Mercenario — multi-model coding                   | `aider-fix`, `aider-refactor`              |

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
6. **REASONING**: `reasoning "complex problem"` → DeepSeek R1 671b chain-of-thought

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

## Federation Protocol

- **Escalation**: Air writes findings in `shared/escalations.json`, Pro reads at session start
- **Git sync** (2026-03-28): Automatic via `.husky/post-commit`:
  - Pro commits → Air auto-pulls (`ssh air 'git pull pro main --ff-only'`)
  - Air commits → Air pushes to Pro (`git push pro main`)
  - GitHub: only Pro pushes to `origin`. Air NEVER pushes to `origin`.
  - Both on `main`. No `air` branch. Log: `~/.openclaw/logs/git-sync.log`
- **CLAUDE.md**: IDENTICAL on both — git-tracked, push/pull mandatory
- **A2A Plan**: pilot with Damar — Gemini CLI agent per team member, Claude Code supervisor
