# OPENCLAW_SYSTEM.md — Guida Orchestrazione Multi-AI

> Per: OpenClaw (che usa Claude/Kimi come modelli)
> Aggiornato: 2026-02-16

---

## Panoramica

OpenClaw orchestra più AI su Nuzantara. Questo documento definisce **quale AI usare per quale task**, come coordinare il lavoro, e quali MCP server sono disponibili.

---

## Mappa dei Ruoli AI

| AI                             | Forza                                                                | Quando usarlo                                            |
| ------------------------------ | -------------------------------------------------------------------- | -------------------------------------------------------- |
| **Claude (Haiku/Sonnet/Opus)** | Codebase navigation, refactoring, file edit, deploy review           | Modifiche al codice, debug, code review, task multi-file |
| **Kimi**                       | Deep thinking, analisi filosofica/architetturale, browser navigation | Analisi strategiche, research web, review architettura   |
| **Gemini**                     | Velocità, task semplici, search                                      | Task rapidi, query singole, lookup                       |
| **Cursor**                     | IDE-native editing                                                   | Modifiche inline in file aperti nell'IDE                 |

---

## MCP Server Disponibili (tutti gli agenti)

### `nuzantara-rag` — Dominio

```
Binary: /Users/nuzantara/.local/bin/nuzantara-mcp
Env: NUZANTARA_BACKEND_URL=https://nuzantara-rag.fly.dev
```

| Tool                                       | Descrizione               |
| ------------------------------------------ | ------------------------- |
| `search_kbli(query, limit)`                | Cerca codici KBLI 2025    |
| `inspect_kbli(code)`                       | Dettaglio codice KBLI     |
| `chat_kbli(query)`                         | Consultazione AI KBLI     |
| `ask_legal(question, user_id, session_id)` | RAG legale (richiede JWT) |
| `check_health()`                           | Health backend            |
| `check_health_detailed()`                  | Health per-servizio       |
| `get_qdrant_metrics()`                     | Metriche vector DB        |

### `nuzantara-ops` — Operativo

```
Binary: /Users/nuzantara/.local/bin/nuzantara-mcp-advanced
Env: FLY_APP=nuzantara-rag, NUZANTARA_ROOT=/Users/nuzantara/Desktop/nuzantara
```

| Tool                                    | Descrizione                 |
| --------------------------------------- | --------------------------- |
| `check_fly_status()`                    | Status Fly.io               |
| `get_fly_logs(lines, filter_str)`       | Log produzione              |
| `check_deployment_readiness()`          | Pre-deploy check automatico |
| `run_backend_tests(test_path, verbose)` | Esegui pytest               |
| `run_type_checking()`                   | mypy                        |
| `run_linting()`                         | ruff check + format         |
| `check_system_health()`                 | Health completo             |
| `get_collection_stats()`                | Stats Qdrant                |
| `search_codebase(query, file_pattern)`  | Cerca nel codice            |

---

## Workflow Consigliati

### Deploy Backend

1. **Claude** → `check_deployment_readiness()` via nuzantara-ops
2. **Claude** → revisiona le modifiche, conferma
3. **Claude** → `fly deploy --strategy rolling`
4. **Claude** → `check_system_health()` per verifica post-deploy

### Debug Produzione

1. **Claude** → `get_fly_logs(100, "ERROR")` per isolare il problema
2. **Kimi** → analisi approfondita del pattern di errore
3. **Claude** → fix e test locali
4. **Claude** → deploy

### Research KBLI / Business

1. **Kimi** → research contestuale e navigazione web
2. **Claude** → `search_kbli(query)` per match precisi
3. **Claude** → implementa la risposta nel codebase

### Code Review

1. **Claude** → `run_linting()` + `run_type_checking()`
2. **Claude** → revisiona file modificati con strumenti nativi
3. **Kimi** → review architetturale se necessario

---

## Configurazione MCP per OpenClaw

Aggiungere in `~/.openclaw/config.toml` o equivalente:

```toml
[mcp.servers.nuzantara-rag]
command = "/Users/nuzantara/.local/bin/nuzantara-mcp"
[mcp.servers.nuzantara-rag.env]
NUZANTARA_BACKEND_URL = "https://nuzantara-rag.fly.dev"

[mcp.servers.nuzantara-ops]
command = "/Users/nuzantara/.local/bin/nuzantara-mcp-advanced"
[mcp.servers.nuzantara-ops.env]
FLY_APP = "nuzantara-rag"
NUZANTARA_ROOT = "/Users/nuzantara/Desktop/nuzantara"
```

---

## Regole di Coordinazione

1. **Una fonte di verità:** `CLAUDE.md` è la fonte primaria. GEMINI.md, `.cursorrules`, `.kimi/NUZANTARA_IDENTITY.md` sono adattatori.
2. **No rogue refactoring:** Nessun AI deve rimuovere import, rinominare funzioni o cancellare file senza esplicita richiesta di Zero.
3. **Deploy = Claude:** Solo Claude esegue i deploy (ha il contesto pre-deploy completo).
4. **Kimi per browser:** Solo Kimi ha accesso Playwright per navigazione web.
5. **Privacy Zero:** Nessun AI rivela il nome reale di Zero. Mai.

---

## Onboarding Rapido per Nuovo Agente

Se stai leggendo questo come nuovo agente, leggi in ordine:

1. `CLAUDE.md` — regole e golden rules
2. `docs/AI_ONBOARDING.md` — contesto completo
3. `docs/LIVING_ARCHITECTURE.md` — architettura live
4. `.mcp.json` — tool disponibili nel workspace
5. Questo file — come collaborare con gli altri AI
