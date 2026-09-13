# MCP servers and deployment architecture

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.

## 6. MCP Servers

**Primary:** `apps/nuzantara-mcp/` (v2.1, FastMCP, stdio transport)
**Capabilities:**

- **115 Tools** across 24 modules (CRM, portal, intel, content, analytics, knowledge, comms, drive, sheets, workflows, admin, health, google_bridge, journey, pricing, invoicing, compliance, memory, langsmith, legal, prime, federation, naga, heartbeat)
- **10 Prompts** for guided workflows
- **5 Resources** for knowledge base access
- **8 Workflow Chains** for deterministic automation (daily_ops_autopilot, new_client_onboarding, practice_lifecycle_check, intel_pipeline, weekly_report, client_health_monitor, compliance_autopilot, journey_accelerator)

**Additional MCP servers:**

- `apps/nuzantara-mcp-advanced/` — Fly.io ops, deployment readiness, code search, diagnostics
- `apps/nuzantara-mcp-browser/` — Browser automation

## 7. Deployment Architecture

### Production Stack

- **Frontend:** Vercel (CDN, Edge Functions)
- **Backend:** Fly.io `nuzantara-rag` (Asia region)
- **Databases:**
  - PostgreSQL: Fly.io managed
  - Qdrant: Fly.io app
  - Redis: Upstash or Fly.io

### Environment Variables

**Required:**

- `OPENAI_API_KEY` - For embeddings
- `DATABASE_URL` - PostgreSQL connection
- `QDRANT_URL`, `QDRANT_API_KEY` - Vector DB
- `REDIS_URL` - Cache
- `JWT_SECRET` - Authentication
- `FLY_API_TOKEN` - Deployment (CI/CD)
