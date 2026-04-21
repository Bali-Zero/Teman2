# CLAUDE.md — Nuzantara Project Context (trimmed 2026-04-22, T1.2)

> **Read `SYMBIOSIS.md` first.** Defines principles governing this ecosystem.
> **Read `VADEMECUM.md` before building new.** Operative checklist per element type.
> **Find where X lives?** See [`INDEX.md`](INDEX.md).
> **Full detail:** [`CLAUDE-DETAIL.md`](CLAUDE-DETAIL.md) — load on demand via Read tool.

## 0. Machine Identification (IMPORTANT)

| Machine | User             | Hostname      | Role                            |
| ------- | ---------------- | ------------- | ------------------------------- |
| **Pro** | `nuzantara`      | `Nuzantara`   | Server H24 + Dev (48GB M4 Pro)  |
| **Air** | `antonellosiano` | `Nuzantara-9` | Server H24 (16GB M4)            |

At session start:
```bash
echo "Machine: $(whoami)@$(hostname)" && OTHER=$(if [ "$(whoami)" = "nuzantara" ]; then echo "air"; else echo "pro"; fi) && ssh -o ConnectTimeout=3 $OTHER 'echo "Peer: $(whoami)@$(hostname)"' 2>/dev/null || echo "Peer: UNREACHABLE"
```

- `whoami` = `nuzantara` → **Pro** · `whoami` = `antonellosiano` → **Air**
- Always prefix first response with `[Pro]` or `[Air]`
- SSH: `ssh air` / `ssh pro` (mDNS)

## 1. Project Overview

**Name:** Nuzantara (Zantara) · **Version:** 5.2.0
**Business:** Bali Zero — agenzia immigration/company/tax Indonesia
**Stack:** FastAPI + Postgres + Qdrant + Redis, Next.js/React 6 subdomains Vercel, Fly.io hosting

Detail: [CLAUDE-DETAIL.md §1](CLAUDE-DETAIL.md)

## 2. Claude Code Behavior Rules (IMPORTANT)

**DO NOT ask the user to write code.** Act first, ask if blocked. Use `Edit`, `Write`, `Bash` without asking. **NEVER** "should I write this?" — just do it.

**Autonomous Ops L2 attivo** (2026-04-21): read [`AUTONOMOUS_OPS.md`](AUTONOMOUS_OPS.md) before git push, PR, deploy, `fly ssh`, shared-state changes.

**Browser:** ALWAYS `mcp__claude-in-chrome__*`, NEVER `mcp__playwright__*` (unless ordered). Text before screenshot.

**Escalations:** check `shared/escalations.json` at session start.

Detail (Federation orchestrator triggers, Preflight SDD levels): [CLAUDE-DETAIL.md §2](CLAUDE-DETAIL.md)

## 3. MOS — Memory Operating System (essentials)

SessionStart hook auto-loads last 5 important memories (importance ≥ 7) from SQLite.

**CLI `mem`** (`~/.claude/scripts/mem`):
| Command | Action | Latency |
|---|---|---|
| `mem recent` | ultime memorie importanti | <10ms |
| `mem query "text"` | FTS5 search | <10ms |
| `mem save decision \|discovery\|fact\|unresolved "text" <importance>` | salva | <10ms |

**Salvataggio proattivo OBBLIGATORIO**: salva senza chiedere quando emerge decision (8-10), discovery (7-8), fact (7-8), unresolved (5-6). File changes auto-tracciati.

Detail (NB lookup, entities, sessions): [CLAUDE-DETAIL.md §3](CLAUDE-DETAIL.md)

## 4. Golden Rules (ENFORCE STRICTLY)

1. **Virtualenv Mandatory** — never system Python
2. **No Root Execution** — `PYTHONPATH=. python -m backend.module`
3. **Path Discipline** — absolute imports only
4. **Async First** — `httpx` not `requests`
5. **Type Hints** — full annotations
6. **No Hardcoded Secrets** — env vars / secrets manager
7. **Data/Logic Separation** — business logic ≠ data access
8. **Clean Logging** — `logger` never `print()`
9. **Verify Sources** — never presume
10. **Async HTTP Clients** — persistent `_get_client`, close in `lifespan`, NEVER `httpx.AsyncClient()` in methods/loops

Detail: [CLAUDE-DETAIL.md §4](CLAUDE-DETAIL.md)

