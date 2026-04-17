# Air-3 — GraphRAG 2.0 Completion (C estesa 12-24h)

## Obiettivo

Completare i 3 gap residui di GraphRAG 2.0 deployed (2026-04-07): entity linker full populate, trimodal RRF weight>0, community summaries.

## Contesto

- Macchina: Air (cwd `/Users/antonellosiano/Projects/nuzantara`)
- Memory "GraphRAG 2.0": 5 phases DEPLOYED, 6,310 clusters Louvain, KG 108K nodes 243K edges
- Next-step list da memory:
  1. Populate entity linker full
  2. Activate trimodal RRF weight>0
  3. Generate community summaries
- KG collection: `legal_unified_hybrid_hybrid` (68,519 total), Qdrant Cloud key in memory
- DB tunnel: `postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag`
- Target: `apps/backend-rag/backend/` (kg, queries, rag)

## Scope SÌ (3 subtask coordinati)

### Subtask 1 — Entity Linker full populate (4-6h)

- Identificare entity linker script/module
- Run su intera collection KG (108K nodes)
- Batch size adeguato (evitare OOM su Air 16GB)
- Idempotent (resume-friendly)
- Telegram digest progress ogni 10K entity

### Subtask 2 — Trimodal RRF weight>0 activation (3-5h)

- Localizzare config RRF (Reciprocal Rank Fusion) in rag pipeline
- Test A/B weight 0 → 0.3 → 0.5 su set benchmark query
- Metriche MRR, NDCG@10, Recall@50
- Report decision (weight scelto + motivazione)

### Subtask 3 — Community summaries generation (4-8h)

- 6,310 cluster Louvain → generare summary testuale per ciascuno
- LLM: Ollama qwen3.5:9b locale preferito (cost $0), fallback Gemini
- Batch resume-friendly, persist in PG table `community_summaries`
- Telegram progress ogni 500 cluster

## Scope NO

- NON cambiare algoritmo Louvain (già deployed stabile)
- NON re-popolare KG da zero
- NON toccare migration KG esistenti
- NON merge main, NON deploy

## Deliverables attesi

1. Branch `graphrag/completion-gaps` con commit per subtask
2. Entity linker: log counts prima/dopo in `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-3-entity-linker.log`
3. RRF: benchmark report `docs/graphrag-rrf-weight-decision.md`
4. Community summaries: DB table popolata + sample 20 summaries in log
5. Report unificato `docs/graphrag-v2-completion-2026-04-17.md`
6. Log finale `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-3.log`

## Stop conditions

- OOM su Air → ridurre batch size, retry, se fallisce 3 volte → stop
- Qdrant Cloud rate limit → backoff esponenziale, se persiste → stop
- Tempo > 20h → checkpoint, stop hard 24h
- Se subtask 1 bloccato >6h → skippa al 2 poi 3

## Skills

1. `superpowers:using-superpowers`
2. `superpowers:using-git-worktrees`
3. `superpowers:systematic-debugging`
4. `superpowers:verification-before-completion`

## Prompt da incollare (Air via tmux)

```
Sessione Air C estesa 12-24h. Obiettivo: completare 3 gap GraphRAG 2.0.

Subtask:
1. Entity linker full populate (108K nodes, batch resume-safe, Telegram progress)
2. Trimodal RRF weight>0 (benchmark 0/0.3/0.5, MRR+NDCG+Recall, decision report)
3. Community summaries (6310 cluster Louvain, Ollama qwen3.5:9b, PG persist)

Worktree .worktrees/graphrag-completion branch graphrag/completion-gaps da main.

NO merge, NO deploy. Checkpoint ogni 4h. Stop hard 24h.
Log: docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-3.log

DB tunnel localhost:15432 nuzantara_rag. Qdrant Cloud key in MEMORY.md.

Usa superpowers:systematic-debugging. Inizia da subtask 1.
```
