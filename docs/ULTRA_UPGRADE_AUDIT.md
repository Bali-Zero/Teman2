# Audit “Ultra Upgrade” (per componente)

Legenda:
- **OK** = buono, non urgente.
- **Near‑Ultra** = già competitivo, manca 1–2 upgrade chiave.
- **Needs Work** = limita qualità/affidabilità.
- **Ultra** = livello top globale.

## 1) Backend API (FastAPI monolite: `apps/backend-rag`)

**Stato:** Near‑Ultra  
**Perché è forte:** fail‑fast sui servizi critici, middleware security (auth/rate limit), osservabilità (Prometheus + tracing opzionale), router modulari.

**Upgrade Ultra:**
- “Contract clarity”: una sola “source of truth” su modelli AI usati (config + docs) e versioning API stabile.
- Ridurre import path misti (`app.*` vs `backend.*`) per mantenibilità e onboarding.
- Pool usage coerente: evitare `asyncpg.connect()` per-request su WhatsApp/IG, usare `db_pool`.
- Privacy-by-design: evitare log di payload completi; loggare solo id/event_type + hash.

## 2) RAG retrieval (Qdrant + routing + search)

**Stato:** Near‑Ultra  
**Punti forti:** collezioni verticali; routing; filtri (es. esclusione “dicabut”); cache TTL; base per parent/child e “golden router”.

**Upgrade Ultra:**
- **Hybrid retrieval** (BM25 + vector) + **reranker** (anche leggero) per i casi hard.
- **Evaluation loop continuo**: dataset + metriche (faithfulness, answer relevancy, citation coverage) in CI.
- **Semantic cache reale**: evitare placeholder embeddings; usare embedding reale o “keyed semantic hashes”.
- **Citation UX**: tornare sempre “evidence pack” (top‑N fonti) + “what changed” se aggiornamenti.

## 3) Orchestrazione agentica (`services/rag/agentic.py`)

**Stato:** OK → Near‑Ultra (dipende dal modello)  
**Punti forti:** tool calling, out‑of‑domain, post‑processing, gestione contesto, streaming con status/tool events.

**Upgrade Ultra:**
- **Model routing per difficoltà**: flash per 80%, “super/deep think” quando: bassa confidenza, alto rischio, multi‑step, user chiede “precision mode”.
- **Verifier pass**: secondo pass (anche più economico) che controlla: citazioni presenti, numeri coerenti, no hallucination.
- **Structured outputs** per alcuni domini (tax, compliance checklist) + schema validation.

## 4) Memoria, conversazioni e CRM

**Stato:** Near‑Ultra  
**Punti forti:** persistenza conversazioni, auto‑CRM, shared memory, endpoints ricchi.

**Upgrade Ultra:**
- Separare “memoria conversazionale” (short-term) e “memoria fattuale” (long-term) con politiche di retention e consenso.
- “Human handoff” nativo: assegnazione conversazioni, note interne, SLA, escalation.
- Event sourcing / audit trail per compliance (chi ha visto cosa e quando).

## 5) Multi‑canale (WhatsApp/Instagram/Web)

**Stato:** OK  
**Punti forti:** integrazione già presente, background task, unified router.

**Upgrade Ultra:**
- Normalizzare i canali su un’unica pipeline (id utente, session, consent, rate limit, templates).
- “Reply quality guardrails” per canali: lunghezza massima, chunking messaggi, fallback templates.

## 6) Observability + Reliability

**Stato:** Near‑Ultra  
**Punti forti:** metrics, tracing opzionale, health monitor, error monitoring.

**Upgrade Ultra:**
- SLO/SLA concreti (p95 latency, error budget, quota monitor).
- Dashboard per: retrieval quality, model routing, cache hit rate, citation coverage.
- Load shedding: degradare tool expensive prima di degradare answer quality.

## 7) Frontend webapp (`apps/mouth`)

**Stato:** Near‑Ultra  
**Punti forti:** UI moderna, streaming, step/status UI, fonti/citazioni, websocket, micro‑interazioni.

**Upgrade Ultra:**
- Streaming “robusto”: parser SSE con buffering e gestione boundary (evita perdita token).
- “Stop / Regenerate / Retry with Deep Think” come controlli utente.
- “Intent UI”: quick actions contestuali e follow-up suggeriti, non generici.

## 8) Satellite apps (intel scraper, media, evaluator)

**Stato:** OK (strategico)  
**Punti forti:** supply chain contenuti + eval (RAGAS) + media engine. Questo è un moltiplicatore.

**Upgrade Ultra:**
- Collegare direttamente l’evaluator a CI e a un “quality dashboard”.
- Far convergere duplicati (es. `apps/kb` e `apps/scraper`) o chiarire ownership.