## 5. CRITICAL OPERATIONAL RULES (compressed)

**Virtualenv**: Air `venv` · Pro `.venv` · pip Air `/Users/antonellosiano/.pyenv/shims/python3 -m pip`

**Drive Polling**: Air only, cron 5min, NOT Fly.io. `page_token` in `system_settings`. Circuit breaker 3 fail → OPEN + Telegram.

**Drive OAuth**: token `google_drive_tokens`, ~90d expiry, watchdog alerts 7d prior. Re-auth `https://kita.balizero.com/settings/integrations`.

**OCR Multi-page**: ALL pages always, 120s timeout >3 pages. Vision: `qwen2.5vl:7b` ONLY.

**Cache Invalidation**:
```python
await invalidate_cache("zantara:namespace:*")  # after EVERY mutation
```

**KG Subgraph**: Company ✅ · Visa ✅ · Property ✅ · Tax ✅

**Cron Air full table + GitHub Secrets detail**: [CLAUDE-DETAIL.md §14](CLAUDE-DETAIL.md)

## 6. Critical Paths (quick index)

- `apps/backend-rag/` — FastAPI backend (PRIMARY deploy)
- `apps/mouth/` — kita + 6 subdomain Vercel (deploy from monorepo root)
- `apps/evaluator/` — SEO Guardian, KBLI indexing, NLM research
- `apps/cell/` — biological cell system (self-repair, SEO cell v2.1)
- `packages/cell-core/` — shared library (workspace `-e ../../packages/cell-core`)

Full map + domain knowledge: [CLAUDE-DETAIL.md §5-6](CLAUDE-DETAIL.md)

## 7. MCP Servers (essentials)

Active: `claude-in-chrome`, `notebooklm`, `filesystem`, `github`, `sequential-thinking`, `memory`, `exa`, `brave-search`, `ahrefs`, `cloudflare`, `canva`, `context7`. Full list + auth notes: [CLAUDE-DETAIL.md §7](CLAUDE-DETAIL.md)

## 8. Deployment (essentials)

**Rules**:
- `mouth/kita` → da root monorepo (`~/Desktop/nuzantara`), NON da `apps/mouth/`
- Backend → SEMPRE da `apps/backend-rag/` (no monorepo root — manca `training-data`)
- Satellite apps → da `apps/<name>/` dir (vercel già linkato)
- Frontend `NEXT_PUBLIC_*` env → `git push` non `vercel --prod`

**Post-deploy QA obbligatorio** (screenshot): vedi [CLAUDE-DETAIL.md §10](CLAUDE-DETAIL.md).

**Pre-deploy Checklist + AI Dispatch System**: [CLAUDE-DETAIL.md §11-12](CLAUDE-DETAIL.md)

## 9. Language Protocol

- **Italian** per interazione con user (Antonello)
- **English** per commit message, PR body, code comments (se servono), docs
- Mai mescolare nello stesso artifact

## 10. Anthropic API — Quick Reference

- **Mai API a pagamento nuova** (regola fissa) — solo quota OAuth MAX già attiva
- Model IDs: `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`
- Detail routing + cache: [CLAUDE-DETAIL.md §13](CLAUDE-DETAIL.md)

## 11. Research Capture Convention

Quando produci ricerca sostanziosa (≥400 parole + ≥3 fonti + checklist) per caso cliente Bali Zero (property/visa/tax/HR/compliance):

**Dove**: `~/Desktop/nuzantara/research/{domain}/YYYY-MM-DD-topic-slug.md` con frontmatter `date/domain/client_case/sources`.

**Su approval**: scrivi file, appendi entry in `~/.claude/projects/-Users-nuzantara/memory/MEMORY.md` sotto `## Research Captures`. Solo domain=property → push NB-5 via `mcp__notebooklm-mcp__source_add`.

**Never auto-promote** a KB ufficiale (`apps/backend-rag/backend/kb/`).

Full spec + frontmatter example: [CLAUDE-DETAIL.md §16](CLAUDE-DETAIL.md)

---

**Last Updated:** 2026-04-22 (trimmed 487→150 righe in T1.2)
**Maintained by:** Bali Zero AI Team
**Full content archived:** [CLAUDE-DETAIL.md](CLAUDE-DETAIL.md) (lazy-loadable)
