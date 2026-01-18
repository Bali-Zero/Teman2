# Agent Test LLM Configuration

## LLM utilizzato negli Agent Tests

### Local Model (NEW - Recommended for Tests)

**Ollama Qwen 2.5** (`qwen2.5:latest`)

- **Provider**: Ollama (locale)
- **URL**: `http://localhost:11434` (default)
- **Caratteristiche**: Locale, veloce, privato, zero cost
- **Uso**: **Raccomandato per test** - nessun costo API, nessun rate limit
- **Configurazione**: `OLLAMA_URL` e `OLLAMA_MODEL` env vars

### Primary Model (Production)

**Google Gemini 3 Flash Preview** (`gemini-3-flash-preview`)

- **Tier**: `TIER_FLASH = 0`
- **Caratteristiche**: Fast, cost-effective, production-ready
- **Uso**: Modello principale per produzione

### Fallback Model

**Google Gemini 2.0 Flash** (`gemini-2.0-flash`)

- **Tier**: `TIER_FALLBACK = 3`
- **Caratteristiche**: Stable, reliable fallback
- **Uso**: Attivato quando Gemini 3 Flash non è disponibile

### Final Fallback

**OpenRouter** (ModelTier.RAG)

- **Provider**: OpenRouter API
- **Caratteristiche**: Third-party fallback per alta disponibilità
- **Uso**: Attivato quando tutti i modelli Gemini sono non disponibili

## Architettura LLM Gateway

```
LLMGateway
├── Local (NEW): Ollama Qwen 2.5 (localhost:11434)
│   └── Zero cost, no rate limits - IDEAL FOR TESTS
├── Primary: gemini-3-flash-preview
│   └── Fallback: gemini-2.0-flash
│       └── Final: OpenRouter (RAG tier)
```

**Note**: Ollama è disponibile come provider ma non ancora integrato nel fallback chain di LLMGateway. Può essere usato direttamente tramite `OllamaProvider`.

## Configurazione nei Test

### Test Mock

I test usano `mock_llm_gateway` per evitare chiamate API reali:

- Mock del `LLMGateway`
- Mock delle risposte Gemini
- Mock del fallback OpenRouter

### Test Reali (quando eseguiti)

Quando i test vengono eseguiti senza mock:

1. Prova `gemini-3-flash-preview` (primary)
2. Se fallisce → `gemini-2.0-flash` (fallback)
3. Se fallisce → OpenRouter (final fallback)

## File di Configurazione

**File principale**: `apps/backend-rag/backend/services/rag/agentic/llm_gateway.py`

```python
# Model Tier Constants
TIER_FLASH = 0  # gemini-3-flash-preview
TIER_FALLBACK = 3  # gemini-2.0-flash

# Model names
self.model_name_flash = "gemini-3-flash-preview"  # Primary
self.model_name_fallback = "gemini-2.0-flash"  # Fallback
```

## Test Files che usano LLM

1. `test_llm_gateway_comprehensive.py` - Test completi LLMGateway
2. `test_reasoning.py` - Test reasoning (usa mock LLM)
3. `test_orchestrator_core.py` - Test orchestrator (usa mock LLM)
4. `test_agentic_tools_comprehensive.py` - Test tools (usa mock LLM)

## Note

- I test **non fanno chiamate API reali** per default (usano mock)
- Per test reali, rimuovere i mock e configurare `GOOGLE_API_KEY`
- OpenRouter richiede `OPENROUTER_API_KEY` per fallback reale
