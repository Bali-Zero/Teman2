# SOLIDIFICATION PROMPT 04 — LLM Integration Layer
# Machine: PRO | Model: Claude Opus 4.6 MAX | Component: LLM Integration

---

## IDENTITA E RUOLO

Sei un architetto di sistemi LLM multi-provider di produzione. Analizzi il layer di integrazione LLM di Nuzantara — 6 provider (Gemini, DeepSeek, Vertex AI, OpenRouter, Ollama, OpenAI), pattern Ollama-first con fallback cloud. Devi unificare, solidificare e rendere questo layer auto-ottimizzante.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Non farti influenzare dal bias "piu provider = meglio". Valuta se ogni provider serve davvero.

---

## FASE 1 — STUDIO PROFONDO

Leggi TUTTO in:

```
apps/backend-rag/backend/llm/                          # 3,422 righe totali
  ollama_client.py                                     # Ollama locale — CRITICAL: think:false per Qwen
  zantara_ai_client.py                                 # Client unificato principale
  client.py                                            # Client wrapper
  prompt_manager.py                                    # Template management
  token_estimator.py                                   # Token counting
  config.py                                            # Configurazione LLM
  fallback_messages.py                                 # Risposte fallback
  retry_handler.py                                     # Retry logic
  genai_client.py                                      # Google GenAI
  providers/                                           # ollama.py, gemini.py, vertex.py, deepseek.py, openrouter.py
  adapters/                                            # base.py, gemini.py, registry.py

apps/backend-rag/backend/services/llm_clients/         # 1,307 righe
  gemini_service.py                                    # 349 righe
  openrouter_client.py                                 # 371 righe
  deepseek_client.py                                   # 221 righe
  vertex_ai_service.py                                 # 112 righe
  pricing.py                                           # 237 righe — cost tracking
```

Mappa:
1. **Provider topology**: chi chiama chi, overlap tra `llm/` e `services/llm_clients/`
2. **Fallback chain**: Ollama → Gemini → ? Esplicita o implicita?
3. **Client lifecycle**: come vengono creati/riusati i client HTTP (REGOLA: mai AsyncClient in loop)
4. **Token budget**: come viene gestito il limite di token per request
5. **Cost tracking**: come si traccia il costo per provider/per query
6. **Model routing**: come si sceglie quale model per quale task
7. **Duplicazione**: codice duplicato tra llm/ e services/llm_clients/

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

### 2a. Gemini CLI (explore)
```bash
./scripts/ai-dispatch.sh explore "Mappa le dipendenze tra backend/llm/ e backend/services/llm_clients/. Identifica: 1) codice duplicato tra i due package, 2) client HTTP creati dentro loop/metodi (violazione regola golden), 3) pattern di fallback inconsistenti, 4) model selection hardcoded vs configurabile"
```

### 2b. Codex CLI (sandbox)
```bash
./scripts/ai-dispatch.sh sandbox "Testa i client LLM in backend/llm/providers/: 1) cosa succede con timeout di rete per ogni provider, 2) retry handler funziona con rate limit 429?, 3) token_estimator e accurato per ogni model?, 4) ollama_client con think:false — verifica che funzioni su native /api/chat e NON su OpenAI-compat"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "Sistema LLM con 6 provider (Ollama locale, Gemini, DeepSeek, Vertex AI, OpenRouter, OpenAI). Pattern attuale: Ollama-first con fallback cloud. Domande: 1) E meglio un router unificato o adapter per-provider? 2) Come implementare cost-aware routing (scegli il provider piu economico che soddisfa quality threshold)? 3) Come tracciare quality per provider senza human feedback? 4) Come gestire graceful degradation quando Ollama e sovraccarico (M4 Pro 48GB, qwen3.5:27b usa ~20GB)?"
```

### 2d. Deep Research
- LLM gateway/router architectures 2025-2026 (LiteLLM, Portkey, custom)
- Cost-aware LLM routing patterns
- Token budget management across providers
- Ollama production patterns (health checks, model preloading, memory management)
- LLM observability: traces, latency, quality metrics

### 2e. Opus self-reflection — VALUTAZIONE CRITICA

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- Unificare `llm/` e `services/llm_clients/` — un solo package, zero duplicazione
- Eliminare provider non usati in produzione
- Consolidare adapter pattern: un'interfaccia, N implementazioni
- Rimuovere fallback_messages hardcoded se non servono

### B. IRROBUSTIMENTO
- Client HTTP persistente per provider (mai creare in loop)
- Circuit breaker per provider: 3 fallimenti → skip per 60s
- Timeout budget: max 30s per LLM call, con progressive timeout (10s → 20s → 30s)
- Retry con exponential backoff + jitter per rate limit
- Health check per Ollama: verifica model loaded prima di mandare request
- Graceful degradation chain esplicita e configurabile

### C. POTENZIAMENTO
- Router unificato: `LLMRouter.complete(task_type, messages)` sceglie automaticamente
- Cost tracking real-time: costo per query, per sessione, per giorno
- Quality tracking: latenza, token efficiency, error rate per provider
- Semantic caching: stessa domanda (embedding similarity > 0.95) → risposta cached
- Model selection intelligente basata su task (classification → Haiku, reasoning → Opus)

### D. AUTOMATISMO EVOLUTIVO
- Auto-routing: basato su metriche storiche, il sistema impara quale provider e migliore per quale task
- Cost alert: se costo giornaliero supera threshold → alert + switch a provider economico
- Model health dashboard: metriche per provider aggiornate ogni ora
- Auto-fallback learning: se un fallback viene usato troppo spesso, promuovilo a primary
- Ollama memory monitor: se RAM > 80%, scarica modelli non usati da 1h

### E. METRICHE
- Latenza p50/p95 per provider
- Cost per 1k tokens per provider
- Fallback rate (target: < 5%)
- Error rate per provider (target: < 1%)
- Cache hit rate (target: > 30% per query simili)

---

## FASE 4 — VALIDAZIONE NB-1

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano solidificazione LLM Integration: [PIANO]. Focus: 1) compatibilita con RAG pipeline esistente, 2) impatto su latenza user-facing, 3) rischi di regressione nel pattern Ollama-first, 4) cost model realistico"
```

---

## CONTESTO

- MODEL_FAST=qwen3.5:9b (<0.5s), MODEL_HEAVY=deepseek-r1:32b (~30s), MODEL_KG=qwen3.5:27b (~5-8s), MODEL_JSON=gemma3:12b
- Vision: qwen2.5vl:7b UNICO (qwen3.5 Q4_K_M strips vision weights)
- Ollama: think:false NON funziona via OpenAI-compat API → fix 2-step in ollama_chat_kg()
- Pro: M4 Pro 48GB — Ollama usa ~20-25GB con modelli caricati
- Fly.io: Gemini sempre (no Ollama)
- Embedding: text-embedding-3-small (1536 dims) — FROZEN
- Golden Rule #10: NEVER httpx.AsyncClient() in methods/loops
