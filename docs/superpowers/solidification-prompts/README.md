# Solidification Prompts — 13 Component Deep Analysis

13 prompt per Claude Opus 4.6 MAX. Ogni prompt lancia un'analisi profonda di un componente fondamentale del sistema Nuzantara, con brainstorming multi-agente e validazione NB-1.

## Distribution

### PRO (nuzantara@Nuzantara) — 6 prompt

| # | File | Componente | Righe |
|---|------|-----------|-------|
| 01 | `01-pro-rag-pipeline.md` | RAG Pipeline (61 file, LangGraph, 4 subgraph, hybrid search) | 149 |
| 02 | `02-pro-app-bootstrap.md` | App Bootstrap (dependencies.py, app_factory, 94 router) | 115 |
| 03 | `03-pro-auth-security.md` | Auth/Security (JWT, RBAC, SSO, PDP compliance) | 125 |
| 04 | `04-pro-llm-integration.md` | LLM Integration (6 provider, Ollama-first, fallback) | 134 |
| 05 | `05-pro-knowledge-graph.md` | Knowledge Graph (108k nodi, 243k edges, 4 subgraph) | 132 |
| 06 | `06-pro-deploy-infra.md` | Deploy/Infra (Fly.io 3 app, Vercel, backup, DR) | 131 |

### AIR (antonellosiano@Nuzantara-9) — 5 prompt

| # | File | Componente | Righe |
|---|------|-----------|-------|
| 07 | `07-air-database-layer.md` | Database Layer (pool, 94 migration, repository) | 128 |
| 08 | `08-air-crm-system.md` | CRM System (client lifecycle, practices, compliance) | 139 |
| 09 | `09-air-channel-system.md` | Channel System (WhatsApp, Telegram, Instagram, Web, X) | 138 |
| 10 | `10-air-cron-background.md` | Cron/Background (15+ job, Air+Pro+Fly.io) | 156 |
| 11 | `11-air-mcp-server.md` | MCP Server (131 tools, 8 chains, 24 moduli) | 132 |

### COWORK — 2 prompt

| # | File | Componente | Righe |
|---|------|-----------|-------|
| 12 | `12-cowork-vector-search.md` | Vector Search/Qdrant (10 collection, 93k docs, hybrid) | 136 |
| 13 | `13-cowork-frontend.md` | Frontend/mouth (Next.js, 1841 TSX, 8 subdomain) | 153 |

## Workflow per prompt

```
FASE 1: STUDIO PROFONDO
  └─ Opus legge TUTTO il codice del componente

FASE 2: BRAINSTORMING MULTI-AGENTE
  ├─ Gemini CLI (explore/search)
  ├─ Codex CLI (sandbox testing)
  ├─ DeepSeek R1 (reasoning)
  ├─ Deep Research (Exa + NLM)
  └─ Opus VALUTAZIONE CRITICA
      └─ Per ogni suggerimento: ACCETTO / RIFIUTO / PARZIALE (con motivazione)

FASE 3: WRITING PLAN
  ├─ A. PULIZIA (eliminare/semplificare)
  ├─ B. IRROBUSTIMENTO (resilienza)
  ├─ C. POTENZIAMENTO (migliorare)
  ├─ D. AUTOMATISMO EVOLUTIVO (auto-grow, auto-learn)
  └─ E. METRICHE DI SUCCESSO

FASE 4: VALIDAZIONE NB-1
  └─ Oracolo valida, Opus resta critico
```

## Principi chiave

- **NON INFLUENZABILE**: Opus valuta ogni input con scetticismo costruttivo
- **CRITICO**: non accettare suggerimenti per consensus, solo per merito tecnico
- **PRAGMATICO**: soluzioni mantenibili per team piccolo, non over-engineering
- **MISURABILE**: ogni proposta ha metriche before/after

## Come lanciare

```bash
# Pro — copia e incolla in una nuova sessione Claude Code
cat docs/superpowers/solidification-prompts/01-pro-rag-pipeline.md | pbcopy

# Air — via SSH
ssh air
cat ~/Projects/nuzantara/docs/superpowers/solidification-prompts/07-air-database-layer.md | pbcopy

# Cowork — apri il file nel workspace e copia in una nuova conversazione
```

## Output atteso per ogni prompt

1. Mappa completa del componente (diagramma testuale)
2. Audit findings con severity (CRITICAL/HIGH/MEDIUM/LOW)
3. Writing Plan con task ordinate per priorita e dipendenza
4. Stima effort per task (S/M/L/XL)
5. Rischi e mitigazioni
6. Metriche before/after
