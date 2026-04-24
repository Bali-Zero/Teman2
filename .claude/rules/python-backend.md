---
paths:
  [
    "apps/backend-rag/**/*.py",
    "apps/nuzantara-mcp/**/*.py",
    "apps/nuzantara-mcp-advanced/**/*.py",
    "apps/bali-intel-scraper/**/*.py",
    "apps/graph-engine/**/*.py",
  ]
---

# Python Backend Rules

- Always use `PYTHONPATH=. python -m module.path` — never run files directly
- Use `httpx` (async) — never `requests`
- Use `logger` — never `print()`
- Absolute imports only: `from backend.core import config`
- Full type annotations on every function
- Flat Qdrant payloads — never nested structures
- All I/O must be async (httpx, aiofiles, asyncpg)
- Embedding model is FROZEN: `text-embedding-3-small` (1536 dims) — never change
- Prices come from `PricingTool` only — never hardcode
- Tests required for new features: `PYTHONPATH=. pytest tests/path -v`
- **Anthropic access is OAuth-only** — never `ANTHROPIC_API_KEY`, never `anthropic.Anthropic(...)`, never Bedrock/Vertex Anthropic paid endpoints. Every Claude call must go through `backend/llm/claude_oauth_client.py` (spawns `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN` from Max subscription). See project CLAUDE.md Golden Rule #13.
