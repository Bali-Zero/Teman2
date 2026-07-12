# Nuzantara Autonomous Agents - V2 Enhanced Architecture

**Data:** 2026-03-14
**Versione:** 5.2.0 (Military-Grade)
**Status:** APPROVED for Implementation Strategy

## 1. Executive Summary

L'architettura V2 evolve dalla semplice gerarchia a un **Sistema Deterministico a Stati (LangGraph)** supportato da una **Memoria Episodica Ibrida (Qdrant)** e un **Layer di Auto-Guarigione (Fly.io NATS)**. Il principio cardine rimane "The Zantara Order": nessuna azione LLM senza validazione Pydantic + Business Rule Check.

## 2. Refined Hierarchy (The Command Chain)

### 🛡️ TECHNICAL COMMAND (Antigravity General)

- **Orchestrazione:** LangGraph State Machine con persistenza su Redis.
- **Self-Healing (Captain):** Middleware FastAPI che intercetta traceback -> Invio a NATS -> Analisi LLM -> Proposta Patch via GitHub PR.
- **Vector-Ops (Captain):** Hybrid Search (Dense + Sparse) su Qdrant. Obbligo di **Flat Payload** per ogni metadato.

### 🏛️ LEGAL & COMPLIANCE (Immigration General)

- **KBLI 2025 Expert (Captain):** Workflow deterministico. Non "indovina" il codice, ma interroga la collezione KBLI e valida l'output contro il JSON ufficiale BPS con score > 0.85.
- **Visa Automator (Commander):** Gestisce il "Plan-and-Execute" dei permessi. Se un documento manca, il grafo si ferma e attiva il _CRM Automator_.

### 📈 GROWTH & REVENUE (Marketing General)

- **Article Composer (Captain):** Utilizza la memoria episodica per scrivere articoli basati su successi reali (es. "Come abbiamo ottenuto un KITAS Investor in 7 giorni").
- **Predictor (Captain):** Analisi sentiment e scoring LTV per priorità di intervento degli agenti di supporto.

## 3. Core Technical Pillars (The Enhancement)

### 3.1. Orchestrazione: LangGraph Determinism

Sostituzione dei router autonomi con **StateGraphs**.

- **Vantaggio:** Prevenzione di loop infiniti e tracciabilità totale (Audit Log).
- **Fallback:** Ogni nodo ha un timeout e un percorso di errore verso l'intervento umano (Zero).

### 3.2. Memoria: Episodic Hybrid Storage

Utilizzo di Qdrant con configurazione doppia:

- **Dense (OpenAI):** Per la ricerca semantica del contesto.
- **Sparse (FastEmbed/BM25):** Per keyword critiche (codici KBLI, nomi di leggi).
- **RRF (Reciprocal Rank Fusion):** Per unificare i risultati in un'unica API call performante.

### 3.3. Validazione: The Zantara Order (SDV)

- **Pydantic v2 `model_validator`**: Validazione cross-field (es. Capitale sociale vs Nazionalità).
- **Evidence Scoring**: Ogni risposta legale deve citare la fonte (Articolo di legge/Regolamento). Se lo score di confidenza è `< 0.15`, il sistema fa **ABSTAIN**.

## 4. Resource Optimization (Fly.io 2GB RAM)

- **Stateless Agents:** Gli agenti non caricano modelli pesanti; usano API (OpenAI/Anthropic) e tool MCP.
- **Async-First:** Utilizzo massivo di `httpx` e `asyncio` per gestire centinaia di agenti concorrenti senza saturare la CPU.

---

## 5. Mappa Gerarchica (Overview)

1. **Macro Area: TECHNICAL COMMAND (Technical General)**
   - Micro: Infrastructure (Commander) -> Self-Healing (Captain), Performance (Captain)
   - Micro: Codebase (Commander) -> Feature Developer (Captain), Refactoring & Quality (Captain)

2. **Macro Area: INTELLIGENCE & RAG (Intelligence General)**
   - Micro: Regulatory Research (Commander) -> KBLI 2025 Expert (Captain), Law Scraper (Captain)
   - Micro: Knowledge Graph (Commander) -> Relationship Builder (Captain)

3. **Macro Area: LEGAL & COMPLIANCE (Immigration General)**
   - Micro: Visa Operations (Commander) -> KITAS Specialist (Captain), Document Validator (Captain)
   - Micro: Corporate (Commander) -> PT PMA Setup (Captain)

4. **Macro Area: GROWTH & REVENUE (Marketing General)**
   - Micro: Content Strategy (Commander) -> Article Composer (Captain), Newsletter Manager (Captain)
   - Micro: Client Success (Commander) -> Predictor (Captain)
