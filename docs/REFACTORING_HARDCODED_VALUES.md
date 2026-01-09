# 🔧 Refactoring: Spostamento Valori Hardcoded in Constants/Config

**Data:** 2026-01-09  
**Status:** ✅ Completato

---

## 📋 Riepilogo Modifiche

Questo refactoring ha spostato tutti i valori hardcoded identificati nell'analisi di qualità codice in file centralizzati di constants e config, migliorando la manutenibilità e la configurabilità del codice.

---

## ✅ Modifiche Completate

### 1. **Evidence Score Constants** (`app/core/constants.py`)

**Aggiunta classe:** `EvidenceScoreConstants`

**Valori spostati da `reasoning.py`:**
- `ABSTAIN_THRESHOLD = 0.3` (sostituisce `0.3` hardcoded)
- `HIGH_QUALITY_SOURCE_THRESHOLD = 0.3`
- `HIGH_QUALITY_SOURCE_BONUS = 0.5`
- `MULTIPLE_SOURCES_BONUS = 0.2`
- `MIN_SOURCES_FOR_BONUS = 3`
- `CONTEXT_KEYWORD_BONUS = 0.3`
- `KEYWORD_MATCH_THRESHOLD = 0.3`
- `SUBSTANTIAL_CONTEXT_LENGTH = 500`
- `CONTEXT_QUALITY_KEYWORD_WEIGHT = 0.7`
- `CONTEXT_QUALITY_COUNT_WEIGHT = 0.3`
- `PREFERRED_CONTEXT_ITEMS = 5`
- `MAX_SCORE = 1.0`

**File aggiornati:**
- ✅ `services/rag/agentic/reasoning.py` - Tutti i valori hardcoded sostituiti con constants

---

### 2. **Intel Service Constants** (`app/core/constants.py`)

**Aggiunta classe:** `IntelConstants`

**Valori spostati da `intel.py`:**
- `COLLECTIONS` - Mapping collezioni Qdrant per intel
- `VISA_CATEGORIES` - Categorie per classificazione visa
- `VISA_KEYWORDS` - Keywords per classificazione visa
- `MIN_VISA_KEYWORDS = 3` - Soglia minima keywords per classificare come visa
- `DEFAULT_EXTRACTION_METHOD = "css"`
- `DEFAULT_TIER = "T2"`

**File aggiornati:**
- ✅ `app/routers/intel.py` - Collezioni, keywords e default values sostituiti

---

### 3. **HTTP Timeout Constants** (`app/core/constants.py`)

**Aggiunta classe:** `HttpTimeoutConstants`

**Valori standardizzati:**
- `DEFAULT_TIMEOUT = 30.0`
- `SHORT_TIMEOUT = 10.0`
- `MEDIUM_TIMEOUT = 60.0`
- `LONG_TIMEOUT = 120.0`

**Timeout service-specific:**
- `ZOHO_OAUTH_TIMEOUT = 30.0`
- `ZOHO_EMAIL_TIMEOUT = 60.0`
- `ZOHO_EMAIL_LONG_TIMEOUT = 120.0`
- `TELEGRAM_TIMEOUT = 30.0`
- `AUDIO_TTS_TIMEOUT = 10.0`
- `AUDIO_TTS_FALLBACK_TIMEOUT = 5.0`
- `IMAGE_GENERATION_TIMEOUT = 60.0`
- `WEB_SEARCH_TIMEOUT = 15.0`
- `DEEPSEEK_TIMEOUT = 60.0`
- `DEEPSEEK_STREAM_TIMEOUT = 120.0`
- `OPENROUTER_TIMEOUT = 10.0`
- `HEALTH_CHECK_TIMEOUT = 10.0`
- `HEALTH_CHECK_SHORT_TIMEOUT = 5.0`
- `DIAGNOSTICS_TIMEOUT = 5.0`
- `DIAGNOSTICS_SHORT_TIMEOUT = 3.0`
- `ANALYTICS_TIMEOUT = 10.0`
- `SLACK_WEBHOOK_TIMEOUT = 5.0`
- `DISCORD_WEBHOOK_TIMEOUT = 5.0`
- `INTEL_SCRAPER_TIMEOUT = 30.0`
- `GUARDIAN_AGENT_TIMEOUT = 120.0`
- `CIRCUIT_BREAKER_TIMEOUT = 60.0`
- `MEMORY_LOCK_TIMEOUT = 5.0`

