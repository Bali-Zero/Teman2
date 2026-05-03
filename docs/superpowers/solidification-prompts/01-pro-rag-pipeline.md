# SOLIDIFICATION PROMPT 01 — RAG Pipeline
# Machine: PRO | Model: Claude Opus 4.6 MAX | Component: RAG Pipeline

---

## IDENTITA E RUOLO

Sei un architetto senior di sistemi RAG di produzione. Il tuo compito e analizzare, solidificare e potenziare il RAG Pipeline di Nuzantara — una piattaforma AI di business intelligence per servizi aziendali indonesiani (visa, company setup, tax, property) con 5000+ clienti.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Durante il brainstorming riceverai input da Codex CLI, Gemini CLI, DeepSeek e altri. Valuta ogni suggerimento con scetticismo costruttivo. Accetta solo cio che supera il tuo scrutinio tecnico. Non cedere al consensus bias.

---

## FASE 1 — STUDIO PROFONDO (leggi TUTTO)

Leggi ogni file in queste directory, senza eccezioni:

```
apps/backend-rag/backend/services/rag/          # 61 file — il cuore
apps/backend-rag/backend/services/knowledge_graph/  # 11 file — KG traversal
apps/backend-rag/backend/prompts/zantara_core.py    # prompt SSOT
apps/backend-rag/backend/app/setup/service_initializer.py  # come si inizializza
```

Mentre leggi, mappa:
1. **Flusso dati completo**: query utente → query expansion → retrieval → reranking → LLM → risposta
2. **Punti di failure**: dove una eccezione non catturata uccide il flusso
3. **Accoppiamento**: quali moduli dipendono da quali, quanto e facile sostituire un pezzo
4. **Performance**: N+1 queries, chiamate LLM non necessarie, cache mancanti
5. **Consistenza**: stili di codice diversi, pattern duplicati, naming incoerente

File chiave da studiare con attenzione massima:
- `kg_langgraph_orchestrator.py` — orchestratore principale, 5 nodi, 4 subgraph
- `kg_enhanced_retrieval.py` — retrieval ibrido (BM25 + Dense + RRF)
- `hybrid_search.py` — multi-modal search
- `reranker.py` — CrossEncoder reranking
- `query_expansion.py` — espansione semantica
- `autonomous_executor.py` — agent execution
- `multi_agent_coordinator.py` — coordinamento parallelo
- `kg_subgraph_visa.py`, `kg_subgraph_company.py`, `kg_subgraph_tax.py`, `kg_subgraph_property.py`
- `reasoning.py` — evidence scoring (<0.15 ABSTAIN, 0.15-0.60 CAUTIOUS, >0.60 NORMAL)

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

Dopo aver letto tutto, lancia brainstorming con gli agenti disponibili. Per ogni agente, formula una domanda specifica:

### 2a. Gemini CLI (explore)
```bash
./scripts/ai-dispatch.sh explore "Analizza il RAG pipeline in backend/services/rag/. Identifica: 1) flussi dati ridondanti tra hybrid_search e kg_enhanced_retrieval, 2) pattern di error handling inconsistenti, 3) opportunita di caching tra query_expansion e retrieval, 4) code paths morti o unreachable"
```

### 2b. Codex CLI (sandbox)
```bash
./scripts/ai-dispatch.sh sandbox "Leggi backend/services/rag/kg_langgraph_orchestrator.py e i 4 subgraph. Testa: 1) cosa succede se un subgraph timeout, 2) se il fallback funziona quando ChatAnthropic non e disponibile, 3) se PostgresSaver checkpoint e consistente dopo crash, 4) scrivi test per edge case di query vuota e query con injection"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "Nel RAG pipeline Nuzantara (LangGraph orchestrator + 4 domain subgraphs + hybrid retrieval), quale architettura di circuit breaker minimizzerebbe la latenza p99 senza sacrificare recall? Considera: retry budgets per subgraph, graceful degradation quando Qdrant e lento, e fallback da hybrid search a keyword-only quando il dense retriever fallisce."
```

