# Nuzantara MCP Server v2.1

Primary MCP server for Zantara AI assistant. FastMCP, stdio transport.

## Capabilities

- **115 Tools** (primary MCP server) + **14 Advanced** (nuzantara-mcp-advanced, separate server)
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
- `src/nuzantara_mcp/auth.py` — Per-tool role enforcement

## Auth model — defense in depth

Tool access is gated at two independent layers. Either one alone is enough to
block a wrong-role call; together they fail closed on misconfiguration.

1. **Wrapper filter (primary gate)** — `apps/team-agent/mcp-wrapper/` is a
   stdio proxy that inspects JSON-RPC traffic. `tools/list` responses are
   filtered to only expose tools allowed for the caller's `AGENT_ROLE`, and
   `tools/call` for any other tool is rejected at the proxy. Production
   clients (OpenClaw, Gemini CLI) connect through the wrapper.
2. **Per-tool decorator (defense in depth)** — `nuzantara_mcp.auth.require_role(*roles)`
   wraps each sensitive tool. Even if a client bypasses the wrapper and
   connects directly to the MCP server's stdio, the decorator re-checks
   `AGENT_ROLE` and raises `MCPAccessDenied` on mismatch.

### Source of truth

Both layers read from the same YAML:
`apps/team-agent/mcp-wrapper/config/roles.yaml`. That file lists, per role, the
tool names the role may invoke. `admin` holds the `*` wildcard and always
passes. Changing the taxonomy is a one-file edit; both the wrapper's filter
and the decorator's `ROLE_TAXONOMY` pick it up on restart.

### AGENT_ROLE resolution

The wrapper forwards its configured `AGENT_ROLE` to the MCP subprocess it
spawns. When the wrapper is skipped (direct stdio for debug or dev), the
env var is usually unset — the decorator reads that as the `unknown` role,
which only has access to tools decorated with `@public_tool`. Missing env =
no data, fail closed.

### OSINT blindato in denied-access logs

When a caller is denied, the auth module logs `tool + caller role + required
roles` at WARNING level. Tool arguments are never logged — they may carry
OSINT or client PII, and the `test_denied_access_is_logged_without_payload`
test pins this invariant.

### Coverage

`@require_role` currently decorates 36 of the 115 tools, prioritising the 25
tools explicitly listed in `roles.yaml` plus 11 admin-only mutation/ingest
tools (legal ingestion, invoice operations, admin logs, team hours). Tools
not yet decorated still pass through the wrapper filter, which is the primary
gate; the decorator roll-out continues tool by tool with no downtime.