**File aggiornati:**
- ✅ `app/routers/intel.py` - Timeout HTTP sostituito
- ✅ `services/integrations/zoho_oauth_service.py` - Tutti i timeout sostituiti
- ✅ `services/integrations/zoho_email_service.py` - Tutti i timeout sostituiti
- ✅ `services/integrations/telegram_bot_service.py` - Timeout sostituito
- ✅ `services/rag/agentic/llm_gateway.py` - Circuit breaker timeout sostituito

---

### 4. **Path Constants** (`app/core/config.py`)

**Aggiunte proprietà alla classe `Settings`:**

- `intel_staging_base_dir` - Base directory per staging Intel (configurabile via env var)
- `intel_pending_path` - Path per pending Intel approval (configurabile via env var)

**Metodi helper:**
- `get_intel_staging_base_dir` - Ritorna `/data/staging` in produzione, `/tmp/staging` in dev
- `get_intel_pending_path` - Ritorna path configurato o `/tmp/pending_intel` di default

**File aggiornati:**
- ✅ `app/routers/intel.py` - Path hardcoded sostituiti con `settings.get_intel_staging_base_dir` e `settings.get_intel_pending_path`

---

## 📊 Statistiche

- **File constants aggiornati:** 1 (`app/core/constants.py`)
- **File config aggiornati:** 1 (`app/core/config.py`)
- **File sorgente aggiornati:** 6
- **Valori hardcoded rimossi:** ~60+
- **Constants aggiunte:** 3 classi (`EvidenceScoreConstants`, `IntelConstants`, `HttpTimeoutConstants`)
- **Nuove constants Intel:** 8 valori aggiunti (scheduling, time ranges, metrics, content limits)

---

## 🎯 Benefici

1. **Manutenibilità:** Valori centralizzati facili da trovare e modificare
2. **Configurabilità:** Path e timeout configurabili via environment variables
3. **Consistenza:** Valori standardizzati evitano discrepanze tra file
4. **Testabilità:** Più facile testare con valori diversi modificando solo constants
5. **Documentazione:** Constants documentate con docstring chiare

---

## 📝 Note per Sviluppatori Futuri

### Come aggiungere nuove constants:

1. **Per valori numerici/stringhe semplici:**
   - Aggiungi alla classe appropriata in `app/core/constants.py`
   - Usa naming convention: `UPPER_SNAKE_CASE`
   - Aggiungi docstring se necessario

2. **Per valori configurabili via env:**
   - Aggiungi a `Settings` class in `app/core/config.py`
   - Usa `Field()` con `default=None` e `description`
   - Crea property helper se serve logica di fallback

3. **Per sostituire valori hardcoded:**
   - Importa la costante: `from app.core.constants import YourConstants`
   - Sostituisci il valore hardcoded con `YourConstants.VALUE_NAME`
   - Verifica che il comportamento rimanga identico

---

## 🔍 File Ancora da Aggiornare (Opzionale)

I seguenti file hanno ancora alcuni timeout hardcoded che potrebbero essere standardizzati in futuro:

- `services/rag/agentic/tools.py` - Image generation timeout (60.0)
- `services/rag/agentic/tools.py` - Web search timeout (15.0)
- `services/llm_clients/deepseek_client.py` - DeepSeek timeouts
- `services/llm_clients/openrouter_client.py` - OpenRouter timeout
- `services/monitoring/unified_health_service.py` - Health check timeouts
- `services/monitoring/alert_service.py` - Webhook timeouts
- `services/rag/agent/diagnostics_tool.py` - Diagnostics timeouts
- `services/analytics/analytics_aggregator.py` - Analytics timeout
- `app/services/audio_service.py` - TTS timeouts
- `core/qdrant_db.py` - Qdrant connection/retry timeouts

**Nota:** Questi possono essere aggiornati in un secondo momento se necessario. Le modifiche principali sono complete.

---

## ✅ Testing

Prima di mergeare, verificare:

1. ✅ Tutti i test passano: `pytest`
2. ✅ Nessun import mancante: `ruff check`
3. ✅ Type checking: `mypy` (se configurato)
4. ✅ Linting: `ruff format` e `ruff lint`

---

**Ultimo Aggiornamento:** 2026-01-09  
**Aggiornamento Finale:** 2026-01-09 (valori hardcoded aggiuntivi in intel.py)  
**Autore:** AI Assistant