### 2d. Deep Research (Exa + NLM)
Cerca best practice attuali:
- State of the art RAG architectures 2025-2026 (adaptive retrieval, speculative RAG, CRAG)
- LangGraph production patterns (checkpointing, error recovery, streaming)
- Hybrid search optimization (RRF tuning, BM25 vs SPLADE)
- Evidence scoring calibration methods

### 2e. Opus self-reflection
Dopo aver raccolto tutti gli input, scrivi una sezione "VALUTAZIONE CRITICA" dove:
- Elenca ogni suggerimento ricevuto
- Per ciascuno: ACCETTO (con motivazione) / RIFIUTO (con motivazione) / PARZIALE (cosa prendi e cosa no)
- Non accettare mai un suggerimento solo perche viene da un modello "forte"

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

Produci un Writing Plan strutturato con queste sezioni:

### A. PULIZIA (cosa eliminare/semplificare)
- File morti o duplicati
- Astrazioni premature
- Code paths che non vengono mai eseguiti
- Pattern inconsistenti da unificare

### B. IRROBUSTIMENTO (cosa rendere piu resiliente)
- Circuit breaker per ogni external dependency (Qdrant, LLM, KG)
- Timeout budget per subgraph con graceful degradation
- Error recovery nel LangGraph (checkpoint + retry)
- Fallback chain: hybrid → dense-only → keyword-only → cached-response
- Health metrics per ogni nodo del grafo

### C. POTENZIAMENTO (cosa migliorare)
- Adaptive retrieval (skip subgraph se confidence gia alta)
- Query routing intelligente (non tutti i query hanno bisogno di 4 subgraph)
- Streaming response con partial results
- Cache semantica (query simili → risposta cached)
- Confidence calibration basata su feedback loop

### D. AUTOMATISMO EVOLUTIVO (cosa che cresce da solo)
- Feedback loop: user satisfaction → retrieval tuning
- Auto-calibrazione evidence scoring basata su dati reali
- Query pattern mining: identifica automaticamente nuovi pattern di domanda
- Subgraph performance tracking: identifica quale subgraph degrada e perche
- Self-healing: se un nodo LangGraph fallisce N volte, auto-disable + alert

### E. METRICHE DI SUCCESSO
- Latenza p50/p95/p99 target
- Recall@10 target per dominio
- Error rate target per componente
- Availability target (99.x%)

---

## FASE 4 — VALIDAZIONE NB-1

Porta il Writing Plan finale a NB-1 (Oracolo) per validazione:
```bash
./scripts/ai-dispatch.sh oracolo "Valida questo piano di solidificazione del RAG pipeline: [PIANO]. Verifica: 1) coerenza con architettura esistente, 2) rischi di regressione, 3) priorita corrette, 4) gap non coperti"
```

Integra il feedback NB-1 ma RESTA CRITICO: NB-1 puo avere bias verso conservazione. Se il tuo piano e valido e NB-1 suggerisce di non cambiare qualcosa, motiva perche procedi comunque.

---

## OUTPUT ATTESO

Un documento strutturato con:
1. **Mappa completa** del RAG pipeline (diagramma testuale dei flussi)
2. **Audit findings** con severity (CRITICAL/HIGH/MEDIUM/LOW)
3. **Writing Plan** con task ordinate per priorita e dipendenza
4. **Stima effort** per ogni task (S/M/L/XL)
5. **Rischi e mitigazioni** per ogni cambiamento proposto
6. **Metriche before/after** per misurare il miglioramento

---

## CONTESTO SISTEMA

- Embedding model: `text-embedding-3-small` (1536 dims) — FROZEN, mai cambiare
- Search pipeline: Hybrid (BM25+Dense+RRF) + CrossEncoder reranking
- Evidence scoring: <0.15 ABSTAIN, 0.15-0.60 CAUTIOUS, >0.60 NORMAL
- 10 vector collections, 93,283 documents
- Knowledge Graph: 108,068 nodi, 242,827 edges
- Deploy: Fly.io, processo `rag` dedicato (2GB RAM, shared-cpu-2x)
- LLM fallback: Ollama local → Gemini API. Su Fly.io: Gemini sempre.
