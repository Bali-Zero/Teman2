# nuzantara-mcp-browser — Non-Inferable Knowledge

## Purpose
FastMCP server exposing stealth Playwright tools backed by `packages/browser-core`.

## When to use
- **Not** for Claude Code interactive (use `mcp__claude-in-chrome__*` per root CLAUDE.md section 2)
- **Yes** for OpenClaw agents, backend pipelines, headless automation
- **Yes** when user explicitly orders `mcp__nuzantara-browser__*`

## Test commands

```bash
pytest                                   # unit (in-memory Client, mocked manager)
pytest -m integration                    # real Chromium + example.com
pytest -m stealth --rootdir=../../packages/browser-core  # bot.sannysoft.com validation
```

## Lifespan

`@lifespan` decorator initializes the shared `BrowserManager` on startup
and closes it on shutdown. No orphan Chromium processes on SIGTERM.

## Policy

Local Playwright only, no LLM SDK imports, compliant with
`feedback_no_anthropic_api_automation.md`.
