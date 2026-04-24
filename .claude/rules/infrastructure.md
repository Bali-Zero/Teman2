---
paths:
  [
    "**/fly.toml",
    "**/Dockerfile",
    "**/.env*",
    "**/docker-compose*",
    "**/vercel.json",
  ]
---

# Infrastructure Rules

- Fly.io: ONLY 3 apps (nuzantara-rag, nuzantara-qdrant, nuzantara-postgres)
- bali-intel-scraper runs ONLY on Pro locally via OpenClaw — NOT on Fly
- Backend deploy: ALWAYS from `apps/backend-rag/` (not monorepo root — manca training-data)
- Use `fly deploy --strategy rolling` for zero-downtime
- Pre-deploy: run critical import chain + KG tests (CLAUDE.md §13 checklist)
- Never modify fly.toml, docker-compose.yml, .env.production without user confirmation
- Secrets via env vars or secrets manager — never hardcode
