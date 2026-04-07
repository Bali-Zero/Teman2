# nuzantara-mcp-browser

FastMCP server exposing Nuzantara's stealth Playwright browser manager
(`packages/browser-core/`) as MCP tools.

## When to use

- **NOT** for Claude Code interactive -> use `mcp__claude-in-chrome__*`
  (enforced by root `CLAUDE.md` section 2).
- **Yes** for OpenClaw agents, backend automation, or non-interactive
  contexts where `claude-in-chrome` does not apply.
- **Yes** when the user explicitly orders `mcp__nuzantara-browser__*`
  during a Claude Code session.

## Tools

| Tool | Signature | Purpose |
|---|---|---|
| `browser_navigate` | `(url)` | Navigate, return {url, title, status} |
| `browser_get_page_content` | `(url)` | One-shot HTML fetch |
| `browser_snapshot` | `(url)` | Accessibility tree dict |
| `browser_click` | `(url, selector)` | Click first match |
| `browser_type` | `(url, selector, text)` | Fill first match |
| `browser_extract_text` | `(url, selector)` | inner_text of first match |

## Install

    cd apps/nuzantara-mcp-browser
    pip install -e ".[dev]"
    python -m playwright install chromium

## Run

    nuzantara-mcp-browser   # stdio transport

## Testing

    pytest                          # unit tests (in-memory Client)
    pytest -m integration           # real Chromium + example.com

## Policy compliance

Local Playwright only. No LLM SDK imports. Complies with
feedback_no_anthropic_api_automation.md.
