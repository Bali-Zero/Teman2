---
name: antigravity
description: 'Bridge to Google Antigravity IDE — open files in visual editor, launch browser subagent, trigger visual diff, delegate complex multi-file refactoring and architecture tasks. Use when task needs visual editing, browser automation, or multi-agent workspace coordination.'
metadata: { 'openclaw': { 'emoji': '🚀', 'requires': { 'bins': ['antigravity'] } } }
---

# Antigravity IDE Bridge

## What is Antigravity?

Google's agent-first IDE with visual editor, browser subagent, Knowledge Items (persistent memory), and multi-model orchestration. It runs locally on Pro as a standalone app.

## Commands

### Open file in visual editor

```bash
antigravity "/Users/nuzantara/Desktop/nuzantara/path/to/file.py"
```

### Visual diff between files

```bash
antigravity -d file1.py file2.py
```

### Open workspace

```bash
antigravity "/Users/nuzantara/Desktop/nuzantara"
```

## When to Delegate to Antigravity

Use Antigravity (via bridge) when the task requires:

- **Visual architecture review** — complex multi-file relationships
- **Browser subagent** — visual QA, web scraping, form interaction
- **Planning mode** — deep research + structured task groups
- **Multi-file refactoring** — Antigravity's editor handles file coordination well

## Bridge Script

To inject a task into Antigravity's context for its agents to pick up:

```bash
/Users/nuzantara/Desktop/nuzantara/scripts/zan_to_antigravity.sh "task description here"
```

This appends the task to `.antigravity/context.md` and plays a macOS notification sound.

## Antigravity Configuration

### Workspace Rules (`.agents/rules/`)

- `always-on.md` — Core identity, owner info, machine context
- `nuzantara-backend.md` — Python/FastAPI rules (glob: `apps/backend-rag/**/*.py`)
- `nuzantara-frontend.md` — Next.js/TypeScript rules (glob: `apps/mouth/**/*.{ts,tsx}`)
- `nuzantara-infra.md` — Fly.io/Docker infrastructure rules

### Workspace Workflows (`.agents/workflows/`)

- `/deploy-backend` — Fly.io deploy with safety checks
- `/deploy-frontend` — Vercel deploy with visual QA
- `/qa-visual` — Screenshot all subdomains and verify

### Workspace Skills (`.agents/skills/`)

- `nuzantara-dev` — Full-stack development patterns and decision tree

### MCP Servers (via `~/.gemini/antigravity/mcp_config.json`)

- `nuzantara-rag` — 115 tools (CRM, portal, intel, KBLI, analytics)
- `nuzantara-ops` — Fly.io ops, deployment, diagnostics
- `sequential-thinking` — Structured reasoning
- `GitKraken` — Git operations via GitLens
- `StitchMCP` — Google Stitch integration
- `gmp-code-assist` — Google Maps code assistance

## Knowledge Items

Antigravity auto-generates Knowledge Items from conversations. These persist across sessions and inform future responses. No manual management needed — the system learns from usage.

## Agent Modes

- **Planning mode**: For complex tasks — creates task groups, artifacts, structured research
- **Fast mode**: For simple tasks — direct execution, no planning overhead

Recommend Planning mode for Nuzantara work (architecture, features). Fast mode for quick fixes only.

## Settings Recommendations

- Artifact Review: "Always Proceed" (trusted developer)
- Terminal Allow: `git *`, `npm *`, `python -m *`, `fly *`, `ruff *`
- Non-Workspace File Access: ON (needed for ~/.gemini/, secrets)
