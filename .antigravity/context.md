# Nuzantara — Antigravity IDE Context

> Aggiornato: 2026-03-14

## REGOLA ZERO: Verifica prima di agire

- **LEGGI il file** prima di modificarlo. Ogni volta.
- **VERIFICA** che funzioni/classi/endpoint esistano prima di riferirciti
- Se hai un "ricordo" di sessioni precedenti, **non fidarti** — verifica lo stato attuale
- Prima di ogni commit: `git diff` per verificare cosa stai committando
- `git push --force` su main: **PROIBITO ASSOLUTO**

## Project Identity

**Name:** Nuzantara (Zantara) v5.2.0
**Type:** Production AI Business Intelligence Platform
**Owner:** Bali Zero | **URL:** https://kita.balizero.com
**Owner codename:** Zero (real name PRIVATE — never expose)

## Architecture (updated 2026-03-22)

```
nuzantara/
├── apps/
│   ├── mouth/              → Next.js frontend (Vercel) — kita/my/prime.balizero.com
│   ├── backend-rag/        → FastAPI RAG backend (Fly.io) — 88 routers, 244 services
│   ├── nuzantara-mcp/      → MCP server v2.1 (109 tools, 10 prompts, 8 chains)
│   ├── nuzantara-mcp-advanced/ → Fly.io ops, diagnostics (14 tools)
│   ├── evaluator/          → SEO Guardian + QA + Core Guardian V3
│   ├── war-room/           → Ops dashboard + Canva automation
│   ├── bali-intel-scraper/ → Intel gathering (LOCAL ONLY on Pro, not on Fly)
│   ├── calendar/drive/knowledge/mail/web/ → Subdomain satellites
│   ├── admin-dashboard/    → Admin UI
│   └── webapp/             → Web application
└── packages/
    ├── kb/                 → Knowledge base
    └── core/               → Shared libraries (BZ tokens, BZLogo)
```

### Technology Matrix

| Layer | Technology | Scale |
|-------|------------|-------|
| Backend | FastAPI, Python 3.11+ | 88 routers, 244 services, 385 tests |
| Frontend | Next.js, TypeScript, Tailwind | App Router |
| Database | PostgreSQL 17 | Fly.io `nuzantara-postgres` (2GB) |
| Vectors | Qdrant | 9 collections, 66,595 vectors |
| Cache | Redis | Local on Pro |
| Knowledge Graph | LangGraph | 56,113 nodes, 161,173 edges |
| Embeddings | `text-embedding-3-small` | 1536 dims — **FROZEN** |
| Deploy | Fly.io (backend) + Vercel (frontend) | |
| MCP | nuzantara-mcp | 109 tools, 8 workflow chains |
| Channels | 7 omnichannel | WA, TG, IG, X, Web, GChat, Slack |

### Fly.io — ONLY 3 APPS

| App | RAM | Note |
|-----|-----|------|
| `nuzantara-rag` | 2GB | auto_stop=true, min=0 |
| `nuzantara-postgres` | 2GB | v0.1.0 |
| `nuzantara-qdrant` | 2GB | v1.12.1 |

## The 10 Golden Rules

1. **Virtualenv mandatory** — `source apps/backend-rag/venv/bin/activate`
2. **PYTHONPATH execution** — `PYTHONPATH=. python -m backend.module`
3. **Absolute imports** — `from backend.core import config`
4. **Async-first** — Use `httpx`, never `requests`
5. **Type everything** — Full type hints required
6. **No secrets in code** — Environment variables only
7. **Logger, not print** — Structured logging via `logger`
8. **Separate data/logic** — Clean architecture
9. **Quality gates** — Tests + error handling mandatory
10. **Verify sources** — Never presume, always check

## Prohibited Actions

- Remove `Any` from `typing` without verifying every usage
- Use `requests` instead of `httpx`
- Create nested Qdrant payloads (must be FLAT)
- Set `--workers 2+` in Dockerfile (OOM on Fly.io 2GB)
- Use relative imports
- `git push --force` on main
- Delete existing tests
- Modify `fly.toml` or `.env.production` without user confirmation

## Domain Knowledge

### KBLI (Indonesian Business Codes)
**Storage:** Qdrant | **Format:** FLAT payloads only
```json
{ "code": "47911", "title_id": "...", "title_en": "...", "category": "G" }
```

### Pricing: ONLY from PricingTool — never hardcode
### Evidence Scoring: <0.15 ABSTAIN | 0.15-0.60 CAUTIOUS | >0.60 NORMAL

## Git Sync Architecture (updated 2026-03-28)

Both Pro and Air work on `main`. Sync is **automatic via husky post-commit hooks**.

- **Pro commits** → Air auto-pulls via SSH (`git pull pro main --ff-only`)
- **Air commits** → Air auto-pushes to Pro (`git push pro main`)
- **GitHub** → Pro pushes to `origin/main` after its own commits

Do NOT manually push from Air to GitHub — Pro handles GitHub sync.
Do NOT create an `air` branch — both machines are always on `main`.

Log: `~/.openclaw/logs/git-sync.log` on both machines.

## Multi-Agent Coordination

- **Claude Code:** Architecture, refactoring, complex logic, autonomous agents
- **Gemini:** Research, analysis, multi-file operations
- **Antigravity (you):** System orchestration, cross-cutting changes

### Handoff Protocol
1. Read current state of files involved (don't trust memory)
2. Specify exact files/paths
3. State expected outcomes
4. Verify after completion with `git diff`

## Pre-Deploy Checklist (MANDATORY)

```bash
git diff --name-only HEAD -- apps/backend-rag/backend/
cd apps/backend-rag && source venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py -q
fly deploy --strategy rolling --app nuzantara-rag
```

**If any step fails, DO NOT deploy.**

## Resources

- `CLAUDE.md` — Complete project rules (primary source, most detailed)
- `PRICING_REFERENCE.md`, `VISA_TYPES_REFERENCE.md`
- API Docs: http://localhost:8000/docs

---
**Last updated:** 2026-03-28
**Maintainer:** Bali Zero AI Team
