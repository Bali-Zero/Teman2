# NotebookLM Knowledge Fabric — Operational Strategy v1.0

**Date:** 2026-03-25
**Tier:** Google AI Ultra (600 sources/notebook, 500 notebooks)
**Authors:** Claude Code (Opus 4.6) + Gemini 3.1 Flash (implementation) + Codex 5.4 (quality audit)

---

## Architecture: 8+1 Notebooks

| NB       | Name                      | Sources | Tags                                    | Refresh                |
| -------- | ------------------------- | :-----: | --------------------------------------- | ---------------------- |
| NB-1     | Codebase & Architecture   |   35    | codebase, architecture, mcp, deploy     | Daily (OpenClaw 04:30) |
| NB-2     | Immigration & Visa        |   ~80   | immigration, visa, kitas, kitap, tka    | Monthly                |
| NB-3     | Company, KBLI & Licensing |  ~100   | company, kbli, pma, oss, licensing      | Quarterly              |
| NB-4     | Tax & Compliance          |   ~70   | tax, compliance, lkpm, npwp, pph        | Monthly                |
| NB-5     | Property & Zoning         |   ~60   | property, zoning, land, hgb, villa      | Quarterly              |
| NB-6     | Operations & Service      |   ~35   | operations, sop, team, pricing, crm     | Monthly                |
| NB-7     | Editorial & Market Intel  |   ~50   | editorial, seo, content, intel, trends  | Weekly                 |
| NB-8     | Expat Life & Bali Living  |   ~60   | lifestyle, expat, healthcare, education | Monthly                |
| **NB-9** | **Research Lab**          | Dynamic | research, external, web                 | On-demand only         |

**NB-9 is NEVER mixed into NB-1.** Deep Research creates web sources that would drown internal code truth.

---

## 1. When to Consult Notebooks (Oracolo)

### Via CLI

```bash
# Architecture questions (NB-1)
./scripts/ai-dispatch.sh oracolo "How does the ReAct loop handle tool timeouts?"

# Domain questions (any notebook)
./scripts/ai-dispatch.sh oracolo-nb "immigration" "What are the KITAS renewal requirements for 2026?"
./scripts/ai-dispatch.sh oracolo-nb "tax" "What are PPN obligations for PT PMA?"
```

### Trigger Conditions

| Trigger                  | Command                                                 | When                  |
| ------------------------ | ------------------------------------------------------- | --------------------- |
| Modifying >2 modules     | `oracolo "impact analysis for [change]"`                | Before coding         |
| Debugging cross-module   | `oracolo "trace the flow of [data] through the system"` | During debug          |
| New feature design       | `oracolo "existing patterns for [feature type]"`        | Before planning       |
| Pre-deploy review        | `oracolo "risks of deploying changes to [files]"`       | Before `fly deploy`   |
| Domain query from client | `oracolo-nb "tag" "question"`                           | When RAG score < 0.60 |

### CLAUDE.md Rule

> _"Per modifiche che toccano >2 moduli, DEVI consultare NB-1 via `oracolo` prima di proporre un piano."_

---

## 2. When to Trigger Deep Research

### Via CLI

```bash
# Deep research (5min, ~40 web sources → NB-9)
./scripts/ai-dispatch.sh research "Fly.io Python FastAPI auto_stop cold start optimization 2026" deep

# Fast research (30s, ~10 sources → NB-9)
./scripts/ai-dispatch.sh research "A2A protocol specification agent card" fast
```

### Trigger Conditions (on NB-9, NEVER on NB-1)

| Scenario               | Query Template                                  | Mode |
| ---------------------- | ----------------------------------------------- | ---- |
| New library adoption   | "[library] best practices migration [year]"     | deep |
| Production incident    | "[error] [framework] debugging [year]"          | fast |
| Performance bottleneck | "[component] optimization [metric] [year]"      | deep |
| Framework upgrade      | "[framework] v[old] to v[new] breaking changes" | deep |
| Regulatory update (ID) | "Indonesian [regulation type] [topic] [year]"   | deep |

### NEVER trigger Deep Research for:

- Questions notebooks already answer well
- Generic curiosity ("what is LangGraph?")
- Periodic refresh — web sources become stale, on-demand only

### Query Quality Rules

**Good:** `"Fly.io Python FastAPI 2GB RAM auto_stop cold start 2025 2026"` (specific, deployment-relevant)
**Bad:** `"FastAPI best practices"` (generic, imports 40 tutorials)
**Rule:** If the notebook can answer it, don't research it. Research fills gaps, not duplicates.

---

## 3. Daily NB-1 Refresh (OpenClaw Cron)

**Schedule:** 04:30 WITA daily
**Script:** `scripts/nlm_nb1_daily_refresh.py`
**Runtime:** OpenClaw cron on Pro

### Flow:

1. `git log --since="24 hours ago" --name-only` → changed files
2. Classify by area → regenerate only impacted bundles
3. `nlm source delete` old → `nlm source add` new
4. Log results

### Impact Areas:

| Changed Path                         | Bundle to Regenerate            |
| ------------------------------------ | ------------------------------- |
| `apps/backend-rag/backend/app/`      | `backend_01_app_and_agents.txt` |
| `apps/backend-rag/backend/services/` | `backend_02_services.txt`       |
| `apps/backend-rag/backend/core/`     | `backend_03_core_and_misc.txt`  |
| `apps/mouth/src/`                    | `nuzantara_frontend_mouth.txt`  |
| `apps/federation/`                   | `federation_*.txt`              |
| `apps/nuzantara-mcp/`                | `nuzantara_mcp_ecosystem.txt`   |
| `docs/*.md`                          | Update individual doc sources   |

---

## 4. Vision Model Routing

| Document Type              | Model                  | Reason                           |
| -------------------------- | ---------------------- | -------------------------------- |
| Client passport/KTP/NPWP   | **Qwen 2.5VL local**   | PII — never send to cloud        |
| Client contracts           | **Qwen 2.5VL local**   | Confidential business data       |
| UI screenshot for QA       | **Gemini Flash cloud** | Not sensitive, need speed (2-3s) |
| Public government PDF      | **Gemini Flash cloud** | Already public                   |
| OCR of degraded regulation | **Gemini Flash cloud** | Need quality OCR                 |

## 5. Reasoning Model Routing

| Task Type                  | Model                              | Why                                    |
| -------------------------- | ---------------------------------- | -------------------------------------- |
| "How does X work?"         | Claude Code / Oracolo NB-1         | Fast, grounded                         |
| Architecture decision      | **DeepSeek R1 671b** ($0.01/query) | Chain-of-thought, 27K+ reasoning chars |
| Complex cross-module debug | **DeepSeek R1 671b**               | Multi-step logic                       |
| Quick fix                  | Aider (DeepSeek V3)                | Fast, cheap                            |
| Code review                | Gemini Explore (1M ctx)            | Sees full codebase                     |

## 6. Integration Points

### ai-dispatch.sh Commands

- `oracolo` — NB-1 query (grounded citations)
- `oracolo-nb` — Any notebook query (tag-routed)
- `research` — Deep Research (web → NB-9)

### Federation Orchestrator

`orchestrator.py` can call `oracolo` as a pre-planning step for high-risk tasks.

### RAG Pipeline (Future — Phase 4-6)

NLM serves as Tier 2 Oracle for CAUTIOUS evidence scores (0.15-0.60), enriching Gemini Flash responses with normative citations.
