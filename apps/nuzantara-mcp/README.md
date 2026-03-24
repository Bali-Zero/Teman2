# Nuzantara MCP Server v2.1

Primary MCP server for Zantara AI assistant. FastMCP, stdio transport.

## Capabilities

- **131 Tools** (118 Nuzantara + 13 Advanced via federation bridge)
- **10 Prompts** for guided workflows
- **5 Resources** for knowledge base access
- **8 Workflow Chains** (daily_ops_autopilot, new_client_onboarding, etc.)

## Setup

```bash
cd apps/nuzantara-mcp
pip install -e .
# Or via OpenClaw mcporter wrappers in ~/.local/bin/
```

## Key Files

- `src/nuzantara_mcp/server.py` — Main server
- `src/nuzantara_mcp/tools/` — Tool definitions
- `src/nuzantara_mcp/prompts/` — Prompt templates
- `src/nuzantara_mcp/resources/` — Resource providers
